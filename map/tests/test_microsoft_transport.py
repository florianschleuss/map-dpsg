"""Offline tests: all external HTTP is mocked; no tenant credentials are used."""
import io,json,socket,ssl,unittest
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
from urllib.error import HTTPError,URLError
from urllib.parse import parse_qs
from map import microsoft_mail as ms

class MicrosoftTransportTests(unittest.TestCase):
    def setUp(self):
        ms._TOKEN_CACHE.clear()
        self.config=SimpleNamespace(tenant_id='11111111-1111-1111-1111-111111111111',client_id='22222222-2222-2222-2222-222222222222',from_email='map@example.org')
    def test_token_request_uses_fixed_tenant_endpoint_and_graph_scope(self):
        with patch.object(ms,'request_json',return_value={'access_token':'opaque-test-token','expires_in':3600}) as request:
            self.assertEqual(ms.access_token(self.config,'test-secret'),'opaque-test-token')
        args,kwargs=request.call_args
        self.assertEqual(args[0],'https://login.microsoftonline.com/'+self.config.tenant_id+'/oauth2/v2.0/token')
        self.assertEqual(kwargs['form'],{'client_id':self.config.client_id,'client_secret':'test-secret','grant_type':'client_credentials','scope':'https://graph.microsoft.com/.default'})
    def test_cache_reuses_token_and_fresh_probe_refetches(self):
        with patch.object(ms,'request_json',return_value={'access_token':'token','expires_in':3600}) as request:
            for unused in range(2):ms.access_token(self.config,'secret')
            self.assertEqual(request.call_count,1)
            ms.access_token(self.config,'secret',fresh=True);self.assertEqual(request.call_count,2)
    def test_expired_or_changed_secret_does_not_reuse_token(self):
        with patch.object(ms,'request_json',return_value={'access_token':'token','expires_in':0}) as request:
            ms.access_token(self.config,'old');ms.access_token(self.config,'old');ms.access_token(self.config,'new')
            self.assertEqual(request.call_count,3)
    def test_cache_is_bounded(self):
        with patch.object(ms,'request_json',return_value={'access_token':'token','expires_in':3600}):
            for n in range(20):ms.access_token(self.config,str(n))
        self.assertLessEqual(len(ms._TOKEN_CACHE),8)
        self.assertNotIn('secret',repr(ms._TOKEN_CACHE))
    def test_invalid_tenant_or_missing_secret_never_calls_network(self):
        for field in ['tenant_id','client_id']:
            original=getattr(self.config,field);setattr(self.config,field,'../../attacker')
            with patch.object(ms,'request_json') as request,self.assertRaises(ms.MicrosoftMailError):ms.access_token(self.config,'secret')
            request.assert_not_called();setattr(self.config,field,original)
        with self.assertRaises(ms.MicrosoftMailError):ms.access_token(self.config,'')
    def test_token_response_must_contain_nonempty_string(self):
        for response in [{},{'access_token':None},{'access_token':42}]:
            with patch.object(ms,'request_json',return_value=response),self.assertRaises(ms.MicrosoftMailError):ms.access_token(self.config,'secret',fresh=True)
    def test_send_uses_selected_mailbox_text_and_sent_copy(self):
        with patch.object(ms,'access_token',return_value='token'),patch.object(ms,'request_json',return_value={}) as request:
            self.assertEqual(ms.send_graph(self.config,'secret','Betreff','Text',['parent@example.org']),1)
        args,kwargs=request.call_args
        self.assertEqual(args[0],'https://graph.microsoft.com/v1.0/users/map%40example.org/sendMail')
        self.assertEqual(kwargs['body']['message']['body']['contentType'],'HTML')
        self.assertIn('Text',kwargs['body']['message']['body']['content'])
        self.assertIn('font-size:12px',kwargs['body']['message']['body']['content'])
        self.assertEqual(kwargs['body']['message']['from']['emailAddress']['name'],'Anmeldungsverwaltung')
        self.assertTrue(kwargs['body']['saveToSentItems'])
        self.assertEqual(kwargs['body']['message']['toRecipients'],[{'emailAddress':{'address':'parent@example.org'}}])
    def test_rejected_token_is_refreshed_once(self):
        with patch.object(ms,'access_token',return_value='token') as token,patch.object(ms,'request_json',side_effect=[ms.MicrosoftMailError('ms_auth'),{}]) as request:
            self.assertEqual(ms.send_graph(self.config,'secret','a','b',['a@example.org']),1)
        self.assertEqual(request.call_count,2);self.assertTrue(token.call_args.kwargs['fresh'])
    def test_permission_denial_is_not_retried_as_token_failure(self):
        with patch.object(ms,'access_token',return_value='token') as token,patch.object(ms,'request_json',side_effect=ms.MicrosoftMailError('ms_mailbox_permission')) as request,self.assertRaises(ms.MicrosoftMailError):
            ms.send_graph(self.config,'secret','a','b',['a@example.org'])
        self.assertEqual(request.call_count,1);self.assertEqual(token.call_count,1)
    def test_unknown_provider_text_and_secrets_are_never_exposed(self):
        for payload in [{'error':'invalid_client','error_description':'PRIVATE-SECRET','error_codes':[7000215]},{'error':{'untrusted':'PRIVATE-SECRET'}},{'error':['PRIVATE-SECRET']}]:
            error=ms.classify_http_error(400,payload,'token')
            self.assertNotIn('PRIVATE-SECRET',str(error));self.assertNotIn('error_description',str(error))
        self.assertIn('AADSTS7000215',str(ms.classify_http_error(400,{'error':'invalid_client','error_codes':[7000215]},'token')))
    def test_expired_secret_has_specific_german_message(self):
        error=ms.classify_http_error(401,{'error':'invalid_client','error_codes':[7000222]},'token')
        self.assertEqual(error.code,'ms_secret_expired');self.assertIn('abgelaufen',str(error))
    def test_graph_error_categories_and_bounded_retry_delay(self):
        for status,code in [(401,'ms_auth'),(403,'ms_mailbox_permission'),(404,'ms_mailbox_missing'),(429,'ms_throttled'),(503,'ms_unavailable')]:
            self.assertEqual(ms.classify_http_error(status,{},'send').code,code)
        self.assertEqual(ms.classify_http_error(429,{},'send',{'Retry-After':'99999'}).retry_after,3600)
        self.assertIsNone(ms.classify_http_error(429,{},'send',{'Retry-After':'unsafe'}).retry_after)
    def test_redirect_handler_never_follows_credentials(self):
        self.assertIsNone(ms.NoRedirect().redirect_request(None,None,302,'',{},'https://attacker.invalid'))
        self.assertEqual(ms.classify_http_error(302,{},'token').code,'ms_redirect')
    def test_http_request_encodes_secret_in_post_body(self):
        response=MagicMock();response.__enter__.return_value=response;response.status=200;response.read.return_value=b'{"access_token":"ok"}'
        opener=MagicMock();opener.open.return_value=response
        with patch.object(ms,'build_opener',return_value=opener):
            self.assertEqual(ms.request_json('https://login.microsoftonline.com/test',phase='token',form={'client_secret':'a+b&c'}),{'access_token':'ok'})
        request=opener.open.call_args.args[0]
        self.assertNotIn('a+b',request.full_url);self.assertEqual(parse_qs(request.data.decode())['client_secret'],['a+b&c'])
        self.assertEqual(opener.open.call_args.kwargs['timeout'],10)
    def test_only_202_is_accepted_for_send(self):
        for status in [200,202]:
            response=MagicMock();response.__enter__.return_value=response;response.status=status;response.read.return_value=b'{}'
            opener=MagicMock();opener.open.return_value=response
            with patch.object(ms,'build_opener',return_value=opener):
                if status==202:self.assertEqual(ms.request_json('https://graph.microsoft.com/test',phase='send',body={},token='token'),{})
                else:
                    with self.assertRaises(ms.MicrosoftMailError):ms.request_json('https://graph.microsoft.com/test',phase='send',body={})
    def test_network_tls_and_malformed_json_have_safe_messages(self):
        for exception,code in [(URLError('PRIVATE'),'ms_network'),(URLError(ssl.SSLError('PRIVATE')),'ms_tls'),(socket.timeout('PRIVATE'),'ms_network')]:
            opener=MagicMock();opener.open.side_effect=exception
            with patch.object(ms,'build_opener',return_value=opener),self.assertRaises(ms.MicrosoftMailError) as caught:ms.request_json('https://graph.microsoft.com/test',phase='send',body={})
            self.assertEqual(caught.exception.code,code);self.assertNotIn('PRIVATE',str(caught.exception))
        response=MagicMock();response.__enter__.return_value=response;response.status=200;response.read.return_value=b'invalid'
        opener=MagicMock();opener.open.return_value=response
        with patch.object(ms,'build_opener',return_value=opener),self.assertRaises(ms.MicrosoftMailError):ms.request_json('https://login.microsoftonline.com/test',phase='token',form={})
    def test_http_error_is_redacted(self):
        error=HTTPError('https://graph.microsoft.com/test',403,'PRIVATE',{},io.BytesIO(b'{"error":{"message":"PRIVATE"}}'))
        opener=MagicMock();opener.open.side_effect=error
        with patch.object(ms,'build_opener',return_value=opener),self.assertRaises(ms.MicrosoftMailError) as caught:ms.request_json('https://graph.microsoft.com/test',phase='send',body={})
        self.assertEqual(caught.exception.code,'ms_mailbox_permission');self.assertNotIn('PRIVATE',str(caught.exception))

if __name__=='__main__':unittest.main(verbosity=2)

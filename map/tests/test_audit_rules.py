import unittest
from map.security_rules import client_ip,numeric_pk,bounded_confirmation_hours,normalized_login

class SecurityRuleTests(unittest.TestCase):
    def test_untrusted_peer_cannot_spoof_forwarded_address(self):
        self.assertEqual(client_ip('203.0.113.5','198.51.100.8',['172.18.0.2/32']),'203.0.113.5')
    def test_trusted_proxy_exposes_actual_client(self):
        self.assertEqual(client_ip('172.18.0.2','198.51.100.8',['172.18.0.2/32']),'198.51.100.8')
    def test_forwarded_chain_uses_nearest_untrusted_hop(self):
        self.assertEqual(client_ip('172.18.0.2','192.0.2.99,198.51.100.8',['172.18.0.2/32']),'198.51.100.8')
    def test_two_trusted_proxies_are_removed_from_right(self):
        self.assertEqual(client_ip('172.18.0.2','198.51.100.8,172.18.0.3',['172.18.0.0/24']),'198.51.100.8')
    def test_malformed_forwarding_falls_back_to_peer(self):
        for value in ['unknown','198.51.100.8, garbage','198.51.100.8:1234','a'*1025,','.join(['198.51.100.8']*11)]:
            self.assertEqual(client_ip('172.18.0.2',value,['172.18.0.2']),'172.18.0.2')
    def test_ipv6_and_missing_peer_are_safe(self):
        self.assertEqual(client_ip('::1','2001:db8::9',['::1/128']),'2001:db8::9')
        self.assertEqual(client_ip('','198.51.100.8',['127.0.0.1']),'unknown')
    def test_no_implicit_private_network_trust(self):
        self.assertEqual(client_ip('10.0.0.2','198.51.100.8',[]),'10.0.0.2')
    def test_bad_proxy_configuration_does_not_grant_trust(self):
        self.assertEqual(client_ip('203.0.113.5','198.51.100.8',['bad-cidr']),'203.0.113.5')
    def test_unicode_and_oversized_database_ids_are_rejected(self):
        for value in ['²','١٢','１２','1.0','-1','0','9'*1000,2**63,None,True]:self.assertIsNone(numeric_pk(value))
    def test_valid_database_ids_are_preserved(self):
        for value in [1,'12',2**63-1]:self.assertEqual(numeric_pk(value),int(value))
    def test_historical_confirmation_values_cannot_overflow_datetime(self):
        self.assertEqual(bounded_confirmation_hours(2**31-1),8760)
        self.assertEqual(bounded_confirmation_hours(-10),1)
        self.assertEqual(bounded_confirmation_hours('invalid'),48)
    def test_compatible_unicode_login_forms_share_rate_limit_key(self):
        self.assertEqual(normalized_login('Ａｄｍｉｎ'),normalized_login('Admin'))
        self.assertEqual(normalized_login(' Admin '),'admin')
        self.assertLessEqual(len(normalized_login('x'*100000)),150)

if __name__=='__main__':unittest.main()

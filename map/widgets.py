import json
from django import forms
from .models import ScoutGroup, FormTemplate

class QuickDateTimeWidget(forms.DateTimeInput):
    input_type = 'datetime-local'
    template_name = 'map/widgets/datetime.html'
    def __init__(self, attrs=None):
        super().__init__(attrs=attrs,format='%Y-%m-%dT%H:%M')

class GroupLimitsWidget(forms.Widget):
    template_name = 'map/widgets/group_limits.html'
    def get_context(self,name,value,attrs):
        context=super().get_context(name,value,attrs)
        try: selected=json.loads(value) if isinstance(value,str) else value or {}
        except (TypeError,ValueError): selected={}
        if not isinstance(selected,dict): selected={}
        groups=ScoutGroup.objects.order_by('name')
        if getattr(self,'allowed_ids',None) is not None: groups=groups.filter(pk__in=self.allowed_ids)
        context['widget']['groups']=[{'id':str(group.pk),'name':group.name,'selected':str(group.pk) in selected,'capacity':selected.get(str(group.pk),20)} for group in groups]
        context['widget']['value']=json.dumps(selected,ensure_ascii=False)
        return context

class BuilderWidget(forms.Widget):
    template_name = 'map/widgets/builder.html'
    def get_context(self,name,value,attrs):
        from .forms import template_schema
        context=super().get_context(name,value,attrs)
        templates=FormTemplate.objects.prefetch_related('modules__fields').all()
        if hasattr(self,'allowed_template_ids'):templates=templates.filter(pk__in=self.allowed_template_ids)
        context['widget']['templates_data']={str(template.pk):template_schema(template) for template in templates}
        from django.conf import settings
        context['widget']['photo_label']=settings.MAP_PHOTO_DISPLAY_LABEL
        context['widget']['json_id']=(attrs or {}).get('id',name)+'_templates'
        return context


class TemplatePickerWidget(forms.Select):
    template_name='map/widgets/template_picker.html'
    def __init__(self,event_id=None,can_create=False,**kwargs):
        self.event_id=event_id;self.can_create=can_create
        super().__init__(**kwargs)
    def get_context(self,name,value,attrs):
        from django.urls import reverse
        from urllib.parse import urlencode
        context=super().get_context(name,value,attrs)
        selected=str(value or '')
        query=urlencode({'event':self.event_id,'zurueck':reverse('event_settings',args=[self.event_id])}) if self.event_id else ''
        context['widget'].update(event_id=self.event_id,can_create=self.can_create,edit_url=(reverse('map_form_builder',args=[selected])+'?'+query) if selected.isdigit() else '',create_url=reverse('map_form_builder_new')+'?'+query,options_url=reverse('template_options',args=[self.event_id]) if self.event_id else '')
        return context

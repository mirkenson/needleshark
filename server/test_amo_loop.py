import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
import urllib.error
sys.path.insert(0, str(Path(__file__).parent))
import amo_loop
import amo_delivery as amo
from test_amo_delivery import ENV


class StructuredTests(unittest.TestCase):
    def setUp(self):
        self.config = amo.configuration(dict(ENV, AMO_STRUCTURED_FIELDS='1', AMO_SOURCE_FIELD_ID='25'))
        self.lead = dict(id='12345678-1234-4234-8234-123456789abc', order_id=1, created_at='2026-10-28T00:00:00Z', name='ТЕСТ', contact='qa@example.invalid', question='Тестовый комментарий', source_path='/napravleniya/chehly/', business_intent='custom', business_direction='chehly', ym_client_id='12345678901234567890',utm_source='yandex',utm_medium='cpc')
        self.client=MagicMock(); self.client.list.return_value=[]
        self.save=MagicMock(return_value=True)

    def test_structured_fields_preserve_native_client_and_omit_wall_of_text(self):
        fields=amo.payload(self.lead,self.config)['custom_fields_values']
        bycode={f.get('field_code'):f['values'][0]['value'] for f in fields}
        self.assertEqual(bycode['NS_YM_CLIENT_ID'],bycode['_YM_UID'])
        self.assertEqual(bycode['NS_PAGE'],'https://needle-shark.ru/napravleniya/chehly/')
        self.assertEqual(bycode['NS_DIRECTION'],'Изделие на заказ')
        self.assertEqual(bycode['NS_PRODUCT'],'Чехлы на технику и оборудование')
        self.assertNotIn(22,[f.get('field_id') for f in fields])
        self.assertNotIn('Тестовый комментарий',json.dumps(fields,ensure_ascii=False))
        self.assertIn('Тестовый комментарий',amo.note_text(self.lead))

    def test_missing_tracking_is_not_invented(self):
        fields=amo.structured_fields({'source_path':'/'},self.config)
        self.assertIn('неизвестен',fields[0]['values'][0]['value'])
        self.assertNotIn('NS_YM_CLIENT_ID',[x.get('field_code') for x in fields])

    def test_note_is_fenced_then_saved(self):
        self.client.request.return_value={'_embedded':{'notes':[{'id':99}]}}
        self.assertEqual(amo.ensure_note({'lead':self.lead},123,self.config,self.save,self.client),123)
        self.assertEqual(self.save.call_args_list[0].kwargs,{'note_started':True})
        self.assertEqual(self.save.call_args_list[1].kwargs,{'amo_note_id':99})

    def test_lost_note_response_reconciles_without_post(self):
        job={'lead':self.lead,'note_started':True}
        with self.assertRaisesRegex(amo.DeliveryError,'amo_note_unconfirmed'):
            amo.ensure_note(job,123,self.config,self.save,self.client)
        self.client.request.assert_not_called()
        self.client.list.return_value=[{'id':99,'note_type':'common','params':{'text':amo.note_text(self.lead)}}]
        amo.ensure_note(job,123,self.config,self.save,self.client)
        self.client.request.assert_not_called()
        self.save.assert_called_once_with(job,amo_note_id=99)

    def test_saved_deal_still_gets_note_without_creating_deal(self):
        self.client.request.return_value={'_embedded':{'notes':[{'id':99}]}}
        amo.send({'lead':self.lead,'amo_lead_id':123},self.config,self.save,self.client)
        self.assertEqual(self.client.request.call_args.args[1],'/api/v4/leads/123/notes')


class LoopTests(unittest.TestCase):
    def test_only_authorized_mention_is_active_and_link_is_real(self):
        body=amo_loop.message(123,'@channel [click](https://evil.example)\n@daniil','https://example.amocrm.ru')
        self.assertEqual(body['text'].count('@daniil'),1)
        self.assertNotIn('@channel',body['text'])
        self.assertIn('🚨🚨🚨 НОВАЯ ЗАЯВКА 🚨🚨🚨',body['text'])
        self.assertIn('https://example.amocrm.ru/leads/detail/123',body['text'])
        self.assertNotIn('[click](https://evil.example)',body['text'])

    def test_discovery_deduplicates_chat_and_ignores_old_deals(self):
        client=MagicMock()
        def listing(entity, params):
            return ([{'id':1,'created_at':110,'name':'form'},{'id':2,'created_at':1,'name':'old'}] if entity=='leads' else
                [{'_embedded':{'leads':[{'id':1},{'id':3}]}}])
        client.list.side_effect=listing
        client.request.return_value={'id':3,'created_at':120,'name':'chat'}
        rows=amo_loop.discover(client,100,200)
        self.assertEqual([r['id'] for r in rows],[1,3])
        client.request.assert_called_once()

    def test_config_does_not_enable_old_form_notifications(self):
        self.assertIsNone(amo_loop.configuration(ENV))
        env=dict(ENV,AMO_LOOP_WEBHOOK_URL='https://neesha.loop.ru/hooks/'+'a'*26,AMO_LOOP_STARTED_AT='1793190000')
        self.assertEqual(amo_loop.configuration(env)['start'],1793190000)
        with self.assertRaises(ValueError):
            amo_loop.configuration(dict(env,LOOP_LEADS_WEBHOOK_URL=env['AMO_LOOP_WEBHOOK_URL']))

    @patch('amo_loop.urllib.request.build_opener')
    def test_only_confirmed_ok_is_sent_and_timeout_is_not_retried(self,build):
        response=build.return_value.open.return_value.__enter__.return_value
        response.status=200; response.read.return_value=b'ok'
        self.assertEqual(amo_loop.post('https://neesha.loop.ru/hooks/'+'a'*26,{'text':'test'}),('sent',None))
        build.return_value.open.side_effect=TimeoutError()
        self.assertEqual(amo_loop.post('https://neesha.loop.ru/hooks/'+'a'*26,{'text':'test'})[0],'uncertain')
        build.return_value.open.side_effect=urllib.error.HTTPError('private',429,'',{},None)
        self.assertEqual(amo_loop.post('https://neesha.loop.ru/hooks/'+'a'*26,{'text':'test'})[0],'pending')

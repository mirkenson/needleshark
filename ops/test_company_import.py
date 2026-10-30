"""Whole importer retries against a fake CRM, never a real account."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT/'server'))
import amo_delivery, company_profile, delivery_store
spec=importlib.util.spec_from_file_location('company_import',Path(__file__).with_name('import-companies.py'))
imp=importlib.util.module_from_spec(spec);spec.loader.exec_module(imp)


class FakeDB:
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def cursor(self):return self
    def execute(self,*args):pass
    def fetchone(self):return (1,)


class RetryTests(unittest.TestCase):
    def exercise(self,lose,save_before_error=True):
        specs=company_profile.FIELD_SPECS+[('PHONE','Телефон','multitext'),('EMAIL','Email','multitext'),('WEB','Web','url'),('CITY','Город','text')]
        fields=[dict(id=i,code=code,name=name,type=kind,enums=[dict(id=101,value='Robotics')] if kind=='multiselect' else
                     [dict(id=201+j,value=v) for j,v in enumerate(company_profile.OUTREACH_STATUSES)] if kind=='select' else None)
                for i,(code,name,kind) in enumerate(specs,1)]
        row=dict(key='synthetic',name='Synthetic Company',sites='example.invalid',city='',activity='Manufacturing',
                 specialist='',general='desk@example.invalid',supplier='',priority_channel='',sources='https://example.invalid',
                 directions=['Robotics'],expected_id=None,offer='Cover',offer_note='Synthetic offer note')
        remote=[];notes=[];writes=[];failed=[]
        def metadata(payload):
            result=[]
            for v in payload:
                field=next(f for f in fields if f['id']==v['field_id'])
                result.append(dict(v,field_code=field['code'],field_name=field['name']))
            return result
        def request(_client,method,path,payload=None):
            path=urlsplit(path).path
            if method=='GET':
                if path=='/api/v4/account':return {'id':1}
                if path.endswith('/custom_fields'):return {'_embedded':{'custom_fields':copy.deepcopy(fields)}}
                if path.endswith('/notes'):return {'_embedded':{'notes':copy.deepcopy(notes)}}
                if path=='/api/v4/companies':return {'_embedded':{'companies':copy.deepcopy(remote)}}
                if path=='/api/v4/companies/123':return copy.deepcopy(remote[0])
                raise AssertionError(path)
            writes.append((method,path))
            should_fail=path.endswith(lose) and not failed
            if should_fail:failed.append(True)
            if not should_fail or save_before_error:
                if path=='/api/v4/companies':
                    remote.append(dict(id=123,name=payload[0]['name'],created_at=int(time.time()),updated_at=int(time.time()),
                                       custom_fields_values=metadata(payload[0]['custom_fields_values']),_embedded={}))
                    result={'_embedded':{'companies':[{'id':123}]}}
                elif path.endswith('/notes'):
                    notes.append(dict(id=456,**payload[0]));result={'_embedded':{'notes':notes}}
                else:raise AssertionError('unexpected mutation:'+path)
            if should_fail:raise amo_delivery.DeliveryError('amo_network_error')
            return result
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);(path/'input.json').write_text(json.dumps(dict(account_id=1,source_url='https://example.invalid/source',companies=[row])))
            args=SimpleNamespace(input=str(path/'input.json'),state=str(path/'state.json'),server_dir=str(ROOT/'server'),apply=True)
            with patch.object(amo_delivery,'configuration',return_value={}),patch.object(amo_delivery.Client,'request',new=request),patch.object(delivery_store,'connection',return_value=FakeDB()),contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(amo_delivery.DeliveryError):imp.run(args)
                if save_before_error:
                    imp.run(args);imp.run(args)
                    self.assertEqual(len(remote),1);self.assertEqual(len(notes),1)
                    self.assertTrue(json.loads((path/'state.json').read_text())['rows']['synthetic']['verified'])
                else:
                    with self.assertRaisesRegex(ValueError,'unconfirmed'):imp.run(args)
            self.assertEqual(sum(p=='/api/v4/companies' for _,p in writes),1)
            self.assertLessEqual(sum(p.endswith('/notes') for _,p in writes),1)
            self.assertTrue(all(p.startswith('/api/v4/companies') for _,p in writes))

    def test_lost_company_ack_is_read_back_without_recreation(self):self.exercise('/companies')
    def test_lost_note_ack_is_read_back_without_duplicate(self):self.exercise('/notes')
    def test_unknown_company_outcome_is_never_blindly_replayed(self):self.exercise('/companies',False)
    def test_unknown_note_outcome_is_never_blindly_replayed(self):self.exercise('/notes',False)

if __name__=='__main__':unittest.main()

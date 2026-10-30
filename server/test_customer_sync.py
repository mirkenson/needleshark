import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import unittest
from unittest.mock import patch
import customer_registry as registry
import customer_sync
import unisender_sync as uni

class SyncTests(unittest.TestCase):
    def test_identifiers_and_no_speculative_email_rewrite(self):
        self.assertEqual(registry.normalize('phone','8 (999) 000-00-00'),'79990000000')
        self.assertEqual(registry.normalize('email',' A.B+tag@EXAMPLE.COM '),'a.b+tag@example.com')
        self.assertIsNone(registry.normalize('phone','12345'))
    def test_strong_synthetic_label_only(self):
        self.assertTrue(customer_sync.clearly_test({'name':'QA — не обрабатывать'}))
        self.assertFalse(customer_sync.clearly_test({'name':'Тестирование образца для производства'}))
    def test_directory_never_enables_new_recipient(self):
        p=uni.payload({'email':'x@example.com','name':'x','NS_CUSTOMER_ID':1,'NS_PERMISSION':'allowed'},42,None)
        self.assertEqual(p['contact_status'],'disabled')
    def test_existing_unsubscribe_and_lists_not_overwritten(self):
        remote={'email':{'status':'unsubscribed'},'lists':[{'id':42,'status':'unsubscribed'}]}
        p=uni.payload({'email':'x@example.com','name':'x','NS_CUSTOMER_ID':1},42,remote)
        self.assertNotIn('contact_status',p);self.assertNotIn('email_list_ids',p)
        remote['email']['status']='active'
        self.assertNotIn('email_list_ids',uni.payload({'email':'x@example.com','name':'x'},42,remote))
    def test_partial_import_is_not_success(self):
        class Fake:
            def call(self,*a):return {'total':1,'inserted':0,'updated':0,'invalid':1}
        with self.assertRaises(uni.ApiError):uni.import_one(Fake(),{'email':'x@example.com'})
    def test_messaging_api_forbidden(self):
        c=uni.Client('test-key-with-no-real-credential')
        with self.assertRaises(uni.ApiError):c.call('sendEmail',{})
    def test_readback_required(self):
        p={'NS_CUSTOMER_ID':'123','email':'x@example.com','Name':'x','email_list_ids':'42'}
        remote={'fields':{'NS_CUSTOMER_ID':'123','Name':'x'},'lists':[]}
        self.assertFalse(uni.matches(remote,p,42));remote['lists']=[{'id':42}]
        self.assertTrue(uni.matches(remote,p,42))

if __name__=='__main__':unittest.main()

import copy
import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parent))
import company_profile as profile
spec = importlib.util.spec_from_file_location('company_import', Path(__file__).parents[1]/'ops/import-companies.py')
imp = importlib.util.module_from_spec(spec); spec.loader.exec_module(imp)


class CompanyProfileTests(unittest.TestCase):
    def setUp(self):
        self.mapping = {}
        specs = profile.FIELD_SPECS + [('CITY', 'Город', 'text'), ('WEB','Web','url'),
                                      ('EMAIL','Email','multitext'), ('PHONE','Телефон','multitext')]
        for i,(code,name,kind) in enumerate(specs,1):
            self.mapping[code] = dict(id=i,code=code,name=name,type=kind)
        self.mapping['NS_COMPANY_DIRECTIONS']['enums'] = [dict(id=101,value='Robotics'),dict(id=102,value='Lab')]
        self.mapping['NS_OUTREACH_STATUS']['enums'] = [dict(id=i+201,value=v) for i,v in enumerate(profile.OUTREACH_STATUSES)]
        self.row = dict(name='Synthetic Company',sites='example.invalid',city='New City',activity='New activity',
                        specialist='Technical: tech@example.invalid',general='info@example.invalid; +7 (999) 000-00-00',
                        supplier='',priority_channel='tech@example.invalid',sources='https://example.invalid/contact',
                        directions=['Lab'])

    def field(self,code,value):
        f=self.mapping[code]
        return dict(field_id=f['id'],field_code=code,values=[dict(value=value)])

    def test_additive_merge_keeps_manager_values_and_is_repeatable(self):
        old = dict(id=42,name='Manager name',custom_fields_values=[
            self.field('CITY','Old City'),self.field('WEB','https://existing.invalid'),
            self.field('NS_OUTREACH_STATUS','Контакт был'),self.field('NS_COMPANY_DIRECTIONS','Robotics'),
            self.field('EMAIL','old@example.invalid'),self.field('PHONE','8 (999) 000-00-00'),
            dict(field_id=999,values=[dict(value='Untouched tax ID')])])
        original = copy.deepcopy(old)
        delta = imp.changes(self.row,old,self.mapping,profile.domains)
        self.assertEqual(old,original)
        self.assertNotIn(self.mapping['NS_OUTREACH_STATUS']['id'],[f['field_id'] for f in delta])
        self.assertNotIn(self.mapping['WEB']['id'],[f['field_id'] for f in delta])
        self.assertNotIn(self.mapping['PHONE']['id'],[f['field_id'] for f in delta])
        combined={f['field_id']:f for f in old['custom_fields_values']}
        combined.update({f['field_id']:f for f in delta})
        old['custom_fields_values']=list(combined.values())
        self.assertEqual(imp.changes(self.row,old,self.mapping,profile.domains),[])
        self.assertEqual(combined[999],original['custom_fields_values'][-1])
        self.assertEqual(combined[self.mapping['CITY']['id']]['values'][0]['value'],'Old City\n\nNew City')
        self.assertEqual(len(combined[self.mapping['EMAIL']['id']]['values']),2)

    def test_matching_is_exact_and_ambiguous_stops(self):
        existing=dict(id=1,name='Different name',custom_fields_values=[self.field('WEB','https://www.example.invalid')])
        self.assertEqual(imp.match_company(self.row,[existing],profile.domains)['id'],1)
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            imp.match_company(self.row,[existing,dict(existing,id=2)],profile.domains)
        self.assertIsNone(imp.match_company(dict(self.row,sites='sub.example.invalid'),[existing],profile.domains))

    def test_unknown_contact_history_not_false_negative(self):
        code=self.mapping['NS_OUTREACH_STATUS']['id']
        new=imp.changes(self.row,None,self.mapping,profile.domains)
        old=imp.changes(self.row,{'id':1},self.mapping,profile.domains)
        self.assertEqual(next(f['values'][0]['value'] for f in new if f['field_id']==code),'Контакта не было')
        self.assertEqual(next(f['values'][0]['value'] for f in old if f['field_id']==code),'Не уточнено')

    def test_channels_do_not_guess_shorthand_and_keep_extensions(self):
        self.assertEqual(imp.email_values('rostov@, moscow@ and full@example.invalid'),['full@example.invalid'])
        self.assertEqual(imp.phone_values('+7 999 000-00-00 доб. 119; 49-26-43'),['+7 999 000-00-00 доб. 119'])

    def test_projection_preserves_text_but_not_person_identity(self):
        row=dict(custom_fields_values=[self.field('NS_SPECIALIST_CONTACTS','Person, technical desk'),
                                       self.field('NS_COMPANY_DIRECTIONS','Lab'),self.field('EMAIL','info@example.invalid')])
        result=profile.projection(row)
        self.assertEqual(result['directions'],['Lab'])
        self.assertEqual(result['specialist_contacts'],'Person, technical desk')
        self.assertNotIn('customer_id',result)

if __name__=='__main__':unittest.main()

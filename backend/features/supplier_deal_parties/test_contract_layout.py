"""Synthetic column-layout regressions; no customer documents or identities."""
import unittest
from .contract_extraction import extract_contract_parties

IDENTITIES = {'supplier': '7709876543', 'buyer': '7701234567', 'payer': '7701234567'}
TEXT = '''Договор поставки
Общество «Материалы» (ООО «Материалы»), именуемое «Поставщик», в лице
Генерального директора Иванова Петра Сергеевича, действующего на основании Устава,
и Общество «Объект» (ООО «Объект»), именуемое «Покупатель», в лице
директора Петровой Анны Ивановны, действующей на основании доверенности № 5,
заключили настоящий договор.
12. ЮРИДИЧЕСКИЕ АДРЕСА, РЕКВИЗИТЫ И ПОДПИСИ СТОРОН
ПОСТАВЩИК
ООО «Материалы»
ОГРН 1234567890123
ИНН/КПП 7709876543/770901001
Юридический адрес:
123456, Московская область,
г. Пример, ул. Первая, д. 2
Почтовый адрес:
999999, г. Другой, а/я 17
р/с 40702810400000000001
в Филиале «Тестовый»
ПАО «Банк», г. Москва
к/с 30101810100000000001
БИК 044525411
Тел./факс 8(495)123-45-67
е-mail: materials@example.org
Поставщик
ПОКУПАТЕЛЬ
ООО «Объект»
ОГРН 1234567890999
ИНН/КПП 7701234567/770101001
Юридический адрес: 654321, г. Пример, ул. Вторая, д. 3
р/с 40702810400000000002
ООО «Другой банк», г. Москва
к/с 30101810100000000002
БИК 044525104
Тел./факс 8-495-987-65-43
e-mail:client@example.org
'''

class LayoutTests(unittest.TestCase):
    def extract(self,text=TEXT):
        return extract_contract_parties(text,IDENTITIES)['parties']

    def test_column_blocks_extract_multiline_requisites_without_postal_address(self):
        result=self.extract()
        supplier=result['supplier']['fields'];buyer=result['buyer']['fields']
        self.assertEqual(supplier['ogrn']['value'],'1234567890123')
        self.assertEqual(buyer['ogrn']['value'],'1234567890999')
        self.assertEqual(supplier['legalAddress']['value'],'123456, Московская область, г. Пример, ул. Первая, д. 2')
        self.assertEqual(supplier['bankName']['value'],'в Филиале «Тестовый» ПАО «Банк», г. Москва')
        self.assertEqual(buyer['bankName']['value'],'ООО «Другой банк», г. Москва')
        self.assertEqual(supplier['phone']['value'],'8(495)123-45-67')
        self.assertEqual(supplier['email']['value'],'materials@example.org')
        self.assertEqual(result['payer']['fields'],{})
        for party in result.values():
            for field in party['fields'].values():
                self.assertTrue('\n'.join(TEXT.splitlines()[field['line']-1:]).startswith(field['quote']))

    def test_preamble_signer_tied_to_named_role_and_matching_organization(self):
        result=self.extract()
        self.assertEqual(result['supplier']['fields']['directorName']['value'],'Иванова Петра Сергеевича')
        self.assertEqual(result['buyer']['fields']['directorName']['value'],'Петровой Анны Ивановны')
        self.assertEqual(result['supplier']['fields']['basis']['value'],'Устава')

    def test_wrong_role_identity_does_not_import_requisites_or_signer(self):
        result=self.extract(TEXT.replace('7709876543','7709999999'))
        self.assertEqual(result['supplier']['fields'],{})

    def test_no_signer_when_preamble_names_different_organization(self):
        result=self.extract(TEXT.replace('Общество «Материалы» (ООО «Материалы»)', 'Общество «Чужая фирма»'))
        self.assertNotIn('directorName',result['supplier']['fields'])

    def test_conflicting_repeated_columns_are_not_resolved_by_order(self):
        result=self.extract(TEXT+'\nПОСТАВЩИК\nИНН/КПП 7709876543/770901001\nБИК 044525999')
        self.assertEqual(result['supplier']['fields'],{})

    def test_mixed_columns_do_not_attach_unowned_ogrn(self):
        text='РЕКВИЗИТЫ СТОРОН\nПОСТАВЩИК ПОКУПАТЕЛЬ\nОГРН 1234567890123 ОГРН 1234567890999\nИНН/КПП 7709876543/770901001\nр/с 40702810400000000001'
        self.assertNotIn('ogrn',self.extract(text)['supplier']['fields'])

    def test_unknown_identity_interrupts_column(self):
        result=self.extract(TEXT.replace('Юридический адрес:\n','ИНН/КПП 7709999999/770901001\nЮридический адрес:\n',1))
        self.assertEqual(result['supplier']['fields'],{})
    def test_malformed_duplicate_account_is_not_ignored(self):
        result=self.extract(TEXT.replace('БИК 044525411','р/с 4070281O400000000001\nБИК 044525411'))
        self.assertNotIn('rs',result['supplier']['fields'])

    def test_separately_labelled_foreign_inn_invalidates_column(self):
        result=self.extract(TEXT.replace('ОГРН 1234567890123','ИНН: 7709999999\nОГРН 1234567890123'))
        self.assertEqual(result['supplier']['fields'],{})


class ColumnGeometryTests(unittest.TestCase):
    def test_only_distinct_aligned_headers_can_split_page(self):
        from .contract_document_worker import column_boundary
        header='text\tconf\tleft\ttop\twidth\n'
        good=header+'ПОСТАВЩИК\t95\t300\t1000\t200\nПОКУПАТЕЛЬ\t95\t1000\t1005\t200\n'
        self.assertEqual(column_boundary(good,1500,2200),(750,992))
        for bad in (good.replace('1005','1500'),good.replace('ПОКУПАТЕЛЬ','ПОСТАВЩИК'),good.replace('95','40')):
            self.assertIsNone(column_boundary(bad,1500,2200))

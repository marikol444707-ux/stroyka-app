import unittest
from datetime import datetime, timezone

from .rfq_email_content import build_rfq_email


class RfqEmailContentTests(unittest.TestCase):
    def test_names_customer_deadline_and_reply_channel(self):
        subject,body,sender_name,reply_to=build_rfq_email({
            'id':71,'companyName':'ООО «АльянсПромСтрой»','companyEmail':'office@example.com',
            'project':'Лицей 4','workPackage':'Электрика','itemLines':['- Кабель: 100 м'],
            'deliveryAddress':'г. Кисловодск, ул. Школьная, 4',
            'contactName':'Иван Петров','contactEmail':'buyer@example.com','contactPhone':'+7 900 000-00-00',
            'notes':'Позвонить перед доставкой','responseDueAt':datetime(2026,9,30,9,15,tzinfo=timezone.utc),
        },'ООО ВИСТ')
        self.assertEqual(subject,'Запрос КП №71 от ООО «АльянсПромСтрой»')
        self.assertIn('ООО «АльянсПромСтрой» приглашает вас',body)
        self.assertIn('Срок ответа: 30.09.2026, 12:15 (МСК)',body)
        self.assertIn('ответьте на это письмо',body)
        self.assertIn('Кабель: 100 м',body)
        self.assertIn('Адрес доставки: г. Кисловодск, ул. Школьная, 4',body)
        self.assertIn('Контакт по заявке: Иван Петров · buyer@example.com · +7 900 000-00-00',body)
        self.assertEqual(sender_name,'Стройка · ООО «АльянсПромСтрой»')
        self.assertEqual(reply_to,'buyer@example.com')

    def test_missing_optional_company_contact_is_not_invented(self):
        subject,body,sender_name,reply_to=build_rfq_email({
            'id':5,'companyName':'Компания Б','companyEmail':'','project':'',
            'workPackage':'','itemLines':[],'notes':'','responseDueAt':None,
        })
        self.assertEqual(subject,'Запрос КП №5 от Компания Б')
        self.assertNotIn('ответьте на это письмо',body)
        self.assertNotIn('Срок ответа:',body)
        self.assertEqual(sender_name,'Стройка · Компания Б')
        self.assertEqual(reply_to,'')

    def test_header_values_are_flat_and_bounded(self):
        subject,_,sender_name,reply_to=build_rfq_email({
            'id':9,'companyName':'Компания\r\nBcc: victim@example.com'+'x'*200,
            'companyEmail':'bad\n@example.com','project':'Объект','workPackage':'Раздел',
            'itemLines':[],'notes':'','responseDueAt':None,
        })
        self.assertNotIn('\n',subject+sender_name+reply_to)
        self.assertLessEqual(len(sender_name),78)
        self.assertEqual(reply_to,'')


if __name__ == '__main__':
    unittest.main()

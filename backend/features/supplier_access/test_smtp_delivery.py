import smtplib,unittest
from unittest.mock import MagicMock
from .smtp_delivery import send_rfq_email

class SMTPDeliveryTests(unittest.TestCase):
    def send(self,smtp):
        return send_rfq_email('test@example.com','subject','body',host='localhost',port=25,
            sender='no@example.com',username='',password='',ssl=False,tls=False,factory=lambda *a,**k:smtp)
    def test_success_even_when_quit_loses_connection(self):
        smtp=MagicMock();smtp.send_message.return_value={};smtp.quit.side_effect=OSError()
        self.assertEqual(self.send(smtp)['outcome'],'accepted')
    def test_confirmed_rejection_is_retryable(self):
        smtp=MagicMock();smtp.send_message.side_effect=smtplib.SMTPDataError(550,b'private')
        result=self.send(smtp);self.assertEqual(result['outcome'],'rejected');self.assertNotIn('private',str(result))
    def test_unknown_acknowledgement_is_not_retryable(self):
        smtp=MagicMock();smtp.send_message.side_effect=TimeoutError()
        self.assertEqual(self.send(smtp)['outcome'],'unconfirmed')
    def test_failure_before_data_is_safe_to_retry(self):
        result=send_rfq_email('t@example.com','s','b',host='localhost',port=25,sender='n@example.com',
            username='',password='',ssl=False,tls=False,factory=MagicMock(side_effect=ConnectionError()))
        self.assertEqual(result['outcome'],'rejected')

    def test_partial_acceptance_is_never_retryable(self):
        smtp=MagicMock();smtp.send_message.return_value={'refused@example.com':(550,b'private')}
        self.assertEqual(self.send(smtp)['outcome'],'unconfirmed')
    def test_multiple_recipients_rejected_before_network(self):
        factory=MagicMock()
        result=send_rfq_email('a@example.com,b@example.com','s','b',host='localhost',port=25,
            sender='n@example.com',username='',password='',ssl=False,tls=False,factory=factory)
        self.assertEqual(result['outcome'],'rejected');factory.assert_not_called()

    def test_transactional_headers_keep_aligned_envelope_and_company_reply(self):
        smtp=MagicMock();smtp.send_message.return_value={}
        result=send_rfq_email('supplier@example.com','Запрос КП','Текст',
            host='localhost',port=25,sender='noreply@stroyka26.pro',username='',password='',
            ssl=False,tls=False,factory=lambda *a,**k:smtp,
            sender_name='Стройка · АльянсПромСтрой',reply_to='office@customer.example')
        self.assertEqual(result['outcome'],'accepted')
        message=smtp.send_message.call_args.args[0]
        self.assertEqual(str(message['From']),'Стройка · АльянсПромСтрой <noreply@stroyka26.pro>')
        self.assertEqual(str(message['Reply-To']),'office@customer.example')
        self.assertEqual(str(message['Auto-Submitted']),'auto-generated')
        self.assertTrue(message['Date'])
        self.assertTrue(str(message['Message-ID']).endswith('@stroyka26.pro>'))
        self.assertEqual(smtp.send_message.call_args.kwargs['from_addr'],'noreply@stroyka26.pro')

    def test_invalid_reply_to_is_omitted_without_changing_envelope(self):
        smtp=MagicMock();smtp.send_message.return_value={}
        result=send_rfq_email('supplier@example.com','s','b',host='localhost',port=25,
            sender='noreply@stroyka26.pro',username='',password='',ssl=False,tls=False,
            factory=lambda *a,**k:smtp,sender_name='Стройка',reply_to='a@example.com,b@example.com')
        self.assertEqual(result['outcome'],'accepted')
        message=smtp.send_message.call_args.args[0]
        self.assertIsNone(message['Reply-To'])

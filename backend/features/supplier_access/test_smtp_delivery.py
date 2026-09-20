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

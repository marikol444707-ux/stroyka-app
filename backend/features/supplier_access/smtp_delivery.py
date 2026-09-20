"""RFQ-specific SMTP result; never expose addresses or provider exception text."""
import smtplib
from email.message import EmailMessage
from email.utils import getaddresses


def send_rfq_email(to, subject, body, *, host, port, sender, username, password,
                   ssl, tls, factory=None):
    smtp = None
    sending = False
    try:
        recipients = getaddresses([to])
        if len(recipients) != 1 or not recipients[0][1] or '@' not in recipients[0][1]:
            return {'outcome': 'rejected', 'code': 'recipient_rejected'}
        message = EmailMessage()
        message['From'], message['To'], message['Subject'] = sender, to, subject
        message.set_content(body)
        smtp = (factory or (smtplib.SMTP_SSL if ssl else smtplib.SMTP))(host, port, timeout=20)
        if tls and not ssl:
            smtp.starttls()
        if username and password:
            smtp.login(username, password)
        sending = True
        refused = smtp.send_message(message, to_addrs=[recipients[0][1]])
        if refused != {}:
            return {'outcome': 'unconfirmed', 'code': 'acknowledgement_unknown'}
        return {'outcome': 'accepted', 'code': 'smtp_accepted'}
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPDataError):
        return {'outcome': 'rejected', 'code': 'smtp_rejected'}
    except Exception:
        return {'outcome': 'unconfirmed' if sending else 'rejected',
                'code': 'acknowledgement_unknown' if sending else 'connection_or_auth_failed'}
    finally:
        if smtp is not None:
            try:
                smtp.quit()
            except Exception:
                try:
                    smtp.close()
                except Exception:
                    pass

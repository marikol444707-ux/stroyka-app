"""RFQ-specific SMTP result; never expose addresses or provider exception text."""
import smtplib
from email.message import EmailMessage
from email.headerregistry import Address
from email.utils import formatdate, getaddresses, make_msgid


def _single_address(value):
    raw = str(value or '').strip()
    if not raw or '\r' in raw or '\n' in raw:
        return ''
    parsed = getaddresses([raw])
    return parsed[0][1] if len(parsed) == 1 and parsed[0][1] and '@' in parsed[0][1] else ''


def send_rfq_email(to, subject, body, *, host, port, sender, username, password,
                   ssl, tls, factory=None, sender_name='', reply_to=''):
    smtp = None
    sending = False
    try:
        recipients = getaddresses([to])
        sender_address = _single_address(sender)
        if (len(recipients) != 1 or not recipients[0][1] or '@' not in recipients[0][1]
                or not sender_address):
            return {'outcome': 'rejected', 'code': 'recipient_rejected'}
        message = EmailMessage()
        local, domain = sender_address.rsplit('@', 1)
        message['From'] = Address(display_name=str(sender_name or '').strip()[:78],
                                  username=local, domain=domain)
        message['To'], message['Subject'] = recipients[0][1], subject
        reply_address = _single_address(reply_to)
        if reply_address:
            message['Reply-To'] = reply_address
        message['Date'] = formatdate(localtime=False)
        message['Message-ID'] = make_msgid(domain=domain)
        message['Auto-Submitted'] = 'auto-generated'
        message['X-Auto-Response-Suppress'] = 'All'
        message.set_content(body)
        smtp = (factory or (smtplib.SMTP_SSL if ssl else smtplib.SMTP))(host, port, timeout=20)
        if tls and not ssl:
            smtp.starttls()
        if username and password:
            smtp.login(username, password)
        sending = True
        refused = smtp.send_message(message, from_addr=sender_address,
                                    to_addrs=[recipients[0][1]])
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

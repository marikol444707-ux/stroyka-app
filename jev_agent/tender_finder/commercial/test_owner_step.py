"""Synthetic layout regressions based on the reviewed public STEP markup."""
import hashlib
from unittest import TestCase
from unittest.mock import Mock

from .access import Decision
from .model import Document, Profile
from .owner_step import SOURCE, LISTING, read, parse_card, adapter, MAX_HTML
from .policy import assess
from .test_commercial import NOW

CARD = 'https://ahstep.ru/tenders/tender63928705612762'
LIST = ('<h1>Закупочные процедуры</h1><main>№ закупочной процедуры Текущий статус'
        '<a href="/tenders/tender63928705612762">Работы</a>'
        '<a href="https://attacker.example/tenders/tender12345678901">Чужой</a></main>').encode()
BODY = '''<h1>Закупочная процедура №25202</h1><main><body><p>УВЕДОМЛЕНИЕ<br>
О ПРОВЕДЕНИИ ЗАКУПОЧНОЙ ПРОЦЕДУРЫ</p><p>АО Агрохолдинг «СТЕПЬ» адрес:
Ростовская область объявляет о проведении открытого запроса предложений на:</p>
<p>«Капитальный ремонт здания»</p><p>и приглашает юридических лиц и индивидуальных предпринимателей.</p>
<p>Организатор:</p><p>Департамент закупок АО Агрохолдинг «СТЕПЬ»</p>
<p>не позднее 16:00 часов (московское время)<br>13.11.2026г.</p>
<a href="https://www.ahstep.ru/storage/tenders\\tender63928705612762.zip">1. Закупочная документация</a>
<script>Сторона договора (заказчик): FAKE</script></body></main>
<footer>Место выполнения работ: Ростовская область</footer>'''.encode()


class StepTests(TestCase):
    def permission(self, _): return Decision(True, 'allowed')

    def capture(self, url=CARD, body=BODY, permission=None):
        return read(url, clock=lambda: NOW, access_check=permission or self.permission,
                    fetch=lambda _: (200, 'text/html; charset=UTF-8', body))

    def document(self, capture):
        return Document('primary', SOURCE.id, capture.url, 'Карточка', 'card', NOW,
                        capture.text, raw_sha256=capture.raw_sha256)

    def test_explicit_primary_number_title_and_timezone_are_quoted(self):
        observation = self.capture(); card = self.document(observation)
        result = parse_card(card, 'step')
        self.assertEqual(result.number, '25202')
        self.assertEqual(result.facts['title'][0].value, 'Капитальный ремонт здания')
        self.assertEqual(result.facts['deadline'][0].value, '2026-11-13T16:00:00+03:00')
        self.assertEqual(card.sha256, hashlib.sha256(BODY).hexdigest())
        result.validate(NOW, {'step': SOURCE.hosts})

    def test_footer_scripts_and_organizer_address_do_not_prove_direct_role_or_worksite(self):
        result = parse_card(self.document(self.capture()), 'step')
        for field in ('role', 'authority', 'counterparty', 'work_region', 'work_address', 'price', 'stage'):
            self.assertNotIn(field, result.facts)
        self.assertNotIn('FAKE', result.documents[0].text)

    def test_missing_explicit_timezone_is_not_assumed_moscow(self):
        result = parse_card(self.document(self.capture(body=BODY.replace('(московское время)'.encode(), b''))), 'step')
        self.assertNotIn('deadline', result.facts)

    def test_past_primary_deadline_is_visible_without_inventing_a_closed_stage(self):
        row = parse_card(self.document(self.capture(body=BODY.replace(b'13.11.2026', b'13.11.2025'))), 'step')
        review = assess(row, NOW, {'step': SOURCE.hosts})
        self.assertIn('Указанный срок истёк; текущий этап требует проверки', review['risks'])
        self.assertNotIn('stage', review['values'])
        self.assertEqual(review['bucket'], 'unconfirmed')

    def test_access_gate_precedes_every_network_read(self):
        fetch = Mock()
        result = read(CARD, clock=lambda: NOW, access_check=lambda _: Decision(False, 'robots_disallow'), fetch=fetch)
        self.assertEqual(result.status, 'robots_disallow'); fetch.assert_not_called()

    def test_foreign_login_paths_redirects_and_oversize_fail_closed(self):
        for url in ('https://attacker.example/tenders/tender12345678901', 'https://ahstep.ru/login'):
            with self.assertRaises(ValueError): self.capture(url=url)
        for reply in ((302, 'text/html', b''), (200, 'text/html', b'x'*(MAX_HTML+1)), (200, 'text/html', b'<html>login</html>')):
            result = read(CARD, clock=lambda: NOW, access_check=self.permission, fetch=lambda _: reply)
            self.assertEqual(result.status, 'unavailable')

    def test_listing_has_only_reviewed_card_links_and_requires_known_structure(self):
        observation = self.capture(url=LISTING, body=LIST)
        self.assertEqual(observation.search_state['notice_urls'], [CARD])
        self.assertEqual(self.capture(url=LISTING, body=b'<h1>empty</h1>').status, 'unavailable')

    def test_one_bounded_reader_uses_fresh_primary_cards_and_leaves_documents_unread(self):
        fetch = Mock(side_effect=lambda url: (200, 'text/html', LIST if url==LISTING else BODY))
        result = adapter(clock=lambda: NOW, access_check=self.permission, fetch=fetch)(Profile(), NOW)
        self.assertEqual(result.status, 'partial')
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(fetch.call_count, 2)
        self.assertIn('documents_not_read', result.limitations)
        self.assertEqual(result.attachment_statuses, ())


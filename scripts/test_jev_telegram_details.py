import json
import tempfile
import unittest
from pathlib import Path

from scripts.jev_telegram import classify, digest, render_html
from scripts.jev_telegram_details import describe
from scripts.jev_telegram_history import save_batch


class DetailsTest(unittest.TestCase):
    def test_multiple_work_types_and_unknown(self):
        self.assertEqual(describe('Нужна бригада на кладку и крышу')['tags'], ['Кладка', 'Кровля'])
        examples = [
            ('Нужно построить дом', 'Дом целиком'), ('Фундамент', 'Фундамент'),
            ('Покраска и обои', 'Ремонт и отделка'), ('Перекрытия', 'Перекрытия'),
            ('Каркасный дом', 'Каркас'), ('Электрика и отопление', 'Инженерные работы')]
        for text, tag in examples:
            with self.subTest(text=text): self.assertIn(tag, describe(text)['tags'])
        self.assertEqual(describe('Нужна бригада на объект')['tags'], ['Нужно уточнить'])
        report = digest([{'text': 'Нужна бригада на объект'}])
        self.assertEqual(report['orders'][0]['tags'], ['Нужно уточнить'])

    def test_only_literal_fields(self):
        text = 'Нужна бригада на отделку. Город: Ставрополь; объём 120 м². Бюджет: до 350 000 ₽. Срок: 20 дней.'
        fields = describe(text)['fields']
        self.assertEqual(describe(text)['headline'], 'Нужна бригада на отделку.')
        self.assertIn('Ставрополь', fields['place'][0])
        self.assertIn('120 м²', fields['volume'])
        self.assertEqual(fields['budget'], ['Бюджет: до 350 000 ₽'])
        self.assertEqual(fields['deadline'], ['Срок: 20 дней'])
        for values in fields.values():
            for value in values: self.assertIn(value, text)
        unknown = describe('Нужен маляр. Материалы 1000 ₽, звонить 123456')['fields']
        self.assertEqual(unknown['budget'], [])
        self.assertEqual(unknown['place'], [])
        self.assertEqual(unknown['deadline'], [])
        self.assertEqual(describe('Нужен маляр. Начало: завтра')['fields']['deadline'], ['Начало: завтра'])
        self.assertEqual(describe('Опыт 2 г. назад')['fields']['place'], [])
        self.assertEqual(describe('Работа в г. Минеральные Воды')['fields']['place'], ['г. Минеральные Воды'])

    def test_vacancies_not_orders_or_service_advertising(self):
        self.assertEqual(classify('Требуется электрик в штат. Зарплата 80000 рублей'), 'vacancy')
        self.assertEqual(classify(
            'Требуются люди на монтаж строительных лесов, жильё за счёт работодателя, '
            'оплата 7000 + КТУ, аванс 10000, объект в Воронеже'), 'vacancy')
        details = describe(
            'Требуются люди на монтаж строительных лесов, жильё за счёт работодателя, '
            'оплата 7000 + КТУ, аванс 10000, объект в Воронеже')
        self.assertIn('Монтаж строительных конструкций', details['tags'])
        self.assertEqual(details['fields']['place'], ['объект в Воронеже'])
        self.assertEqual(details['fields']['budget'], ['оплата 7000 + КТУ', 'аванс 10000'])
        self.assertEqual(classify('Нужен электрик провести проводку в доме'), 'order')
        self.assertEqual(classify('Ищу работу электриком, зарплата от 80000 рублей'), 'services')
        self.assertEqual(classify('Выполняем ремонт. Вакансия: требуется маляр в штат'), 'review')
        self.assertEqual(classify('Вакансия: продавец обуви'), 'irrelevant')
        self.assertEqual(classify('Нужен электрик, не в штат, не вакансия, разовая работа'), 'order')

    def test_saved_history_is_reannotated_and_vacancy_remains_separate(self):
        rows = [{'id': 1, 'source': 'testa', 'date': '2026-10-20', 'url': 'https://t.me/testa/1',
                 'text': 'Нужен электрик в штат. Зарплата 80000 рублей'}]
        with tempfile.TemporaryDirectory() as folder:
            first = save_batch(folder, digest(rows), {})
            report = json.loads(Path(first['json']).read_text())
            self.assertEqual(len(report['vacancies']), 1)
            self.assertEqual(report['orders'], [])
            self.assertEqual(first['new_vacancies'], 1)
            html = render_html(report)
            self.assertIn('Вакансии', html)
            self.assertIn('Инженерные работы', html)
            second = save_batch(folder, digest([]), {})
            self.assertEqual(second['new_vacancies'], 0)
            self.assertEqual(second['vacancies'], 1)

    def test_legacy_order_is_reclassified_without_becoming_new(self):
        import sqlite3
        row = {'text': 'Требуется маляр в штат', 'id': 1, 'url': 'https://t.me/testa/1',
               'source': 'testa', 'date': '2026-10-20'}
        with tempfile.TemporaryDirectory() as folder:
            save_batch(folder, digest([row]), {'a': 1})
            with sqlite3.connect(str(Path(folder) / 'history.sqlite3')) as conn:
                conn.execute("UPDATE cards SET category='order'")
            result = save_batch(folder, digest([]), {'a': 1})
            self.assertEqual(result['vacancies'], 1)
            self.assertEqual(result['orders'], 0)
            self.assertEqual(result['new_vacancies'], 0)


if __name__ == '__main__': unittest.main()

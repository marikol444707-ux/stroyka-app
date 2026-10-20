"""Explainable labels and literal excerpts; no guessed locations, prices or dates."""
import re

WORK_TYPES = (
    ('Ремонт и отделка', r'отдел|ремонт|маляр|покраск|штукатур|шпакл|плиточ|плитк|покле|обои|стяжк|гипсокартон|напольн'),
    ('Дом целиком', r'(?:построить|построим|возвести|строительств[ао])\s+(?:(?:частного|жилого|загородного)\s+)?(?:дом\w*|коттедж\w*)|дом\w*\s+(?:целиком|под\s+ключ)'),
    ('Фундамент', r'фундамент|\bсва[ий]'),
    ('Кладка', r'кладк|каменщик|газобетон'),
    ('Перекрытия', r'перекрыт'),
    ('Кровля', r'кров(?:л|ель)|крыш'),
    ('Каркас', r'каркас'),
    ('Инженерные работы', r'электри|электромонтаж|проводк|сантех|отоплен|водоснабж|канализац'),
)
PATTERNS = [(label, re.compile(pattern, re.I)) for label, pattern in WORK_TYPES]
VACANCY = re.compile(r'\bваканси|\bв\s+штат|трудоустройств|зарплат|заработн\w*\s+плат|\bз/п\b', re.I)

NUMBER = r'\d(?:[\d\u00a0 .,]*\d)?'
FIELDS = {
    'place': re.compile(r'(?i:\b(?:город|место|объект|адрес)\s*:\s*)[^\n;.!?]{1,100}|\b[гГ]\.\s*[А-ЯЁ][А-ЯЁа-яё-]{2,35}(?:\s+[А-ЯЁ][А-ЯЁа-яё-]{2,35})?'),
    'volume': re.compile(NUMBER + r'\s*(?:м[²³23]|кв\.?\s*м\.?|куб\.?\s*м\.?|пог\.?\s*м\.?|сот(?:ок|ки|ка)|этаж(?:а|ей)?)(?!\w)', re.I),
    'budget': re.compile(r'\b(?:бюджет|оплата|зарплата|з/п|стоимость\s+работ|цена\s+за\s+работу)\s*[:—-]?\s*(?:(?:до|от)\s+)?' + NUMBER + r'\s*(?:(?:тыс\.?|млн\.?)\s*)?(?:₽|руб\w*)(?:\s*/\s*(?:м[²2]|день|месяц))?', re.I),
    'deadline': re.compile(r'\b(?:срок(?:\s+(?:начала|сдачи|выполнения))?|начало|закончить\s+до|сдать\s+до|приступить)\s*[:—-]?\s*(?:(?:до|с)\s+)?(?:\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?|\d+\s*(?:дней|дня|день|недел\w*|месяц\w*)|послезавтра|завтра|сегодня|срочно)(?!\w)', re.I),
}


def is_vacancy(text):
    # Explicit denial alone must not turn a one-off job into employment.
    cleaned = re.sub(r'\bне\s+вакансия\b|\bне\s+в\s+штат\b', '', text, flags=re.I)
    return bool(VACANCY.search(cleaned))


def describe(text):
    tags = [label for label, pattern in PATTERNS if pattern.search(text)]
    fields = {}
    for key, pattern in FIELDS.items():
        excerpts = list(dict.fromkeys(match.group().strip() for match in pattern.finditer(text)))
        fields[key] = excerpts[:3]
    headline = next((line.strip() for line in text.splitlines() if line.strip()), '')
    headline = re.split(r'(?<=[.!?])\s+(?=[А-ЯЁA-Z])', headline, maxsplit=1)[0]
    if len(headline) > 140: headline = headline[:140] + '…'
    return {'headline': headline, 'tags': tags or ['Нужно уточнить'], 'fields': fields}

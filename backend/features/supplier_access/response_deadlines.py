"""RFQ response deadlines: next weekday at the same Moscow wall-clock time."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

MOSCOW = ZoneInfo('Europe/Moscow')

def response_deadline(value=None, now=None):
    now = now or datetime.now(timezone.utc)
    if value is None or value == '':
        result = now.astimezone(MOSCOW) + timedelta(days=1)
        while result.weekday() >= 5:
            result += timedelta(days=1)
    else:
        if not isinstance(value, str):
            raise ValueError('Укажите корректную дату и время ответа на КП')
        try:
            result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError('Укажите корректную дату и время ответа на КП') from None
        if result.tzinfo is None:
            raise ValueError('В сроке ответа на КП должен быть указан часовой пояс')
        if result <= now:
            raise ValueError('Срок ответа на КП должен быть в будущем')
    return result.astimezone(timezone.utc)

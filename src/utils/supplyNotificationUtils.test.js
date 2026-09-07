import {
  supplierEmailNotificationLabel,
  supplierMaxNotificationLabel,
  supplyNotificationSummary,
} from './supplyNotificationUtils';

describe('notification status labels', () => {
  it.each([
    ['Отправлено', 'Передано SMTP'],
    ['Нет email', 'Нет email'],
    ['SMTP не настроен', 'SMTP не настроен'],
    ['Ошибка отправки', 'Ошибка отправки'],
    ['Пропущено: тестовый email', 'Пропущено: тестовый email'],
    ['', 'Статус неизвестен'],
  ])('renders email status %s without claiming delivery', (status, expected) => {
    expect(supplierEmailNotificationLabel({ emailStatus: status })).toBe(expected);
    expect(supplierEmailNotificationLabel({ emailNotificationStatus: status })).toBe(expected);
  });

  it.each([
    ['queued', 'В очереди MAX'],
    ['sent', 'Передано MAX'],
    ['failed', 'Ошибка отправки в MAX'],
    ['skipped', 'Пропущено в MAX'],
    ['cancelled', 'Отменено в MAX'],
    ['unknown', 'Статус очереди MAX неизвестен'],
  ])('prefers current queue status %s over the stored queue snapshot', (status, expected) => {
    expect(supplierMaxNotificationLabel({
      maxNotificationStatus: 'В очереди MAX', actualMaxQueueStatus: status,
    })).toBe(expected);
  });

  it.each(['future_status', 'constructor', 'toString', '__proto__'])('treats unrecognized status %s as unknown', status => {
    expect(supplierEmailNotificationLabel({ emailStatus: status })).toBe('Неизвестный статус: ' + status);
    expect(supplierMaxNotificationLabel({ maxStatus: status })).toBe('Неизвестный статус: ' + status);
  });

  it('does not invent a creation count when a legacy response omits it', () => {
    expect(supplyNotificationSummary({ ok: true })).toBe('Запрос КП обработан. Статусы уведомлений неизвестны. Проверьте получателей.');
  });

  it('keeps null status data unknown without breaking the panel or summary', () => {
    expect(supplierEmailNotificationLabel(null)).toBe('Статус неизвестен');
    expect(supplierMaxNotificationLabel(null)).toBe('Статус неизвестен');
    expect(supplyNotificationSummary(null)).toContain('Статусы уведомлений неизвестны');
  });
});

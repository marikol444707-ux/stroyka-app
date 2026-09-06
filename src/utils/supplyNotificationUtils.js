const EMAIL_LABELS = {
  'Отправлено': 'Передано SMTP',
  'Нет email': 'Нет email',
  'Пропущено: тестовый email': 'Пропущено: тестовый email',
  'SMTP не настроен': 'SMTP не настроен',
  'Ошибка отправки': 'Ошибка отправки',
};

const MAX_LABELS = {
  'MAX не привязан': 'MAX не привязан',
  'В очереди MAX': 'В очереди MAX',
  'Отправлено MAX': 'Передано MAX',
  queued: 'В очереди MAX',
  processing: 'Обрабатывается MAX',
  retry: 'Ожидает повтора MAX',
  sent: 'Передано MAX',
  failed: 'Ошибка отправки в MAX',
  skipped: 'Пропущено в MAX',
  cancelled: 'Отменено в MAX',
  unknown: 'Статус очереди MAX неизвестен',
};

const statusLabel = (status, labels) => Object.prototype.hasOwnProperty.call(labels, status)
  ? labels[status]
  : (status ? 'Неизвестный статус: ' + status : 'Статус неизвестен');

export function supplierEmailNotificationLabel(row = {}) {
  return statusLabel(row?.emailNotificationStatus || row?.emailStatus, EMAIL_LABELS);
}

export function supplierMaxNotificationLabel(row = {}) {
  return statusLabel(row?.actualMaxQueueStatus || row?.maxNotificationStatus || row?.maxStatus, MAX_LABELS);
}

export function supplyNotificationSummary(data = {}) {
  const created = Number.isInteger(data?.created) && data.created >= 0
    ? 'Создано запросов КП: ' + data.created + '.'
    : 'Запрос КП обработан.';
  const notifications = Array.isArray(data?.notifications) ? data.notifications.filter(Boolean) : [];
  if (!notifications.length) return created + ' Статусы уведомлений неизвестны. Проверьте получателей.';

  const counts = label => {
    const grouped = new Map();
    notifications.forEach(row => {
      const text = label(row);
      grouped.set(text, (grouped.get(text) || 0) + 1);
    });
    return [...grouped].map(([text, count]) => text + ': ' + count).join('; ');
  };
  return created + ' Email — ' + counts(supplierEmailNotificationLabel)
    + '. MAX — ' + counts(supplierMaxNotificationLabel)
    + '. Доставка и прочтение не подтверждены.';
}

import { buildInventoryReport } from './inventoryPrint';

test('inventory print keeps all saved user text literal and cannot create markup or handlers', () => {
  const attack = '<img src=x onerror="alert(1)"><script>alert(2)</script>&\'"';
  const data = {
    inventory: { id: 41, project: 'Объект ' + attack, date: '2026-09-19', status: 'Утверждена',
      state: 'approved', createdBy: 'Автор ' + attack, notes: 'Примечание ' + attack,
      company: { id: 2, fullName: 'Организация ' + attack, inn: '1234567890', source: 'company_requisites' } },
    rows: [
      { key: 'material:1', kind: 'material', name: 'Материал ' + attack, package: 'Пакет ' + attack,
        expected: '5', unit: 'кг ' + attack, actual: '2', difference: '-3', reason: 'Причина ' + attack },
      { key: 'tool:2', kind: 'tool', name: 'Инструмент ' + attack, inventoryNumber: 'INV ' + attack,
        status: 'На складе ' + attack, holderName: 'Получатель ' + attack,
        condition: 'missing', reason: 'Проверка ' + attack },
    ],
    history: [{ id: 71, action: 'approve', actorName: 'Директор ' + attack,
      createdAt: 'Дата ' + attack, reason: 'Решение ' + attack }],
  };
  const before = JSON.parse(JSON.stringify(data));
  const container = document.createElement('div');
  container.innerHTML = buildInventoryReport(data);

  expect(container.querySelectorAll('img, script, [onerror], [onload]')).toHaveLength(0);
  for (const label of ['Объект', 'Автор', 'Примечание', 'Материал', 'Пакет', 'кг', 'Причина',
    'Инструмент', 'INV', 'На складе', 'Получатель', 'Проверка', 'Директор', 'Дата', 'Решение', 'Организация']) {
    expect(container.textContent).toContain(label + ' ' + attack);
  }
  expect(container.textContent).toContain('Зафиксирована при начале сверки');
  expect(container.textContent).toContain('Утверждённая ведомость');
  expect(data).toEqual(before);
});

test('inventory print clearly marks a draft and names the counter and approving director', () => {
  const html = buildInventoryReport({
    inventory: { id: 8, project: 'Основной склад', date: '2026-10-02', status: 'На проверке',
      state: 'submitted', company: { id: 3, fullName: 'ООО Склад', inn: '1234567890' } },
    rows: [],
    history: [
      { id: 1, action: 'create', actorName: 'Кладовщик', createdAt: '2026-10-02T08:00:00Z', reason: '' },
      { id: 2, action: 'approve', actorName: 'Директор', createdAt: '2026-10-02T09:00:00Z', reason: 'Проверено' },
    ],
  });
  expect(html).toContain('Черновик — не утверждён');
  expect(html).toContain('Провёл пересчёт: Кладовщик');
  expect(html).toContain('Утвердил: Директор');
});

import { buildInventoryReport } from './inventoryPrint';

test('inventory print keeps all saved user text literal and cannot create markup or handlers', () => {
  const attack = '<img src=x onerror="alert(1)"><script>alert(2)</script>&\'"';
  const data = {
    inventory: { id: 41, project: 'Объект ' + attack, date: '2026-09-19', status: 'Утверждена',
      createdBy: 'Автор ' + attack, notes: 'Примечание ' + attack },
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
    'Инструмент', 'INV', 'На складе', 'Получатель', 'Проверка', 'Директор', 'Дата', 'Решение']) {
    expect(container.textContent).toContain(label + ' ' + attack);
  }
  expect(data).toEqual(before);
});

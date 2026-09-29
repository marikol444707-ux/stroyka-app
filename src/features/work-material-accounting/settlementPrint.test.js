import { buildSettlementAct } from './settlementPrint';

const copy = value => JSON.parse(JSON.stringify(value));
const text = html => {
  const container = document.createElement('div');
  container.innerHTML = html;
  return container.textContent.replace(/\s+/g, ' ').trim();
};
const freeze = value => {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
};
function savedAct() {
  return {
    id: 81, totalAmount: 1200.5, fineAmount: 350.25, netAmount: 850.25,
    snapshot: {
      contractId: 41, projectName: 'Лицей', brigadeName: 'Бригада монтажников', workPackage: 'Основная',
      periodFrom: '2026-09-18', periodTo: '2026-09-18',
      grossAmount: '1200.50', fineAmount: '350.25', netAmount: '850.25',
      works: [{ id: 501, description: 'Монтаж', room_name: 'Кабинет 4', unit: 'м²', quantity: 2.5,
        execution_price_per_unit: 480.2, execution_total: 1200.5 }],
      fines: [{ defectId: 601, decisionId: 901, journalId: 501, amount: '350.25',
        reason: 'Повреждение при монтаже', contractEvidence: 'Договор № 41, пункт 8.2',
        valuations: [{ entryId: 701, quantity: '3.5', unit: 'кг', unitPrice: '200.00', amount: '700.00',
          priceEvidence: 'Накладная № 77 от 15.09.2026' }] }],
    },
  };
}

test('printed gross, fine and net remain the saved act values when live work and totals change', () => {
  const act = savedAct();
  const snapshotBefore = copy(act.snapshot);
  freeze(act.snapshot);
  act.works = copy(act.snapshot.works);
  act.fines = copy(act.snapshot.fines);
  const original = buildSettlementAct(act);
  act.totalAmount = 99000;
  act.fineAmount = 10000;
  act.netAmount = 89000;
  act.works[0].execution_total = 99000;
  act.works[0].description = 'Изменённая работа после подписания';
  act.fines[0].amount = '10000.00';
  expect(buildSettlementAct(act)).toBe(original);
  expect(act.snapshot).toEqual(snapshotBefore);
  const printed = text(original);
  expect(printed).toContain('Стоимость принятых работ: 1 200,50 ₽');
  expect(printed).toContain('Итого штрафы: 350,25 ₽');
  expect(printed).toContain('К оплате по акту: 850,25 ₽');
  expect(printed).toContain('Кабинет 4');
  expect(printed).not.toContain('Изменённая работа после подписания');
});

test('printed fine identifies its original work, defect, decision, material and documentary evidence', () => {
  const printed = text(buildSettlementAct(savedAct()));
  expect(printed).toMatch(/Брак\s*№\s*601/);
  expect(printed).toMatch(/ЖПР\s*№\s*501/);
  expect(printed).toMatch(/Решение\s*№\s*901/i);
  expect(printed).toContain('Материал №701');
  expect(printed).toContain('Повреждение при монтаже');
  expect(printed).toContain('Договор № 41, пункт 8.2');
  expect(printed).toContain('Накладная № 77 от 15.09.2026');
  expect(printed).toContain('3.5 кг × 200,00 ₽');
});

test('an allocated part of a larger defect is printed as this act fine without recalculating the full loss', () => {
  const act = savedAct();
  // The full valued loss is 700; only 350.25 was allocated to this immutable act.
  const container = document.createElement('div');
  container.innerHTML = buildSettlementAct(act);
  const defectRow = [...container.querySelectorAll('tr')].find(row => row.textContent.includes('Брак №601'));
  expect(text(defectRow.innerHTML)).toContain('350,25');
  expect(text(container.innerHTML)).toContain('Итого штрафы: 350,25 ₽');
  expect(text(container.innerHTML)).toContain('К оплате по акту: 850,25 ₽');
  expect(act.snapshot.fines[0].valuations[0].amount).toBe('700.00');
});

test('user-supplied contract, work and defect text stays literal and cannot create HTML elements or handlers', () => {
  const act = savedAct();
  const attack = '<img src=x onerror="alert(1)"><script>alert(2)</script>&\'"';
  act.snapshot.projectName = 'Объект ' + attack;
  act.snapshot.brigadeName = 'Исполнитель ' + attack;
  act.snapshot.workPackage = 'Пакет ' + attack;
  act.snapshot.works[0].description = 'Работа ' + attack;
  act.snapshot.works[0].room_name = 'Помещение ' + attack;
  act.snapshot.fines[0].reason = 'Причина ' + attack;
  act.snapshot.fines[0].contractEvidence = 'Договор ' + attack;
  act.snapshot.fines[0].valuations[0].name = 'Материал ' + attack;
  act.snapshot.fines[0].valuations[0].priceEvidence = 'Накладная ' + attack;
  const container = document.createElement('div');
  container.innerHTML = buildSettlementAct(act);
  expect(container.querySelectorAll('img, script, [onerror], [onload]')).toHaveLength(0);
  for (const label of ['Объект', 'Исполнитель', 'Пакет', 'Работа', 'Помещение', 'Причина', 'Договор', 'Материал', 'Накладная']) {
    expect(container.textContent).toContain(label + ' ' + attack);
  }
});

test('user-supplied tool fine text stays literal and cannot inject print markup', () => {
  const act = savedAct();
  const attack = '<img src=x onerror="alert(1)"><script>alert(2)</script>&\'"';
  act.snapshot.fines = [{
    source: 'tool', incidentId: '81' + attack, decisionId: '91' + attack,
    toolName: 'Перфоратор ' + attack, reason: 'Утеря ' + attack,
    contractEvidence: 'Договор ' + attack, priceEvidence: 'Счёт ' + attack,
    amount: '350.25',
  }];
  const container = document.createElement('div');
  container.innerHTML = buildSettlementAct(act);
  expect(container.querySelectorAll('img, script, [onerror], [onload]')).toHaveLength(0);
  for (const label of ['Перфоратор', 'Утеря', 'Договор', 'Счёт']) {
    expect(container.textContent).toContain(label + ' ' + attack);
  }
  expect(container.textContent).toContain('происшествие №81' + attack);
  expect(container.textContent).toContain('Решение №91' + attack);
});

test.each([undefined, null, { works: null, fines: [] }, { works: [], fines: {} }])(
  'missing or incomplete saved snapshot %p cannot print a financial act', snapshot => {
    expect(() => buildSettlementAct({ ...savedAct(), snapshot })).toThrow(/сохранённого состава/i);
  },
);

import { buildMovementDocContent } from './printDocumentBuilders';

test('M-11 prints frozen company route actor and materials', () => {
  const first = {
    id: 9,
    fromLocation: 'Изменённый склад',
    documentSnapshot: {
      company: {fullName: 'ООО Зафиксировано'},
      document: {date: '2026-10-02'},
      route: {from: {name: 'Основной склад'}, to: {name: 'Лицей'}},
      actor: {name: 'Кладовщик'},
      material: {name: 'Краска', unit: 'кг', quantity: '5'},
    },
  };
  const html = buildMovementDocContent(first, [first], {
    companyName: 'Текущая компания', userName: 'Текущий пользователь',
  });
  expect(html).toContain('ООО Зафиксировано');
  expect(html).toContain('Основной склад');
  expect(html).toContain('Лицей');
  expect(html).toContain('Кладовщик');
  expect(html).toContain('Краска');
  expect(html).not.toContain('Текущая компания');
  expect(html).not.toContain('Текущий пользователь');
  expect(html).not.toContain('Изменённый склад');
});

test('legacy M-11 does not borrow current company identity', () => {
  const html = buildMovementDocContent(
    {fromLocation: 'А', toLocation: 'Б', materialName: 'Кабель', quantity: 2, unit: 'м'},
    [],
    {companyName: 'Сегодняшняя компания', userName: 'Сегодняшний сотрудник'},
  );
  expect(html).toContain('Историческая запись');
  expect(html).toContain('Реквизиты не зафиксированы');
  expect(html).not.toContain('Сегодняшняя компания');
  expect(html).not.toContain('Сегодняшний сотрудник');
});

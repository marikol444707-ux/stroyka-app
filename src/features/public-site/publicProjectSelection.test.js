import {
  buildPublicProjectLeadComment,
  describePublicLayoutPreferences,
} from './publicProjectSelection';

test('describes house layout preferences in Russian', () => {
  expect(describePublicLayoutPreferences({
    spaces: 4,
    bathrooms: 2,
    garage: true,
    notes: 'кабинет у входа',
    isHouseLayout: true,
  })).toBe('4 спальни, 2 санузла, гараж нужен, дополнительно: кабинет у входа');
});

test('builds a lead comment with the selected project variant and layout', () => {
  const comment = buildPublicProjectLeadComment({
    direction: { title: 'Одноэтажный дом', text: 'Базовая планировка' },
    project: { title: 'Дом 110 м2', layout: 'Кухня-гостиная и 3 спальни' },
    objectFormat: 'Дом под ключ',
    projectUrl: 'https://stroyka26.pro/?project=H1-01#projects',
    mirrored: true,
    packageSelection: { label: 'Тёплый контур' },
    layoutPreferences: {
      spaces: 4,
      bathrooms: 2,
      garage: false,
      notes: '',
      isHouseLayout: true,
    },
  });

  expect(comment).toContain('Вариант: зеркальный.');
  expect(comment).toContain('Комплектация: Тёплый контур.');
  expect(comment).toContain('Пожелания: 4 спальни, 2 санузла, гараж не нужен.');
  expect(comment).toContain('Ссылка на карточку: https://stroyka26.pro/?project=H1-01#projects');
  expect(comment).not.toContain('..');
});

test('normalizes punctuation in project and customer text', () => {
  const comment = buildPublicProjectLeadComment({
    direction: { title: 'Дом', text: 'Базовая планировка.' },
    project: { title: 'Дом 110 м2', layout: 'Кухня и спальня.' },
    projectUrl: 'https://stroyka26.pro/#projects',
    layoutPreferences: {
      spaces: 2,
      bathrooms: 1,
      garage: false,
      notes: 'Нужен кабинет.',
      isHouseLayout: true,
    },
  });

  expect(comment).toContain('дополнительно: Нужен кабинет.');
  expect(comment).toContain('Исходная планировка: Кухня и спальня.');
  expect(comment).not.toContain('..');
});

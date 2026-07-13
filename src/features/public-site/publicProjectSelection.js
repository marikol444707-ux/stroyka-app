const pluralize = (count, one, few, many) => {
  const value = Math.abs(Number(count)) % 100;
  const lastDigit = value % 10;
  if (value > 10 && value < 20) return many;
  if (lastDigit === 1) return one;
  if (lastDigit > 1 && lastDigit < 5) return few;
  return many;
};

const withoutSentenceEnd = (value) => String(value || '').trim().replace(/[.!?]+$/, '');

export const describePublicLayoutPreferences = (preferences) => {
  if (!preferences) return '';

  const { spaces, bathrooms, garage, notes, isHouseLayout } = preferences;
  const spacesLabel = isHouseLayout
    ? pluralize(spaces, 'спальня', 'спальни', 'спален')
    : pluralize(spaces, 'комната / зона', 'комнаты / зоны', 'комнат / зон');
  const parts = [
    `${spaces} ${spacesLabel}`,
    `${bathrooms} ${pluralize(bathrooms, 'санузел', 'санузла', 'санузлов')}`,
  ];
  if (isHouseLayout) parts.push(garage ? 'гараж нужен' : 'гараж не нужен');
  if (notes) parts.push(`дополнительно: ${withoutSentenceEnd(notes)}`);
  return parts.join(', ');
};

export const buildPublicProjectLeadComment = ({
  direction,
  project,
  objectFormat,
  projectUrl,
  mirrored = false,
  layoutPreferences = null,
}) => [
  layoutPreferences ? 'Нужна доработка планировки.' : `Интересует: ${direction.title}.`,
  layoutPreferences ? `Направление: ${direction.title}.` : '',
  `Проект: ${project.title}.`,
  `Вариант: ${mirrored ? 'зеркальный' : 'обычный'}.`,
  objectFormat ? `Формат объекта: ${objectFormat}.` : '',
  layoutPreferences ? `Пожелания: ${describePublicLayoutPreferences(layoutPreferences)}.` : '',
  `Исходная планировка: ${withoutSentenceEnd(project.layout || direction.text)}.`,
  `Ссылка на карточку: ${projectUrl}`,
].filter(Boolean).join(' ');

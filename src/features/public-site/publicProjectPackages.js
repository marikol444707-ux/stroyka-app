export const publicProjectHousePackages = [
  {
    value: 'box',
    label: 'Коробка',
    description: 'Несущая основа дома без окон, инженерии и отделки.',
    duration: 'ориентир 3-5 месяцев',
    includes: ['Несущие стены', 'Перекрытия и проёмы', 'Кровельная конструкция'],
  },
  {
    value: 'warm',
    label: 'Тёплый контур',
    description: 'Дом закрыт от погоды и готов к инженерным работам.',
    duration: 'ориентир 4-6 месяцев',
    includes: ['Всё из «Коробки»', 'Окна и входные двери', 'Утепление, кровля и фасад'],
  },
  {
    value: 'turnkey',
    label: 'Под ключ',
    description: 'Полный цикл до готовности дома к проживанию.',
    duration: 'ориентир 7-10 месяцев',
    includes: ['Всё из «Тёплого контура»', 'Инженерные системы', 'Внутренняя отделка'],
  },
];

export const getPublicProjectHousePackage = (value) => (
  publicProjectHousePackages.find((item) => item.value === value)
  || publicProjectHousePackages[2]
);

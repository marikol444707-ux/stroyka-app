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

export const publicProjectPaymentSchedules = {
  box: [
    { id: 'foundation', title: 'Подготовка и фундамент', percent: 25 },
    { id: 'walls', title: 'Несущие стены и каркас', percent: 35 },
    { id: 'roof', title: 'Перекрытия и кровля', percent: 30 },
    { id: 'acceptance', title: 'Проверка и приёмка коробки', percent: 10 },
  ],
  warm: [
    { id: 'foundation', title: 'Подготовка и фундамент', percent: 20 },
    { id: 'box', title: 'Стены и перекрытия', percent: 30 },
    { id: 'roof', title: 'Кровля и утепление', percent: 20 },
    { id: 'openings', title: 'Окна, двери и фасад', percent: 20 },
    { id: 'acceptance', title: 'Проверка и приёмка контура', percent: 10 },
  ],
  turnkey: [
    { id: 'start', title: 'Проектирование и запуск работ', percent: 5 },
    { id: 'box', title: 'Фундамент и коробка', percent: 25 },
    { id: 'warm', title: 'Тёплый контур', percent: 20 },
    { id: 'engineering', title: 'Инженерные системы', percent: 20 },
    { id: 'finishing', title: 'Внутренняя отделка', percent: 20 },
    { id: 'acceptance', title: 'Финальная проверка и приёмка', percent: 10 },
  ],
};

export const getPublicProjectPaymentSchedule = (packageValue, estimate = {}) => {
  const stages = publicProjectPaymentSchedules[packageValue] || publicProjectPaymentSchedules.turnkey;
  const estimateMin = Math.max(0, Number(estimate.min) || 0);
  const estimateMax = Math.max(estimateMin, Number(estimate.max) || estimateMin);

  return stages.map((stage) => ({
    ...stage,
    min: Math.round((estimateMin * stage.percent) / 100),
    max: Math.round((estimateMax * stage.percent) / 100),
  }));
};

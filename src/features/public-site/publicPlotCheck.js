const plotOptions = {
  status: {
    unknown: 'Пока не указано',
    owned: 'Участок уже есть',
    selecting: 'Участок подбирается',
  },
  access: {
    unknown: 'Пока не знаю',
    good: 'Свободный подъезд',
    restricted: 'Подъезд ограничен',
  },
  relief: {
    unknown: 'Пока не знаю',
    flat: 'Преимущественно ровный',
    slope: 'Есть уклон',
  },
  utilities: {
    unknown: 'Пока не знаю',
    boundary: 'Сети у границы участка',
    connection: 'Нужно подключение',
  },
};

export const publicPlotCheckDefaults = {
  status: 'unknown',
  access: 'unknown',
  relief: 'unknown',
  utilities: 'unknown',
  geologyReady: false,
  geodesyReady: false,
};

export const publicPlotCheckOptions = plotOptions;

export const getPublicPlotCheckSummary = (value = publicPlotCheckDefaults) => {
  const plotCheck = { ...publicPlotCheckDefaults, ...value };
  const reviewItems = [];
  if (plotCheck.status === 'unknown') reviewItems.push('статус участка');
  if (plotCheck.status === 'selecting') reviewItems.push('параметры будущего участка');
  if (plotCheck.access !== 'good') reviewItems.push('подъезд техники');
  if (plotCheck.relief === 'slope') reviewItems.push('перепад высот');
  if (plotCheck.relief === 'unknown') reviewItems.push('рельеф');
  if (plotCheck.utilities === 'connection') reviewItems.push('точки подключения сетей');
  if (plotCheck.utilities === 'unknown') reviewItems.push('подключение сетей');
  if (!plotCheck.geologyReady) reviewItems.push('геология');
  if (!plotCheck.geodesyReady) reviewItems.push('геодезия');

  const completed = [
    plotCheck.status !== 'unknown',
    plotCheck.access !== 'unknown',
    plotCheck.relief !== 'unknown',
    plotCheck.utilities !== 'unknown',
    plotCheck.geologyReady,
    plotCheck.geodesyReady,
  ].filter(Boolean).length;

  return {
    completed,
    total: 6,
    ready: reviewItems.length === 0,
    reviewItems,
  };
};

export const serializePublicPlotCheck = (value = publicPlotCheckDefaults) => {
  const plotCheck = { ...publicPlotCheckDefaults, ...value };
  const summary = getPublicPlotCheckSummary(plotCheck);
  return {
    ...plotCheck,
    statusLabel: plotOptions.status[plotCheck.status] || plotOptions.status.unknown,
    accessLabel: plotOptions.access[plotCheck.access] || plotOptions.access.unknown,
    reliefLabel: plotOptions.relief[plotCheck.relief] || plotOptions.relief.unknown,
    utilitiesLabel: plotOptions.utilities[plotCheck.utilities] || plotOptions.utilities.unknown,
    completed: summary.completed,
    total: summary.total,
    ready: summary.ready,
    reviewItems: summary.reviewItems,
  };
};

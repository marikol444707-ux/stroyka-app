import {
  getPublicPlotCheckSummary,
  publicPlotCheckDefaults,
  serializePublicPlotCheck,
} from './publicPlotCheck';

test('starts without making assumptions about the plot', () => {
  const summary = getPublicPlotCheckSummary(publicPlotCheckDefaults);

  expect(summary.ready).toBe(false);
  expect(summary.reviewItems).toEqual([
    'статус участка',
    'подъезд техники',
    'рельеф',
    'подключение сетей',
    'геология',
    'геодезия',
  ]);
});

test('serializes plot answers for the CRM lead', () => {
  const plotCheck = serializePublicPlotCheck({
    status: 'owned',
    access: 'good',
    relief: 'flat',
    utilities: 'boundary',
    geologyReady: true,
    geodesyReady: true,
  });

  expect(plotCheck.ready).toBe(true);
  expect(plotCheck.statusLabel).toBe('Участок уже есть');
  expect(plotCheck.accessLabel).toBe('Свободный подъезд');
  expect(plotCheck.reviewItems).toEqual([]);
});

import {
  getPublicProjectPaymentSchedule,
  publicProjectPaymentSchedules,
} from './publicProjectPackages';

test.each(Object.entries(publicProjectPaymentSchedules))('%s payment schedule totals 100 percent', (_, stages) => {
  expect(stages.reduce((total, stage) => total + stage.percent, 0)).toBe(100);
});

test('calculates stage ranges from the selected project estimate', () => {
  const schedule = getPublicProjectPaymentSchedule('turnkey', { min: 10000000, max: 12000000 });

  expect(schedule).toHaveLength(6);
  expect(schedule[0]).toMatchObject({ percent: 5, min: 500000, max: 600000 });
  expect(schedule.at(-1)).toMatchObject({ percent: 10, min: 1000000, max: 1200000 });
});

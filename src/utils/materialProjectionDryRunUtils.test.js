import { buildMaterialProjectionDryRun } from './materialProjectionDryRunUtils';

const row = (name, planQty, overrides = {}) => ({
  name,
  materialKey: name.toLowerCase(),
  unit: 'шт',
  workPackage: 'Электрика',
  planQty,
  ...overrides,
});

describe('buildMaterialProjectionDryRun', () => {
  test('compares quantities without mutating either projection', () => {
    const legacyRows = [row('Кабель ВВГ 3х1,5', 100)];
    const correctedRows = [row('Кабель ВВГ 3х1,5', 80)];
    const legacySnapshot = JSON.stringify(legacyRows);
    const correctedSnapshot = JSON.stringify(correctedRows);

    const report = buildMaterialProjectionDryRun([{
      projectId: 7,
      projectName: 'Лицей',
      legacyRows,
      correctedRows,
    }]);

    expect(report).toMatchObject({
      ok: true,
      dryRun: true,
      writesAttempted: 0,
      summary: {
        projects: 1,
        legacyRows: 1,
        correctedRows: 1,
        unchanged: 0,
        quantityChanged: 1,
        legacyOnly: 0,
        correctedOnly: 0,
        splitRows: 0,
      },
    });
    expect(report.projects[0].changes[0]).toMatchObject({
      status: 'quantity_changed',
      legacyQty: 100,
      correctedQty: 80,
      deltaQty: -20,
    });
    expect(JSON.stringify(legacyRows)).toBe(legacySnapshot);
    expect(JSON.stringify(correctedRows)).toBe(correctedSnapshot);
  });

  test('reports rows that exist on only one side', () => {
    const report = buildMaterialProjectionDryRun([{
      projectName: 'Школа',
      legacyRows: [row('Старый материал', 5)],
      correctedRows: [row('Новый материал', 7)],
    }]);

    expect(report.summary).toMatchObject({legacyOnly: 1, correctedOnly: 1});
    expect(report.projects[0].changes.map(change => change.status)).toEqual([
      'corrected_only',
      'legacy_only',
    ]);
  });

  test('detects when one legacy aggregate splits into corrected material identities', () => {
    const sourceA = {estimateId: 10, packageName: 'Электрика', sectionName: 'Кабели', materialName: 'Кабель ВВГ 3х1,5'};
    const sourceB = {estimateId: 10, packageName: 'Электрика', sectionName: 'Кабели', materialName: 'Кабель ВВГ 3х2,5'};
    const report = buildMaterialProjectionDryRun([{
      projectName: 'Больница',
      legacyRows: [row('Кабель ВВГ', 300, {planDetails: [sourceA, sourceB]})],
      correctedRows: [
        row('Кабель ВВГ 3х1,5', 100, {planDetails: [sourceA]}),
        row('Кабель ВВГ 3х2,5', 200, {planDetails: [sourceB]}),
      ],
    }]);

    expect(report.summary).toMatchObject({
      splitRows: 1,
      legacyOnly: 0,
      correctedOnly: 0,
    });
    expect(report.projects[0].changes).toEqual([
      expect.objectContaining({
        status: 'split',
        legacyName: 'Кабель ВВГ',
        correctedNames: ['Кабель ВВГ 3х1,5', 'Кабель ВВГ 3х2,5'],
      }),
    ]);
  });
});

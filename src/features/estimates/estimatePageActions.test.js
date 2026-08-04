import { ESTIMATE_IMPORT_MAX_BYTES, estimateImportFileError } from './estimatePageActions';

describe('estimate import file validation', () => {
  test('accepts the Excel formats supported by the backend parser', () => {
    expect(estimateImportFileError({name:'Корректировка.XLSX', size:1024})).toBe('');
    expect(estimateImportFileError({name:'Корректировка.xlsm', size:1024})).toBe('');
  });

  test('explains unsupported and oversized files before upload', () => {
    expect(estimateImportFileError({name:'Старая смета.xls', size:1024})).toMatch(/сохраните.*xlsx/i);
    expect(estimateImportFileError({name:'Большая смета.xlsx', size:ESTIMATE_IMPORT_MAX_BYTES + 1})).toMatch(/15 МБ/);
  });
});

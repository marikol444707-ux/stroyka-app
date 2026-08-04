import { ESTIMATE_IMPORT_MAX_BYTES, estimateImportFileError, estimateImportRequestError } from './estimatePageActions';

describe('estimate import file validation', () => {
  test('accepts the Excel formats supported by the backend parser', () => {
    expect(estimateImportFileError({name:'Корректировка.XLSX', size:1024})).toBe('');
    expect(estimateImportFileError({name:'Корректировка.xlsm', size:1024})).toBe('');
  });

  test('explains unsupported and oversized files before upload', () => {
    expect(estimateImportFileError({name:'Старая смета.xls', size:1024})).toMatch(/сохраните.*xlsx/i);
    expect(estimateImportFileError({name:'Большая смета.xlsx', size:ESTIMATE_IMPORT_MAX_BYTES + 1})).toMatch(/15 МБ/);
  });

  test('turns an nginx timeout page into an actionable import error', () => {
    expect(estimateImportRequestError(new Error('<html><h1>504 Gateway Time-out</h1></html>'))).toMatch(/Смета не сохранена/);
  });
});

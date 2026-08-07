import { materialNormProjectOwnerByName } from './materialNormActions';

describe('materialNormProjectOwnerByName', () => {
  test('returns the immutable stored owner for one exact project', () => {
    expect(materialNormProjectOwnerByName([
      {id: 11, companyId: 4, name: 'Лицей'},
    ], 'Лицей')).toEqual({companyId: 4, projectId: 11, projectName: 'Лицей'});
  });

  test('fails closed for ownerless or same-name projects', () => {
    expect(materialNormProjectOwnerByName([
      {id: 11, name: 'Лицей'},
    ], 'Лицей')).toBeNull();
    expect(materialNormProjectOwnerByName([
      {id: 11, companyId: 4, name: 'Лицей'},
      {id: 12, companyId: 5, name: 'Лицей'},
    ], 'Лицей')).toBeNull();
  });
});

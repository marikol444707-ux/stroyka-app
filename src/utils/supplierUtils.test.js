import { groupSuppliers } from './supplierUtils';

describe('groupSuppliers', () => {
  it('keeps request and recommendation flags when linked supplier cards are merged', () => {
    const [group] = groupSuppliers([
      {
        id: 17,
        name: 'АО «САТУРН ЮГ»',
        inn: '2635000000',
        alreadyRequested: false,
        aiRecommend: false,
        deliveriesCount: 1,
      },
      {
        id: 25,
        name: 'ООО Сатурн',
        inn: '2635000000',
        alreadyRequested: true,
        aiRecommend: true,
        deliveriesCount: 4,
      },
    ]);

    expect(group._supplierIds).toEqual([17, 25]);
    expect(group.alreadyRequested).toBe(true);
    expect(group.aiRecommend).toBe(true);
    expect(group.deliveriesCount).toBe(4);
  });
});

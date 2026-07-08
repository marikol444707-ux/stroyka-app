import { splitSupplierOffersByStatus } from './supplyUtils';

describe('splitSupplierOffersByStatus', () => {
  it('keeps working KP offers separate from withdrawn and rejected history', () => {
    const result = splitSupplierOffersByStatus([
      { id: 1, status: 'Ожидает ответа' },
      { id: 2, status: 'Отозвано' },
      { id: 3, status: 'Получено' },
      { id: 4, status: 'Отклонено' },
      { id: 5, status: 'Утверждено' },
    ]);

    expect(result.active.map(offer => offer.id)).toEqual([1, 3, 5]);
    expect(result.history.map(offer => offer.id)).toEqual([2, 4]);
  });

  it('treats an empty or unknown status as a visible working offer', () => {
    const result = splitSupplierOffersByStatus([
      { id: 1, status: '' },
      { id: 2 },
    ]);

    expect(result.active.map(offer => offer.id)).toEqual([1, 2]);
    expect(result.history).toEqual([]);
  });
});

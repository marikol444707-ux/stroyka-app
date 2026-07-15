import { performerRows } from './WorkAssignmentModal';

describe('work assignment performers', () => {
  it('offers a subcontractor as an estimate work assignee', () => {
    const rows = performerRows([], [
      { id: 11, name: 'ИП Исполнитель', role: 'субподрядчик' },
      { id: 12, name: 'Бухгалтер', role: 'бухгалтер' },
    ]);

    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      contractorId: 11,
      name: 'ИП Исполнитель',
      employmentType: 'субподрядчик',
    });
  });
});

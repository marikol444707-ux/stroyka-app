import {
  notificationsForUser,
} from './notificationUtils';
import {buildHiddenWorkPhotoNotifications} from '../features/hidden-works/hiddenWorkPhotoNotifications';


describe('hidden-work photo notifications', () => {
  const user = {id: 12, name: 'Иванов', role: 'субподрядчик'};
  const estimate = {
    id: 7,
    projectName: 'Лицей',
    status: 'Активная',
    workPackage: 'Отделка',
    sections: [{
      name: 'Полы',
      items: [{
        estimateItemKey: 'floor-waterproofing',
        name: 'Гидроизоляция пола',
        hiddenWork: true,
        quantity: 20,
        doneQuantity: 0,
        unit: 'м²',
      }],
    }],
  };
  const assignment = {
    id: 55,
    contractId: 91,
    estimateItemKey: 'floor-waterproofing',
    projectName: 'Лицей',
    workPackage: 'Отделка',
    name: 'Гидроизоляция пола',
  };

  it('warns an assigned worker before hidden work is submitted', () => {
    const result = buildHiddenWorkPhotoNotifications({
      user,
      estimatesList: [estimate],
      brigadeContracts: [{id: 91, contractorId: 12, brigadeName: 'Иванов'}],
      brigadeContractItems: [assignment],
      workJournal: [],
    });

    expect(result).toHaveLength(1);
    expect(result[0]).toEqual(expect.objectContaining({
      type: 'work',
      recipientUserId: 12,
      title: 'Фотоотчёт обязателен',
      read: false,
    }));
    expect(result[0].text).toMatch(/Гидроизоляция пола.*Лицей.*фото/i);
  });

  it('does not warn a worker about another contractor assignment', () => {
    const result = buildHiddenWorkPhotoNotifications({
      user,
      estimatesList: [estimate],
      brigadeContracts: [{id: 91, contractorId: 99, brigadeName: 'Петров'}],
      brigadeContractItems: [assignment],
      workJournal: [],
    });

    expect(result).toEqual([]);
  });

  it('keeps warning while a hidden journal row has no photo', () => {
    const result = buildHiddenWorkPhotoNotifications({
      user,
      estimatesList: [],
      brigadeContractItems: [],
      workJournal: [{
        id: 88,
        masterId: 12,
        masterName: 'Иванов',
        project: 'Лицей',
        description: 'Гидроизоляция пола',
        hiddenWork: true,
        photoUrl: '',
        status: 'На проверке',
      }],
    });

    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('hidden-work-photo:journal:88');
  });

  it('does not warn after a journal photo is attached', () => {
    const result = buildHiddenWorkPhotoNotifications({
      user,
      estimatesList: [],
      brigadeContractItems: [],
      workJournal: [{
        id: 88,
        masterId: 12,
        masterName: 'Иванов',
        hiddenWork: true,
        photoUrl: '/tenant-files/88/content',
        status: 'На проверке',
      }],
    });

    expect(result).toEqual([]);
  });

  it('routes an explicitly addressed notification to the recipient', () => {
    const rows = notificationsForUser([
      {id: 'mine', type: 'work', text: 'Фото обязательно', recipientUserId: 12},
      {id: 'foreign', type: 'work', text: 'Фото обязательно', recipientUserId: 99},
    ], user);

    expect(rows.map(row => row.id)).toEqual(['mine']);
  });
});

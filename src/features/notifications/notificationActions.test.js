import {createNotificationActions} from './notificationActions';


describe('notification actions', () => {
  it('includes persistent hidden-work photo warnings in the worker bell', () => {
    const actions = createNotificationActions({
      hiddenWorkPhotoNotifications: [{
        id: 'hidden-work-photo:journal:88',
        type: 'work',
        text: 'Фото обязательно',
        recipientUserId: 12,
        read: false,
      }],
      notifications: [],
      user: {id: 12, name: 'Иванов', role: 'субподрядчик'},
    });

    expect(actions.myNotifications([]).map(item => item.id)).toEqual([
      'hidden-work-photo:journal:88',
    ]);
  });
});

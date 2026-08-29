import {createWorkJournalActions} from './workJournalActions';


describe('createWorkJournalActions hidden-work photo rule', () => {
  const originalAlert = global.alert;
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.alert = jest.fn();
    global.fetch = jest.fn();
  });

  afterEach(() => {
    global.alert = originalAlert;
    global.fetch = originalFetch;
  });

  it('stops a hidden estimate work before sending when its photo is missing', async () => {
    const actions = createWorkJournalActions({
      API: 'https://api.test',
      GENERAL_WORK_ROOM_NAME: 'Без помещения',
      denormalizeMeasure: Number,
      estimateWorkKey: () => 'estimate:7:item:2',
      estimateWorkParams: {'estimate:7:item:2': {photoUrl: ''}},
      estimatesList: [{id: 7, sections: []}],
      fmtMeasure: String,
      masterProjectId: '3',
      projects: [{id: 3, name: 'Лицей'}],
      rooms: [],
      toNum: Number,
    });

    await actions.submitEstimateWorkDone({
      estId: 7,
      sectionIdx: 0,
      itemIdx: 2,
      name: 'Гидроизоляция',
      quantity: 10,
      doneQuantity: 0,
      unit: 'м²',
      hiddenWork: true,
    }, 2);

    expect(global.alert).toHaveBeenCalledWith(expect.stringMatching(/скрыт.*фото/i));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('stops a supervisor from confirming hidden work without its photo', async () => {
    const actions = createWorkJournalActions({});

    await actions.confirmJ({
      id: 88,
      description: 'Гидроизоляция',
      hiddenWork: true,
      photoUrl: '',
    }, 1, 'Принято');

    expect(global.alert).toHaveBeenCalledWith(expect.stringMatching(/скрыт.*фото/i));
    expect(global.fetch).not.toHaveBeenCalled();
  });
});

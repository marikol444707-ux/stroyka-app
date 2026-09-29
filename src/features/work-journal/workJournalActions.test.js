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

  it('binds material sources and contract params to the stable item key after estimate rows are filtered', async () => {
    const previousFlag = process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED;
    process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED = '1';
    const confirm = jest.spyOn(window, 'confirm').mockReturnValue(true);
    const previousCrypto = window.crypto;
    Object.defineProperty(window, 'crypto', {configurable:true,value:{randomUUID:()=> '12345678-1234-4234-8234-123456789012'}});
    const material = {name:'Краска',quantity:2,unit:'кг',personalQuantity:1,warehouseQuantity:1,warehouseMaterialId:8};
    const draftKey = '7:0:0'; // Full estimate has a hidden material row before this work.
    const item = {id:'stable-work',estimateItemKey:'stable-work',name:'Покраска',quantity:10,doneQuantity:0,unit:'м²'};
    global.fetch.mockResolvedValue({ok:true,json:async()=>({ok:true})});
    sessionStorage.clear();
    try {
      const actions = createWorkJournalActions({
        API:'',companyContext:{selectedCompanyId:2},user:{id:11},GENERAL_WORK_ROOM_NAME:'Без помещения',
        denormalizeMeasure:Number,estimatePackage:()=> 'Основная',estimateWorkKey:()=>draftKey,
        estimateDoneDrafts:{[draftKey]:1},estimateWorkMaterials:{[draftKey]:[material]},estimateWorkParams:{},
        estimatesList:[{id:7,sections:[{name:'Раздел',items:[item]}]}],fmtMeasure:String,
        masterProjectId:'3',projects:[{id:3,name:'Лицей'}],rooms:[],toNum:Number,
        isPersonalMaterialRole:()=>true,autoFillNormMaterialsForWork:()=>[material],
        applyMaterialOverNormReason:(_project,rows)=>rows,materialNormOverrunReason:()=>'',
        materialWriteoffBlockMessage:()=>'',prepareWorkMaterialGroups:()=>[[material]],
        setEstimateDoneDrafts:jest.fn(),setEstimateWorkMaterials:jest.fn(),setEstimateWorkParams:jest.fn(),
        setEstimatesList:jest.fn(),refreshData:jest.fn(),notify:jest.fn(),
      });
      const estimateDraftValueRef={current:{[draftKey]:1}};
      await actions.submitEstimateWorkDone({...item,estId:7,sectionIdx:0,itemIdx:0,contractItemId:5,executionPricePerUnit:10},1,estimateDraftValueRef);
      expect(global.fetch).toHaveBeenCalledTimes(1);
      const payload=JSON.parse(global.fetch.mock.calls[0][1].body);
      expect(payload._workJournalMaterials['stable-work']).toEqual([material]);
      expect(payload._workJournalParams['stable-work']).toMatchObject({contractItemId:5,estimateItemKey:'stable-work'});
      expect(payload._workJournalMaterials[draftKey]).toBeUndefined();
      expect(estimateDraftValueRef.current).toEqual({});
    } finally {
      if (previousFlag === undefined) delete process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED;
      else process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED = previousFlag;
      confirm.mockRestore();sessionStorage.clear();
      Object.defineProperty(window, 'crypto', {configurable:true,value:previousCrypto});
    }
  });
});

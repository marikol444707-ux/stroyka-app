import {createWorkJournalActions} from './workJournalActions';

test('a second performer adds their delta to the estimate total, not their personal contract total', async () => {
  const oldFetch = global.fetch, oldAlert = global.alert;
  const item = {id:'work',name:'Монтаж',unit:'м2',quantity:100,doneQuantity:3};
  global.fetch = jest.fn(async () => ({ok:true,json:async()=>({ok:true,revision:8})}));
  global.alert = jest.fn();
  try {
    const actions = createWorkJournalActions({
      API:'/api',user:{id:12},masterProjectId:1,projects:[{id:1,name:'Объект'}],
      estimatesList:[{id:7,revision:7,sections:[{name:'Основная',items:[item]}]}],
      toNum:value=>Number(value)||0,denormalizeMeasure:Number,fmtMeasure:String,
      estimateWorkKey:()=> '7:0:0',estimatePackage:()=> 'Основная',
      estimateWorkParams:{},estimateWorkMaterials:{},rooms:[],GENERAL_WORK_ROOM_NAME:'Без помещения',
      isPersonalMaterialRole:()=>true,autoFillNormMaterialsForWork:()=>[],
      materialWriteoffBlockMessage:()=>'',materialNormOverrunReason:()=>'',
      applyMaterialOverNormReason:(_project,rows)=>rows,
      setEstimateWorkMaterials:jest.fn(),setEstimateWorkParams:jest.fn(),setEstimateDoneDrafts:jest.fn(),
      setEstimatesList:jest.fn(),refreshData:jest.fn(),notify:jest.fn(),
    });
    await actions.submitEstimateWorkDone({...item,estId:7,sectionIdx:0,itemIdx:0,
      estimateItemKey:'work',contractItemId:8,doneQuantity:0,executionPricePerUnit:50},0.5);
    const payload=JSON.parse(fetch.mock.calls[0][1].body);
    expect(payload.sections[0].items[0].doneQuantity).toBe(3.5);
    expect(payload.expectedRevision).toBe(7);
    expect(payload._workJournalParams.work.contractItemId).toBe(8);
  } finally { global.fetch=oldFetch;global.alert=oldAlert; }
});

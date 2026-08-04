import { createEstimatePageActions, ESTIMATE_IMPORT_MAX_BYTES, estimateImportFileError, estimateImportRequestError } from './estimatePageActions';

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

describe('estimate import versioning', () => {
  test('uses the next group version instead of stale form version', async () => {
    const fetchFn = jest.fn(async url => {
      if (url.endsWith('/parse-smeta')) return {data:{items:[{section:'Раздел',name:'Работа',unit:'шт',quantity:1,type:'work'}],count:1,meta:{}}};
      if (url.endsWith('/estimates')) return {data:{id:22}};
      return {json:async()=>({response:'{"warnings":[]}'})};
    });
    const noop = jest.fn();
    const actions = createEstimatePageActions({
      API:'', ROLE_LABELS:{}, applyEstimateActivationState:rows=>rows, aiMessages:[], autoReconcileEstimateChanges:noop,
      brigadeContracts:[], buildEstimateDiffContent:noop, contracts:[], createEstimateReconciliation:noop,
      enrichEstimateMeasurementBasis:sections=>sections, estimateDiffBaseFor:noop, estimateItemMaterialSum:noop,
      estimateItemTotal:noop, estimateItemTypeMeta:noop, estimateItemWorkSum:noop, estimateQualityRows:()=>[],
      executionPriceFillPercent:0, exportToExcel:noop, estimatesList:[], isGlobalEstimateTemplate:()=>false,
      isLeadership:true, isEstimateWorkItem:()=>true, materials:[], newEstimate:{projectId:'1',projectName:'Объект',version:'1.0',smetaType:'Заказчик',workPackage:'Отопление',status:'Черновик'},
      nextEstimateVersionFor:()=> '3.0', normalizeEstimateImportSections:sections=>sections, normalizeEstimateItemType:value=>value,
      projects:[{id:1,name:'Объект'}], queueEstimateDiffReviewTask:noop, queueEstimateNormReviewTask:noop,
      queueEstimateQualityReviewTask:noop, readApiResult:async response=>response.data, sameEstimateGroup:()=>true,
      setAiInput:noop, setAiLoading:noop, setAiMessages:noop, setDistributeAssignments:noop, setDistributeBrigades:noop,
      setEstimateChatHistoryLoading:noop, setEstimateChatInput:noop, setEstimateChatLoading:noop, setEstimateChatMessages:noop,
      setEstimateVersions:noop, setEstimatesList:noop, setEstimatesTab:noop, setExecutionPriceFillPercent:noop,
      setImportValidating:noop, setImportValidationWarnings:noop, setSelectedEstimate:noop, setSelectedVersionsToCompare:noop,
      setShowAiChat:noop, setShowDistribute:noop, setShowEstimateChat:noop, setShowVersionHistory:noop, setShowWorkAssignment:noop,
      showPreview:noop, staff:[], toNum:Number, user:{role:'директор'}, fetchFn, alertFn:noop,
    });
    const target = {files:[new File(['x'], 'Отопление.xlsx')], value:'selected'};

    await actions.handleEstimateImportFile({target});

    const saveCall = fetchFn.mock.calls.find(([url]) => url.endsWith('/estimates'));
    expect(JSON.parse(saveCall[1].body).version).toBe('3.0');
  });
});

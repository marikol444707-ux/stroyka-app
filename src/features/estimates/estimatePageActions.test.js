import { buildEstimatePreviewHtml, createEstimatePageActions, ESTIMATE_IMPORT_MAX_BYTES, estimateHiddenWorksResultMessage, estimateImportFileError, estimateImportRequestError } from './estimatePageActions';

describe('estimate preview HTML', () => {
  test('encodes imported estimate text instead of turning it into markup', () => {
    const html = buildEstimatePreviewHtml({
      estimate: {
        name: '<img src=x onerror="window.__xss=1">',
        sections: [{
          name: '<script>window.__xss=2</script>',
          items: [{
            name: '<svg onload="window.__xss=3">',
            unit: '<iframe srcdoc="bad">',
            quantity: 1,
            priceWork: 10,
          }],
        }],
      },
      estimateItemMaterialSum: () => 0,
      estimateItemTotal: () => 10,
      estimateItemTypeMeta: () => ({label: '<b onclick="bad()">Работа</b>'}),
      normalizeEstimateItemType: () => 'work',
      estimateMeasurementBasisMeta: () => ({label: '<a href="javascript:bad()">Основание</a>'}),
      estimateMeasurementBasisOf: () => 'estimate',
    });

    expect(html).toContain('&lt;img');
    expect(html).toContain('&lt;script&gt;');
    expect(html).toContain('&lt;svg');
    const preview = document.createElement('div');
    preview.innerHTML = html;
    expect(preview.querySelector('script, svg, iframe')).toBeNull();
    expect(preview.querySelector('[onerror], [onclick], [onload]')).toBeNull();
    expect(preview.querySelector('a[href^="javascript:"]')).toBeNull();
  });
});

describe('hidden works detection result', () => {
  test('identifies the local model instead of reporting a keyword fallback', () => {
    expect(estimateHiddenWorksResultMessage({
      count: 4,
      method: 'local_ai_canary',
    })).toBe('🔒 Отмечено работ для АОСР: 4 (определила локальная модель)');
  });

  test('keeps the safe fallback message for keyword detection', () => {
    expect(estimateHiddenWorksResultMessage({
      count: 2,
      method: 'keywords',
    })).toBe('🔒 Отмечено работ для АОСР: 2 (по ключевым словам — ИИ был недоступен)');
  });
});

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
      buildEstimateDiffContent:noop, contracts:[], createEstimateReconciliation:noop,
      enrichEstimateMeasurementBasis:sections=>sections, estimateDiffBaseFor:noop, estimateItemMaterialSum:noop,
      estimateItemTotal:noop, estimateItemTypeMeta:noop, estimateItemWorkSum:noop, estimateQualityRows:()=>[],
      executionPriceFillPercent:0, exportToExcel:noop, estimatesList:[], isGlobalEstimateTemplate:()=>false,
      isLeadership:true, isEstimateWorkItem:()=>true, materials:[], newEstimate:{projectId:'1',projectName:'Объект',version:'1.0',smetaType:'Заказчик',workPackage:'Отопление',status:'Черновик'},
      nextEstimateVersionFor:()=> '3.0', normalizeEstimateImportSections:sections=>sections, normalizeEstimateItemType:value=>value,
      projects:[{id:1,name:'Объект'}], queueEstimateDiffReviewTask:noop, queueEstimateNormReviewTask:noop,
      queueEstimateQualityReviewTask:noop, readApiResult:async response=>response.data, sameEstimateGroup:()=>true,
      setAiInput:noop, setAiLoading:noop, setAiMessages:noop,
      setEstimateChatHistoryLoading:noop, setEstimateChatInput:noop, setEstimateChatLoading:noop, setEstimateChatMessages:noop,
      setEstimateVersions:noop, setEstimatesList:noop, setEstimatesTab:noop, setExecutionPriceFillPercent:noop,
      setImportValidating:noop, setImportValidationWarnings:noop, setSelectedEstimate:noop, setSelectedVersionsToCompare:noop,
      setShowAiChat:noop, setShowEstimateChat:noop, setShowVersionHistory:noop, setShowWorkAssignment:noop,
      showPreview:noop, staff:[], toNum:Number, user:{role:'директор'}, fetchFn, alertFn:noop,
    });
    const target = {files:[new File(['x'], 'Отопление.xlsx')], value:'selected'};

    await actions.handleEstimateImportFile({target});

    const saveCall = fetchFn.mock.calls.find(([url]) => url.endsWith('/estimates'));
    expect(JSON.parse(saveCall[1].body).version).toBe('3.0');
  });

  test('saves the reconciliation and loads full revisions before background comparison', async () => {
    const fetchFn = jest.fn(async url => {
      if (url.endsWith('/parse-smeta')) return {data:{items:[{section:'Стены',name:'Штукатурка',unit:'м2',quantity:90,type:'work'}],count:1,meta:{}}};
      if (url.endsWith('/estimates')) return {data:{id:22}};
      return {json:async()=>({response:'{"warnings":[]}'})};
    });
    const backgroundDone = {};
    backgroundDone.promise = new Promise(resolve => { backgroundDone.resolve = resolve; });
    const queueEstimateDiffReviewTask = jest.fn();
    const autoReconcileEstimateChanges = jest.fn(async () => backgroundDone.resolve());
    const createEstimateReconciliation = jest.fn(async () => ({id:44}));
    const baseSummary = {
      id: 21,
      projectId: 1,
      projectName: 'Объект',
      workPackage: 'Отделка',
      smetaType: 'Заказчик',
      status: 'Активная',
      sectionsLoaded: false,
      sections: [],
    };
    const fullBase = {
      ...baseSummary,
      sectionsLoaded: true,
      sections: [{name:'Стены',items:[{name:'Штукатурка',unit:'м2',quantity:80}]}],
    };
    const loadEstimateDetails = jest.fn(async estimates => [fullBase, estimates[1]]);
    const noop = jest.fn();
    const actions = createEstimatePageActions({
      API:'', ROLE_LABELS:{}, applyEstimateActivationState:rows=>rows, aiMessages:[], autoReconcileEstimateChanges,
      buildEstimateDiffContent:noop, contracts:[], createEstimateReconciliation,
      enrichEstimateMeasurementBasis:sections=>sections, estimateDiffBaseFor:noop, estimateItemMaterialSum:noop,
      estimateItemTotal:noop, estimateItemTypeMeta:noop, estimateItemWorkSum:noop, estimateQualityRows:()=>[],
      executionPriceFillPercent:0, exportToExcel:noop, estimatesList:[baseSummary], isGlobalEstimateTemplate:()=>false,
      isLeadership:true, isEstimateWorkItem:()=>true, loadEstimateDetails, materials:[], newEstimate:{projectId:'1',projectName:'Объект',version:'1.0',smetaType:'Заказчик',workPackage:'Отделка',status:'Активная'},
      nextEstimateVersionFor:()=> '2.0', normalizeEstimateImportSections:sections=>sections, normalizeEstimateItemType:value=>value,
      projects:[{id:1,name:'Объект'}], queueEstimateDiffReviewTask, queueEstimateNormReviewTask:noop,
      queueEstimateQualityReviewTask:noop, readApiResult:async response=>response.data, sameEstimateGroup:()=>true,
      setAiInput:noop, setAiLoading:noop, setAiMessages:noop,
      setEstimateChatHistoryLoading:noop, setEstimateChatInput:noop, setEstimateChatLoading:noop, setEstimateChatMessages:noop,
      setEstimateVersions:noop, setEstimatesList:noop, setEstimatesTab:noop, setExecutionPriceFillPercent:noop,
      setImportValidating:noop, setImportValidationWarnings:noop, setSelectedEstimate:noop, setSelectedVersionsToCompare:noop,
      setShowAiChat:noop, setShowEstimateChat:noop, setShowVersionHistory:noop, setShowWorkAssignment:noop,
      showPreview:noop, staff:[], toNum:Number, user:{role:'директор'}, fetchFn, alertFn:noop,
    });
    const target = {files:[new File(['x'], 'Отделка.xlsx')], value:'selected'};

    await actions.handleEstimateImportFile({target});
    await backgroundDone.promise;

    expect(createEstimateReconciliation).toHaveBeenCalledWith(
      baseSummary,
      expect.objectContaining({id:22, status:'Активная'}),
      {silent:true},
    );
    expect(loadEstimateDetails).toHaveBeenCalledWith([
      baseSummary,
      expect.objectContaining({id:22}),
    ]);
    expect(queueEstimateDiffReviewTask).toHaveBeenCalledWith(
      fullBase,
      expect.objectContaining({id:22}),
      'Импорт сметы',
    );
  });
});

import {scannedSupplierSelection} from './scannedSupplierSelection';
test('explicit supplier replaces stale identity and template without touching invoice items or totals',()=>{
 const draft={supplierId:1,supplierInn:'wrong',scanRecognition:{method:'template',supplierId:1,templateId:9},items:[{name:'Goods'}],totalWithVat:244};
 const patch=scannedSupplierSelection(draft,{id:2,name:'Correct',inn:'1234567890',kpp:'123456789',ogrn:'123'});
 expect(patch).toMatchObject({supplierId:2,supplier:'Correct',supplierName:'Correct',supplierInn:'1234567890',isNewSupplier:false,scanRecognition:{supplierId:2,templateId:null,templateName:'',method:'manual'}});
 expect(patch.items).toBeUndefined();expect(patch.totalWithVat).toBeUndefined();expect(draft.supplierId).toBe(1);
 expect(scannedSupplierSelection({...draft,...patch},null,'New')).toMatchObject({supplierId:'',supplierInn:'',supplierKpp:'',supplierOgrn:'',scanRecognition:{supplierId:0,templateId:null}});
});

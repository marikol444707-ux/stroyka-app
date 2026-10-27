export function scannedSupplierSelection(draft, supplier, manualName = '') {
  const name = supplier ? supplier.name : manualName;
  return {supplierId:supplier?.id || '',supplierName:name,supplier:name,newSupplierName:name,isNewSupplier:!supplier,
    supplierInn:supplier?.inn || '',supplierKpp:supplier?.kpp || '',supplierOgrn:supplier?.ogrn || '',
    scanHasManualCorrections:true,scanRecognition:{...(draft.scanRecognition || {}),supplierId:supplier?.id || 0,supplierName:name,
      templateId:null,templateName:'',method:'manual',label:'Поставщик указан вручную'}};
}

const appendSupplierReqNote = (current, line) => {
  const base = String(current || '').trim();
  const addition = String(line || '').trim();
  if (!addition || base.includes(addition)) return base;
  return base ? base + '\n' + addition : addition;
};

const alertMessage = (message) => {
  if (typeof window !== 'undefined' && typeof window.alert === 'function') {
    window.alert(message);
  }
};

export function createSupplierPortalActions({
  API,
  mySupplier,
  refreshData,
  user,
}) {
  const supplierRequisitesPatchFromRecognition = (result, current = {}) => {
    const extracted = result?.extracted || {};
    const doc = result?.suggestedCrmDocument || {};
    const docType = String(extracted.docType || doc.docType || '').toLowerCase();
    const contractLike = docType.includes('договор') || docType.includes('контракт');
    const patch = {
      companyName: extracted.counterpartyName || '',
      inn: extracted.inn || '',
      kpp: extracted.kpp || '',
      ogrn: extracted.ogrn || '',
      address: extracted.legalAddress || '',
      bank: extracted.bank || '',
      bik: extracted.bik || '',
      account: extracted.bankAccount || '',
      korAccount: extracted.corrAccount || '',
      directorName: extracted.signerName || '',
      directorPosition: extracted.signerBasis || '',
      contractNumber: contractLike ? (extracted.number || '') : '',
      contractDate: contractLike ? (extracted.docDate || '') : '',
      contractUrl: contractLike ? (result?.fileUrl || '') : '',
      specialization: extracted.workType || '',
    };
    if (extracted.contractSubject) {
      patch.notes = appendSupplierReqNote(current.notes, 'Предмет договора: ' + extracted.contractSubject);
    }
    return Object.fromEntries(Object.entries(patch).filter(([, value]) => value));
  };

  const createOwnSupplierDocumentFromRecognition = async (docPatch, result) => {
    const supplierId = mySupplier?.id || 0;
    if (!supplierId) {
      alertMessage('Сначала сохраните реквизиты поставщика');
      return;
    }
    const extracted = result?.extracted || {};
    const res = await fetch(API + '/supplier-documents', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        supplierId,
        docType: docPatch.docType || extracted.docType || 'Другое',
        title: docPatch.title || extracted.documentTitle || 'Распознанный документ',
        fileUrl: docPatch.fileUrl || result?.fileUrl || '',
        status: 'На проверке',
        signedAt: extracted.docDate || '',
        notes: docPatch.notes || (extracted.contractSubject ? 'Предмет договора: ' + extracted.contractSubject : ''),
        uploadedBy: user?.name || '',
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.detail || data.error) {
      alertMessage(data.detail || data.error || 'Не удалось добавить документ');
      return;
    }
    await refreshData();
  };

  return {
    createOwnSupplierDocumentFromRecognition,
    supplierRequisitesPatchFromRecognition,
  };
}

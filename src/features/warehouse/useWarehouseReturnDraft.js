import { useCallback } from 'react';
import useWarehouseDraft from './useWarehouseDraft';
const positive = value => Number.isSafeInteger(value) && value > 0;
export function validateReturnDraft(data, companyId, userId) {
  const doc = data?.document, source = data?.source;
  if (data?.companyId !== companyId || data.userId !== userId || !Number.isSafeInteger(data.revision) || data.revision < 0
      || !doc || (doc.allocationId !== null && !positive(doc.allocationId))
      || typeof doc.quantity !== 'string' || doc.quantity.length > 100
      || typeof doc.reason !== 'string' || doc.reason.length > 1000
      || (doc.allocationId === null && (doc.quantity || doc.reason))
      || (source !== null && (!source || source.id !== doc.allocationId || source.companyId !== companyId
        || typeof source.projectName !== 'string' || typeof source.materialName !== 'string' || typeof source.unit !== 'string'))) {
    throw Error('Сервер не подтвердил черновик возврата пользователя и компании.');
  }
  return { ...data, document: { allocationId: doc.allocationId, quantity: doc.quantity, reason: doc.reason } };
}
export default function useWarehouseReturnDraft({ returning, quantity, reason, setReturning, setQuantity, setReason, setConfirmed, ...options }) {
  const applyDocument = useCallback((document, data) => {
    const source = data.source?.id === document.allocationId ? data.source : null;
    setReturning(document.allocationId ? source || { id: document.allocationId, projectName: `Распределение #${document.allocationId}`, materialName: '', unit: '', netQuantity: 0 } : null);
    setQuantity(document.quantity); setReason(document.reason);
    // Physical confirmation is deliberately session-local, never restored from a draft.
    setConfirmed(false);
  }, [setReturning, setQuantity, setReason, setConfirmed]);
  return useWarehouseDraft({ ...options, document: { allocationId: returning?.id ?? null, quantity, reason }, applyDocument,
    validate: validateReturnDraft, path: '/return-draft', downloadName: 'warehouse-return-draft.json' });
}

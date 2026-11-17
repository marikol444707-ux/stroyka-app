import { useCallback } from 'react';
import useWarehouseDraft from './useWarehouseDraft';
const positive = value => Number.isSafeInteger(value) && value > 0;
export function batchDocument(rows, reason) {
  return { rows: rows.map(row => ({ lotId: row.lotId === '' ? null : Number(row.lotId),
    projectId: row.projectId === '' ? null : Number(row.projectId), quantity: row.quantity })), reason };
}
export function validateDraft(data, companyId, userId) {
  if (data?.companyId !== companyId || data.userId !== userId || !Number.isSafeInteger(data.revision) || data.revision < 0
      || !Array.isArray(data.document?.rows) || !data.document.rows.length || data.document.rows.length > 50
      || typeof data.document.reason !== 'string' || data.document.reason.length > 1000
      || data.document.rows.some(r => !r || (r.lotId !== null && !positive(r.lotId)) || (r.projectId !== null && !positive(r.projectId))
        || typeof r.quantity !== 'string' || r.quantity.length > 100)
      || !Array.isArray(data.sources)) throw Error('Сервер не подтвердил черновик пользователя и компании.');
  return { ...data, document: { rows: data.document.rows.map(r => ({ lotId: r.lotId, projectId: r.projectId, quantity: r.quantity })), reason: data.document.reason } };
}

export default function useWarehouseBatchDraft({ rows, reason, setRows, setReason, setSelectedSources, ...options }) {
  const applyDocument = useCallback((document, data) => {
    setRows(document.rows.map(row => ({ ...row, lotId: row.lotId === null ? '' : String(row.lotId), projectId: row.projectId === null ? '' : String(row.projectId) })));
    setReason(document.reason);
    setSelectedSources(data.sources.map(source => ({ ...source, availabilityUnknown: true })));
  }, [setRows, setReason, setSelectedSources]);
  const draft = useWarehouseDraft({ ...options, document: batchDocument(rows, reason), applyDocument, validate: validateDraft,
    path: '/draft', downloadName: 'warehouse-batch-draft.json' });
  const clear = () => { setRows([{ lotId: '', projectId: '', quantity: '' }]); setReason(''); setSelectedSources([]); };
  return { ...draft, clear, reloadAfterIssue: draft.reloadAfterOperation };
}

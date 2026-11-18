import useWarehouseDraft from './useWarehouseDraft';
import { validateTransfer } from './distributionCommands';

export const emptyTransferDraft = () => ({ kind: null, allocationId: null, transferId: null,
  toProjectId: null, quantity: '', expectedQuantity: '', reason: '' });
const positive = value => Number.isSafeInteger(value) && value > 0;
export function validateTransferDraft(data, companyId, userId) {
  const doc = data?.document, source = data?.source;
  const fail = () => { throw Error('Сервер не подтвердил черновик перемещения пользователя и компании.'); };
  if (data?.companyId !== companyId || data.userId !== userId || !Number.isSafeInteger(data.revision) || data.revision < 0
      || !doc || ![null, 'dispatch', 'receipt'].includes(doc.kind)
      || !['allocationId', 'transferId', 'toProjectId'].every(key => doc[key] === null || positive(doc[key]))
      || !['quantity', 'expectedQuantity', 'reason'].every(key => typeof doc[key] === 'string' && doc[key].length <= (key === 'reason' ? 1000 : 100) && !doc[key].includes('\0'))
      || (doc.kind === null && Object.keys(emptyTransferDraft()).some(key => doc[key] !== emptyTransferDraft()[key]))
      || (doc.kind === 'dispatch' && (!doc.allocationId || doc.transferId || doc.expectedQuantity))
      || (doc.kind === 'receipt' && (!doc.transferId || doc.allocationId || doc.toProjectId))) fail();
  if (source !== null) {
    if (!source || !doc.kind || source.companyId !== companyId || source.id !== (doc.kind === 'dispatch' ? doc.allocationId : doc.transferId)) fail();
    if (doc.kind === 'receipt') validateTransfer(source, companyId);
    else if (!['projectName', 'materialName', 'unit'].every(key => typeof source[key] === 'string') || !positive(source.projectId)) fail();
  }
  return { ...data, document: Object.fromEntries(Object.keys(emptyTransferDraft()).map(key => [key, doc[key]])) };
}
export default function useWarehouseTransferDraft(options) {
  return useWarehouseDraft({ ...options, validate: validateTransferDraft, path: '/transfer-draft', downloadName: 'warehouse-transfer-draft.json' });
}

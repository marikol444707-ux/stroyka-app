/* Synthetic in-memory transfers for browser checks. No DB/auth/quality proof. */
function transferCommand(state, pathname, body, { fail, units, decimal, balance }) {
  const stamp = { reason: body.reason.trim(), createdAt: new Date().toISOString(), createdBy: 'Анна — preview' };
  if (pathname === '/warehouse-distributions/transfers') {
    const source = state.records.find(row => row.id === body.allocationId);
    if (!source || ![11, 12].includes(body.toProjectId)) fail('Распределение или объект не найден', 404);
    if (source.projectId === body.toProjectId) fail('Нужен другой объект');
    const amount = units(body.quantity);
    if (amount > balance(source.netQuantity)) fail('Недостаточно невыданного остатка', 409);
    const shipment = {
      id: state.nextTransferId++, companyId: 2, sourceAllocationId: source.id,
      fromProjectId: source.projectId, fromProjectName: source.projectName,
      toProjectId: body.toProjectId, toProjectName: body.toProjectId === 11 ? 'Школа' : 'Больница',
      warehouseInvoiceId: source.warehouseInvoiceId, invoiceNumber: source.invoiceNumber,
      lotId: source.lotId, materialName: source.materialName, unit: source.unit,
      quantity: decimal(amount), receivedQuantity: '0', inTransitQuantity: decimal(amount),
      status: 'in_transit', receipts: [], ...stamp,
    };
    source.netQuantity = decimal(balance(source.netQuantity) - amount);
    source.transferredQuantity = decimal(balance(source.transferredQuantity || '0') + amount);
    state.transfers.unshift(shipment);
    return { ok: true, requestId: body.requestId, item: structuredClone(shipment), synthetic: true };
  }
  const match = pathname.match(/^\/warehouse-distributions\/transfers\/(\d+)\/receipts$/);
  const shipment = match && state.transfers.find(row => row.id === Number(match[1]));
  if (!shipment) fail('Отправка не найдена', 404);
  const accepted = body.quantity === '0' ? 0 : units(body.quantity);
  const expected = units(body.expectedQuantity);
  if (accepted > expected || expected > balance(shipment.inTransitQuantity)) fail('Количество превышает остаток в пути', 409);
  let allocationId = null;
  if (accepted) {
    const source = state.records.find(row => row.id === shipment.sourceAllocationId);
    allocationId = state.nextId++;
    state.records.unshift({ ...source, id: allocationId, projectId: shipment.toProjectId,
      projectName: shipment.toProjectName, quantity: decimal(accepted), returnedQuantity: '0',
      transferredQuantity: '0', netQuantity: decimal(accepted), returns: [], ...stamp });
  }
  shipment.receivedQuantity = decimal(balance(shipment.receivedQuantity) + accepted);
  shipment.inTransitQuantity = decimal(balance(shipment.inTransitQuantity) - accepted);
  shipment.receipts.push({ id: state.nextTransferReceiptId++, quantity: decimal(accepted),
    expectedQuantity: decimal(expected), discrepancyQuantity: decimal(expected - accepted), allocationId, ...stamp });
  shipment.status = shipment.inTransitQuantity === '0' ? 'received'
    : shipment.receipts.some(row => balance(row.discrepancyQuantity) > 0) ? 'discrepancy'
      : balance(shipment.receivedQuantity) > 0 ? 'partial' : 'in_transit';
  return { ok: true, requestId: body.requestId, item: structuredClone(shipment), synthetic: true };
}

function transferList(state, params) {
  const limit = Math.min(200, Math.max(1, Number(params.get('limit')) || 100));
  const before = Number(params.get('beforeId'));
  const q = (params.get('q') || '').trim().toLocaleLowerCase('ru');
  const rows = state.transfers.filter(row => (!before || row.id < before)
    && [row.fromProjectName, row.toProjectName, row.materialName, row.invoiceNumber, row.id]
      .join(' ').toLocaleLowerCase('ru').includes(q)).sort((a, b) => b.id - a.id);
  const items = rows.slice(0, limit);
  const truncated = rows.length > limit;
  return { items, truncated, nextCursor: truncated ? items[items.length - 1].id : null };
}

module.exports = { transferCommand, transferList };

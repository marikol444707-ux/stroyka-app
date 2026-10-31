export const createMaterialTransferActions = ({
  API,
  companyContext = {},
  user = {},
  receiptScopeRef = { current: null },
  fmtMeasure,
  notify,
  refreshData,
  setMaterialTransfers,
  toNum,
  alertFn = window.alert,
  promptFn = window.prompt,
}) => {
  const companyId = Number(companyContext.selectedCompanyId);
  const scopeKey = JSON.stringify([API, user?.id, companyContext.mode, companyId, Boolean(companyContext.loading)]);
  if (receiptScopeRef.current?.key !== scopeKey) receiptScopeRef.current = { key: scopeKey, pending: new Set() };
  const scope = receiptScopeRef.current;
  const isCurrent = () => receiptScopeRef.current === scope;
  const confirmMaterialReceipt = async (transferId) => {
    if (!isCurrent() || scope.pending.has(transferId)) return false;
    if (!user?.id || companyContext.loading || companyContext.mode !== 'company' || !Number.isSafeInteger(companyId) || companyId <= 0) {
      alertFn('Выберите компанию для подтверждения получения материала.');
      return false;
    }
    scope.pending.add(transferId);
    try {
      const response = await fetch(API + '/material-transfers/' + transferId + '/sign', {
        method: 'PUT', headers: { 'X-Company-Id': String(companyId), 'X-Company-Mode': 'company' },
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || data.ok !== true) {
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Получение материала не подтверждено сервером.');
      }
      if (!isCurrent()) return false;
      setMaterialTransfers(prev => prev.map(t => t.id === transferId ? {...t, signed: true} : t));
      return true;
    } catch (error) {
      if (isCurrent()) alertFn('Не удалось подтвердить получение: ' + error.message
        + ' Обновите список или повторите подтверждение этой передачи.');
      return false;
    } finally {
      scope.pending.delete(transferId);
    }
  };

  const returnMaterialToProject = async (materialRow) => {
    const maxQty = toNum(materialRow?.quantity);
    if (!materialRow || maxQty <= 0) return;

    const raw = promptFn('Сколько вернуть на склад объекта? Доступно: ' + fmtMeasure(maxQty, materialRow.unit), String(maxQty));
    if (raw === null) return;

    const qty = toNum(raw);
    if (!qty || qty <= 0) {
      alertFn('Укажите количество больше 0');
      return;
    }
    if (qty > maxQty) {
      alertFn('Нельзя вернуть больше остатка: ' + fmtMeasure(maxQty, materialRow.unit));
      return;
    }

    const res = await fetch(API + '/material-transfers/return', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        projectName: materialRow.project,
        materialName: materialRow.name,
        quantity: qty,
        unit: materialRow.unit,
        workPackage: materialRow.workPackage || '',
        date: new Date().toISOString().split('T')[0],
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      alertFn('Ошибка: ' + (data.detail || data.error || 'не удалось вернуть материал'));
      return;
    }

    notify('Материал возвращён на склад объекта: ' + materialRow.name + ' · ' + fmtMeasure(qty, materialRow.unit), 'material');
    await refreshData();
  };

  return {
    confirmMaterialReceipt,
    returnMaterialToProject,
  };
};

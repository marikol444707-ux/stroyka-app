export const createMaterialTransferActions = ({
  API,
  fmtMeasure,
  notify,
  refreshData,
  setMaterialTransfers,
  toNum,
  alertFn = window.alert,
  promptFn = window.prompt,
}) => {
  const confirmMaterialReceipt = async (transferId) => {
    await fetch(API + '/material-transfers/' + transferId + '/sign', {method: 'PUT'});
    setMaterialTransfers(prev => prev.map(t => t.id === transferId ? {...t, signed: true} : t));
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

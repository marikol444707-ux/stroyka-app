import React from 'react';
import { API } from '../api';
import {
  EmptyTransfersState,
  MaterialTransferForm,
  TransfersTable
} from './materials/ProjectMaterialsTransferParts';

const emptyTransfer = () => ({
  materialName: '',
  quantity: '',
  unit: 'шт',
  workPackage: '',
  items: [],
  toPerson: '',
  toPersonRole: '',
  toUserId: '',
  fromLocation: 'Основной склад',
  notes: '',
  transferDate: new Date().toISOString().split('T')[0],
});

const emptyProjectTransfer = (projectName) => ({
  ...emptyTransfer(),
  fromLocation: projectName || '',
});

export default function ProjectMaterialsTransferPanel({
  projectName,
  showTransferForm,
  setShowTransferForm,
  newTransfer,
  setNewTransfer,
  materialTransfers = [],
  setMaterialTransfers,
  materials = [],
  setMaterials,
  supplyRequests = [],
  staff = [],
  workJournal = [],
  history = [],
  workPackageOptions = [],
  user,
  C,
  card,
  inp,
  tbl,
  tblH,
  tblC,
  btnO,
  btnG,
  btnGr,
  btnB,
  btnR,
  normalizeUnit,
  convertUnits,
  fmtMeasure,
  showPreview,
  buildM15Content,
}) {
  const toNum = (v) => {
    if (v === null || v === undefined || v === '') return 0;
    const n = Number(String(v).replace(',', '.').replace(/\s+/g, ''));
    return Number.isFinite(n) ? n : 0;
  };
  const materialKey = (v) => (v || '').trim().toLowerCase();
  const sourceProject = projectName || newTransfer.fromLocation || '';
  const normalizeTransferItems = React.useCallback((items = []) => (
    (Array.isArray(items) ? items : [])
      .map(item => ({
        materialName: item.materialName || item.name || '',
        quantity: item.quantity ?? '',
        unit: item.unit || 'шт',
        workPackage: item.workPackage || item.work_package || '',
      }))
      .filter(item => item.materialName)
  ), []);
  const transferItemsFromState = React.useCallback((transfer = {}) => {
    const explicitItems = Array.isArray(transfer.items) ? transfer.items : [];
    const cleaned = explicitItems
      .map(item => ({
        materialName: item.materialName || item.name || '',
        quantity: item.quantity ?? '',
        unit: item.unit || 'шт',
        workPackage: item.workPackage || item.work_package || '',
      }))
      .filter(item => item.materialName);
    if (cleaned.length > 0) return cleaned;
    if (!transfer.materialName) return [];
    return [{
      materialName: transfer.materialName,
      quantity: transfer.quantity,
      unit: transfer.unit || 'шт',
      workPackage: transfer.workPackage || '',
    }];
  }, []);
  const selectedTransferItems = React.useMemo(() => transferItemsFromState(newTransfer), [newTransfer, transferItemsFromState]);
  const primaryTransferItem = selectedTransferItems[0] || {
    materialName: newTransfer.materialName || '',
    quantity: newTransfer.quantity || '',
    unit: newTransfer.unit || 'шт',
    workPackage: newTransfer.workPackage || '',
  };
  const stockForTransferItem = (item) => materials.find(m =>
    m.name === item.materialName &&
    m.project === sourceProject &&
    (m.workPackage || m.work_package || '') === (item.workPackage || '')
  );
  const transferItemQty = (item) => toNum(item.quantity);
  const transferItemStockQty = (item) => toNum(stockForTransferItem(item)?.quantity);
  const transferItemOverStock = (item) => !!item.materialName && transferItemQty(item) > transferItemStockQty(item);
  const updateTransferItems = React.useCallback((itemsOrUpdater) => {
    setNewTransfer(prev => {
      const currentItems = transferItemsFromState(prev);
      const nextItemsRaw = typeof itemsOrUpdater === 'function' ? itemsOrUpdater(currentItems) : itemsOrUpdater;
      const normalizedItems = normalizeTransferItems(nextItemsRaw);
      const first = normalizedItems[0] || {materialName: '', quantity: '', unit: 'шт', workPackage: ''};
      return {
        ...prev,
        items: normalizedItems,
        materialName: first.materialName,
        quantity: first.quantity,
        unit: first.unit || 'шт',
        workPackage: normalizedItems.length === 1 ? (first.workPackage || '') : '',
      };
    });
  }, [normalizeTransferItems, setNewTransfer, transferItemsFromState]);
  const fmtQty = (qty, unit) => {
    if (fmtMeasure) return fmtMeasure(qty, unit);
    const n = Math.round(toNum(qty) * 1000) / 1000;
    return n.toLocaleString('ru-RU') + (unit ? ' ' + unit : '');
  };
  const parseJournalMaterials = (raw) => {
    if (!raw) return [];
    if (Array.isArray(raw)) return raw;
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (_) {
      return [];
    }
  };

  const availableMaterials = materials.filter(m => m.project === sourceProject);
  const transfers = materialTransfers.filter(t => t.projectName === projectName);
  const selectedStockQty = transferItemStockQty(primaryTransferItem);
  const hasStockOverrun = selectedTransferItems.some(item => transferItemOverStock(item));
  const receiverRole = (newTransfer.toPersonRole || '').trim().toLowerCase();
  const needsWorkPackage = !!projectName && ['мастер', 'бригадир', 'субподрядчик'].includes(receiverRole);
  const missingWorkPackage = needsWorkPackage && selectedTransferItems.some(item => !(item.workPackage || '').trim());

  const packageMatches = (rowPackage, targetPackage) => {
    if (!targetPackage) return true;
    return rowPackage === targetPackage;
  };

  const personMaterialBalance = (personName, materialName, workPackage = '') => {
    const nameKey = materialKey(materialName);
    if (!personName || !nameKey) return {issued: 0, pending: 0, used: 0, returned: 0, balance: 0};
    const person = (staff || []).find(s => s.name === personName);
    const personId = person?.id || newTransfer.toUserId || newTransfer.to_user_id;
    const transferBelongsToPerson = (t) => {
      const transferUserId = t.toUserId || t.to_user_id;
      if (personId && transferUserId) return Number(transferUserId) === Number(personId);
      return !transferUserId && t.toPerson === personName;
    };
    let issued = 0;
    let pending = 0;
    let used = 0;
    let returned = 0;

    transfers
      .filter(t => transferBelongsToPerson(t) && materialKey(t.materialName) === nameKey && packageMatches(t.workPackage, workPackage))
      .forEach(t => {
        if (t.signed) issued += toNum(t.quantity);
        else pending += toNum(t.quantity);
      });

    (workJournal || [])
      .filter(w => w.project === projectName && !['Отклонено', 'Аннулировано'].includes(w.status || '') && ((w.masterName || w.master_name || '') === personName) && packageMatches(w.workPackage || w.work_package, workPackage))
      .forEach(w => {
        parseJournalMaterials(w.materialsUsed !== undefined ? w.materialsUsed : w.materials_used)
          .filter(m => materialKey(m.name) === nameKey)
          .forEach(m => { used += toNum(m.quantity); });
      });

    (history || [])
      .filter(h => h.project === projectName && h.type === 'возврат от мастера' && ((h.issuedBy || h.issued_by || '') === personName) && materialKey(h.material) === nameKey && packageMatches(h.workPackage || h.work_package, workPackage))
      .forEach(h => { returned += toNum(h.quantity); });

    return {issued, pending, used, returned, balance: Math.max(0, issued - used - returned)};
  };

  const selectedPersonBalance = personMaterialBalance(newTransfer.toPerson, primaryTransferItem.materialName, primaryTransferItem.workPackage);
  const canSaveTransfer = selectedTransferItems.length > 0 &&
    selectedTransferItems.every(item => transferItemQty(item) > 0) &&
    !!newTransfer.toPerson &&
    !hasStockOverrun &&
    !missingWorkPackage;

  const matchingRequestForItem = (item) => {
    const matName = (item.materialName || '').toLowerCase().trim();
    if (!matName) return null;

    return supplyRequests.find(r => {
      if (r.project !== projectName) return false;
      if (r.status === 'Отменена' || r.status === 'Отклонена') return false;
      const requestName = (r.materialName || '').toLowerCase().trim();
      if (!requestName) return false;
      return requestName.includes(matName.split(' ')[0]) || matName.includes(requestName.split(' ')[0]);
    });
  };
  const matchingRequest = matchingRequestForItem(primaryTransferItem);

  const requesterOptions = (() => {
    const materialNames = selectedTransferItems.map(item => (item.materialName || '').toLowerCase().trim()).filter(Boolean);
    const requesters = new Map();

    supplyRequests
      .filter(r => r.project === projectName && (r.status === 'Утверждена' || r.status === 'Подтверждена прорабом' || r.status === 'Новая'))
      .forEach(r => {
        if (materialNames.length > 0) {
          const requestName = (r.materialName || '').toLowerCase();
          const matchesAny = materialNames.some(matName => requestName.includes(matName.split(' ')[0]) || matName.includes(requestName.split(' ')[0] || ''));
          if (!matchesAny) return;
        }
        if (r.createdBy && !requesters.has(r.createdBy)) {
          requesters.set(r.createdBy, {
            name: r.createdBy,
            role: r.requestedByRole || '',
            materialName: r.materialName,
            quantity: r.quantity,
            unit: r.unit,
          });
        }
      });

    return {
      requesters: Array.from(requesters.values()),
      requesterNames: new Set(requesters.keys()),
    };
  })();

  const saveTransfer = async () => {
    if (selectedTransferItems.length === 0 || !newTransfer.toPerson) return;
    if (!canSaveTransfer) {
      alert(hasStockOverrun
        ? 'Нельзя выдать больше остатка на складе.'
        : missingWorkPackage
          ? 'Для выдачи мастеру, бригадиру или субподрядчику выберите пакет работ.'
        : 'Укажите материалы, получателя и количество больше нуля по каждой строке.');
      return;
    }

    const savedTransfers = [];
    for (const item of selectedTransferItems) {
      const data = {
        ...newTransfer,
        items: undefined,
        materialName: item.materialName,
        quantity: item.quantity,
        unit: item.unit,
        workPackage: item.workPackage,
        projectName,
        fromLocation: sourceProject,
        createdBy: user.name,
      };
      const res = await fetch(API + '/material-transfers', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data),
      });
      const saved = await res.json();

      if (!res.ok || !saved.ok) {
        if (savedTransfers.length > 0) {
          setMaterialTransfers(prev => [...savedTransfers.map(row => ({...row.data, id: row.id, signed: false})).reverse(), ...prev]);
          setMaterials(prev => savedTransfers.reduce((acc, row) => acc.map(m => (
            m.name === row.data.materialName &&
            m.project === sourceProject &&
            (m.workPackage || m.work_package || '') === (row.data.workPackage || '')
          ) ? {...m, quantity: Number(m.quantity || 0) - Number(row.data.quantity || 0)} : m), prev));
        }
        alert('Ошибка по позиции «' + item.materialName + '»: ' + (saved.detail || saved.error || 'не удалось списать со склада'));
        return;
      }
      savedTransfers.push({id: saved.id, data});
    }

    setMaterialTransfers(prev => [...savedTransfers.map(row => ({...row.data, id: row.id, signed: false})).reverse(), ...prev]);

    setMaterials(prev => savedTransfers.reduce((acc, row) => acc.map(m => (
      m.name === row.data.materialName &&
      m.project === sourceProject &&
      (m.workPackage || m.work_package || '') === (row.data.workPackage || '')
    ) ? {...m, quantity: Number(m.quantity || 0) - Number(row.data.quantity || 0)} : m), prev));

    setNewTransfer(emptyProjectTransfer(projectName));
    setShowTransferForm(false);
  };

  const signTransfer = async (transferId) => {
    const res = await fetch(API + '/material-transfers/' + transferId + '/sign', {method: 'PUT'});
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      alert('Ошибка: ' + (data.detail || data.error || 'не удалось подписать передачу'));
      return;
    }
    setMaterialTransfers(prev => prev.map(mt => mt.id === transferId ? {...mt, signed: true, signedAt: new Date().toISOString()} : mt));
  };

  const deleteTransfer = async (transfer) => {
    if (!transfer || transfer.signed) return;
    const res = await fetch(API + '/material-transfers/' + transfer.id, {method: 'DELETE'});
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      alert('Ошибка: ' + (data.detail || data.error || 'не удалось удалить передачу'));
      return;
    }
    setMaterialTransfers(prev => prev.filter(mt => mt.id !== transfer.id));
    const qty = Number(transfer.quantity || 0);
    setMaterials(prev => prev.map(m => (
      m.name === transfer.materialName &&
      m.project === (transfer.fromLocation || projectName) &&
      (m.workPackage || m.work_package || '') === (transfer.workPackage || '')
    ) ? {...m, quantity: Number(m.quantity || 0) + qty} : m));
  };

  return (
    <div>
      {showTransferForm && (
        <MaterialTransferForm
          projectName={projectName}
          C={C}
          card={card}
          inp={inp}
          btnO={btnO}
          btnG={btnG}
          btnGr={btnGr}
          availableMaterials={availableMaterials}
          newTransfer={newTransfer}
          setNewTransfer={setNewTransfer}
          selectedTransferItems={selectedTransferItems}
          updateTransferItems={updateTransferItems}
          selectedStockQty={selectedStockQty}
          selectedPersonBalance={selectedPersonBalance}
          hasStockOverrun={hasStockOverrun}
          matchingRequest={matchingRequest}
          matchingRequestForItem={matchingRequestForItem}
          personMaterialBalance={personMaterialBalance}
          transferItemStockQty={transferItemStockQty}
          transferItemOverStock={transferItemOverStock}
          normalizeUnit={normalizeUnit}
          convertUnits={convertUnits}
          fmtQty={fmtQty}
          requesterOptions={requesterOptions}
          staff={staff}
          workPackageOptions={workPackageOptions}
          needsWorkPackage={needsWorkPackage}
          missingWorkPackage={missingWorkPackage}
          canSaveTransfer={canSaveTransfer}
          saveTransfer={saveTransfer}
          setShowTransferForm={setShowTransferForm}
        />
      )}

      <TransfersTable
        transfers={transfers}
        C={C}
        tbl={tbl}
        tblH={tblH}
        tblC={tblC}
        btnO={btnO}
        btnB={btnB}
        btnR={btnR}
        fmtQty={fmtQty}
        personMaterialBalance={personMaterialBalance}
        signTransfer={signTransfer}
        deleteTransfer={deleteTransfer}
        showPreview={showPreview}
        buildM15Content={buildM15Content}
      />

      {transfers.length === 0 && (
        <EmptyTransfersState C={C} card={card}/>
      )}
    </div>
  );
}

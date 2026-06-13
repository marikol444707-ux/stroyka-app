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
  toPerson: '',
  toPersonRole: '',
  fromLocation: 'Основной склад',
  notes: '',
  transferDate: new Date().toISOString().split('T')[0],
});

export default function ProjectMaterialsTransferPanel({
  projectName,
  showTransferForm,
  setShowTransferForm,
  newTransfer,
  setNewTransfer,
  materialTransfers = [],
  setMaterialTransfers,
  warehouseMain = [],
  setWarehouseMain,
  materials = [],
  setMaterials,
  visibleProjects = [],
  supplyRequests = [],
  staff = [],
  brigadeContracts = [],
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

  const availableMaterials = [
    ...warehouseMain.filter(m => m.location === newTransfer.fromLocation || (!m.location && newTransfer.fromLocation === 'Основной склад')),
    ...materials.filter(m => m.project === newTransfer.fromLocation),
  ];
  const transfers = materialTransfers.filter(t => t.projectName === projectName);
  const selectedStock = newTransfer.fromLocation === 'Основной склад'
    ? warehouseMain.find(m => m.name === newTransfer.materialName)
    : materials.find(m =>
        m.name === newTransfer.materialName &&
        m.project === newTransfer.fromLocation &&
        (m.workPackage || m.work_package || '') === (newTransfer.workPackage || '')
      );
  const selectedQty = toNum(newTransfer.quantity);
  const selectedStockQty = toNum(selectedStock?.quantity);
  const hasStockOverrun = !!newTransfer.materialName && selectedQty > selectedStockQty;

  const packageMatches = (rowPackage, targetPackage) => {
    if (!targetPackage) return true;
    return !rowPackage || rowPackage === targetPackage;
  };

  const personMaterialBalance = (personName, materialName, workPackage = '') => {
    const nameKey = materialKey(materialName);
    if (!personName || !nameKey) return {issued: 0, pending: 0, used: 0, returned: 0, balance: 0};
    let issued = 0;
    let pending = 0;
    let used = 0;
    let returned = 0;

    transfers
      .filter(t => t.toPerson === personName && materialKey(t.materialName) === nameKey && packageMatches(t.workPackage, workPackage))
      .forEach(t => {
        if (t.signed) issued += toNum(t.quantity);
        else pending += toNum(t.quantity);
      });

    (workJournal || [])
      .filter(w => w.project === projectName && w.status !== 'Отклонено' && ((w.masterName || w.master_name || '') === personName) && packageMatches(w.workPackage || w.work_package, workPackage))
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

  const selectedPersonBalance = personMaterialBalance(newTransfer.toPerson, newTransfer.materialName, newTransfer.workPackage);
  const canSaveTransfer = !!newTransfer.materialName && selectedQty > 0 && !!newTransfer.toPerson && !hasStockOverrun;

  const matchingRequest = (() => {
    const matName = (newTransfer.materialName || '').toLowerCase().trim();
    if (!matName) return null;

    return supplyRequests.find(r => {
      if (r.project !== projectName) return false;
      if (r.status === 'Отменена' || r.status === 'Отклонена') return false;
      const requestName = (r.materialName || '').toLowerCase().trim();
      if (!requestName) return false;
      return requestName.includes(matName.split(' ')[0]) || matName.includes(requestName.split(' ')[0]);
    });
  })();

  const requesterOptions = (() => {
    const matName = (newTransfer.materialName || '').toLowerCase().trim();
    const requesters = new Map();

    supplyRequests
      .filter(r => r.project === projectName && (r.status === 'Утверждена' || r.status === 'Подтверждена прорабом' || r.status === 'Новая'))
      .forEach(r => {
        if (matName) {
          const requestName = (r.materialName || '').toLowerCase();
          if (!requestName.includes(matName.split(' ')[0]) && !matName.includes(requestName.split(' ')[0] || '')) return;
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
    if (!newTransfer.materialName || !newTransfer.quantity || !newTransfer.toPerson) return;
    if (!canSaveTransfer) {
      alert(hasStockOverrun
        ? 'Нельзя выдать больше остатка на складе.'
        : 'Укажите материал, получателя и количество больше нуля.');
      return;
    }

    const data = {...newTransfer, projectName, createdBy: user.name};
    const res = await fetch(API + '/material-transfers', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data),
    });
    const saved = await res.json();

    if (!res.ok || !saved.ok) {
      alert('Ошибка: ' + (saved.detail || saved.error || 'не удалось списать со склада'));
      return;
    }

    setMaterialTransfers(prev => [{...data, id: saved.id, signed: false}, ...prev]);
    const qty = Number(newTransfer.quantity);

    if (newTransfer.fromLocation === 'Основной склад') {
      setWarehouseMain(prev => prev.map(m => m.name === newTransfer.materialName ? {...m, quantity: Number(m.quantity || 0) - qty} : m));
    } else {
      setMaterials(prev => prev.map(m => (
        m.name === newTransfer.materialName &&
        m.project === newTransfer.fromLocation &&
        (m.workPackage || m.work_package || '') === (newTransfer.workPackage || '')
      ) ? {...m, quantity: Number(m.quantity || 0) - qty} : m));
    }

    setNewTransfer(emptyTransfer());
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
    if ((transfer.fromLocation || '') === 'Основной склад') {
      setWarehouseMain(prev => prev.map(m => m.name === transfer.materialName ? {...m, quantity: Number(m.quantity || 0) + qty} : m));
    } else {
      setMaterials(prev => prev.map(m => (
        m.name === transfer.materialName &&
        m.project === transfer.fromLocation &&
        (m.workPackage || m.work_package || '') === (transfer.workPackage || '')
      ) ? {...m, quantity: Number(m.quantity || 0) + qty} : m));
    }
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
          visibleProjects={visibleProjects}
          availableMaterials={availableMaterials}
          newTransfer={newTransfer}
          setNewTransfer={setNewTransfer}
          selectedQty={selectedQty}
          selectedStockQty={selectedStockQty}
          selectedPersonBalance={selectedPersonBalance}
          hasStockOverrun={hasStockOverrun}
          matchingRequest={matchingRequest}
          normalizeUnit={normalizeUnit}
          convertUnits={convertUnits}
          fmtQty={fmtQty}
          requesterOptions={requesterOptions}
          staff={staff}
          brigadeContracts={brigadeContracts}
          workPackageOptions={workPackageOptions}
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

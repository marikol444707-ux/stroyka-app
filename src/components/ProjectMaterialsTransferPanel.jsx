import React from 'react';
import { Check, Package, Trash2, X } from 'lucide-react';
import { API } from '../api';

const emptyTransfer = () => ({
  materialName: '',
  quantity: '',
  unit: 'шт',
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
  showPreview,
  buildM15Content,
}) {
  const availableMaterials = [
    ...warehouseMain.filter(m => m.location === newTransfer.fromLocation || (!m.location && newTransfer.fromLocation === 'Основной склад')),
    ...materials.filter(m => m.project === newTransfer.fromLocation),
  ];
  const transfers = materialTransfers.filter(t => t.projectName === projectName);
  const selectedStock = newTransfer.fromLocation === 'Основной склад'
    ? warehouseMain.find(m => m.name === newTransfer.materialName)
    : materials.find(m => m.name === newTransfer.materialName && m.project === newTransfer.fromLocation);

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
      setMaterials(prev => prev.map(m => (m.name === newTransfer.materialName && m.project === newTransfer.fromLocation) ? {...m, quantity: Number(m.quantity || 0) - qty} : m));
    }

    setNewTransfer(emptyTransfer());
    setShowTransferForm(false);
  };

  const signTransfer = async (transferId) => {
    await fetch(API + '/material-transfers/' + transferId + '/sign', {method: 'PUT'});
    setMaterialTransfers(prev => prev.map(mt => mt.id === transferId ? {...mt, signed: true} : mt));
  };

  const deleteTransfer = async (transferId) => {
    await fetch(API + '/material-transfers/' + transferId, {method: 'DELETE'});
    setMaterialTransfers(prev => prev.filter(mt => mt.id !== transferId));
  };

  return (
    <div>
      {showTransferForm && (
        <div style={{...card, padding: '20px', marginBottom: '16px'}}>
          <h3 style={{color: C.text, marginBottom: '15px', fontWeight: '700'}}>Передача материала бригаде/мастеру</h3>
          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px'}}>
            <select
              value={newTransfer.fromLocation}
              onChange={e => setNewTransfer({...newTransfer, fromLocation: e.target.value, materialName: '', quantity: ''})}
              style={{...inp, marginBottom: 0, gridColumn: 'span 2'}}
            >
              <option value="Основной склад">Основной склад</option>
              {visibleProjects.map(pr => <option key={pr.id} value={pr.name}>{pr.name}</option>)}
            </select>

            <div style={{gridColumn: 'span 2'}}>
              <p style={{fontSize: '12px', color: C.textSec, marginBottom: '6px'}}>Материалы на складе:</p>
              <div style={{maxHeight: '200px', overflowY: 'auto', border: '1.5px solid ' + C.border, borderRadius: '8px', padding: '8px'}}>
                {availableMaterials.map((m, i) => (
                  <div key={i} style={{display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 0', borderBottom: '1px solid ' + C.border}}>
                    <input
                      type="checkbox"
                      checked={newTransfer.materialName === m.name}
                      onChange={e => setNewTransfer({...newTransfer, materialName: e.target.checked ? m.name : '', unit: e.target.checked ? m.unit : newTransfer.unit, quantity: ''})}
                      style={{width: '16px', height: '16px', cursor: 'pointer'}}
                    />
                    <span style={{flex: 1, fontSize: '12px', color: C.text}}>{m.name}</span>
                    <span style={{fontSize: '11px', color: C.textSec}}>Остаток: {m.quantity} {m.unit}</span>
                  </div>
                ))}
                {availableMaterials.length === 0 && <p style={{color: C.textMuted, fontSize: '12px', textAlign: 'center', padding: '10px'}}>Нет материалов на этом складе</p>}
              </div>
            </div>

            {newTransfer.materialName && (
              <>
                <div style={{display: 'flex', gap: '6px', gridColumn: 'span 2', alignItems: 'center'}}>
                  <b style={{fontSize: '12px', color: C.text, flex: 1}}>Передаём: {newTransfer.materialName}</b>
                  <input
                    placeholder="Кол-во *"
                    type="number"
                    step="any"
                    inputMode="decimal"
                    value={newTransfer.quantity}
                    onChange={e => setNewTransfer({...newTransfer, quantity: e.target.value})}
                    style={{...inp, marginBottom: 0, width: '120px'}}
                  />
                  <span style={{fontSize: '12px', color: C.textSec}}>{newTransfer.unit}</span>
                  <span style={{fontSize: '11px', color: C.warning}}>
                    Остаток: {selectedStock?.quantity || 0} {newTransfer.unit}
                  </span>
                </div>

                {matchingRequest && normalizeUnit(matchingRequest.unit) !== normalizeUnit(newTransfer.unit) && (() => {
                  const conv = convertUnits(newTransfer.materialName, matchingRequest.quantity, matchingRequest.unit, newTransfer.unit);
                  if (conv) {
                    return (
                      <div style={{gridColumn: 'span 2', padding: '10px 12px', backgroundColor: C.infoLight, border: '1.5px solid ' + C.infoBorder, borderRadius: '8px', fontSize: '12px'}}>
                        📐 Заявка была на <b>{matchingRequest.quantity} {matchingRequest.unit}</b>, склад в {newTransfer.unit}. Это ≈ <b style={{color: C.accent}}>{conv.qty.toFixed(2)} {newTransfer.unit}</b>.
                        <p style={{margin: '4px 0 6px', color: C.textSec, fontSize: '11px'}}>{conv.note}</p>
                        <button onClick={() => setNewTransfer({...newTransfer, quantity: Number(conv.qty.toFixed(3))})} style={{...btnGr, padding: '4px 10px', fontSize: '11px'}}>
                          <Check size={11}/>Подставить {conv.qty.toFixed(2)} {newTransfer.unit}
                        </button>
                      </div>
                    );
                  }

                  return (
                    <div style={{gridColumn: 'span 2', padding: '10px 12px', backgroundColor: C.warningLight, border: '1.5px solid ' + C.warningBorder, borderRadius: '8px', fontSize: '12px', color: C.text}}>
                      ⚠️ Заявка в <b>{matchingRequest.quantity} {matchingRequest.unit}</b>, на складе в <b>{newTransfer.unit}</b>. Конверсия не задана — пересчитайте вручную.
                    </div>
                  );
                })()}
              </>
            )}

            <select
              value={newTransfer.toPerson}
              onChange={e => {
                const selected = staff.find(st => st.name === e.target.value);
                setNewTransfer({...newTransfer, toPerson: e.target.value, toPersonRole: selected ? selected.role : ''});
              }}
              style={{...inp, marginBottom: 0}}
            >
              <option value="">Кому передать *</option>
              {requesterOptions.requesters.length > 0 && (
                <optgroup label="📋 Заявляли этот материал">
                  {requesterOptions.requesters.map((r, i) => (
                    <option key={'req-' + i} value={r.name}>⭐ {r.name} ({r.role}) — просил {r.quantity} {r.unit}</option>
                  ))}
                </optgroup>
              )}
              <optgroup label={requesterOptions.requesters.length > 0 ? '👥 Остальные мастера и прорабы' : '👥 Мастера и прорабы'}>
                {staff
                  .filter(s => ['мастер', 'прораб', 'бригадир', 'субподрядчик'].includes((s.role || '').toLowerCase()) && !requesterOptions.requesterNames.has(s.name))
                  .map(s => <option key={s.id} value={s.name}>{s.name} ({s.role})</option>)}
              </optgroup>
              {brigadeContracts.filter(bc => bc.projectName === projectName).length > 0 && (
                <optgroup label="🔨 Бригады по объекту">
                  {brigadeContracts.filter(bc => bc.projectName === projectName).map(bc => <option key={bc.id} value={bc.brigadeName}>{bc.brigadeName} ({bc.contractorType})</option>)}
                </optgroup>
              )}
            </select>

            <input type="date" value={newTransfer.transferDate} onChange={e => setNewTransfer({...newTransfer, transferDate: e.target.value})} style={{...inp, marginBottom: 0}}/>
            <input placeholder="Примечание" value={newTransfer.notes} onChange={e => setNewTransfer({...newTransfer, notes: e.target.value})} style={{...inp, marginBottom: 0}}/>
          </div>
          <div style={{display: 'flex', gap: '8px', marginTop: '12px'}}>
            <button onClick={saveTransfer} style={btnO}><Check size={14}/>Передать</button>
            <button onClick={() => setShowTransferForm(false)} style={btnG}><X size={14}/>Отмена</button>
          </div>
        </div>
      )}

      <table style={tbl}>
        <thead>
          <tr>
            <th style={tblH}>Материал</th>
            <th style={tblH}>Кол-во</th>
            <th style={tblH}>Кому</th>
            <th style={tblH}>Дата</th>
            <th style={tblH}>Статус</th>
            <th style={tblH}></th>
          </tr>
        </thead>
        <tbody>
          {transfers.map(t => (
            <tr key={t.id}>
              <td style={tblC}>{t.materialName}</td>
              <td style={tblC}>{t.quantity} {t.unit}</td>
              <td style={tblC}>{t.toPerson}<br/><span style={{fontSize: '11px', color: C.textSec}}>{t.toPersonRole}</span></td>
              <td style={tblC}>{t.transferDate}</td>
              <td style={tblC}>{t.signed ? <span style={{color: C.success, fontSize: '12px'}}>✅ Подписано</span> : <span style={{color: C.warning, fontSize: '12px'}}>⏳ Ожидает подписи</span>}</td>
              <td style={tblC}>
                {!t.signed && (
                  <button onClick={() => signTransfer(t.id)} style={{...btnO, padding: '4px 10px', fontSize: '11px'}}>
                    <Check size={11}/>Подписать
                  </button>
                )}
                <button onClick={() => showPreview(buildM15Content(t), 'М-15 № ' + t.id)} style={{...btnB, padding: '4px 8px', marginLeft: '4px'}} title="Печать М-15 (накладная на отпуск)">🖨️</button>
                <button onClick={() => deleteTransfer(t.id)} style={{...btnR, padding: '4px 8px', marginLeft: '4px'}}>
                  <Trash2 size={11}/>
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {transfers.length === 0 && (
        <div style={{...card, padding: '40px', textAlign: 'center', color: C.textMuted}}>
          <Package size={48} style={{marginBottom: '15px', opacity: 0.3}}/>
          <p>Передач материалов нет</p>
        </div>
      )}
    </div>
  );
}

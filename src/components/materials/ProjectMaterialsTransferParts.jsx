import React from 'react';
import { Check, Package, Trash2, X } from 'lucide-react';

export function TransferMetricCards({
  C,
  metrics,
}) {
  return (
    <div style={{display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: '8px', gridColumn: 'span 2'}}>
      {metrics.map(([label, value, color]) => (
        <div key={label} style={{padding: '10px 12px', border: '1.5px solid ' + C.border, borderRadius: '8px', backgroundColor: C.bg}}>
          <p style={{margin: '0 0 4px', fontSize: '10px', color: C.textSec, textTransform: 'uppercase', letterSpacing: 0}}>{label}</p>
          <b style={{fontSize: '13px', color, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis'}}>{value}</b>
        </div>
      ))}
    </div>
  );
}

export function MaterialPicker({
  C,
  newTransfer,
  setNewTransfer,
  availableMaterials,
}) {
  return (
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
  );
}

export function TransferQuantityBlock({
  C,
  inp,
  btnGr,
  newTransfer,
  setNewTransfer,
  selectedQty,
  selectedStockQty,
  selectedPersonBalance,
  hasStockOverrun,
  matchingRequest,
  normalizeUnit,
  convertUnits,
  fmtQty,
}) {
  if (!newTransfer.materialName) return null;

  return (
    <>
      <TransferMetricCards
        C={C}
        metrics={[
          ['На складе', fmtQty(selectedStockQty, newTransfer.unit), C.text],
          ['Передаём', selectedQty > 0 ? fmtQty(selectedQty, newTransfer.unit) : 'не указано', selectedQty > 0 ? C.warning : C.textMuted],
          ['Останется', fmtQty(Math.max(0, selectedStockQty - selectedQty), newTransfer.unit), hasStockOverrun ? C.danger : C.success],
          ['У получателя', fmtQty(selectedPersonBalance.balance, newTransfer.unit), C.accent],
        ]}
      />

      <div style={{display: 'flex', gap: '6px', gridColumn: 'span 2', alignItems: 'center'}}>
        <b style={{fontSize: '12px', color: C.text, flex: 1}}>Передаём: {newTransfer.materialName}</b>
        <input
          placeholder="Кол-во *"
          type="number"
          step="any"
          inputMode="decimal"
          value={newTransfer.quantity}
          onChange={e => setNewTransfer({...newTransfer, quantity: e.target.value})}
          max={selectedStockQty}
          style={{...inp, marginBottom: 0, width: '120px'}}
        />
        <span style={{fontSize: '12px', color: C.textSec}}>{newTransfer.unit}</span>
        <span style={{fontSize: '11px', color: hasStockOverrun ? C.danger : C.warning}}>
          Остаток: {fmtQty(selectedStockQty, newTransfer.unit)}
        </span>
      </div>

      {newTransfer.toPerson && (
        <div style={{gridColumn: 'span 2', padding: '9px 12px', backgroundColor: C.bg, border: '1.5px solid ' + C.border, borderRadius: '8px', color: C.textSec, fontSize: '12px'}}>
          У {newTransfer.toPerson}: подписано {fmtQty(selectedPersonBalance.issued, newTransfer.unit)}, ожидает подписи {fmtQty(selectedPersonBalance.pending, newTransfer.unit)}, списано {fmtQty(selectedPersonBalance.used, newTransfer.unit)}, возвращено {fmtQty(selectedPersonBalance.returned, newTransfer.unit)}.
        </div>
      )}

      {hasStockOverrun && (
        <div style={{gridColumn: 'span 2', padding: '10px 12px', backgroundColor: C.dangerLight, border: '1.5px solid ' + C.dangerBorder, borderRadius: '8px', color: C.danger, fontSize: '12px', fontWeight: 700}}>
          Нельзя выдать больше остатка: на складе {fmtQty(selectedStockQty, newTransfer.unit)}, указано {fmtQty(selectedQty, newTransfer.unit)}.
        </div>
      )}

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
  );
}

export function TransferRecipientSelect({
  inp,
  newTransfer,
  setNewTransfer,
  requesterOptions,
  staff,
  brigadeContracts,
  projectName,
}) {
  return (
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
  );
}

export function MaterialTransferForm({
  projectName,
  C,
  card,
  inp,
  btnO,
  btnG,
  btnGr,
  visibleProjects,
  availableMaterials,
  newTransfer,
  setNewTransfer,
  selectedQty,
  selectedStockQty,
  selectedPersonBalance,
  hasStockOverrun,
  matchingRequest,
  normalizeUnit,
  convertUnits,
  fmtQty,
  requesterOptions,
  staff,
  brigadeContracts,
  canSaveTransfer,
  saveTransfer,
  setShowTransferForm,
}) {
  return (
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

        <MaterialPicker
          C={C}
          newTransfer={newTransfer}
          setNewTransfer={setNewTransfer}
          availableMaterials={availableMaterials}
        />

        <TransferQuantityBlock
          C={C}
          inp={inp}
          btnGr={btnGr}
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
        />

        <TransferRecipientSelect
          inp={inp}
          newTransfer={newTransfer}
          setNewTransfer={setNewTransfer}
          requesterOptions={requesterOptions}
          staff={staff}
          brigadeContracts={brigadeContracts}
          projectName={projectName}
        />

        <input type="date" value={newTransfer.transferDate} onChange={e => setNewTransfer({...newTransfer, transferDate: e.target.value})} style={{...inp, marginBottom: 0}}/>
        <input placeholder="Примечание" value={newTransfer.notes} onChange={e => setNewTransfer({...newTransfer, notes: e.target.value})} style={{...inp, marginBottom: 0}}/>
      </div>
      <div style={{display: 'flex', gap: '8px', marginTop: '12px'}}>
        <button onClick={saveTransfer} disabled={!canSaveTransfer} style={{...btnO, opacity: canSaveTransfer ? 1 : 0.55, cursor: canSaveTransfer ? 'pointer' : 'not-allowed'}}><Check size={14}/>Передать</button>
        <button onClick={() => setShowTransferForm(false)} style={btnG}><X size={14}/>Отмена</button>
      </div>
    </div>
  );
}

export function TransfersTable({
  transfers,
  C,
  tbl,
  tblH,
  tblC,
  btnO,
  btnB,
  btnR,
  fmtQty,
  personMaterialBalance,
  signTransfer,
  deleteTransfer,
  showPreview,
  buildM15Content,
}) {
  return (
    <table style={tbl}>
      <thead>
        <tr>
          <th style={tblH}>Материал</th>
          <th style={tblH}>Кол-во</th>
          <th style={tblH}>Источник</th>
          <th style={tblH}>Кому</th>
          <th style={tblH}>Баланс</th>
          <th style={tblH}>Дата</th>
          <th style={tblH}>Статус</th>
          <th style={tblH}></th>
        </tr>
      </thead>
      <tbody>
        {transfers.map(t => {
          const balance = personMaterialBalance(t.toPerson, t.materialName);
          return (
            <tr key={t.id}>
              <td style={tblC}>{t.materialName}</td>
              <td style={tblC}>{fmtQty(t.quantity, t.unit)}</td>
              <td style={tblC}>{t.fromLocation || 'Основной склад'}</td>
              <td style={tblC}>{t.toPerson}<br/><span style={{fontSize: '11px', color: C.textSec}}>{t.toPersonRole}</span></td>
              <td style={tblC}>
                <b style={{color: C.accent, fontSize: '12px'}}>{fmtQty(balance.balance, t.unit)}</b>
                <br/>
                <span style={{fontSize: '10px', color: C.textSec}}>подписано {fmtQty(balance.issued, t.unit)} · списано {fmtQty(balance.used, t.unit)}</span>
              </td>
              <td style={tblC}>{t.transferDate}</td>
              <td style={tblC}>{t.signed ? <span style={{color: C.success, fontSize: '12px'}}>✅ Подписано</span> : <span style={{color: C.warning, fontSize: '12px'}}>⏳ Ожидает подписи</span>}</td>
              <td style={tblC}>
                {!t.signed && (
                  <button onClick={() => signTransfer(t.id)} style={{...btnO, padding: '4px 10px', fontSize: '11px'}}>
                    <Check size={11}/>Подписать
                  </button>
                )}
                <button onClick={() => showPreview(buildM15Content(t), 'М-15 № ' + t.id)} style={{...btnB, padding: '4px 8px', marginLeft: '4px'}} title="Печать М-15 (накладная на отпуск)">🖨️</button>
                {!t.signed ? (
                  <button onClick={() => deleteTransfer(t)} style={{...btnR, padding: '4px 8px', marginLeft: '4px'}} title="Удалить неподписанную передачу и вернуть материал на склад">
                    <Trash2 size={11}/>
                  </button>
                ) : (
                  <span style={{marginLeft: '6px', color: C.textMuted, fontSize: '10px'}} title="Подписанную передачу нельзя удалить, нужен возврат">закрыто</span>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function EmptyTransfersState({C, card}) {
  return (
    <div style={{...card, padding: '40px', textAlign: 'center', color: C.textMuted}}>
      <Package size={48} style={{marginBottom: '15px', opacity: 0.3}}/>
      <p>Передач материалов нет</p>
    </div>
  );
}

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

const transferItemKey = item => [
  item.materialName || item.name || '',
  item.workPackage || item.work_package || '',
  item.unit || '',
].join('|||');

export function MaterialPicker({
  C,
  newTransfer,
  setNewTransfer,
  availableMaterials,
  selectedTransferItems = [],
  updateTransferItems,
}) {
  const selectedKeys = new Set((selectedTransferItems || []).map(transferItemKey));
  return (
    <div style={{gridColumn: 'span 2'}}>
      <p style={{fontSize: '12px', color: C.textSec, marginBottom: '6px'}}>Материалы на складе:</p>
      <div style={{maxHeight: '200px', overflowY: 'auto', border: '1.5px solid ' + C.border, borderRadius: '8px', padding: '8px'}}>
        {availableMaterials.map((m, i) => (
          <div key={i} style={{display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 0', borderBottom: '1px solid ' + C.border}}>
            <input
              type="checkbox"
              checked={selectedKeys.has(transferItemKey({materialName: m.name, workPackage: m.workPackage || m.work_package || '', unit: m.unit || 'шт'}))}
              onChange={e => {
                const item = {
                  materialName: m.name,
                  unit: m.unit || 'шт',
                  workPackage: m.workPackage || m.work_package || '',
                  quantity: '',
                };
                if (updateTransferItems) {
                  updateTransferItems(e.target.checked
                    ? [...selectedTransferItems, item]
                    : selectedTransferItems.filter(row => transferItemKey(row) !== transferItemKey(item)));
                  return;
                }
                setNewTransfer({
                  ...newTransfer,
                  materialName: e.target.checked ? m.name : '',
                  unit: e.target.checked ? m.unit : newTransfer.unit,
                  workPackage: e.target.checked ? (m.workPackage || m.work_package || '') : '',
                  quantity: ''
                });
              }}
              style={{width: '16px', height: '16px', cursor: 'pointer'}}
            />
            <span style={{flex: 1, fontSize: '12px', color: C.text}}>
              {m.name}
              {(m.workPackage || m.work_package) && <span style={{color: C.textSec}}> · 📁 {m.workPackage || m.work_package}</span>}
            </span>
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
  selectedTransferItems = [],
  updateTransferItems,
  transferItemStockQty,
  transferItemOverStock,
  personMaterialBalance,
  selectedStockQty,
  selectedPersonBalance,
  hasStockOverrun,
  matchingRequest,
  matchingRequestForItem,
  normalizeUnit,
  convertUnits,
  fmtQty,
}) {
  const items = (selectedTransferItems || []).length
    ? selectedTransferItems
    : (newTransfer.materialName ? [{
      materialName: newTransfer.materialName,
      quantity: newTransfer.quantity,
      unit: newTransfer.unit || 'шт',
      workPackage: newTransfer.workPackage || '',
    }] : []);
  if (items.length === 0) return null;
  const updateItemQuantity = (item, quantity) => {
    if (updateTransferItems) {
      updateTransferItems(items.map(row => transferItemKey(row) === transferItemKey(item) ? {...row, quantity} : row));
      return;
    }
    setNewTransfer({...newTransfer, quantity});
  };
  const removeItem = (item) => {
    if (updateTransferItems) {
      updateTransferItems(items.filter(row => transferItemKey(row) !== transferItemKey(item)));
    }
  };

  return (
    <>
      <TransferMetricCards
        C={C}
        metrics={[
          ['Выбрано', String(items.length), C.text],
          ['С количеством', String(items.filter(item => Number(item.quantity || 0) > 0).length), C.warning],
          ['Ошибки остатка', String(items.filter(item => transferItemOverStock ? transferItemOverStock(item) : hasStockOverrun).length), hasStockOverrun ? C.danger : C.success],
          ['Получатель', newTransfer.toPerson || 'не выбран', newTransfer.toPerson ? C.accent : C.textMuted],
        ]}
      />

      <div style={{gridColumn: 'span 2', display: 'grid', gap: '8px'}}>
        {items.map(item => {
          const stockQty = transferItemStockQty ? transferItemStockQty(item) : selectedStockQty;
          const qty = Number(item.quantity || 0);
          const overrun = transferItemOverStock ? transferItemOverStock(item) : hasStockOverrun;
          const balance = personMaterialBalance ? personMaterialBalance(newTransfer.toPerson, item.materialName, item.workPackage || '') : selectedPersonBalance;
          const request = matchingRequestForItem ? matchingRequestForItem(item) : matchingRequest;
          return (
            <div key={transferItemKey(item)} style={{padding: '10px', border: '1.5px solid ' + (overrun ? C.dangerBorder : C.border), borderRadius: '8px', backgroundColor: overrun ? C.dangerLight : C.bg}}>
              <div style={{display: 'grid', gridTemplateColumns: 'minmax(180px,1fr) 120px auto auto', gap: '8px', alignItems: 'center'}}>
                <div style={{minWidth: 0}}>
                  <b style={{display: 'block', fontSize: '12px', color: C.text, overflowWrap: 'anywhere'}}>{item.materialName}</b>
                  {item.workPackage && <span style={{display: 'block', fontSize: '10px', color: C.textSec, marginTop: '2px'}}>Пакет: {item.workPackage}</span>}
                </div>
                <input
                  placeholder="Кол-во *"
                  type="number"
                  step="any"
                  inputMode="decimal"
                  value={item.quantity}
                  onChange={e => updateItemQuantity(item, e.target.value)}
                  max={stockQty}
                  style={{...inp, marginBottom: 0, width: '120px'}}
                />
                <span style={{fontSize: '12px', color: C.textSec}}>{item.unit}</span>
                {updateTransferItems && (
                  <button type="button" onClick={() => removeItem(item)} style={{padding: '6px 9px', border: '1px solid ' + C.border, borderRadius: '7px', backgroundColor: C.bgWhite, color: C.textSec, cursor: 'pointer'}}>
                    <X size={12}/>
                  </button>
                )}
              </div>
              <div style={{display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '6px', fontSize: '11px', color: C.textSec}}>
                <span style={{color: overrun ? C.danger : C.textSec}}>Остаток: {fmtQty(stockQty, item.unit)}</span>
                <span>Останется: {fmtQty(Math.max(0, stockQty - qty), item.unit)}</span>
                {newTransfer.toPerson && <span>У получателя: {fmtQty(balance.balance, item.unit)}</span>}
              </div>
              {request && normalizeUnit(request.unit) !== normalizeUnit(item.unit) && (() => {
                const conv = convertUnits(item.materialName, request.quantity, request.unit, item.unit);
                if (conv) {
                  return (
                    <div style={{marginTop: '8px', padding: '8px 10px', backgroundColor: C.infoLight, border: '1.5px solid ' + C.infoBorder, borderRadius: '8px', fontSize: '12px'}}>
                      📐 Заявка была на <b>{request.quantity} {request.unit}</b>, склад в {item.unit}. Это ≈ <b style={{color: C.accent}}>{conv.qty.toFixed(2)} {item.unit}</b>.
                      <button onClick={() => updateItemQuantity(item, Number(conv.qty.toFixed(3)))} style={{...btnGr, padding: '4px 10px', fontSize: '11px', marginLeft: '8px'}}>
                        <Check size={11}/>Подставить
                      </button>
                    </div>
                  );
                }
                return (
                  <div style={{marginTop: '8px', padding: '8px 10px', backgroundColor: C.warningLight, border: '1.5px solid ' + C.warningBorder, borderRadius: '8px', fontSize: '12px', color: C.text}}>
                    ⚠️ Заявка в <b>{request.quantity} {request.unit}</b>, на складе в <b>{item.unit}</b>. Конверсия не задана — пересчитайте вручную.
                  </div>
                );
              })()}
            </div>
          );
        })}
      </div>

      {hasStockOverrun && (
        <div style={{gridColumn: 'span 2', padding: '10px 12px', backgroundColor: C.dangerLight, border: '1.5px solid ' + C.dangerBorder, borderRadius: '8px', color: C.danger, fontSize: '12px', fontWeight: 700}}>
          Нельзя выдать больше остатка. Проверьте строки, выделенные красным.
        </div>
      )}
    </>
  );
}

export function TransferRecipientSelect({
  inp,
  newTransfer,
  setNewTransfer,
  requesterOptions,
  staff,
}) {
  return (
    <select
      value={newTransfer.toUserId ? 'user:' + newTransfer.toUserId : newTransfer.toPerson}
      onChange={e => {
        const rawValue = e.target.value;
        const selected = rawValue.startsWith('user:') ? staff.find(st => String(st.id) === rawValue.slice(5)) : null;
        const requesterUser = !selected ? staff.find(st => st.name === rawValue) : null;
        const person = selected || requesterUser;
        setNewTransfer({
          ...newTransfer,
          toPerson: person ? person.name : rawValue,
          toPersonRole: person ? person.role : '',
          toUserId: person ? person.id : '',
        });
      }}
      style={{...inp, marginBottom: 0}}
    >
      <option value="">Кому передать *</option>
      {requesterOptions.requesters.length > 0 && (
        <optgroup label="📋 Заявляли этот материал">
          {requesterOptions.requesters.map((r, i) => (
            <option key={'req-' + i} value={staff.find(st => st.name === r.name) ? 'user:' + staff.find(st => st.name === r.name).id : r.name}>⭐ {r.name} ({r.role}) — просил {r.quantity} {r.unit}</option>
          ))}
        </optgroup>
      )}
        <optgroup label={requesterOptions.requesters.length > 0 ? '👥 Остальные исполнители' : '👥 Исполнители'}>
        {staff
          .filter(s => ['мастер', 'бригадир', 'субподрядчик'].includes((s.role || '').toLowerCase()) && !requesterOptions.requesterNames.has(s.name))
          .map(s => <option key={s.id} value={'user:' + s.id}>{s.name} ({s.role})</option>)}
      </optgroup>
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
  availableMaterials,
  newTransfer,
  setNewTransfer,
  selectedTransferItems = [],
  updateTransferItems,
  selectedStockQty,
  selectedPersonBalance,
  hasStockOverrun,
  matchingRequest,
  matchingRequestForItem,
  personMaterialBalance,
  transferItemStockQty,
  transferItemOverStock,
  normalizeUnit,
  convertUnits,
  fmtQty,
  requesterOptions,
  staff,
  workPackageOptions,
  needsWorkPackage,
  missingWorkPackage,
  canSaveTransfer,
  saveTransfer,
  setShowTransferForm,
}) {
  const [manualPackageEdit, setManualPackageEdit] = React.useState(false);
  const selectedPackages = [...new Set((selectedTransferItems || []).map(item => item.workPackage || '').filter(Boolean))];
  const missingPackageCount = (selectedTransferItems || []).filter(item => !(item.workPackage || '').trim()).length;
  const packageSelectValue = selectedPackages.length === 1 ? selectedPackages[0] : (newTransfer.workPackage || '');
  const showPackageControl = selectedTransferItems.length > 0 && (manualPackageEdit || missingWorkPackage);
  const packageHint = (() => {
    if (missingWorkPackage) {
      return `У ${missingPackageCount} строк пакет не определён. Выберите пакет, чтобы передача и дальнейшее списание прошли в одном разделе работ.`;
    }
    if (missingPackageCount > 0) {
      return `У ${missingPackageCount} строк пакет не указан. Если выдаёте исполнителю, система попросит выбрать пакет перед сохранением.`;
    }
    if (selectedPackages.length > 1) {
      return `У выбранных строк разные пакеты: ${selectedPackages.slice(0, 3).join(', ')}${selectedPackages.length > 3 ? '...' : ''}. Каждая строка уйдёт в своём пакете.`;
    }
    if (selectedPackages.length === 1) {
      return `Пакет берётся из выбранной строки склада: ${selectedPackages[0]}.`;
    }
    return 'Пакет будет взят из строки склада после выбора материала.';
  })();
  const applyPackageToSelected = (workPackage) => {
    if (updateTransferItems && selectedTransferItems.length > 0) {
      updateTransferItems(selectedTransferItems.map(item => ({...item, workPackage})));
      return;
    }
    setNewTransfer({...newTransfer, workPackage});
  };

  return (
    <div style={{...card, padding: '20px', marginBottom: '16px'}}>
      <h3 style={{color: C.text, marginBottom: '15px', fontWeight: '700'}}>Передача материала исполнителю</h3>
      <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px'}}>
        <select
          value={projectName}
          onChange={() => {}}
          disabled
          style={{...inp, marginBottom: 0, gridColumn: 'span 2'}}
        >
          <option value={projectName}>Склад объекта: {projectName}</option>
        </select>

        <MaterialPicker
          C={C}
          newTransfer={newTransfer}
          setNewTransfer={setNewTransfer}
          availableMaterials={availableMaterials}
          selectedTransferItems={selectedTransferItems}
          updateTransferItems={updateTransferItems}
        />

        <TransferQuantityBlock
          C={C}
          inp={inp}
          btnGr={btnGr}
          newTransfer={newTransfer}
          setNewTransfer={setNewTransfer}
          selectedTransferItems={selectedTransferItems}
          updateTransferItems={updateTransferItems}
          transferItemStockQty={transferItemStockQty}
          transferItemOverStock={transferItemOverStock}
          personMaterialBalance={personMaterialBalance}
          selectedStockQty={selectedStockQty}
          selectedPersonBalance={selectedPersonBalance}
          hasStockOverrun={hasStockOverrun}
          matchingRequest={matchingRequest}
          matchingRequestForItem={matchingRequestForItem}
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
        />

        {selectedTransferItems.length > 0 && (
          <div style={{gridColumn: 'span 2', padding: '10px 12px', backgroundColor: missingWorkPackage ? C.warningLight : C.infoLight, border: '1.5px solid ' + (missingWorkPackage ? C.warningBorder : C.infoBorder), borderRadius: '8px', fontSize: '12px', color: C.text}}>
            <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap'}}>
              <b style={{color: missingWorkPackage ? C.warning : C.info}}>Пакет работ</b>
              {!showPackageControl && (
                <button type="button" onClick={() => setManualPackageEdit(true)} style={{...btnG, padding: '4px 10px', fontSize: '11px'}}>
                  Изменить вручную
                </button>
              )}
            </div>
            <p style={{margin: '5px 0 0', color: C.textSec}}>{packageHint}</p>
          </div>
        )}
        {showPackageControl && (
          <select
            value={packageSelectValue}
            onChange={e => {
              applyPackageToSelected(e.target.value);
              if (e.target.value) setManualPackageEdit(false);
            }}
            style={{...inp, marginBottom: 0, borderColor: missingWorkPackage ? C.warning : inp.borderColor, gridColumn: 'span 2'}}
          >
            <option value="">{selectedTransferItems.length > 1 && selectedPackages.length > 1 ? 'Разные пакеты в выбранных строках' : (needsWorkPackage ? 'Пакет работ *' : 'Пакет работ: общий')}</option>
            {(workPackageOptions || []).map(pkg => <option key={pkg} value={pkg}>{pkg}</option>)}
          </select>
        )}
        {manualPackageEdit && !missingWorkPackage && (
          <button type="button" onClick={() => setManualPackageEdit(false)} style={{...btnG, marginBottom: 0, gridColumn: 'span 2', justifyContent: 'center'}}>
            Оставить пакеты из строк склада
          </button>
        )}
        <input type="date" value={newTransfer.transferDate} onChange={e => setNewTransfer({...newTransfer, transferDate: e.target.value})} style={{...inp, marginBottom: 0}}/>
        <input placeholder="Примечание" value={newTransfer.notes} onChange={e => setNewTransfer({...newTransfer, notes: e.target.value})} style={{...inp, marginBottom: 0}}/>
      </div>
      {missingWorkPackage && (
        <div style={{marginTop: '10px', padding: '10px 12px', backgroundColor: C.warningLight, border: '1.5px solid ' + C.warningBorder, borderRadius: '8px', color: C.warning, fontSize: '12px', fontWeight: 700}}>
          Для выдачи материала мастеру, бригадиру или субподрядчику выберите пакет работ. Потом списание в ЖПР пройдет только в этом же пакете.
        </div>
      )}
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
          const balance = personMaterialBalance(t.toPerson, t.materialName, t.workPackage || '');
          return (
            <tr key={t.id}>
              <td style={tblC}>
                {t.materialName}
                {t.workPackage && <><br/><span style={{fontSize: '10px', color: C.textSec}}>Пакет: {t.workPackage}</span></>}
              </td>
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

import React, { useState } from 'react';
import { Trash2 } from 'lucide-react';
import { API } from '../api';

const defaultNormalizeMeasure = (qty, unit) => ({qty, unit, factor: 1});
const defaultToNum = (value) => Number(value || 0) || 0;
const defaultFmtMeasure = (qty, unit) => String(qty || 0) + (unit ? ' ' + unit : '');

export default function ProjectBrigadeCalculationTable({
  brigadeContractItems = [],
  setBrigadeContractItems,
  showFinance = false,
  showLeadership = false,
  normalizeMeasure = defaultNormalizeMeasure,
  toNum = defaultToNum,
  fmtMeasure = defaultFmtMeasure,
  C,
  tbl,
  tblH,
  tblC,
  inp,
  btnR,
}) {
  const [deleteError, setDeleteError] = useState('');
  const [deletingId, setDeletingId] = useState(null);
  const updateQuantity = async (item, index, rawValue) => {
    const factor = normalizeMeasure(1, item.unit).factor;
    const quantity = toNum(rawValue) / factor;
    const updated = {...item, quantity};

    setBrigadeContractItems(prev => prev.map((it, i) => i === index ? updated : it));
    await fetch(API + '/brigade-contract-items/' + item.id, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({...updated, quantity}),
    });
  };

  // Ручная цена бригаде/мастеру по конкретной строке — сохраняется поверх коэффициента
  const updatePriceBrigade = async (item, index, rawValue) => {
    const priceBrigade = toNum(rawValue);
    const updated = {...item, priceBrigade};
    setBrigadeContractItems(prev => prev.map((it, i) => i === index ? updated : it));
    await fetch(API + '/brigade-contract-items/' + item.id, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(updated),
    });
  };

  const deleteItem = async (item) => {
    setDeleteError('');
    setDeletingId(item.id);
    try {
      const response = await fetch(API + '/brigade-contract-items/' + item.id, {method: 'DELETE'});
      const data = await response.json().catch(() => ({}));
      if (!response.ok || data.ok === false) {
        setDeleteError(typeof data.detail === 'string' ? data.detail : 'Не удалось удалить позицию. Повторите попытку.');
        return;
      }
      setBrigadeContractItems(prev => prev.filter(row => row.id !== item.id));
    } catch (_) {
      setDeleteError('Не удалось удалить позицию. Проверьте соединение.');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <><table style={tbl}>
      <thead>
        <tr>
          <th style={tblH}>Наименование</th>
          <th style={tblH}>Ед.</th>
          <th style={tblH}>План</th>
          <th style={tblH} title="Отмечает мастер в смете — здесь только просмотр">Выполнено (из сметы)</th>
          <th style={tblH}>Осталось</th>
          <th style={tblH}>%</th>
          <th style={{...tblH, display: showFinance ? '' : 'none'}}>Цена смета</th>
          <th style={{...tblH, display: showLeadership ? '' : 'none'}}>Цена бригаде</th>
          <th style={{...tblH, display: showLeadership ? '' : 'none'}}>К оплате</th>
          <th style={{...tblH, display: showFinance ? '' : 'none'}}>Экономия</th>
          <th style={{...tblH, display: showLeadership ? '' : 'none'}}></th>
        </tr>
      </thead>
      <tbody>
        {brigadeContractItems.map((item, index) => {
          const pct = item.quantity > 0 ? Math.round(item.doneQuantity / item.quantity * 100) : 0;
          const toPay = Math.round(item.doneQuantity * item.priceBrigade);
          const economy = Math.round(item.doneQuantity * (item.priceSmeta - item.priceBrigade));
          const remain = Math.max(0, Number(item.quantity || 0) - Number(item.doneQuantity || 0));
          const unit = normalizeMeasure(1, item.unit).unit || item.unit;

          return (
            <tr key={item.id || index}>
              <td style={tblC}>{item.name}</td>
              <td style={tblC}>{unit}</td>
              <td style={tblC}>
                {showLeadership ? (
                  <input
                    type="number"
                    step="any"
                    inputMode="decimal"
                    value={item.quantity ? String(toNum(item.quantity) * normalizeMeasure(1, item.unit).factor) : ''}
                    onChange={e => updateQuantity(item, index, e.target.value)}
                    style={{...inp, marginBottom: 0, width: '70px', fontSize: '12px', padding: '4px 6px'}}
                  />
                ) : fmtMeasure(Number(item.quantity || 0), item.unit)}
              </td>
              <td
                style={{...tblC, fontWeight: '600', color: C.text}}
                title="«Выполнено» отмечает мастер в смете (колонка «Сделано»). Здесь только просмотр — расчёт берётся из сметы."
              >
                {Number(item.doneQuantity || 0) > 0 ? fmtMeasure(Number(item.doneQuantity || 0), item.unit) : '—'}
              </td>
              <td style={{...tblC, color: remain > 0 ? C.warning : C.success, fontWeight: '600'}}>
                {Number(item.quantity) > 0 ? fmtMeasure(remain, item.unit) : '—'}
              </td>
              <td style={tblC}>
                <span style={{padding: '2px 6px', borderRadius: '4px', fontSize: '11px', backgroundColor: pct >= 100 ? C.successLight : pct > 0 ? C.warningLight : C.bg, color: pct >= 100 ? C.success : pct > 0 ? C.warning : C.textMuted}}>
                  {pct + '%'}
                </span>
              </td>
              <td style={{...tblC, display: showFinance ? '' : 'none'}}>{Number(item.priceSmeta || 0).toLocaleString('ru-RU') + ' ₽'}</td>
              <td style={{...tblC, display: showLeadership ? '' : 'none'}}>
                <input
                  type="number"
                  step="any"
                  inputMode="decimal"
                  value={item.priceBrigade ? String(toNum(item.priceBrigade)) : ''}
                  onChange={e => updatePriceBrigade(item, index, e.target.value)}
                  title="Цену можно задать вручную по строке — сохранится поверх коэффициента"
                  style={{...inp, marginBottom: 0, width: '80px', fontSize: '12px', padding: '4px 6px'}}
                />
              </td>
              <td style={{...tblC, fontWeight: '600', color: C.accent, display: showLeadership ? '' : 'none'}}>{toPay.toLocaleString('ru-RU') + ' ₽'}</td>
              <td style={{...tblC, fontWeight: '600', color: C.success, display: showFinance ? '' : 'none'}}>{economy.toLocaleString('ru-RU') + ' ₽'}</td>
              <td style={{...tblC, display: showLeadership ? '' : 'none'}}>
                <button type="button" onClick={() => deleteItem(item)} disabled={deletingId === item.id} aria-label={'Удалить ' + item.name} style={{...btnR, padding: '3px 7px'}}>
                  <Trash2 size={11}/>
                </button>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>{deleteError && <p role="alert" style={{color: C.danger, margin: '8px 0'}}>{deleteError}</p>}</>
  );
}

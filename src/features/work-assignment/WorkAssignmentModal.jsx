import React, { useMemo, useState } from 'react';
import { CheckSquare, RotateCcw, UserCheck, X } from 'lucide-react';
import { formatMoney, formatQty, toNumber, workRowsForEstimate } from './workAssignmentUtils';
import { findUserForStaff, normalizePersonKey } from '../../utils/performerUtils';

function isPerformer(item = {}) {
    const text = [item.role, item.systemRole, item.category, item.employmentType, item.position, item.name].map(value => String(value || '').toLowerCase()).join(' ');
    return ['мастер', 'субподрядчик', 'бригадир', 'электрик', 'слаботочник', 'отделочник', 'гпх', 'самозанятый', 'ип', 'ооо'].some(token => text.includes(token));
}

export function performerRows(staff = [], users = []) {
  const rows = [];
  const seenKeys = new Set();
  const seenUserIds = new Set();
  const addRow = (item, key, userId = '') => {
    if (!item || !key || seenKeys.has(key)) return;
    seenKeys.add(key);
    if (userId) seenUserIds.add(String(userId));
    rows.push(item);
  };
  (staff || []).filter(isPerformer).forEach(item => {
    const accessUser = findUserForStaff(item, users);
    const contractorId = accessUser?.id || item.id;
    addRow({
      ...item,
      id: contractorId,
      contractorId,
      role: item.role || accessUser?.role || '',
      employmentType: item.employmentType || accessUser?.role || 'мастер',
      email: accessUser?.email || item.email || item.emailWork || item.emailPersonal || '',
    }, accessUser?.id ? 'user:' + accessUser.id : 'staff:' + (item.id || normalizePersonKey(item.name)), accessUser?.id);
  });
  (users || []).filter(isPerformer).forEach(item => {
    if (!item.id || seenUserIds.has(String(item.id))) return;
    addRow({
      ...item,
      contractorId: item.id,
      employmentType: item.role || 'мастер',
    }, 'user:' + item.id, item.id);
  });
  return rows.sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'ru'));
}

export default function WorkAssignmentModal({
  show,
  onClose,
  selectedEstimate,
  staff = [],
  users = [],
  API,
  loadAll,
  C,
  card,
  inp,
  btnO,
  btnG,
  btnB,
  isMobile,
}) {
  const [selectedIds, setSelectedIds] = useState({});
  const [contractorId, setContractorId] = useState('');
  const [manualName, setManualName] = useState('');
  const [coefficient, setCoefficient] = useState('0.6');
  const [priceMode, setPriceMode] = useState('coefficient');
  const [manualPrices, setManualPrices] = useState({});
  const [submitting, setSubmitting] = useState(false);

  const rows = useMemo(() => workRowsForEstimate(selectedEstimate), [selectedEstimate]);
  const performers = useMemo(() => performerRows(staff, users), [staff, users]);
  const selectedRows = rows.filter(row => selectedIds[row.id]);
  const selectedPerformer = performers.find(item => String(item.contractorId || item.id) === String(contractorId));
  const brigadeName = (selectedPerformer?.name || manualName || '').trim();
  const coef = Math.max(0, toNumber(coefficient));
  const hasManualPrice = rowId => Object.prototype.hasOwnProperty.call(manualPrices, rowId);
  const priceForRow = row => (
    priceMode === 'manual' || hasManualPrice(row.id)
      ? toNumber(manualPrices[row.id])
      : row.priceSmeta * coef
  );
  const selectedTotal = selectedRows.reduce((sum, row) => {
    return sum + row.quantity * priceForRow(row);
  }, 0);

  if (!show || !selectedEstimate) return null;

  const toggleAll = () => {
    const allSelected = rows.length > 0 && rows.every(row => selectedIds[row.id]);
    if (allSelected) {
      setSelectedIds({});
      return;
    }
    setSelectedIds(Object.fromEntries(rows.map(row => [row.id, true])));
  };

  const submit = async () => {
    if (!brigadeName) {
      alert('Выберите исполнителя или укажите название бригады');
      return;
    }
    if (!selectedRows.length) {
      alert('Выберите работы');
      return;
    }
    if (priceMode === 'coefficient' && coef <= 0) {
      alert('Коэффициент должен быть больше нуля');
      return;
    }
    if (selectedRows.some(row => (
      (priceMode === 'manual' || hasManualPrice(row.id)) && toNumber(manualPrices[row.id]) <= 0
    ))) {
      alert('Для ручной цены заполните цену исполнителю по каждой выбранной строке');
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        assignee: {
          contractorId: selectedPerformer?.contractorId || contractorId || null,
          brigadeName,
          contractorType: selectedPerformer?.employmentType || selectedPerformer?.role || 'Своя бригада',
        },
        priceMode,
        coefficient: coef,
        items: selectedRows.map(row => {
          const rowUsesManualPrice = priceMode === 'manual' || hasManualPrice(row.id);
          return {
            sectionIndex: row.sectionIndex,
            itemIndex: row.itemIndex,
            section: row.section,
            name: row.name,
            unit: row.unit,
            estimateItemKey: row.estimateItemKey,
            coefficient: coef,
            priceMode: rowUsesManualPrice ? 'manual' : 'coefficient',
            manualPrice: rowUsesManualPrice ? toNumber(manualPrices[row.id]) : undefined,
          };
        }),
      };
      const token = localStorage.getItem('authToken');
      const headers = token ? {'Content-Type': 'application/json', Authorization: 'Bearer ' + token} : {'Content-Type': 'application/json'};
      const response = await fetch(API + '/estimates/' + selectedEstimate.id + '/work-assignment', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) {
        alert(data.detail || 'Не удалось назначить работы');
        return;
      }
      await loadAll();
      setSelectedIds({});
      setManualPrices({});
      onClose();
      alert('Работы выданы: ' + data.brigadeName + '\nПозиции: ' + data.items.length + '\nНаряд #' + data.contractId);
    } catch (err) {
      alert('Не удалось назначить работы: ' + (err?.message || err));
    } finally {
      setSubmitting(false);
    }
  };

  const modalWidth = isMobile ? 'calc(100vw - 20px)' : '920px';
  const rowGrid = isMobile ? '28px minmax(0,1fr)' : '28px minmax(220px,1.4fr) 110px 110px 126px 126px';

  return (
    <div onClick={() => !submitting && onClose()} style={{position: 'fixed', inset: 0, backgroundColor: 'rgba(15,23,42,.62)', zIndex: 760, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: isMobile ? '10px' : '22px'}}>
      <div onClick={event => event.stopPropagation()} style={{...card, width: modalWidth, maxHeight: '92vh', overflow: 'hidden', display: 'flex', flexDirection: 'column', padding: 0}}>
        <div style={{padding: '18px 20px', borderBottom: '1px solid ' + C.border, display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start'}}>
          <div>
            <div style={{display: 'flex', gap: '8px', alignItems: 'center'}}>
              <UserCheck size={20} color={C.accent} />
              <b style={{color: C.text, fontSize: '16px'}}>Назначить работы исполнителю</b>
            </div>
            <p style={{color: C.textSec, fontSize: '12px', margin: '5px 0 0'}}>
              {selectedEstimate.projectName || 'Объект'} · {selectedEstimate.workPackage || selectedEstimate.work_package || 'Основная'}
            </p>
          </div>
          <button type="button" onClick={onClose} disabled={submitting} style={{...btnG, padding: '7px 9px'}}><X size={14} /></button>
        </div>

        <div style={{padding: '16px 20px', overflowY: 'auto'}}>
          <div style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'minmax(260px,1fr) 180px 180px', gap: '10px', marginBottom: '14px'}}>
            <select value={contractorId} onChange={event => { setContractorId(event.target.value); if (event.target.value) setManualName(''); }} style={{...inp, marginBottom: 0}}>
              <option value="">Выберите мастера / субподрядчика / бригаду</option>
              {performers.map(item => <option key={(item.contractorId || item.id) + '-' + item.name} value={item.contractorId || item.id}>{item.name}</option>)}
            </select>
            <input value={manualName} onChange={event => { setManualName(event.target.value); if (event.target.value) setContractorId(''); }} placeholder="Или название бригады" style={{...inp, marginBottom: 0}} />
            <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px'}}>
              <button type="button" onClick={() => setPriceMode('coefficient')} style={priceMode === 'coefficient' ? btnO : btnG}>Коэфф.</button>
              <button type="button" onClick={() => setPriceMode('manual')} style={priceMode === 'manual' ? btnO : btnG}>Ручная</button>
            </div>
          </div>

          <div style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '180px 1fr auto', gap: '10px', alignItems: 'center', marginBottom: '14px'}}>
            <label style={{display: 'flex', alignItems: 'center', gap: '8px', color: C.textSec, fontSize: '12px'}}>
              Коэффициент
              <input disabled={priceMode !== 'coefficient'} type="number" min="0.01" step="0.01" value={coefficient} onChange={event => setCoefficient(event.target.value)} style={{...inp, width: '86px', marginBottom: 0, opacity: priceMode === 'coefficient' ? 1 : 0.55}} />
            </label>
            <div style={{padding: '9px 12px', border: '1px solid ' + C.border, borderRadius: '8px', backgroundColor: C.bg}}>
              <b style={{color: C.text, fontSize: '12px'}}>Выбрано: {selectedRows.length} из {rows.length}</b>
              <span style={{color: C.textSec, fontSize: '12px', marginLeft: '8px'}}>к оплате исполнителю: {formatMoney(selectedTotal)}</span>
            </div>
            <button type="button" onClick={toggleAll} style={btnB}><CheckSquare size={14} />{rows.every(row => selectedIds[row.id]) ? 'Снять все' : 'Выбрать все'}</button>
          </div>

          <div style={{border: '1px solid ' + C.border, borderRadius: '10px', overflow: 'hidden'}}>
            {!isMobile && (
              <div style={{display: 'grid', gridTemplateColumns: rowGrid, gap: '8px', padding: '9px 10px', backgroundColor: C.bg, color: C.textMuted, fontSize: '10px', textTransform: 'uppercase', fontWeight: 700}}>
                <span />
                <span>Работа</span>
                <span>Объем</span>
                <span>Смета</span>
                <span>Мастеру</span>
                <span>Сумма</span>
              </div>
            )}
            <div style={{maxHeight: isMobile ? '48vh' : '420px', overflowY: 'auto'}}>
              {rows.map(row => {
                const checked = !!selectedIds[row.id];
                const rowHasManualPrice = hasManualPrice(row.id);
                const masterPrice = priceForRow(row);
                const displayedPrice = rowHasManualPrice ? manualPrices[row.id] : Math.round(row.priceSmeta * coef * 100) / 100;
                return (
                  <div key={row.id} style={{display: 'grid', gridTemplateColumns: rowGrid, gap: '8px', alignItems: 'center', padding: '10px', borderTop: '1px solid ' + C.border, backgroundColor: checked ? C.accentLight : C.bgWhite}}>
                    <input type="checkbox" checked={checked} onChange={event => setSelectedIds(prev => ({...prev, [row.id]: event.target.checked}))} style={{width: '16px', height: '16px', accentColor: C.accent}} />
                    <div style={{minWidth: 0}}>
                      <b style={{display: 'block', color: C.text, fontSize: '12px', overflow: 'hidden', textOverflow: 'ellipsis'}}>{row.name}</b>
                      <span style={{color: C.textMuted, fontSize: '10px'}}>{row.section}</span>
                    </div>
                    <span style={{color: C.textSec, fontSize: '12px'}}>{formatQty(row.quantity, row.unit)}</span>
                    <span style={{color: C.textSec, fontSize: '12px'}}>{formatMoney(row.priceSmeta)}</span>
                    <div style={{display: 'grid', gridTemplateColumns: rowHasManualPrice && priceMode === 'coefficient' ? 'minmax(0,1fr) 26px' : 'minmax(0,1fr)', gap: '4px', alignItems: 'center'}}>
                      <input
                        aria-label={'Цена исполнителю: ' + row.name}
                        type="number"
                        min="0.01"
                        step="any"
                        inputMode="decimal"
                        disabled={!checked}
                        value={priceMode === 'manual' && !rowHasManualPrice ? '' : displayedPrice}
                        onChange={event => setManualPrices(prev => ({...prev, [row.id]: event.target.value}))}
                        placeholder="₽/ед."
                        style={{...inp, width: '100%', minWidth: 0, marginBottom: 0, padding: '6px 7px', fontSize: '12px', borderColor: rowHasManualPrice ? C.warning : C.border}}
                      />
                      {rowHasManualPrice && priceMode === 'coefficient' && (
                        <button
                          type="button"
                          aria-label={'Вернуть цену по коэффициенту: ' + row.name}
                          title="Вернуть цену по коэффициенту"
                          onClick={() => setManualPrices(prev => {
                            const next = {...prev};
                            delete next[row.id];
                            return next;
                          })}
                          style={{...btnG, width: '26px', height: '28px', padding: 0, display: 'inline-flex', alignItems: 'center', justifyContent: 'center'}}
                        >
                          <RotateCcw size={13} />
                        </button>
                      )}
                    </div>
                    <span style={{color: C.success, fontSize: '12px', fontWeight: 800}}>{checked ? formatMoney(row.quantity * masterPrice) : '—'}</span>
                  </div>
                );
              })}
              {!rows.length && <div style={{padding: '24px', textAlign: 'center', color: C.textMuted}}>В смете нет рабочих строк для назначения</div>}
            </div>
          </div>
        </div>

        <div style={{padding: '14px 20px', borderTop: '1px solid ' + C.border, display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap'}}>
          <p style={{margin: 0, color: C.textSec, fontSize: '11px'}}>После выдачи мастер увидит выбранные строки в кабинете и сможет отправлять объемы в ЖПР.</p>
          <div style={{display: 'flex', gap: '8px'}}>
            <button type="button" onClick={onClose} disabled={submitting} style={btnG}>Отмена</button>
            <button type="button" onClick={submit} disabled={submitting || !selectedRows.length || !brigadeName} style={{...btnO, opacity: submitting || !selectedRows.length || !brigadeName ? 0.65 : 1}}>
              {submitting ? 'Выдаю...' : 'Выдать в работу'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

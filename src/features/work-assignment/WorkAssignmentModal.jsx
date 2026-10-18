import React, { useEffect, useMemo, useRef, useState } from 'react';
import { CheckSquare, RotateCcw, Settings2, UserCheck, X } from 'lucide-react';
import { assignmentsForEstimate, contractName, formatMoney, formatQty, toNumber } from './workAssignmentUtils';
import { normalizePersonKey } from '../../utils/performerUtils';

function isPerformer(item = {}) {
    const text = [item.role, item.systemRole, item.category, item.employmentType, item.position, item.name].map(value => String(value || '').toLowerCase()).join(' ');
    return ['мастер', 'субподрядчик', 'бригадир', 'электрик', 'слаботочник', 'отделочник', 'гпх', 'самозанятый', 'ип', 'ооо'].some(token => text.includes(token));
}

const performerOptionId = item => String(item?.optionId || item?.contractorId || item?.id || '');

export function performerRows(staff = [], users = [], brigadeContracts = []) {
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
    if(!Number.isSafeInteger(Number(item.id))||Number(item.id)<=0)return;
    const accessUser = item.accessUserId ? users.find(user=>Number(user.id)===Number(item.accessUserId)) : null;
    const contractorId = item.id;
    addRow({
      ...item,
      id: contractorId,
      contractorId,
      optionId:'staff:'+item.id,
      contractorRef:{type:'staff',id:Number(item.id)},
      role: item.role || accessUser?.role || '',
      employmentType: item.employmentType || accessUser?.role || 'мастер',
      email: accessUser?.email || item.email || item.emailWork || item.emailPersonal || '',
    }, 'staff:'+item.id, item.accessUserId);
  });
  (users || []).filter(isPerformer).forEach(item => {
    if (!item.id || seenUserIds.has(String(item.id))) return;
    addRow({
      ...item,
      contractorId: item.id,
      optionId:'user:'+item.id,
      contractorRef:{type:'user',id:Number(item.id)},
      employmentType: item.role || 'мастер',
    }, 'user:' + item.id, item.id);
  });
  (brigadeContracts || []).forEach(contract => {
    const name = String(contract.brigadeName || contract.brigade_name || '').trim();
    const contractId = contract.id;
    if (!name || !Number.isSafeInteger(Number(contractId)) || Number(contractId) <= 0
      || ['Аннулирован','Удалён','Удален'].includes(contract.status)) return;
    addRow({
      ...contract,
      id: 'contract:' + contractId,
      optionId: 'contract:' + contractId,
      contractorRef: {type:'contract',id:Number(contractId)},
      contractorId: contract.contractorId || contract.contractor_id || '',
      name,
      employmentType: contract.contractorType || contract.contractor_type || 'Своя бригада',
    }, 'contract:' + contractId);
  });
  return rows.sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'ru'));
}

export default function WorkAssignmentModal({
  show,
  onClose,
  selectedEstimate,
  brigadeContracts,
  brigadeContractItems,
  staff,
  users,
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
  const [manualPerformer, setManualPerformer] = useState(false);
  const [manualName, setManualName] = useState('');
  const [percentage, setPercentage] = useState('60');
  const [priceMode, setPriceMode] = useState('coefficient');
  const [manualPrices, setManualPrices] = useState({});
  const [showPriceSettings, setShowPriceSettings] = useState(false);
  const [workSearch, setWorkSearch] = useState('');
  const [sectionFilter, setSectionFilter] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submissionError, setSubmissionError] = useState('');
  const [showAssigned, setShowAssigned] = useState(false);
  const [mobileStep, setMobileStep] = useState(1);
  const bodyRef = useRef(null);
  useEffect(() => { if (bodyRef.current) bodyRef.current.scrollTop = 0; }, [mobileStep]);
  const initializedSourceRef = useRef(null);

  const assignmentRows = useMemo(
    () => assignmentsForEstimate(selectedEstimate, brigadeContractItems || [], brigadeContracts || []),
    [selectedEstimate, brigadeContractItems, brigadeContracts],
  );
  const rows = useMemo(
    () => assignmentRows.filter(row => row.assignments.length === 0),
    [assignmentRows],
  );
  const assignedRows = useMemo(
    () => assignmentRows.filter(row => row.assignments.length > 0),
    [assignmentRows],
  );
  const workSections = useMemo(() => Array.from(new Map(rows.map(row => [
    String(row.sectionIndex), {id: String(row.sectionIndex), name: row.section, number: row.sectionIndex + 1},
  ])).values()), [rows]);
  const hasWorkFilter = Boolean(workSearch.trim() || sectionFilter);
  const visibleRows = useMemo(() => {
    const query = workSearch.trim().toLocaleLowerCase('ru-RU');
    return rows.filter(row => (sectionFilter === '' || String(row.sectionIndex) === sectionFilter)
      && (!query || [row.name, row.section].some(value => String(value || '').toLocaleLowerCase('ru-RU').includes(query))));
  }, [rows, workSearch, sectionFilter]);
  const assignedCount = assignedRows.length;
  const performers = useMemo(
    () => performerRows(staff || [], users || [], (brigadeContracts || []).filter(contract => (
      Number(selectedEstimate?.projectId || selectedEstimate?.project_id) > 0
      && Number(contract.projectId || contract.project_id) === Number(selectedEstimate?.projectId || selectedEstimate?.project_id)
      && (contract.workPackage || contract.work_package || 'Основная') === (selectedEstimate?.workPackage || selectedEstimate?.work_package || 'Основная')
    ))),
    [staff, users, brigadeContracts, selectedEstimate],
  );
  const sourceKey = useMemo(() => JSON.stringify([
    selectedEstimate?.id,
    assignmentRows.map(row => [row.estimateItemKey, row.name, row.quantity, row.priceSmeta, row.assignments.map(item => item.contractId || item.contract_id)]),
  ]), [selectedEstimate?.id, assignmentRows]);
  const selectedRows = rows.filter(row => selectedIds[row.id]);
  const visibleIds = new Set(visibleRows.map(row => row.id));
  const hiddenSelectedCount = selectedRows.filter(row => !visibleIds.has(row.id)).length;
  const allVisibleSelected = visibleRows.length > 0 && visibleRows.every(row => selectedIds[row.id]);
  const selectedPerformer = performers.find(item => performerOptionId(item) === String(contractorId));
  const brigadeName = (selectedPerformer?.name || manualName || '').trim();
  const coef = Math.max(0, toNumber(percentage) / 100);
  const hasManualPrice = rowId => Object.prototype.hasOwnProperty.call(manualPrices, rowId);
  const priceForRow = row => (
    priceMode === 'manual' || hasManualPrice(row.id)
      ? toNumber(manualPrices[row.id])
      : row.priceSmeta * coef
  );
  const selectedTotal = selectedRows.reduce((sum, row) => {
    return sum + row.quantity * priceForRow(row);
  }, 0);
  const missingStep = !brigadeName ? 'Сначала выберите исполнителя.' : !selectedRows.length ? 'Отметьте хотя бы одну работу.' : '';

  useEffect(() => {
    setSubmissionError('');
  }, [brigadeName, selectedIds, percentage, manualPrices, priceMode]);

  useEffect(() => {
    if (!show || !selectedEstimate) {
      initializedSourceRef.current = null;
      return;
    }
    if (initializedSourceRef.current === sourceKey) return;
    initializedSourceRef.current = sourceKey;
    setSelectedIds(Object.fromEntries(rows.map(row => [row.id, true])));
    setContractorId(performers.length === 1 ? performerOptionId(performers[0]) : '');
    setManualPerformer(false);
    setManualName('');
    setMobileStep(1);
    setPercentage('60');
    setPriceMode('coefficient');
    setManualPrices({});
    setShowPriceSettings(false);
    setWorkSearch('');
    setSectionFilter('');
    setSubmissionError('');
    setShowAssigned(rows.length === 0 && assignedRows.length > 0);
  }, [show, selectedEstimate, rows, assignedRows, performers, sourceKey]);

  if (!show || !selectedEstimate) return null;

  const toggleAll = () => {
    setSelectedIds(previous => {
      const next = {...previous};
      visibleRows.forEach(row => { next[row.id] = !allVisibleSelected; });
      return next;
    });
  };

  const submit = async () => {
    setSubmissionError('');
    if (!brigadeName) {
      setSubmissionError('Выберите исполнителя или укажите название бригады');
      return;
    }
    if (!selectedRows.length) {
      setSubmissionError('Выберите работы');
      return;
    }
    if (priceMode === 'coefficient' && coef <= 0) {
      setSubmissionError('Укажите долю исполнителя больше 0%');
      return;
    }
    if (selectedRows.some(row => (
      (priceMode === 'manual' || hasManualPrice(row.id)) && toNumber(manualPrices[row.id]) <= 0
    ))) {
      setSubmissionError('Для ручной цены заполните цену исполнителю по каждой выбранной строке');
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        assignee: {
          contractorId: selectedPerformer?.contractorId || null,
          ...(selectedPerformer?.contractorRef ? {contractorRef:selectedPerformer.contractorRef} : {}),
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
      const response = await fetch(API + '/estimates/' + selectedEstimate.id + '/work-assignment', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) {
        setSubmissionError(typeof data.detail === 'string' ? data.detail : 'Не удалось назначить работы');
        return;
      }
      let refreshFailed = false;
      try {
        await loadAll();
      } catch (_) {
        refreshFailed = true;
      }
      setSelectedIds({});
      setManualPrices({});
      onClose();
      alert('Работы выданы: ' + (data.brigadeName || brigadeName)
        + '\nПозиции: ' + (Array.isArray(data.items) ? data.items.length : selectedRows.length)
        + (data.contractId ? '\nНаряд #' + data.contractId : '')
        + (refreshFailed ? '\nСписок не обновился. Обновите страницу.' : ''));
    } catch (_) {
      setSubmissionError('Не удалось назначить работы. Проверьте соединение и повторите попытку.');
    } finally {
      setSubmitting(false);
    }
  };

  const modalWidth = isMobile ? 'calc(100vw - 20px)' : '920px';
  const rowGrid = '28px minmax(140px,1.4fr) minmax(70px,.7fr) minmax(70px,.7fr) minmax(90px,.85fr) minmax(90px,.85fr)';

  return (
    <div onClick={() => !submitting && onClose()} style={{position: 'fixed', inset: 0, backgroundColor: 'rgba(15,23,42,.62)', zIndex: 760, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: isMobile ? '10px' : '22px'}}>
      <div role="dialog" aria-modal="true" aria-labelledby="work-assignment-title" onClick={event => event.stopPropagation()} style={{...card, width: modalWidth, maxHeight: 'calc(100dvh - 20px)', minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column', padding: 0}}>
        <div style={{flexShrink: 0, padding: isMobile ? '12px' : '18px 20px', borderBottom: '1px solid ' + C.border, display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start'}}>
          <div>
            <div style={{display: 'flex', gap: '8px', alignItems: 'center'}}>
              <UserCheck size={20} color={C.accent} />
              <b id="work-assignment-title" style={{color: C.text, fontSize: '16px'}}>Назначить работы исполнителю</b>
            </div>
            <p style={{color: C.textSec, fontSize: '12px', margin: '5px 0 0'}}>
              {selectedEstimate.projectName || 'Объект'} · {selectedEstimate.workPackage || selectedEstimate.work_package || 'Основная'}
            </p>
          </div>
          <button type="button" aria-label="Закрыть назначение работ" onClick={onClose} disabled={submitting} style={{...btnG, padding: '7px 9px'}}><X size={14} /></button>
        </div>

        {isMobile && <p role="status" style={{margin:'10px 12px',color:C.textSec,fontSize:13}}>Шаг {mobileStep} из 3 · {['Исполнитель','Работы','Проверка суммы'][mobileStep-1]}</p>}
        <div ref={bodyRef} style={{padding: isMobile ? '12px' : '16px 20px', overflowY: 'auto', minHeight: 0, flex: '1 1 auto', overscrollBehavior: 'contain'}}>
          <div style={{display: isMobile && mobileStep !== 1 ? 'none' : undefined, marginBottom: '18px'}}>
            <b style={{display: 'block', color: C.text, fontSize: '15px', marginBottom: '4px'}}>1. Кому выдать работы</b>
            <p style={{color: C.textSec, fontSize: '12px', margin: '0 0 10px'}}>Выберите человека или бригаду. Новую бригаду можно указать в этом же списке.</p>
            <div style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'minmax(260px,1fr) minmax(200px,1fr)', gap: '10px'}}>
              <select aria-label="Исполнитель" value={manualPerformer ? '__manual__' : contractorId} onChange={event => {
                const isManual = event.target.value === '__manual__';
                setManualPerformer(isManual);
                setContractorId(isManual ? '' : event.target.value);
                if (!isManual) setManualName('');
              }} style={{...inp, marginBottom: 0}}>
                <option value="">Выберите исполнителя</option>
                {performers.map(item => <option key={performerOptionId(item) + '-' + item.name} value={performerOptionId(item)}>{item.name}{item.contractorRef?.type==='contract' ? ` · договор №${item.contractorRef.id}` : performers.filter(row=>normalizePersonKey(row.name)===normalizePersonKey(item.name)).length>1 ? (item.contractorRef?.type==='staff'?' · сотрудник':' · учётная запись') : ''}</option>)}
                <option value="__manual__">+ Новая бригада</option>
              </select>
              {manualPerformer && <input aria-label="Название новой бригады" autoFocus value={manualName} onChange={event => setManualName(event.target.value)} placeholder="Название бригады" style={{...inp, marginBottom: 0}} />}
            </div>
          </div>

          <div style={{display:isMobile && mobileStep !== 2 ? 'none' : undefined}}>
          <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', marginBottom: '10px'}}>
            <div>
              <b style={{display: 'block', color: C.text, fontSize: '15px'}}>2. Какие работы выдать</b>
              <span style={{color: C.textSec, fontSize: '12px'}}>Показаны только ещё не назначенные работы.</span>
            </div>
            {rows.length > 0 && <button type="button" onClick={toggleAll} disabled={!visibleRows.length} style={btnB}><CheckSquare size={14} />{hasWorkFilter ? (allVisibleSelected ? 'Снять показанные' : 'Выбрать показанные') : (allVisibleSelected ? 'Снять все' : 'Выбрать все')}</button>}
          </div>
          <div style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'minmax(220px,1fr) auto', gap: '10px', alignItems: 'center', marginBottom: '14px'}}>
            <div style={{padding: '9px 12px', border: '1px solid ' + C.border, borderRadius: '8px', backgroundColor: C.bg}}>
              <b style={{color: C.text, fontSize: '12px'}}>Выбрано: {selectedRows.length} из {rows.length}</b>
              {assignedCount > 0 && <button type="button" aria-expanded={showAssigned} aria-controls="work-assignment-existing" onClick={() => setShowAssigned(value => !value)} style={{border: 0, background: 'none', padding: 0, marginLeft: '8px', color: C.success, fontSize: '12px', cursor: 'pointer', textDecoration: 'underline'}}>Уже назначено: {assignedCount}</button>}
            </div>
          </div>
          {showAssigned && assignedCount > 0 && <div id="work-assignment-existing" role="region" aria-label="Уже назначенные работы" style={{display: 'grid', gap: '7px', marginBottom: '14px', padding: '10px', border: '1px solid ' + C.border, borderRadius: '8px', backgroundColor: C.bg}}>
            {assignedRows.map(row => <div key={row.id} style={{display: 'flex', gap: '4px 10px', justifyContent: 'space-between', flexWrap: 'wrap', padding: '7px 8px', borderRadius: '6px', backgroundColor: C.bgWhite, color: C.text, fontSize: '12px'}}>
              <span>{row.name}</span>
              <span style={{color: C.textSec}}>{row.assignments.map(assignment => contractName(assignment.contract) || contractName(assignment) || 'Исполнитель не указан').join(', ')}</span>
            </div>)}
          </div>}

          {(rows.length > 8 || workSections.length > 1) && <div style={{marginBottom:'10px'}}>
            {workSections.length > 1 && <label style={{display:'grid',gap:4,color:C.textSec,fontSize:12,marginBottom:8}}>Раздел сметы
              <select aria-label="Раздел сметы" value={sectionFilter} onChange={event => setSectionFilter(event.target.value)} style={{...inp,width:'100%',boxSizing:'border-box',marginBottom:0}}>
                <option value="">Все разделы</option>
                {workSections.map(section => <option key={section.id} value={section.id}>{section.number}. {section.name || 'Без названия'}</option>)}
              </select>
            </label>}
            <input type="search" aria-label="Найти работу" value={workSearch} onChange={event => setWorkSearch(event.target.value)} placeholder="Найти работу или раздел" style={{...inp,width:'100%',boxSizing:'border-box',marginBottom:'4px'}} />
            <span style={{color:C.textSec,fontSize:'11px'}}>Показано: {visibleRows.length} из {rows.length}. Кнопка выбора действует только на показанные работы.</span>
            {hiddenSelectedCount > 0 && <div role="status" style={{marginTop:'8px',padding:'10px',border:'1px solid '+C.border,borderRadius:'8px'}}>
              <p style={{color:C.text,margin:'0 0 8px',fontSize:'12px'}}>Ещё {hiddenSelectedCount} выбранных работ скрыты {sectionFilter ? 'фильтром' : 'поиском'}. Они тоже будут выданы исполнителю.</p>
              <button type="button" disabled={submitting} onClick={() => setSelectedIds(previous => Object.fromEntries(
                Object.entries(previous).filter(([id]) => visibleRows.some(row => String(row.id) === id)),
              ))} style={{...btnB,minHeight:'44px'}}>Оставить только найденные</button>
            </div>}
          </div>}

          </div>
          <div style={{display:isMobile && mobileStep !== 3 ? 'none' : undefined}}>
          {isMobile && <p style={{color:C.text}}>Исполнитель: <strong>{brigadeName}</strong></p>}
          <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', marginBottom: '10px'}}>
            <div>
              <b style={{display: 'block', color: C.text, fontSize: '15px'}}>3. Сколько получит исполнитель</b>
              <span style={{color: C.textSec, fontSize: '12px'}}>По умолчанию исполнителю идёт 60% от цены работы в смете. Перед выдачей проверьте сумму ниже.</span>
            </div>
            <button type="button" onClick={() => setShowPriceSettings(value => !value)} style={btnG}>
              <Settings2 size={14} />{showPriceSettings ? 'Скрыть цену' : 'Настроить цену'}
            </button>
          </div>

          {showPriceSettings && (
            <div style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '180px 180px 1fr', gap: '10px', alignItems: 'center', marginBottom: '14px', padding: '10px', border: '1px solid ' + C.border, borderRadius: '8px', backgroundColor: C.bg}}>
              <button type="button" onClick={() => setPriceMode('coefficient')} style={priceMode === 'coefficient' ? btnO : btnG}>Доля от сметы</button>
              <button type="button" onClick={() => setPriceMode('manual')} style={priceMode === 'manual' ? btnO : btnG}>Своя цена</button>
              <label style={{display: 'flex', alignItems: 'center', gap: '8px', color: C.textSec, fontSize: '12px'}}>
                Доля исполнителя, %
                <input aria-label="Доля исполнителя, %" disabled={priceMode !== 'coefficient'} type="number" min="0.01" step="any" value={percentage} onChange={event => setPercentage(event.target.value)} style={{...inp, width: '86px', marginBottom: 0, opacity: priceMode === 'coefficient' ? 1 : 0.55}} />
              </label>
            </div>
          )}

          </div>
          <div style={{display:isMobile && mobileStep === 1 ? 'none' : undefined}}>
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
            <div style={{maxHeight: isMobile ? undefined : '420px', overflowY: isMobile ? 'visible' : 'auto'}}>
              {(isMobile && mobileStep === 3 ? selectedRows : visibleRows).map(row => {
                const checked = !!selectedIds[row.id];
                const rowHasManualPrice = hasManualPrice(row.id);
                const masterPrice = priceForRow(row);
                const displayedPrice = rowHasManualPrice ? manualPrices[row.id] : Math.round(row.priceSmeta * coef * 100) / 100;
                return (
                  <div key={row.id} style={{display: 'grid', gridTemplateColumns: isMobile ? '28px minmax(0,1fr) auto' : rowGrid, gap: '8px', alignItems: 'center', padding: isMobile ? '14px 12px' : '10px', borderTop: '1px solid ' + C.border, backgroundColor: checked ? C.accentLight : C.bgWhite}}>
                    <input aria-label={'Выбрать работу: ' + row.name} type="checkbox" checked={checked} onChange={event => setSelectedIds(prev => ({...prev, [row.id]: event.target.checked}))} style={{width: '18px', height: '18px', accentColor: C.accent}} />
                    <div style={{minWidth: 0}}>
                      <b style={{display: 'block', color: C.text, fontSize: '12px', overflow: 'hidden', textOverflow: 'ellipsis'}}>{row.name}</b>
                      <span style={{color: C.textMuted, fontSize: '10px'}}>{row.section}{isMobile ? ' · ' + formatQty(row.quantity, row.unit) : ''}</span>
                      {isMobile && <span style={{display: 'block', color: C.textSec, fontSize: '11px', marginTop: '3px'}}>Смета: {formatMoney(row.priceSmeta)}/ед. · Исполнителю: {formatMoney(masterPrice)}/ед.</span>}
                    </div>
                    <span style={{color: C.textSec, fontSize: '12px', display: isMobile ? 'none' : undefined}}>{formatQty(row.quantity, row.unit)}</span>
                    <span style={{color: C.textSec, fontSize: '12px', display: isMobile ? 'none' : undefined}}>{formatMoney(row.priceSmeta)}</span>
                    {showPriceSettings && (!isMobile || mobileStep === 3) ? <div style={{display: 'grid', gridTemplateColumns: rowHasManualPrice && priceMode === 'coefficient' ? 'minmax(0,1fr) 26px' : 'minmax(0,1fr)', gap: '4px', alignItems: 'center', gridColumn: isMobile ? '2 / -1' : undefined, gridRow: isMobile ? '2' : undefined}}>
                      {isMobile && <span style={{gridColumn: '1 / -1', color: C.textSec, fontSize: '11px'}}>Цена исполнителю за единицу</span>}
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
                    </div> : <span style={{color: C.textSec, fontSize: '12px', display: isMobile ? 'none' : undefined}}>{formatMoney(masterPrice)}</span>}
                    <span style={{color: C.success, fontSize: '12px', fontWeight: 800, gridColumn: isMobile ? '3' : undefined, gridRow: isMobile ? '1' : undefined}}>{checked ? formatMoney(row.quantity * masterPrice) : '—'}</span>
                  </div>
                );
              })}
              {!(isMobile && mobileStep === 3 ? selectedRows : visibleRows).length && <div style={{padding: '24px', textAlign: 'center', color: C.textMuted}}>{rows.length ? (sectionFilter ? 'Работы не найдены. Измените раздел или очистите поиск.' : 'Работы не найдены. Очистите поиск.') : assignmentRows.length ? 'Все работы этой сметы уже назначены' : 'В смете нет рабочих строк для назначения'}</div>}
            </div>
          </div>
          </div>
        </div>

        <div style={{flexShrink: 0, padding: isMobile ? '12px' : '14px 20px', borderTop: '1px solid ' + C.border, backgroundColor: C.bgWhite, display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', alignItems: 'center'}}>
          <div><b style={{display: 'block', color: C.text, fontSize: '14px'}}>Исполнителю: {formatMoney(selectedTotal)}</b><span style={{color: C.textSec, fontSize: '11px'}}>Выбрано работ: {selectedRows.length}</span></div>
          <div style={{display: 'flex', gap: '8px'}}>
            {isMobile && mobileStep > 1 && <button type="button" disabled={submitting} onClick={()=>setMobileStep(step=>step-1)} style={{...btnG,minHeight:44}}>Назад</button>}
            <button type="button" onClick={onClose} disabled={submitting} style={btnG}>Отмена</button>
            {isMobile && mobileStep < 3 ? <button type="button" disabled={submitting || (mobileStep===1 ? !brigadeName : !selectedRows.length)} onClick={()=>setMobileStep(step=>step+1)} style={{...btnO,minHeight:44}}>Далее</button> : <button type="button" onClick={submit} disabled={submitting || !selectedRows.length || !brigadeName} style={{...btnO, opacity: submitting || !selectedRows.length || !brigadeName ? 0.65 : 1}}>
              {submitting ? 'Выдаю...' : 'Выдать в работу'}
            </button>}
          </div>
          {submissionError
            ? <p role="alert" style={{order: 1, flexBasis: '100%', color: C.danger || '#b91c1c', margin: 0, fontSize: '12px'}}>{submissionError}</p>
            : missingStep && <p role="status" style={{order: 1, flexBasis: '100%', color: C.textSec, margin: 0, fontSize: '12px'}}>{missingStep}</p>}
        </div>
      </div>
    </div>
  );
}

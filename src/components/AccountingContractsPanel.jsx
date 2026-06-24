import React from 'react';
import { Check, Eye, Plus, Search, Trash2, X } from 'lucide-react';

export default function AccountingContractsPanel({
  C,
  card,
  inp,
  btnO,
  btnG,
  btnB,
  btnR,
  badge,
  isFinanceRole,
  showForm,
  setShowForm,
  newContract,
  setNewContract,
  resolveContractPerformer,
  contractRequisitesWarning,
  createContract,
  projects,
  staff,
  listSearch,
  setListSearch,
  matchSearch,
  contracts,
  brigadeContracts,
  projectDocuments,
  normalizePersonKey,
  allBrigadePayments,
  interimActs,
  pdConsents,
  allBrigadeItems,
  showPreview,
  buildContractContent,
  deleteContract,
}) {
  const emptyFn = () => {};
  const canEditFinance = typeof isFinanceRole === 'function' ? isFinanceRole : () => Boolean(isFinanceRole);
  const searchMatches = typeof matchSearch === 'function'
    ? matchSearch
    : (query, ...values) => {
      const needle = String(query || '').trim().toLowerCase();
      if (!needle) return true;
      return values.some(value => String(value || '').toLowerCase().includes(needle));
    };
  const personKey = typeof normalizePersonKey === 'function'
    ? normalizePersonKey
    : value => String(value || '').trim().toLowerCase().replace(/\s+/g, ' ');
  const resolvePerformer = (row = {}) => {
    if (typeof resolveContractPerformer !== 'function') {
      const name = row.masterName || row.brigadeName || row.performerName || 'Исполнитель не выбран';
      return { fullName: name, name, contractType: row.contractType || row.contractorType || 'ГПХ' };
    }
    try {
      return resolveContractPerformer(row) || {};
    } catch (error) {
      console.warn('Accounting contracts performer resolve failed', error);
      const name = row.masterName || row.brigadeName || row.performerName || 'Исполнитель не выбран';
      return { fullName: name, name, contractType: row.contractType || row.contractorType || 'ГПХ' };
    }
  };
  const requisitesWarning = (performer, type) => {
    if (typeof contractRequisitesWarning !== 'function') return '';
    try {
      return contractRequisitesWarning(performer || {}, type || '') || '';
    } catch (error) {
      console.warn('Accounting contracts requisites check failed', error);
      return '';
    }
  };
  const renderBadge = typeof badge === 'function'
    ? badge
    : (color, bg, border) => ({ color, backgroundColor: bg, border: '1px solid ' + border, borderRadius: '999px', padding: '4px 8px', fontSize: '11px', fontWeight: 800 });
  const contractRows = Array.isArray(contracts) ? contracts.filter(Boolean) : [];
  const brigadeContractRows = Array.isArray(brigadeContracts) ? brigadeContracts.filter(Boolean) : [];
  const documents = Array.isArray(projectDocuments) ? projectDocuments : [];
  const brigadePayments = Array.isArray(allBrigadePayments) ? allBrigadePayments : [];
  const acts = Array.isArray(interimActs) ? interimActs : [];
  const consents = Array.isArray(pdConsents) ? pdConsents : [];
  const brigadeItems = Array.isArray(allBrigadeItems) ? allBrigadeItems : [];
  const projectRows = Array.isArray(projects) ? projects.filter(Boolean) : [];
  const staffRows = Array.isArray(staff) ? staff.filter(Boolean) : [];
  const draftContract = newContract || { masterId: '', masterName: '', contractType: 'ГПХ', contractNumber: '', project: '', startDate: '', endDate: '' };
  const updateDraftContract = typeof setNewContract === 'function' ? setNewContract : emptyFn;
  const toggleForm = typeof setShowForm === 'function' ? setShowForm : emptyFn;
  const updateSearch = typeof setListSearch === 'function' ? setListSearch : emptyFn;
  const openPreview = typeof showPreview === 'function' ? showPreview : emptyFn;
  const buildPreview = typeof buildContractContent === 'function' ? buildContractContent : () => '<p>Печатная форма договора недоступна</p>';
  const removeContract = typeof deleteContract === 'function' ? deleteContract : emptyFn;
  const submitContract = typeof createContract === 'function' ? createContract : emptyFn;

  const sourceRows = [
    ...(contractRows.map((contract, index) => ({ ...contract, _kind: 'contract', _rowKey: 'contract-' + (contract.id || index), projectName: contract.project || contract.projectName || '' }))),
    ...(brigadeContractRows.map((contract, index) => ({
      ...contract,
      _kind: 'brigade',
      _rowKey: 'brigade-' + (contract.id || index),
      masterId: contract.contractorId,
      masterName: contract.brigadeName,
      contractType: contract.contractorType,
      contractNumber: contract.contractNumber || ('БР-' + contract.id),
      project: contract.projectName,
      projectName: contract.projectName,
      startDate: contract.signedAt || '',
      endDate: '',
    }))),
  ];

  const hasClosingDoc = (row, performer, docNeed = '') => {
    const projectName = row.project || row.projectName || '';
    const nameKey = personKey(performer.fullName || row.masterName || row.brigadeName);
    return documents.some(document => {
      if (projectName && document.projectName !== projectName) return false;
      const rawHaystack = [document.counterparty, document.docType, document.number, document.notes].filter(Boolean).join(' ');
      const haystack = personKey(rawHaystack);
      if (docNeed === 'self-employed-receipt' && !/чек|нпд|самозан|закрыва/i.test(rawHaystack)) return false;
      if (docNeed && docNeed !== 'self-employed-receipt' && !haystack.includes(personKey(docNeed))) return false;
      return !nameKey || haystack.includes(nameKey) || nameKey.includes(personKey(document.counterparty));
    });
  };

  const rowFinance = (row, performer) => {
    const isBrigade = row._kind === 'brigade';
    const type = String(row.contractType || row.contractorType || performer.contractType || '').toLowerCase();
    if (isBrigade) {
      const accrued = Number(row.doneAmount || 0);
      const paid = brigadePayments.filter(payment => Number(payment.contractId) === Number(row.id)).reduce((sum, payment) => sum + Number(payment.amount || 0), 0) || Number(row.paidAmount || 0);
      const retention = Math.round(accrued * 0.05);
      const payable = Math.max(0, accrued - retention);
      const owe = Math.max(0, payable - paid);
      const missingDocs = [];
      if (accrued > 0 && !row.actScanUrl) missingDocs.push('скан подписанного акта');
      if (paid > 0 && type.includes('самозан') && !hasClosingDoc(row, performer, 'self-employed-receipt')) missingDocs.push('чек НПД');
      return { accrued, paid, retention, payable, owe, missingDocs };
    }

    const rowActs = acts.filter(act =>
      Number(act.contractId || 0) === Number(row.id)
      || (Number(act.masterId || 0) === Number(row.masterId || 0) && (!row.project || act.project === row.project))
      || (personKey(act.masterName) === personKey(row.masterName) && (!row.project || act.project === row.project))
    );
    const accrued = rowActs.reduce((sum, act) => sum + Number(act.totalAmount || 0), 0);
    const paid = rowActs.reduce((sum, act) => sum + Number(act.paidAmount || 0), 0);
    const retention = Math.round(accrued * 0.05);
    const payable = Math.max(0, accrued - retention);
    const owe = Math.max(0, payable - paid);
    const missingDocs = [];
    if (rowActs.some(act => Number(act.totalAmount || 0) > 0 && !act.scanUrl)) missingDocs.push('скан подписанного акта');
    if (paid > 0 && type.includes('самозан') && !hasClosingDoc(row, performer, 'self-employed-receipt')) missingDocs.push('чек НПД');
    return { accrued, paid, retention, payable, owe, missingDocs, actsCount: rowActs.length };
  };

  const visibleRows = sourceRows.filter(row => {
    const performer = resolvePerformer(row);
    return searchMatches(listSearch, row.contractNumber, row.project, row.projectName, row.masterName, row.brigadeName, performer.fullName, performer.inn);
  });

  const groupedRows = (() => {
    const groups = {};
    visibleRows.forEach(row => {
      const performer = resolvePerformer(row);
      const finance = rowFinance(row, performer);
      const key = personKey(performer.fullName || row.masterName || row.brigadeName) || row._rowKey;
      if (!groups[key]) {
        groups[key] = {
          key,
          name: performer.fullName || row.masterName || row.brigadeName || 'Исполнитель',
          performer,
          rows: [],
          projects: new Set(),
          types: new Set(),
          total: 0,
          paid: 0,
          retention: 0,
          payable: 0,
          owe: 0,
          warnings: new Set(),
          missingDocs: new Set(),
        };
      }
      groups[key].rows.push({ ...row, performer, finance });
      if (row.project || row.projectName) groups[key].projects.add(row.project || row.projectName);
      if (row.contractType || row.contractorType) groups[key].types.add(row.contractType || row.contractorType);
      groups[key].total += finance.accrued;
      groups[key].paid += finance.paid;
      groups[key].retention += finance.retention;
      groups[key].payable += finance.payable;
      groups[key].owe += finance.owe;
      const warning = requisitesWarning(performer, row.contractType || row.contractorType);
      if (warning) groups[key].warnings.add(warning);
      (finance.missingDocs || []).forEach(item => groups[key].missingDocs.add(item));
    });
    return Object.values(groups).sort((left, right) => String(left.name || '').localeCompare(String(right.name || ''), 'ru'));
  })();

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
        <b style={{ color: C.text, fontSize: '15px', fontWeight: '700' }}>Договоры</b>
        {canEditFinance() && (
          <button onClick={() => toggleForm(!showForm)} style={btnO}>
            <Plus size={14} />
            Новый договор
          </button>
        )}
      </div>
      {showForm && (
        <div style={{ ...card, padding: '20px', marginBottom: '16px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <select
              value={draftContract.masterId || ''}
              onChange={event => {
                const masterId = event.target.value;
                const performer = resolvePerformer({ ...draftContract, masterId });
                updateDraftContract({
                  ...draftContract,
                  masterId,
                  masterName: performer.fullName || performer.name || '',
                  contractType: performer.contractType || draftContract.contractType || 'ГПХ',
                });
              }}
              style={{ ...inp, marginBottom: 0 }}
            >
              <option value="">Выберите исполнителя *</option>
              {(() => {
                const activeStaff = staffRows.filter(item => item.status !== 'Уволен' && item.status !== 'Архив' && item.name);
                const normalizedRole = role => String(role || '').toLowerCase().replace('_', ' ').trim();
                const groups = [
                  { label: '👷 Мастера и субподрядчики', match: role => ['мастер', 'субподрядчик', 'бригадир', 'рабочий', 'отделочник', 'электрик', 'сантехник', 'штукатур', 'маляр', 'плиточник', 'каменщик', 'монтажник'].some(key => role.includes(key)) },
                  { label: '🔨 Прорабы и ИТР', match: role => (['прораб', 'инженер', 'начальник', 'мастер участка'].some(key => role.includes(key)) && !['мастер участка'].includes(role)) ? true : ['прораб', 'инженер', 'начальник'].some(key => role.includes(key)) },
                  { label: '🏢 Юр.лица (ИП/ООО/Орг)', match: role => ['ип', 'ооо', 'организация', 'юр', 'зао', 'оао'].some(key => role.includes(key)) },
                  { label: '👥 Прочие сотрудники', match: () => true },
                ];
                const used = new Set();
                return groups.map(group => {
                  const items = activeStaff.filter(item => !used.has(item.id) && group.match(normalizedRole(item.role)));
                  items.forEach(item => used.add(item.id));
                  if (items.length === 0) return null;
                  return (
                    <optgroup key={group.label} label={group.label}>
                      {items.map(item => (
                        <option key={item.id} value={item.id}>
                          {item.name + (item.role ? ' · ' + item.role : '') + (item.specialization ? ' · ' + item.specialization : '')}
                        </option>
                      ))}
                    </optgroup>
                  );
                });
              })()}
            </select>
            <select value={draftContract.contractType || 'ГПХ'} onChange={event => updateDraftContract({ ...draftContract, contractType: event.target.value })} style={{ ...inp, marginBottom: 0 }}>
              {['ГПХ', 'ТД', 'Самозанятый', 'ИП', 'ООО', 'Подряд'].map(type => <option key={type}>{type}</option>)}
            </select>
            <input placeholder="Номер договора *" value={draftContract.contractNumber || ''} onChange={event => updateDraftContract({ ...draftContract, contractNumber: event.target.value })} style={{ ...inp, marginBottom: 0 }} />
            <select value={draftContract.project || ''} onChange={event => updateDraftContract({ ...draftContract, project: event.target.value })} style={{ ...inp, marginBottom: 0 }}>
              <option value="">Выберите объект *</option>
              {projectRows.map(project => <option key={project.id || project.name} value={project.name}>{project.name}</option>)}
            </select>
            <input type="date" placeholder="Начало" value={draftContract.startDate || ''} onChange={event => updateDraftContract({ ...draftContract, startDate: event.target.value })} style={{ ...inp, marginBottom: 0 }} />
            <input type="date" placeholder="Конец" value={draftContract.endDate || ''} onChange={event => updateDraftContract({ ...draftContract, endDate: event.target.value })} style={{ ...inp, marginBottom: 0 }} />
          </div>
          {draftContract.masterId && (() => {
            const performer = resolvePerformer(draftContract);
            const warning = requisitesWarning(performer, draftContract.contractType);
            return warning ? (
              <div style={{ marginTop: '10px', padding: '10px 12px', borderRadius: '8px', backgroundColor: C.warningLight, border: '1.5px solid ' + C.warningBorder, color: C.warning, fontSize: '12px', fontWeight: '600' }}>
                ⚠️ {warning}
              </div>
            ) : (
              <div style={{ marginTop: '10px', padding: '10px 12px', borderRadius: '8px', backgroundColor: C.successLight, border: '1.5px solid ' + C.successBorder, color: C.success, fontSize: '12px', fontWeight: '600' }}>
                ✅ Реквизиты исполнителя заполнены для печати договора
              </div>
            );
          })()}
          <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
            <button onClick={submitContract} style={btnO}>
              <Check size={14} />
              Создать
            </button>
            <button onClick={() => toggleForm(false)} style={btnG}>
              <X size={14} />
              Отмена
            </button>
          </div>
        </div>
      )}

      <div style={{ position: 'relative', marginBottom: '12px' }}>
        <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: C.textMuted }} />
        <input placeholder='🔍 Поиск договора (номер, мастер, объект)' value={listSearch || ''} onChange={event => updateSearch(event.target.value)} style={{ ...inp, marginBottom: 0, paddingLeft: '32px' }} />
      </div>

      {groupedRows.length === 0 ? (
        <p style={{ color: C.textMuted, textAlign: 'center', padding: '30px' }}>Договоров и расчётов с исполнителями нет</p>
      ) : (
        groupedRows.map(group => (
          <div key={group.key} style={{ ...card, padding: '14px', marginBottom: '10px', borderLeft: '3px solid ' + (group.warnings.size || group.missingDocs.size ? C.warning : C.accent) }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '10px', flexWrap: 'wrap', marginBottom: '10px' }}>
              <div>
                <b style={{ color: C.text, fontSize: '14px' }}>📁 {group.name}</b>
                <p style={{ color: C.textSec, margin: '3px 0', fontSize: '12px' }}>{Array.from(group.types).filter(Boolean).join(' · ') || 'Исполнитель'} · {group.rows.length} док. · {Array.from(group.projects).join(', ') || 'без объекта'}</p>
                {group.performer.inn && <p style={{ color: C.textMuted, margin: 0, fontSize: '11px' }}>ИНН: {group.performer.inn}{group.performer.bankName ? ' · ' + group.performer.bankName : ''}</p>}
              </div>
              <div style={{ textAlign: 'right' }}>
                {group.total > 0 && <b style={{ color: C.success, fontSize: '14px' }}>{Math.round(group.total).toLocaleString('ru-RU') + ' ₽ начислено'}</b>}
                {group.owe > 0 && <p style={{ color: C.danger, margin: '3px 0 0', fontSize: '11px', fontWeight: '700' }}>к выплате: {Math.round(group.owe).toLocaleString('ru-RU')} ₽</p>}
                {group.warnings.size > 0 && <p style={{ color: C.warning, margin: '3px 0 0', fontSize: '11px', fontWeight: '700' }}>⚠️ реквизиты не полные</p>}
                {group.missingDocs.size > 0 && <p style={{ color: C.warning, margin: '3px 0 0', fontSize: '11px', fontWeight: '700' }}>⚠️ закрывающие не полные</p>}
                {!group.warnings.size && !group.missingDocs.size && <p style={{ color: C.success, margin: '3px 0 0', fontSize: '11px', fontWeight: '700' }}>документы в порядке</p>}
              </div>
            </div>

            {(group.total > 0 || group.paid > 0) && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(120px,1fr))', gap: '8px', marginBottom: '8px' }}>
                <div style={{ padding: '8px', borderRadius: '8px', backgroundColor: C.bg, border: '1px solid ' + C.border }}><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 2px' }}>Начислено</p><b style={{ color: C.text, fontSize: '12px' }}>{Math.round(group.total).toLocaleString('ru-RU')} ₽</b></div>
                <div style={{ padding: '8px', borderRadius: '8px', backgroundColor: C.bg, border: '1px solid ' + C.border }}><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 2px' }}>Удержание 5%</p><b style={{ color: C.warning, fontSize: '12px' }}>{Math.round(group.retention).toLocaleString('ru-RU')} ₽</b></div>
                <div style={{ padding: '8px', borderRadius: '8px', backgroundColor: C.bg, border: '1px solid ' + C.border }}><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 2px' }}>Можно выплатить</p><b style={{ color: C.accent, fontSize: '12px' }}>{Math.round(group.payable).toLocaleString('ru-RU')} ₽</b></div>
                <div style={{ padding: '8px', borderRadius: '8px', backgroundColor: C.bg, border: '1px solid ' + C.border }}><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 2px' }}>Оплачено</p><b style={{ color: C.success, fontSize: '12px' }}>{Math.round(group.paid).toLocaleString('ru-RU')} ₽</b></div>
                <div style={{ padding: '8px', borderRadius: '8px', backgroundColor: C.bg, border: '1px solid ' + C.border }}><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 2px' }}>Остаток к выплате</p><b style={{ color: group.owe > 0 ? C.danger : C.success, fontSize: '12px' }}>{group.owe > 0 ? Math.round(group.owe).toLocaleString('ru-RU') + ' ₽' : 'закрыто'}</b></div>
              </div>
            )}

            {group.warnings.size > 0 && <div style={{ padding: '8px 10px', borderRadius: '8px', backgroundColor: C.warningLight, border: '1px solid ' + C.warningBorder, color: C.warning, fontSize: '11px', marginBottom: '8px' }}>{Array.from(group.warnings)[0]}</div>}
            {group.missingDocs.size > 0 && <div style={{ padding: '8px 10px', borderRadius: '8px', backgroundColor: C.warningLight, border: '1px solid ' + C.warningBorder, color: C.warning, fontSize: '11px', marginBottom: '8px' }}>Не хватает закрывающих: {Array.from(group.missingDocs).join(', ')}</div>}

            {group.rows.sort((left, right) => String(left.project || '').localeCompare(String(right.project || ''), 'ru')).map(row => {
              const isBrigade = row._kind === 'brigade';
              const items = isBrigade ? brigadeItems.filter(item => Number(item.contractId) === Number(row.id)) : [];
              return (
                <div key={row._rowKey} style={{ padding: '8px 0', borderTop: '1px solid ' + C.border, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <div>
                    <b style={{ color: C.text, fontSize: '12px' }}>{isBrigade ? 'Расчёт/договор бригады № ' : 'Договор № '}{row.contractNumber}</b>
                    <p style={{ color: C.textSec, margin: '2px 0', fontSize: '11px' }}>{(row.project || row.projectName || 'без объекта') + ' · ' + (row.contractType || row.contractorType || '')}{isBrigade && row.status ? ' · ' + row.status : ''}</p>
                    {(row.finance.accrued > 0 || row.finance.paid > 0) && <p style={{ color: C.textMuted, margin: 0, fontSize: '10px' }}>начислено {Math.round(row.finance.accrued).toLocaleString('ru-RU')} ₽ · удержание {Math.round(row.finance.retention).toLocaleString('ru-RU')} ₽ · можно выплатить {Math.round(row.finance.payable).toLocaleString('ru-RU')} ₽ · оплачено {Math.round(row.finance.paid).toLocaleString('ru-RU')} ₽ · остаток {Math.round(row.finance.owe).toLocaleString('ru-RU')} ₽</p>}
                    {row.finance.missingDocs?.length > 0 && <p style={{ color: C.warning, margin: '2px 0 0', fontSize: '10px', fontWeight: '700' }}>⚠️ Не хватает: {row.finance.missingDocs.join(', ')}</p>}
                    {!isBrigade && <p style={{ color: C.textMuted, margin: 0, fontSize: '10px' }}>{(row.startDate || '') + ' — ' + (row.endDate || '')}</p>}
                  </div>
                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <button onClick={() => openPreview(buildPreview(row.performer, row, items), 'Договор')} style={btnB}>
                      <Eye size={13} />
                      Просмотр
                    </button>
                    {!isBrigade && consents.find(consent => Number(consent.userId) === Number(row.masterId)) && <span style={renderBadge(C.success, C.successLight, C.successBorder)}>ПД ✅</span>}
                    {!isBrigade && <button onClick={() => removeContract(row.id)} style={{ ...btnR, padding: '4px 8px' }}><Trash2 size={11} /></button>}
                  </div>
                </div>
              );
            })}
          </div>
        ))
      )}
    </div>
  );
}

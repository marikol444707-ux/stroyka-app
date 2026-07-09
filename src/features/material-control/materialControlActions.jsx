import React from 'react';
import {
  canCreateInvoiceControlReviewTaskForUser,
  canCreateSupplyRequestFromControlForUser,
} from '../../utils/accessUtils';
import {
  invoiceControlMaterialName,
  invoiceControlNeedsReview,
  invoiceControlProjectName,
  invoiceControlReviewMarker,
  invoiceControlReviewReason,
  invoiceControlSupplyMarker,
  invoiceControlUnit,
  materialControlRowPackageKey,
  materialControlSupplyMarker,
  parseAiTaskPayload,
} from '../../utils/aiControlDescriptionUtils';
import {
  isActiveSupplyRequestStatus,
  materialControlRequestItems,
} from '../../utils/supplyUtils';

export const materialControlRowCanCreateSupply = (row, toNumber = Number) => (
  !!row?.name
  && toNumber(row.toBuy) > 0
  && toNumber(row.invalidPlanCount) <= 0
  && !row.reviewRequired
  && row.procurementEligible !== false
);

export function createMaterialControlActions({
  API,
  C,
  btnB,
  btnG,
  btnO,
  user,
  materialAliases,
  setMaterialAliases,
  supplyRequests,
  aiTaskByMarker,
  setAiTasks,
  materialNameLookupKey,
  materialAliasCandidates,
  canonicalMaterialMeta,
  materialNameKey,
  warehouseInvoiceEstimateControl,
  openAiTaskAction,
  updateAiTask,
  hasActiveEstimator,
  notify,
  refreshData,
  fmtMeasure,
  toNum,
  _normalizeUnit,
  isLeadership,
}) {
  const currentUser = user || {};
  const isLeadershipUser = typeof isLeadership === 'function' ? isLeadership() : Boolean(isLeadership);

  const createMaterialAlias = async (projectName, aliasName, canonicalName, canonicalUnit = '') => {
    if (!aliasName || !canonicalName) return null;
    const res = await fetch(API + '/material-aliases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectName, aliasName, canonicalName, canonicalUnit, source: 'manual' })
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      alert(data.detail || 'Не удалось сохранить сопоставление материала');
      return null;
    }
    const row = await res.json();
    setMaterialAliases(prev => [row, ...(prev || []).filter(a => !(
      a.active !== false &&
      (a.projectName || '') === (row.projectName || '') &&
      materialNameLookupKey(a.aliasName) === materialNameLookupKey(row.aliasName)
    ))]);
    return row;
  };

  const acceptMaterialAliasTask = async (task) => {
    const payload = parseAiTaskPayload(task);
    const suggestion = payload.aliasCandidate || null;
    if (!suggestion?.aliasName || !suggestion?.canonicalName) {
      openAiTaskAction(task);
      return;
    }
    const row = await createMaterialAlias(
      suggestion.projectName || payload.projectName || task.projectName || '',
      suggestion.aliasName,
      suggestion.canonicalName,
      suggestion.canonicalUnit || ''
    );
    if (row && task?.id) await updateAiTask(task.id, { status: 'Закрыто' });
  };

  const renderMaterialAliasControls = (projectName, row) => {
    if (!row?.isOutsideEstimate || !(isLeadershipUser || ['прораб', 'главный_инженер', 'сметчик', 'снабженец', 'кладовщик'].includes(currentUser.role))) return null;
    const candidates = materialAliasCandidates(projectName, row);
    if (!candidates.length) return null;
    const aliasName = row.aliases?.[0] || row.name;
    return (
      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '5px' }}>
        <span style={{ color: C.textMuted, fontSize: '10px' }}>Привязать к смете:</span>
        {candidates.map(c => (
          <button
            key={c.key}
            onClick={async e => { e.stopPropagation(); await createMaterialAlias(projectName, aliasName, c.name, c.unit); }}
            style={{ ...btnG, padding: '2px 6px', fontSize: '10px', borderRadius: '6px' }}
            title={'Считать «' + aliasName + '» как «' + c.name + '»'}
          >
            {c.name}
          </button>
        ))}
      </div>
    );
  };

  const materialControlSupplyRequestExists = (projectName, row) => {
    const marker = materialControlSupplyMarker(projectName, row);
    const rowKey = materialNameKey(row?.name);
    const unitKey = _normalizeUnit(row?.unit || '');
    const packageKey = materialControlRowPackageKey(row);
    return (supplyRequests || []).some(req => {
      if ((req.project || '') !== projectName || !isActiveSupplyRequestStatus(req.status)) return false;
      if (String(req.notes || '').includes(marker)) return true;
      return materialControlRequestItems(req).some(it =>
        materialNameKey(canonicalMaterialMeta(projectName, it.materialName, it.unit).name) === rowKey &&
        (!unitKey || _normalizeUnit(it.unit || '') === unitKey) &&
        materialControlRowPackageKey(it) === packageKey
      );
    });
  };

  const canCreateSupplyRequestFromControl = () => canCreateSupplyRequestFromControlForUser(user);

  const invoiceControlSupplyRequestExists = (inv, ctrl, item = {}) => {
    const projectName = invoiceControlProjectName(inv, ctrl);
    const marker = invoiceControlSupplyMarker(projectName, inv, ctrl, item);
    const rowKey = materialNameKey(invoiceControlMaterialName(ctrl, item));
    const unitKey = _normalizeUnit(invoiceControlUnit(ctrl, item) || '');
    const packageKey = materialControlRowPackageKey(ctrl || item);
    return (supplyRequests || []).some(req => {
      if ((req.project || '') !== projectName || !isActiveSupplyRequestStatus(req.status)) return false;
      if (String(req.notes || '').includes(marker)) return true;
      return materialControlRequestItems(req).some(it =>
        materialNameKey(canonicalMaterialMeta(projectName, it.materialName, it.unit).name) === rowKey &&
        (!unitKey || _normalizeUnit(it.unit || '') === unitKey) &&
        materialControlRowPackageKey(it) === packageKey
      );
    });
  };

  const createSupplyRequestFromMaterialControl = async (projectName, row) => {
    if (!projectName || !materialControlRowCanCreateSupply(row, toNum)) return;
    if (!canCreateSupplyRequestFromControl()) { alert('У вашей роли нет права создать заявку снабжения'); return; }
    if (materialControlSupplyRequestExists(projectName, row) && !window.confirm('По этой позиции уже есть активная заявка. Создать ещё одну?')) return;
    const qtyRaw = window.prompt('Количество к заявке:', String(Math.round(toNum(row.toBuy) * 1000) / 1000));
    if (qtyRaw === null) return;
    const qty = toNum(qtyRaw);
    if (qty <= 0) { alert('Количество должно быть больше 0'); return; }
    const unit = row.unit || 'шт';
    const rowPackage = row.workPackage || row.packageName || '';
    const marker = materialControlSupplyMarker(projectName, row);
    const planSourceCount = row.planSourceCount || (row.planDetails || []).length;
    const notes = [
      'Создано из контроля материалов: строка `Докупить`.',
      marker,
      'Объект: ' + projectName,
      rowPackage ? 'Пакет работ: ' + rowPackage : '',
      'Материал: ' + row.name,
      planSourceCount ? 'Сметных строк: ' + planSourceCount : '',
      (row.sections || []).length ? 'Разделы: ' + (row.sections || []).slice(0, 5).join('; ') : '',
      (row.workRefs || []).length ? 'Работы: ' + (row.workRefs || []).slice(0, 5).join('; ') : '',
      'План по смете: ' + fmtMeasure(row.planQty, unit),
      row.normPlanQty ? 'Норма по работам: ' + fmtMeasure(row.normPlanQty, unit) : '',
      row.controlPlanQty ? 'Контрольная потребность: ' + fmtMeasure(row.controlPlanQty, unit) : '',
      'Поставлено/перемещено: ' + fmtMeasure(row.supplied, unit),
      'В заявках и пути: ' + fmtMeasure(toNum(row.requested) + toNum(row.inTransit), unit),
      'Расчётная нехватка: ' + fmtMeasure(row.toBuy, unit),
    ].filter(Boolean).join('\n');
    const res = await fetch(API + '/supply-requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        materialName: row.name,
        quantity: qty,
        unit,
        workPackage: rowPackage,
        items: [{ materialName: row.name, quantity: qty, unit, workPackage: rowPackage }],
        project: projectName,
        createdBy: currentUser.name || '',
        date: new Date().toISOString().split('T')[0],
        notes,
        category: '',
        urgency: row.toBuy > toNum(row.controlPlanQty || row.planQty) * 0.25 ? 'срочная' : 'обычная',
        requestedByRole: currentUser.role || '',
        requestedById: currentUser.id || null,
        selectedSuppliers: [],
      })
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      alert(data.detail || 'Не удалось создать заявку снабжения');
      return;
    }
    notify('Создана заявка снабжения: ' + row.name + ' — ' + fmtMeasure(qty, unit) + '. Поставщикам не отправлена: откройте «Снабжение» и нажмите «Запросить КП».', 'supply');
    await refreshData();
  };

  const createBatchSupplyRequestFromMaterialControl = async (projectName, rows = []) => {
    if (!projectName) return;
    if (!canCreateSupplyRequestFromControl()) { alert('У вашей роли нет права создать заявку снабжения'); return; }
    const candidates = (rows || [])
      .filter(row => materialControlRowCanCreateSupply(row, toNum))
      .filter(row => !materialControlSupplyRequestExists(projectName, row))
      .slice(0, 120);
    if (!candidates.length) { notify('По выбранному фильтру нет новых позиций к закупке', 'supply'); return; }
    const groups = candidates.reduce((acc, row) => {
      const pkg = String(row.workPackage || row.packageName || 'Основная').trim() || 'Основная';
      if (!acc[pkg]) acc[pkg] = [];
      acc[pkg].push(row);
      return acc;
    }, {});
    const groupNames = Object.keys(groups);
    if (!window.confirm('Создать ' + groupNames.length + ' заявк. снабжения на ' + candidates.length + ' позиций по текущему фильтру?')) return;
    let createdItems = 0;
    for (const [requestPackage, groupRows] of Object.entries(groups)) {
      const items = groupRows.map(row => ({
        materialName: row.name,
        quantity: Math.round(toNum(row.toBuy) * 1000) / 1000,
        unit: row.unit || 'шт',
        workPackage: requestPackage
      }));
      const notes = [
        'Создано из контроля материалов: массовая заявка по текущему фильтру.',
        'Объект: ' + projectName,
        'Пакет работ: ' + requestPackage,
        'Позиций: ' + items.length,
        ...groupRows.map(row => materialControlSupplyMarker(projectName, row)),
        '',
        ...groupRows.slice(0, 40).map((row, idx) => {
          const unit = row.unit || 'шт';
          return (idx + 1) + '. ' + row.name + ' — докупить ' + fmtMeasure(row.toBuy, unit) + '; план ' + fmtMeasure(row.planQty, unit) + '; получено ' + fmtMeasure(row.supplied, unit);
        }),
        groupRows.length > 40 ? '...ещё ' + (groupRows.length - 40) + ' поз.' : ''
      ].filter(Boolean).join('\n');
      const res = await fetch(API + '/supply-requests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          materialName: items[0]?.materialName || 'Материалы по смете',
          quantity: items.length,
          unit: 'поз.',
          workPackage: requestPackage,
          items,
          project: projectName,
          createdBy: currentUser.name || '',
          date: new Date().toISOString().split('T')[0],
          notes,
          category: 'Материалы по смете',
          urgency: groupRows.some(row => toNum(row.toBuy) > toNum(row.controlPlanQty || row.planQty) * 0.25) ? 'срочная' : 'обычная',
          requestedByRole: currentUser.role || '',
          requestedById: currentUser.id || null,
          selectedSuppliers: [],
        })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        alert((data.detail || 'Не удалось создать массовую заявку снабжения') + ' · раздел ' + requestPackage);
        return;
      }
      createdItems += items.length;
    }
    notify('Создано заявок снабжения: ' + groupNames.length + ' · позиций ' + createdItems + '. Поставщикам не отправлено: в «Снабжении» выберите поставщиков через «Запросить КП».', 'supply');
    await refreshData();
  };

  const createSupplyRequestFromInvoiceControl = async (inv, ctrl, item = {}) => {
    const projectName = invoiceControlProjectName(inv, ctrl);
    const materialName = invoiceControlMaterialName(ctrl, item);
    const qty = toNum(ctrl?.shortageQty);
    const unit = invoiceControlUnit(ctrl, item);
    const rowPackage = ctrl.workPackage || ctrl.packageName || item.workPackage || item.work_package || '';
    if (!projectName || !materialName || qty <= 0) return;
    if (!canCreateSupplyRequestFromControl()) { alert('У вашей роли нет права создать заявку снабжения'); return; }
    if (invoiceControlSupplyRequestExists(inv, ctrl, item)) { notify('По этой позиции уже есть активная заявка снабжения', 'supply'); return; }
    const marker = invoiceControlSupplyMarker(projectName, inv, ctrl, item);
    const planSourceCount = ctrl.planSourceCount || (ctrl.planDetails || []).length;
    const notes = [
      'Создано из сметного контроля накладной: остаток к закупке после прихода.',
      marker,
      'Объект: ' + projectName,
      rowPackage ? 'Пакет работ: ' + rowPackage : '',
      'Накладная: №' + (inv?.number || inv?.id || '') + ' от ' + (inv?.date || ''),
      'Материал: ' + materialName,
      planSourceCount ? 'Сметных строк: ' + planSourceCount : '',
      (ctrl.sectionsList || []).length ? 'Разделы: ' + (ctrl.sectionsList || []).slice(0, 5).join('; ') : '',
      (ctrl.workRefs || []).length ? 'Работы: ' + (ctrl.workRefs || []).slice(0, 5).join('; ') : '',
      'План по смете: ' + (ctrl.planText || '—'),
      'До накладной: ' + (ctrl.beforeText || '—'),
      'По накладной: ' + (ctrl.incomingText || fmtMeasure(ctrl.incomingQty, unit)),
      'После накладной: ' + (ctrl.afterText || '—'),
      'Докупить: ' + fmtMeasure(qty, unit),
    ].filter(Boolean).join('\n');
    const res = await fetch(API + '/supply-requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        materialName,
        quantity: qty,
        unit,
        workPackage: rowPackage,
        items: [{ materialName, quantity: qty, unit, workPackage: rowPackage }],
        project: projectName,
        createdBy: currentUser.name || '',
        date: new Date().toISOString().split('T')[0],
        notes,
        category: '',
        urgency: qty > toNum(ctrl.planQty) * 0.25 ? 'срочная' : 'обычная',
        requestedByRole: currentUser.role || '',
        requestedById: currentUser.id || null,
        selectedSuppliers: [],
      })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      alert(data.detail || 'Не удалось создать заявку снабжения');
      return;
    }
    notify('Создана заявка из накладной: ' + materialName + ' — ' + fmtMeasure(qty, unit) + '. Поставщикам не отправлена: откройте «Снабжение» и нажмите «Запросить КП».', 'supply');
    await refreshData();
  };

  const canCreateInvoiceControlReviewTask = () => canCreateInvoiceControlReviewTaskForUser(user);

  const invoiceControlReviewTaskExists = (inv, ctrl, item = {}) => {
    const projectName = invoiceControlProjectName(inv, ctrl);
    return !!aiTaskByMarker(invoiceControlReviewMarker(projectName, inv, ctrl, item));
  };

  const createInvoiceControlReviewTask = async (inv, ctrl, item = {}) => {
    const projectName = invoiceControlProjectName(inv, ctrl);
    const materialName = invoiceControlMaterialName(ctrl, item);
    const unit = invoiceControlUnit(ctrl, item);
    if (!projectName || !materialName || !invoiceControlNeedsReview(ctrl)) return;
    if (!canCreateInvoiceControlReviewTask()) { alert('У вашей роли нет права создать задачу по сметному контролю'); return; }
    const marker = invoiceControlReviewMarker(projectName, inv, ctrl, item);
    const existingTask = aiTaskByMarker(marker);
    if (existingTask) { notify('Задача по этой строке уже есть в ИИ-контроле', 'ai'); return existingTask; }
    const reason = invoiceControlReviewReason(ctrl);
    const payload = {
      type: 'invoice_material_review',
      marker,
      dedupeKey: marker,
      projectName,
      invoiceId: inv?.id || null,
      invoiceNumber: inv?.number || '',
      invoiceDate: inv?.date || '',
      supplierName: inv?.supplierName || '',
      materialName,
      originalMaterialName: ctrl.name || item.name || '',
      status: ctrl.status || '',
      reason,
      quantity: toNum(ctrl.incomingQty || ctrl.quantity),
      unit,
      lineSum: toNum(ctrl.lineSum),
      planText: ctrl.planText || '',
      beforeText: ctrl.beforeText || '',
      afterText: ctrl.afterText || '',
      shortageText: ctrl.shortageText || '',
      overText: ctrl.overText || '',
      priceOverText: ctrl.priceOverText || '',
      planSourceCount: ctrl.planSourceCount || 0,
      sections: (ctrl.sectionsList || []).slice(0, 8),
      works: (ctrl.workRefs || []).slice(0, 8),
    };
    const description = [
      'Накладная создала сметное замечание по материалу.',
      'Причина: ' + reason + '.',
      'Объект: ' + projectName + '.',
      'Накладная: №' + (inv?.number || inv?.id || '') + ' от ' + (inv?.date || '') + ', поставщик: ' + (inv?.supplierName || '—') + '.',
      'Материал: ' + materialName + (ctrl.name && ctrl.name !== materialName ? ' (в накладной: ' + ctrl.name + ')' : '') + '.',
      payload.planSourceCount ? 'Сметная группа: ' + payload.planSourceCount + ' строк; разделы: ' + (payload.sections.join('; ') || '—') + '; работы: ' + (payload.works.join('; ') || '—') + '.' : '',
      'Количество по накладной: ' + fmtMeasure(payload.quantity, unit) + '. Сумма строки: ' + (payload.lineSum ? payload.lineSum.toLocaleString('ru-RU') + ' ₽' : '—') + '.',
      'План: ' + (ctrl.planText || '—') + '. До: ' + (ctrl.beforeText || '—') + '. После: ' + (ctrl.afterText || '—') + '.',
      'Докупить: ' + (ctrl.shortageText || '—') + '. Сверх: ' + (ctrl.overText || '—') + '. Цена: ' + (ctrl.invoicePriceText || '—') + ' / ' + (ctrl.planPriceText || '—') + '.',
      'Что сделать: сметчику/директору решить, привязать материал к смете через alias, оформить допматериал/допработу или подтвердить закупку вне сметы. После решения бухгалтер видит основание расхода.',
    ].filter(Boolean).join('\n');
    const res = await fetch(API + '/ai-tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        projectName,
        title: (ctrl.status === 'Вне сметы' ? 'Материал вне сметы: ' : 'Проверить материал накладной: ') + materialName,
        description,
        assignedRole: hasActiveEstimator() ? 'сметчик' : 'директор',
        status: 'Новое',
        actionLabel: 'Разобрать накладную',
        actionPayload: JSON.stringify(payload),
      })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      alert(data.detail || 'Не удалось создать задачу');
      return;
    }
    setAiTasks(prev => {
      const list = prev || [];
      if (data?.id && list.some(t => Number(t.id) === Number(data.id))) return list.map(t => Number(t.id) === Number(data.id) ? data : t);
      return [data, ...list];
    });
    notify('Создана задача по накладной: ' + materialName, 'ai');
    return data;
  };

  const createInvoiceControlReviewTasksForInvoice = async (inv) => {
    if (!inv || invoiceControlProjectName(inv) === '' || !canCreateInvoiceControlReviewTask()) return 0;
    const rows = warehouseInvoiceEstimateControl(inv).filter(invoiceControlNeedsReview);
    let created = 0;
    for (const ctrl of rows) {
      const materialName = invoiceControlMaterialName(ctrl, ctrl);
      if (!materialName || invoiceControlReviewTaskExists(inv, ctrl, ctrl)) continue;
      const task = await createInvoiceControlReviewTask(inv, ctrl, ctrl);
      if (task?.id) created += 1;
    }
    return created;
  };

  const renderInvoiceControlActions = (inv, ctrl, item = {}) => {
    if (!ctrl?.name) return null;
    const actions = [];
    if (toNum(ctrl.shortageQty) > 0 && canCreateSupplyRequestFromControl()) {
      const exists = invoiceControlSupplyRequestExists(inv, ctrl, item);
      actions.push(
        <button
          key="supply"
          onClick={e => { e.stopPropagation(); if (!exists) createSupplyRequestFromInvoiceControl(inv, ctrl, item); }}
          disabled={exists}
          style={{ ...(exists ? btnG : btnO), padding: '3px 7px', fontSize: '10px', opacity: exists ? 0.75 : 1 }}
          title={exists ? 'По этой позиции уже есть активная заявка' : 'Создать заявку снабжения на остаток к закупке'}
        >
          {exists ? 'Заявка есть' : 'Заявка'}
        </button>
      );
    }
    if (invoiceControlNeedsReview(ctrl) && canCreateInvoiceControlReviewTask()) {
      const exists = invoiceControlReviewTaskExists(inv, ctrl, item);
      actions.push(
        <button
          key="review"
          onClick={e => { e.stopPropagation(); if (!exists) createInvoiceControlReviewTask(inv, ctrl, item); }}
          disabled={exists}
          style={{ ...(exists ? btnG : btnB), padding: '3px 7px', fontSize: '10px', opacity: exists ? 0.75 : 1 }}
          title={exists ? 'Задача уже есть в ИИ-контроле' : 'Создать задачу сметчику/директору на разбор строки'}
        >
          {exists ? 'Задача есть' : 'Разбор'}
        </button>
      );
    }
    if (!actions.length) return null;
    return <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>{actions}</div>;
  };

  const renderMaterialSupplyAction = (projectName, row) => {
    if (!materialControlRowCanCreateSupply(row, toNum) || !canCreateSupplyRequestFromControl()) return null;
    const exists = materialControlSupplyRequestExists(projectName, row);
    return (
      <button
        onClick={e => { e.stopPropagation(); if (!exists) createSupplyRequestFromMaterialControl(projectName, row); }}
        disabled={exists}
        style={{ ...(exists ? btnG : btnO), padding: '3px 7px', fontSize: '10px', marginTop: '5px', opacity: exists ? 0.75 : 1 }}
        title={exists ? 'По этой позиции уже есть активная заявка' : 'Создать заявку снабжения на недостачу'}
      >
        {exists ? 'Заявка есть' : 'Заявка'}
      </button>
    );
  };

  return {
    acceptMaterialAliasTask,
    canCreateInvoiceControlReviewTask,
    canCreateSupplyRequestFromControl,
    createBatchSupplyRequestFromMaterialControl,
    createInvoiceControlReviewTask,
    createInvoiceControlReviewTasksForInvoice,
    createMaterialAlias,
    createSupplyRequestFromInvoiceControl,
    createSupplyRequestFromMaterialControl,
    invoiceControlReviewTaskExists,
    invoiceControlSupplyRequestExists,
    materialControlSupplyRequestExists,
    renderInvoiceControlActions,
    renderMaterialAliasControls,
    renderMaterialSupplyAction,
  };
}

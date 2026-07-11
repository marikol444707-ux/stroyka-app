import { resolveEstimatePackage } from '../../utils/estimatePackage';
import {
  activeEstimateFromList,
  normalizeImportedEstimateItem,
} from '../../utils/estimateUtils';
import { createEstimateChatActions } from './estimateChatActions';

export function createEstimatePageActions({
  API,
  ROLE_LABELS,
  applyEstimateActivationState,
  aiMessages,
  autoReconcileEstimateChanges,
  brigadeContracts,
  buildEstimateDiffContent,
  contracts,
  createEstimateReconciliation,
  enrichEstimateMeasurementBasis,
  estimateDiffBaseFor,
  estimateItemMaterialSum,
  estimateItemTotal,
  estimateItemTypeMeta,
  estimateItemWorkSum,
  estimateChatInput,
  estimateChatLoading,
  estimateChatMessages,
  estimateChatRequestRef,
  estimateMeasurementBasisMeta,
  estimateMeasurementBasisOf,
  estimateQualityRows,
  executionPriceFillPercent,
  exportToExcel,
  estimatesList,
  isGlobalEstimateTemplate,
  isLeadership,
  isEstimateWorkItem,
  materials,
  newEstimate,
  nextEstimateVersionFor,
  normalizeEstimateImportSections,
  normalizeEstimateItemType,
  persistEstimate,
  projects,
  queueEstimateDiffReviewTask,
  queueEstimateNormReviewTask,
  queueEstimateQualityReviewTask,
  readApiResult,
  sameEstimateGroup,
  selectedEstimate,
  setAiInput,
  setAiLoading,
  setAiMessages,
  setDistributeAssignments,
  setDistributeBrigades,
  setEstimateChatInput,
  setEstimateChatLoading,
  setEstimateChatMessages,
  setEstimateVersions,
  setEstimatesList,
  setEstimatesTab,
  setExecutionPriceFillPercent,
  setImportValidating,
  setImportValidationWarnings,
  setSelectedEstimate,
  setSelectedVersionsToCompare,
  setShowAiChat,
  setShowDistribute,
  setShowEstimateChat,
  setShowVersionHistory,
  setShowWorkAssignment,
  showPreview,
  staff,
  toNum,
  user,
  fetchFn = fetch,
  alertFn = window.alert,
  confirmFn = window.confirm,
}) {
  const currentUser = user || {};
  const {
    clearEstimateChatHistory,
    handleOpenSelectedEstimateChat,
    sendEstimateChatMessage,
  } = createEstimateChatActions({
    API,
    alertFn,
    estimateChatInput,
    estimateChatLoading,
    estimateChatMessages,
    estimateChatRequestRef,
    fetchFn,
    readApiResult,
    selectedEstimate,
    setEstimateChatInput,
    setEstimateChatLoading,
    setEstimateChatMessages,
    setShowEstimateChat,
  });
  const isLeadershipUser = typeof isLeadership === 'function' ? isLeadership() : Boolean(isLeadership);
  const sendAiAssistantMessage = async (rawMessage, fallbackText = 'Ошибка соединения с ИИ.') => {
    const msg = String(rawMessage || '').trim();
    if (!msg) return;
    setAiInput('');
    setAiMessages(prev => [...prev, {role: 'user', content: msg}]);
    setAiLoading(true);
    try {
      const context = 'Данные системы: проектов ' + projects.length + ', сотрудников ' + staff.length + ', материалов на складе ' + (materials || []).length + ' позиций, договоров ' + contracts.length + '. Текущий пользователь: ' + (currentUser.name || '') + ' (' + (ROLE_LABELS[currentUser.role] || currentUser.role || '') + ').';
      const res = await fetchFn(API + '/ai-chat', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({messages: [...aiMessages, {role: 'user', content: context + ' Вопрос: ' + msg}]})});
      const data = await res.json();
      setAiMessages(prev => [...prev, {role: 'assistant', content: data.response || data.error || 'Ошибка ответа'}]);
    } catch (err) {
      setAiMessages(prev => [...prev, {role: 'assistant', content: fallbackText}]);
    }
    setAiLoading(false);
  };

  const handleEstimateImportFile = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (!newEstimate.projectId) {
      alertFn('Сначала выберите проект — без привязки смета не сохранится');
      e.target.value = '';
      return;
    }
    const fd = new FormData();
    fd.append('file', file);
    try {
      const data = await readApiResult(await fetchFn(API + '/parse-smeta', {method: 'POST', body: fd}));
      if (data.error) throw new Error(data.error);
      if (!Array.isArray(data.items) || !data.items.length) {
        throw new Error('В файле не найдены рабочие строки сметы. Если это ССР/сводный расчёт, загрузите его как документ, а рабочую смету импортируйте из ЛСР или СК.');
      }
      const sections = {};
      (data.items || []).forEach(item => {
        if (!sections[item.section]) {
          sections[item.section] = {id: Date.now() + Math.random(), name: item.section, items: []};
        }
        const importedItem = normalizeImportedEstimateItem({
          id: Date.now() + Math.random(),
          name: item.name,
          unit: item.unit,
          quantity: item.quantity,
          rawUnit: item.rawUnit || '',
          rawQuantity: item.rawQuantity,
          unitFactor: item.unitFactor || 1,
          quantityBase: item.quantityBase,
          quantityCoefficient: item.quantityCoefficient,
          quantityFinal: item.quantityFinal,
          baseUnitPrice: item.baseUnitPrice,
          costCoefficient: item.costCoefficient,
          baseTotal: item.baseTotal,
          costIndex: item.costIndex,
          currentTotal: item.currentTotal,
          lineTotalSource: item.lineTotalSource,
          total: item.total,
          sum: item.sum,
          amount: item.amount,
          lineTotal: item.lineTotal,
          totalSum: item.totalSum,
          totalWork: item.totalWork,
          totalMaterial: item.totalMaterial,
          priceWork: item.priceWork,
          priceMaterial: item.priceMaterial,
          sourceCode: item.sourceCode || item.obosn || '',
          workKey: item.workKey || '',
          workName: item.workName || '',
          workSourceCode: item.workSourceCode || '',
          parentWorkKey: item.parentWorkKey || '',
          parentWorkName: item.parentWorkName || '',
          parentWorkSourceCode: item.parentWorkSourceCode || '',
          resourceRole: item.resourceRole || '',
          isImported: true,
          itemType: item.type || '',
        }, item.section);
        sections[item.section].items.push(importedItem);
      });

      const projName = newEstimate.projectName || ((projects || []).find(p => p.id === Number(newEstimate.projectId))?.name || '');
      const fileName = file.name.replace('.xlsx', '').replace('.xls', '');
      const resolvedWorkPackage = resolveEstimatePackage(newEstimate.workPackage, fileName, newEstimate.name);
      const estimateStatus = isLeadershipUser ? (newEstimate.status || 'Активная') : 'Черновик';
      const estDraft = {
        projectId: newEstimate.projectId,
        projectName: projName,
        smetaType: newEstimate.smetaType || 'Заказчик',
        workPackage: resolvedWorkPackage,
      };
      const est = {
        id: Date.now(),
        name: fileName || newEstimate.name || 'Смета — ' + projName,
        projectId: newEstimate.projectId,
        projectName: projName,
        version: newEstimate.version || nextEstimateVersionFor(estDraft),
        smetaType: newEstimate.smetaType || 'Заказчик',
        workPackage: resolvedWorkPackage,
        status: estimateStatus,
        sections: enrichEstimateMeasurementBasis(Object.values(sections)),
      };
      const saved = await readApiResult(await fetchFn(API + '/estimates', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(est),
      }));
      if (!saved?.id) throw new Error('Сервер не вернул id сохранённой сметы');
      const estWithId = {...est, id: saved.id, smetaType: newEstimate.smetaType || 'Заказчик', workPackage: resolvedWorkPackage, status: estimateStatus};
      const diffBase = activeEstimateFromList((estimatesList || []).filter(e => (
        estWithId.status === 'Активная' &&
        !isGlobalEstimateTemplate(e) &&
        sameEstimateGroup(e, estWithId) &&
        e.status === 'Активная'
      )));
      const nextEstimates = applyEstimateActivationState([...(estimatesList || []), estWithId], estWithId);
      setEstimatesList(nextEstimates);
      setSelectedEstimate(estWithId);
      setEstimatesTab('list');
      if (diffBase) {
        await queueEstimateDiffReviewTask(diffBase, estWithId, 'Импорт сметы');
        await autoReconcileEstimateChanges(diffBase, estWithId, 'Импорт сметы');
        await createEstimateReconciliation(diffBase, estWithId, {silent: true});
      }
      await queueEstimateQualityReviewTask(estWithId, 'Импорт сметы');
      await queueEstimateNormReviewTask(estWithId, 'Импорт сметы', nextEstimates);
      const qualityWarnings = estimateQualityRows(estWithId).map(row => ({
        type: 'качество',
        where: (row.sectionName || '') + ' / ' + (row.itemName || ''),
        message: row.status + ': ' + row.message,
        severity: row.severity === 'critical' ? 'критично' : row.severity === 'info' ? 'совет' : 'внимание',
      }));
      setImportValidating(true);
      setImportValidationWarnings(qualityWarnings);
      try {
        const items = Object.values(sections).flatMap(s => (s.items || []).map(i => ({
          section: s.name,
          name: i.name,
          unit: i.unit,
          qty: Number(i.quantity || 0),
        })));
        const valPrompt = 'Проверь смету "' + est.name + '" на типовые проблемы при импорте из Гранд Сметы. Позиции:\n' + JSON.stringify(items, null, 1) + '\n\nИЩИ:\n- Забытые сопутствующие работы (например штукатурка без грунтовки)\n- Возможные дубликаты позиций\n- Подозрительно большие или маленькие объёмы\n- Странные единицы измерения\n\nОТВЕТЬ СТРОГО JSON:\n{"warnings":[{"type":"забыто|дубль|объём|единица|другое","where":"раздел или позиция","message":"что не так","severity":"критично|внимание|совет"}]}\nЕсли всё хорошо — пиши {"warnings":[]}. Только JSON.';
        const r = await fetchFn(API + '/ai-chat', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({messages: [{role: 'user', content: valPrompt}], jsonOnly: true}),
        });
        const d = await r.json();
        const raw = (d.response || '').trim();
        const clean = raw.replace(/^```(?:json)?/i, '').replace(/```$/, '').trim();
        const s = clean.indexOf('{');
        const en = clean.lastIndexOf('}');
        if (s >= 0 && en > s) {
          const p = JSON.parse(clean.slice(s, en + 1));
          if (Array.isArray(p.warnings)) setImportValidationWarnings([...qualityWarnings, ...p.warnings]);
        }
      } catch (err) {}
      setImportValidating(false);
      const meta = data.meta || {};
      const mismatchText = meta.totalMismatch
        ? '\n\nВнимание: итог файла ' + Number(meta.declaredTotal || 0).toLocaleString('ru-RU') + ' ₽, сумма разобранных строк ' + Number(meta.parsedTotal || 0).toLocaleString('ru-RU') + ' ₽. Строки НЕ умножались общим коэффициентом, чтобы не ломать оплату мастерам. Нужно разобрать итоговый блок/индексы работ и материалов отдельно.'
        : '';
      alertFn('Импортировано ' + data.count + ' позиций! ИИ проверяет смету в фоне — результат появится сверху.' + mismatchText);
    } catch (err) {
      alertFn('Ошибка импорта: ' + (err.message || err));
    } finally {
      e.target.value = '';
    }
  };

  const handleEstimateAiAnalysis = async () => {
    let plMap = {};
    const proj = projects.find(p => p.id === Number(selectedEstimate.projectId));
    if (proj && proj.pricelistId) {
      try {
        const pli = await fetchFn(API + '/pricelists/' + proj.pricelistId + '/items').then(r => r.json());
        (pli || []).forEach(p => {
          const k = (p.name || '').toLowerCase().trim();
          if (k) plMap[k] = Number(p.price || 0);
        });
      } catch (e) {}
    }
    const allItems = (selectedEstimate.sections || []).flatMap(s => (s.items || []).map(i => {
      const work = Number(i.priceWork || 0);
      const mat = Number(i.priceMaterial || 0);
      const qty = Number(i.quantity || 0);
      const sum = estimateItemTotal(i);
      let plPrice = 0;
      let diff = 0;
      if (Object.keys(plMap).length) {
        const k = (i.name || '').toLowerCase().trim();
        plPrice = plMap[k] || 0;
        if (!plPrice) {
          const f = Object.keys(plMap).find(pk => pk.length > 5 && (k.includes(pk) || pk.includes(k)));
          if (f) plPrice = plMap[f];
        }
        const unitPrice = qty > 0 ? sum / qty : (work + mat);
        if (plPrice && unitPrice > 0) diff = Math.round((unitPrice / plPrice - 1) * 100);
      }
      return {section: s.name, name: i.name, unit: i.unit, qty, work, mat, sum, plPrice, diff};
    }));
    const total = allItems.reduce((s, i) => s + i.sum, 0);
    const top5 = [...allItems].sort((a, b) => b.sum - a.sum).slice(0, 5);
    const bySection = {};
    allItems.forEach(i => { bySection[i.section] = (bySection[i.section] || 0) + i.sum; });
    const shares = Object.entries(bySection).map(([n, s]) => ({name: n, sum: s, share: total > 0 ? Math.round(s / total * 100) : 0})).sort((a, b) => b.sum - a.sum);
    const fmt = n => Number(n || 0).toLocaleString('ru-RU');
    const prompt = 'Ты эксперт по строительным сметам. Анализируешь смету "' + selectedEstimate.name + '" на ' + fmt(total) + ' ₽.\n\n'
      + 'РАЗДЕЛЫ (' + shares.length + '):\n' + shares.map(s => '• ' + s.name + ': ' + fmt(s.sum) + ' ₽ (' + s.share + '%)').join('\n') + '\n\n'
      + 'ТОП-5 ДОРОГИХ ПОЗИЦИЙ:\n' + top5.map((i, n) => (n + 1) + '. [' + i.section + '] ' + i.name + ': ' + i.qty + ' ' + i.unit + ', ' + fmt(i.sum) + ' ₽ (' + (total > 0 ? Math.round(i.sum / total * 100) : 0) + '%)' + (i.plPrice ? ', прайс ' + fmt(i.plPrice) + '₽ → ' + (i.diff > 0 ? '+' : '') + i.diff + '%' : '')).join('\n') + '\n\n'
      + 'ВСЕ ПОЗИЦИИ:\n' + allItems.map(i => '- [' + i.section + '] ' + i.name + ' | ' + i.qty + ' ' + i.unit + ' | ' + fmt(i.sum) + '₽' + (i.plPrice ? ' (прайс ' + fmt(i.plPrice) + '₽, ' + (i.diff > 0 ? '+' : '') + i.diff + '%)' : '')).join('\n') + '\n\n'
      + 'ОТВЕТЬ СТРОГО В ФОРМАТЕ JSON (без markdown, без ```, только сырой JSON):\n'
      + '{\n'
      + '  "top": [{"name":"название позиции","section":"раздел","sum":число,"share":процент,"why":"почему дорого"}],\n'
      + '  "sections": [{"name":"полное название раздела","sum":число,"share":процент,"summary":"что в разделе","note":"на что обратить внимание или норма"}],\n'
      + '  "risks": [{"where":"конкретная позиция или раздел","problem":"что не так","impact":число_или_0}],\n'
      + '  "actions": [{"do":"конкретное действие","target":"что/где менять","savings":число_или_0}]\n'
      + '}\n\n'
      + 'ПРАВИЛА:\n'
      + '• top — 5 позиций из ТОП-5 выше, цифры из данных точно.\n'
      + '• sections — ОБЯЗАТЕЛЬНО по КАЖДОМУ из ' + shares.length + ' разделов (не пропускай ни один). Для каждого: summary одной фразой (например "штукатурка, шпатлёвка, окраска"), note — что важного увидел (отклонения, странные объёмы) или просто "норма".\n'
      + '• risks — позиции с отклонением от прайса >20%, странные объёмы, возможные дубли, забытые сопутствующие работы. Минимум 0, максимум 7. Если ничего — [].\n'
      + '• actions — 3-6 КОНКРЕТНЫХ шагов с привязкой к позиции или разделу. НЕ "найти поставщиков", а "заменить X на Y в позиции Z". savings — оценка экономии в рублях или 0.\n'
      + '• Все числа — без пробелов, без "руб", только цифры. 1260000 а не "1 260 000 руб".\n'
      + '• Только валидный JSON. Никакого текста до или после.';
    setShowAiChat(true);
    setAiMessages([{role: 'user', content: 'Анализ сметы: ' + selectedEstimate.name}]);
    setAiLoading(true);
    try {
      const res = await fetchFn(API + '/ai-chat', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({messages: [{role: 'user', content: prompt}], jsonOnly: true})});
      const data = await res.json();
      const raw = (data.response || data.error || '').trim();
      let parsed = null;
      try {
        const clean = raw.replace(/^```(?:json)?/i, '').replace(/```$/, '').trim();
        const start = clean.indexOf('{');
        const end = clean.lastIndexOf('}');
        if (start >= 0 && end > start) parsed = JSON.parse(clean.slice(start, end + 1));
      } catch (e) {}
      let out;
      if (parsed && (parsed.top || parsed.sections || parsed.risks || parsed.actions)) {
        const lines = [];
        lines.push('💰 Общая сумма: ' + fmt(total) + ' ₽');
        lines.push('');
        if (Array.isArray(parsed.top) && parsed.top.length) {
          lines.push('🔝 ТОП ДОРОГИХ ПОЗИЦИЙ');
          parsed.top.forEach((t, n) => {
            lines.push((n + 1) + '. ' + (t.name || '?') + (t.section ? ' [' + t.section + ']' : ''));
            lines.push('   ' + fmt(t.sum) + ' ₽' + (t.share ? ' (' + t.share + '%)' : '') + (t.why ? ' — ' + t.why : ''));
          });
          lines.push('');
        }
        if (Array.isArray(parsed.sections) && parsed.sections.length) {
          lines.push('📊 ПО РАЗДЕЛАМ');
          parsed.sections.forEach((s, n) => {
            lines.push((n + 1) + '. ' + (s.name || '?') + ' — ' + fmt(s.sum) + ' ₽' + (s.share ? ' (' + s.share + '%)' : ''));
            if (s.summary) lines.push('   ' + s.summary);
            if (s.note && s.note.toLowerCase() !== 'норма') lines.push('   ⚡ ' + s.note);
          });
          lines.push('');
        }
        if (Array.isArray(parsed.risks) && parsed.risks.length) {
          lines.push('⚠️ РИСКИ');
          parsed.risks.forEach((r, n) => {
            lines.push((n + 1) + '. ' + (r.where || '?') + ': ' + (r.problem || '') + (r.impact ? ' (~' + fmt(r.impact) + ' ₽)' : ''));
          });
          lines.push('');
        } else {
          lines.push('✅ Явных рисков не выявлено');
          lines.push('');
        }
        if (Array.isArray(parsed.actions) && parsed.actions.length) {
          lines.push('🎯 ЧТО СДЕЛАТЬ');
          parsed.actions.forEach((a, n) => {
            lines.push((n + 1) + '. ' + (a.do || '?') + (a.target ? ' → ' + a.target : '') + (a.savings ? ' (экономия ~' + fmt(a.savings) + ' ₽)' : ''));
          });
        }
        out = lines.join('\n');
      } else {
        out = raw || 'Ошибка: пустой ответ от ИИ';
      }
      setAiMessages([{role: 'user', content: 'Анализ сметы: ' + selectedEstimate.name}, {role: 'assistant', content: out}]);
    } catch (e) {
      setAiMessages(prev => [...prev, {role: 'assistant', content: 'Ошибка соединения'}]);
    }
    setAiLoading(false);
  };

  const handleDetectEstimateHiddenWorks = async () => {
    if (!selectedEstimate || !selectedEstimate.id) return;
    if (!confirmFn('ИИ пройдёт по позициям сметы и отметит 🔒 работы, по которым нужно подготовить АОСР. Уже отмеченные вручную останутся. Продолжить?')) return;
    try {
      const res = await fetchFn(API + '/estimates/' + selectedEstimate.id + '/ai-detect-hidden', {method: 'POST'});
      const data = await res.json();
      if (!res.ok || !data.ok) {
        alertFn('Не удалось: ' + (data.detail || 'ошибка'));
        return;
      }
      const updated = {...selectedEstimate, sections: data.sections};
      setSelectedEstimate(updated);
      setEstimatesList(prev => prev.map(e => e.id === updated.id ? updated : e));
      alertFn('🔒 Отмечено работ для АОСР: ' + data.count + (data.method === 'ai' ? ' (определил ИИ)' : ' (по ключевым словам — ИИ был недоступен)'));
    } catch (e) {
      alertFn('Ошибка соединения');
    }
  };

  const handlePreviewSelectedEstimate = () => {
    if (!selectedEstimate) return;
    const total = (selectedEstimate.sections || []).flatMap(s => s.items || []).reduce((sum, i) => sum + estimateItemTotal(i), 0);
    const html = '<h2>' + selectedEstimate.name + '</h2><table><tr><th>N</th><th>Тип</th><th>Основание</th><th>Наименование</th><th>Ед.</th><th>Кол-во</th><th>Цена работ</th><th>Материалы</th><th>Сумма</th></tr>' + (selectedEstimate.sections || []).flatMap(s => [`<tr><td colspan="9"><b>${s.name}</b></td></tr>`, ...(s.items || []).map((it, i) => { const meta = estimateItemTypeMeta(normalizeEstimateItemType(it, s.name)); const basis = estimateMeasurementBasisMeta(estimateMeasurementBasisOf(it, s.name)); return `<tr><td>${i + 1}</td><td>${meta.label}</td><td>${basis.label}</td><td>${it.name}</td><td>${it.unit}</td><td>${it.quantity}</td><td>${Number(it.priceWork || 0).toLocaleString()}</td><td>${Math.round(estimateItemMaterialSum(it)).toLocaleString()}</td><td>${Math.round(estimateItemTotal(it)).toLocaleString()}</td></tr>`; })]).join('') + '<tr><td colspan="8"><b>ИТОГО:</b></td><td><b>' + Math.round(total).toLocaleString() + ' ₽</b></td></tr></table>';
    showPreview(html, 'Смета');
  };

  const handleShowSelectedEstimateDiff = () => {
    const base = estimateDiffBaseFor(selectedEstimate);
    if (base) showPreview(buildEstimateDiffContent(base, selectedEstimate), 'Сопоставительная ведомость');
  };

  const handleExportSelectedEstimate = () => {
    if (!selectedEstimate) return;
    exportToExcel((selectedEstimate.sections || []).flatMap(s => (s.items || []).map(i => ({Раздел: s.name, Тип: estimateItemTypeMeta(normalizeEstimateItemType(i, s.name)).label, Основание: estimateMeasurementBasisMeta(estimateMeasurementBasisOf(i, s.name)).label, Наименование: i.name, Единица: i.unit, Количество: i.quantity, 'Цена работ': i.priceWork, 'Цена мат.': i.priceMaterial, Сумма: estimateItemTotal(i)}))), selectedEstimate.name);
  };

  const selectedEstimateExecutionPriceStats = () => {
    if (!selectedEstimate) return {workRows: 0, pricedRows: 0, emptyRows: 0};
    let workRows = 0;
    let pricedRows = 0;
    (selectedEstimate.sections || []).forEach(section => {
      (section.items || []).forEach(item => {
        if (!isEstimateWorkItem(item, section.name)) return;
        workRows += 1;
        if (toNum(item.executionPricePerUnit || item.internalPricePerUnit || item.masterPricePerUnit) > 0) pricedRows += 1;
      });
    });
    return {workRows, pricedRows, emptyRows: Math.max(0, workRows - pricedRows)};
  };

  const estimateWorkCustomerUnitPrice = (item, sectionName) => {
    const qty = toNum(item.quantity);
    const lineWorkSum = estimateItemWorkSum({...item, sectionName});
    if (qty > 0 && lineWorkSum > 0) return lineWorkSum / qty;
    return toNum(item.priceWork || item.price || item.pricePerUnit);
  };

  const fillSelectedEstimateExecutionPrices = async (overwrite = false) => {
    if (!selectedEstimate?.id) return;
    const percent = Math.max(1, Math.min(100, toNum(executionPriceFillPercent) || 50));
    setExecutionPriceFillPercent(String(percent));
    let changed = 0;
    const sections = (selectedEstimate.sections || []).map(section => ({
      ...section,
      items: (section.items || []).map(item => {
        if (!isEstimateWorkItem(item, section.name)) return item;
        const hasPrice = toNum(item.executionPricePerUnit || item.internalPricePerUnit || item.masterPricePerUnit) > 0;
        if (hasPrice && !overwrite) return item;
        const customerUnitPrice = estimateWorkCustomerUnitPrice(item, section.name);
        if (customerUnitPrice <= 0) return item;
        changed += 1;
        return {
          ...item,
          executionPricePerUnit: Math.round(customerUnitPrice * percent) / 100,
          executionPriceMode: 'percent_' + percent,
          executionPricePercent: percent,
        };
      }),
    }));
    if (!changed) {
      alertFn('Нет строк для заполнения: внутренние цены уже проставлены или нет цены заказчика.');
      return;
    }
    const updated = {...selectedEstimate, sections};
    setSelectedEstimate(updated);
    setEstimatesList(prev => prev.map(e => e.id === updated.id ? updated : e));
    await persistEstimate(updated);
    alertFn('Заполнено внутренних цен исполнителям: ' + changed + '. Каждую строку можно поправить вручную.');
  };

  const handleToggleSelectedEstimateTemplate = async () => {
    if (!selectedEstimate?.id) return;
    const res = await fetchFn(API + '/estimates/' + selectedEstimate.id + '/toggle-template', {method: 'PUT'});
    const data = await res.json();
    setEstimatesList(prev => prev.map(e => e.id === selectedEstimate.id ? {...e, isTemplate: data.isTemplate} : e));
    setSelectedEstimate(prev => ({...prev, isTemplate: data.isTemplate}));
    alertFn(data.isTemplate ? 'Смета помечена как шаблон — её можно использовать при создании новых смет' : 'Смета больше не шаблон');
  };

  const handleOpenSelectedEstimateHistory = async () => {
    if (!selectedEstimate?.id) return;
    try {
      const versions = await fetchFn(API + '/estimates/' + selectedEstimate.id + '/versions').then(r => r.json());
      setEstimateVersions(Array.isArray(versions) ? versions : []);
      setSelectedVersionsToCompare([]);
      setShowVersionHistory(true);
    } catch (e) {
      alertFn('Не удалось загрузить историю');
    }
  };

  const handleNormalizeSelectedEstimateImport = async () => {
    if (!selectedEstimate?.id) return;
    const normalizedSections = normalizeEstimateImportSections(selectedEstimate.sections || []);
    const updated = {...selectedEstimate, sections: normalizedSections};
    setSelectedEstimate(updated);
    setEstimatesList(prev => prev.map(e => e.id === updated.id ? updated : e));
    await persistEstimate(updated);
    const qualityWarnings = estimateQualityRows(updated).map(row => ({
      type: 'качество',
      where: (row.sectionName || '') + ' / ' + (row.itemName || ''),
      message: row.status + ': ' + row.message,
      severity: row.severity === 'critical' ? 'критично' : row.severity === 'info' ? 'совет' : 'внимание',
    }));
    setImportValidationWarnings(qualityWarnings);
    await queueEstimateQualityReviewTask(updated, 'Нормализация импорта сметы');
    alertFn('Импорт нормализован. Осталось замечаний: ' + qualityWarnings.length);
  };

  const handleOpenEstimateDistribute = () => {
    if (!selectedEstimate) return;
    setDistributeAssignments({});
    const existing = brigadeContracts.filter(bc => bc.projectName === selectedEstimate.projectName);
    setDistributeBrigades(existing.length ? existing.map(bc => ({name: bc.brigadeName, contractorType: bc.contractorType, pricelistId: bc.pricelistId || ''})) : []);
    setShowDistribute(true);
  };

  const handleOpenWorkAssignment = () => {
    if (!selectedEstimate) return;
    setShowWorkAssignment(true);
  };

  return {
    clearEstimateChatHistory,
    fillSelectedEstimateExecutionPrices,
    handleDetectEstimateHiddenWorks,
    handleEstimateAiAnalysis,
    handleEstimateImportFile,
    handleExportSelectedEstimate,
    handleNormalizeSelectedEstimateImport,
    handleOpenEstimateDistribute,
    handleOpenSelectedEstimateChat,
    handleOpenSelectedEstimateHistory,
    handleOpenWorkAssignment,
    handlePreviewSelectedEstimate,
    handleShowSelectedEstimateDiff,
    handleToggleSelectedEstimateTemplate,
    selectedEstimateExecutionPriceStats,
    sendAiAssistantMessage,
    sendEstimateChatMessage,
  };
}

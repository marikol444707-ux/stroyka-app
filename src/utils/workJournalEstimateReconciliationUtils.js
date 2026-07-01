import {
  estimateDiffTextKey,
  estimateItemTotal,
  estimatePackage,
  estimateSectionsOf,
  isEstimateWorkItem,
  workJournalReconcileNameScore,
} from './estimateUtils';
import { _normalizeUnit, normalizeMeasure, toNum } from './measureUtils';

export const workJournalEstimateRowsFor = (project, { activeEstimates = [], workJournal = [] } = {}) => {
  if (!project) return [];
  const estimateRows = [];

  (activeEstimates || []).forEach(est => estimateSectionsOf(est).forEach((section, sectionIdx) => (section.items || []).forEach((item, itemIdx) => {
    if (!isEstimateWorkItem(item, section.name)) return;
    const plan = normalizeMeasure(item.quantity, item.unit);
    const done = normalizeMeasure(item.doneQuantity, item.unit);
    const planQty = toNum(plan.qty);
    const unit = plan.unit || item.unit || '';
    const unitKey = _normalizeUnit(unit);
    const total = estimateItemTotal(item);
    estimateRows.push({
      key: [est.id, sectionIdx, itemIdx].join(':'),
      estimateId: est.id,
      estimateName: est.name || 'Смета',
      packageName: estimatePackage(est),
      sectionName: section.name || 'Без раздела',
      itemName: item.name || '',
      planQty,
      doneQty: toNum(done.qty),
      unit,
      unitKey,
      total,
      unitPrice: planQty > 0 ? total / planQty : 0,
    });
  })));

  const workRows = (workJournal || [])
    .filter(w => w.project === project.name && (w.status || '') !== 'Отклонено')
    .map((w, idx) => {
      const normalized = normalizeMeasure(w.quantity, w.unit);
      const workQty = toNum(normalized.qty);
      const workUnit = normalized.unit || w.unit || '';
      const workUnitKey = _normalizeUnit(workUnit);
      const linkedPool = w.estimateId ? estimateRows.filter(r => Number(r.estimateId) === Number(w.estimateId)) : [];
      const pool = linkedPool.length ? linkedPool : estimateRows;
      let best = null;

      pool.forEach(er => {
        const unitOk = !workUnitKey || !er.unitKey || workUnitKey === er.unitKey;
        const nameScore = workJournalReconcileNameScore(w.description, er.itemName);
        const sectionScore = w.sectionName && er.sectionName
          ? (estimateDiffTextKey(w.sectionName) === estimateDiffTextKey(er.sectionName) ? 0.12 : workJournalReconcileNameScore(w.sectionName, er.sectionName) * 0.08)
          : 0;
        const linkedBonus = w.estimateId && Number(w.estimateId) === Number(er.estimateId) ? 0.18 : 0;
        const unitBonus = unitOk ? 0.08 : -0.12;
        const score = Math.max(0, Math.min(1, nameScore + sectionScore + linkedBonus + unitBonus));
        if (!best || score > best.score) best = {row: er, score, unitOk};
      });

      let status = 'Вне сметы';
      if (!estimateRows.length) status = 'Нет активной сметы';
      else if (best && best.unitOk && w.estimateId && Number(w.estimateId) === Number(best.row.estimateId) && best.score >= 0.45) status = 'Из сметы';
      else if (best && best.unitOk && best.score >= 0.68) status = 'Найдено';
      else if (best && best.score >= 0.44) status = 'На проверку';
      const estimateValue = (['Из сметы', 'Найдено'].includes(status) && best?.row?.unitPrice) ? workQty * best.row.unitPrice : 0;

      return {
        key: 'wj-' + (w.id || idx),
        work: w,
        workQty,
        workUnit,
        workUnitKey,
        match: best?.row || null,
        score: best?.score || 0,
        unitOk: !!best?.unitOk,
        status,
        overQty: 0,
        estimateValue,
      };
    });

  const grouped = {};
  workRows.forEach(r => {
    if (!['Из сметы', 'Найдено'].includes(r.status) || !r.match || !r.unitOk) return;
    if (!grouped[r.match.key]) grouped[r.match.key] = {estimate: r.match, rows: [], qty: 0};
    grouped[r.match.key].rows.push(r);
    grouped[r.match.key].qty += r.workQty;
  });
  Object.values(grouped).forEach(g => {
    const tolerance = Math.max(0.001, Math.abs(g.estimate.planQty) * 0.01);
    const overQty = g.qty - g.estimate.planQty;
    if (overQty <= tolerance) return;
    g.rows.forEach(r => {
      r.status = 'Превышение объёма';
      r.overQty = overQty;
      r.estimateValue = r.workQty * (r.match?.unitPrice || 0);
    });
  });

  const rank = {'Превышение объёма': 0, 'Вне сметы': 1, 'На проверку': 2, 'Нет активной сметы': 3, 'Найдено': 4, 'Из сметы': 5};
  return workRows.sort((a, b) => (rank[a.status] ?? 9) - (rank[b.status] ?? 9) || Number(b.work.id || 0) - Number(a.work.id || 0));
};

export const workJournalEstimateSummaryFor = (project, options = {}) => {
  const rows = options.rows || workJournalEstimateRowsFor(project, options);
  const planDone = options.planDone || {plan: 0, done: 0};
  return {
    rows,
    estimatePlan: planDone.plan,
    estimateDone: planDone.done,
    journalTotal: rows.reduce((s, r) => s + toNum(r.work.total), 0),
    estimateValue: rows.reduce((s, r) => s + toNum(r.estimateValue), 0),
    linkedRows: rows.filter(r => ['Из сметы', 'Найдено'].includes(r.status)),
    reviewRows: rows.filter(r => r.status === 'На проверку'),
    outsideRows: rows.filter(r => r.status === 'Вне сметы' || r.status === 'Нет активной сметы'),
    overRows: rows.filter(r => r.status === 'Превышение объёма'),
    outsideTotal: rows.filter(r => r.status === 'Вне сметы' || r.status === 'Нет активной сметы').reduce((s, r) => s + toNum(r.work.total), 0),
    reviewTotal: rows.filter(r => r.status === 'На проверку').reduce((s, r) => s + toNum(r.work.total), 0),
    overTotal: rows.filter(r => r.status === 'Превышение объёма').reduce((s, r) => s + toNum(r.work.total), 0),
  };
};

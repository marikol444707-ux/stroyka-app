import React from 'react';

const parseDate = (value) => {
  if (!value) return null;
  const date = new Date(String(value).slice(0, 10) + 'T00:00:00');
  return Number.isNaN(date.getTime()) ? null : date;
};

const daysBetween = (from, to) => Math.ceil((to.getTime() - from.getTime()) / 86400000);

const fmtDate = (value) => {
  const date = parseDate(value);
  return date ? date.toLocaleDateString('ru-RU') : '—';
};

const fmtMoney = (value) => Math.round(Number(value || 0)).toLocaleString('ru-RU') + ' ₽';

export default function ProjectScheduleSummaryPanel({
  C,
  card,
  project,
  stages = [],
  workJournal = [],
  planDone = {plan: 0, done: 0},
  progress = 0,
  materialSummary = null,
  supplierInvoices = [],
  isMobile,
  onOpenStages,
  onOpenJournal,
  onOpenMaterials,
}) {
  if (!project) return null;

  const today = parseDate(new Date().toISOString());
  const projectName = project.name || '';
  const projectStages = (stages || []).filter(stage => stage.projectName === projectName);
  const datedStages = projectStages.filter(stage => parseDate(stage.startDate) && parseDate(stage.endDate));
  const doneStages = projectStages.filter(stage => stage.status === 'Завершён').length;
  const activeStages = projectStages.filter(stage => stage.status === 'В работе').length;
  const overdueStages = projectStages.filter(stage => {
    const end = parseDate(stage.endDate);
    return end && today && end < today && stage.status !== 'Завершён';
  }).length;
  const deadline = parseDate(project.deadline);
  const deadlineDelta = deadline && today ? daysBetween(today, deadline) : null;
  const projectWorks = (workJournal || []).filter(work => work.project === projectName);
  const workDate = (work) => parseDate(work.date || work.confirmedAt || work.createdAt);
  const recentBorder = today ? new Date(today.getTime() - 7 * 86400000) : null;
  const recentWorks = projectWorks.filter(work => {
    const date = workDate(work);
    return date && recentBorder && date >= recentBorder;
  });
  const pendingWorks = projectWorks.filter(work => !work.status || work.status === 'На проверке' || work.status === 'Автоматически из сметы').length;
  const lastWorkDate = projectWorks
    .map(workDate)
    .filter(Boolean)
    .sort((a, b) => b.getTime() - a.getTime())[0];
  const projectInvoices = (supplierInvoices || []).filter(invoice => (invoice.projectName || invoice.project) === projectName);
  const pendingInvoices = projectInvoices.filter(invoice => ['На утверждении', 'Утверждён', 'Частично оплачен', ''].includes(invoice.status || '')).length;
  const materialNeedRows = (materialSummary?.toBuyRows || []).length;
  const materialMismatchRows = (materialSummary?.mismatchRows || []).length + (materialSummary?.stockMismatchRows || []).length;
  const outsideMaterialRows = (materialSummary?.outsideRows || []).length;
  const materialBlockers = materialNeedRows + materialMismatchRows + outsideMaterialRows + pendingInvoices;

  const startDates = datedStages.map(stage => parseDate(stage.startDate)).filter(Boolean).sort((a, b) => a - b);
  const endDates = datedStages.map(stage => parseDate(stage.endDate)).filter(Boolean).sort((a, b) => b - a);
  const scheduleStart = startDates[0] || null;
  const scheduleEnd = endDates[0] || deadline || null;
  const plannedProgress = scheduleStart && scheduleEnd && today
    ? Math.max(0, Math.min(100, Math.round((today - scheduleStart) / Math.max(1, scheduleEnd - scheduleStart) * 100)))
    : null;
  const lag = plannedProgress !== null ? Math.max(0, plannedProgress - Number(progress || 0)) : 0;
  const stageText = projectStages.length ? `${doneStages}/${projectStages.length} завершено` : 'этапы не заведены';
  const deadlineText = deadlineDelta === null
    ? 'срок не задан'
    : deadlineDelta < 0
      ? 'просрочено на ' + Math.abs(deadlineDelta) + ' дн.'
      : deadlineDelta === 0 ? 'срок сегодня' : 'осталось ' + deadlineDelta + ' дн.';

  const risks = [
    overdueStages ? 'просроченных этапов: ' + overdueStages : '',
    pendingWorks ? 'ЖПР на проверке: ' + pendingWorks : '',
    !recentWorks.length && projectWorks.length ? 'нет новых работ за 7 дней' : '',
    !projectStages.length ? 'нужно завести этапы' : '',
    lag >= 15 ? 'отставание от календаря: ' + lag + '%' : '',
    materialNeedRows ? 'материалов докупить: ' + materialNeedRows : '',
    materialMismatchRows ? 'расхождений материалов: ' + materialMismatchRows : '',
    pendingInvoices ? 'поставки/счета в работе: ' + pendingInvoices : '',
  ].filter(Boolean);

  const metric = (label, value, color, sub, options = {}) => (
    <div style={{
      padding: '12px',
      borderRadius: '10px',
      backgroundColor: options.bg || C.bg,
      border: '1.5px solid ' + (options.border || C.border),
      minWidth: 0,
    }}>
      <p style={{margin: '0 0 4px', color: C.textSec, fontSize: '11px'}}>{label}</p>
      <b style={{display: 'block', color, fontSize: '16px', lineHeight: 1.2, wordBreak: 'break-word'}}>{value}</b>
      {sub ? <p style={{margin: '5px 0 0', color: C.textMuted, fontSize: '10px', lineHeight: 1.35}}>{sub}</p> : null}
    </div>
  );

  return (
    <div style={{...card, padding: '16px', marginBottom: '14px', backgroundColor: C.bgWhite, border: '1.5px solid ' + (risks.length ? C.warningBorder : C.successBorder)}}>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap', marginBottom: '12px'}}>
        <div>
          <b style={{display: 'block', color: C.text, fontSize: '15px'}}>📈 Управление сроками</b>
          <p style={{margin: '4px 0 0', color: C.textSec, fontSize: '12px', lineHeight: 1.4}}>
            Сводка строится по этапам, дедлайну объекта и записям журнала производства работ.
          </p>
        </div>
        <div style={{display: 'flex', gap: '8px', flexWrap: 'wrap'}}>
          <button onClick={onOpenStages} style={{padding: '6px 10px', borderRadius: '9px', border: '1.5px solid ' + C.border, background: C.bg, color: C.text, cursor: 'pointer', fontSize: '12px', fontWeight: 700}}>Этапы</button>
          <button onClick={onOpenJournal} style={{padding: '6px 10px', borderRadius: '9px', border: '1.5px solid ' + C.border, background: C.bg, color: C.text, cursor: 'pointer', fontSize: '12px', fontWeight: 700}}>ЖПР</button>
          <button onClick={onOpenMaterials} style={{padding: '6px 10px', borderRadius: '9px', border: '1.5px solid ' + C.border, background: C.bg, color: C.text, cursor: 'pointer', fontSize: '12px', fontWeight: 700}}>Материалы</button>
        </div>
      </div>

      <div style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr 1fr' : 'repeat(5,minmax(0,1fr))', gap: '10px', marginBottom: '10px'}}>
        {metric('Реальный прогресс', `${progress}%`, lag >= 15 ? C.warning : C.success, plannedProgress !== null ? `календарь: ${plannedProgress}%` : 'нет дат этапов')}
        {metric('Срок объекта', fmtDate(project.deadline), deadlineDelta !== null && deadlineDelta < 0 ? C.danger : C.info, deadlineText, {bg: deadlineDelta !== null && deadlineDelta < 0 ? C.dangerLight : C.bg, border: deadlineDelta !== null && deadlineDelta < 0 ? C.dangerBorder : C.border})}
        {metric('Этапы', stageText, overdueStages ? C.warning : C.accent, activeStages ? 'в работе: ' + activeStages : 'активных нет')}
        {metric('Активность ЖПР', recentWorks.length + ' за 7 дней', recentWorks.length ? C.success : C.warning, lastWorkDate ? 'последняя: ' + lastWorkDate.toLocaleDateString('ru-RU') : 'записей нет')}
        {metric('Материалы', materialBlockers ? materialBlockers + ' сигналов' : 'без блокировок', materialBlockers ? C.warning : C.success, materialNeedRows ? 'докупить: ' + materialNeedRows : pendingInvoices ? 'поставки: ' + pendingInvoices : 'сверка спокойная', {bg: materialBlockers ? C.warningLight : C.successLight, border: materialBlockers ? C.warningBorder : C.successBorder})}
      </div>

      <div style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: '10px'}}>
        {metric('Смета / закрыто', fmtMoney(planDone.done || 0), C.success, 'план: ' + fmtMoney(planDone.plan || 0))}
        <div style={{padding: '12px', borderRadius: '10px', backgroundColor: risks.length ? C.warningLight : C.successLight, border: '1.5px solid ' + (risks.length ? C.warningBorder : C.successBorder)}}>
          <p style={{margin: '0 0 6px', color: C.textSec, fontSize: '11px'}}>Что требует внимания</p>
          <b style={{display: 'block', color: risks.length ? C.warning : C.success, fontSize: '13px', lineHeight: 1.35}}>
            {risks.length ? risks.slice(0, 4).join(' · ') : 'критичных отклонений не видно'}
          </b>
        </div>
      </div>
    </div>
  );
}

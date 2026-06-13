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
  const workDateMs = (work) => {
    const date = workDate(work);
    return date ? date.getTime() : 0;
  };
  const workAmount = (work) => Number(work.executionTotal || work.execution_total || work.total || work.amount || 0) || 0;
  const workStatus = (work) => work.status || 'На проверке';
  const rawWorkPackage = (work) => String(work.workPackage || work.work_package || work.package || '').trim();
  const rawWorkRoom = (work) => String(work.roomName || work.room_name || work.room || work.zoneName || work.zone || '').trim();
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
  const worksWithoutPackage = projectWorks.filter(work => !rawWorkPackage(work)).length;
  const worksWithoutRoom = projectWorks.filter(work => !rawWorkRoom(work)).length;

  const buildWorkGroupRows = (keyGetter, fallbackLabel) => {
    const grouped = new Map();
    projectWorks.forEach(work => {
      const key = keyGetter(work) || fallbackLabel;
      const current = grouped.get(key) || {
        key,
        total: 0,
        confirmed: 0,
        pending: 0,
        rejected: 0,
        amount: 0,
        lastMs: 0,
      };
      current.total += 1;
      if (workStatus(work) === 'Подтверждено') current.confirmed += 1;
      else if (workStatus(work) === 'Отклонено') current.rejected += 1;
      else current.pending += 1;
      current.amount += workAmount(work);
      current.lastMs = Math.max(current.lastMs, workDateMs(work));
      grouped.set(key, current);
    });
    return Array.from(grouped.values()).sort((a, b) => {
      if (b.pending !== a.pending) return b.pending - a.pending;
      if (b.lastMs !== a.lastMs) return b.lastMs - a.lastMs;
      return b.total - a.total;
    });
  };

  const packageRows = buildWorkGroupRows(rawWorkPackage, 'Без пакета');
  const roomRows = buildWorkGroupRows(rawWorkRoom, 'Без помещения/зоны');

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
    worksWithoutPackage ? 'работ без пакета: ' + worksWithoutPackage : '',
    worksWithoutRoom ? 'работ без помещения/зоны: ' + worksWithoutRoom : '',
  ].filter(Boolean);

  const groupStatusLine = (row) => [
    row.confirmed ? 'подтв. ' + row.confirmed : '',
    row.pending ? 'на проверке ' + row.pending : '',
    row.rejected ? 'откл. ' + row.rejected : '',
    row.amount ? 'сумма ' + fmtMoney(row.amount) : '',
  ].filter(Boolean).join(' · ');

  const workGroupList = (title, rows, emptyText) => (
    <div style={{padding: '12px', borderRadius: '10px', backgroundColor: C.bg, border: '1.5px solid ' + C.border, minWidth: 0}}>
      <p style={{margin: '0 0 8px', color: C.textSec, fontSize: '11px'}}>{title}</p>
      {rows.length ? (
        <div style={{display: 'grid', gap: '8px'}}>
          {rows.slice(0, 6).map(row => (
            <div key={row.key} style={{display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto', gap: '8px', alignItems: 'center'}}>
              <div style={{minWidth: 0}}>
                <b style={{display: 'block', color: row.key.startsWith('Без ') ? C.warning : C.text, fontSize: '12px', lineHeight: 1.25, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
                  {row.key}
                </b>
                <span style={{display: 'block', color: C.textMuted, fontSize: '10px', lineHeight: 1.35}}>
                  {groupStatusLine(row) || 'фактов: ' + row.total}
                </span>
              </div>
              <span style={{
                color: row.pending ? C.warning : C.success,
                backgroundColor: row.pending ? C.warningLight : C.successLight,
                border: '1px solid ' + (row.pending ? C.warningBorder : C.successBorder),
                borderRadius: '999px',
                padding: '3px 7px',
                fontSize: '10px',
                fontWeight: 800,
                whiteSpace: 'nowrap',
              }}>
                {row.confirmed}/{row.total}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p style={{margin: 0, color: C.textMuted, fontSize: '12px'}}>{emptyText}</p>
      )}
    </div>
  );

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

      <div style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: '10px', marginTop: '10px'}}>
        {workGroupList('Пакеты работ по ЖПР', packageRows, 'в журнале пока нет работ по пакетам')}
        {workGroupList('Помещения и зоны по ЖПР', roomRows, 'помещения/зоны в журнале пока не указаны')}
      </div>
    </div>
  );
}

import React from 'react';

export default function ProjectScheduleTab({
  C,
  ProjectScheduleSummaryPanel,
  card,
  isMobile,
  materialControlSummaryForProject,
  project,
  projectPayments,
  projectPlanDone,
  projectRealProgress,
  projectStages,
  setActiveProjectTab,
  supplierInvoices,
  workJournal,
}) {
  const stages = projectStages.filter(stage => stage.projectName === project.name && stage.startDate && stage.endDate);
  const projectPaymentRows = projectPayments.filter(payment => payment.projectName === project.name);

  const renderGantt = () => {
    if (stages.length === 0) {
      return (
        <p style={{ color: C.textMuted, textAlign: 'center', padding: '30px' }}>
          Добавьте этапы с датами во вкладке Этапы
        </p>
      );
    }

    const allDates = stages.flatMap(stage => [stage.startDate, stage.endDate]).filter(Boolean).sort();
    const minDate = new Date(allDates[0]);
    const maxDate = new Date(allDates[allDates.length - 1]);
    const totalDays = Math.max(1, Math.round((maxDate - minDate) / 86400000)) + 1;
    const statusColors = {
      'Не начат': C.textSec,
      'В работе': C.info,
      'Завершён': C.success,
      'Заморожен': C.warning,
      'Просрочен': C.danger,
    };

    return (
      <div style={{ overflowX: 'auto' }}>
        <div style={{ minWidth: '600px' }}>
          <div style={{ display: 'flex', borderBottom: '1.5px solid ' + C.border, paddingBottom: '6px', marginBottom: '8px' }}>
            <div style={{ width: '200px', flexShrink: 0, fontSize: '11px', color: C.textSec, fontWeight: '600' }}>Этап</div>
            <div style={{ flex: 1, fontSize: '11px', color: C.textSec, fontWeight: '600' }}>Временная шкала</div>
          </div>

          {stages.map(stage => {
            const startDate = new Date(stage.startDate);
            const endDate = new Date(stage.endDate);
            const left = Math.round((startDate - minDate) / 86400000) / totalDays * 100;
            const width = Math.max(1, Math.round((endDate - startDate) / 86400000) + 1) / totalDays * 100;
            const color = statusColors[stage.status] || C.textSec;

            return (
              <div key={stage.id} style={{ display: 'flex', alignItems: 'center', marginBottom: '10px' }}>
                <div style={{ width: '200px', flexShrink: 0, fontSize: '12px', color: C.text, paddingRight: '10px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {stage.name}
                </div>
                <div style={{ flex: 1, position: 'relative', height: '26px', backgroundColor: C.bg, borderRadius: '4px', border: '1px solid ' + C.border }}>
                  <div style={{ position: 'absolute', left: left + '%', width: width + '%', minWidth: '2%', height: '100%', backgroundColor: color, borderRadius: '4px', display: 'flex', alignItems: 'center', paddingLeft: '6px', overflow: 'hidden' }}>
                    <span style={{ fontSize: '10px', color: 'white', fontWeight: '600', whiteSpace: 'nowrap' }}>{stage.progress + '%'}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {projectPaymentRows.length > 0 && (
          <div style={{ marginTop: '12px' }}>
            <b style={{ color: C.textSec, fontSize: '12px', display: 'block', marginBottom: '8px' }}>История оплат:</b>
            {projectPaymentRows.map(payment => (
              <div key={payment.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid ' + C.border }}>
                <div>
                  <span style={{ fontSize: '12px', color: C.text }}>{payment.note || 'Оплата'}</span>
                  {(payment.workPackage || payment.work_package) && (
                    <span style={{ fontSize: '11px', color: C.info, marginLeft: '8px' }}>📁 {payment.workPackage || payment.work_package}</span>
                  )}
                  <span style={{ fontSize: '11px', color: C.textMuted, marginLeft: '8px' }}>{payment.date}</span>
                </div>
                <b style={{ fontSize: '12px', color: C.success }}>+{Number(payment.amount).toLocaleString() + ' ₽'}</b>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div>
      <ProjectScheduleSummaryPanel
        C={C}
        card={card}
        project={project}
        stages={projectStages}
        workJournal={workJournal}
        planDone={projectPlanDone(project)}
        progress={projectRealProgress(project)}
        materialSummary={materialControlSummaryForProject(project.name)}
        supplierInvoices={supplierInvoices}
        isMobile={isMobile}
        onOpenStages={() => setActiveProjectTab('Этапы')}
        onOpenJournal={() => setActiveProjectTab('Производство работ')}
        onOpenMaterials={() => setActiveProjectTab('Материалы')}
      />

      <b style={{ color: C.text, display: 'block', marginBottom: '15px' }}>График Ганта</b>
      {renderGantt()}
    </div>
  );
}

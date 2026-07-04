import React from 'react';

export default function ProjectJournalsHubTab({
  C,
  card,
  hiddenActs,
  prescriptionsList,
  project,
  projectJournalDiagnostics,
  setActiveProjectTab,
  tbJournal,
  weatherLog,
  workJournal,
}) {
  const diagnostics = projectJournalDiagnostics(project.name);
  const cards = [
    { tab: 'Производство работ', icon: '📖', label: 'Производство работ', hint: 'Журнал по форме КС-6а', count: workJournal.filter(row => row.project === project.name).length },
    { tab: 'АОСР', icon: '🔒', label: 'АОСР', hint: 'Печатные формы из сметы и журнала работ', count: hiddenActs.filter(act => act.projectName === project.name).length },
    {
      tab: 'Входной контроль',
      icon: '📦',
      label: 'Входной контроль материалов',
      hint: 'СП 48.13330.2019',
      count: diagnostics.inspections.length,
      warningCount: diagnostics.stockWithoutInspection.length,
      details: [
        { label: 'склад', value: diagnostics.projectStock.length, color: C.textSec },
        { label: 'контроль', value: diagnostics.inspections.length, color: C.success },
        { label: 'не связано', value: diagnostics.stockWithoutInspection.length, color: diagnostics.stockWithoutInspection.length ? C.warning : C.textMuted },
      ],
    },
    {
      tab: 'Кабельная продукция',
      icon: '⚡',
      label: 'Кабельная продукция',
      hint: 'СП 76.13330 · ПУЭ',
      count: diagnostics.cables.length,
      warningCount: diagnostics.cableWithoutJournal.length,
      details: [
        { label: 'на складе', value: diagnostics.cableStock.length, color: C.textSec },
        { label: 'в журнале', value: diagnostics.cables.length, color: C.success },
        { label: 'не связано', value: diagnostics.cableWithoutJournal.length, color: diagnostics.cableWithoutJournal.length ? C.warning : C.textMuted },
      ],
    },
    {
      tab: 'Материалы',
      icon: '🔎',
      label: 'Сметная сверка',
      hint: 'По смете · сверх · вне сметы · алиасы',
      count: diagnostics.smetaRows.length,
      warningCount: diagnostics.smetaOutsideRows.length + diagnostics.aliasNeededRows.length,
      details: [
        { label: 'по смете', value: diagnostics.smetaInPlanRows.length, color: C.success },
        { label: 'сверх', value: diagnostics.smetaOverRows.length, color: diagnostics.smetaOverRows.length ? C.warning : C.textMuted },
        { label: 'вне/алиас', value: diagnostics.smetaOutsideRows.length + '/' + diagnostics.aliasNeededRows.length, color: diagnostics.smetaOutsideRows.length ? C.warning : C.textMuted },
      ],
    },
    { tab: 'Журнал ТБ', icon: '🛡️', label: 'Техника безопасности', hint: 'ГОСТ 12.0.004-2015', count: (tbJournal || []).filter(entry => entry.project === project.name).length },
    { tab: 'Погода', icon: '🌤', label: 'Погода', hint: 'Метеоусловия по дням', count: (weatherLog || []).filter(row => row.projectName === project.name).length },
    { tab: 'Предписания', icon: '⚠️', label: 'Предписания', hint: 'От технадзора и стройконтроля', count: (prescriptionsList || []).filter(item => item.projectName === project.name).length },
    { tab: 'Чат', icon: '💬', label: 'Чат проекта', hint: 'Переписка по объекту', count: 0 },
  ];

  return (
    <div>
      <div style={{ marginBottom: '15px' }}>
        <b style={{ color: C.text, fontSize: '15px', fontWeight: '700' }}>📚 Журналы объекта</b>
        <p style={{ color: C.textMuted, fontSize: '12px', margin: '4px 0 0' }}>Клик по карточке откроет соответствующий журнал.</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: '12px' }}>
        {cards.map(item => (
          <div
            key={item.tab}
            onClick={() => setActiveProjectTab(item.tab)}
            style={{ ...card, padding: '16px', cursor: 'pointer', border: '1.5px solid ' + (item.warningCount ? C.warningBorder : C.border), backgroundColor: item.warningCount ? C.warningLight : card.backgroundColor }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
              <span style={{ fontSize: '24px' }}>{item.icon}</span>
              <b style={{ color: C.text, fontSize: '13px' }}>{item.label}</b>
            </div>
            <p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 6px' }}>{item.hint}</p>
            <b style={{ color: item.warningCount ? C.warning : C.accent, fontSize: '13px' }}>{item.count + ' ' + (item.count === 1 ? 'запись' : item.count >= 2 && item.count <= 4 ? 'записи' : 'записей')}</b>
            {item.details && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,minmax(0,1fr))', gap: '6px', marginTop: '10px' }}>
                {item.details.map(detail => (
                  <div key={detail.label} style={{ minWidth: 0 }}>
                    <p style={{ color: C.textMuted, fontSize: '10px', margin: '0 0 2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{detail.label}</p>
                    <b style={{ color: detail.color, fontSize: '12px' }}>{detail.value}</b>
                  </div>
                ))}
              </div>
            )}
            {item.warningCount > 0 && <p style={{ color: C.warning, fontSize: '11px', margin: '8px 0 0', fontWeight: '700' }}>Есть несвязанные позиции</p>}
          </div>
        ))}
      </div>
    </div>
  );
}

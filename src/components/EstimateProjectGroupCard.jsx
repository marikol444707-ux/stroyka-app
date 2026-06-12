import React from 'react';
import { Archive, CheckCircle, ChevronRight, FileText, Trash2 } from 'lucide-react';

export default function EstimateProjectGroupCard({
  C,
  card,
  badge,
  btnB,
  btnG,
  btnGr,
  btnR,
  projectName,
  groups,
  setSelectedEstimate,
  estimateTypeIcon,
  estimateKind,
  estimatePackage,
  estimateUpdatedTs,
  activeEstimateFromList,
  estimateTotal,
  estimateStatusView,
  estimateDisplayVersion,
  estimateVersionChain,
  isArchivedEstimate,
  setEstimateStatusRemote,
  deleteEstimateRemote,
  showPreview,
  buildEstimateDiffContent,
  isLeadership,
}) {
  const projectGroups = (groups || []).map(([key, items]) => {
    const sorted = [...items].sort((a, b) => (estimateUpdatedTs(b) || Number(b.id || 0)) - (estimateUpdatedTs(a) || Number(a.id || 0)));
    const active = activeEstimateFromList(sorted);
    const kind = estimateKind(active || sorted[0]);
    const pkg = estimatePackage(active || sorted[0]);
    const archivedCount = sorted.filter(isArchivedEstimate).length;
    const draftCount = sorted.filter(e => (e.status || 'Черновик') === 'Черновик').length;
    const activeCount = sorted.filter(e => e.status === 'Активная').length;
    const last = sorted[0];
    const prevForActive = active ? sorted.find(e => e.id !== active.id) : null;
    const diff = active && prevForActive ? estimateTotal(active) - estimateTotal(prevForActive) : 0;
    return { key, sorted, active, kind, pkg, archivedCount, draftCount, activeCount, last, prevForActive, diff };
  });

  const projectTotal = projectGroups.reduce((sum, group) => sum + (group.active ? estimateTotal(group.active) : 0), 0);
  const activeCount = projectGroups.reduce((sum, group) => sum + group.activeCount, 0);
  const archivedCount = projectGroups.reduce((sum, group) => sum + group.archivedCount, 0);
  const draftCount = projectGroups.reduce((sum, group) => sum + group.draftCount, 0);

  return (
    <div style={{ ...card, marginBottom: '14px', overflow: 'hidden' }}>
      <div style={{ padding: '14px', backgroundColor: C.bg, borderBottom: '1.5px solid ' + C.border, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
        <div style={{ minWidth: '260px', flex: 1 }}>
          <b style={{ color: C.text, fontSize: '15px' }}>{'🏗️ ' + projectName}</b>
          <p style={{ color: C.textSec, margin: '4px 0 0', fontSize: '12px' }}>
            {'Папок смет: ' + projectGroups.length + ' · активных ' + activeCount + ' · архив ' + archivedCount + (draftCount ? ' · черновиков ' + draftCount : '')}
          </p>
        </div>
        <b style={{ color: C.success, fontSize: '15px', whiteSpace: 'nowrap' }}>
          {Math.round(projectTotal).toLocaleString('ru-RU') + ' ₽'}
        </b>
      </div>

      <div style={{ padding: '10px 12px' }}>
        {projectGroups.map(group => (
          <div key={group.key} style={{ marginBottom: '10px', border: '1px solid ' + C.border, borderRadius: '10px', overflow: 'hidden', backgroundColor: C.bgWhite }}>
            <div style={{ padding: '12px 14px', backgroundColor: C.bg, borderBottom: '1px solid ' + C.border, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
              <div style={{ minWidth: '240px', flex: 1 }}>
                <b style={{ color: C.text, fontSize: '13px' }}>{estimateTypeIcon(group.kind) + ' ' + group.pkg}</b>
                <p style={{ color: C.textSec, margin: '3px 0 0', fontSize: '12px' }}>
                  {group.kind + ' · ' + group.sorted.length + ' верс. · активных ' + group.activeCount + ' · архив ' + group.archivedCount + (group.draftCount ? ' · черновиков ' + group.draftCount : '')}
                </p>
                {group.active && (
                  <p style={{ color: C.textMuted, margin: '3px 0 0', fontSize: '11px' }}>
                    Сейчас в расчётах: {estimateDisplayVersion(group.active, group.sorted)} · {group.active.name}
                    {group.last?.id !== group.active.id ? ' · последняя загруженная: ' + estimateDisplayVersion(group.last, group.sorted) : ''}
                  </p>
                )}
                <p style={{ color: C.textMuted, margin: '3px 0 0', fontSize: '11px' }}>Цепочка: {estimateVersionChain(group.sorted)}</p>
              </div>
              <div style={{ textAlign: 'right' }}>
                <b style={{ color: C.success, fontSize: '14px' }}>{group.active ? Math.round(estimateTotal(group.active)).toLocaleString('ru-RU') + ' ₽' : '—'}</b>
                {group.prevForActive && (
                  <p style={{ color: group.diff >= 0 ? C.warning : C.success, margin: '3px 0 0', fontSize: '11px' }}>
                    {(group.diff >= 0 ? '+' : '') + Math.round(group.diff).toLocaleString('ru-RU') + ' ₽ к прошлой'}
                  </p>
                )}
              </div>
            </div>

            <div style={{ padding: '8px 12px' }}>
              {group.sorted.map(est => {
                const st = estimateStatusView(est, group.sorted);
                const isUsed = group.active?.id === est.id;
                const diffBase = (group.active && group.active.id !== est.id) ? group.active : group.sorted.find(other => other.id !== est.id);
                return (
                  <div key={est.id} onClick={() => setSelectedEstimate(est)} style={{ padding: '10px 8px', borderBottom: '1px solid ' + C.border, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', cursor: 'pointer', opacity: isArchivedEstimate(est) ? 0.72 : 1 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <b style={{ color: C.text, fontSize: '13px' }}>{isUsed ? '✓ ' : ''}{est.name}</b>
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '4px' }}>
                        <span style={badge(st.color, st.bg, st.border)}>{st.label}</span>
                        <span style={badge(C.textSec, C.bgGray, C.border)}>{estimateDisplayVersion(est, group.sorted)}</span>
                        {est.versionCount > 0 && <span style={badge(C.info, C.infoLight, C.infoBorder)}>{'история ' + est.versionCount}</span>}
                        {est.createdAt && <span style={{ color: C.textMuted, fontSize: '11px', alignSelf: 'center' }}>{String(est.createdAt).slice(0, 10)}</span>}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                      <b style={{ color: C.success, fontSize: '13px' }}>{Math.round(estimateTotal(est)).toLocaleString('ru-RU') + ' ₽'}</b>
                      {diffBase && <button onClick={e => { e.stopPropagation(); showPreview(buildEstimateDiffContent(diffBase, est), 'Сопоставительная ведомость'); }} style={{ ...btnB, padding: '4px 8px', fontSize: '11px' }}><FileText size={11} />Ведомость</button>}
                      {est.status !== 'Активная' && <button onClick={e => { e.stopPropagation(); setEstimateStatusRemote(est, 'Активная'); }} style={{ ...btnGr, padding: '4px 8px', fontSize: '11px' }}><CheckCircle size={11} />Активной</button>}
                      {est.status !== 'Архив' && <button onClick={e => { e.stopPropagation(); setEstimateStatusRemote(est, 'Архив'); }} style={{ ...btnG, padding: '4px 8px', fontSize: '11px' }} title="В архив"><Archive size={11} /></button>}
                      {isLeadership() && <button onClick={e => { e.stopPropagation(); deleteEstimateRemote(est); }} style={{ ...btnR, padding: '4px 8px', fontSize: '11px' }} title="Удалить смету"><Trash2 size={11} /></button>}
                      <ChevronRight size={16} color={C.textMuted} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

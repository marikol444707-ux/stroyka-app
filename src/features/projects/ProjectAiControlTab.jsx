import React from 'react';

const AI_TASK_GROUP_ORDER = ['materials', 'rooms', 'estimate', 'changes', 'other'];
const MATERIAL_TASK_TYPES = [
  'material_purchase_review',
  'material_outside_estimate_review',
  'material_writeoff_review',
  'material_norm_over_review',
  'material_without_norm_review',
  'material_transfer_sign_review',
];
const ROOM_TASK_TYPES = ['room_measurement_review', 'work_room_link_review'];
const ESTIMATE_TASK_TYPES = ['estimate_quality_review', 'estimate_norm_review', 'material_norm_coverage'];
const CHANGE_TASK_TYPES = ['estimate_diff_review', 'estimate_change_reconcile'];

export default function ProjectAiControlTab({
  C,
  Bot,
  Calculator,
  Check,
  Eye,
  FileText,
  GitBranch,
  MapPin,
  Package,
  _normalizeUnit,
  acceptMaterialAliasTask,
  aiFindingsForProject,
  aiSeverityMeta,
  aiTasksForProject,
  badge,
  btnB,
  btnG,
  btnGr,
  btnO,
  btnR,
  card,
  generateAiFindingsForProject,
  isMobile,
  materialNameKey,
  materialReconciliationRows,
  openAiTaskAction,
  parseAiTaskPayload,
  project,
  renderEstimateChangeReconcileTask,
  renderMaterialSupplyAction,
  toNum,
  updateAiFinding,
  updateAiTask,
  user,
}) {
  const projectFindings = aiFindingsForProject(project.name);
  const projectTasks = aiTasksForProject(project.name);
  const standaloneTasks = projectTasks.filter(t => !t.findingId);
  const byCategory = projectFindings.reduce((acc, finding) => {
    const key = finding.category || 'Общее';
    if (!acc[key]) acc[key] = [];
    acc[key].push(finding);
    return acc;
  }, {});
  const importantCount = projectFindings.filter(
    finding => finding.severity === 'Критично' || finding.severity === 'Не хватает данных'
  ).length;
  const canRunAiControl =
    user && ['директор', 'зам_директора', 'прораб', 'главный_инженер', 'сметчик', 'технадзор', 'стройконтроль'].includes(user.role);

  const taskTypeMeta = (task) => {
    const type = parseAiTaskPayload(task).type;
    if (MATERIAL_TASK_TYPES.includes(type)) {
      return { key: 'materials', label: 'Материалы', icon: <Package size={13} />, color: C.info, bg: C.infoLight, border: C.infoBorder };
    }
    if (ROOM_TASK_TYPES.includes(type)) {
      return { key: 'rooms', label: 'Помещения', icon: <MapPin size={13} />, color: C.success, bg: C.successLight, border: C.successBorder };
    }
    if (ESTIMATE_TASK_TYPES.includes(type)) {
      return { key: 'estimate', label: 'Смета и нормы', icon: <Calculator size={13} />, color: C.accent, bg: C.accentLight, border: C.accentBorder };
    }
    if (CHANGE_TASK_TYPES.includes(type)) {
      return { key: 'changes', label: 'Изменения к смете', icon: <GitBranch size={13} />, color: C.warning, bg: C.warningLight, border: C.warningBorder };
    }
    return { key: 'other', label: 'Прочее', icon: <Eye size={13} />, color: C.textSec, bg: C.bgGray, border: C.border };
  };

  const groupedStandaloneTasks = standaloneTasks.reduce((acc, task) => {
    const meta = taskTypeMeta(task);
    if (!acc[meta.key]) acc[meta.key] = { meta, tasks: [] };
    acc[meta.key].tasks.push(task);
    return acc;
  }, {});
  const standaloneTaskGroups = AI_TASK_GROUP_ORDER.map(key => groupedStandaloneTasks[key]).filter(Boolean);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexWrap: 'wrap', marginBottom: '14px' }}>
        <div>
          <b style={{ color: C.text, fontSize: '15px' }}>🤖 ИИ-контроль объекта</b>
          <p style={{ color: C.textSec, fontSize: '12px', margin: '4px 0 0' }}>Фоновый контроль обмеров, ЖПР, смет, норм, материалов и поручений.</p>
        </div>
        <button onClick={() => generateAiFindingsForProject(project.name)} disabled={!canRunAiControl} style={{ ...btnO, opacity: canRunAiControl ? 1 : 0.55 }}>
          <Bot size={14} />Обновить контроль
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr 1fr' : 'repeat(4,1fr)', gap: '10px', marginBottom: '14px' }}>
        <div style={{ padding: '12px', borderRadius: '10px', backgroundColor: C.bgWhite, border: '1.5px solid ' + C.border }}>
          <p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Открыто</p>
          <b style={{ color: C.text, fontSize: '20px' }}>{projectFindings.length}</b>
        </div>
        <div style={{ padding: '12px', borderRadius: '10px', backgroundColor: importantCount ? C.warningLight : C.successLight, border: '1.5px solid ' + (importantCount ? C.warningBorder : C.successBorder) }}>
          <p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Важные</p>
          <b style={{ color: importantCount ? C.warning : C.success, fontSize: '20px' }}>{importantCount}</b>
        </div>
        <div style={{ padding: '12px', borderRadius: '10px', backgroundColor: C.bgWhite, border: '1.5px solid ' + C.border }}>
          <p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Поручения</p>
          <b style={{ color: C.accent, fontSize: '20px' }}>{projectTasks.length}</b>
        </div>
        <div style={{ padding: '12px', borderRadius: '10px', backgroundColor: C.bgWhite, border: '1.5px solid ' + C.border }}>
          <p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Категорий</p>
          <b style={{ color: C.text, fontSize: '20px' }}>{Object.keys(byCategory).length}</b>
        </div>
      </div>

      {projectFindings.length === 0 && standaloneTasks.length === 0 && (
        <div style={{ ...card, padding: '18px', textAlign: 'center', backgroundColor: C.successLight, border: '1.5px solid ' + C.successBorder }}>
          <b style={{ color: C.success, fontSize: '14px' }}>Замечаний пока нет</b>
          <p style={{ color: C.textSec, fontSize: '12px', margin: '6px 0 12px' }}>Система обновляет контроль после ключевых событий, а эту кнопку можно использовать для ручного пересчёта.</p>
          <button onClick={() => generateAiFindingsForProject(project.name)} disabled={!canRunAiControl} style={{ ...btnGr, opacity: canRunAiControl ? 1 : 0.55 }}>
            <Bot size={14} />Обновить контроль
          </button>
        </div>
      )}

      {standaloneTasks.length > 0 && (
        <div style={{ ...card, padding: '14px', marginBottom: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            <b style={{ color: C.text, fontSize: '13px' }}>Поручения</b>
            <span style={badge(C.accent, C.accentLight, C.accentBorder)}>{standaloneTasks.length}</span>
          </div>
          {standaloneTaskGroups.map(group => (
            <div key={group.meta.key} style={{ marginBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: '0 0 8px', padding: '7px 9px', borderRadius: '10px', backgroundColor: group.meta.bg, border: '1.5px solid ' + group.meta.border }}>
                <span style={{ color: group.meta.color, display: 'inline-flex' }}>{group.meta.icon}</span>
                <b style={{ color: group.meta.color, fontSize: '12px' }}>{group.meta.label}</b>
                <span style={badge(group.meta.color, group.meta.bg, group.meta.border)}>{group.tasks.length}</span>
              </div>
              {group.tasks.map(task => (
                <StandaloneAiTaskCard
                  key={task.id}
                  C={C}
                  Calculator={Calculator}
                  Check={Check}
                  Eye={Eye}
                  FileText={FileText}
                  MapPin={MapPin}
                  Package={Package}
                  _normalizeUnit={_normalizeUnit}
                  acceptMaterialAliasTask={acceptMaterialAliasTask}
                  badge={badge}
                  btnB={btnB}
                  btnG={btnG}
                  btnGr={btnGr}
                  btnO={btnO}
                  btnR={btnR}
                  materialNameKey={materialNameKey}
                  materialReconciliationRows={materialReconciliationRows}
                  openAiTaskAction={openAiTaskAction}
                  parseAiTaskPayload={parseAiTaskPayload}
                  renderEstimateChangeReconcileTask={renderEstimateChangeReconcileTask}
                  renderMaterialSupplyAction={renderMaterialSupplyAction}
                  task={task}
                  toNum={toNum}
                  updateAiTask={updateAiTask}
                />
              ))}
            </div>
          ))}
        </div>
      )}

      {Object.entries(byCategory).map(([category, list]) => (
        <div key={category} style={{ ...card, padding: '14px', marginBottom: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            <b style={{ color: C.text, fontSize: '13px' }}>{category}</b>
            <span style={badge(C.accent, C.accentLight, C.accentBorder)}>{list.length}</span>
          </div>
          {list.map(finding => (
            <AiFindingCard
              key={finding.id}
              C={C}
              aiSeverityMeta={aiSeverityMeta}
              badge={badge}
              btnG={btnG}
              btnGr={btnGr}
              btnO={btnO}
              btnR={btnR}
              finding={finding}
              projectTasks={projectTasks}
              updateAiFinding={updateAiFinding}
              updateAiTask={updateAiTask}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

function StandaloneAiTaskCard({
  C,
  Calculator,
  Check,
  Eye,
  FileText,
  MapPin,
  Package,
  _normalizeUnit,
  acceptMaterialAliasTask,
  badge,
  btnB,
  btnG,
  btnGr,
  btnO,
  btnR,
  materialNameKey,
  materialReconciliationRows,
  openAiTaskAction,
  parseAiTaskPayload,
  renderEstimateChangeReconcileTask,
  renderMaterialSupplyAction,
  task,
  toNum,
  updateAiTask,
}) {
  const payload = parseAiTaskPayload(task);
  const isEstimateTask = [...ESTIMATE_TASK_TYPES, ...CHANGE_TASK_TYPES].includes(payload.type);
  const isMaterialTask = MATERIAL_TASK_TYPES.includes(payload.type);
  const isRoomTask = ROOM_TASK_TYPES.includes(payload.type);
  const aliasCandidate = payload.aliasCandidate || null;
  const purchaseRow = payload.type === 'material_purchase_review'
    ? materialReconciliationRows(payload.projectName || task.projectName || '').find(
        row => materialNameKey(row.name) === materialNameKey(payload.materialName) && (!payload.unit || _normalizeUnit(row.unit || '') === _normalizeUnit(payload.unit || ''))
      )
    : null;

  return (
    <div style={{ padding: '12px', borderRadius: '10px', backgroundColor: C.bg, border: '1.5px solid ' + C.border, marginBottom: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '10px', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: '220px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', marginBottom: '5px' }}>
            <span style={badge(C.info, C.infoLight, C.infoBorder)}>{task.status || 'Новое'}</span>
            <span style={{ fontSize: '11px', color: C.textSec }}>{task.assignedRole ? 'кому: ' + task.assignedRole : 'без роли'}</span>
          </div>
          <b style={{ display: 'block', color: C.text, fontSize: '13px', lineHeight: 1.35 }}>{task.title}</b>
          {payload.type === 'estimate_change_reconcile'
            ? renderEstimateChangeReconcileTask(task)
            : task.description && <p style={{ color: C.textSec, fontSize: '12px', margin: '6px 0 0', lineHeight: 1.45, whiteSpace: 'pre-wrap' }}>{task.description}</p>}
        </div>
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {aliasCandidate?.aliasName && aliasCandidate?.canonicalName && (
            <button onClick={() => acceptMaterialAliasTask(task)} style={{ ...btnGr, padding: '5px 9px', fontSize: '11px' }}>
              <Check size={11} />Привязать
            </button>
          )}
          {purchaseRow && toNum(purchaseRow.toBuy) > 0 && renderMaterialSupplyAction(payload.projectName || task.projectName || '', purchaseRow)}
          {task.actionLabel && (
            <button onClick={() => openAiTaskAction(task)} style={{ ...btnB, padding: '5px 9px', fontSize: '11px' }}>
              {payload.type === 'estimate_diff_review' ? <FileText size={11} /> : isEstimateTask ? <Calculator size={11} /> : isMaterialTask ? <Package size={11} /> : isRoomTask ? <MapPin size={11} /> : <Eye size={11} />} {task.actionLabel}
            </button>
          )}
          {task.status === 'Новое' && <button onClick={() => updateAiTask(task.id, { status: 'Принято к исполнению' })} style={{ ...btnG, padding: '5px 9px', fontSize: '11px' }}>Принять</button>}
          {['Новое', 'Принято к исполнению'].includes(task.status || '') && <button onClick={() => updateAiTask(task.id, { status: 'В работе' })} style={{ ...btnO, padding: '5px 9px', fontSize: '11px' }}>В работу</button>}
          <button onClick={() => updateAiTask(task.id, { status: 'Закрыто' })} style={{ ...btnGr, padding: '5px 9px', fontSize: '11px' }}>Закрыть</button>
          <button onClick={() => updateAiTask(task.id, { status: 'Отклонено' })} style={{ ...btnR, padding: '5px 9px', fontSize: '11px' }}>Отклонить</button>
        </div>
      </div>
    </div>
  );
}

function AiFindingCard({
  C,
  aiSeverityMeta,
  badge,
  btnG,
  btnGr,
  btnO,
  btnR,
  finding,
  projectTasks,
  updateAiFinding,
  updateAiTask,
}) {
  const meta = aiSeverityMeta(finding.severity);
  const task = projectTasks.find(item => Number(item.findingId) === Number(finding.id));

  return (
    <div style={{ padding: '12px', borderRadius: '10px', backgroundColor: meta.bg, border: '1.5px solid ' + meta.border, marginBottom: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '10px', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: '220px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', marginBottom: '5px' }}>
            <span style={badge(meta.color, meta.bg, meta.border)}>{finding.severity || 'Проверить'}</span>
            <span style={{ fontSize: '11px', color: C.textSec }}>{finding.assignedRole ? 'кому: ' + finding.assignedRole : 'без роли'}{task && task.status ? ' · ' + task.status : ''}</span>
          </div>
          <b style={{ display: 'block', color: C.text, fontSize: '13px', lineHeight: 1.35 }}>{finding.title}</b>
          {finding.description && <p style={{ color: C.textSec, fontSize: '12px', margin: '6px 0 0', lineHeight: 1.45 }}>{finding.description}</p>}
          {finding.suggestedAction && <p style={{ color: C.text, fontSize: '12px', margin: '6px 0 0' }}><b>Что сделать:</b> {finding.suggestedAction}</p>}
        </div>
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {task && task.status === 'Новое' && <button onClick={() => updateAiTask(task.id, { status: 'Принято к исполнению' })} style={{ ...btnG, padding: '5px 9px', fontSize: '11px' }}>Принять</button>}
          {task && ['Новое', 'Принято к исполнению'].includes(task.status || '') && <button onClick={() => updateAiTask(task.id, { status: 'В работе' })} style={{ ...btnO, padding: '5px 9px', fontSize: '11px' }}>В работу</button>}
          <button onClick={() => updateAiFinding(finding.id, { status: 'Исправлено' })} style={{ ...btnGr, padding: '5px 9px', fontSize: '11px' }}>Исправлено</button>
          <button onClick={() => updateAiFinding(finding.id, { status: 'Закрыто' })} style={{ ...btnG, padding: '5px 9px', fontSize: '11px' }}>Закрыть</button>
          <button onClick={() => updateAiFinding(finding.id, { status: 'Отклонено' })} style={{ ...btnR, padding: '5px 9px', fontSize: '11px' }}>Отклонить</button>
        </div>
      </div>
    </div>
  );
}

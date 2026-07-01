import React from 'react';
import { ArrowLeft, Bot, Download, Eye, FileText, GitBranch, MessageSquare, UserCheck, Users } from 'lucide-react';
import EstimateSelectedStatusActions from './EstimateSelectedStatusActions';
import EstimateSelectedTitleBadges from './EstimateSelectedTitleBadges';

export default function EstimateSelectedToolbar({
  C,
  badge,
  btnB,
  btnG,
  btnGr,
  btnO,
  estimateKind,
  estimatePackage,
  estimateStatusView,
  estimateTypeIcon,
  estimatesList,
  hasDiff,
  issueCount,
  onAiAnalysis,
  onBack,
  onDetectHiddenWorks,
  onExport,
  onHistory,
  onNormalize,
  onOpenChat,
  onOpenDistribute,
  onOpenWorkAssignment,
  onPreview,
  onCreateReconciliation,
  onShowDiff,
  onToggleIssuesOnly,
  onToggleTemplate,
  sameEstimateGroup,
  selectedEstimate,
  setEstimateStatusRemote,
  showLeadership,
  showEstimateIssuesOnly
}) {
  const issuesStyle = issueCount
    ? {
        ...(showEstimateIssuesOnly ? btnO : btnB),
        backgroundColor: showEstimateIssuesOnly ? C.danger : C.bg,
        color: showEstimateIssuesOnly ? 'white' : C.danger,
        borderColor: C.dangerBorder
      }
    : {...btnG, opacity: 0.75, cursor: 'default'};

  return (
    <div style={{display:'flex',gap:'8px',marginBottom:'15px',alignItems:'center',flexWrap:'wrap'}}>
      <button onClick={onBack} style={btnG}><ArrowLeft size={14}/>Назад</button>
      <EstimateSelectedTitleBadges
        C={C}
        badge={badge}
        selectedEstimate={selectedEstimate}
        estimatesList={estimatesList}
        sameEstimateGroup={sameEstimateGroup}
        estimateStatusView={estimateStatusView}
        estimateTypeIcon={estimateTypeIcon}
        estimateKind={estimateKind}
        estimatePackage={estimatePackage}
      />
      <EstimateSelectedStatusActions
        selectedEstimate={selectedEstimate}
        btnGr={btnGr}
        btnG={btnG}
        setEstimateStatusRemote={setEstimateStatusRemote}
        showLeadership={showLeadership}
      />
      <button disabled={!issueCount} onClick={onToggleIssuesOnly} style={issuesStyle}>
        {issueCount ? '⚠️ Проблемы: '+issueCount : '✅ Ошибок нет'}
      </button>
      <button onClick={onPreview} style={btnB}><Eye size={14}/>Просмотр</button>
      {hasDiff && <button onClick={onShowDiff} style={btnB}><FileText size={14}/>Ведомость</button>}
      {hasDiff && onCreateReconciliation && <button onClick={onCreateReconciliation} style={btnO}><GitBranch size={14}/>Сверка</button>}
      <button onClick={onExport} style={btnG}><Download size={14}/>Excel</button>
      {showLeadership && (
        <button onClick={onToggleTemplate} style={selectedEstimate.isTemplate ? {...btnO,backgroundColor:'#facc15',color:'#1f2937'} : btnG}>
          ⭐ {selectedEstimate.isTemplate ? 'Шаблон' : 'В шаблон'}
        </button>
      )}
      <button onClick={onHistory} style={btnG}>📜 История</button>
      {showLeadership && <button onClick={onNormalize} style={btnGr}>🧹 Нормализовать импорт</button>}
      <button onClick={onOpenChat} style={{...btnB,backgroundColor:'#0ea5e9'}}><MessageSquare size={14}/>Чат</button>
      {showLeadership && <button onClick={onOpenWorkAssignment} style={{...btnO,backgroundColor:'#16a34a'}}><UserCheck size={14}/>Назначить мастеру</button>}
      {showLeadership && <button onClick={onOpenDistribute} style={btnG}><Users size={14}/>Расширенное</button>}
      <button onClick={onAiAnalysis} style={{...btnB,backgroundColor:'#10b981',color:'white',borderColor:'#059669'}}><Bot size={14}/>ИИ Анализ</button>
      <button onClick={onDetectHiddenWorks} style={btnB}><Bot size={14}/>Найти работы для АОСР</button>
    </div>
  );
}

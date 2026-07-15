import React, { useEffect, useRef, useState } from 'react';
import { AlertTriangle, ArrowLeft, Bot, Download, Eye, FileText, GitBranch, MoreHorizontal, UserCheck, Users } from 'lucide-react';
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
  const [moreOpen, setMoreOpen] = useState(false);
  const moreMenuRef = useRef(null);

  useEffect(() => {
    if (!moreOpen) return undefined;

    const closeOnOutsideClick = (event) => {
      if (!moreMenuRef.current?.contains(event.target)) setMoreOpen(false);
    };
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setMoreOpen(false);
    };

    document.addEventListener('mousedown', closeOnOutsideClick);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('mousedown', closeOnOutsideClick);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [moreOpen]);

  const runMenuAction = (action) => {
    setMoreOpen(false);
    action?.();
  };
  const menuItemStyle = {
    ...btnG,
    width: '100%',
    justifyContent: 'flex-start',
    border: 'none',
    backgroundColor: 'transparent',
    color: C.text,
    textAlign: 'left'
  };
  const issuesStyle = {
    ...(showEstimateIssuesOnly ? btnO : btnB),
    backgroundColor: showEstimateIssuesOnly ? C.danger : C.bg,
    color: showEstimateIssuesOnly ? 'white' : C.danger,
    borderColor: C.dangerBorder
  };

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
      {issueCount > 0 && (
        <button onClick={onToggleIssuesOnly} style={issuesStyle}>
          <AlertTriangle aria-hidden="true" size={14}/>Проблемы: {issueCount}
        </button>
      )}
      <button onClick={onPreview} style={btnB}><Eye size={14}/>Просмотр</button>
      {showLeadership && (
        <button onClick={onOpenWorkAssignment} style={{...btnO,backgroundColor:'#16a34a'}}>
          <UserCheck size={14}/>Назначить работы
        </button>
      )}
      <div ref={moreMenuRef} style={{position:'relative'}}>
        <button
          aria-expanded={moreOpen}
          aria-haspopup="menu"
          onClick={() => setMoreOpen((open) => !open)}
          style={btnG}
        >
          <MoreHorizontal aria-hidden="true" size={16}/>Ещё
        </button>
        {moreOpen && (
          <div
            role="menu"
            style={{
              position:'absolute',
              top:'calc(100% + 6px)',
              right:0,
              zIndex:30,
              display:'grid',
              gap:'2px',
              width:'260px',
              maxWidth:'calc(100vw - 32px)',
              padding:'6px',
              border:`1px solid ${C.border || '#334155'}`,
              borderRadius:'8px',
              backgroundColor:C.bgWhite || C.bg || '#fff',
              boxShadow:'0 12px 30px rgba(15, 23, 42, 0.22)'
            }}
          >
            <EstimateSelectedStatusActions
              selectedEstimate={selectedEstimate}
              btnGr={menuItemStyle}
              btnG={menuItemStyle}
              setEstimateStatusRemote={(estimate, status) => runMenuAction(() => setEstimateStatusRemote?.(estimate, status))}
              showLeadership={showLeadership}
            />
            {hasDiff && (
              <button onClick={() => runMenuAction(onShowDiff)} style={menuItemStyle}>
                <FileText size={14}/>Сопоставительная ведомость
              </button>
            )}
            {hasDiff && onCreateReconciliation && (
              <button onClick={() => runMenuAction(onCreateReconciliation)} style={menuItemStyle}>
                <GitBranch size={14}/>Создать сверку
              </button>
            )}
            <button onClick={() => runMenuAction(onExport)} style={menuItemStyle}><Download size={14}/>Excel</button>
            {showLeadership && (
              <button onClick={() => runMenuAction(onToggleTemplate)} style={menuItemStyle}>
                ⭐ {selectedEstimate.isTemplate ? 'Шаблон' : 'Добавить в шаблоны'}
              </button>
            )}
            <button onClick={() => runMenuAction(onHistory)} style={menuItemStyle}>📜 История</button>
            {showLeadership && (
              <button onClick={() => runMenuAction(onNormalize)} style={menuItemStyle}>🧹 Нормализовать импорт</button>
            )}
            {showLeadership && (
              <button onClick={() => runMenuAction(onOpenDistribute)} style={menuItemStyle}>
                <Users size={14}/>Расширенное распределение
              </button>
            )}
            <button onClick={() => runMenuAction(onAiAnalysis)} style={menuItemStyle}><Bot size={14}/>ИИ-анализ</button>
            <button onClick={() => runMenuAction(onDetectHiddenWorks)} style={menuItemStyle}>
              <Bot size={14}/>Найти работы для АОСР
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

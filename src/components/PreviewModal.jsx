import React, {useLayoutEffect, useMemo, useRef, useState} from 'react';
import { Printer, X } from 'lucide-react';
import {sanitizeDocumentHtml} from '../utils/safeHtml';
import { journalScopeKey } from '../hooks/useJournalMutation';
import { PREVIEW_INVALIDATED } from '../hooks/usePreviewInvalidation';
import { getQualityJournalRevision, QUALITY_JOURNAL_MUTATED } from '../utils/qualityJournalEvents';

export default function PreviewModal({content, title, onClose, onPrint}) {
  const [opened] = useState(() => ({ scope: journalScopeKey(), revision: getQualityJournalRevision() }));
  const [blocked, setBlocked] = useState(false);
  const invalid = useRef(false);
  const close = useRef(onClose);
  close.current = onClose;
  const stale = opened.scope !== journalScopeKey() || opened.revision !== getQualityJournalRevision();
  useLayoutEffect(() => {
    const invalidate = () => {
      invalid.current = true;
      setBlocked(true);
      close.current?.();
    };
    const storageChanged = () => {
      if (opened.scope !== journalScopeKey()) invalidate();
    };
    if (stale) invalidate();
    window.addEventListener(QUALITY_JOURNAL_MUTATED, invalidate);
    window.addEventListener(PREVIEW_INVALIDATED, invalidate);
    window.addEventListener('storage', storageChanged);
    return () => {
      window.removeEventListener(QUALITY_JOURNAL_MUTATED, invalidate);
      window.removeEventListener(PREVIEW_INVALIDATED, invalidate);
      window.removeEventListener('storage', storageChanged);
    };
  }, [opened, stale]);
  const print = () => {
    if (invalid.current || opened.scope !== journalScopeKey() || opened.revision !== getQualityJournalRevision()) {
      invalid.current = true;
      setBlocked(true);
      close.current?.();
      return;
    }
    onPrint?.(safeContent);
  };
  const safeContent = useMemo(
    () => sanitizeDocumentHtml(content),
    [content],
  );

  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.6)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:3000}}>
      <div style={{backgroundColor:'white',borderRadius:'16px',width:'820px',maxWidth:'95%',maxHeight:'90vh',display:'flex',flexDirection:'column',boxShadow:'0 20px 60px rgba(0,0,0,0.2)'}}>
        <div style={{padding:'16px 24px',borderBottom:'1px solid #e5e7eb',display:'flex',justifyContent:'space-between',alignItems:'center',backgroundColor:'#f9fafb',borderRadius:'16px 16px 0 0'}}>
          <b style={{color:'#111827',fontSize:'15px'}}>{'📄 '+title}</b>
          <div style={{display:'flex',gap:'10px'}}>
            <button disabled={blocked || stale} onClick={print} style={{padding:'8px 20px',background:'linear-gradient(135deg,#f97316,#ea580c)',color:'white',border:'none',borderRadius:'8px',cursor:'pointer',fontSize:'14px',fontWeight:'600',display:'flex',alignItems:'center',gap:'6px'}}>
              <Printer size={14}/>Распечатать
            </button>
            <button onClick={onClose} style={{padding:'8px 16px',backgroundColor:'#6b7280',color:'white',border:'none',borderRadius:'8px',cursor:'pointer',display:'flex',alignItems:'center',gap:'6px'}}>
              <X size={14}/>Закрыть
            </button>
          </div>
        </div>
        <div style={{flex:1,overflowY:'auto',padding:'24px',backgroundColor:'white',borderRadius:'0 0 16px 16px',colorScheme:'light'}}>
          {blocked || stale
            ? <div role="alert">Предпросмотр устарел. Обновите данные и сформируйте документ заново.</div>
            : <div style={{fontFamily:'Arial',fontSize:'12px',lineHeight:'1.6',color:'#111827'}} dangerouslySetInnerHTML={{__html:safeContent}}/>}
        </div>
      </div>
    </div>
  );
}

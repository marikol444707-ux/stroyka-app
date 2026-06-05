import React from 'react';
import { RefreshCw, X } from 'lucide-react';

function SystemStatusModal({
  show,
  systemStatus,
  systemStatusLoading,
  onRefresh,
  onClose,
  C,
  badge,
  btnG,
}) {
  if (!show) return null;

  const apiErrors = systemStatus?.apiErrors || [];
  const recentAudit = systemStatus?.recentAudit || [];

  const cellBorder = (index, list) => index < list.length - 1 ? '1px solid ' + C.border : 'none';
  const headerCell = {
    padding: '8px 10px',
    textAlign: 'left',
    color: C.textSec,
    borderBottom: '1px solid ' + C.border,
  };

  return (
    <div onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }} style={{position:'fixed',inset:0,backgroundColor:'rgba(0,0,0,0.55)',zIndex:1710,display:'flex',alignItems:'center',justifyContent:'center',padding:'18px'}}>
      <div style={{backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,borderRadius:'18px',boxShadow:'0 14px 55px rgba(0,0,0,0.35)',width:'min(760px,96vw)',maxHeight:'88vh',overflowY:'auto'}}>
        <div style={{padding:'18px 20px',borderBottom:'1.5px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center',gap:'12px'}}>
          <div><h3 style={{margin:0,color:C.text,fontSize:'18px'}}>Статус системы</h3><p style={{margin:'4px 0 0',color:C.textSec,fontSize:'12px'}}>{systemStatus?.time||'—'}</p></div>
          <div style={{display:'flex',gap:'8px',alignItems:'center'}}>
            <span style={badge(systemStatusLoading?C.warning:(systemStatus?.ok?C.success:C.danger),systemStatusLoading?C.warningLight:(systemStatus?.ok?C.successLight:C.dangerLight),systemStatusLoading?C.warningBorder:(systemStatus?.ok?C.successBorder:C.dangerBorder))}>{systemStatusLoading?'Проверяю':(systemStatus?.ok?'OK':'Ошибка')}</span>
            <button onClick={onRefresh} disabled={systemStatusLoading} style={{...btnG,padding:'6px 10px',opacity:systemStatusLoading?0.6:1}}><RefreshCw size={13}/></button>
            <button onClick={onClose} style={{...btnG,padding:'6px 10px'}}><X size={14}/></button>
          </div>
        </div>
        <div style={{padding:'18px 20px'}}>
          {systemStatusLoading&&!systemStatus&&<p style={{color:C.textSec,margin:0}}>Загружаю статус...</p>}
          {systemStatus&&(<>
            <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(150px,1fr))',gap:'10px',marginBottom:'14px'}}>
              {[['Backend',systemStatus.ok?'работает':'ошибка'],['БД',systemStatus.db?.ok?'OK':'ошибка'],['S3',systemStatus.storage?.s3Configured?'подключён':'не настроен'],['Версия',systemStatus.version||'—']].map(([k,v])=><div key={k} style={{padding:'12px',borderRadius:'10px',backgroundColor:C.bg,border:'1.5px solid '+C.border}}><p style={{margin:0,color:C.textSec,fontSize:'11px',fontWeight:'700',textTransform:'uppercase'}}>{k}</p><b style={{display:'block',marginTop:'5px',color:C.text,fontSize:'14px'}}>{v}</b></div>)}
            </div>
            <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(120px,1fr))',gap:'8px',marginBottom:'14px'}}>
              {Object.entries(systemStatus.counts||{}).map(([k,v])=><div key={k} style={{padding:'10px 12px',borderRadius:'10px',backgroundColor:C.bg,border:'1px solid '+C.border}}><p style={{margin:0,color:C.textSec,fontSize:'11px'}}>{k}</p><b style={{color:C.text,fontSize:'16px'}}>{v}</b></div>)}
            </div>
            <div style={{padding:'12px',borderRadius:'10px',backgroundColor:C.bg,border:'1.5px solid '+C.border,marginBottom:'14px'}}>
              <b style={{color:C.text,fontSize:'13px'}}>Хранилище</b>
              <p style={{margin:'6px 0 0',color:C.textSec,fontSize:'12px'}}>{'backend: '+(systemStatus.storage?.backend||'—')+' · prefix: '+(systemStatus.storage?.prefix||'—')+' · лимит: '+(systemStatus.storage?.maxUploadMb||0)+' МБ'}</p>
            </div>
            <div style={{borderRadius:'10px',border:'1.5px solid '+C.border,overflow:'hidden',marginBottom:'14px'}}>
              <div style={{padding:'10px 12px',backgroundColor:C.bg,borderBottom:'1px solid '+C.border,display:'flex',justifyContent:'space-between',gap:'10px',alignItems:'center'}}>
                <b style={{color:C.text,fontSize:'13px'}}>API ошибки</b>
                <span style={badge(apiErrors.length?C.danger:C.success,apiErrors.length?C.dangerLight:C.successLight,apiErrors.length?C.dangerBorder:C.successBorder)}>{apiErrors.length?'Последние '+apiErrors.length:'Нет 500'}</span>
              </div>
              {apiErrors.length===0?<p style={{padding:'12px',margin:0,color:C.textMuted,fontSize:'12px'}}>Свежих серверных 500-ошибок нет.</p>:(
                <div style={{overflowX:'auto'}}>
                  <table style={{width:'100%',borderCollapse:'collapse',minWidth:'820px',fontSize:'11px'}}>
                    <thead><tr>
                      <th style={headerCell}>Время</th>
                      <th style={headerCell}>Код</th>
                      <th style={headerCell}>Метод</th>
                      <th style={headerCell}>Путь</th>
                      <th style={headerCell}>Пользователь</th>
                      <th style={headerCell}>Ошибка</th>
                    </tr></thead>
                    <tbody>{apiErrors.map((e,i)=><tr key={e.id||i}>
                      <td style={{padding:'8px 10px',borderBottom:cellBorder(i, apiErrors),color:C.textSec,whiteSpace:'nowrap'}}>{e.createdAt||'—'}</td>
                      <td style={{padding:'8px 10px',borderBottom:cellBorder(i, apiErrors),color:C.danger,fontWeight:'800'}}>{e.statusCode||500}</td>
                      <td style={{padding:'8px 10px',borderBottom:cellBorder(i, apiErrors),color:C.text,fontWeight:'700'}}>{e.method||'—'}</td>
                      <td style={{padding:'8px 10px',borderBottom:cellBorder(i, apiErrors),color:C.text,wordBreak:'break-word'}}>{e.path||'—'}</td>
                      <td style={{padding:'8px 10px',borderBottom:cellBorder(i, apiErrors),color:C.textSec}}>{(e.user||'—')+(e.role?' · '+e.role:'')}</td>
                      <td title={e.message||''} style={{padding:'8px 10px',borderBottom:cellBorder(i, apiErrors),color:C.textSec,wordBreak:'break-word'}}><b style={{color:C.text}}>{e.errorType||'—'}</b>{e.message?' · '+e.message:''}</td>
                    </tr>)}</tbody>
                  </table>
                </div>
              )}
            </div>
            <div style={{borderRadius:'10px',border:'1.5px solid '+C.border,overflow:'hidden'}}>
              <div style={{padding:'10px 12px',backgroundColor:C.bg,borderBottom:'1px solid '+C.border}}><b style={{color:C.text,fontSize:'13px'}}>Последние события</b></div>
              {recentAudit.length===0?<p style={{padding:'12px',margin:0,color:C.textMuted,fontSize:'12px'}}>Событий нет</p>:recentAudit.map((a,i)=><div key={i} style={{padding:'10px 12px',borderBottom:cellBorder(i, recentAudit)}}><b style={{color:C.text,fontSize:'12px'}}>{a.action||'—'}</b><p style={{margin:'3px 0 0',color:C.textSec,fontSize:'11px'}}>{(a.user||'—')+' · '+(a.entityType||'—')+' · '+(a.createdAt||'')}</p>{a.description&&<p style={{margin:'3px 0 0',color:C.textMuted,fontSize:'11px'}}>{a.description}</p>}</div>)}
            </div>
          </>)}
        </div>
      </div>
    </div>
  );
}

export default SystemStatusModal;

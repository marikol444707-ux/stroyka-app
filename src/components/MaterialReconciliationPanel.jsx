import React from 'react';
import { Printer } from 'lucide-react';

export default function MaterialReconciliationPanel({
  projectName,
  options = {},
  C,
  card,
  btnB,
  tbl,
  tblH,
  tblC,
  badge,
  fmtMeasure,
  materialControlSummaryForProject,
  materialControlStatus,
  renderMaterialAliasControls,
  renderMaterialSupplyAction,
  showPreview,
  buildMaterialRequirementContent,
  isFinanceRole,
  isLeadership,
  user,
}) {
  const limit = options.limit || 25;
  const title = options.title || '📊 Материалы: смета ↔ поставки ↔ склад';
  const summary = materialControlSummaryForProject(projectName);
  const showMoney = isFinanceRole() || isLeadership() || ['кладовщик','снабженец','прораб','главный_инженер'].includes(user?.role);

  return (
    <div style={{...card,padding:'14px',marginBottom:'14px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.accentBorder}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px',flexWrap:'wrap',marginBottom:'12px'}}>
        <div>
          <b style={{color:C.text,fontSize:'14px'}}>{title}</b>
          <p style={{color:C.textSec,fontSize:'11px',margin:'2px 0 0'}}>План из активных смет; факт из заявок, поставок, накладных, перемещений, выдач и списаний.</p>
        </div>
        <button onClick={()=>showPreview(buildMaterialRequirementContent(projectName),'Потребность материалов — '+projectName)} style={{...btnB,fontSize:'12px',padding:'6px 12px'}}><Printer size={13}/>Печать</button>
      </div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(120px,1fr))',gap:'8px',marginBottom:'12px'}}>
        <div style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1px solid '+C.border}}><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>По смете</p><b style={{color:C.text,fontSize:'15px'}}>{summary.planRows.length}</b></div>
        <div style={{padding:'10px',backgroundColor:C.successLight,borderRadius:'8px',border:'1px solid '+C.successBorder}}><p style={{color:C.success,fontSize:'10px',margin:'0 0 3px'}}>Поставлялось</p><b style={{color:C.success,fontSize:'15px'}}>{summary.suppliedRows.length}</b></div>
        <div style={{padding:'10px',backgroundColor:summary.invoiceRows.length?C.infoLight:C.bg,borderRadius:'8px',border:'1px solid '+(summary.invoiceRows.length?C.infoBorder:C.border)}}><p style={{color:summary.invoiceRows.length?C.info:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>Накладные</p><b style={{color:summary.invoiceRows.length?C.info:C.text,fontSize:'15px'}}>{summary.invoiceRows.length}</b></div>
        <div style={{padding:'10px',backgroundColor:summary.deliveryRows.length?C.successLight:C.bg,borderRadius:'8px',border:'1px solid '+(summary.deliveryRows.length?C.successBorder:C.border)}}><p style={{color:summary.deliveryRows.length?C.success:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>Поставки</p><b style={{color:summary.deliveryRows.length?C.success:C.text,fontSize:'15px'}}>{summary.deliveryRows.length}</b></div>
        <div style={{padding:'10px',backgroundColor:summary.movedRows.length?C.infoLight:C.bg,borderRadius:'8px',border:'1px solid '+(summary.movedRows.length?C.infoBorder:C.border)}}><p style={{color:summary.movedRows.length?C.info:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>Перемещения</p><b style={{color:summary.movedRows.length?C.info:C.text,fontSize:'15px'}}>{summary.movedRows.length}</b></div>
        <div style={{padding:'10px',backgroundColor:summary.masterBalanceRows.length?C.infoLight:C.bg,borderRadius:'8px',border:'1px solid '+(summary.masterBalanceRows.length?C.infoBorder:C.border)}}><p style={{color:summary.masterBalanceRows.length?C.info:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>У мастеров</p><b style={{color:summary.masterBalanceRows.length?C.info:C.text,fontSize:'15px'}}>{summary.masterBalanceRows.length}</b></div>
        <div style={{padding:'10px',backgroundColor:summary.toBuyRows.length?C.warningLight:C.successLight,borderRadius:'8px',border:'1px solid '+(summary.toBuyRows.length?C.warningBorder:C.successBorder)}}><p style={{color:summary.toBuyRows.length?C.warning:C.success,fontSize:'10px',margin:'0 0 3px'}}>Докупить</p><b style={{color:summary.toBuyRows.length?C.warning:C.success,fontSize:'15px'}}>{summary.toBuyRows.length}</b></div>
        <div style={{padding:'10px',backgroundColor:summary.outsideRows.length?C.dangerLight:C.bg,borderRadius:'8px',border:'1px solid '+(summary.outsideRows.length?C.dangerBorder:C.border)}}><p style={{color:summary.outsideRows.length?C.danger:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>Вне сметы</p><b style={{color:summary.outsideRows.length?C.danger:C.text,fontSize:'15px'}}>{summary.outsideRows.length}</b></div>
        <div style={{padding:'10px',backgroundColor:summary.mismatchRows.length?C.warningLight:C.bg,borderRadius:'8px',border:'1px solid '+(summary.mismatchRows.length?C.warningBorder:C.border)}}><p style={{color:summary.mismatchRows.length?C.warning:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>Ед. изм.</p><b style={{color:summary.mismatchRows.length?C.warning:C.text,fontSize:'15px'}}>{summary.mismatchRows.length}</b></div>
        <div style={{padding:'10px',backgroundColor:summary.stockMismatchRows.length?C.dangerLight:C.bg,borderRadius:'8px',border:'1px solid '+(summary.stockMismatchRows.length?C.dangerBorder:C.border)}}><p style={{color:summary.stockMismatchRows.length?C.danger:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>Расхождения</p><b style={{color:summary.stockMismatchRows.length?C.danger:C.text,fontSize:'15px'}}>{summary.stockMismatchRows.length}</b></div>
        {showMoney&&<div style={{padding:'10px',backgroundColor:C.infoLight,borderRadius:'8px',border:'1px solid '+C.infoBorder}}><p style={{color:C.info,fontSize:'10px',margin:'0 0 3px'}}>План ₽</p><b style={{color:C.info,fontSize:'15px'}}>{Math.round(summary.planSum).toLocaleString('ru-RU')}</b></div>}
      </div>
      {summary.rows.length===0?<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'14px'}}>Нет сметных материалов и движений по объекту.</p>:<div style={{overflowX:'auto'}}>
        <table style={{...tbl,fontSize:'11px',minWidth:'1420px'}}><thead><tr><th style={tblH}>Материал</th><th style={tblH}>План</th><th style={tblH}>В заявках</th><th style={tblH}>В пути</th><th style={tblH}>Накладные</th><th style={tblH}>Поставки</th><th style={tblH}>Перемещено</th><th style={tblH}>Всего получено</th><th style={tblH}>Выдано</th><th style={tblH}>Списано</th><th style={tblH}>У мастеров</th><th style={tblH}>Остаток</th><th style={tblH}>Расчёт</th><th style={tblH}>Расх.</th><th style={tblH}>Докупить</th><th style={tblH}>Статус</th></tr></thead><tbody>
          {summary.rows.slice(0,limit).map(row=>{const status=materialControlStatus(row);return(<tr key={row.key}>
            <td style={tblC}><b style={{fontSize:'12px'}}>{row.name}</b>{row.planSourceCount>1&&<p style={{color:C.textMuted,fontSize:'10px',margin:'2px 0 0'}}>Сгруппировано из {row.planSourceCount} строк сметы</p>}{row.sections.length>0&&<p style={{color:C.textMuted,fontSize:'10px',margin:'2px 0 0'}}>{row.sections.slice(0,2).join(', ')}{row.sections.length>2?'…':''}</p>}{row.workRefs?.length>0&&<p style={{color:C.accent,fontSize:'10px',margin:'2px 0 0'}}>Работы: {row.workRefs.slice(0,2).join('; ')}{row.workRefs.length>2?'…':''}</p>}{row.aliases?.length>0&&<p style={{color:C.info,fontSize:'10px',margin:'2px 0 0'}}>Синонимы: {row.aliases.slice(0,2).join(', ')}{row.aliases.length>2?'…':''}</p>}{row.unitMismatch&&<p style={{color:C.warning,fontSize:'10px',margin:'2px 0 0'}}>⚠️ Разные единицы измерения</p>}{renderMaterialAliasControls(projectName,row)}</td>
            <td style={tblC}>{row.planQty>0?fmtMeasure(row.planQty,row.unit):'—'}</td>
            <td style={{...tblC,color:row.requested>0?C.info:C.textMuted}}>{fmtMeasure(row.requested,row.unit)}</td>
            <td style={{...tblC,color:row.inTransit>0?C.warning:C.textMuted}}>{fmtMeasure(row.inTransit,row.unit)}</td>
            <td style={{...tblC,color:row.invoiceReceived>0?C.success:C.textMuted}}>{fmtMeasure(row.invoiceReceived,row.unit)}</td>
            <td style={{...tblC,color:row.supplyReceived>0?C.success:C.textMuted}}>{fmtMeasure(row.supplyReceived,row.unit)}</td>
            <td style={{...tblC,color:row.movedNet!==0?C.info:C.textMuted}}>{fmtMeasure(row.movedNet,row.unit)}</td>
            <td style={{...tblC,color:row.supplied>=row.planQty&&row.planQty>0?C.success:C.text}}>{fmtMeasure(row.supplied,row.unit)}</td>
            <td style={tblC}>{fmtMeasure(row.issued,row.unit)}</td>
            <td style={tblC}>{fmtMeasure(row.used,row.unit)}</td>
            <td style={{...tblC,color:row.masterBalance>0?C.info:C.textMuted}}>{fmtMeasure(row.masterBalance,row.unit)}</td>
            <td style={{...tblC,fontWeight:'600',color:row.stock>0?C.success:C.textMuted}}>{fmtMeasure(row.stock,row.unit)}</td>
            <td style={{...tblC,color:row.expectedStock>0?C.text:C.textMuted}}>{fmtMeasure(row.expectedStock,row.unit)}</td>
            <td style={{...tblC,fontWeight:'700',color:row.stockMismatch?C.danger:C.success}}>{row.stockMismatch?fmtMeasure(row.stockDiff,row.unit):'0'}</td>
            <td style={{...tblC,fontWeight:'700',color:row.toBuy>0?C.warning:C.success}}>{fmtMeasure(row.toBuy,row.unit)}</td>
            <td style={tblC}><span style={badge(status.color,status.bg,status.border)}>{status.label}{row.stockMismatch?' · '+fmtMeasure(row.stockDiff,row.unit):row.toBuy>0?' · '+fmtMeasure(row.toBuy,row.unit):row.shortage>0?' · '+fmtMeasure(row.shortage,row.unit):row.masterBalance>0?' · '+fmtMeasure(row.masterBalance,row.unit):''}</span>{renderMaterialSupplyAction(projectName,row)}</td>
          </tr>);})}
        </tbody></table>
        {summary.rows.length>limit&&<p style={{color:C.textMuted,fontSize:'11px',margin:'8px 0 0'}}>Показаны первые {limit} строк. Полный список — в печатной ведомости.</p>}
      </div>}
    </div>
  );
}

import React from 'react';
import { Bot, FileText } from 'lucide-react';

export default function EstimateVersionHistoryModal({
  showVersionHistory,
  setShowVersionHistory,
  selectedEstimate,
  estimateVersions,
  selectedVersionsToCompare,
  setSelectedVersionsToCompare,
  isMobile,
  C,
  card,
  btnB,
  btnG,
  btnO,
  API,
  user,
  setSelectedEstimate,
  setEstimatesList,
  showPreview,
  buildEstimateDiffContent,
  estimateItemTotal,
  setShowAiChat,
  setAiMessages,
  setAiLoading,
}) {
  if (!showVersionHistory || !selectedEstimate) return null;

  const restoreVersion = async (v) => {
    if(!window.confirm('Восстановить эту версию? Текущие данные будут сохранены как новая запись в истории.')) return;
    const ver=await fetch(API+'/estimate-version/'+v.id).then(r=>r.json());
    if(ver&&ver.sections){
      const updated={...selectedEstimate,sections:ver.sections};
      await fetch(API+'/estimates/'+selectedEstimate.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...updated,versionComment:'Восстановление из v'+(v.versionLabel||''),updatedBy:user.name})});
      setSelectedEstimate(updated);
      setEstimatesList(prev=>prev.map(e=>e.id===updated.id?updated:e));
      setShowVersionHistory(false);
      alert('Версия восстановлена');
    }
  };

  const loadPair = async () => {
    const [aId,bId]=selectedVersionsToCompare;
    return Promise.all([fetch(API+'/estimate-version/'+aId).then(r=>r.json()),fetch(API+'/estimate-version/'+bId).then(r=>r.json())]);
  };

  const printDiff = async () => {
    const [a,b]=await loadPair();
    const [older,newer]=[a,b].sort((x,y)=>(new Date(x.createdAt||0).getTime()-new Date(y.createdAt||0).getTime())||(Number(x.id||0)-Number(y.id||0)));
    const base={...selectedEstimate,name:'Версия '+(older.versionLabel||'?'),version:older.versionLabel,status:'История',createdAt:older.createdAt,sections:older.sections||[]};
    const next={...selectedEstimate,name:'Версия '+(newer.versionLabel||'?'),version:newer.versionLabel,status:'История',createdAt:newer.createdAt,sections:newer.sections||[]};
    setShowVersionHistory(false);
    showPreview(buildEstimateDiffContent(base,next),'Сопоставительная ведомость версий');
  };

  const compareWithAi = async () => {
    const pair=await loadPair();
    const [a,b]=pair.sort((x,y)=>(new Date(x.createdAt||0).getTime()-new Date(y.createdAt||0).getTime())||(Number(x.id||0)-Number(y.id||0)));
    const totalOf=(secs)=>secs.flatMap(s=>s.items||[]).reduce((sum,i)=>sum+estimateItemTotal(i),0);
    const flatten=(secs)=>secs.flatMap(s=>(s.items||[]).map(i=>({section:s.name,name:i.name,unit:i.unit,qty:Number(i.quantity||0),work:Number(i.priceWork||0),mat:Number(i.priceMaterial||0),sum:estimateItemTotal(i)})));
    const payload={a:{label:a.versionLabel,total:totalOf(a.sections||[]),items:flatten(a.sections||[])},b:{label:b.versionLabel,total:totalOf(b.sections||[]),items:flatten(b.sections||[])}};
    const prompt='Сравни две версии сметы. Версия A (старая) и B (новая). Данные:\n'+JSON.stringify(payload,null,1)+'\n\nОТВЕТЬ СТРОГО JSON:\n{"summary":"одной фразой что произошло (стало дороже/дешевле и насколько)","changes":[{"what":"конкретная позиция или раздел","kind":"добавлена|удалена|объём|цена","detail":"что изменилось","impact":число_в_рублях}]}\nИспользуй только данные.';
    setShowVersionHistory(false);
    setShowAiChat(true);
    setAiMessages([{role:'user',content:'Сравнение версий v'+a.versionLabel+' ↔ v'+b.versionLabel}]);
    setAiLoading(true);
    try{
      const res=await fetch(API+'/ai-chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[{role:'user',content:prompt}],jsonOnly:true})});
      const data=await res.json();
      const raw=(data.response||data.error||'').trim();
      let parsed=null;
      try{const clean=raw.replace(/^```(?:json)?/i,'').replace(/```$/,'').trim();const s=clean.indexOf('{'),e=clean.lastIndexOf('}');if(s>=0&&e>s) parsed=JSON.parse(clean.slice(s,e+1));}catch(e){}
      let out;
      if(parsed){
        const ln=[];
        if(parsed.summary) ln.push('📋 '+parsed.summary,'');
        if(Array.isArray(parsed.changes)&&parsed.changes.length){ln.push('🔍 ИЗМЕНЕНИЯ');parsed.changes.forEach((c,n)=>ln.push((n+1)+'. ['+(c.kind||'?')+'] '+(c.what||'?')+': '+(c.detail||'')+(c.impact?' ('+(c.impact>0?'+':'')+Number(c.impact).toLocaleString('ru-RU')+' ₽)':'')));}
        out=ln.join('\n');
      }else out=raw||'Ошибка';
      setAiMessages([{role:'user',content:'Сравнение v'+a.versionLabel+' ↔ v'+b.versionLabel},{role:'assistant',content:out}]);
    }catch(e){setAiMessages(prev=>[...prev,{role:'assistant',content:'Ошибка соединения'}]);}
    setAiLoading(false);
  };

  return (
    <div onClick={()=>setShowVersionHistory(false)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:600,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div onClick={e=>e.stopPropagation()} className='mobile-modal' style={{...card,padding:'20px',width:'520px',margin:'20px',maxHeight:'85vh',overflowY:'auto'}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'14px'}}>
          <b style={{color:C.text,fontSize:'15px'}}>📜 История версий: {selectedEstimate.name}</b>
          <button onClick={()=>setShowVersionHistory(false)} style={{background:'none',border:'none',cursor:'pointer',fontSize:'18px',color:C.textSec}}>×</button>
        </div>
        {estimateVersions.length===0?(<p style={{color:C.textMuted,fontSize:'13px',padding:'20px',textAlign:'center'}}>История пуста. Снимки сохраняются автоматически при сохранении изменений сметы.</p>):(
          <>
            <p style={{color:C.textSec,fontSize:'12px',marginBottom:'10px'}}>Отметьте 2 версии, чтобы распечатать разницу или сравнить через ИИ:</p>
            <div style={{maxHeight:'320px',overflowY:'auto',marginBottom:'12px'}}>
              {estimateVersions.map(v=>{const sel=selectedVersionsToCompare.includes(v.id);return(
                <div key={v.id} style={{padding:'10px',marginBottom:'6px',borderRadius:'8px',border:'1.5px solid '+(sel?C.accent:C.border),backgroundColor:sel?C.accentLight:C.bg,display:'flex',alignItems:'center',gap:'10px'}}>
                  <input type='checkbox' checked={sel} onChange={e=>{if(e.target.checked){if(selectedVersionsToCompare.length<2)setSelectedVersionsToCompare([...selectedVersionsToCompare,v.id]);}else{setSelectedVersionsToCompare(selectedVersionsToCompare.filter(id=>id!==v.id));}}} style={{width:'16px',height:'16px',accentColor:C.accent}}/>
                  <div style={{flex:1}}>
                    <b style={{fontSize:'12px',color:C.text}}>v{v.versionLabel||'?'} — {Number(v.total||0).toLocaleString('ru-RU')} ₽</b>
                    <p style={{fontSize:'11px',color:C.textSec,margin:'2px 0'}}>{new Date(v.createdAt).toLocaleString('ru-RU')}{v.createdBy?' · '+v.createdBy:''}</p>
                    {v.comment&&<p style={{fontSize:'11px',color:C.textMuted,margin:'2px 0'}}>{v.comment}</p>}
                  </div>
                  <button onClick={()=>restoreVersion(v)} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}>↶ Восстановить</button>
                </div>
              );})}
            </div>
            {selectedVersionsToCompare.length===2&&(
              <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'1fr 1fr',gap:'8px'}}>
                <button onClick={printDiff} style={{...btnB,width:'100%',justifyContent:'center'}}><FileText size={14}/>Печать ведомости</button>
                <button onClick={compareWithAi} style={{...btnO,backgroundColor:'#10b981',width:'100%',justifyContent:'center'}}><Bot size={14}/>🤖 Сравнить через ИИ</button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

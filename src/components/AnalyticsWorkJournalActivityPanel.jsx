import React from 'react';

export default function AnalyticsWorkJournalActivityPanel({C, card, tbl, tblH, tblC, badge, workJournal}) {
  return (
    <div style={{...card,padding:'20px'}}>
      <h4 style={{color:C.text,marginBottom:'15px',fontSize:'14px',fontWeight:'700'}}>Активность журнала работ</h4>
      <table style={tbl}>
        <thead>
          <tr>
            <th style={tblH}>Мастер</th>
            <th style={tblH}>Работ</th>
            <th style={tblH}>Сумма</th>
            <th style={tblH}>Подтверждено</th>
          </tr>
        </thead>
        <tbody>
          {[...new Set(workJournal.map(j=>j.masterName))].map(name=>{
            const mWorks = workJournal.filter(j=>j.masterName===name);
            const confirmed = mWorks.filter(j=>j.status==='Подтверждено');
            return (
              <tr key={name}>
                <td style={tblC}>{name}</td>
                <td style={tblC}>{mWorks.length}</td>
                <td style={{...tblC,fontWeight:'600',color:C.success}}>{mWorks.reduce((s,w)=>s+(w.total||0),0).toLocaleString()+' ₽'}</td>
                <td style={tblC}><span style={badge(C.success,C.successLight,C.successBorder)}>{confirmed.length+'/'+mWorks.length}</span></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

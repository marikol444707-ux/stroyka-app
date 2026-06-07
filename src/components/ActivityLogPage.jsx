import React from 'react';

export default function ActivityLogPage({C, tbl, tblH, tblC, activityLog, roleLabels}) {
  return (
    <div>
      <h3 style={{color:C.text,marginBottom:'20px',fontSize:'16px',fontWeight:'700'}}>Журнал активности</h3>
      <table style={tbl}>
        <thead>
          <tr>
            <th style={tblH}>Действие</th>
            <th style={tblH}>Пользователь</th>
            <th style={tblH}>Роль</th>
            <th style={tblH}>Время</th>
          </tr>
        </thead>
        <tbody>
          {activityLog.map((e,i)=>(
            <tr key={i}>
              <td style={tblC}>{e.action}</td>
              <td style={tblC}>{e.user}</td>
              <td style={tblC}>{roleLabels[e.role]||e.role}</td>
              <td style={tblC}>{e.time}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {activityLog.length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Журнал пуст</p>}
    </div>
  );
}

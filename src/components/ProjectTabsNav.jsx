import React from 'react';

const canSeeJournalReconcileRole = (role) => ['директор','зам_директора','бухгалтер','прораб','главный_инженер','сметчик'].includes(role);

const projectTabGroupsForRole = (role) => {
  const canSeeJournalReconcile = canSeeJournalReconcileRole(role);
  if (role === 'прораб') {
    return [
      {id:'work',icon:'🔨',label:'Работы',tabs:['Расчёт с бригадой','Изменения к смете',...(canSeeJournalReconcile?['Сверка ЖПР']:[]),'Чек-листы','Смета']},
      {id:'object',icon:'🏗️',label:'Объект',tabs:['Общее','ИИ-контроль','Проект / Обмеры','Помещения','График','Этапы','Материалы']},
      {id:'journals',icon:'📚',label:'Журналы',tabs:['Главный','Производство работ','АОСР','Входной контроль','Кабельная продукция','Журнал ТБ','Погода','Предписания','Чат']},
      {id:'docs',icon:'📋',label:'Документы',tabs:['📁 Реестр','✉️ Переписка','Акты технадзора','Замечания ГСН','Гарантия']},
    ];
  }
  return [
    {id:'work',icon:'🔨',label:'Работы',tabs:['Расчёт с бригадой','Изменения к смете',...(canSeeJournalReconcile?['Сверка ЖПР']:[]),'Чек-листы']},
    {id:'finance',icon:'💰',label:'Финансы',tabs:['Финансы','Смета','Материалы']},
    {id:'object',icon:'🏗️',label:'Объект',tabs:['Общее','ИИ-контроль','Проект / Обмеры','Помещения','График','Этапы']},
    {id:'journals',icon:'📚',label:'Журналы',tabs:['Главный','Производство работ','АОСР','Входной контроль','Кабельная продукция','Журнал ТБ','Погода','Предписания','Чат']},
    {id:'docs',icon:'📋',label:'Документы',tabs:['📁 Реестр','✉️ Переписка','КС-2','КС-3','Паспорт','Акты технадзора','Замечания ГСН','Гарантия']},
  ];
};

function ProjectTabsNav({
  C,
  role,
  activeProjectTab,
  activeTabGroup,
  setActiveProjectTab,
  setActiveTabGroup,
}) {
  const tabGroups = projectTabGroupsForRole(role);
  const activeGroup = tabGroups.find(group=>group.tabs.includes(activeProjectTab));

  return (
    <div>
      <div style={{display:'grid',gridTemplateColumns:'repeat('+tabGroups.length+',1fr)',gap:'6px',marginBottom:'12px'}}>
        {tabGroups.map(group=>(
          <div
            key={group.id}
            onClick={()=>{setActiveTabGroup(activeTabGroup===group.id?null:group.id);if(group.tabs.length>0)setActiveProjectTab(group.tabs[0]);}}
            style={{padding:'12px 4px',borderRadius:'12px',cursor:'pointer',display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',gap:'4px',backgroundColor:activeGroup&&activeGroup.id===group.id?C.accentLight:C.bgWhite,border:'1.5px solid '+(activeGroup&&activeGroup.id===group.id?C.accentBorder:C.border),transition:'all 0.15s',minHeight:'72px'}}
          >
            <div style={{fontSize:'22px',lineHeight:1,display:'flex',alignItems:'center',justifyContent:'center'}}>{group.icon}</div>
            <div style={{fontSize:'11px',fontWeight:activeGroup&&activeGroup.id===group.id?'700':'500',color:activeGroup&&activeGroup.id===group.id?C.accent:C.textSec,textAlign:'center',lineHeight:1.2}}>{group.label}</div>
          </div>
        ))}
      </div>
      {activeGroup&&(
        <div style={{display:'flex',gap:'4px',overflowX:'auto',minHeight:'34px',alignItems:'center',paddingBottom:'2px'}}>
          {activeGroup.tabs.map(tab=>(
            <button key={tab} onClick={()=>setActiveProjectTab(tab)} style={{padding:'6px 12px',backgroundColor:activeProjectTab===tab?C.accent:C.bgWhite,cursor:'pointer',fontSize:'12px',fontWeight:activeProjectTab===tab?'700':'400',color:activeProjectTab===tab?'white':C.textSec,borderRadius:'20px',border:'1.5px solid '+(activeProjectTab===tab?C.accent:C.border),flexShrink:0,whiteSpace:'nowrap'}}>
              {tab}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export { projectTabGroupsForRole };
export default ProjectTabsNav;

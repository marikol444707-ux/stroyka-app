import React from 'react';
import { Check, CloudSun, Plus, ScrollText, X } from 'lucide-react';
import WeatherTabsNav from './WeatherTabsNav';

export default function WeatherPage({
  C,
  WEATHER_CONDITIONS,
  btnB,
  btnG,
  btnO,
  buildJPRContent,
  card,
  inp,
  newWeather,
  projects,
  saveWeather,
  setNewWeather,
  setShowForm,
  setWeatherTab,
  showForm,
  showPreview,
  weatherLog,
  weatherTab,
  workJournal,
}) {
  return (
    <div>
      <WeatherTabsNav weatherTab={weatherTab} setWeatherTab={setWeatherTab} btnO={btnO} btnG={btnG}/>

      {weatherTab==='log'&&(<div>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
          <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Журнал погоды</b>
          <button onClick={()=>setShowForm(!showForm)} style={btnO}><Plus size={14}/>Добавить запись</button>
        </div>
        {showForm&&(<div style={{...card,padding:'20px',marginBottom:'16px'}}>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
            <select value={newWeather.projectName} onChange={e=>setNewWeather({...newWeather,projectName:e.target.value})} style={{...inp,marginBottom:0}}><option value="">Выберите объект *</option>{projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}</select>
            <input type="date" value={newWeather.date} onChange={e=>setNewWeather({...newWeather,date:e.target.value})} style={{...inp,marginBottom:0}}/>
            <select value={newWeather.condition} onChange={e=>setNewWeather({...newWeather,condition:e.target.value})} style={{...inp,marginBottom:0}}>{WEATHER_CONDITIONS.map(w=><option key={w}>{w}</option>)}</select>
            <input placeholder="Температура (°C)" type="number" step="any" inputMode="decimal" value={newWeather.temperature} onChange={e=>setNewWeather({...newWeather,temperature:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="Скорость ветра (м/с)" type="number" step="any" inputMode="decimal" value={newWeather.windSpeed} onChange={e=>setNewWeather({...newWeather,windSpeed:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="Примечание" value={newWeather.notes} onChange={e=>setNewWeather({...newWeather,notes:e.target.value})} style={{...inp,marginBottom:0}}/>
          </div>
          <div style={{display:'flex',gap:'8px',marginTop:'12px'}}><button onClick={()=>{saveWeather();setShowForm(false);}} style={btnO}><Check size={14}/>Сохранить</button><button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button></div>
        </div>)}
        {projects.map(p=>{
          const pWeather=weatherLog.filter(w=>w.projectName===p.name).sort((a,b)=>b.date.localeCompare(a.date));
          if(pWeather.length===0) return null;
          return(<div key={p.id} style={{...card,marginBottom:'12px'}}>
            <div style={{padding:'12px 16px',backgroundColor:C.bg,borderBottom:'1.5px solid '+C.border}}><b style={{color:C.text,fontSize:'13px'}}>{'📍 '+p.name}</b></div>
            <div style={{padding:'12px 16px'}}>
              {pWeather.map(w=>(<div key={w.id} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'8px 0',borderBottom:'1px solid '+C.border}}>
                <div><b style={{fontSize:'13px',color:C.text}}>{w.date}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{w.condition+' · '+w.temperature+'°C · Ветер: '+w.windSpeed+' м/с'+(w.notes?' · '+w.notes:'')}</p></div>
                <span style={{fontSize:'24px'}}>{{Ясно:'☀️',Облачно:'⛅',Пасмурно:'☁️',Дождь:'🌧️',Снег:'❄️',Гроза:'⛈️',Туман:'🌫️',Ветер:'💨'}[w.condition]||'🌤️'}</span>
              </div>))}
            </div>
          </div>);
        })}
        {weatherLog.length===0&&<div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}><CloudSun size={48} style={{marginBottom:'15px',opacity:0.3}}/><p>Записей нет</p></div>}
      </div>)}

      {weatherTab==='jpr'&&(<div>
        <h3 style={{color:C.text,marginBottom:'15px',fontSize:'15px',fontWeight:'700'}}>Журнал производства работ</h3>
        {projects.map(p=>{const works=workJournal.filter(j=>j.project===p.name&&j.status==='Подтверждено');if(works.length===0) return null;return(<div key={p.id} style={{...card,padding:'14px',marginBottom:'10px',display:'flex',justifyContent:'space-between',alignItems:'center'}}><div><b style={{color:C.text,fontSize:'13px'}}>{p.name}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{works.length+' работ · '+works.reduce((s,w)=>s+(w.total||0),0).toLocaleString()+' ₽'}</p></div><button onClick={()=>showPreview(buildJPRContent(p.name),'ЖПР — '+p.name)} style={btnB}><ScrollText size={14}/>ЖПР</button></div>);})}
        {projects.every(p=>workJournal.filter(j=>j.project===p.name&&j.status==='Подтверждено').length===0)&&<div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}>Подтверждённых работ нет</div>}
      </div>)}
    </div>
  );
}

import React from 'react';
import { Bot, Plus, Search } from 'lucide-react';

const emptyGenerateEstimateForm = {
  description: '',
  projectId: '',
  projectName: '',
  pricelistId: '',
  area: '',
  name: '',
  version: '1.0',
  smetaType: 'Заказчик',
  workPackage: 'Основная',
  status: 'Активная',
};

export default function EstimatesListToolbar({
  C,
  btnB,
  btnO,
  inp,
  showForm,
  setShowForm,
  setGenerateForm,
  setShowGenerateEstimate,
  estimateSearch,
  setEstimateSearch,
  projectOptions = [],
  projectFilter = '',
  setProjectFilter = () => {},
  showLeadership = false,
}) {
  return (
    <>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'10px'}}>
        <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Сметы</b>
        <div style={{display:'flex',gap:'8px'}}>
          <button
            onClick={() => {
              setGenerateForm({...emptyGenerateEstimateForm, status: showLeadership ? 'Активная' : 'Черновик'});
              setShowGenerateEstimate(true);
            }}
            style={{...btnB,backgroundColor:'#10b981',color:'white',borderColor:'#059669'}}
          >
            <Bot size={14}/>🤖 Сгенерировать ИИ
          </button>
          <button onClick={() => setShowForm(!showForm)} style={btnO}>
            <Plus size={14}/>Новая смета
          </button>
        </div>
      </div>
      <div style={{marginBottom:'14px',display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(240px,1fr))',gap:'8px',alignItems:'center'}}>
        <select
          value={projectFilter||''}
          onChange={e=>setProjectFilter(e.target.value)}
          style={{...inp,marginBottom:0}}
          title="Фильтр смет по объекту"
        >
          <option value="">Все объекты</option>
          {projectOptions.map(projectName => (
            <option key={projectName} value={projectName}>{projectName}</option>
          ))}
        </select>
        <div style={{position:'relative'}}>
          <Search size={15} style={{position:'absolute',left:'12px',top:'50%',transform:'translateY(-50%)',color:C.textMuted}}/>
          <input
            placeholder='🔍 Поиск по позициям смет (например: «демонтаж», «штукатурка»…)'
            value={estimateSearch||''}
            onChange={e=>setEstimateSearch(e.target.value)}
            style={{...inp,marginBottom:0,paddingLeft:'34px'}}
          />
        </div>
      </div>
    </>
  );
}

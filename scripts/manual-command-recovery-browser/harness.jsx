import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import ProjectBrigadeCreateForm from '../../src/components/ProjectBrigadeCreateForm';
import WorkAssignmentModal from '../../src/features/work-assignment/WorkAssignmentModal';

// This fixture checks real components and browser storage with a simulated API.
// PostgreSQL/HTTP idempotency and authorization have separate backend tests.
const user = {id:9,role:'директор'};
const companyContext = {mode:'company',selectedCompanyId:4};
localStorage.setItem('user',JSON.stringify(user));
localStorage.setItem('stroyka.companyContext.v1.9',JSON.stringify({mode:'company',companyId:4}));
window.fetch = async (_url,init={}) => {
  const state = JSON.parse(localStorage.getItem('qa-server') || '{"bodies":[],"contract":null}');
  if (init.method === 'POST') {
    state.bodies.push(init.body);
    if (!state.contract) {
      const body = JSON.parse(init.body);
      const reference = body.contractorRef || body.assignee.contractorRef;
      state.contract = {ok:true,id:70,contractId:70,companyId:4,projectId:17,manualRequestId:reference.requestId};
      localStorage.setItem('qa-server',JSON.stringify(state));
      throw new TypeError('Fixture: response lost after simulated commit');
    }
    localStorage.setItem('qa-server',JSON.stringify(state));
    return {ok:true,json:async()=>state.contract};
  }
  return {ok:true,json:async()=>[{id:70,companyId:4,projectId:17,brigadeName:'Исходная бригада'}]};
};

function Harness() {
  const [draft,setDraft] = useState({brigadeName:'Новый черновик после загрузки',contractorId:'',contractorType:'Мастер',notes:''});
  const [done,setDone] = useState(false);
  const common = {user,companyContext,C:{},card:{},inp:{width:'100%',minWidth:0,boxSizing:'border-box'},btnO:{},btnG:{},btnB:{}};
  if (done) return <p role="status">Восстановление завершено</p>;
  return window.location.search.includes('assignment')
    ? <WorkAssignmentModal {...common} show API="/api" isMobile={window.innerWidth<600}
      selectedEstimate={{id:25,projectId:17,sections:[{name:'Монтаж',items:[{
        name:'Исходная работа',unit:'м',quantity:5,priceWork:100,estimateItemKey:'original-work',
      }]}]}} staff={[]} users={[]} onClose={()=>setDone(true)} loadAll={async()=>{}}/>
    : <ProjectBrigadeCreateForm {...common} project={{id:17,name:'Лицей'}}
      newBrigadeContract={draft} setNewBrigadeContract={setDraft}
      setBrigadeContracts={()=>{}} setSelectedBrigadeContract={()=>{}} openBrigadeContract={()=>{}}
      setBrigadeContractItems={()=>{}} setBrigadePayments={()=>{}}
      setShowBrigadeForm={show=>{if(!show)setDone(true);}}/>;
}

createRoot(document.getElementById('root')).render(<Harness/>);

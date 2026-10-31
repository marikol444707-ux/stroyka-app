import React, { useState } from 'react';
import { Check, X } from 'lucide-react';
import { API } from '../api';
import { useManualCommandRecovery } from '../features/work-assignment/manualCommandRecovery';
import ManualCommandRecoveryNotice from '../features/work-assignment/ManualCommandRecoveryNotice';

const emptyBrigadeContract = () => ({
  projectId: '',
  projectName: '',
  brigadeName: '',
  contractorType: 'Своя бригада',
  contractorId: '',
  notes: '',
  pricelistId: '',
});

export default function ProjectBrigadeCreateForm({
  companyContext,
  user,
  project,
  brigadeContracts = [],
  newBrigadeContract,
  setNewBrigadeContract,
  staff = [],
  pricelists = [],
  setBrigadeContracts,
  setSelectedBrigadeContract,
  openBrigadeContract,
  setBrigadeContractItems,
  setBrigadePayments,
  setShowBrigadeForm,
  card,
  inp,
  btnO,
  btnG,
}) {
  const [saving, setSaving] = useState(false);
  const [existingContractId, setExistingContractId] = useState('');
  const recovery = useManualCommandRecovery({API,user,companyContext,kind:'contract',
    source:{id:project.id,companyId:project.companyId,workPackage:newBrigadeContract.workPackage}});
  const finishForm = () => {setShowBrigadeForm(false);setNewBrigadeContract(emptyBrigadeContract());};
  const applyManual = async(saved,_payload,current) => {
    const response=await fetch(API+'/brigade-contracts',{credentials:'include',headers:{
      'X-Company-Mode':'company','X-Company-Id':String(recovery.scope.companyId)}});
    const list=await response.json().catch(()=>null);
    if(!current()) return;
    const contract=response.ok && Array.isArray(list) ? list.find(item=>item.id===saved.id
      && item.companyId===saved.companyId && item.projectId===saved.projectId) : null;
    if(!contract) throw new Error('Договор сохранён, но список не обновился. Повторите обновление списка.');
    return {contract,current};
  };
  const completeManual=(_saved,_payload,{contract,current})=>{
    if(!current())return;
    setBrigadeContracts(previous=>current()?[...previous.filter(item=>item.id!==contract.id),contract]:previous);
    if(typeof openBrigadeContract==='function') openBrigadeContract(contract);
    else setSelectedBrigadeContract(contract);
    finishForm();
  };
  const selectedStaff=staff.find(item=>String(item.id)===String(newBrigadeContract.contractorId));
  const availableContracts = brigadeContracts.filter(contract => Number(contract.projectId) === Number(project.id)
    && !['Аннулирован','Удалён','Удален'].includes(contract.status)
    && String(contract.workPackage || 'Основная') === String(newBrigadeContract.workPackage || 'Основная'));
  const existingContract = availableContracts.find(contract => String(contract.id) === existingContractId);
  const createBrigadeContract = async () => {
    if (saving) return;
    if (recovery.pending || recovery.busy || recovery.blocked) return;
    if (!existingContract && !String(newBrigadeContract.brigadeName || '').trim()) return;
    if(existingContractId&&!existingContract){alert('Обновите список и выберите договор заново');return;}
    if(!existingContract&&newBrigadeContract.contractorId&&!selectedStaff){alert('Обновите список и выберите карточку исполнителя заново');return;}
    setSaving(true);
    try {
      const data = {
        ...newBrigadeContract,
        projectId: project.id,
        projectName: project.name,
        brigadeName: existingContract?.brigadeName || newBrigadeContract.brigadeName,
        contractorId: existingContract ? existingContract.contractorId ?? null : selectedStaff ? newBrigadeContract.contractorId : null,
        contractorRef: existingContract ? {type:'contract',id:Number(existingContract.id)}
          : selectedStaff ? {type:'staff',id:Number(selectedStaff.id)}
          : {type:'manual'},
      };
      if (!existingContract && !selectedStaff) {
        await recovery.run({payload:data,apply:applyManual,done:completeManual});
        return;
      }
      const res = await fetch(API + '/brigade-contracts', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data),
      });
      const saved = await res.json().catch(() => ({}));
      if (!res.ok || !saved.ok || !saved.id) {
        throw new Error(saved.detail || 'проверьте компанию, объект и исполнителя');
      }
      if (saved.reused) {
        const listResponse = await fetch(API + '/brigade-contracts');
        const latest = await listResponse.json().catch(() => []);
        const existing = listResponse.ok && Array.isArray(latest)
          ? latest.find(contract => Number(contract.id) === Number(saved.id)) : null;
        if (!existing) throw new Error('Договор уже есть, но не удалось открыть его. Обновите страницу');
        setBrigadeContracts(prev => [...prev.filter(contract => Number(contract.id) !== Number(saved.id)), existing]);
        if (typeof openBrigadeContract === 'function') openBrigadeContract(existing);
        else setSelectedBrigadeContract(existing);
      } else {
        const newContract = {
          ...data,
          contractorId:saved.contractorId??null,
          id: saved.id,
          companyId: saved.companyId,
          projectId: saved.projectId || project.id,
          totalAmount: 0,
          status: 'Черновик',
          items: [],
        };
        setBrigadeContracts(prev => [...prev, newContract]);
        setSelectedBrigadeContract(newContract);
        setBrigadeContractItems([]);
        setBrigadePayments([]);
      }
      setShowBrigadeForm(false);
      setNewBrigadeContract(emptyBrigadeContract());
    } catch (error) {
      alert('Не удалось создать договор: ' + (error.message || 'проверьте соединение'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{...card, padding: '20px', marginBottom: '16px'}}>
      <ManualCommandRecoveryNotice pending={recovery.pending} busy={recovery.busy}
        onResume={()=>recovery.run({apply:applyManual,done:completeManual})}/>
      {recovery.error && <p role="alert">{recovery.error}</p>}
      <fieldset disabled={saving || recovery.busy || Boolean(recovery.pending) || recovery.blocked} style={{border:0,padding:0,margin:0,minWidth:0}}>
      {availableContracts.length > 0 && <label>Существующий договор
        <select aria-label="Существующий договор" value={existingContractId} onChange={event=>setExistingContractId(event.target.value)} style={inp}>
          <option value="">Создать новый</option>
          {availableContracts.map(contract=><option key={contract.id} value={contract.id}>{contract.brigadeName} · договор №{contract.id}</option>)}
        </select>
      </label>}
      <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px'}}>
        <select value={newBrigadeContract.contractorType} onChange={e => setNewBrigadeContract({...newBrigadeContract, contractorType: e.target.value})} style={{...inp, marginBottom: 0}}>
          {['Своя бригада', 'Субподрядчик', 'Мастер', 'ГПХ', 'Самозанятый', 'ИП', 'ООО', 'Трудовой договор'].map(t => <option key={t}>{t}</option>)}
        </select>
        <input placeholder="Название / ФИО *" value={newBrigadeContract.brigadeName} onChange={e => setNewBrigadeContract({...newBrigadeContract, brigadeName: e.target.value})} style={{...inp, marginBottom: 0}}/>
        <select value={newBrigadeContract.contractorId} onChange={e => {const val=e.target.value;const st=staff.find(s=>String(s.id)===String(val));setNewBrigadeContract({...newBrigadeContract, contractorId: val, brigadeName: st?.name || newBrigadeContract.brigadeName, contractorType: st?.employmentType || newBrigadeContract.contractorType});}} style={{...inp, marginBottom: 0}}>
          <option value="">Привязать к карточке исполнителя</option>
          {staff.map(s => <option key={s.id} value={s.id}>{s.name}{s.employmentType ? ' · ' + s.employmentType : ''}{s.specialization ? ' · ' + s.specialization : ''}</option>)}
        </select>
        <select value={newBrigadeContract.pricelistId || ''} onChange={e => setNewBrigadeContract({...newBrigadeContract, pricelistId: e.target.value})} style={{...inp, marginBottom: 0}}>
          <option value="">🏷️ Прайс бригады (по умолчанию — прайс объекта)</option>
          {pricelists.map(pl => <option key={pl.id} value={pl.id}>{pl.name}{pl.forWho ? ' (' + pl.forWho + ')' : ''}</option>)}
        </select>
        <textarea placeholder="Примечание" value={newBrigadeContract.notes} onChange={e => setNewBrigadeContract({...newBrigadeContract, notes: e.target.value})} style={{...inp, marginBottom: 0, height: '60px'}}/>
      </div>
      {!existingContract && !selectedStaff && <p role="status">Бригада без аккаунта. Доступ к программе не выдаётся.</p>}
      {existingContract && <p role="status">Выбран договор №{existingContract.id}. Доступ будет проверен при открытии.</p>}
      <div style={{display: 'flex', gap: '8px', marginTop: '12px'}}>
        <button onClick={createBrigadeContract} disabled={saving || recovery.busy || Boolean(recovery.pending) || recovery.blocked} style={btnO}><Check size={14}/>{saving ? 'Сохраняем…' : existingContract ? 'Открыть договор' : 'Создать договор'}</button>
        <button onClick={() => setShowBrigadeForm(false)} style={btnG}><X size={14}/>Отмена</button>
      </div>
      </fieldset>
      {recovery.pending && <button type="button" disabled={recovery.busy} onClick={()=>setShowBrigadeForm(false)} style={btnG}>Закрыть — отправка сохранится</button>}
    </div>
  );
}

import React, { useRef, useState } from 'react';
import { Check, X } from 'lucide-react';
import { API } from '../api';
import { commandUuid } from '../utils/commandUuid';

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
  const manualRequestRef = useRef(null);
  const selectedStaff=staff.find(item=>String(item.id)===String(newBrigadeContract.contractorId));
  const availableContracts = brigadeContracts.filter(contract => Number(contract.projectId) === Number(project.id)
    && !['Аннулирован','Удалён','Удален'].includes(contract.status)
    && String(contract.workPackage || 'Основная') === String(newBrigadeContract.workPackage || 'Основная'));
  const existingContract = availableContracts.find(contract => String(contract.id) === existingContractId);
  const createBrigadeContract = async () => {
    if (saving) return;
    if (!existingContract && !String(newBrigadeContract.brigadeName || '').trim()) return;
    if(existingContractId&&!existingContract){alert('Обновите список и выберите договор заново');return;}
    if(!existingContract&&newBrigadeContract.contractorId&&!selectedStaff){alert('Обновите список и выберите карточку исполнителя заново');return;}
    setSaving(true);
    try {
      const scope = JSON.stringify([project.companyId,project.id,newBrigadeContract.workPackage || 'Основная']);
      if (!existingContract && !selectedStaff && manualRequestRef.current?.scope !== scope) {
        manualRequestRef.current = {scope,requestId:commandUuid()};
      }
      const data = {
        ...newBrigadeContract,
        projectId: project.id,
        projectName: project.name,
        brigadeName: existingContract?.brigadeName || newBrigadeContract.brigadeName,
        contractorId: existingContract ? existingContract.contractorId ?? null : selectedStaff ? newBrigadeContract.contractorId : null,
        contractorRef: existingContract ? {type:'contract',id:Number(existingContract.id)}
          : selectedStaff ? {type:'staff',id:Number(selectedStaff.id)}
          : {type:'manual',requestId:manualRequestRef.current.requestId},
      };
      const res = await fetch(API + '/brigade-contracts', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data),
      });
      const saved = await res.json().catch(() => ({}));
      if (!res.ok || !saved.ok || !saved.id) {
        if ([400,422].includes(res.status)) manualRequestRef.current = null;
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
      manualRequestRef.current = null;
      setNewBrigadeContract(emptyBrigadeContract());
    } catch (error) {
      alert('Не удалось создать договор: ' + (error.message || 'проверьте соединение'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{...card, padding: '20px', marginBottom: '16px'}}>
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
        <button onClick={createBrigadeContract} disabled={saving} style={btnO}><Check size={14}/>{saving ? 'Сохраняем…' : existingContract ? 'Открыть договор' : 'Создать договор'}</button>
        <button onClick={() => setShowBrigadeForm(false)} style={btnG}><X size={14}/>Отмена</button>
      </div>
    </div>
  );
}

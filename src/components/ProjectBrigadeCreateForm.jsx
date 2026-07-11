import React from 'react';
import { Check, X } from 'lucide-react';
import { API } from '../api';

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
  newBrigadeContract,
  setNewBrigadeContract,
  staff = [],
  pricelists = [],
  setBrigadeContracts,
  setSelectedBrigadeContract,
  setBrigadeContractItems,
  setBrigadePayments,
  setShowBrigadeForm,
  card,
  inp,
  btnO,
  btnG,
}) {
  const createBrigadeContract = async () => {
    if (!newBrigadeContract.brigadeName) return;

    const data = {
      ...newBrigadeContract,
      projectId: project.id,
      projectName: project.name,
    };
    const res = await fetch(API + '/brigade-contracts', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data),
    });
    const saved = await res.json();
    if (!res.ok || !saved.ok || !saved.id) {
      alert('Не удалось создать договор: ' + (saved.detail || 'проверьте компанию, объект и исполнителя'));
      return;
    }
    const newContract = {
      ...data,
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
    setShowBrigadeForm(false);
    setNewBrigadeContract(emptyBrigadeContract());
  };

  return (
    <div style={{...card, padding: '20px', marginBottom: '16px'}}>
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
      <div style={{display: 'flex', gap: '8px', marginTop: '12px'}}>
        <button onClick={createBrigadeContract} style={btnO}><Check size={14}/>Создать</button>
        <button onClick={() => setShowBrigadeForm(false)} style={btnG}><X size={14}/>Отмена</button>
      </div>
    </div>
  );
}

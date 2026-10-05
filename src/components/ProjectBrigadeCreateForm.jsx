import React, { useState } from 'react';
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
  const normalizedName = String(newBrigadeContract.brigadeName || '').trim().toLocaleLowerCase('ru-RU');
  const existingContract = normalizedName && brigadeContracts.find(contract => contract.projectName === project.name
    && contract.status !== 'Аннулирован'
    && String(contract.workPackage || 'Основная') === String(newBrigadeContract.workPackage || 'Основная')
    && (newBrigadeContract.contractorId && contract.contractorId
      ? String(contract.contractorId) === String(newBrigadeContract.contractorId)
      : String(contract.brigadeName || '').trim().toLocaleLowerCase('ru-RU') === normalizedName));
  const createBrigadeContract = async () => {
    if (saving) return;
    if (!newBrigadeContract.brigadeName) return;
    if (existingContract) {
      if (typeof openBrigadeContract === 'function') openBrigadeContract(existingContract);
      else setSelectedBrigadeContract(existingContract);
      setShowBrigadeForm(false);
      return;
    }

    const data = {
      ...newBrigadeContract,
      projectId: project.id,
      projectName: project.name,
    };
    setSaving(true);
    try {
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
      {existingContract && <p role="status" style={{margin:'12px 0 0',fontSize:'13px'}}>У этого исполнителя уже есть договор по объекту. Откройте его и добавьте работы туда.</p>}
      <div style={{display: 'flex', gap: '8px', marginTop: '12px'}}>
        <button onClick={createBrigadeContract} disabled={saving} style={btnO}><Check size={14}/>{saving ? 'Сохраняем…' : existingContract ? 'Открыть договор' : 'Создать договор'}</button>
        <button onClick={() => setShowBrigadeForm(false)} style={btnG}><X size={14}/>Отмена</button>
      </div>
    </div>
  );
}

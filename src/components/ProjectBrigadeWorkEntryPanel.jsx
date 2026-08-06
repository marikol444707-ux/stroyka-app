import React from 'react';
import { Plus } from 'lucide-react';
import { API } from '../api';

const emptyBrigadeItem = (workPackage = 'Основная') => ({
  name: '',
  unit: 'м',
  quantity: '',
  priceSmeta: '',
  priceBrigade: '',
  estimateSection: '',
  workPackage,
  estimateItemKey: '',
});

export default function ProjectBrigadeWorkEntryPanel({
  selectedBrigadeContract,
  newBrigadeItem,
  setNewBrigadeItem,
  setBrigadeContractItems,
  UNITS = [],
  C,
  card,
  inp,
  btnO,
  showLeadership = false,
}) {
  if (!showLeadership) return null;
  const contractPackage = selectedBrigadeContract?.workPackage || selectedBrigadeContract?.work_package || '';
  const itemWorkPackage = contractPackage || newBrigadeItem.workPackage || 'Основная';
  const workPackageOptions = [itemWorkPackage];

  const addManualItem = async () => {
    if (!newBrigadeItem.name || !selectedBrigadeContract) return;

    const item = {
      ...newBrigadeItem,
      workPackage: itemWorkPackage,
      contractId: selectedBrigadeContract.id,
      doneQuantity: 0,
      status: 'Не начато',
    };
    const res = await fetch(API + '/brigade-contract-items', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(item),
    });
    const saved = await res.json();
    setBrigadeContractItems(prev => [...prev, {...item, id: saved.id}]);
    setNewBrigadeItem(emptyBrigadeItem(itemWorkPackage));
  };

  return (
    <div style={{...card, padding: '16px', marginBottom: '16px'}}>
      <b style={{color: C.text, fontSize: '13px', display: 'block', marginBottom: '10px'}}>Добавить работу вручную</b>
      <div style={{display: 'grid', gridTemplateColumns: '3fr 1.2fr 1fr 1fr 1fr 1fr auto', gap: '6px', alignItems: 'center'}}>
        <input placeholder="Наименование *" value={newBrigadeItem.name} onChange={e => setNewBrigadeItem({...newBrigadeItem, name: e.target.value})} style={{...inp, marginBottom: 0, fontSize: '12px'}}/>
        <select value={newBrigadeItem.workPackage || 'Основная'} onChange={e => setNewBrigadeItem({...newBrigadeItem, workPackage: e.target.value})} style={{...inp, marginBottom: 0, fontSize: '12px'}}>
          {workPackageOptions.map(workPackage => <option key={workPackage} value={workPackage}>{workPackage}</option>)}
        </select>
        <select value={newBrigadeItem.unit} onChange={e => setNewBrigadeItem({...newBrigadeItem, unit: e.target.value})} style={{...inp, marginBottom: 0, fontSize: '12px'}}>
          {UNITS.map(unit => <option key={unit}>{unit}</option>)}
        </select>
        <input placeholder="Объём" type="number" step="any" inputMode="decimal" value={newBrigadeItem.quantity} onChange={e => setNewBrigadeItem({...newBrigadeItem, quantity: e.target.value})} style={{...inp, marginBottom: 0, fontSize: '12px'}}/>
        <input placeholder="Цена смета" type="number" step="any" inputMode="decimal" value={newBrigadeItem.priceSmeta} onChange={e => setNewBrigadeItem({...newBrigadeItem, priceSmeta: e.target.value})} style={{...inp, marginBottom: 0, fontSize: '12px'}}/>
        <input placeholder="Цена бригаде" type="number" step="any" inputMode="decimal" value={newBrigadeItem.priceBrigade} onChange={e => setNewBrigadeItem({...newBrigadeItem, priceBrigade: e.target.value})} style={{...inp, marginBottom: 0, fontSize: '12px'}}/>
        <button onClick={addManualItem} style={{...btnO, padding: '7px 12px'}}><Plus size={13}/></button>
      </div>
    </div>
  );
}

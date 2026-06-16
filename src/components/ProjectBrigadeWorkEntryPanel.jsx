import React from 'react';
import { Plus } from 'lucide-react';
import { API } from '../api';

const MATERIAL_WORDS = [
  'кабель', 'провод', 'труба', 'трубы', 'лоток', 'короб', 'розетка', 'выключатель', 'светильник', 'щит', 'шина',
  'соединитель', 'кронштейн', 'уголок', 'переходник', 'консоль', 'держатель', 'болт', 'гайка', 'дюбель',
  'профиль', 'плита', 'панель', 'муфта', 'тройник', 'отвод', 'клапан', 'вентиль', 'кран', 'датчик',
  'грунтовка', 'клей', 'раствор', 'смесь', 'краска', 'лак', 'герметик', 'пена', 'мастика', 'шпатлевка',
  'плитка', 'кирпич', 'утеплитель', 'пленка', 'анкер', 'саморез', 'скоба', 'хомут', 'проволока',
  'изолятор', 'автомат', 'рубильник', 'реле', 'счетчик',
];

const WORK_WORDS = [
  'устройство', 'монтаж', 'прокладка', 'установка', 'разборка', 'пробивка', 'сверление', 'окраска',
  'штукатурка', 'кладка', 'демонтаж', 'погрузка', 'перевозка', 'очистка', 'покрытие', 'изоляция',
  'сборка', 'укладка', 'ремонт', 'снятие', 'затаривание', 'огрунтовка', 'добавлять', 'исключать',
  'смена', 'третья шпатлевка', 'вторая шпатлевка',
];

const emptyBrigadeItem = () => ({
  name: '',
  unit: 'м',
  quantity: '',
  priceSmeta: '',
  priceBrigade: '',
  estimateSection: '',
  workPackage: 'Основная',
  estimateItemKey: '',
});

const estimateIcon = (smetaType) => ({
  Заказчик: '📋',
  Работы: '👷',
  Материалы: '📦',
}[smetaType] || '📄');

const estimatePackageName = (estimate) => estimate?.workPackage || estimate?.work_package || 'Основная';

const getEstimateItems = (estimate) => (
  estimate.sections || []
).flatMap((section, sectionIndex) => (
  section.items || []
).map((item, itemIndex) => ({
  ...item,
  estimateSection: section.name,
  workPackage: estimatePackageName(estimate),
  estimateItemKey: item.estimateItemKey || item.estimate_item_key || (String(estimate.id || '') + ':' + sectionIndex + ':' + itemIndex),
})));

const isWorkItem = (item) => {
  const name = (item.name || '').toLowerCase();
  const unit = item.unit || '';

  if (unit === '%') return false;
  if (MATERIAL_WORDS.some(word => name.startsWith(word))) return false;

  return WORK_WORDS.some(word => name.includes(word));
};

export default function ProjectBrigadeWorkEntryPanel({
  project,
  selectedBrigadeContract,
  estimatesList = [],
  newBrigadeItem,
  setNewBrigadeItem,
  setBrigadeContractItems,
  UNITS = [],
  C,
  card,
  inp,
  btnG,
  btnO,
  showLeadership = false,
}) {
  if (!showLeadership) return null;
  const contractPackage = selectedBrigadeContract?.workPackage || selectedBrigadeContract?.work_package || '';
  const projectEstimates = estimatesList.filter(estimate => (
    (estimate.projectName === project.name || estimate.projectId === project.id) &&
    (!contractPackage || estimatePackageName(estimate) === contractPackage)
  ));
  const workPackageOptions = Array.from(new Set([
    ...projectEstimates.map(estimatePackageName),
    newBrigadeItem.workPackage || '',
    'Основная',
  ].filter(Boolean)));

  const loadEstimateItems = async (estimate) => {
    if (!selectedBrigadeContract) return;

    const rawItems = getEstimateItems(estimate);
    if (!window.confirm('Загрузить ' + rawItems.length + ' позиций из сметы ' + estimate.name + '?')) return;

    const workItems = rawItems.filter(isWorkItem);
    for (const item of workItems) {
      const newItem = {
        contractId: selectedBrigadeContract.id,
        estimateSection: item.estimateSection || '',
        name: item.name,
        unit: item.unit,
        quantity: item.quantity || 0,
        priceSmeta: item.priceWork || 0,
        priceBrigade: 0,
        workPackage: item.workPackage || 'Основная',
        estimateItemKey: item.estimateItemKey || '',
        doneQuantity: 0,
        status: 'Не начато',
      };
      const res = await fetch(API + '/brigade-contract-items', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(newItem),
      });
      const saved = await res.json();
      setBrigadeContractItems(prev => [...prev, {...newItem, id: saved.id}]);
    }

    alert('Загружено!');
  };

  const addManualItem = async () => {
    if (!newBrigadeItem.name || !selectedBrigadeContract) return;

    const item = {
      ...newBrigadeItem,
      workPackage: newBrigadeItem.workPackage || (workPackageOptions[0] || 'Основная'),
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
    setNewBrigadeItem(emptyBrigadeItem());
  };

  return (
    <div style={{...card, padding: '16px', marginBottom: '16px'}}>
      <div style={{marginBottom: '12px'}}>
        {projectEstimates.length > 0 && (
          <div>
            <p style={{color: C.textSec, fontSize: '12px', marginBottom: '6px'}}>Загрузить из сметы:</p>
            <div style={{display: 'flex', gap: '6px', flexWrap: 'wrap'}}>
              {projectEstimates.map(estimate => (
                <button
                  key={estimate.id}
                  onClick={() => loadEstimateItems(estimate)}
                  style={{...btnG, fontSize: '11px', padding: '5px 10px'}}
                >
                  {estimateIcon(estimate.smetaType)} {estimate.name}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
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

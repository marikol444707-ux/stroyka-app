// Synthetic browser fixture. No real authentication, documents or production API.
import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import OwnedAliasEditor from '../../src/features/material-control/OwnedAliasEditor';

function Preview() {
  const [company, setCompany] = useState(2);
  const [role, setRole] = useState('директор');
  const project = {id: company === 2 ? 7 : 8, companyId: company, name: 'Школа'};
  return <main><h1>Проверка справочника материалов</h1><p>Только синтетические данные. Ничего не отправляется в рабочую платформу.</p>
    <label>Компания <select value={company} onChange={e => setCompany(Number(e.target.value))}><option value={2}>Компания А</option><option value={3}>Компания Б</option></select></label>{' '}
    <label>Роль <select value={role} onChange={e => setRole(e.target.value)}><option>директор</option><option>бухгалтер</option></select></label>{' '}
    <button onClick={() => fetch('/fixture-concurrent-edit?companyId='+company, {method: 'POST'})}>Изменение другим сотрудником</button>
    <h2>Объектный справочник</h2>
    <OwnedAliasEditor key={company+role} API="" project={project}
      companyContext={{mode: 'company', selectedCompanyId: company, selectedCompany: {companyId: company, companyName: company === 2 ? 'Компания А' : 'Компания Б', role, membershipId: company, source: 'membership', active: true, companyActive: true}}}/>
  </main>;
}
createRoot(document.getElementById('root')).render(<Preview/>);

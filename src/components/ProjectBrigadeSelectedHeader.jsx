import React from 'react';
import { ArrowLeft, Check, Download, Eye } from 'lucide-react';
import { API } from '../api';
import { buildPerformerContractHtml } from '../utils/contractTemplates';

export default function ProjectBrigadeSelectedHeader({
  projectName,
  selectedBrigadeContract,
  setSelectedBrigadeContract,
  brigadeContractItems = [],
  setBrigadeContractItems,
  setBrigadeContracts,
  setBrigadePayments,
  showPreview,
  companyRequisites,
  companyName,
  C,
  btnG,
  btnO,
  btnB,
}) {
  const closeContract = () => {
    setSelectedBrigadeContract(null);
    setBrigadeContractItems([]);
    setBrigadePayments([]);
  };

  const signContract = async () => {
    const signedAt = new Date().toISOString().split('T')[0];
    const signedContract = {...selectedBrigadeContract, status: 'Подписан', signedAt};

    await fetch(API + '/brigade-contracts/' + selectedBrigadeContract.id, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(signedContract),
    });
    setSelectedBrigadeContract(signedContract);
    setBrigadeContracts(prev => prev.map(bc => bc.id === selectedBrigadeContract.id ? signedContract : bc));
  };

  const showContract = () => {
    const total = brigadeContractItems.reduce((sum, item) => sum + item.quantity * item.priceBrigade, 0);
    const html = buildPerformerContractHtml({
      company: companyRequisites && companyRequisites.fullName ? companyRequisites : companyName,
      performer: {
        fullName: selectedBrigadeContract.brigadeName,
      },
      contract: {
        ...selectedBrigadeContract,
        id: selectedBrigadeContract.id,
        contractNumber: selectedBrigadeContract.contractNumber || 'БР-' + selectedBrigadeContract.id,
        contractType: selectedBrigadeContract.contractorType,
        project: projectName,
        projectName,
        totalAmount: total || selectedBrigadeContract.totalAmount || selectedBrigadeContract.planAmount || 0,
      },
      items: brigadeContractItems,
    });

    showPreview(html, 'Договор');
  };

  const loadFromPricelist = async () => {
    const res = await fetch(API + '/brigade-contracts/' + selectedBrigadeContract.id + '/load-from-pricelist', {method: 'POST'});
    const data = await res.json();

    if (!res.ok || !data.ok) {
      alert('Ошибка: ' + (data.detail || 'не удалось'));
      return;
    }

    const items = await fetch(API + '/brigade-contract-items/' + selectedBrigadeContract.id).then(r => r.json());
    setBrigadeContractItems(items);
    alert('Загружено позиций: ' + data.itemsLoaded + (data.matchedFromEstimate ? '\nОбъёмы взяты из сметы: ' + data.matchedFromEstimate : ''));
  };

  return (
    <div style={{display: 'flex', gap: '8px', marginBottom: '15px', alignItems: 'center', flexWrap: 'wrap'}}>
      <button onClick={closeContract} style={btnG}><ArrowLeft size={14}/>Назад</button>
      <b style={{color: C.text, fontSize: '14px'}}>{selectedBrigadeContract.brigadeName}</b>
      <span style={{padding: '3px 8px', borderRadius: '6px', fontSize: '11px', backgroundColor: C.accentLight, color: C.accent}}>
        {selectedBrigadeContract.contractorType}
      </span>
      {selectedBrigadeContract.status !== 'Подписан' && (
        <button onClick={signContract} style={btnO}><Check size={14}/>Подписать</button>
      )}
      <button onClick={showContract} style={btnB}><Eye size={14}/>Договор</button>
      {selectedBrigadeContract.pricelistId && (
        <button onClick={loadFromPricelist} style={{border: 'none', borderRadius: '10px', padding: '8px 16px', cursor: 'pointer', background: 'linear-gradient(135deg, #10b981, #059669)', color: 'white', fontWeight: '600', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', boxShadow: '0 2px 8px rgba(16,185,129,0.3)'}}>
          <Download size={14}/>Подгрузить из прайса
        </button>
      )}
    </div>
  );
}

import React from 'react';
import { Eye, Plus, ScrollText, Trash2, Upload } from 'lucide-react';
import { API } from '../api';

export default function ProjectBrigadeActPaymentPanel({
  project,
  selectedBrigadeContract,
  brigadeContractItems = [],
  brigadePayments = [],
  showFinance = false,
  userName = '',
  setNewBrigadePayment,
  setShowBrigadePayModal,
  setSelectedBrigadeContract,
  setBrigadeContracts,
  deleteBrigadePayment,
  showPreview,
  uploadPhoto,
  fileSrc,
  C,
  card,
  btnO,
  btnG,
  btnB,
  btnR,
}) {
  const due = Math.round(brigadeContractItems.reduce((sum, item) => sum + Number(item.doneQuantity || 0) * Number(item.priceBrigade || 0), 0));
  const paid = Math.round((brigadePayments || []).reduce((sum, payment) => sum + Number(payment.amount || 0), 0));
  const owe = Math.max(0, due - paid);
  const brigadeTotal = brigadeContractItems.reduce((sum, item) => sum + Math.round(item.doneQuantity * item.priceBrigade), 0);
  const economyTotal = brigadeContractItems.reduce((sum, item) => sum + Math.round(item.doneQuantity * (item.priceSmeta - item.priceBrigade)), 0);

  const showActPreview = () => {
    const items = brigadeContractItems.filter(item => item.doneQuantity > 0);
    if (!items.length) {
      alert('Нет выполненных работ');
      return;
    }

    const total = items.reduce((sum, item) => sum + Math.round(item.doneQuantity * item.priceBrigade), 0);
    const html = '<h2>АКТ ВЫПОЛНЕННЫХ РАБОТ</h2><p>Объект: ' + project.name + '</p><p>Исполнитель: ' + selectedBrigadeContract.brigadeName + '</p><table><tr><th>N</th><th>Наименование</th><th>Ед.</th><th>Выполнено</th><th>Цена</th><th>Сумма</th></tr>'
      + items.map((item, index) => '<tr><td>' + (index + 1) + '</td><td>' + item.name + '</td><td>' + item.unit + '</td><td>' + item.doneQuantity + '</td><td>' + Number(item.priceBrigade).toLocaleString() + '</td><td>' + Math.round(item.doneQuantity * item.priceBrigade).toLocaleString() + '</td></tr>').join('')
      + '<tr><td colspan=5><b>ИТОГО:</b></td><td><b>' + total.toLocaleString() + ' руб.</b></td></tr></table>';

    showPreview(html, 'Акт');
  };

  const uploadSignedAct = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const url = await uploadPhoto(file, {
      projectName: selectedBrigadeContract.projectName,
      context: 'brigade-contracts',
    });
    if (!url) return;

    await fetch(API + '/brigade-contracts/' + selectedBrigadeContract.id, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({...selectedBrigadeContract, actScanUrl: url}),
    });
    setSelectedBrigadeContract(prev => ({...prev, actScanUrl: url}));
    setBrigadeContracts(prev => prev.map(contract => (
      contract.id === selectedBrigadeContract.id ? {...contract, actScanUrl: url} : contract
    )));
  };

  const openPaymentModal = () => {
    setNewBrigadePayment({
      amount: String(owe > 0 ? owe : ''),
      paidBy: userName,
      paidDate: new Date().toISOString().split('T')[0],
      note: '',
    });
    setShowBrigadePayModal(true);
  };

  return (
    <>
      {brigadeContractItems.length > 0 && (
        <div style={{...card, padding: '16px', marginTop: '16px', backgroundColor: C.successLight, border: '1.5px solid ' + C.successBorder}}>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px'}}>
            <div><b style={{color: C.text, fontSize: '14px'}}>К оплате бригаде:</b></div>
            <div style={{textAlign: 'right'}}>
              <b style={{color: C.accent, fontSize: '18px', display: 'block'}}>{brigadeTotal.toLocaleString() + ' руб.'}</b>
              <b style={{color: C.success, fontSize: '13px'}}>{'+' + economyTotal.toLocaleString() + ' руб. экономия'}</b>
            </div>
          </div>
          <button onClick={showActPreview} style={{...btnO, width: '100%', justifyContent: 'center'}}>
            <ScrollText size={14}/>Сформировать акт
          </button>
          <div style={{display: 'flex', alignItems: 'center', gap: '10px', marginTop: '12px', flexWrap: 'wrap', borderTop: '1px solid ' + C.border, paddingTop: '12px'}}>
            {selectedBrigadeContract.actScanUrl ? (
              <>
                <span style={{fontSize: '12px', color: C.success, fontWeight: '600'}}>✅ Подписанный акт загружен — оплата разрешена</span>
                <a href={fileSrc(selectedBrigadeContract.actScanUrl)} target="_blank" rel="noreferrer" style={{...btnB, padding: '4px 8px', fontSize: '11px', textDecoration: 'none'}}>
                  <Eye size={11}/>Скан
                </a>
              </>
            ) : (
              <span style={{fontSize: '12px', color: C.warning, fontWeight: '600'}}>⏳ Скан подписанного акта не загружен — оплата заблокирована</span>
            )}
            {showFinance && (
              <label style={{...btnG, cursor: 'pointer', margin: 0, fontSize: '11px', padding: '5px 10px'}}>
                <Upload size={12}/>{selectedBrigadeContract.actScanUrl ? 'Заменить скан' : 'Загрузить подписанный акт'}
                <input type="file" style={{display: 'none'}} onChange={uploadSignedAct}/>
              </label>
            )}
          </div>
        </div>
      )}

      <div style={{...card, padding: '16px', marginTop: '16px'}}>
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', marginBottom: '10px'}}>
          <b style={{color: C.text, fontSize: '14px'}}>💰 Оплаты бригаде</b>
          {showFinance && due > 0 && (
            selectedBrigadeContract.actScanUrl ? (
              <button onClick={openPaymentModal} style={btnO}><Plus size={14}/>Записать оплату</button>
            ) : (
              <button onClick={() => alert('Оплата заблокирована: сначала загрузите скан подписанного акта бригады (ниже, у кнопки «Сформировать акт»).')} style={{...btnG, opacity: 0.6}} title="Нет скана подписанного акта">
                <Plus size={14}/>Оплата 🔒
              </button>
            )
          )}
        </div>
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '10px', marginBottom: '12px'}}>
          <div>
            <p style={{color: C.textSec, fontSize: '11px', margin: '0 0 3px'}}>К оплате</p>
            <b style={{color: C.accent, fontSize: '15px'}}>{due.toLocaleString('ru-RU') + ' ₽'}</b>
          </div>
          <div>
            <p style={{color: C.textSec, fontSize: '11px', margin: '0 0 3px'}}>Оплачено</p>
            <b style={{color: C.success, fontSize: '15px'}}>{paid.toLocaleString('ru-RU') + ' ₽'}</b>
          </div>
          <div>
            <p style={{color: C.textSec, fontSize: '11px', margin: '0 0 3px'}}>Остаток</p>
            <b style={{color: owe > 0 ? C.danger : C.success, fontSize: '15px'}}>{owe > 0 ? owe.toLocaleString('ru-RU') + ' ₽' : '✓ закрыто'}</b>
          </div>
        </div>
        {(brigadePayments || []).length > 0 ? (
          <div style={{borderTop: '1px solid ' + C.border, paddingTop: '8px'}}>
            {brigadePayments.map(payment => (
              <div key={payment.id} style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderBottom: '1px solid ' + C.border, fontSize: '12px'}}>
                <span style={{color: C.textSec}}>{(payment.paidDate || '') + ' · ' + (payment.paidBy || '') + (payment.note ? ' · ' + payment.note : '')}</span>
                <span style={{display: 'flex', gap: '8px', alignItems: 'center'}}>
                  <b style={{color: C.success}}>{Math.round(Number(payment.amount || 0)).toLocaleString('ru-RU') + ' ₽'}</b>
                  {showFinance && (
                    <button onClick={() => deleteBrigadePayment(payment.id)} style={{...btnR, padding: '2px 6px'}}>
                      <Trash2 size={10}/>
                    </button>
                  )}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p style={{color: C.textMuted, fontSize: '12px', margin: 0}}>Оплат пока нет</p>
        )}
      </div>
    </>
  );
}

import React from 'react';
import { Plus } from 'lucide-react';
import { API } from '../api';

export default function ProjectFinancePanel({
  projectName,
  projectPayments = [],
  accountablePayments = [],
  ownExpenses = [],
  expenseCategories = [],
  expByCategory,
  projectPaymentInAmount,
  projectPaymentSignedAmount,
  formatSignedRub,
  user,
  C,
  card,
  btnO,
  btnB,
  btnG,
  btnR,
  showBalanceDetails,
  setShowBalanceDetails,
  setAddExpenseProject,
  setNewManualExpense,
  setShowAccountableForm,
  newAccountable,
  setNewAccountable,
  setShowPhotoModal,
  fileSrc,
  loadAll,
  showProfit,
  canAddExpense,
}) {
  const cat = expByCategory(projectName);
  const total = Object.values(cat).reduce((sum, value) => sum + value, 0);
  const projectPays = projectPayments.filter(pay => pay.projectName === projectName);
  const received = projectPays.reduce((sum, pay) => sum + projectPaymentInAmount(pay), 0);
  const inAccountable = accountablePayments
    .filter(ac => ac.projectName === projectName)
    .reduce((sum, ac) => sum + Math.max(0, Number(ac.amount || 0) - Number(ac.spentAmount || 0)), 0);
  const profit = received - total - inAccountable;
  const toReimburse = ownExpenses.filter(e => e.projectName === projectName && e.status === 'Ожидает');
  const categoryById = new Map(expenseCategories.map(c => [c.id, c]));
  const activeCategories = Object.entries(cat)
    .filter(([, value]) => Number(value || 0) > 0)
    .map(([id, value]) => ({
      id,
      label: categoryById.get(id)?.label || id,
      color: categoryById.get(id)?.color || C.accent,
      value,
    }));
  const workPackageLabel = pay => pay?.workPackage || pay?.work_package || '';

  const addCustomerPayment = () => {
    const amount = prompt('Сумма оплаты от заказчика (₽):');
    const note = prompt('Примечание:');

    if (amount && Number(amount) > 0) {
      fetch(API + '/project-payments', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          projectName,
          amount: Number(amount),
          note: note || '',
          date: new Date().toISOString().split('T')[0],
          addedBy: user.name,
        }),
      }).then(() => loadAll());
    }
  };

  const updateOwnExpenseStatus = async (expenseId, status) => {
    await fetch(API + '/own-expenses/' + expenseId, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({status, approvedBy: user.name}),
    });
    await loadAll();
  };

  return (
    <div>
      <div style={{display: 'flex', gap: '8px', marginBottom: '12px', flexWrap: 'wrap'}}>
        <button onClick={addCustomerPayment} style={{...btnO, fontSize: '12px', padding: '7px 14px'}}>
          <Plus size={13}/>Оплата от заказчика
        </button>
        {canAddExpense && (
          <button onClick={() => {
            setAddExpenseProject(projectName);
            setNewManualExpense({category: 'materials', customCategory: '', projectName: '', amount: '', note: '', date: ''});
          }} style={{...btnB, fontSize: '12px', padding: '7px 14px'}}>
            <Plus size={13}/>Расход по объекту
          </button>
        )}
        <button onClick={() => {
          setShowAccountableForm(true);
          setNewAccountable({...newAccountable, projectName});
        }} style={{...btnG, fontSize: '12px', padding: '7px 14px'}}>
          <Plus size={13}/>Подотчёт по объекту
        </button>
        {toReimburse.length > 0 && (
          <div style={{display: 'flex', alignItems: 'center', gap: '6px', padding: '7px 14px', backgroundColor: C.warningLight, borderRadius: '8px', border: '1.5px solid ' + C.warningBorder}}>
            <span style={{fontSize: '12px', color: C.warning, fontWeight: '600'}}>
              {'⏳ К возмещению: ' + toReimburse.reduce((sum, e) => sum + Number(e.amount), 0).toLocaleString() + ' ₽'}
            </span>
          </div>
        )}
      </div>

      <div style={{...card, padding: '16px', marginBottom: '12px', backgroundColor: C.accentLight, border: '1.5px solid ' + C.accentBorder}}>
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', cursor: 'pointer'}} onClick={() => setShowBalanceDetails(!showBalanceDetails)}>
          <b style={{color: C.text, fontSize: '14px'}}>💰 Баланс объекта</b>
          <span style={{fontSize: '12px', color: C.accent}}>{showBalanceDetails ? '▲ Свернуть' : '▼ Подробнее'}</span>
        </div>
        <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px'}}>
          <div style={{padding: '10px', backgroundColor: C.bgWhite, borderRadius: '8px'}}>
            <p style={{color: C.textSec, fontSize: '11px', margin: '0 0 2px'}}>Получено от заказчика</p>
            <b style={{color: C.success, fontSize: '15px'}}>{received.toLocaleString() + ' ₽'}</b>
          </div>
          <div style={{padding: '10px', backgroundColor: C.bgWhite, borderRadius: '8px'}}>
            <p style={{color: C.textSec, fontSize: '11px', margin: '0 0 2px'}}>Все расходы</p>
            <b style={{color: C.danger, fontSize: '15px'}}>{total.toLocaleString() + ' ₽'}</b>
          </div>
          <div style={{padding: '10px', backgroundColor: C.bgWhite, borderRadius: '8px'}}>
            <p style={{color: C.textSec, fontSize: '11px', margin: '0 0 2px'}}>В подотчёте</p>
            <b style={{color: C.warning, fontSize: '15px'}}>{inAccountable.toLocaleString() + ' ₽'}</b>
          </div>
          {showProfit && (
            <div style={{padding: '10px', backgroundColor: profit >= 0 ? C.successLight : C.dangerLight, borderRadius: '8px', border: '1.5px solid ' + (profit >= 0 ? C.successBorder : C.dangerBorder)}}>
              <p style={{color: C.textSec, fontSize: '11px', margin: '0 0 2px'}}>Прибыль</p>
              <b style={{color: profit >= 0 ? C.success : C.danger, fontSize: '15px'}}>{profit.toLocaleString() + ' ₽'}</b>
            </div>
          )}
        </div>
      </div>

      {showBalanceDetails && (
        <div style={{...card, padding: '16px', marginBottom: '12px'}}>
          <b style={{color: C.text, fontSize: '14px', display: 'block', marginBottom: '10px'}}>📊 Расходы по категориям</b>
          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px'}}>
            {activeCategories.map(c => (
              <div key={c.id} style={{padding: '10px', backgroundColor: C.bg, borderRadius: '8px', border: '1.5px solid ' + C.border}}>
                <p style={{margin: '0 0 2px', fontSize: '11px', color: C.textSec}}>{c.label}</p>
                <b style={{fontSize: '14px', color: c.color}}>{Number(c.value || 0).toLocaleString() + ' ₽'}</b>
              </div>
            ))}
            {activeCategories.length === 0 && <p style={{color: C.textMuted, fontSize: '12px', gridColumn: 'span 2', textAlign: 'center', padding: '10px'}}>Расходов пока нет</p>}
          </div>
        </div>
      )}

      {toReimburse.length > 0 && (
        <div style={{...card, padding: '16px', marginBottom: '12px'}}>
          <b style={{color: C.text, fontSize: '14px', display: 'block', marginBottom: '10px'}}>⏳ К возмещению</b>
          {toReimburse.map(e => {
            const urls = (e.photoUrl || '').split(',').filter(Boolean);
            return (
              <div key={e.id} style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid ' + C.border}}>
                <div>
                  <b style={{fontSize: '13px', color: C.text}}>{e.employeeName}</b>
                  <p style={{color: C.textSec, margin: '2px 0', fontSize: '12px'}}>{e.description}</p>
                </div>
                <div style={{display: 'flex', gap: '6px', alignItems: 'center'}}>
                  <b style={{color: C.accent, fontSize: '13px'}}>{Number(e.amount).toLocaleString() + ' ₽'}</b>
                  {urls.length === 1 && <button onClick={() => setShowPhotoModal(fileSrc(urls[0]))} style={{...btnG, padding: '3px 8px', fontSize: '11px'}}>📷</button>}
                  {urls.length > 1 && <button onClick={() => setShowPhotoModal(fileSrc(urls[0]))} style={{...btnG, padding: '3px 8px', fontSize: '11px'}}>📷 {urls.length}</button>}
                  <button onClick={() => updateOwnExpenseStatus(e.id, 'Возмещено')} style={{...btnO, padding: '3px 8px', fontSize: '11px'}}>✅</button>
                  <button onClick={() => updateOwnExpenseStatus(e.id, 'Отклонено')} style={{...btnR, padding: '3px 8px', fontSize: '11px'}}>❌</button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {projectPays.length > 0 && (
        <div style={{...card, padding: '16px', marginBottom: '12px'}}>
          <b style={{color: C.text, fontSize: '14px', display: 'block', marginBottom: '10px'}}>📋 Движение денег по объекту</b>
          {projectPays.map(pay => {
            const signed = projectPaymentSignedAmount(pay);
            return (
              <div key={pay.id} style={{display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid ' + C.border}}>
                <div>
                  <span style={{fontSize: '12px', color: C.text}}>{pay.note || 'Оплата'}</span>
                  {workPackageLabel(pay) && <span style={{fontSize: '11px', color: C.info, marginLeft: '8px'}}>📁 {workPackageLabel(pay)}</span>}
                  <span style={{fontSize: '11px', color: C.textMuted, marginLeft: '8px'}}>{pay.date}</span>
                </div>
                <b style={{fontSize: '12px', color: signed >= 0 ? C.success : C.danger}}>{formatSignedRub(signed)}</b>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

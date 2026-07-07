import React, { useState } from 'react';
import { FileText, Image, Paperclip, Plus } from 'lucide-react';
import { API } from '../api';
import { createAccountablePaymentForm, createManualExpenseForm } from '../features/payments/paymentInitialForms';

export default function ProjectFinancePanel({
  projectName,
  projectPayments = [],
  accountablePayments = [],
  ownExpenses = [],
  manualExpenses = [],
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
  inp,
  showBalanceDetails,
  setShowBalanceDetails,
  setAddExpenseProject,
  setNewManualExpense,
  setShowAccountableForm,
  setNewAccountable,
  setShowPhotoModal,
  fileSrc,
  loadAll,
  showProfit,
  canAddExpense,
}) {
  const today = () => new Date().toISOString().split('T')[0];
  const parseAmount = value => Number(String(value || '').replace(/\s+/g, '').replace(',', '.'));
  const [showCustomerPaymentForm, setShowCustomerPaymentForm] = useState(false);
  const [customerPaymentForm, setCustomerPaymentForm] = useState({
    amount: '',
    date: today(),
    note: '',
  });
  const [customerPaymentError, setCustomerPaymentError] = useState('');
  const [customerPaymentBusy, setCustomerPaymentBusy] = useState(false);
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
  const projectManualExpenses = [...manualExpenses]
    .filter(expense => expense.project === projectName)
    .sort((a, b) => Number(b.id || 0) - Number(a.id || 0));
  const activeCategories = Object.entries(cat)
    .filter(([, value]) => Number(value || 0) > 0)
    .map(([id, value]) => ({
      id,
      label: categoryById.get(id)?.label || id,
      color: categoryById.get(id)?.color || C.accent,
      value,
    }));
  const workPackageLabel = pay => pay?.workPackage || pay?.work_package || '';
  const expenseAttachmentUrls = expense => String(expense?.photoUrl || expense?.photo_url || '').split(',').map(url => url.trim()).filter(Boolean);
  const isImageUrl = url => /\.(png|jpe?g|webp|gif|heic|heif|bmp|svg)(\?|$)/i.test(String(url || ''));
  const attachmentLabel = url => {
    const raw = String(url || '').split('?')[0].split('/').filter(Boolean).pop() || 'Файл';
    try {
      return decodeURIComponent(raw);
    } catch (_e) {
      return raw;
    }
  };
  const openAttachment = url => {
    const src = typeof fileSrc === 'function' ? fileSrc(url) : url;
    if (isImageUrl(url) && typeof setShowPhotoModal === 'function') {
      setShowPhotoModal(src);
      return;
    }
    if (typeof window !== 'undefined') window.open(src, '_blank', 'noopener,noreferrer');
  };

  const addCustomerPayment = async () => {
    const amount = parseAmount(customerPaymentForm.amount);
    setCustomerPaymentError('');
    if (!amount || amount <= 0) {
      setCustomerPaymentError('Укажите сумму оплаты больше нуля.');
      return;
    }
    setCustomerPaymentBusy(true);
    try {
      const response = await fetch(API + '/project-payments', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          projectName,
          amount,
          note: customerPaymentForm.note || '',
          date: customerPaymentForm.date || today(),
          addedBy: user.name,
        }),
      });
      let result = {};
      try {
        result = await response.json();
      } catch (_e) {
        result = {};
      }
      if (!response.ok) {
        setCustomerPaymentError(result.detail || 'Не удалось добавить оплату от заказчика.');
        return;
      }
      setCustomerPaymentForm({ amount: '', date: today(), note: '' });
      setShowCustomerPaymentForm(false);
      await loadAll();
    } catch (_e) {
      setCustomerPaymentError('Не удалось связаться с сервером.');
    } finally {
      setCustomerPaymentBusy(false);
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
        <button
          onClick={() => {
            setCustomerPaymentForm({ amount: '', date: today(), note: '' });
            setCustomerPaymentError('');
            setShowCustomerPaymentForm(true);
          }}
          style={{...btnO, fontSize: '12px', padding: '7px 14px'}}
        >
          <Plus size={13}/>Оплата от заказчика
        </button>
        {canAddExpense && (
          <button onClick={() => {
            setAddExpenseProject(projectName);
            setNewManualExpense(createManualExpenseForm());
          }} style={{...btnB, fontSize: '12px', padding: '7px 14px'}}>
            <Plus size={13}/>Расход по объекту
          </button>
        )}
        <button onClick={() => {
          setShowAccountableForm(true);
          setNewAccountable(createAccountablePaymentForm({projectName}));
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

      {showCustomerPaymentForm && (
        <div style={{...card, padding: '14px', marginBottom: '12px', border: '1.5px solid ' + C.accentBorder, backgroundColor: C.bgWhite}}>
          <b style={{color: C.text, fontSize: '14px', display: 'block', marginBottom: '10px'}}>Оплата от заказчика</b>
          <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(170px,1fr))', gap: '8px'}}>
            <input
              type="number"
              min="0"
              step="0.01"
              placeholder="Сумма, ₽"
              value={customerPaymentForm.amount}
              onChange={e => setCustomerPaymentForm({...customerPaymentForm, amount: e.target.value})}
              style={{...inp, marginBottom: 0}}
            />
            <input
              type="date"
              value={customerPaymentForm.date}
              onChange={e => setCustomerPaymentForm({...customerPaymentForm, date: e.target.value})}
              style={{...inp, marginBottom: 0}}
            />
            <input
              placeholder="Договор, счёт или комментарий"
              value={customerPaymentForm.note}
              onChange={e => setCustomerPaymentForm({...customerPaymentForm, note: e.target.value})}
              style={{...inp, marginBottom: 0}}
            />
          </div>
          {customerPaymentError && (
            <p style={{color: C.danger, fontSize: '12px', margin: '8px 0 0'}}>{customerPaymentError}</p>
          )}
          <div style={{display: 'flex', gap: '8px', marginTop: '10px', flexWrap: 'wrap'}}>
            <button onClick={addCustomerPayment} disabled={customerPaymentBusy} style={{...btnO, opacity: customerPaymentBusy ? 0.65 : 1}}>
              {customerPaymentBusy ? 'Сохраняем...' : 'Сохранить оплату'}
            </button>
            <button
              onClick={() => {
                setShowCustomerPaymentForm(false);
                setCustomerPaymentError('');
              }}
              disabled={customerPaymentBusy}
              style={btnG}
            >
              Отмена
            </button>
          </div>
        </div>
      )}

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

      {projectManualExpenses.length > 0 && (
        <div style={{...card, padding: '16px', marginBottom: '12px'}}>
          <b style={{color: C.text, fontSize: '14px', display: 'block', marginBottom: '10px'}}>📎 Последние расходы по объекту</b>
          {projectManualExpenses.slice(0, 10).map(expense => {
            const urls = expenseAttachmentUrls(expense);
            const category = categoryById.get(expense.category)?.label || expense.category || 'Расход';
            return (
              <div key={expense.id} style={{display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto', gap: '10px', padding: '8px 0', borderBottom: '1px solid ' + C.border, alignItems: 'start'}}>
                <div style={{minWidth: 0}}>
                  <div style={{display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap'}}>
                    <b style={{fontSize: '13px', color: C.text, overflowWrap: 'anywhere'}}>{category}</b>
                    {expense.source && <span style={{fontSize: '10px', color: C.textMuted, backgroundColor: C.bg, border: '1px solid ' + C.border, borderRadius: '999px', padding: '1px 6px'}}>{expense.source}</span>}
                  </div>
                  {(expense.note || expense.date || expense.addedBy) && (
                    <p style={{color: C.textSec, margin: '2px 0', fontSize: '12px', overflowWrap: 'anywhere'}}>
                      {[expense.note, expense.date, expense.addedBy].filter(Boolean).join(' · ')}
                    </p>
                  )}
                  {urls.length > 0 && (
                    <div style={{display: 'flex', gap: '5px', flexWrap: 'wrap', marginTop: '5px'}}>
                      {urls.map((url, index) => {
                        const isImage = isImageUrl(url);
                        return (
                          <button key={url + index} type='button' onClick={() => openAttachment(url)} title={attachmentLabel(url)} style={{...btnG, padding: '3px 7px', fontSize: '11px', maxWidth: '160px'}}>
                            {isImage ? <Image size={12}/> : <FileText size={12}/>}
                            <span style={{overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>{isImage ? 'Фото ' + (index + 1) : attachmentLabel(url)}</span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
                <div style={{display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'flex-end', flexWrap: 'wrap'}}>
                  {urls.length > 0 && <span style={{fontSize: '11px', color: C.accent, display: 'flex', alignItems: 'center', gap: '3px'}}><Paperclip size={12}/>{urls.length}</span>}
                  <b style={{color: C.danger, fontSize: '13px', whiteSpace: 'nowrap'}}>{Number(expense.amount || 0).toLocaleString() + ' ₽'}</b>
                </div>
              </div>
            );
          })}
          {projectManualExpenses.length > 10 && <p style={{margin: '8px 0 0', color: C.textMuted, fontSize: '11px'}}>Показаны последние 10 расходов.</p>}
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

export const createPaymentActions = ({
  API,
  actPayments,
  interimActs,
  loadPricelistItems,
  newBrigadePayment,
  newPayment,
  refreshData,
  selectedBrigadeContract,
  setActPayments,
  setBrigadeContractItems,
  setBrigadePayments,
  setNewBrigadePayment,
  setNewPayment,
  setSelectedBrigadeContract,
  setShowBrigadePayModal,
  setShowPayActModal,
  toNum,
  user,
}) => {
  const saveActPayment = async (actId) => {
    if (!newPayment.amount || !newPayment.date) { alert('Заполните сумму и дату'); return; }
    const act = interimActs.find(a => a.id === actId);
    if (!act) return;
    const amount = Number(newPayment.amount);
    if (!Number.isFinite(amount) || amount <= 0) { alert('Введите сумму оплаты больше нуля'); return; }
    const paymentNote = 'Оплата акта #' + actId + ' · ' + (act.masterName || act.brigadeName || act.performerName || 'исполнитель') + (newPayment.notes ? ' · ' + newPayment.notes : '');
    const payRes = await fetch(API + '/interim-acts/' + actId + '/pay', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        amount,
        note: paymentNote,
        paidDate: newPayment.date,
        paidBy: newPayment.paidBy || user?.name || '',
      }),
    });
    if (!payRes.ok) {
      const err = await payRes.json().catch(() => ({detail:'Не удалось провести оплату акта'}));
      alert(err.detail || 'Не удалось провести оплату акта');
      return;
    }
    const payment = {...newPayment, id:Date.now(), actId, amount};
    const updated = [...actPayments, payment];
    setActPayments(updated);
    localStorage.setItem('actPayments', JSON.stringify(updated));
    await refreshData();
    setNewPayment({amount:'', paymentType:'Наличный расчёт', paidBy:'', date:'', notes:''});
    setShowPayActModal(null);
  };

  const openBrigadeContract = async (bc) => {
    setSelectedBrigadeContract(bc);
    try {
      const [items, pays] = await Promise.all([
        fetch(API + '/brigade-contract-items/' + bc.id).then(r => r.json()),
        fetch(API + '/brigade-payments?contract_id=' + bc.id).then(r => r.json()),
      ]);
      setBrigadeContractItems(Array.isArray(items) ? items : []);
      setBrigadePayments(Array.isArray(pays) ? pays : []);
    } catch (_) {}
    if (bc.pricelistId) await loadPricelistItems(bc.pricelistId);
  };

  const saveBrigadePayment = async () => {
    if (!selectedBrigadeContract) return;
    const sum = toNum(newBrigadePayment.amount);
    if (sum <= 0) { alert('Введите сумму оплаты'); return; }
    const payRes = await fetch(API + '/brigade-payments', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        contractId:selectedBrigadeContract.id,
        amount:sum,
        paidBy:newBrigadePayment.paidBy || user.name,
        paidDate:newBrigadePayment.paidDate || new Date().toISOString().split('T')[0],
        note:newBrigadePayment.note || '',
      }),
    });
    if (!payRes.ok) {
      const err = await payRes.json().catch(() => ({detail:'Не удалось записать оплату'}));
      alert(err.detail || 'Не удалось записать оплату');
      return;
    }
    const pays = await fetch(API + '/brigade-payments?contract_id=' + selectedBrigadeContract.id).then(r => r.json());
    setBrigadePayments(Array.isArray(pays) ? pays : []);
    setNewBrigadePayment({amount:'', paidBy:'', paidDate:'', note:''});
    setShowBrigadePayModal(false);
    await refreshData();
  };

  const deleteBrigadePayment = async (id) => {
    if (!window.confirm('Удалить эту оплату?')) return;
    await fetch(API + '/brigade-payments/' + id, {method:'DELETE'});
    if (selectedBrigadeContract) {
      const pays = await fetch(API + '/brigade-payments?contract_id=' + selectedBrigadeContract.id).then(r => r.json());
      setBrigadePayments(Array.isArray(pays) ? pays : []);
    }
    await refreshData();
  };

  return {
    deleteBrigadePayment,
    openBrigadeContract,
    saveActPayment,
    saveBrigadePayment,
  };
};

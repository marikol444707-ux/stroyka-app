import { emptySupplierForm, normalizeSupplierPayload } from '../../utils/supplierUtils';
import { createRequestForm, createSupplierOfferForm } from './supplyInitialForms';

export const createSupplyActions = ({
  API,
  editingItem,
  getProjectWorkPackageOptions,
  newOffer,
  newOfferInvoice,
  newRequest,
  newSupplier,
  newSupplyReq,
  notify,
  priceHints,
  receiveForm,
  refreshData,
  selectedSupplierIds,
  setCompareLoadingReqId,
  setCompareResultByReq,
  setDeliveryAiLoadingId,
  setDeliveryAiResultById,
  setEditingItem,
  setInvoicingOfferId,
  setNewOffer,
  setNewOfferInvoice,
  setNewRequest,
  setNewSupplier,
  setNewSupplyReq,
  setPriceHints,
  setReceiveForm,
  setReceivingDeliveryId,
  setRequestKpLoading,
  setSelectedSupplierIds,
  setShipmentForm,
  setShippingOfferId,
  setShowForm,
  setShowRequestKpModal,
  setShowSupplyForm,
  setSuggestedSuppliers,
  setSupplyAiLoading,
  setSupplyAiText,
  setSupplyRejectId,
  setSupplyRejectReason,
  setSupplyStockCheck,
  shipmentForm,
  showRequestKpModal,
  suggestedSuppliers,
  supplyRejectReason,
  supplyRequests,
  supplyTemplates,
  user,
}) => {
  const currentUser = user || {};

  const saveSupplier = async () => {
    if (!newSupplier.name) return;
    const payload = normalizeSupplierPayload(newSupplier);
    if (editingItem && editingItem.id) {
      await fetch(API + '/suppliers/' + editingItem.id, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } else {
      await fetch(API + '/suppliers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    }
    await refreshData();
    setNewSupplier(emptySupplierForm());
    setEditingItem(null);
    setShowForm(false);
  };

  const deleteSupplier = async (id) => {
    if (window.confirm('Удалить?')) {
      await fetch(API + '/suppliers/' + id, { method: 'DELETE' });
      await refreshData();
    }
  };

  const saveRequest = async () => {
    const requestPackages = getProjectWorkPackageOptions(newRequest.project);
    const defaultWorkPackage = newRequest.workPackage || (requestPackages.length === 1 ? requestPackages[0] : '');
    const validItems = newRequest.items
      .filter(i => i.materialName && i.quantity)
      .map(i => ({ ...i, workPackage: i.workPackage || defaultWorkPackage }));
    if (!validItems.length || !newRequest.project) return;
    const itemsPayload = validItems.map(item => ({
      materialName: item.materialName,
      quantity: Number(item.quantity),
      unit: item.unit || 'шт',
      workPackage: item.workPackage || '',
    }));
    const itemPackages = Array.from(new Set(itemsPayload.map(i => i.workPackage || 'Основная')));
    if (itemPackages.length > 1) {
      alert('В одной заявке нельзя смешивать разные разделы сметы: ' + itemPackages.join(', ') + '. Создайте отдельные заявки.');
      return;
    }
    const requestPackage = Array.from(new Set(itemsPayload.map(i => i.workPackage).filter(Boolean))).length === 1
      ? itemsPayload.find(i => i.workPackage)?.workPackage || ''
      : '';
    const res = await fetch(API + '/supply-requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        materialName: itemsPayload[0].materialName,
        quantity: itemsPayload[0].quantity,
        unit: itemsPayload[0].unit,
        items: itemsPayload,
        workPackage: requestPackage,
        project: newRequest.project,
        createdBy: currentUser.name || '',
        date: new Date().toISOString().split('T')[0],
        notes: newRequest.notes,
        selectedSuppliers: newRequest.selectedSuppliers,
        category: newRequest.category || '',
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.detail || data.error) {
      alert('Не удалось создать заявку: ' + (data.detail || data.error || res.status));
      return;
    }
    notify('Новая заявка на материалы', 'supply');
    await refreshData();
    setNewRequest(createRequestForm());
    setShowForm(false);
  };

  const cancelRequest = async (id) => {
    await fetch(API + '/supply-requests/' + id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'Отменена' }),
    });
    await refreshData();
  };

  const createSupplyReq = async () => {
    const valid = (newSupplyReq.items || []).filter(i => i.materialName && Number(i.quantity) > 0);
    if (!valid.length || !newSupplyReq.project) {
      alert('Заполните хотя бы одну строку (материал + кол-во) и выберите объект');
      return;
    }
    const requestPackages = getProjectWorkPackageOptions(newSupplyReq.project);
    const defaultWorkPackage = newSupplyReq.workPackage || (requestPackages.length === 1 ? requestPackages[0] : '');
    const itemsPayload = valid.map(it => ({
      materialName: it.materialName,
      quantity: Number(it.quantity),
      unit: it.unit || 'шт',
      workPackage: it.workPackage || defaultWorkPackage || '',
    }));
    const itemPackages = Array.from(new Set(itemsPayload.map(it => it.workPackage || 'Основная')));
    if (itemPackages.length > 1) {
      alert('В одной заявке нельзя смешивать разные разделы сметы: ' + itemPackages.join(', ') + '. Создайте отдельные заявки.');
      return;
    }
    const requestPackage = Array.from(new Set(itemsPayload.map(it => it.workPackage).filter(Boolean))).length === 1
      ? itemsPayload.find(it => it.workPackage)?.workPackage || ''
      : '';
    const r = await fetch(API + '/supply-requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        materialName: itemsPayload[0].materialName,
        quantity: itemsPayload[0].quantity,
        unit: itemsPayload[0].unit,
        items: itemsPayload,
        workPackage: requestPackage,
        project: newSupplyReq.project,
        createdBy: currentUser.name || '',
        date: new Date().toISOString().split('T')[0],
        notes: newSupplyReq.notes || '',
        category: newSupplyReq.category || '',
        urgency: newSupplyReq.urgency || 'обычная',
        requestedByRole: currentUser.role || '',
        requestedById: currentUser.id || null,
        selectedSuppliers: [],
      }),
    });
    if (!r.ok) {
      let err = '';
      try { err = (await r.json()).detail || ''; } catch (_) {}
      alert('Не удалось создать заявку' + (err ? ': ' + err : ''));
      return;
    }
    const msg = valid.length > 1
      ? ('Заявка из ' + valid.length + ' позиций — объект ' + newSupplyReq.project)
      : ('Заявка «' + valid[0].materialName + '» — объект ' + newSupplyReq.project);
    if (['мастер', 'субподрядчик', 'бригадир'].includes(currentUser.role)) {
      notify('Новая заявка от ' + (currentUser.name || 'пользователя') + ': ' + msg, 'supply');
    } else if (currentUser.role === 'прораб') {
      notify('Прораб ' + (currentUser.name || 'пользователь') + ': ' + msg + ' — нужно утвердить', 'supply');
    } else {
      notify(msg + ' — утверждена директором', 'supply');
    }
    await refreshData();
    setNewSupplyReq({ items: [{ materialName: '', quantity: '', unit: 'шт', workPackage: '' }], project: '', urgency: 'обычная', notes: '', category: '' });
    setShowSupplyForm(false);
  };

  const fetchPriceHint = async (name) => {
    const key = (name || '').trim();
    if (!key || key.length < 2 || priceHints[key]) return;
    try {
      const res = await fetch(API + '/material-price-history?material=' + encodeURIComponent(key));
      if (!res.ok) return;
      const data = await res.json();
      setPriceHints(prev => ({ ...prev, [key]: data }));
    } catch (_) {}
  };

  const saveSupplyTemplate = async () => {
    const valid = (newSupplyReq.items || []).filter(i => i.materialName && Number(i.quantity) > 0);
    if (!valid.length) { alert('Добавьте хотя бы одну позицию, чтобы сохранить шаблон'); return; }
    const name = window.prompt('Название шаблона (например «Стартовый набор на объект»):', '');
    if (!name || !name.trim()) return;
    const r = await fetch(API + '/supply-request-templates', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name.trim(),
        category: newSupplyReq.category || '',
        items: valid.map(it => ({ materialName: it.materialName, quantity: Number(it.quantity), unit: it.unit || 'шт', workPackage: it.workPackage || '' })),
        createdBy: currentUser.name || '',
        createdById: currentUser.id || null,
      }),
    });
    if (!r.ok) {
      let e = '';
      try { e = (await r.json()).detail || ''; } catch (_) {}
      alert('Не удалось сохранить шаблон' + (e ? ': ' + e : ''));
      return;
    }
    await refreshData();
    alert('Шаблон «' + name.trim() + '» сохранён');
  };

  const applySupplyTemplate = (tplId) => {
    const tpl = (supplyTemplates || []).find(t => String(t.id) === String(tplId));
    if (!tpl) return;
    const items = (tpl.items || []).map(it => ({
      materialName: it.materialName,
      quantity: String(it.quantity || ''),
      unit: it.unit || 'шт',
      workPackage: it.workPackage || '',
    }));
    setNewSupplyReq(prev => ({ ...prev, items: items.length ? items : [{ materialName: '', quantity: '', unit: 'шт', workPackage: '' }], category: tpl.category || prev.category }));
  };

  const deleteSupplyTemplate = async (tplId) => {
    if (!window.confirm('Удалить шаблон?')) return;
    await fetch(API + '/supply-request-templates/' + tplId, { method: 'DELETE' });
    await refreshData();
  };

  const confirmSupplyAsProrab = async (id) => {
    await fetch(API + '/supply-requests/' + id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'confirm_prorab', userId: currentUser.id || null, userName: currentUser.name || '' }),
    });
    notify('Заявка подтверждена прорабом — ждёт директора', 'supply');
    await refreshData();
  };

  const approveSupplyAsDirector = async (id) => {
    const r = await fetch(API + '/supply-requests/' + id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'approve_director', userId: currentUser.id || null, userName: currentUser.name || '' }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok || data.detail || data.error) {
      alert('Не удалось утвердить заявку: ' + (data.detail || data.error || r.status));
      return;
    }
    notify('Заявка утверждена директором', 'supply');
    await refreshData();
  };

  const rejectSupply = async (id) => {
    if (!supplyRejectReason.trim()) { alert('Укажите причину отказа'); return; }
    await fetch(API + '/supply-requests/' + id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'reject', rejectReason: supplyRejectReason }),
    });
    setSupplyRejectId(null);
    setSupplyRejectReason('');
    notify('Заявка отклонена', 'supply');
    await refreshData();
  };

  const cancelSupply = async (id) => {
    if (!window.confirm('Отменить заявку?')) return;
    await fetch(API + '/supply-requests/' + id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'cancel' }),
    });
    await refreshData();
  };

  const loadSupplyStockCheck = async (id) => {
    setSupplyStockCheck(null);
    setSupplyAiText('');
    try {
      const r = await fetch(API + '/supply-requests/' + id + '/stock-check');
      const data = await r.json();
      setSupplyStockCheck(data);
    } catch (_) {
      setSupplyStockCheck({ error: 'Не удалось загрузить' });
    }
  };

  const askSupplyAi = async (req, stock) => {
    setSupplyAiLoading(true);
    setSupplyAiText('');
    try {
      const prompt = 'Заявка на материал: "' + req.materialName + '" — нужно ' + req.quantity + ' ' + req.unit +
        '. На складе найдено похожих позиций: ' + (stock.stockMatches || []).map(m => m.name + ' (' + m.quantity + ' ' + m.unit + ')').join(', ') +
        '. Дефицит: ' + stock.shortage + ' ' + req.unit + '. Бюджет проекта «' + req.project + '» использован на ' + Math.round(stock.budgetRiskPercent || 0) + '%. Дай короткий совет директору: стоит ли закупать и сколько, или взять со склада. 2-3 предложения, по-русски.';
      const r = await fetch(API + '/ai-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: [{ role: 'user', content: prompt }], skipContext: true }),
      });
      const data = await r.json();
      setSupplyAiText((data && data.response) || 'AI не ответил');
    } catch (_) {
      setSupplyAiText('Ошибка вызова AI');
    }
    setSupplyAiLoading(false);
  };

  const openRequestKpModal = async (requestId) => {
    setShowRequestKpModal(requestId);
    setSuggestedSuppliers(null);
    setSelectedSupplierIds([]);
    setRequestKpLoading(true);
    try {
      const r = await fetch(API + '/supply-requests/' + requestId + '/suggest-suppliers');
      const data = await r.json();
      if (data.error) {
        setSuggestedSuppliers({ suppliers: [], error: data.error });
      } else {
        setSuggestedSuppliers(data);
        setSelectedSupplierIds(data.suppliers.filter(s => s.aiRecommend && !s.alreadyRequested).map(s => s.id));
      }
    } catch (_) {
      setSuggestedSuppliers({ suppliers: [], error: 'Не удалось загрузить' });
    }
    setRequestKpLoading(false);
  };

  const sendKpRequest = async () => {
    if (!showRequestKpModal || selectedSupplierIds.length === 0) { alert('Выберите хотя бы одного поставщика'); return; }
    const aiIds = (suggestedSuppliers?.suppliers || []).filter(s => s.aiRecommend).map(s => s.id);
    const r = await fetch(API + '/supply-requests/' + showRequestKpModal + '/request-kp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ supplierIds: selectedSupplierIds, aiRecommendedIds: aiIds }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok || data.detail || data.error) { alert('Ошибка: ' + (data.detail || data.error || r.status)); return; }
    notify('Отправлен запрос КП ' + selectedSupplierIds.length + ' поставщикам', 'supply');
    setShowRequestKpModal(null);
    setSelectedSupplierIds([]);
    setSuggestedSuppliers(null);
    await refreshData();
  };

  const selectSupplierOffer = async (offerId) => {
    if (!window.confirm('Выбрать это КП? Остальные КП по этой заявке будут отклонены.')) return;
    await fetch(API + '/supplier-offers/' + offerId, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'select' }),
    });
    notify('КП утверждено директором', 'supply');
    await refreshData();
  };

  const rejectSupplierOffer = async (offerId) => {
    if (!window.confirm('Отклонить это КП?')) return;
    await fetch(API + '/supplier-offers/' + offerId, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'reject' }),
    });
    await refreshData();
  };

  const runCompareKp = async (reqId) => {
    setCompareLoadingReqId(reqId);
    try {
      const r = await fetch(API + '/supply-requests/' + reqId + '/compare-kp');
      const data = await r.json();
      setCompareResultByReq(prev => ({ ...prev, [reqId]: data }));
    } catch (e) {
      setCompareResultByReq(prev => ({ ...prev, [reqId]: { error: 'Не удалось получить сравнение' } }));
    }
    setCompareLoadingReqId(null);
  };

  const createInvoiceFromOffer = async (offerId) => {
    if (!newOfferInvoice.invoiceNumber || !newOfferInvoice.amount) { alert('Заполните номер счёта и сумму'); return; }
    const r = await fetch(API + '/supplier-offers/' + offerId + '/create-invoice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        invoiceNumber: newOfferInvoice.invoiceNumber,
        invoiceDate: newOfferInvoice.invoiceDate,
        amount: Number(newOfferInvoice.amount),
        vatAmount: Number(newOfferInvoice.vatAmount || 0),
        description: newOfferInvoice.description,
        fileUrl: newOfferInvoice.fileUrl,
      }),
    });
    const data = await r.json();
    if (data.error) { alert('Ошибка: ' + data.error); return; }
    notify('Счёт выставлен — ждёт оплаты бухгалтером', 'supply');
    setInvoicingOfferId(null);
    setNewOfferInvoice({ invoiceNumber: '', invoiceDate: new Date().toISOString().split('T')[0], amount: '', vatAmount: '', description: '', fileUrl: '' });
    await refreshData();
  };

  const createShipmentFromOffer = async (offer) => {
    const req = supplyRequests.find(r => r.id === offer.requestId);
    const qty = shipmentForm.shippedQuantity || req?.quantity || '';
    if (!qty) { alert('Укажите количество отгрузки'); return; }
    const r = await fetch(API + '/supplier-offers/' + offer.id + '/ship', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        shippedQuantity: Number(qty),
        waybillNumber: shipmentForm.waybillNumber,
        waybillDate: shipmentForm.waybillDate,
        vehicleNumber: shipmentForm.vehicleNumber,
        driverName: shipmentForm.driverName,
        documentUrl: shipmentForm.documentUrl,
        photoUrl: shipmentForm.photoUrl,
      }),
    });
    const data = await r.json();
    if (data.detail || data.error) { alert('Ошибка: ' + (data.detail || data.error)); return; }
    notify('Поставка отгружена — ждёт приёмки', 'delivery');
    setShippingOfferId(null);
    setShipmentForm({ shippedQuantity: '', waybillNumber: '', waybillDate: new Date().toISOString().split('T')[0], vehicleNumber: '', driverName: '', documentUrl: '', photoUrl: '' });
    await refreshData();
  };

  const receiveSupplyDelivery = async (delivery) => {
    if (!receiveForm.receivedQuantity && receiveForm.receivedQuantity !== 0) { alert('Укажите принятое количество'); return; }
    const r = await fetch(API + '/supply-deliveries/' + delivery.id + '/receive', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        receivedQuantity: Number(receiveForm.receivedQuantity),
        qualityStatus: receiveForm.qualityStatus,
        qualityNotes: receiveForm.qualityNotes,
        photoUrl: receiveForm.photoUrl,
        claimDescription: receiveForm.claimDescription,
        receivedBy: currentUser.name || '',
      }),
    });
    const data = await r.json();
    if (data.detail || data.error) { alert('Ошибка: ' + (data.detail || data.error)); return; }
    notify((data.claimId ? 'Приёмка с претензией' : 'Поставка принята') + (data.invoiceId ? ' · создана накладная #' + data.invoiceId : ''), 'delivery');
    setReceivingDeliveryId(null);
    setReceiveForm({ receivedQuantity: '', qualityStatus: 'Принято', qualityNotes: '', photoUrl: '', claimDescription: '' });
    await refreshData();
  };

  const runDeliveryAiCheck = async (delivery, parsedItems = []) => {
    setDeliveryAiLoadingId(delivery.id);
    try {
      const r = await fetch(API + '/supply-deliveries/' + delivery.id + '/ai-check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ parsedItems }),
      });
      const data = await r.json();
      setDeliveryAiResultById(prev => ({ ...prev, [delivery.id]: data.result || 'AI не ответил' }));
    } catch (e) {
      setDeliveryAiResultById(prev => ({ ...prev, [delivery.id]: 'AI-сверка не сработала' }));
    }
    setDeliveryAiLoadingId(null);
  };

  const saveOffer = async (requestId) => {
    if (!newOffer.supplierId || !newOffer.pricePerUnit || !newOffer.deliveryDays) {
      alert('Заполните все поля включая срок поставки');
      return;
    }
    const req = supplyRequests.find(r => r.id === requestId);
    await fetch(API + '/supplier-offers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        requestId,
        supplierId: Number(newOffer.supplierId),
        pricePerUnit: Number(newOffer.pricePerUnit),
        totalPrice: Number(newOffer.pricePerUnit) * (req ? req.quantity : 1),
        deliveryDays: Number(newOffer.deliveryDays),
        notes: newOffer.notes,
      }),
    });
    await refreshData();
    setNewOffer(createSupplierOfferForm());
  };

  const approveOffer = async (offer) => {
    const r = await fetch(API + '/supplier-offers/' + offer.id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'select' }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok || data.detail || data.error) {
      alert('Не удалось утвердить КП: ' + (data.detail || data.error || r.status));
      return;
    }
    notify('КП утверждено', 'supply');
    await refreshData();
  };

  return {
    approveOffer,
    approveSupplyAsDirector,
    askSupplyAi,
    cancelRequest,
    cancelSupply,
    confirmSupplyAsProrab,
    createInvoiceFromOffer,
    createShipmentFromOffer,
    createSupplyReq,
    deleteSupplier,
    deleteSupplyTemplate,
    fetchPriceHint,
    loadSupplyStockCheck,
    openRequestKpModal,
    receiveSupplyDelivery,
    rejectSupplierOffer,
    rejectSupply,
    runCompareKp,
    runDeliveryAiCheck,
    saveOffer,
    saveRequest,
    saveSupplier,
    saveSupplyTemplate,
    selectSupplierOffer,
    sendKpRequest,
    applySupplyTemplate,
  };
};

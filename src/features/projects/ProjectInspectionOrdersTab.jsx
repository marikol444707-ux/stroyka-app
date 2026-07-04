import React from 'react';

export default function ProjectInspectionOrdersTab({
  API,
  C,
  Check,
  Plus,
  Trash2,
  badge,
  btnG,
  btnGr,
  btnO,
  btnR,
  card,
  createInspectionOrderForm,
  inp,
  inspectionOrders,
  newInspOrder,
  project,
  refreshData,
  setNewInspOrder,
  setShowForm,
  showForm,
}) {
  const orders = (inspectionOrders || []).filter(order => order.projectName === project.name);
  const openCount = orders.filter(order => order.status !== 'Закрыто').length;
  const closedCount = orders.filter(order => order.status === 'Закрыто').length;

  const openForm = () => {
    const nextOpen = showForm !== 'gsn';
    setShowForm(nextOpen ? 'gsn' : false);
    setNewInspOrder(nextOpen ? createInspectionOrderForm() : null);
  };

  const saveOrder = async () => {
    if (!(newInspOrder && newInspOrder.description)) {
      alert('Опишите замечание');
      return;
    }
    await fetch(API + '/inspection-orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        projectName: project.name,
        body: newInspOrder.body || 'ГСН',
        inspector: newInspOrder.inspector || '',
        description: newInspOrder.description,
        recommendations: newInspOrder.recommendations || '',
        deadline: newInspOrder.deadline || null,
        date: newInspOrder.date || new Date().toISOString().split('T')[0],
        status: 'Открыто',
      }),
    });
    await refreshData();
    setNewInspOrder(null);
    setShowForm(false);
  };

  const closeOrder = async (order) => {
    const response = prompt('Опишите как устранили / ответ органу:');
    if (!response) return;
    await fetch(API + '/inspection-orders/' + order.id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'Закрыто', response, responseDate: new Date().toISOString().split('T')[0] }),
    });
    await refreshData();
  };

  const deleteOrder = async (order) => {
    if (!window.confirm('Удалить замечание?')) return;
    await fetch(API + '/inspection-orders/' + order.id, { method: 'DELETE' });
    await refreshData();
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px', flexWrap: 'wrap', gap: '8px' }}>
        <b style={{ color: C.text, fontSize: '15px', fontWeight: '700' }}>🏛 Замечания контролирующих органов</b>
        <button onClick={openForm} style={btnO}><Plus size={14} />Добавить</button>
      </div>

      {showForm === 'gsn' && (
        <div style={{ ...card, padding: '16px', marginBottom: '14px', backgroundColor: C.bg }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '8px' }}>
            <select value={newInspOrder?.body || 'ГСН'} onChange={event => setNewInspOrder({ ...(newInspOrder || {}), body: event.target.value })} style={{ ...inp, marginBottom: 0 }}>
              {['ГСН', 'ГПН', 'Роспотребнадзор', 'Ростехнадзор', 'Прокуратура', 'Иное'].map(body => <option key={body}>{body}</option>)}
            </select>
            <input placeholder="ФИО инспектора" value={newInspOrder?.inspector || ''} onChange={event => setNewInspOrder({ ...(newInspOrder || {}), inspector: event.target.value })} style={{ ...inp, marginBottom: 0 }} />
          </div>
          <textarea placeholder="Описание замечания/нарушения *" value={newInspOrder?.description || ''} onChange={event => setNewInspOrder({ ...(newInspOrder || {}), description: event.target.value })} style={{ ...inp, minHeight: '60px', marginBottom: '8px' }} />
          <textarea placeholder="Требования / рекомендации" value={newInspOrder?.recommendations || ''} onChange={event => setNewInspOrder({ ...(newInspOrder || {}), recommendations: event.target.value })} style={{ ...inp, minHeight: '50px', marginBottom: '8px' }} />
          <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
            <input type="date" value={newInspOrder?.date || ''} onChange={event => setNewInspOrder({ ...(newInspOrder || {}), date: event.target.value })} title="Дата проверки" style={{ ...inp, marginBottom: 0, flex: 1 }} />
            <input type="date" value={newInspOrder?.deadline || ''} onChange={event => setNewInspOrder({ ...(newInspOrder || {}), deadline: event.target.value })} title="Срок устранения" style={{ ...inp, marginBottom: 0, flex: 1 }} />
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button onClick={saveOrder} style={btnO}><Check size={14} />Сохранить</button>
            <button onClick={() => { setShowForm(false); setNewInspOrder(null); }} style={btnG}>Отмена</button>
          </div>
        </div>
      )}

      {orders.length === 0 ? (
        <div style={{ ...card, padding: '30px', textAlign: 'center', color: C.textMuted }}>
          Замечаний контролирующих органов нет. Если приходила проверка с замечаниями — зафиксируй её здесь, чтобы пакет ИД был полным.
        </div>
      ) : (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '10px', marginBottom: '12px' }}>
            <div style={{ ...card, padding: '10px', backgroundColor: C.dangerLight }}><p style={{ color: C.danger, fontSize: '11px', margin: '0 0 4px' }}>Открытых</p><b style={{ color: C.danger, fontSize: '16px' }}>{openCount}</b></div>
            <div style={{ ...card, padding: '10px', backgroundColor: C.successLight }}><p style={{ color: C.success, fontSize: '11px', margin: '0 0 4px' }}>Закрытых</p><b style={{ color: C.success, fontSize: '16px' }}>{closedCount}</b></div>
            <div style={{ ...card, padding: '10px', backgroundColor: C.bg }}><p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Всего</p><b style={{ color: C.text, fontSize: '16px' }}>{orders.length}</b></div>
          </div>

          {orders.map(order => (
            <div key={order.id} style={{ ...card, padding: '14px', marginBottom: '8px', borderLeft: '3px solid ' + (order.status === 'Закрыто' ? C.success : C.danger) }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '10px', flexWrap: 'wrap' }}>
                <div style={{ flex: 1, minWidth: '200px' }}>
                  <b style={{ color: C.text, fontSize: '13px' }}>{order.orderNumber + ' · ' + (order.body || 'ГСН') + (order.inspector ? ' · ' + order.inspector : '')}</b>
                  <p style={{ color: C.danger, margin: '4px 0', fontSize: '12px' }}>{order.description || '—'}</p>
                  {order.recommendations && <p style={{ color: C.text, margin: '4px 0', fontSize: '11px' }}><b>Требования:</b> {order.recommendations}</p>}
                  <p style={{ color: C.textMuted, margin: '4px 0 0', fontSize: '11px' }}>{(order.date || '') + (order.deadline ? ' · срок: ' + order.deadline : '')}</p>
                  {order.response && <div style={{ marginTop: '8px', padding: '8px 10px', backgroundColor: C.successLight, borderRadius: '6px', fontSize: '11px', color: C.success }}><b>Ответ ({order.responseDate || '—'}):</b> {order.response}</div>}
                </div>
                <div style={{ display: 'flex', gap: '4px', alignItems: 'flex-start' }}>
                  <span style={badge(order.status === 'Закрыто' ? C.success : C.danger, order.status === 'Закрыто' ? C.successLight : C.dangerLight, order.status === 'Закрыто' ? C.successBorder : C.dangerBorder)}>{order.status || 'Открыто'}</span>
                  {order.status !== 'Закрыто' && <button onClick={() => closeOrder(order)} style={{ ...btnGr, padding: '4px 8px', fontSize: '11px' }}>Закрыть</button>}
                  <button onClick={() => deleteOrder(order)} style={{ ...btnR, padding: '4px 8px' }}><Trash2 size={11} /></button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

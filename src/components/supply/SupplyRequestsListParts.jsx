import React from 'react';
import { Bot, Check, X } from 'lucide-react';

export function SupplyRequestsEmpty({ C, card }) {
  return <div style={{ ...card, padding: '40px', textAlign: 'center', color: C.textMuted }}>Заявок нет</div>;
}

export function SupplyRequestsProjectHeader({
  C,
  card,
  badge,
  project,
  requests,
  collapsed,
  onToggle,
}) {
  const pendingCount = requests.filter(r => r.status === 'Новая' || r.status === 'Подтверждена прорабом').length;
  const urgentCount = requests.filter(r => r.urgency === 'срочная').length;

  return (
    <div
      onClick={onToggle}
      style={{
        ...card,
        padding: '12px 16px',
        cursor: 'pointer',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '4px',
        backgroundColor: pendingCount > 0 ? C.warningLight : C.bg,
        border: '1.5px solid ' + (pendingCount > 0 ? C.warningBorder : C.border),
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1 }}>
        <span style={{ fontSize: '14px' }}>{collapsed ? '▶' : '▼'}</span>
        <b style={{ color: C.text, fontSize: '14px' }}>🏗 {project}</b>
        <span style={{ fontSize: '12px', color: C.textSec }}>{requests.length + ' заявок'}</span>
        {pendingCount > 0 && <span style={badge(C.warning, C.warningLight, C.warningBorder)}>⏳ {pendingCount}</span>}
        {urgentCount > 0 && <span style={badge(C.danger, C.dangerLight, C.dangerBorder)}>🔴 {urgentCount}</span>}
      </div>
    </div>
  );
}

function StockCheckBlock({
  C,
  btnGr,
  request,
  supplyStockCheck,
  askSupplyAi,
  supplyAiLoading,
  supplyAiText,
}) {
  return (
    <div style={{ borderTop: '1.5px solid ' + C.border, paddingTop: '14px', marginTop: '12px' }}>
      {!supplyStockCheck && <p style={{ color: C.textMuted, fontSize: '12px' }}>⏳ Проверяю склад...</p>}
      {supplyStockCheck && supplyStockCheck.error && <p style={{ color: C.danger, fontSize: '12px' }}>Ошибка: {supplyStockCheck.error}</p>}
      {supplyStockCheck && !supplyStockCheck.error && (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', gap: '8px', marginBottom: '10px' }}>
            <div style={{ padding: '10px', backgroundColor: C.bg, borderRadius: '8px', border: '1.5px solid ' + C.border }}>
              <p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 3px' }}>Нужно</p>
              <b style={{ color: C.text, fontSize: '14px' }}>{supplyStockCheck.needed + ' ' + supplyStockCheck.unit}</b>
            </div>
            <div style={{ padding: '10px', backgroundColor: supplyStockCheck.totalAvailable > 0 ? C.successLight : C.warningLight, borderRadius: '8px', border: '1.5px solid ' + (supplyStockCheck.totalAvailable > 0 ? C.successBorder : C.warningBorder) }}>
              <p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 3px' }}>На складе</p>
              <b style={{ color: supplyStockCheck.totalAvailable > 0 ? C.success : C.warning, fontSize: '14px' }}>{Math.round(supplyStockCheck.totalAvailable * 100) / 100 + ' ' + supplyStockCheck.unit}</b>
            </div>
            <div style={{ padding: '10px', backgroundColor: supplyStockCheck.shortage > 0 ? C.dangerLight : C.successLight, borderRadius: '8px', border: '1.5px solid ' + (supplyStockCheck.shortage > 0 ? C.dangerBorder : C.successBorder) }}>
              <p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 3px' }}>Закупить</p>
              <b style={{ color: supplyStockCheck.shortage > 0 ? C.danger : C.success, fontSize: '14px' }}>{Math.round(supplyStockCheck.shortage * 100) / 100 + ' ' + supplyStockCheck.unit}</b>
            </div>
            {supplyStockCheck.projectBudget > 0 && (
              <div style={{ padding: '10px', backgroundColor: (supplyStockCheck.budgetRiskPercent > 80) ? C.dangerLight : C.bg, borderRadius: '8px', border: '1.5px solid ' + ((supplyStockCheck.budgetRiskPercent > 80) ? C.dangerBorder : C.border) }}>
                <p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 3px' }}>Бюджет занят</p>
                <b style={{ color: (supplyStockCheck.budgetRiskPercent > 80) ? C.danger : C.text, fontSize: '14px' }}>{Math.round(supplyStockCheck.budgetRiskPercent || 0) + '%'}</b>
              </div>
            )}
          </div>

          {supplyStockCheck.stockMatches && supplyStockCheck.stockMatches.length > 0 && (
            <div style={{ marginBottom: '10px' }}>
              <b style={{ color: C.text, fontSize: '12px', display: 'block', marginBottom: '6px' }}>📦 Похожие позиции на складе:</b>
              {supplyStockCheck.stockMatches.map((m, i) => (
                <div key={i} style={{ padding: '6px 10px', backgroundColor: C.bg, borderRadius: '6px', marginBottom: '4px', fontSize: '12px', color: C.text, border: '1px solid ' + C.border }}>
                  {m.name + ' — ' + m.quantity + ' ' + m.unit + (m.price ? ' · ' + Math.round(m.price).toLocaleString() + ' ₽/ед' : '')}
                </div>
              ))}
            </div>
          )}
          {supplyStockCheck.stockMatches && supplyStockCheck.stockMatches.length === 0 && <p style={{ color: C.warning, fontSize: '12px', marginBottom: '8px' }}>⚠️ Похожих позиций на складе не найдено — нужна закупка</p>}
          {supplyStockCheck.budgetRiskPercent > 80 && (
            <div style={{ padding: '10px 12px', backgroundColor: C.dangerLight, border: '1.5px solid ' + C.dangerBorder, borderRadius: '8px', marginBottom: '10px', fontSize: '12px', color: C.danger }}>
              ⚠️ Внимание: бюджет проекта почти исчерпан ({Math.round(supplyStockCheck.budgetRiskPercent)}%). Подумайте перед утверждением.
            </div>
          )}
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '6px' }}>
            <button onClick={() => askSupplyAi(request, supplyStockCheck)} disabled={supplyAiLoading} style={{ ...btnGr, fontSize: '12px', padding: '6px 12px', opacity: supplyAiLoading ? 0.6 : 1 }}>
              <Bot size={12} />{supplyAiLoading ? 'AI думает...' : '🤖 Совет AI'}
            </button>
          </div>
          {supplyAiText && (
            <div style={{ padding: '12px', backgroundColor: C.successLight, border: '1.5px solid ' + C.successBorder, borderRadius: '8px', fontSize: '12px', color: C.text }}>
              <b style={{ color: C.success, fontSize: '11px', display: 'block', marginBottom: '6px' }}>🤖 Рекомендация AI:</b>
              {supplyAiText}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function OfferItemsDetails({ C, offer, parseOfferItems }) {
  const items = parseOfferItems(offer);
  if (items.length < 2) return null;

  return (
    <details style={{ marginTop: '6px' }}>
      <summary style={{ cursor: 'pointer', fontSize: '11px', color: C.accent, fontWeight: '600' }}>📋 Разбивка по позициям ({items.length})</summary>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px', marginTop: '6px' }}>
        <thead>
          <tr style={{ backgroundColor: C.bg }}>
            <th style={{ padding: '4px 6px', textAlign: 'left', color: C.textSec, fontWeight: '600' }}>Материал</th>
            <th style={{ padding: '4px 6px', textAlign: 'center', color: C.textSec, fontWeight: '600' }}>Кол-во</th>
            <th style={{ padding: '4px 6px', textAlign: 'right', color: C.textSec, fontWeight: '600' }}>Цена/ед</th>
            <th style={{ padding: '4px 6px', textAlign: 'right', color: C.textSec, fontWeight: '600' }}>Сумма</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it, i) => (
            <tr key={i}>
              <td style={{ padding: '3px 6px', color: C.text }}>{it.materialName}</td>
              <td style={{ padding: '3px 6px', color: C.text, textAlign: 'center' }}>{it.quantity} {it.unit}</td>
              <td style={{ padding: '3px 6px', color: C.text, textAlign: 'right' }}>{Number(it.pricePerUnit || 0).toLocaleString('ru-RU')} ₽</td>
              <td style={{ padding: '3px 6px', color: C.text, textAlign: 'right', fontWeight: '600' }}>{Math.round(Number(it.totalPrice || it.pricePerUnit * it.quantity || 0)).toLocaleString('ru-RU')} ₽</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

const fmtQty = (value) => {
  const n = Number(value || 0);
  if (!Number.isFinite(n)) return '0';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 3 });
};

function SupplyEstimateControlBlock({ C, items }) {
  const rows = (items || [])
    .map(item => ({ item, control: item?.estimateControl || item?.estimate_control || null }))
    .filter(row => row.control);
  if (!rows.length) return null;

  const statusText = (status) => {
    if (status === 'no_active_estimate') return 'Нет активной сметы';
    if (status === 'no_estimate_material') return 'Вне сметы';
    if (status === 'over_estimate_need') return 'Сверх сметы';
    if (status === 'composite_work_material') return 'Комплектация работы';
    if (status === 'covered') return 'Закрыто';
    return 'В потребности';
  };
  const statusStyle = (status) => {
    if (status === 'no_estimate_material' || status === 'over_estimate_need') return [C.danger, C.dangerLight, C.dangerBorder];
    if (status === 'no_active_estimate') return [C.warning, C.warningLight, C.warningBorder];
    if (status === 'composite_work_material') return [C.info, C.infoLight, C.infoBorder];
    if (status === 'covered') return [C.textMuted, C.bg, C.border];
    return [C.success, C.successLight, C.successBorder];
  };

  return (
    <div style={{ marginTop: '10px', padding: '10px', borderRadius: '8px', border: '1.5px solid ' + C.border, backgroundColor: C.bg }}>
      <b style={{ display: 'block', color: C.text, fontSize: '12px', marginBottom: '8px' }}>📐 Контроль по смете</b>
      <div style={{ display: 'grid', gap: '6px' }}>
        {rows.map(({ item, control }, i) => {
          const [color, bg, border] = statusStyle(control.status);
          const unit = item.unit || control.unit || '';
          return (
            <div key={i} style={{ padding: '8px', borderRadius: '7px', border: '1px solid ' + border, backgroundColor: bg }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap', marginBottom: '5px' }}>
                <b style={{ color: C.text, fontSize: '12px' }}>{item.materialName || item.name || 'Материал'}</b>
                <span style={{ color, fontSize: '11px', fontWeight: 700 }}>{statusText(control.status)}</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(120px,1fr))', gap: '6px', fontSize: '11px', color: C.textSec }}>
                <span>План: <b style={{ color: C.text }}>{fmtQty(control.plannedQty)} {unit}</b></span>
                <span>На объекте: <b style={{ color: C.text }}>{fmtQty(control.stockQty)} {unit}</b></span>
                <span>В заявках: <b style={{ color: C.text }}>{fmtQty(control.requestedQty)} {unit}</b></span>
                <span>Остаток: <b style={{ color }}>{fmtQty(control.remainingQty)} {unit}</b></span>
                <span>После заявки: <b style={{ color }}>{fmtQty(control.remainingAfterRequest)} {unit}</b></span>
                {control.plannedSum > 0 && <span>По смете: <b style={{ color: C.text }}>{Number(control.plannedSum).toLocaleString('ru-RU')} ₽</b></span>}
                {control.status === 'composite_work_material' && control.workName && <span>Работа: <b style={{ color: C.text }}>{control.workName}</b></span>}
                {control.status === 'composite_work_material' && control.sectionName && <span>Раздел: <b style={{ color: C.text }}>{control.sectionName}</b></span>}
              </div>
              {control.controlMessage && <p style={{ margin: '6px 0 0', color: C.textSec, fontSize: '11px', lineHeight: 1.35 }}>{control.controlMessage}</p>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CompareResultBlock({ C, compareResult }) {
  return (
    <>
      {compareResult && !compareResult.error && (
        <div style={{ padding: '12px', backgroundColor: C.successLight, border: '1.5px solid ' + C.successBorder, borderRadius: '8px', marginBottom: '10px' }}>
          <b style={{ color: C.success, fontSize: '11px', display: 'block', marginBottom: '6px' }}>🤖 AI рекомендует: {compareResult.bestSupplier}</b>
          {compareResult.aiText && <p style={{ color: C.text, fontSize: '12px', margin: '0 0 8px', lineHeight: '1.5' }}>{compareResult.aiText}</p>}
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px' }}>
            <thead>
              <tr style={{ backgroundColor: C.bg }}>
                <th style={{ padding: '4px 6px', textAlign: 'left', color: C.textSec, fontWeight: '600', borderBottom: '1px solid ' + C.border }}>#</th>
                <th style={{ padding: '4px 6px', textAlign: 'left', color: C.textSec, fontWeight: '600', borderBottom: '1px solid ' + C.border }}>Поставщик</th>
                <th style={{ padding: '4px 6px', textAlign: 'right', color: C.textSec, fontWeight: '600', borderBottom: '1px solid ' + C.border }}>Цена</th>
                <th style={{ padding: '4px 6px', textAlign: 'center', color: C.textSec, fontWeight: '600', borderBottom: '1px solid ' + C.border }}>Срок</th>
                <th style={{ padding: '4px 6px', textAlign: 'left', color: C.textSec, fontWeight: '600', borderBottom: '1px solid ' + C.border }}>Оплата</th>
                <th style={{ padding: '4px 6px', textAlign: 'center', color: C.textSec, fontWeight: '600', borderBottom: '1px solid ' + C.border }}>Балл</th>
              </tr>
            </thead>
            <tbody>
              {(compareResult.ranking || []).map((r, i) => (
                <tr key={r.offerId} style={{ backgroundColor: i === 0 ? 'rgba(34,197,94,0.08)' : 'transparent' }}>
                  <td style={{ padding: '4px 6px', color: i === 0 ? C.success : C.textSec, fontWeight: '600' }}>{i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : (i + 1) + '.'}</td>
                  <td style={{ padding: '4px 6px', color: C.text }}>{r.supplier}{r.rating > 0 ? ' ⭐' + r.rating : ''}</td>
                  <td style={{ padding: '4px 6px', textAlign: 'right', color: C.text }}>{Number(r.pricePerUnit).toLocaleString('ru-RU')} ₽</td>
                  <td style={{ padding: '4px 6px', textAlign: 'center', color: C.text }}>{r.deliveryDays} дн.</td>
                  <td style={{ padding: '4px 6px', color: C.text, fontSize: '10px' }}>{r.paymentTerms}{r.vatIncluded === false ? ' · б/НДС' : ''}</td>
                  <td style={{ padding: '4px 6px', textAlign: 'center', color: i === 0 ? C.success : C.text, fontWeight: i === 0 ? '700' : '400' }}>{r.score}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ color: C.textMuted, fontSize: '10px', margin: '6px 0 0', fontStyle: 'italic' }}>Балл: цена 40% · срок 20% · условия 20% · рейтинг 20%. Финальное решение за вами.</p>
        </div>
      )}
      {compareResult && compareResult.error && (
        <div style={{ padding: '10px 12px', backgroundColor: C.warningLight, border: '1.5px solid ' + C.warningBorder, borderRadius: '8px', marginBottom: '10px', fontSize: '12px', color: C.text }}>
          ℹ️ {compareResult.error}
        </div>
      )}
    </>
  );
}

function OffersBlock({
  C,
  btnGr,
  btnR,
  badge,
  request,
  supplierOffers,
  compareResultByReq,
  compareLoadingReqId,
  runCompareKp,
  suppliers,
  fileSrc,
  parseOfferItems,
  selectSupplierOffer,
  rejectSupplierOffer,
  canApprove,
}) {
  const offers = (supplierOffers || []).filter(o => o.requestId === request.id);
  if (offers.length === 0) return null;

  const winner = offers.find(o => o.status === 'Утверждено');
  const receivedOffers = offers.filter(o => o.status === 'Получено' || o.status === 'Утверждено');
  const compareResult = compareResultByReq[request.id];
  const compareLoading = compareLoadingReqId === request.id;

  return (
    <div style={{ borderTop: '1.5px dashed ' + C.border, paddingTop: '10px', marginTop: '10px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', gap: '8px', flexWrap: 'wrap' }}>
        <b style={{ color: C.text, fontSize: '12px' }}>📊 КП от поставщиков ({offers.length}){winner ? ' · ✅ выбрано' : ''}</b>
        {receivedOffers.length >= 2 && canApprove && !winner && (
          <button onClick={() => runCompareKp(request.id)} disabled={compareLoading} style={{ ...btnGr, padding: '4px 10px', fontSize: '11px', opacity: compareLoading ? 0.6 : 1 }}>
            <Bot size={11} />{compareLoading ? 'AI сравнивает...' : '🤖 Сравнить через AI'}
          </button>
        )}
      </div>
      <CompareResultBlock C={C} compareResult={compareResult} />
      {offers.map(o => {
        const sup = suppliers.find(s => s.id === o.supplierId);
        const isWin = o.status === 'Утверждено';
        const isWait = o.status === 'Ожидает ответа';
        const isRej = o.status === 'Отклонено';
        const stC = isWin ? C.success : isRej ? C.danger : isWait ? C.warning : C.info;
        const stBg = isWin ? C.successLight : isRej ? C.dangerLight : isWait ? C.warningLight : C.infoLight;
        const stBd = isWin ? C.successBorder : isRej ? C.dangerBorder : isWait ? C.warningBorder : C.infoBorder;

        return (
          <div key={o.id} style={{ padding: '10px', backgroundColor: stBg, borderRadius: '6px', marginBottom: '6px', border: '1.5px solid ' + stBd }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px', flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: '200px' }}>
                <b style={{ fontSize: '13px', color: C.text }}>{sup ? sup.name : 'Поставщик #' + o.supplierId}{o.aiRecommended && <span style={{ marginLeft: '6px', fontSize: '10px', color: C.accent }}>🤖 AI рек.</span>}</b>
                {o.pricePerUnit ? (
                  <p style={{ color: C.textSec, margin: '2px 0', fontSize: '12px' }}>
                    {Number(o.pricePerUnit).toLocaleString('ru-RU') + ' ₽/ед'}
                    {o.totalPrice ? ' · итого ' + Number(o.totalPrice).toLocaleString('ru-RU') + ' ₽' : ''}
                    {o.deliveryDays ? ' · ' + o.deliveryDays + ' дн.' : ''}
                  </p>
                ) : <p style={{ color: C.textMuted, margin: '2px 0', fontSize: '12px', fontStyle: 'italic' }}>Поставщик ещё не ответил...</p>}
                {o.paymentTerms && <p style={{ color: C.textMuted, margin: 0, fontSize: '11px' }}>💳 {o.paymentTerms}{o.vatIncluded === false ? ' · без НДС' : ' · с НДС'}{o.validUntil ? ' · до ' + o.validUntil : ''}</p>}
                {o.supplierMessage && <p style={{ color: C.textSec, margin: '4px 0 0', fontSize: '11px', fontStyle: 'italic' }}>💬 «{o.supplierMessage}»</p>}
                {o.pdfUrl && <a href={fileSrc(o.pdfUrl)} target='_blank' rel='noopener noreferrer' style={{ fontSize: '11px', color: C.accent, display: 'inline-block', marginTop: '4px' }}>📄 PDF</a>}
                <OfferItemsDetails C={C} offer={o} parseOfferItems={parseOfferItems} />
              </div>
              <div style={{ display: 'flex', gap: '4px', alignItems: 'center', flexWrap: 'wrap' }}>
                <span style={badge(stC, stBg, stBd)}>{o.status}</span>
                {o.status === 'Получено' && canApprove && (
                  <>
                    <button onClick={() => selectSupplierOffer(o.id)} style={{ ...btnGr, padding: '3px 8px', fontSize: '11px' }}><Check size={11} />Выбрать</button>
                    <button onClick={() => rejectSupplierOffer(o.id)} style={{ ...btnR, padding: '3px 8px', fontSize: '11px' }}><X size={11} /></button>
                  </>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function RejectReasonBlock({
  C,
  inp,
  btnR,
  btnG,
  request,
  supplyRejectReason,
  setSupplyRejectReason,
  rejectSupply,
  setSupplyRejectId,
}) {
  return (
    <div style={{ borderTop: '1.5px solid ' + C.dangerBorder, paddingTop: '12px', marginTop: '10px' }}>
      <b style={{ color: C.danger, fontSize: '12px', display: 'block', marginBottom: '6px' }}>Причина отказа:</b>
      <textarea value={supplyRejectReason} onChange={e => setSupplyRejectReason(e.target.value)} placeholder="Например: уже есть на складе" style={{ ...inp, height: '50px', resize: 'vertical' }} />
      <div style={{ display: 'flex', gap: '6px' }}>
        <button onClick={() => rejectSupply(request.id)} style={{ ...btnR, fontSize: '12px', padding: '5px 12px' }}><X size={12} />Отклонить заявку</button>
        <button onClick={() => { setSupplyRejectId(null); setSupplyRejectReason(''); }} style={{ ...btnG, fontSize: '12px', padding: '5px 12px' }}>Отмена</button>
      </div>
    </div>
  );
}

export function SupplyRequestCard(props) {
  const {
    C,
    card,
    inp,
    btnO,
    btnG,
    btnB,
    btnGr,
    btnR,
    badge,
    request,
    user,
    statusColors,
    parseSupplyItems,
    renderSupplyRequestOrigin,
    supplyRequestOrigin,
    supplyExpandedId,
    setSupplyExpandedId,
    canConfirmProrab,
    canApprove,
    confirmSupplyAsProrab,
    approveSupplyAsDirector,
    openRequestKpModal,
    loadSupplyStockCheck,
    setSupplyRejectId,
    supplyRejectId,
    supplyRejectReason,
    setSupplyRejectReason,
    rejectSupply,
    cancelSupply,
    supplyStockCheck,
    askSupplyAi,
    supplyAiLoading,
    supplyAiText,
    supplierOffers,
    compareResultByReq,
    compareLoadingReqId,
    runCompareKp,
    suppliers,
    fileSrc,
    parseOfferItems,
    selectSupplierOffer,
    rejectSupplierOffer,
  } = props;

  const [stC, stBg, stBd] = statusColors(request.status);
  const isMine = request.createdBy === user.name || request.requestedById === user.id;
  const expanded = supplyExpandedId === request.id;
  const urgC = request.urgency === 'срочная' ? C.danger : request.urgency === 'низкая' ? C.textMuted : C.warning;
  const urgBg = request.urgency === 'срочная' ? C.dangerLight : request.urgency === 'низкая' ? C.bg : C.warningLight;
  const urgBd = request.urgency === 'срочная' ? C.dangerBorder : request.urgency === 'низкая' ? C.border : C.warningBorder;
  const items = parseSupplyItems(request);

  return (
    <div style={{ ...card, padding: '14px', marginBottom: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '10px', flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 280px' }}>
          {items.length <= 1 ? (() => {
            const it = items[0] || { materialName: request.materialName, quantity: request.quantity, unit: request.unit };
            return (
              <>
                <b style={{ color: C.text, fontSize: '14px' }}>{it.materialName}</b>
                <p style={{ color: C.textSec, margin: '3px 0', fontSize: '12px' }}>{it.quantity + ' ' + it.unit + ' · 🏗 ' + (request.project || '—')}</p>
              </>
            );
          })() : (
            <>
              <b style={{ color: C.text, fontSize: '14px' }}>📋 Заявка из {items.length} позиций <span style={{ color: C.textSec, fontSize: '12px', fontWeight: '400' }}>· 🏗 {request.project || '—'}</span></b>
              <ol style={{ margin: '4px 0 6px', paddingLeft: '20px', color: C.text, fontSize: '12px' }}>
                {items.map((it, i) => <li key={i} style={{ marginBottom: '2px' }}>{it.materialName} <span style={{ color: C.textSec }}>— {it.quantity} {it.unit}</span></li>)}
              </ol>
            </>
          )}
          <p style={{ color: C.textMuted, margin: '0', fontSize: '11px' }}>{(request.date || '') + ' · ' + (request.createdBy || '') + (request.requestedByRole ? ' (' + request.requestedByRole + ')' : '')}</p>
          {renderSupplyRequestOrigin(request)}
          {request.notes && !supplyRequestOrigin(request) && <p style={{ color: C.textSec, margin: '4px 0 0', fontSize: '11px', fontStyle: 'italic' }}>«{request.notes}»</p>}
          {request.status === 'Отклонена' && request.rejectReason && <p style={{ color: C.danger, margin: '4px 0 0', fontSize: '11px' }}>❌ Причина: {request.rejectReason}</p>}
          {request.prorabName && <p style={{ color: C.textMuted, margin: '2px 0 0', fontSize: '10px' }}>👷 Прораб: {request.prorabName}</p>}
          {request.directorName && <p style={{ color: C.textMuted, margin: '2px 0 0', fontSize: '10px' }}>👑 Директор: {request.directorName}</p>}
          <SupplyEstimateControlBlock C={C} items={items} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'flex-end' }}>
          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
            {request.urgency && request.urgency !== 'обычная' && <span style={badge(urgC, urgBg, urgBd)}>{request.urgency === 'срочная' ? '🔴 Срочно' : '🟢 Не срочно'}</span>}
            <span style={badge(stC, stBg, stBd)}>{request.status}</span>
          </div>
          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            {request.status === 'Новая' && canConfirmProrab && (
              <button onClick={() => confirmSupplyAsProrab(request.id)} style={{ ...btnGr, padding: '4px 10px', fontSize: '11px' }}><Check size={11} />Подтвердить</button>
            )}
            {request.status === 'Подтверждена прорабом' && canApprove && (
              <button onClick={() => approveSupplyAsDirector(request.id)} style={{ ...btnGr, padding: '4px 10px', fontSize: '11px' }}><Check size={11} />Утвердить</button>
            )}
            {(request.status === 'Утверждена' || request.status === 'КП запрошены') && canApprove && (
              <button onClick={() => openRequestKpModal(request.id)} style={{ ...btnO, padding: '4px 10px', fontSize: '11px' }}>📨 Запросить КП</button>
            )}
            {(request.status === 'Новая' || request.status === 'Подтверждена прорабом') && (canConfirmProrab || canApprove) && (
              <button onClick={async () => {
                if (expanded) {
                  setSupplyExpandedId(null);
                  return;
                }
                setSupplyExpandedId(request.id);
                await loadSupplyStockCheck(request.id);
              }} style={{ ...btnB, padding: '4px 10px', fontSize: '11px' }}><Bot size={11} />Склад / AI</button>
            )}
            {(request.status === 'Новая' || request.status === 'Подтверждена прорабом') && (canConfirmProrab || canApprove) && (
              <button onClick={() => setSupplyRejectId(request.id)} style={{ ...btnR, padding: '4px 10px', fontSize: '11px' }}><X size={11} />Отклонить</button>
            )}
            {isMine && (request.status === 'Новая' || request.status === 'Подтверждена прорабом') && (
              <button onClick={() => cancelSupply(request.id)} style={{ ...btnG, padding: '4px 10px', fontSize: '11px' }}>Отменить</button>
            )}
          </div>
        </div>
      </div>
      {supplyRejectId === request.id && (
        <RejectReasonBlock
          C={C}
          inp={inp}
          btnR={btnR}
          btnG={btnG}
          request={request}
          supplyRejectReason={supplyRejectReason}
          setSupplyRejectReason={setSupplyRejectReason}
          rejectSupply={rejectSupply}
          setSupplyRejectId={setSupplyRejectId}
        />
      )}
      {expanded && (
        <StockCheckBlock
          C={C}
          btnGr={btnGr}
          request={request}
          supplyStockCheck={supplyStockCheck}
          askSupplyAi={askSupplyAi}
          supplyAiLoading={supplyAiLoading}
          supplyAiText={supplyAiText}
        />
      )}
      <OffersBlock
        C={C}
        btnGr={btnGr}
        btnR={btnR}
        badge={badge}
        request={request}
        supplierOffers={supplierOffers}
        compareResultByReq={compareResultByReq}
        compareLoadingReqId={compareLoadingReqId}
        runCompareKp={runCompareKp}
        suppliers={suppliers}
        fileSrc={fileSrc}
        parseOfferItems={parseOfferItems}
        selectSupplierOffer={selectSupplierOffer}
        rejectSupplierOffer={rejectSupplierOffer}
        canApprove={canApprove}
      />
    </div>
  );
}

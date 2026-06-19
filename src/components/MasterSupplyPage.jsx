import React from 'react';
import { Plus } from 'lucide-react';
import SupplyRequestForm from './SupplyRequestForm';
import SupplyRequestsList from './SupplyRequestsList';

export default function MasterSupplyPage({
  C,
  card,
  inp,
  btnO,
  btnG,
  btnR,
  badge,
  isMobile = false,
  role,
  user,
  showSupplyForm,
  setShowSupplyForm,
  supplyRequests,
  supplyTemplates,
  applySupplyTemplate,
  deleteSupplyTemplate,
  newSupplyReq,
  setNewSupplyReq,
  priceHints,
  fetchPriceHint,
  UNITS,
  masterProjectOptions,
  renderSupplyPlanningHint,
  createSupplyReq,
  saveSupplyTemplate,
  parseSupplyItems,
  renderSupplyRequestOrigin,
  supplyRequestOrigin,
  cancelSupply,
  supplyCollapsedProjects,
  setSupplyCollapsedProjects,
}) {
  const myReqs = (supplyRequests || []).filter(
    request => request.createdBy === user.name || request.requestedById === user.id
  );
  const pendingReqs = myReqs.filter(
    request => request.status === 'Новая' || request.status === 'Подтверждена прорабом'
  );
  const approvedReqs = myReqs.filter(request => request.status === 'Утверждена');
  const rejectedReqs = myReqs.filter(request => request.status === 'Отклонена');

  const statusColors = (status) => {
    if (status === 'Утверждена') return [C.success, C.successLight, C.successBorder];
    if (status === 'Подтверждена прорабом') {
      return [C.info || C.accent, C.infoLight || C.accentLight, C.infoBorder || C.accentBorder || C.border];
    }
    if (status === 'Отклонена') return [C.danger, C.dangerLight, C.dangerBorder];
    if (status === 'Отменена') return [C.textMuted, C.bg, C.border];
    return [C.warning, C.warningLight, C.warningBorder];
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
        <h3 style={{ color: C.text, margin: 0, fontSize: '18px', fontWeight: '700' }}>🛒 Заявки на материалы</h3>
        <button onClick={() => setShowSupplyForm(!showSupplyForm)} style={btnO}>
          <Plus size={14} />
          {showSupplyForm ? 'Закрыть форму' : 'Новая заявка'}
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', gap: '10px', marginBottom: '14px' }}>
        <div style={{ ...card, padding: '12px', backgroundColor: C.warningLight, border: '1.5px solid ' + C.warningBorder }}>
          <p style={{ color: C.warning, fontSize: '11px', margin: '0 0 4px', fontWeight: '600' }}>⏳ В работе</p>
          <b style={{ color: C.warning, fontSize: '18px' }}>{pendingReqs.length}</b>
        </div>
        <div style={{ ...card, padding: '12px', backgroundColor: C.successLight, border: '1.5px solid ' + C.successBorder }}>
          <p style={{ color: C.success, fontSize: '11px', margin: '0 0 4px', fontWeight: '600' }}>✅ Утверждено</p>
          <b style={{ color: C.success, fontSize: '18px' }}>{approvedReqs.length}</b>
        </div>
        {rejectedReqs.length > 0 && (
          <div style={{ ...card, padding: '12px', backgroundColor: C.dangerLight, border: '1.5px solid ' + C.dangerBorder }}>
            <p style={{ color: C.danger, fontSize: '11px', margin: '0 0 4px', fontWeight: '600' }}>❌ Отклонено</p>
            <b style={{ color: C.danger, fontSize: '18px' }}>{rejectedReqs.length}</b>
          </div>
        )}
      </div>

      {showSupplyForm && (
        <SupplyRequestForm
          C={C}
          card={card}
          inp={inp}
          btnO={btnO}
          btnG={btnG}
          btnR={btnR}
          role={role}
          isLeadership={false}
          supplyTemplates={supplyTemplates}
          applySupplyTemplate={applySupplyTemplate}
          deleteSupplyTemplate={deleteSupplyTemplate}
          newSupplyReq={newSupplyReq}
          setNewSupplyReq={setNewSupplyReq}
          priceHints={priceHints}
          fetchPriceHint={fetchPriceHint}
          UNITS={UNITS}
          projects={masterProjectOptions}
          renderSupplyPlanningHint={renderSupplyPlanningHint}
          createSupplyReq={createSupplyReq}
          saveSupplyTemplate={saveSupplyTemplate}
          setShowSupplyForm={setShowSupplyForm}
        />
      )}

      {myReqs.length === 0 ? (
        <div style={{ ...card, padding: '30px', textAlign: 'center', color: C.textMuted }}>
          Заявок ещё нет. Нажмите «Новая заявка», если не хватает материала.
        </div>
      ) : (
        <SupplyRequestsList
          C={C}
          card={card}
          inp={inp}
          btnO={btnO}
          btnG={btnG}
          btnR={btnR}
          badge={badge}
          list={myReqs}
          isMobile={isMobile}
          user={user}
          statusColors={statusColors}
          supplyCollapsedProjects={supplyCollapsedProjects}
          setSupplyCollapsedProjects={setSupplyCollapsedProjects}
          parseSupplyItems={parseSupplyItems}
          renderSupplyRequestOrigin={renderSupplyRequestOrigin}
          supplyRequestOrigin={supplyRequestOrigin}
          supplyExpandedId={null}
          setSupplyExpandedId={() => {}}
          canConfirmProrab={false}
          canApprove={false}
          confirmSupplyAsProrab={() => {}}
          approveSupplyAsDirector={() => {}}
          openRequestKpModal={() => {}}
          loadSupplyStockCheck={async () => {}}
          setSupplyRejectId={() => {}}
          supplyRejectId={null}
          supplyRejectReason=""
          setSupplyRejectReason={() => {}}
          rejectSupply={() => {}}
          cancelSupply={cancelSupply}
          supplyStockCheck={null}
          askSupplyAi={async () => {}}
          supplyAiLoading={false}
          supplyAiText=""
          supplierOffers={[]}
          compareResultByReq={{}}
          compareLoadingReqId={null}
          runCompareKp={() => {}}
          suppliers={[]}
          fileSrc={(value) => value}
          parseOfferItems={() => []}
          selectSupplierOffer={() => {}}
          rejectSupplierOffer={() => {}}
        />
      )}
    </div>
  );
}

import React from 'react';
import { Search } from 'lucide-react';
import SupplyHeaderTabs from './SupplyHeaderTabs';
import SupplyRequestForm from './SupplyRequestForm';
import SupplyRequestsList from './SupplyRequestsList';
import SupplyDeliveriesPanel from './SupplyDeliveriesPanel';
import SupplyCatalogPanel from './SupplyCatalogPanel';
import SupplySuppliersPanel from './SupplySuppliersPanel';
import SupplySupplierInvoicesPanel from './SupplySupplierInvoicesPanel';

export default function SupplyPage({
  API,
  C,
  card,
  inp,
  isMobile = false,
  tblH,
  tblC,
  btnO,
  btnG,
  btnB,
  btnGr,
  btnR,
  badge,
  user,
  users = [],
  isLeadership,
  isFinanceRole,
  showSupplyForm,
  setShowSupplyForm,
  showForm,
  setShowForm,
  supplyTab,
  setSupplyTab,
  supplyRequests,
  listSearch,
  setListSearch,
  matchSearch,
  supplyTemplates,
  applySupplyTemplate,
  deleteSupplyTemplate,
  newSupplyReq,
  setNewSupplyReq,
  priceHints,
  fetchPriceHint,
  UNITS,
  projects,
  getProjectWorkPackageOptions,
  renderSupplyPlanningHint,
  createSupplyReq,
  saveSupplyTemplate,
  supplyCollapsedProjects,
  setSupplyCollapsedProjects,
  parseSupplyItems,
  renderSupplyRequestOrigin,
  supplyRequestOrigin,
  supplyExpandedId,
  setSupplyExpandedId,
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
  withdrawSupplierOffer,
  supplierInvoices,
  newSupplierInvoice,
  setNewSupplierInvoice,
  expandedProject,
  setExpandedProject,
  loadAll,
  toNum,
  supplierCategories,
  editingItem,
  setEditingItem,
  newSupplier,
  setNewSupplier,
  saveSupplier,
  deleteSupplier,
  setSupplierInviteForm,
  setGeneratedInviteLink,
  setShowSupplierInviteModal,
  supplierCatalog,
  supplyClaims,
  supplyDeliveries,
  receivingDeliveryId,
  setReceivingDeliveryId,
  receiveForm,
  setReceiveForm,
  deliveryAiLoadingId,
  setDeliveryAiLoadingId,
  deliveryAiResultById,
  setDeliveryAiResultById,
  runDeliveryAiCheck,
  receiveSupplyDelivery,
  invoices,
  showPreview,
  buildInvoiceContent,
  uploadPhoto,
}) {
  const currentUser = user || {};
  const role = currentUser.role || '';
  const isLeadershipUser = typeof isLeadership === 'function' ? isLeadership() : Boolean(isLeadership);
  const isFinanceUser = typeof isFinanceRole === 'function' ? isFinanceRole() : Boolean(isFinanceRole);
  const canCreate = ['мастер', 'субподрядчик', 'бригадир', 'прораб', 'директор', 'зам_директора', 'кладовщик', 'снабженец'].includes(role);
  const canConfirmProrab = role === 'прораб' || isLeadershipUser;
  const canApprove = isLeadershipUser;
  const canViewSuppliers = ['директор', 'зам_директора', 'прораб', 'кладовщик', 'снабженец', 'бухгалтер'].includes(role);
  const canViewDeliveries = ['директор', 'зам_директора', 'прораб', 'кладовщик', 'снабженец', 'бухгалтер'].includes(role);

  let tabs = [];
  if (['мастер','субподрядчик','бригадир'].includes(role)) {
    tabs = [{ id: 'mine', label: '📋 Мои заявки' }];
  } else if (role === 'прораб') {
    tabs = [
      { id: 'inbox', label: '⏳ Ждут подтверждения' },
      { id: 'all', label: '📋 Все заявки' },
      { id: 'deliveries', label: '🚚 Поставки' },
      { id: 'suppliers', label: '🚚 Поставщики' },
      { id: 'catalog', label: '📦 Каталоги' },
    ];
  } else if (role === 'бухгалтер') {
    tabs = [
      { id: 'invoices', label: '💳 Счета' },
      { id: 'all', label: '📋 Все заявки' },
      { id: 'deliveries', label: '🚚 Поставки' },
      { id: 'suppliers', label: '🚚 Поставщики' },
      { id: 'catalog', label: '📦 Каталоги' },
    ];
  } else if (isLeadershipUser) {
    tabs = [
      { id: 'inbox', label: '⏳ На утверждение' },
      { id: 'all', label: '📋 Все заявки' },
      { id: 'deliveries', label: '🚚 Поставки' },
      { id: 'invoices', label: '💳 Счета' },
      { id: 'suppliers', label: '🚚 Поставщики' },
      { id: 'catalog', label: '📦 Каталоги' },
    ];
  } else {
    tabs = [
      { id: 'approved', label: '✅ Утверждённые' },
      { id: 'all', label: '📋 Все' },
      { id: 'deliveries', label: '🚚 Поставки' },
      { id: 'invoices', label: '💳 Счета' },
      { id: 'suppliers', label: '🚚 Поставщики' },
      { id: 'catalog', label: '📦 Каталоги' },
    ];
  }

  if (!canViewSuppliers) tabs = tabs.filter(tab => tab.id !== 'suppliers');
  if (!canViewDeliveries) tabs = tabs.filter(tab => tab.id !== 'deliveries');

  let list = supplyRequests || [];
  const curTab = tabs.find(tab => tab.id === supplyTab) ? supplyTab : tabs[0].id;
  if (['мастер','субподрядчик','бригадир'].includes(role)) {
    list = list.filter(request => request.createdBy === currentUser.name || request.requestedById === currentUser.id);
  } else if (role === 'прораб') {
    if (curTab === 'inbox') list = list.filter(request => request.status === 'Новая');
  } else if (isLeadershipUser) {
    if (curTab === 'inbox') list = list.filter(
      request => request.status === 'Подтверждена прорабом' || request.status === 'Новая'
    );
  } else if (curTab === 'approved') {
    list = list.filter(request => request.status === 'Утверждена');
  }

  list = list.filter(request => matchSearch(listSearch, request.materialName, request.project, request.createdBy));

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
      <SupplyHeaderTabs
        C={C}
        btnO={btnO}
        btnG={btnG}
        role={role}
        isLeadership={isLeadershipUser}
        canCreate={canCreate}
        curTab={curTab}
        tabs={tabs}
        showSupplyForm={showSupplyForm}
        setShowSupplyForm={setShowSupplyForm}
        setSupplyTab={setSupplyTab}
        setShowForm={setShowForm}
      />

      {curTab === 'invoices' && (
        <SupplySupplierInvoicesPanel
          C={C}
          card={card}
          inp={inp}
          btnO={btnO}
          btnG={btnG}
          btnB={btnB}
          btnGr={btnGr}
          btnR={btnR}
          badge={badge}
          user={user}
          users={users}
          suppliers={suppliers}
          projects={projects}
          supplierInvoices={supplierInvoices}
          newSupplierInvoice={newSupplierInvoice}
          setNewSupplierInvoice={setNewSupplierInvoice}
          listSearch={listSearch}
          setListSearch={setListSearch}
          expandedProject={expandedProject}
          setExpandedProject={setExpandedProject}
          canPay={isFinanceUser}
          matchSearch={matchSearch}
          loadAll={loadAll}
          toNum={toNum}
        />
      )}

      {curTab === 'suppliers' && (
        <SupplySuppliersPanel
          C={C}
          card={card}
          inp={inp}
          btnO={btnO}
          btnG={btnG}
          btnB={btnB}
          btnGr={btnGr}
          btnR={btnR}
          user={user}
          suppliers={suppliers}
          supplierCategories={supplierCategories}
          showForm={showForm}
          setShowForm={setShowForm}
          editingItem={editingItem}
          setEditingItem={setEditingItem}
          newSupplier={newSupplier}
          setNewSupplier={setNewSupplier}
          saveSupplier={saveSupplier}
          deleteSupplier={deleteSupplier}
          listSearch={listSearch}
          setListSearch={setListSearch}
          matchSearch={matchSearch}
          setSupplierInviteForm={setSupplierInviteForm}
          setGeneratedInviteLink={setGeneratedInviteLink}
          setShowSupplierInviteModal={setShowSupplierInviteModal}
          loadAll={loadAll}
          supplierInvoices={supplierInvoices}
          supplierOffers={supplierOffers}
          supplyDeliveries={supplyDeliveries}
          invoices={invoices}
          supplierCatalog={supplierCatalog}
          fileSrc={fileSrc}
          uploadPhoto={uploadPhoto}
        />
      )}

      {curTab === 'catalog' && (
        <SupplyCatalogPanel
          C={C}
          card={card}
          inp={inp}
          tblH={tblH}
          tblC={tblC}
          badge={badge}
          supplierCatalog={supplierCatalog}
          listSearch={listSearch}
          setListSearch={setListSearch}
        />
      )}

      {curTab === 'deliveries' && (
        <SupplyDeliveriesPanel
          C={C}
          card={card}
          inp={inp}
          btnO={btnO}
          btnG={btnG}
          btnB={btnB}
          btnGr={btnGr}
          badge={badge}
          role={role}
          supplyClaims={supplyClaims}
          supplyDeliveries={supplyDeliveries}
          receivingDeliveryId={receivingDeliveryId}
          setReceivingDeliveryId={setReceivingDeliveryId}
          receiveForm={receiveForm}
          setReceiveForm={setReceiveForm}
          deliveryAiLoadingId={deliveryAiLoadingId}
          setDeliveryAiLoadingId={setDeliveryAiLoadingId}
          deliveryAiResultById={deliveryAiResultById}
          setDeliveryAiResultById={setDeliveryAiResultById}
          runDeliveryAiCheck={runDeliveryAiCheck}
          receiveSupplyDelivery={receiveSupplyDelivery}
          invoices={invoices}
          showPreview={showPreview}
          buildInvoiceContent={buildInvoiceContent}
          uploadPhoto={uploadPhoto}
        />
      )}

      {curTab !== 'catalog' && curTab !== 'invoices' && curTab !== 'suppliers' && curTab !== 'deliveries' && showSupplyForm && (
        <SupplyRequestForm
          C={C}
          card={card}
          inp={inp}
          btnO={btnO}
          btnG={btnG}
          btnR={btnR}
          role={role}
          isLeadership={isLeadershipUser}
          supplyTemplates={supplyTemplates}
          applySupplyTemplate={applySupplyTemplate}
          deleteSupplyTemplate={deleteSupplyTemplate}
          newSupplyReq={newSupplyReq}
          setNewSupplyReq={setNewSupplyReq}
          priceHints={priceHints}
          fetchPriceHint={fetchPriceHint}
          UNITS={UNITS}
          projects={projects}
          getProjectWorkPackageOptions={getProjectWorkPackageOptions}
          renderSupplyPlanningHint={renderSupplyPlanningHint}
          createSupplyReq={createSupplyReq}
          saveSupplyTemplate={saveSupplyTemplate}
          setShowSupplyForm={setShowSupplyForm}
        />
      )}

      {curTab !== 'catalog' && curTab !== 'invoices' && curTab !== 'suppliers' && curTab !== 'deliveries' && (
        <div style={{ position: 'relative', marginBottom: '12px' }}>
          <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: C.textMuted }} />
          <input
            placeholder="🔍 Поиск по материалу, объекту, автору"
            value={listSearch}
            onChange={e => setListSearch(e.target.value)}
            style={{ ...inp, marginBottom: 0, paddingLeft: '32px' }}
          />
        </div>
      )}

      {curTab !== 'catalog' && curTab !== 'invoices' && curTab !== 'suppliers' && curTab !== 'deliveries' && (
        <SupplyRequestsList
          API={API}
          C={C}
          card={card}
          inp={inp}
          btnO={btnO}
          btnG={btnG}
          btnB={btnB}
          btnGr={btnGr}
          btnR={btnR}
          badge={badge}
          list={list}
          isMobile={isMobile}
          user={user}
          statusColors={statusColors}
          supplyCollapsedProjects={supplyCollapsedProjects}
          setSupplyCollapsedProjects={setSupplyCollapsedProjects}
          parseSupplyItems={parseSupplyItems}
          renderSupplyRequestOrigin={renderSupplyRequestOrigin}
          supplyRequestOrigin={supplyRequestOrigin}
          supplyExpandedId={supplyExpandedId}
          setSupplyExpandedId={setSupplyExpandedId}
          canConfirmProrab={canConfirmProrab}
          canApprove={canApprove}
          confirmSupplyAsProrab={confirmSupplyAsProrab}
          approveSupplyAsDirector={approveSupplyAsDirector}
          openRequestKpModal={openRequestKpModal}
          loadSupplyStockCheck={loadSupplyStockCheck}
          setSupplyRejectId={setSupplyRejectId}
          supplyRejectId={supplyRejectId}
          supplyRejectReason={supplyRejectReason}
          setSupplyRejectReason={setSupplyRejectReason}
          rejectSupply={rejectSupply}
          cancelSupply={cancelSupply}
          supplyStockCheck={supplyStockCheck}
          askSupplyAi={askSupplyAi}
          supplyAiLoading={supplyAiLoading}
          supplyAiText={supplyAiText}
          supplierOffers={supplierOffers}
          compareResultByReq={compareResultByReq}
          compareLoadingReqId={compareLoadingReqId}
          runCompareKp={runCompareKp}
          suppliers={suppliers}
          fileSrc={fileSrc}
          parseOfferItems={parseOfferItems}
          selectSupplierOffer={selectSupplierOffer}
          rejectSupplierOffer={rejectSupplierOffer}
          withdrawSupplierOffer={withdrawSupplierOffer}
        />
      )}
    </div>
  );
}

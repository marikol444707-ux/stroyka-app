import React from 'react';
import {
  ClientsPage,
  PricelistsPage,
  SuppliersPage,
  UsersPage,
} from '../app/lazyComponents';

export default function AppDirectoryPages({ activePage, ui, constants, state, actions }) {
  const { API, C, badge, btnB, btnG, btnGr, btnO, btnR, card, inp, isMobile, tbl, tblC, tblH } = ui;
  const { PRICELISTS_DATA, ROLE_GROUPS, ROLE_LABELS, ROLES, SUPPLIER_CATEGORIES, UNITS } = constants;
  const {
    clients,
    compareLoadingReqId,
    compareResultByReq,
    editingItem,
    editingPlItem,
    estimatesList,
    expandedClient,
    expandedGroup,
    fileSrc,
    inlineEditPl,
    inlineEditPlData,
    inviteCodes,
    listSearch,
    newClient,
    newInviteRole,
    newOffer,
    newPlItem,
    newPricelist,
    newRequest,
    newSupplier,
    newUser,
    pricelistItems,
    pricelists,
    projects,
    searchUser,
    selectedPricelist,
    showForm,
    showInvites,
    showOffers,
    suppliers,
    suppliersTab,
    supplierOffers,
    supplyDeliveries,
    supplyHistory,
    supplyRequestOrigin,
    supplyRequests,
    user,
    users,
  } = state;
  const {
    approveOffer,
    buildPricelistContent,
    cancelInlinePlEdit,
    cancelRequest,
    copyPricelist,
    createInvite,
    deleteClient,
    deleteInvite,
    deletePlItem,
    deletePricelist,
    deleteSupplier,
    deleteUser,
    exportToExcel,
    generateTempPassword,
    getProjectWorkPackageOptions,
    isLeadership,
    loadAll,
    loadPricelistItems,
    matchSearch,
    parseOfferItems,
    parseSupplyItems,
    renderSupplyRequestOrigin,
    resetUserTwoFactor,
    roleColor,
    runCompareKp,
    saveClient,
    saveInlinePlItem,
    saveOffer,
    savePlItem,
    savePricelist,
    saveRequest,
    saveSupplier,
    saveUser,
    selectSupplierOffer,
    setEditingItem,
    setEditingPlItem,
    setExpandedClient,
    setExpandedGroup,
    setFromEstimateForm,
    setGeneratedInviteLink,
    setGeneratePricelistForm,
    setInlineEditPlData,
    setInlineEditPrice,
    setListSearch,
    setNewClient,
    setNewInviteRole,
    setNewOffer,
    setNewPlItem,
    setNewPricelist,
    setNewRequest,
    setNewSupplier,
    setNewUser,
    setPricelistItems,
    setSearchUser,
    setSelectedPricelist,
    setShowForm,
    setShowFromEstimate,
    setShowGeneratePricelist,
    setShowInvites,
    setShowOffers,
    setShowSupplierInviteModal,
    setSupplierInviteForm,
    setSuppliersTab,
    showPreview,
    startInlinePlEdit,
    rejectSupplierOffer,
    toggleUserActive,
  } = actions;
  const isLeadershipUser = typeof isLeadership === 'function' ? isLeadership() : Boolean(isLeadership);

  return (
    <>
      {activePage === 'clients' && (
        <ClientsPage C={C} card={card} inp={inp} btnO={btnO} btnG={btnG} btnR={btnR} clients={clients} projects={projects} showForm={showForm} setShowForm={setShowForm} editingItem={editingItem} setEditingItem={setEditingItem} newClient={newClient} setNewClient={setNewClient} saveClient={saveClient} listSearch={listSearch} setListSearch={setListSearch} expandedClient={expandedClient} setExpandedClient={setExpandedClient} deleteClient={deleteClient} matchSearch={matchSearch} isMobile={isMobile} />
      )}

      {activePage === 'suppliers' && (
        <SuppliersPage
          C={C}
          card={card}
          inp={inp}
          btnO={btnO}
          btnG={btnG}
          btnGr={btnGr}
          btnR={btnR}
          btnB={btnB}
          badge={badge}
          suppliersTab={suppliersTab}
          setSuppliersTab={setSuppliersTab}
          showForm={showForm}
          setShowForm={setShowForm}
          editingItem={editingItem}
          setEditingItem={setEditingItem}
          newSupplier={newSupplier}
          setNewSupplier={setNewSupplier}
          supplierCategories={SUPPLIER_CATEGORIES}
          suppliers={suppliers}
          saveSupplier={saveSupplier}
          deleteSupplier={deleteSupplier}
          loadAll={loadAll}
          listSearch={listSearch}
          setListSearch={setListSearch}
          matchSearch={matchSearch}
          setSupplierInviteForm={setSupplierInviteForm}
          setGeneratedInviteLink={setGeneratedInviteLink}
          setShowSupplierInviteModal={setShowSupplierInviteModal}
          newRequest={newRequest}
          setNewRequest={setNewRequest}
          projects={projects}
          getProjectWorkPackageOptions={getProjectWorkPackageOptions}
          units={UNITS}
          saveRequest={saveRequest}
          supplyRequests={supplyRequests}
          parseSupplyItems={parseSupplyItems}
          renderSupplyRequestOrigin={renderSupplyRequestOrigin}
          supplyRequestOrigin={supplyRequestOrigin}
          showOffers={showOffers}
          setShowOffers={setShowOffers}
          cancelRequest={cancelRequest}
          newOffer={newOffer}
          setNewOffer={setNewOffer}
          saveOffer={saveOffer}
          supplierOffers={supplierOffers}
          isLeadership={isLeadership}
          approveOffer={approveOffer}
          compareResultByReq={compareResultByReq}
          compareLoadingReqId={compareLoadingReqId}
          runCompareKp={runCompareKp}
          fileSrc={fileSrc}
          parseOfferItems={parseOfferItems}
          selectSupplierOffer={selectSupplierOffer}
          rejectSupplierOffer={rejectSupplierOffer}
          supplyDeliveries={supplyDeliveries}
          supplyHistory={supplyHistory}
        />
      )}

      {activePage === 'pricelists' && (
        <PricelistsPage API={API} C={C} PRICELISTS_DATA={PRICELISTS_DATA} UNITS={UNITS} buildPricelistContent={buildPricelistContent} btnB={btnB} btnG={btnG} btnGr={btnGr} btnO={btnO} btnR={btnR} card={card} copyPricelist={copyPricelist} deletePlItem={deletePlItem} deletePricelist={deletePricelist} editingPlItem={editingPlItem} exportToExcel={exportToExcel} inlineEditPl={inlineEditPl} inlineEditPlData={inlineEditPlData} inp={inp} listSearch={listSearch} loadAll={loadAll} loadPricelistItems={loadPricelistItems} matchSearch={matchSearch} newPlItem={newPlItem} newPricelist={newPricelist} pricelistItems={pricelistItems} pricelists={pricelists} saveInlinePlItem={saveInlinePlItem} savePlItem={savePlItem} savePricelist={savePricelist} selectedPricelist={selectedPricelist} setEditingItem={setEditingItem} setEditingPlItem={setEditingPlItem} setFromEstimateForm={setFromEstimateForm} setGeneratePricelistForm={setGeneratePricelistForm} setInlineEditPlData={setInlineEditPlData} setInlineEditPrice={setInlineEditPrice} setListSearch={setListSearch} setNewPlItem={setNewPlItem} setNewPricelist={setNewPricelist} setPricelistItems={setPricelistItems} setSelectedPricelist={setSelectedPricelist} setShowForm={setShowForm} setShowFromEstimate={setShowFromEstimate} setShowGeneratePricelist={setShowGeneratePricelist} showForm={showForm} showPreview={showPreview} startInlinePlEdit={startInlinePlEdit} cancelInlinePlEdit={cancelInlinePlEdit} tbl={tbl} tblC={tblC} tblH={tblH} />
      )}

      {activePage === 'users' && isLeadershipUser && (
        <UsersPage
          C={C}
          card={card}
          inp={inp}
          btnO={btnO}
          btnG={btnG}
          btnGr={btnGr}
          btnR={btnR}
          badge={badge}
          users={users}
          user={user}
          projects={projects}
          estimatesList={estimatesList}
          ROLES={ROLES}
          ROLE_LABELS={ROLE_LABELS}
          ROLE_GROUPS={ROLE_GROUPS}
          roleColor={roleColor}
          searchUser={searchUser}
          setSearchUser={setSearchUser}
          showForm={showForm}
          setShowForm={setShowForm}
          editingItem={editingItem}
          setEditingItem={setEditingItem}
          newUser={newUser}
          setNewUser={setNewUser}
          saveUser={saveUser}
          generateTempPassword={generateTempPassword}
          toggleUserActive={toggleUserActive}
          deleteUser={deleteUser}
          resetUserTwoFactor={resetUserTwoFactor}
          showInvites={showInvites}
          setShowInvites={setShowInvites}
          newInviteRole={newInviteRole}
          setNewInviteRole={setNewInviteRole}
          createInvite={createInvite}
          inviteCodes={inviteCodes}
          deleteInvite={deleteInvite}
          expandedGroup={expandedGroup}
          setExpandedGroup={setExpandedGroup}
        />
      )}
    </>
  );
}

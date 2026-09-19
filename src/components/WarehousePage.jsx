import React from 'react';
import ToolsWorkspace from '../features/tool-custody/ToolsWorkspace';
import { toolCustodyEnabled } from '../features/tool-custody/ToolCustodyPanel';
import InventoryWorkspace, { inventoryReconciliationEnabled } from '../features/inventory-reconciliation/InventoryWorkspace';
import WarehouseInvoicesPanel from './WarehouseInvoicesPanel';
import WarehouseMainStockPanel from './WarehouseMainStockPanel';
import CompanyWarehouses from '../features/company-warehouses/CompanyWarehouses';
import WarehouseHistoryPanel from './WarehouseHistoryPanel';
import WarehouseOperationsPanel from './WarehouseOperationsPanel';
import WarehouseDistributionPanel from '../features/warehouse/WarehouseDistributionPanel';
import WarehouseObjectsPanel from './WarehouseObjectsPanel';
import WarehouseTabsNav from './WarehouseTabsNav';
import WarehouseMaterialControlOverview from './WarehouseMaterialControlOverview';
import HumanApprovedActionReviewPanel from '../features/human-approved-actions/HumanApprovedActionReviewPanel';
import { roleFlagsForUser } from '../utils/accessUtils';

export default function WarehousePage(props) {
  const {
    warehouseTab,
    setWarehouseTab,
    setShowForm,
    btnO,
    btnG,
    C,
    badge,
    btnB,
    buildMaterialRequirementContent,
    card,
    exportToExcel,
    isFinanceRole,
    isLeadership,
    materialControlSummaryForProject,
    materialReconciliationRows,
    parseSupplyItems,
    projects,
    setSelectedWarehouseProject,
    visibleActiveProjects,
    showForm,
    editingItem,
    setEditingItem,
    inp,
    btnR,
    btnGr,
    tbl,
    tblH,
    tblC,
    selectedWarehouseProject,
    materials,
    materialsPage,
    loadMaterialsPage,
    openReceiveInvoice,
    user,
    materialTransfers,
    setMaterialTransfers,
    setNewTransfer,
    showTransferForm,
    setShowTransferForm,
    renderMaterialReconciliationPanel,
    deleteMaterial,
    newTransfer,
    warehouseMain,
    supplyRequests,
    _normalizeUnit,
    convertUnits,
    staff,
    setWarehouseMain,
    setMaterials,
    notify,
    newInvoice,
    setNewInvoice,
    suppliers,
    estimatesList,
    getProjectWorkPackageOptions,
    getProjectEstimateWorkOptions,
    invoices,
    saveInvoiceNew,
    uploadPhoto,
    fileSrc,
    setShowPhotoModal,
    setSverkaModal,
    warehouseInvoiceItems,
    isSupplyDeliveryInvoice,
    warehouseInvoiceEstimateControl,
    renderInvoiceControlActions,
    showPreview,
    buildInvoiceContent,
    setShowQRModal,
    VAT_OPTIONS,
    UNITS,
    MATERIAL_CATEGORIES,
    history,
    listSearch,
    setListSearch,
    matchSearch,
    deleteMainMaterial,
    warehouseMovements,
    newMovement,
    setNewMovement,
    applyWarehouseMovement,
    buildMovementDoc,
    toolsTab,
    setToolsTab,
    newTool,
    setNewTool,
    saveTool,
    deleteTool,
    tools,
    toolHistory,
    isProrab,
    setShowIssueToolModal,
    setShowReturnToolModal,
    TOOL_STATUSES,
    newInventory,
    setNewInventory,
    selectedInventory,
    setSelectedInventory,
    inventory,
    buildInventoryDoc,
    refreshData,
    isMobile,
    API,
    companyContext,
  } = props;
  const canReviewSupplyRequests = roleFlagsForUser(user).isSupplyRole;
  const useTwoStageMovements = process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_ENABLED === 'true'
    && process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED === 'true';

  if (user?.role === 'прораб' && inventoryReconciliationEnabled()) {
    return <InventoryWorkspace {...{ API, companyContext, user, C, showPreview }} onChanged={refreshData} />;
  }

  return (
    <div style={{width:'100%',maxWidth:'100%',minWidth:0,overflowX:'hidden'}}>
      <WarehouseTabsNav
        warehouseTab={warehouseTab}
        setWarehouseTab={setWarehouseTab}
        setShowForm={setShowForm}
        btnO={btnO}
        btnG={btnG}
        isMobile={isMobile}
      />

      {warehouseTab === 'control' && (
        <>
          <HumanApprovedActionReviewPanel
            API={API}
            C={C}
            card={card}
            companyMode={companyContext?.mode}
            isMobile={isMobile}
            projects={projects}
            selectedCompanyId={companyContext?.selectedCompanyId}
            user={user}
          />
          <WarehouseMaterialControlOverview
            C={C}
            badge={badge}
            btnB={btnB}
            btnG={btnG}
            buildMaterialRequirementContent={buildMaterialRequirementContent}
            card={card}
            exportToExcel={exportToExcel}
            isFinanceRole={isFinanceRole}
            isLeadership={isLeadership}
            canReviewSupplyRequests={canReviewSupplyRequests}
            isMobile={isMobile}
            materialControlSummaryForProject={materialControlSummaryForProject}
            materialReconciliationRows={materialReconciliationRows}
            parseSupplyItems={parseSupplyItems}
            projects={projects}
            setSelectedWarehouseProject={setSelectedWarehouseProject}
            setWarehouseTab={setWarehouseTab}
            showPreview={showPreview}
            supplyRequests={supplyRequests}
            visibleActiveProjects={visibleActiveProjects}
          />
        </>
      )}

      {warehouseTab === 'warehouses' && <CompanyWarehouses {...{ API, companyContext, user, C }} onChanged={refreshData} />}

      {warehouseTab === 'objects' && (
        <WarehouseObjectsPanel
          C={C}
          card={card}
          inp={inp}
          btnO={btnO}
          btnG={btnG}
          btnGr={btnGr}
          btnR={btnR}
          tbl={tbl}
          tblH={tblH}
          tblC={tblC}
          badge={badge}
          selectedWarehouseProject={selectedWarehouseProject}
          setSelectedWarehouseProject={setSelectedWarehouseProject}
          visibleActiveProjects={visibleActiveProjects}
          projects={projects}
          materials={materials}
          materialsPage={materialsPage}
          loadMaterialsPage={loadMaterialsPage}
          openReceiveInvoice={openReceiveInvoice}
          isLeadership={isLeadership}
          user={user}
          setMaterialTransfers={setMaterialTransfers}
          setNewTransfer={setNewTransfer}
          setShowTransferForm={setShowTransferForm}
          exportToExcel={exportToExcel}
          renderMaterialReconciliationPanel={renderMaterialReconciliationPanel}
          deleteMaterial={deleteMaterial}
          showTransferForm={showTransferForm}
          newTransfer={newTransfer}
          warehouseMain={warehouseMain}
          supplyRequests={supplyRequests}
          _normalizeUnit={_normalizeUnit}
          convertUnits={convertUnits}
          staff={staff}
          getProjectWorkPackageOptions={getProjectWorkPackageOptions}
          setWarehouseMain={setWarehouseMain}
          setMaterials={setMaterials}
          notify={notify}
          isMobile={isMobile}
        />
      )}

      {warehouseTab === 'main' && (
        <WarehouseMainStockPanel
          user={user}
          warehouseMain={warehouseMain}
          listSearch={listSearch}
          setListSearch={setListSearch}
          matchSearch={matchSearch}
          openReceiveInvoice={openReceiveInvoice}
          exportToExcel={exportToExcel}
          deleteMainMaterial={deleteMainMaterial}
          C={C}
          inp={inp}
          btnO={btnO}
          btnG={btnG}
          btnR={btnR}
          tbl={tbl}
          tblH={tblH}
          tblC={tblC}
          badge={badge}
          isMobile={isMobile}
        />
      )}

      {warehouseTab === 'invoices' && (
        <WarehouseInvoicesPanel
          user={user}
          showForm={showForm}
          setShowForm={setShowForm}
          newInvoice={newInvoice}
          setNewInvoice={setNewInvoice}
          suppliers={suppliers}
          projects={projects}
          estimatesList={estimatesList}
          getProjectWorkPackageOptions={getProjectWorkPackageOptions}
          getProjectEstimateWorkOptions={getProjectEstimateWorkOptions}
          invoices={invoices}
          saveInvoiceNew={saveInvoiceNew}
          uploadPhoto={uploadPhoto}
          fileSrc={fileSrc}
          setShowPhotoModal={setShowPhotoModal}
          setSverkaModal={setSverkaModal}
          warehouseInvoiceItems={warehouseInvoiceItems}
          isSupplyDeliveryInvoice={isSupplyDeliveryInvoice}
          warehouseInvoiceEstimateControl={warehouseInvoiceEstimateControl}
          renderInvoiceControlActions={renderInvoiceControlActions}
          showPreview={showPreview}
          buildInvoiceContent={buildInvoiceContent}
          setShowQRModal={setShowQRModal}
          materials={materials}
          materialControlSummaryForProject={materialControlSummaryForProject}
          setWarehouseTab={setWarehouseTab}
          setSelectedWarehouseProject={setSelectedWarehouseProject}
          setNewTransfer={setNewTransfer}
          setShowTransferForm={setShowTransferForm}
          materialTransfers={materialTransfers}
          C={C}
          card={card}
          inp={inp}
          btnO={btnO}
          btnG={btnG}
          btnB={btnB}
          btnR={btnR}
          tbl={tbl}
          tblH={tblH}
          tblC={tblC}
          VAT_OPTIONS={VAT_OPTIONS}
          UNITS={UNITS}
          MATERIAL_CATEGORIES={MATERIAL_CATEGORIES}
          isMobile={isMobile}
        />
      )}

      {warehouseTab === 'history' && (
        <WarehouseHistoryPanel
          history={history}
          listSearch={listSearch}
          setListSearch={setListSearch}
          matchSearch={matchSearch}
          exportToExcel={exportToExcel}
          C={C}
          btnG={btnG}
          tbl={tbl}
          tblH={tblH}
          tblC={tblC}
          badge={badge}
          isMobile={isMobile}
        />
      )}

      {warehouseTab === 'move' && <WarehouseDistributionPanel companyContext={companyContext} projects={projects} C={C} refreshData={refreshData} />}
      {warehouseTab === 'tools' && toolCustodyEnabled() && <ToolsWorkspace {...{ tools, toolHistory, API, companyContext, user, C, refreshData }} />}
      {warehouseTab === 'inventory' && inventoryReconciliationEnabled() && <InventoryWorkspace {...{ API, companyContext, user, C, showPreview }} onChanged={refreshData} />}

      {((warehouseTab === 'tools' && !toolCustodyEnabled()) || (warehouseTab === 'inventory' && !inventoryReconciliationEnabled()) || (warehouseTab === 'move' && !useTwoStageMovements)) && (
        <WarehouseOperationsPanel
          isMobile={isMobile}
          warehouseTab={warehouseTab}
          C={C}
          card={card}
          inp={inp}
          btnO={btnO}
          btnG={btnG}
          btnB={btnB}
          btnGr={btnGr}
          btnR={btnR}
          badge={badge}
          tbl={tbl}
          tblH={tblH}
          tblC={tblC}
          showForm={showForm}
          setShowForm={setShowForm}
          projects={projects}
          visibleActiveProjects={visibleActiveProjects}
          warehouseMain={warehouseMain}
          materials={materials}
          warehouseInvoices={invoices}
          warehouseMovements={warehouseMovements}
          newMovement={newMovement}
          setNewMovement={setNewMovement}
          applyWarehouseMovement={applyWarehouseMovement}
          buildMovementDoc={buildMovementDoc}
          showPreview={showPreview}
          toolsTab={toolsTab}
          setToolsTab={setToolsTab}
          editingItem={editingItem}
          setEditingItem={setEditingItem}
          newTool={newTool}
          setNewTool={setNewTool}
          saveTool={saveTool}
          deleteTool={deleteTool}
          tools={tools}
          toolHistory={toolHistory}
          isProrab={isProrab}
          setShowIssueToolModal={setShowIssueToolModal}
          setShowReturnToolModal={setShowReturnToolModal}
          TOOL_STATUSES={TOOL_STATUSES}
          newInventory={newInventory}
          setNewInventory={setNewInventory}
          selectedInventory={selectedInventory}
          setSelectedInventory={setSelectedInventory}
          inventory={inventory}
          buildInventoryDoc={buildInventoryDoc}
          refreshData={refreshData}
          user={user}
        />
      )}
    </div>
  );
}

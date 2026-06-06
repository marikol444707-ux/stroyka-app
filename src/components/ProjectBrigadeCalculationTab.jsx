import React from 'react';
import { Plus } from 'lucide-react';
import ProjectBrigadeBudgetSummary from './ProjectBrigadeBudgetSummary';
import ProjectBrigadeCreateForm from './ProjectBrigadeCreateForm';
import ProjectBrigadesList from './ProjectBrigadesList';
import ProjectBrigadeSelectedHeader from './ProjectBrigadeSelectedHeader';
import ProjectBrigadeCalculationSummary from './ProjectBrigadeCalculationSummary';
import ProjectBrigadeWorkEntryPanel from './ProjectBrigadeWorkEntryPanel';
import ProjectBrigadeBulkPricePanel from './ProjectBrigadeBulkPricePanel';
import ProjectBrigadeCalculationTable from './ProjectBrigadeCalculationTable';
import ProjectBrigadeActPaymentPanel from './ProjectBrigadeActPaymentPanel';

export default function ProjectBrigadeCalculationTab({
  project,
  brigadeContracts,
  smetaTotal,
  showBrigadeForm,
  setShowBrigadeForm,
  newBrigadeContract,
  setNewBrigadeContract,
  staff,
  pricelists,
  setBrigadeContracts,
  setSelectedBrigadeContract,
  setBrigadeContractItems,
  setBrigadePayments,
  selectedBrigadeContract,
  brigadeContractItems,
  brigadePayments,
  estimatesList,
  newBrigadeItem,
  setNewBrigadeItem,
  UNITS,
  showLeadership,
  brigadeCoef,
  setBrigadeCoef,
  showFinance,
  normalizeMeasure,
  toNum,
  fmtMeasure,
  userName,
  setNewBrigadePayment,
  setShowBrigadePayModal,
  deleteBrigadePayment,
  showPreview,
  uploadPhoto,
  fileSrc,
  openBrigadeContract,
  C,
  card,
  inp,
  btnO,
  btnG,
  btnB,
  btnR,
  tbl,
  tblH,
  tblC,
}) {
  return (
    <div>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px'}}>
        <b style={{color: C.text, fontSize: '15px', fontWeight: '700'}}>Расчёт с бригадой</b>
        <button onClick={() => setShowBrigadeForm(!showBrigadeForm)} style={btnO}>
          <Plus size={14}/>Новая бригада
        </button>
      </div>

      <ProjectBrigadeBudgetSummary
        projectName={project.name}
        brigadeContracts={brigadeContracts}
        smetaTotal={smetaTotal}
        C={C}
        card={card}
      />

      {showBrigadeForm && (
        <ProjectBrigadeCreateForm
          project={project}
          newBrigadeContract={newBrigadeContract}
          setNewBrigadeContract={setNewBrigadeContract}
          staff={staff}
          pricelists={pricelists}
          setBrigadeContracts={setBrigadeContracts}
          setSelectedBrigadeContract={setSelectedBrigadeContract}
          setBrigadeContractItems={setBrigadeContractItems}
          setBrigadePayments={setBrigadePayments}
          setShowBrigadeForm={setShowBrigadeForm}
          card={card}
          inp={inp}
          btnO={btnO}
          btnG={btnG}
        />
      )}

      {selectedBrigadeContract ? (
        <div>
          <ProjectBrigadeSelectedHeader
            projectName={project.name}
            selectedBrigadeContract={selectedBrigadeContract}
            setSelectedBrigadeContract={setSelectedBrigadeContract}
            brigadeContractItems={brigadeContractItems}
            setBrigadeContractItems={setBrigadeContractItems}
            setBrigadeContracts={setBrigadeContracts}
            setBrigadePayments={setBrigadePayments}
            showPreview={showPreview}
            C={C}
            btnG={btnG}
            btnO={btnO}
            btnB={btnB}
          />

          <ProjectBrigadeCalculationSummary
            brigadeContractItems={brigadeContractItems}
            showFinance={showFinance}
            C={C}
            card={card}
          />

          <ProjectBrigadeWorkEntryPanel
            project={project}
            selectedBrigadeContract={selectedBrigadeContract}
            estimatesList={estimatesList}
            newBrigadeItem={newBrigadeItem}
            setNewBrigadeItem={setNewBrigadeItem}
            setBrigadeContractItems={setBrigadeContractItems}
            UNITS={UNITS}
            C={C}
            card={card}
            inp={inp}
            btnG={btnG}
            btnO={btnO}
          />

          <ProjectBrigadeBulkPricePanel
            show={showLeadership}
            brigadeCoef={brigadeCoef}
            setBrigadeCoef={setBrigadeCoef}
            brigadeContractItems={brigadeContractItems}
            setBrigadeContractItems={setBrigadeContractItems}
            C={C}
            card={card}
            inp={inp}
            btnO={btnO}
            btnG={btnG}
          />

          <ProjectBrigadeCalculationTable
            brigadeContractItems={brigadeContractItems}
            setBrigadeContractItems={setBrigadeContractItems}
            showFinance={showFinance}
            normalizeMeasure={normalizeMeasure}
            toNum={toNum}
            fmtMeasure={fmtMeasure}
            C={C}
            tbl={tbl}
            tblH={tblH}
            tblC={tblC}
            inp={inp}
            btnR={btnR}
          />

          <ProjectBrigadeActPaymentPanel
            project={project}
            selectedBrigadeContract={selectedBrigadeContract}
            brigadeContractItems={brigadeContractItems}
            brigadePayments={brigadePayments}
            showFinance={showFinance}
            userName={userName}
            setNewBrigadePayment={setNewBrigadePayment}
            setShowBrigadePayModal={setShowBrigadePayModal}
            setSelectedBrigadeContract={setSelectedBrigadeContract}
            setBrigadeContracts={setBrigadeContracts}
            deleteBrigadePayment={deleteBrigadePayment}
            showPreview={showPreview}
            uploadPhoto={uploadPhoto}
            fileSrc={fileSrc}
            C={C}
            card={card}
            btnO={btnO}
            btnG={btnG}
            btnB={btnB}
            btnR={btnR}
          />
        </div>
      ) : (
        <ProjectBrigadesList
          projectName={project.name}
          brigadeContracts={brigadeContracts}
          openBrigadeContract={openBrigadeContract}
          setBrigadeContracts={setBrigadeContracts}
          C={C}
          card={card}
          btnR={btnR}
        />
      )}
    </div>
  );
}

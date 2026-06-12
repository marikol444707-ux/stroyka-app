import React from 'react';
import EstimateImportSettings from './EstimateImportSettings';
import EstimateImportSupportedFormat from './EstimateImportSupportedFormat';
import EstimateImportUploadButton from './EstimateImportUploadButton';

export default function EstimateImportView({
  C,
  card,
  inp,
  projects,
  newEstimate,
  setNewEstimate,
  nextEstimateVersionFor,
  estimatePackages,
  onFileChange,
}) {
  return (
    <div>
      <h3 style={{ color: C.text, marginBottom: '15px', fontSize: '15px', fontWeight: '700' }}>
        Импорт из Гранд Смета (Excel)
      </h3>
      <div style={{ ...card, padding: '20px', marginBottom: '20px' }}>
        <p style={{ color: C.textSec, fontSize: '13px', marginBottom: '15px' }}>
          Загрузите Excel файл из Гранд Сметы — система автоматически распознает разделы и позиции.
        </p>
        <EstimateImportSettings
          inp={inp}
          projects={projects}
          newEstimate={newEstimate}
          setNewEstimate={setNewEstimate}
          nextEstimateVersionFor={nextEstimateVersionFor}
          estimatePackages={estimatePackages}
        />
        <EstimateImportUploadButton C={C} onFileChange={onFileChange} />
        <EstimateImportSupportedFormat C={C} />
      </div>
    </div>
  );
}

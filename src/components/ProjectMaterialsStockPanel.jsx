import React from 'react';

export default function ProjectMaterialsStockPanel({
  projectName,
  materials = [],
  warehouseMain = [],
  C,
  card,
}) {
  const objectMaterials = materials.filter(m => m.project === projectName && Number(m.quantity || 0) > 0);
  const mainStockMap = {};

  warehouseMain.forEach(m => {
    mainStockMap[m.name] = Number(m.quantity || 0);
  });

  if (objectMaterials.length === 0) {
    return (
      <div style={{
        ...card,
        padding: '18px',
        marginBottom: '14px',
        backgroundColor: C.bg,
        textAlign: 'center',
        color: C.textMuted,
        fontSize: '13px'
      }}>
        📦 Материалов на объекте нет. Нажмите «Принять материал» чтобы оприходовать накладную.
      </div>
    );
  }

  return (
    <div style={{
      ...card,
      padding: '14px',
      marginBottom: '14px',
      backgroundColor: C.bg
    }}>
      <b style={{color: C.text, fontSize: '13px', display: 'block', marginBottom: '10px'}}>
        📦 Остатки на объекте ({objectMaterials.length} поз.)
      </b>
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(220px,1fr))', gap: '8px'}}>
        {objectMaterials.map(m => {
          const onMain = mainStockMap[m.name] || 0;
          const low = m.minQuantity && Number(m.quantity) < Number(m.minQuantity);

          return (
            <div key={m.id} style={{
              padding: '10px',
              borderRadius: '8px',
              backgroundColor: C.bgWhite,
              border: '1.5px solid ' + (low ? C.dangerBorder : C.border)
            }}>
              <b style={{color: C.text, fontSize: '12px', display: 'block'}}>{m.name}</b>
              <div style={{display: 'flex', justifyContent: 'space-between', marginTop: '4px'}}>
                <span style={{
                  fontSize: '11px',
                  color: low ? C.danger : C.success,
                  fontWeight: '600'
                }}>
                  {'На объекте: ' + Number(m.quantity).toLocaleString('ru-RU') + ' ' + (m.unit || 'шт')}
                </span>
                {onMain > 0 && (
                  <span style={{fontSize: '11px', color: C.info}} title="Есть на основном складе">
                    {'+ склад: ' + onMain.toLocaleString('ru-RU')}
                  </span>
                )}
              </div>
              {low && (
                <span style={{fontSize: '10px', color: C.danger, fontWeight: '600', marginTop: '3px', display: 'block'}}>
                  ⚠️ Ниже минимума {m.minQuantity}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

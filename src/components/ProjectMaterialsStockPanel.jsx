import React from 'react';

export default function ProjectMaterialsStockPanel({
  projectName,
  materials = [],
  warehouseMain = [],
  C,
  card,
}) {
  const [search, setSearch] = React.useState('');
  const [workPackage, setWorkPackage] = React.useState('');
  const [positiveOnly, setPositiveOnly] = React.useState(true);

  const objectMaterials = React.useMemo(
    () => materials.filter(m => m.project === projectName),
    [materials, projectName]
  );

  const workPackageOptions = React.useMemo(
    () => [...new Set(objectMaterials.map(m => String(m.workPackage || m.work_package || '').trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ru')),
    [objectMaterials]
  );

  const filteredMaterials = React.useMemo(() => {
    const q = search.trim().toLowerCase();

    return objectMaterials.filter(m => {
      const pkg = String(m.workPackage || m.work_package || '').trim();
      const qty = Number(m.quantity || 0);
      const haystack = [
        m.name,
        m.category,
        pkg
      ].join(' ').toLowerCase();

      if (positiveOnly && qty <= 0) return false;
      if (workPackage && pkg !== workPackage) return false;
      if (q && !haystack.includes(q)) return false;

      return true;
    });
  }, [objectMaterials, positiveOnly, search, workPackage]);

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
        📦 Материалов на объекте нет. Создайте заявку снабжения или переместите материал с основного склада на объект.
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
      <div style={{display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '10px'}}>
        <b style={{color: C.text, fontSize: '13px'}}>
          📦 Остатки на объекте ({filteredMaterials.length} из {objectMaterials.length} поз.)
        </b>
        <button
          type="button"
          onClick={() => setPositiveOnly(v => !v)}
          style={{
            padding: '6px 10px',
            borderRadius: '8px',
            border: '1.5px solid ' + (positiveOnly ? C.accentBorder : C.border),
            backgroundColor: positiveOnly ? C.accentLight : C.bgWhite,
            color: positiveOnly ? C.accent : C.textSec,
            cursor: 'pointer',
            fontSize: '11px',
            fontWeight: '600'
          }}
          title="Переключить отображение нулевых и отрицательных остатков"
        >
          {positiveOnly ? 'Только положительные' : 'Все остатки'}
        </button>
      </div>

      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: '8px', marginBottom: '10px'}}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Поиск: название, категория, пакет"
          style={{
            padding: '8px 10px',
            borderRadius: '8px',
            border: '1.5px solid ' + C.border,
            backgroundColor: C.bgWhite,
            color: C.text,
            fontSize: '12px',
            minWidth: 0
          }}
        />
        <select
          value={workPackage}
          onChange={e => setWorkPackage(e.target.value)}
          style={{
            padding: '8px 10px',
            borderRadius: '8px',
            border: '1.5px solid ' + C.border,
            backgroundColor: C.bgWhite,
            color: workPackage ? C.text : C.textSec,
            fontSize: '12px',
            minWidth: 0
          }}
        >
          <option value="">Все пакеты работ</option>
          {workPackageOptions.map(pkg => <option key={pkg} value={pkg}>{pkg}</option>)}
        </select>
      </div>

      {filteredMaterials.length === 0 ? (
        <div style={{
          padding: '18px',
          borderRadius: '8px',
          backgroundColor: C.bgWhite,
          border: '1.5px dashed ' + C.border,
          color: C.textMuted,
          fontSize: '12px',
          textAlign: 'center'
        }}>
          Ничего не найдено. Измените поиск, пакет работ или режим отображения остатков.
        </div>
      ) : (
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(220px,1fr))', gap: '8px'}}>
          {filteredMaterials.map(m => {
            const onMain = mainStockMap[m.name] || 0;
            const qty = Number(m.quantity || 0);
            const low = m.minQuantity && qty < Number(m.minQuantity);
            const empty = qty <= 0;

            return (
              <div key={m.id} style={{
                padding: '10px',
                borderRadius: '8px',
                backgroundColor: C.bgWhite,
                border: '1.5px solid ' + (low ? C.dangerBorder : C.border),
                opacity: empty ? 0.72 : 1
              }}>
                <b style={{color: C.text, fontSize: '12px', display: 'block'}}>{m.name}</b>
                {m.category && (
                  <span style={{fontSize: '10px', color: C.textMuted, display: 'block', marginTop: '2px'}}>
                    {m.category}
                  </span>
                )}
                {(m.workPackage || m.work_package) && (
                  <span style={{fontSize: '10px', color: C.textSec, display: 'block', marginTop: '2px'}}>
                    📁 {m.workPackage || m.work_package}
                  </span>
                )}
                <div style={{display: 'flex', justifyContent: 'space-between', marginTop: '4px'}}>
                  <span style={{
                    fontSize: '11px',
                    color: empty ? C.textMuted : low ? C.danger : C.success,
                    fontWeight: '600'
                  }}>
                    {'На объекте: ' + qty.toLocaleString('ru-RU') + ' ' + (m.unit || 'шт')}
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
      )}
    </div>
  );
}

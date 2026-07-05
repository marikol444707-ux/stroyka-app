import React from 'react';
import {
  ArrowLeft,
  Check,
  ChevronRight,
  Download,
  Search,
  Trash2,
  Truck,
  X,
} from 'lucide-react';
import { API } from '../api';
import { createMaterialTransferForm } from '../features/warehouse/warehouseInitialForms';

export default function WarehouseObjectsPanel({
  C,
  card,
  inp,
  btnO,
  btnB,
  btnG,
  btnGr,
  btnR,
  tbl,
  tblH,
  tblC,
  badge,
  selectedWarehouseProject,
  setSelectedWarehouseProject,
  visibleActiveProjects,
  projects,
  materials,
  materialsPage = {},
  loadMaterialsPage,
  isLeadership,
  user,
  setMaterialTransfers,
  setNewTransfer,
  setShowTransferForm,
  exportToExcel,
  renderMaterialReconciliationPanel,
  deleteMaterial,
  showTransferForm,
  newTransfer,
  supplyRequests,
  _normalizeUnit,
  convertUnits,
  staff,
  getProjectWorkPackageOptions,
  setMaterials,
  notify,
  isMobile = false,
}) {
  const [visibleObjectRows, setVisibleObjectRows] = React.useState(60);
  const [visibleTransferRows, setVisibleTransferRows] = React.useState(40);
  const [objectMaterialSearch, setObjectMaterialSearch] = React.useState('');
  const [manualTransferPackageEdit, setManualTransferPackageEdit] = React.useState(false);
  const useCompactRows = isMobile || (typeof window !== 'undefined' && window.innerWidth <= 1100);
  const currentUser = user || {};
  const isLeadershipUser = typeof isLeadership === 'function' ? isLeadership() : Boolean(isLeadership);
  const canDeleteProjectMaterial = currentUser.role === 'директор';
  const materialsByProject = React.useMemo(() => {
    const grouped = new Map();
    (materials || []).forEach(material => {
      const projectName = material.project || '';
      if (!grouped.has(projectName)) grouped.set(projectName, []);
      grouped.get(projectName).push(material);
    });
    return grouped;
  }, [materials]);
  const projectMaterials = React.useCallback(
    projectName => materialsByProject.get(projectName) || [],
    [materialsByProject],
  );
  const visibleWarehouseProjects = React.useMemo(
    () => visibleActiveProjects(projects),
    [visibleActiveProjects, projects],
  );
  const projectStockSummaries = React.useMemo(() => {
    const summaries = new Map();
    visibleWarehouseProjects.forEach(project => {
      const projectRows = projectMaterials(project.name);
      const total = projectRows.reduce((sum, material) => (
        sum + Number(material.price || 0) * Number(material.quantity || 0)
      ), 0);
      summaries.set(project.name, { count: projectRows.length, total });
    });
    return summaries;
  }, [projectMaterials, visibleWarehouseProjects]);
  const transferSourceMaterials = React.useMemo(
    () => projectMaterials(selectedWarehouseProject),
    [projectMaterials, selectedWarehouseProject],
  );
  const toNum = value => {
    const parsed = Number(String(value ?? '').replace(',', '.').replace(/\s+/g, ''));
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const transferItemKey = item => [
    item.materialName || item.name || '',
    item.workPackage || item.work_package || '',
    item.unit || '',
  ].join('|||');
  const normalizeTransferItems = React.useCallback((items = []) => (
    (Array.isArray(items) ? items : [])
      .map(item => ({
        materialName: item.materialName || item.name || '',
        quantity: item.quantity ?? '',
        unit: item.unit || 'шт',
        workPackage: item.workPackage || item.work_package || '',
        invoiceId: item.invoiceId || item.invoice_id || null,
        invoiceLineKey: item.invoiceLineKey || item.invoice_line_key || '',
        invoiceLineIndex: item.invoiceLineIndex ?? item.invoice_line_index ?? null,
        invoiceNumber: item.invoiceNumber || item.invoice_number || '',
      }))
      .filter(item => item.materialName)
  ), []);
  const transferItemsFromState = React.useCallback((transfer = {}) => {
    const explicitItems = Array.isArray(transfer.items) ? transfer.items : [];
    const cleaned = explicitItems
      .map(item => ({
        materialName: item.materialName || item.name || '',
        quantity: item.quantity ?? '',
        unit: item.unit || 'шт',
        workPackage: item.workPackage || item.work_package || '',
        invoiceId: item.invoiceId || item.invoice_id || null,
        invoiceLineKey: item.invoiceLineKey || item.invoice_line_key || '',
        invoiceLineIndex: item.invoiceLineIndex ?? item.invoice_line_index ?? null,
        invoiceNumber: item.invoiceNumber || item.invoice_number || '',
      }))
      .filter(item => item.materialName);
    if (cleaned.length > 0) return cleaned;
    if (!transfer.materialName) return [];
    return [{
      materialName: transfer.materialName,
      quantity: transfer.quantity,
      unit: transfer.unit || 'шт',
      workPackage: transfer.workPackage || '',
      invoiceId: transfer.invoiceId || transfer.invoice_id || null,
      invoiceLineKey: transfer.invoiceLineKey || transfer.invoice_line_key || '',
      invoiceLineIndex: transfer.invoiceLineIndex ?? transfer.invoice_line_index ?? null,
      invoiceNumber: transfer.invoiceNumber || transfer.invoice_number || '',
    }];
  }, []);
  const selectedTransferItems = React.useMemo(() => transferItemsFromState(newTransfer), [newTransfer, transferItemsFromState]);
  const updateTransferItems = React.useCallback((itemsOrUpdater) => {
    setNewTransfer(prev => {
      const currentItems = transferItemsFromState(prev);
      const nextItemsRaw = typeof itemsOrUpdater === 'function' ? itemsOrUpdater(currentItems) : itemsOrUpdater;
      const normalizedItems = normalizeTransferItems(nextItemsRaw);
      const first = normalizedItems[0] || {materialName: '', quantity: '', unit: 'шт', workPackage: ''};
      return {
        ...prev,
        items: normalizedItems,
        materialName: first.materialName,
        quantity: first.quantity,
        unit: first.unit || 'шт',
        workPackage: normalizedItems.length === 1 ? (first.workPackage || '') : '',
      };
    });
  }, [normalizeTransferItems, setNewTransfer, transferItemsFromState]);
  const transferPackageOptions = selectedWarehouseProject
    ? (getProjectWorkPackageOptions
      ? getProjectWorkPackageOptions(selectedWarehouseProject)
      : [...new Set(transferSourceMaterials.map(material => material.workPackage || material.work_package || '').filter(Boolean))])
    : [];
  const stockForTransferItem = item => transferSourceMaterials.find(material =>
    material.name === item.materialName &&
    (material.workPackage || material.work_package || '') === (item.workPackage || '')
  );
  const transferNeedsPackage = ['мастер', 'бригадир', 'субподрядчик'].includes((newTransfer.toPersonRole || '').toLowerCase());
  const transferMissingPackage = transferNeedsPackage && selectedTransferItems.some(item => !(item.workPackage || '').trim());
  const transferOverStock = selectedTransferItems.some(item => {
    const stock = stockForTransferItem(item);
    return !!item.materialName && toNum(item.quantity) > toNum(stock?.quantity);
  });
  const canSaveObjectTransfer = selectedTransferItems.length > 0 &&
    selectedTransferItems.every(item => toNum(item.quantity) > 0) &&
    !!newTransfer.toPerson &&
    !transferMissingPackage &&
    !transferOverStock;
  React.useEffect(() => {
    setVisibleObjectRows(useCompactRows ? 60 : 180);
  }, [useCompactRows, selectedWarehouseProject]);
  React.useEffect(() => {
    setObjectMaterialSearch('');
  }, [selectedWarehouseProject]);
  React.useEffect(() => {
    if (!selectedWarehouseProject || typeof loadMaterialsPage !== 'function') return undefined;
    const search = objectMaterialSearch.trim();
    const timer = setTimeout(() => {
      loadMaterialsPage({projectName: selectedWarehouseProject, search, offset: 0});
      setVisibleObjectRows(useCompactRows ? 60 : 180);
    }, search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [selectedWarehouseProject, objectMaterialSearch, loadMaterialsPage, useCompactRows]);
  React.useEffect(() => {
    setVisibleTransferRows(useCompactRows ? 40 : 100);
  }, [useCompactRows, selectedWarehouseProject, showTransferForm]);
  React.useEffect(() => {
    if (!showTransferForm) setManualTransferPackageEdit(false);
  }, [showTransferForm]);
  const selectedProjectMaterials = projectMaterials(selectedWarehouseProject);
  const normalizedObjectSearch = objectMaterialSearch.trim().toLowerCase();
  const filteredProjectMaterials = normalizedObjectSearch
    ? selectedProjectMaterials.filter(material => [
      material.name,
      material.category,
      material.unit,
      material.workPackage,
      material.work_package,
    ].some(value => String(value || '').toLowerCase().includes(normalizedObjectSearch)))
    : selectedProjectMaterials;
  const displayedProjectMaterials = filteredProjectMaterials.slice(0, visibleObjectRows);
  const hiddenProjectMaterials = Math.max(0, filteredProjectMaterials.length - displayedProjectMaterials.length);
  const objectRowsStep = useCompactRows ? 60 : 180;
  const transferRowsStep = useCompactRows ? 40 : 100;
  const displayedTransferSourceMaterials = transferSourceMaterials.slice(0, visibleTransferRows);
  const hiddenTransferMaterials = Math.max(0, transferSourceMaterials.length - displayedTransferSourceMaterials.length);
  const materialsQueryMatches = materialsPage.projectName === (selectedWarehouseProject || '') && (materialsPage.search || '') === objectMaterialSearch.trim();
  const canLoadMoreFromServer = !!selectedWarehouseProject && typeof loadMaterialsPage === 'function' && materialsQueryMatches && materialsPage.hasMore;
  const loadNextProjectMaterials = () => {
    if (!canLoadMoreFromServer) return;
    loadMaterialsPage({
      projectName: selectedWarehouseProject,
      search: objectMaterialSearch.trim(),
      offset: filteredProjectMaterials.length,
    });
    setVisibleObjectRows(limit => limit + objectRowsStep);
  };

  return (
    <div>
      {!selectedWarehouseProject ? (
        <div>
          <h3 style={{ color: C.text, marginBottom: '15px', fontSize: '15px', fontWeight: '700' }}>Материалы по объектам</h3>
          {visibleWarehouseProjects.map(project => {
            const summary = projectStockSummaries.get(project.name) || { count: 0, total: 0 };
            return (
              <div
                key={project.id}
                style={{ ...card, padding: '16px', marginBottom: '10px', cursor: 'pointer', display: 'flex', flexDirection: useCompactRows ? 'column' : 'row', justifyContent: 'space-between', alignItems: useCompactRows ? 'stretch' : 'center', gap: '10px', minWidth: 0, overflow: 'hidden' }}
                onClick={() => setSelectedWarehouseProject(project.name)}
              >
                <div style={{ minWidth: 0 }}>
                  <b style={{ display: 'block', color: C.text, fontSize: '14px', lineHeight: 1.25, overflowWrap: 'anywhere' }}>{project.name}</b>
                  <p style={{ color: C.textSec, margin: '3px 0', fontSize: '12px', overflowWrap: 'anywhere' }}>{summary.count + ' загруж. позиций · ' + summary.total.toLocaleString() + ' ₽'}</p>
                </div>
                <ChevronRight size={18} color={C.textMuted} style={{ alignSelf: useCompactRows ? 'flex-end' : 'center', flex: '0 0 auto' }} />
              </div>
            );
          })}
        </div>
      ) : (
        <div>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '15px', flexWrap: 'wrap', minWidth: 0 }}>
            <button onClick={() => setSelectedWarehouseProject(null)} style={btnG}>
              <ArrowLeft size={14} />
              Назад
            </button>
            <h3 style={{ color: C.text, margin: 0, fontSize: '15px', fontWeight: '700', minWidth: 0, overflowWrap: 'anywhere', flex: '1 1 220px' }}>{selectedWarehouseProject}</h3>
          </div>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '15px', flexWrap: 'wrap' }}>
            {(isLeadershipUser || currentUser.role === 'прораб' || currentUser.role === 'кладовщик') && (
              <button
                onClick={async () => {
                  const response = await fetch(API + '/material-transfers?project_name=' + encodeURIComponent(selectedWarehouseProject));
                  const data = await response.json();
                  setMaterialTransfers(Array.isArray(data) ? data : []);
                  setNewTransfer(createMaterialTransferForm({
                    items: [],
                    fromLocation: selectedWarehouseProject,
                  }));
                  setShowTransferForm(true);
                }}
                style={btnGr}
              >
                <Truck size={14} />
                Передать мастеру
              </button>
            )}
            <button
              onClick={() => exportToExcel(
                selectedProjectMaterials.map(material => ({
                  Наименование: material.name,
                  Пакет: material.workPackage || material.work_package || '',
                  Единица: material.unit,
                  Количество: material.quantity,
                  Цена: material.price,
                  Сумма: Number(material.quantity || 0) * Number(material.price || 0),
                  Проект: material.project,
                })),
                'Склад_' + selectedWarehouseProject,
              )}
              style={btnG}
            >
              <Download size={14} />
              Excel
            </button>
          </div>
          <div style={{ position: 'relative', marginBottom: '12px' }}>
            <Search size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: C.textMuted }} />
            <input
              value={objectMaterialSearch}
              onChange={event => setObjectMaterialSearch(event.target.value)}
              placeholder="Поиск по складу объекта: материал, пакет, категория"
              style={{ ...inp, marginBottom: 0, paddingLeft: 34, width: '100%', boxSizing: 'border-box' }}
            />
            {(materialsPage.loading || materialsPage.error) && materialsQueryMatches && (
              <div style={{ color: materialsPage.error ? C.danger : C.textMuted, fontSize: '11px', marginTop: '5px' }}>
                {materialsPage.error || 'Ищу на сервере...'}
              </div>
            )}
          </div>
          {user?.role && !canDeleteProjectMaterial && (
            <div style={{margin:'-4px 0 12px',color:C.textMuted,fontSize:'11px'}}>
              Удаление остатков объекта доступно только директору. Для корректировки используйте накладную, перемещение, выдачу или списание.
            </div>
          )}
          {renderMaterialReconciliationPanel(selectedWarehouseProject, { limit: 25, title: '📊 Контроль материалов объекта' })}
          {useCompactRows ? (
            <div style={{ display: 'grid', gap: '10px', width: '100%', maxWidth: 'min(720px,100%)', margin: '0 auto' }}>
              {displayedProjectMaterials.map(material => {
                const workPackage = material.workPackage || material.work_package || '';
                const quantity = Number(material.quantity || 0);
                const price = Number(material.price || 0);
                const total = quantity * price;
                const isLow = material.minQuantity && quantity < Number(material.minQuantity || 0);
                return (
                  <div
                    key={material.id}
                    style={{
                      backgroundColor: isLow ? C.dangerLight : C.bgWhite,
                      border: '1.5px solid ' + (isLow ? C.dangerBorder : C.border),
                      borderRadius: '12px',
                      padding: '12px',
                      display: 'grid',
                      gap: '10px',
                      minWidth: 0,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'flex-start' }}>
                      <div style={{ minWidth: 0 }}>
                        <b style={{ display: 'block', color: C.text, fontSize: '14px', lineHeight: 1.25, overflowWrap: 'anywhere' }}>{material.name}</b>
                        {workPackage && (
                          <div style={{ fontSize: '11px', color: C.textSec, marginTop: '4px', overflowWrap: 'anywhere' }}>
                            📁 {workPackage}
                          </div>
                        )}
                        <span style={{ display: 'block', color: C.textSec, fontSize: '12px', marginTop: '3px' }}>{material.category || 'Без категории'}</span>
                      </div>
                      {canDeleteProjectMaterial && (
                        <button onClick={() => deleteMaterial(material.id)} style={{ ...btnR, flex: '0 0 auto', padding: '8px 10px' }}>
                          <Trash2 size={13} />
                        </button>
                      )}
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(130px,1fr))', gap: '8px' }}>
                      <div>
                        <div style={{ fontSize: '10px', color: C.textSec, textTransform: 'uppercase', letterSpacing: '.03em' }}>Кол-во</div>
                        <b style={{ color: C.text, fontSize: '13px', overflowWrap: 'anywhere' }}>{material.quantity} {material.unit}</b>
                      </div>
                      <div>
                        <div style={{ fontSize: '10px', color: C.textSec, textTransform: 'uppercase', letterSpacing: '.03em' }}>Цена</div>
                        <b style={{ color: C.text, fontSize: '13px', overflowWrap: 'anywhere' }}>{price.toLocaleString()} ₽</b>
                      </div>
                      <div>
                        <div style={{ fontSize: '10px', color: C.textSec, textTransform: 'uppercase', letterSpacing: '.03em' }}>Сумма</div>
                        <b style={{ color: C.success, fontSize: '13px', overflowWrap: 'anywhere' }}>{total.toLocaleString()} ₽</b>
                      </div>
                    </div>
                    {isLow && <span style={{ ...badge(C.danger, C.dangerLight, C.dangerBorder), justifySelf: 'start', fontSize: '11px' }}>Мало!</span>}
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={{ width: '100%', overflowX: 'auto' }}>
              <table style={tbl}>
                <thead>
                  <tr>
                    <th style={tblH}>Наименование</th>
                    <th style={tblH}>Кат.</th>
                    <th style={tblH}>Кол-во</th>
                    <th style={tblH}>Цена</th>
                    <th style={tblH}>Сумма</th>
                    <th style={tblH}></th>
                  </tr>
                </thead>
                <tbody>
                  {displayedProjectMaterials.map(material => (
                    <tr key={material.id} style={{ backgroundColor: material.minQuantity && material.quantity < material.minQuantity ? C.dangerLight : 'transparent' }}>
                      <td style={tblC}>
                        <b style={{ fontSize: '13px' }}>{material.name}</b>
                        {(material.workPackage || material.work_package) && (
                          <div style={{ fontSize: '10px', color: C.textSec, marginTop: '3px' }}>
                            📁 {material.workPackage || material.work_package}
                          </div>
                        )}
                        {material.minQuantity && material.quantity < material.minQuantity && <span style={{ ...badge(C.danger, C.dangerLight, C.dangerBorder), marginLeft: '6px', fontSize: '10px' }}>Мало!</span>}
                      </td>
                      <td style={{ ...tblC, fontSize: '11px', color: C.textSec }}>{material.category || '—'}</td>
                      <td style={tblC}>{material.quantity + ' ' + material.unit}</td>
                      <td style={tblC}>{Number(material.price || 0).toLocaleString() + ' ₽'}</td>
                      <td style={{ ...tblC, fontWeight: '600' }}>{(Number(material.price || 0) * Number(material.quantity || 0)).toLocaleString() + ' ₽'}</td>
                      <td style={tblC}>
                        {canDeleteProjectMaterial && (
                          <button onClick={() => deleteMaterial(material.id)} style={{ ...btnR, padding: '3px 7px' }}>
                            <Trash2 size={11} />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {hiddenProjectMaterials > 0 && (
            <button
              type="button"
              onClick={() => setVisibleObjectRows(limit => Math.min(filteredProjectMaterials.length, limit + objectRowsStep))}
              style={{...btnG, width: '100%', justifyContent: 'center', marginTop: '10px'}}
            >
              Показать ещё {Math.min(hiddenProjectMaterials, objectRowsStep)} материалов
            </button>
          )}
          {canLoadMoreFromServer && (
            <button
              type="button"
              onClick={loadNextProjectMaterials}
              disabled={materialsPage.loading}
              style={{...btnB, width: '100%', justifyContent: 'center', marginTop: '10px', opacity: materialsPage.loading ? 0.65 : 1}}
            >
              {materialsPage.loading ? 'Загружаю...' : 'Загрузить ещё материалы с сервера'}
            </button>
          )}
          {selectedWarehouseProject && !canLoadMoreFromServer && !materialsPage.loading && filteredProjectMaterials.length > 0 && (
            <p style={{ color: C.textMuted, fontSize: '11px', margin: '8px 0 0' }}>
              Показано {displayedProjectMaterials.length} из {filteredProjectMaterials.length} загруженных позиций объекта.
            </p>
          )}
        </div>
      )}

      {showTransferForm && selectedWarehouseProject && (
        <div
          onClick={() => setShowTransferForm(false)}
          style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1600, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        >
          <div onClick={event => event.stopPropagation()} className="mobile-modal" style={{ ...card, padding: isMobile ? '14px' : '20px', width: isMobile ? 'calc(100vw - 24px)' : 'min(560px,92vw)', maxWidth: '720px', maxHeight: isMobile ? 'calc(100dvh - 24px)' : '90vh', overflowY: 'auto', overflowX: 'hidden', boxSizing: 'border-box' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <b style={{ color: C.text, fontSize: '16px' }}>🚚 Передать материал — {selectedWarehouseProject}</b>
              <button onClick={() => setShowTransferForm(false)} style={{ ...btnG, padding: '4px 8px' }}>
                <X size={14} />
              </button>
            </div>
            <select value={selectedWarehouseProject} onChange={() => {}} disabled style={inp}>
              <option value={selectedWarehouseProject}>Склад объекта «{selectedWarehouseProject}»</option>
            </select>
            <p style={{ fontSize: '12px', color: C.textSec, marginBottom: '6px' }}>Выберите материал:</p>
            <div style={{ maxHeight: '180px', overflowY: 'auto', border: '1.5px solid ' + C.border, borderRadius: '8px', padding: '8px', marginBottom: '10px' }}>
              {displayedTransferSourceMaterials.map((material, index) => (
                <div key={index} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 0', borderBottom: '1px solid ' + C.border, flexWrap: isMobile ? 'wrap' : 'nowrap' }}>
                  <input
                    type='checkbox'
                    checked={selectedTransferItems.some(item => transferItemKey(item) === transferItemKey({materialName: material.name, unit: material.unit || 'шт', workPackage: material.workPackage || material.work_package || ''}))}
                    onChange={event => {
                      const item = {
                        materialName: material.name,
                        unit: material.unit || 'шт',
                        workPackage: material.workPackage || material.work_package || '',
                        quantity: '',
                      };
                      updateTransferItems(currentItems => {
                        const existing = (currentItems || []).filter(row => transferItemKey(row) !== transferItemKey(item));
                        return event.target.checked ? [...existing, item] : existing;
                      });
                    }}
                    style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                  />
                  <span style={{ flex: '1 1 180px', minWidth: 0, fontSize: '12px', color: C.text, overflowWrap: 'anywhere' }}>
                    {material.name}
                    {(material.workPackage || material.work_package) && <span style={{ color: C.textSec }}> · 📁 {material.workPackage || material.work_package}</span>}
                  </span>
                  <span style={{ fontSize: '11px', color: C.textSec, flex: isMobile ? '0 0 100%' : '0 0 auto', paddingLeft: isMobile ? '24px' : 0 }}>Остаток: {material.quantity} {material.unit}</span>
                </div>
              ))}
            </div>
            {hiddenTransferMaterials > 0 && (
              <button
                type="button"
                onClick={() => setVisibleTransferRows(limit => Math.min(transferSourceMaterials.length, limit + transferRowsStep))}
                style={{ ...btnG, width: '100%', justifyContent: 'center', marginBottom: '10px' }}
              >
                Показать ещё {Math.min(hiddenTransferMaterials, transferRowsStep)} материалов
              </button>
            )}
            {selectedTransferItems.length > 0 && (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,minmax(0,1fr))', gap: '8px', marginBottom: '10px' }}>
                  <div style={{ padding: '10px', backgroundColor: C.bg, borderRadius: '8px', border: '1px solid ' + C.border }}><p style={{ margin: '0 0 3px', color: C.textSec, fontSize: '10px' }}>Выбрано</p><b style={{ color: C.text }}>{selectedTransferItems.length}</b></div>
                  <div style={{ padding: '10px', backgroundColor: C.bg, borderRadius: '8px', border: '1px solid ' + C.border }}><p style={{ margin: '0 0 3px', color: C.textSec, fontSize: '10px' }}>С количеством</p><b style={{ color: C.warning }}>{selectedTransferItems.filter(item => toNum(item.quantity) > 0).length}</b></div>
                  <div style={{ padding: '10px', backgroundColor: C.bg, borderRadius: '8px', border: '1px solid ' + C.border }}><p style={{ margin: '0 0 3px', color: C.textSec, fontSize: '10px' }}>Ошибки</p><b style={{ color: transferOverStock ? C.danger : C.success }}>{selectedTransferItems.filter(item => toNum(item.quantity) > toNum(stockForTransferItem(item)?.quantity)).length}</b></div>
                  <div style={{ padding: '10px', backgroundColor: C.bg, borderRadius: '8px', border: '1px solid ' + C.border }}><p style={{ margin: '0 0 3px', color: C.textSec, fontSize: '10px' }}>Получатель</p><b style={{ color: newTransfer.toPerson ? C.accent : C.textMuted, overflowWrap: 'anywhere' }}>{newTransfer.toPerson || '—'}</b></div>
                </div>
                <div style={{ display: 'grid', gap: '8px', marginBottom: '10px' }}>
                  {selectedTransferItems.map(item => {
                    const stock = stockForTransferItem(item);
                    const stockQty = toNum(stock?.quantity);
                    const qty = toNum(item.quantity);
                    const over = qty > stockQty;
                    return (
                      <div key={transferItemKey(item)} style={{ padding: '10px', backgroundColor: over ? C.dangerLight : C.bg, border: '1.5px solid ' + (over ? C.dangerBorder : C.border), borderRadius: '8px' }}>
                        <div className='mobile-two-cols' style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'minmax(180px,1fr) 120px auto auto', gap: '8px', alignItems: 'center' }}>
                          <div style={{ minWidth: 0 }}>
                            <b style={{ display: 'block', fontSize: '13px', color: C.text, overflowWrap: 'anywhere' }}>{item.materialName}</b>
                            {item.workPackage && <span style={{ display: 'block', color: C.textSec, fontSize: '10px', marginTop: '2px' }}>Пакет: {item.workPackage}</span>}
                          </div>
                          <input placeholder='Кол-во *' type='number' step='any' inputMode='decimal' value={item.quantity} onChange={event => updateTransferItems(selectedTransferItems.map(row => transferItemKey(row) === transferItemKey(item) ? { ...row, quantity: event.target.value } : row))} style={{ ...inp, marginBottom: 0, width: isMobile ? '100%' : '120px' }} />
                          <span style={{ fontSize: '12px', color: C.textSec }}>{item.unit}</span>
                          <button type='button' onClick={() => updateTransferItems(selectedTransferItems.filter(row => transferItemKey(row) !== transferItemKey(item)))} style={{ ...btnG, padding: '6px 9px' }}><X size={12}/></button>
                        </div>
                        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '6px', fontSize: '11px', color: over ? C.danger : C.textSec }}>
                          <span>Остаток: {stockQty} {item.unit}</span>
                          <span>Останется: {Math.max(0, stockQty - qty)} {item.unit}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
                {selectedTransferItems.map(item => {
                  const materialName = (item.materialName || '').toLowerCase().trim();
                  const matchedRequest = (supplyRequests || []).find(request => {
                    if (request.project !== selectedWarehouseProject) return false;
                    if (request.status === 'Отменена' || request.status === 'Отклонена') return false;
                    const requestName = (request.materialName || '').toLowerCase().trim();
                    if (!materialName || !requestName) return false;
                    return requestName.includes(materialName.split(' ')[0]) || materialName.includes(requestName.split(' ')[0]);
                  });
                  if (!matchedRequest) return null;
                  if (_normalizeUnit(matchedRequest.unit) === _normalizeUnit(item.unit)) return null;
                  const conversion = convertUnits(item.materialName, matchedRequest.quantity, matchedRequest.unit, item.unit);
                  if (conversion) {
                    return (
                      <div key={transferItemKey(item)} style={{ padding: '10px 12px', backgroundColor: C.infoLight, border: '1.5px solid ' + C.infoBorder, borderRadius: '8px', marginBottom: '10px', fontSize: '12px' }}>
                        📐 <b style={{ color: C.text }}>{item.materialName}: заявка была на {matchedRequest.quantity} {matchedRequest.unit}</b>, склад в {item.unit}. Это ≈ <b style={{ color: C.accent }}>{conversion.qty.toFixed(2)} {item.unit}</b>.
                        <p style={{ margin: '4px 0 6px', color: C.textSec, fontSize: '11px' }}>{conversion.note}</p>
                        <button onClick={() => updateTransferItems(selectedTransferItems.map(row => transferItemKey(row) === transferItemKey(item) ? { ...row, quantity: Number(conversion.qty.toFixed(3)) } : row))} style={{ ...btnGr, padding: '4px 10px', fontSize: '11px' }}>
                          <Check size={11} />
                          Подставить {conversion.qty.toFixed(2)} {item.unit}
                        </button>
                      </div>
                    );
                  }
                  return (
                    <div key={transferItemKey(item)} style={{ padding: '10px 12px', backgroundColor: C.warningLight, border: '1.5px solid ' + C.warningBorder, borderRadius: '8px', marginBottom: '10px', fontSize: '12px', color: C.text }}>
                      ⚠️ {item.materialName}: заявка в <b>{matchedRequest.quantity} {matchedRequest.unit}</b>, на складе в <b>{item.unit}</b>. Конверсия не задана — пересчитайте вручную.
                    </div>
                  );
                })}
              </>
            )}
            <select
              value={newTransfer.toUserId ? 'user:' + newTransfer.toUserId : newTransfer.toPerson}
              onChange={event => {
                const rawValue = event.target.value;
                const staffRow = rawValue.startsWith('user:') ? (staff || []).find(item => String(item.id) === rawValue.slice(5)) : null;
                const requesterRow = !staffRow ? (staff || []).find(item => item.name === rawValue) : null;
                const personRow = staffRow || requesterRow;
                setNewTransfer(prev => ({ ...prev, toPerson: personRow ? personRow.name : rawValue, toPersonRole: personRow ? personRow.role : '', toUserId: personRow ? personRow.id : '' }));
              }}
              style={inp}
            >
              <option value=''>Кому передать *</option>
              {(() => {
                const materialNames = selectedTransferItems.map(item => (item.materialName || '').toLowerCase().trim()).filter(Boolean);
                const requesters = new Map();
                (supplyRequests || [])
                  .filter(request => request.project === selectedWarehouseProject && (request.status === 'Утверждена' || request.status === 'Подтверждена прорабом' || request.status === 'Новая'))
                  .forEach(request => {
                    if (materialNames.length > 0) {
                      const requestName = (request.materialName || '').toLowerCase();
                      const matchesAny = materialNames.some(materialName => requestName.includes(materialName.split(' ')[0]) || materialName.includes(requestName.split(' ')[0] || ''));
                      if (!matchesAny) return;
                    }
                    if (request.createdBy && !requesters.has(request.createdBy)) {
                      requesters.set(request.createdBy, { name: request.createdBy, role: request.requestedByRole || '', quantity: request.quantity, unit: request.unit });
                    }
                  });
                const requesterNames = new Set(requesters.keys());
                return (
                  <>
                    {requesters.size > 0 && (
                      <optgroup label="📋 Заявляли этот материал">
                        {Array.from(requesters.values()).map((requester, index) => (
                          <option key={'wreq-' + index} value={(staff || []).find(item => item.name === requester.name) ? 'user:' + (staff || []).find(item => item.name === requester.name).id : requester.name}>
                            ⭐ {requester.name} ({requester.role}) — просил {requester.quantity} {requester.unit}
                          </option>
                        ))}
                      </optgroup>
                    )}
                    <optgroup label={requesters.size > 0 ? '👥 Остальные исполнители' : '👥 Исполнители'}>
                      {(staff || []).filter(item => ['мастер', 'бригадир', 'субподрядчик'].includes((item.role || '').toLowerCase()) && !requesterNames.has(item.name)).map(item => (
                        <option key={item.id} value={'user:' + item.id}>{item.name} ({item.role})</option>
                      ))}
                    </optgroup>
                  </>
                );
              })()}
            </select>
            {(() => {
              const selectedPackages = [...new Set(selectedTransferItems.map(item => item.workPackage || '').filter(Boolean))];
              const missingPackageCount = selectedTransferItems.filter(item => !(item.workPackage || '').trim()).length;
              const packageSelectValue = selectedPackages.length === 1 ? selectedPackages[0] : (newTransfer.workPackage || '');
              const showPackageControl = selectedTransferItems.length > 0 && (manualTransferPackageEdit || transferMissingPackage);
              const packageHint = (() => {
                if (transferMissingPackage) {
                  return `У ${missingPackageCount} строк пакет не определён. Выберите пакет, чтобы передача и дальнейшее списание прошли в одном разделе работ.`;
                }
                if (missingPackageCount > 0) {
                  return `У ${missingPackageCount} строк пакет не указан. Если выдаёте исполнителю, система попросит выбрать пакет перед сохранением.`;
                }
                if (selectedPackages.length > 1) {
                  return `У выбранных строк разные пакеты: ${selectedPackages.slice(0, 3).join(', ')}${selectedPackages.length > 3 ? '...' : ''}. Каждая строка уйдёт в своём пакете.`;
                }
                if (selectedPackages.length === 1) {
                  return `Пакет берётся из выбранной строки склада: ${selectedPackages[0]}.`;
                }
                return 'Пакет будет взят из строки склада после выбора материала.';
              })();
              return (
                <>
                  {selectedTransferItems.length > 0 && (
                    <div style={{ padding: '10px 12px', backgroundColor: transferMissingPackage ? C.warningLight : C.infoLight, border: '1.5px solid ' + (transferMissingPackage ? C.warningBorder : C.infoBorder), borderRadius: '8px', color: C.text, fontSize: '12px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap' }}>
                        <b style={{ color: transferMissingPackage ? C.warning : C.info }}>Пакет работ</b>
                        {!showPackageControl && (
                          <button type='button' onClick={() => setManualTransferPackageEdit(true)} style={{ ...btnG, padding: '4px 10px', fontSize: '11px' }}>
                            Изменить вручную
                          </button>
                        )}
                      </div>
                      <p style={{ margin: '5px 0 0', color: C.textSec }}>{packageHint}</p>
                    </div>
                  )}
                  {showPackageControl && (
                    <select
                      value={packageSelectValue}
                      onChange={event => {
                        updateTransferItems(selectedTransferItems.length > 0
                          ? selectedTransferItems.map(item => ({ ...item, workPackage: event.target.value }))
                          : [{ materialName: newTransfer.materialName, quantity: newTransfer.quantity, unit: newTransfer.unit || 'шт', workPackage: event.target.value }]);
                        if (event.target.value) setManualTransferPackageEdit(false);
                      }}
                      style={{ ...inp, borderColor: transferMissingPackage ? C.warning : inp.borderColor }}
                    >
                      <option value=''>{selectedTransferItems.length > 1 && selectedPackages.length > 1 ? 'Разные пакеты в выбранных строках' : (transferNeedsPackage ? 'Пакет работ *' : 'Пакет работ')}</option>
                      {transferPackageOptions.map(packageName => (
                        <option key={packageName} value={packageName}>{packageName}</option>
                      ))}
                    </select>
                  )}
                  {manualTransferPackageEdit && !transferMissingPackage && (
                    <button type='button' onClick={() => setManualTransferPackageEdit(false)} style={{ ...btnG, justifyContent: 'center' }}>
                      Оставить пакеты из строк склада
                    </button>
                  )}
                </>
              );
            })()}
            <input type='date' value={newTransfer.transferDate} onChange={event => setNewTransfer({ ...newTransfer, transferDate: event.target.value })} style={inp} />
            <input placeholder='Примечание' value={newTransfer.notes} onChange={event => setNewTransfer({ ...newTransfer, notes: event.target.value })} style={inp} />
            {(transferMissingPackage || transferOverStock) && (
              <div style={{ padding: '10px 12px', backgroundColor: transferOverStock ? C.dangerLight : C.warningLight, border: '1.5px solid ' + (transferOverStock ? C.dangerBorder : C.warningBorder), borderRadius: '8px', color: transferOverStock ? C.danger : C.warning, fontSize: '12px', fontWeight: 700 }}>
                {transferOverStock
                  ? 'Нельзя выдать больше остатка. Проверьте строки, выделенные красным.'
                  : 'Для выдачи мастеру, бригадиру или субподрядчику выберите пакет работ.'}
              </div>
            )}
            <div className='mobile-actions' style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={async () => {
                  if (!canSaveObjectTransfer) {
                    window.alert(transferOverStock
                      ? 'Нельзя выдать больше остатка на складе объекта.'
                      : transferMissingPackage
                        ? 'Для выдачи исполнителю выберите пакет работ.'
                        : 'Заполните: материал, количество, кому');
                    return;
                  }
                  const savedRows = [];
                  for (const item of selectedTransferItems) {
                    const data = {
                      ...newTransfer,
                      items: undefined,
                      materialName: item.materialName,
                      quantity: item.quantity,
                      unit: item.unit,
                      workPackage: item.workPackage,
                      invoiceId: item.invoiceId || newTransfer.invoiceId || null,
                      invoiceLineKey: item.invoiceLineKey || newTransfer.invoiceLineKey || '',
                      invoiceLineIndex: item.invoiceLineIndex ?? newTransfer.invoiceLineIndex ?? null,
                      invoiceNumber: item.invoiceNumber || newTransfer.invoiceNumber || '',
                      fromLocation: selectedWarehouseProject,
                      projectName: selectedWarehouseProject,
                      createdBy: currentUser.name || ''
                    };
                    const response = await fetch(API + '/material-transfers', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify(data),
                    });
                    const saved = await response.json();
                    if (!response.ok || !saved.ok) {
                      if (savedRows.length > 0) {
                        setMaterialTransfers(prev => [...savedRows.map(row => ({ ...row.data, id: row.id, signed: false })).reverse(), ...prev]);
                        setMaterials(prev => savedRows.reduce((acc, row) => acc.map(material => (
                          material.name === row.data.materialName &&
                          material.project === selectedWarehouseProject &&
                          (material.workPackage || material.work_package || '') === (row.data.workPackage || '')
                        ) ? { ...material, quantity: Number(material.quantity || 0) - Number(row.data.quantity || 0) } : material), prev));
                      }
                      window.alert('Ошибка по позиции «' + item.materialName + '»: ' + (saved.detail || saved.error || 'не удалось списать со склада'));
                      return;
                    }
                    savedRows.push({ id: saved.id, data });
                  }
                  setMaterialTransfers(prev => [...savedRows.map(row => ({ ...row.data, id: row.id, signed: false })).reverse(), ...prev]);
                  setMaterials(prev => savedRows.reduce((acc, row) => acc.map(material => (
                    material.name === row.data.materialName &&
                    material.project === selectedWarehouseProject &&
                    (material.workPackage || material.work_package || '') === (row.data.workPackage || '')
                  ) ? { ...material, quantity: Number(material.quantity || 0) - Number(row.data.quantity || 0) } : material), prev));
                  setShowTransferForm(false);
                  setNewTransfer(createMaterialTransferForm({ items: [], fromLocation: selectedWarehouseProject }));
                  notify('Передано материалов: ' + savedRows.length + ' → ' + newTransfer.toPerson, 'material');
                }}
                disabled={!canSaveObjectTransfer}
                style={{ ...btnO, opacity: canSaveObjectTransfer ? 1 : 0.55, cursor: canSaveObjectTransfer ? 'pointer' : 'not-allowed' }}
              >
                <Check size={14} />
                Передать
              </button>
              <button onClick={() => setShowTransferForm(false)} style={btnG}>
                <X size={14} />
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

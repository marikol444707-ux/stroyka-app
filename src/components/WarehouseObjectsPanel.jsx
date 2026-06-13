import React from 'react';
import {
  ArrowLeft,
  Check,
  ChevronRight,
  Download,
  Plus,
  Trash2,
  Truck,
  X,
} from 'lucide-react';
import { API } from '../api';

export default function WarehouseObjectsPanel({
  C,
  card,
  inp,
  btnO,
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
  openReceiveInvoice,
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
  warehouseMain,
  supplyRequests,
  _normalizeUnit,
  convertUnits,
  staff,
  setWarehouseMain,
  setMaterials,
  notify,
}) {
  const projectMaterials = (projectName) => (materials || []).filter(material => material.project === projectName);
  const transferSourceMaterials = [
    ...(newTransfer.fromLocation === 'Основной склад' ? (warehouseMain || []) : []),
    ...((newTransfer.fromLocation !== 'Основной склад')
      ? (materials || []).filter(material => material.project === newTransfer.fromLocation)
      : []),
  ];

  return (
    <div>
      {!selectedWarehouseProject ? (
        <div>
          <h3 style={{ color: C.text, marginBottom: '15px', fontSize: '15px', fontWeight: '700' }}>Материалы по объектам</h3>
          {visibleActiveProjects(projects).map(project => {
            const projectRows = projectMaterials(project.name);
            const total = projectRows.reduce((sum, material) => sum + Number(material.price || 0) * Number(material.quantity || 0), 0);
            return (
              <div
                key={project.id}
                style={{ ...card, padding: '16px', marginBottom: '10px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                onClick={() => setSelectedWarehouseProject(project.name)}
              >
                <div>
                  <b style={{ color: C.text, fontSize: '14px' }}>{project.name}</b>
                  <p style={{ color: C.textSec, margin: '3px 0', fontSize: '12px' }}>{projectRows.length + ' позиций · ' + total.toLocaleString() + ' ₽'}</p>
                </div>
                <ChevronRight size={18} color={C.textMuted} />
              </div>
            );
          })}
        </div>
      ) : (
        <div>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '15px' }}>
            <button onClick={() => setSelectedWarehouseProject(null)} style={btnG}>
              <ArrowLeft size={14} />
              Назад
            </button>
            <h3 style={{ color: C.text, margin: 0, fontSize: '15px', fontWeight: '700' }}>{selectedWarehouseProject}</h3>
          </div>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '15px', flexWrap: 'wrap' }}>
            <button onClick={() => openReceiveInvoice(selectedWarehouseProject)} style={btnO}>
              <Plus size={14} />
              Принять материал
            </button>
            {(isLeadership() || user.role === 'прораб' || user.role === 'кладовщик') && (
              <button
                onClick={async () => {
                  const response = await fetch(API + '/material-transfers?project_name=' + encodeURIComponent(selectedWarehouseProject));
                  const data = await response.json();
                  setMaterialTransfers(Array.isArray(data) ? data : []);
                  setNewTransfer({
                    materialName: '',
                    quantity: '',
                    unit: 'шт',
                    workPackage: '',
                    toPerson: '',
                    toPersonRole: '',
                    fromLocation: selectedWarehouseProject,
                    notes: '',
                    transferDate: new Date().toISOString().split('T')[0],
                  });
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
                projectMaterials(selectedWarehouseProject).map(material => ({
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
          {renderMaterialReconciliationPanel(selectedWarehouseProject, { limit: 25, title: '📊 Контроль материалов объекта' })}
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
              {projectMaterials(selectedWarehouseProject).map(material => (
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
                    <button onClick={() => deleteMaterial(material.id)} style={{ ...btnR, padding: '3px 7px' }}>
                      <Trash2 size={11} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showTransferForm && selectedWarehouseProject && (
        <div
          onClick={() => setShowTransferForm(false)}
          style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1600, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        >
          <div onClick={event => event.stopPropagation()} style={{ ...card, padding: '20px', width: 'min(560px,92vw)', maxHeight: '90vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <b style={{ color: C.text, fontSize: '16px' }}>🚚 Передать материал — {selectedWarehouseProject}</b>
              <button onClick={() => setShowTransferForm(false)} style={{ ...btnG, padding: '4px 8px' }}>
                <X size={14} />
              </button>
            </div>
            <select value={newTransfer.fromLocation} onChange={event => setNewTransfer({ ...newTransfer, fromLocation: event.target.value, materialName: '', quantity: '' })} style={inp}>
              <option value='Основной склад'>Основной склад</option>
              <option value={selectedWarehouseProject}>Склад объекта «{selectedWarehouseProject}»</option>
            </select>
            <p style={{ fontSize: '12px', color: C.textSec, marginBottom: '6px' }}>Выберите материал:</p>
            <div style={{ maxHeight: '180px', overflowY: 'auto', border: '1.5px solid ' + C.border, borderRadius: '8px', padding: '8px', marginBottom: '10px' }}>
              {transferSourceMaterials.map((material, index) => (
                <div key={index} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 0', borderBottom: '1px solid ' + C.border }}>
                  <input
                    type='checkbox'
                    checked={newTransfer.materialName === material.name && (newTransfer.workPackage || '') === ((material.workPackage || material.work_package || ''))}
                    onChange={event => setNewTransfer({
                      ...newTransfer,
                      materialName: event.target.checked ? material.name : '',
                      unit: event.target.checked ? material.unit : newTransfer.unit,
                      workPackage: event.target.checked ? (material.workPackage || material.work_package || '') : '',
                      quantity: ''
                    })}
                    style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                  />
                  <span style={{ flex: 1, fontSize: '12px', color: C.text }}>
                    {material.name}
                    {(material.workPackage || material.work_package) && <span style={{ color: C.textSec }}> · 📁 {material.workPackage || material.work_package}</span>}
                  </span>
                  <span style={{ fontSize: '11px', color: C.textSec }}>Остаток: {material.quantity} {material.unit}</span>
                </div>
              ))}
            </div>
            {newTransfer.materialName && (
              <>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '10px', padding: '10px', backgroundColor: C.bg, borderRadius: '8px' }}>
                  <b style={{ fontSize: '13px', color: C.text, flex: 1 }}>{newTransfer.materialName}</b>
                  <input placeholder='Кол-во *' type='number' step='any' inputMode='decimal' value={newTransfer.quantity} onChange={event => setNewTransfer({ ...newTransfer, quantity: event.target.value })} style={{ ...inp, marginBottom: 0, width: '120px' }} />
                  <span style={{ fontSize: '12px', color: C.textSec }}>{newTransfer.unit}</span>
                </div>
                {(() => {
                  const materialName = (newTransfer.materialName || '').toLowerCase().trim();
                  const matchedRequest = (supplyRequests || []).find(request => {
                    if (request.project !== selectedWarehouseProject) return false;
                    if (request.status === 'Отменена' || request.status === 'Отклонена') return false;
                    const requestName = (request.materialName || '').toLowerCase().trim();
                    if (!materialName || !requestName) return false;
                    return requestName.includes(materialName.split(' ')[0]) || materialName.includes(requestName.split(' ')[0]);
                  });
                  if (!matchedRequest) return null;
                  if (_normalizeUnit(matchedRequest.unit) === _normalizeUnit(newTransfer.unit)) return null;
                  const conversion = convertUnits(newTransfer.materialName, matchedRequest.quantity, matchedRequest.unit, newTransfer.unit);
                  if (conversion) {
                    return (
                      <div style={{ padding: '10px 12px', backgroundColor: C.infoLight, border: '1.5px solid ' + C.infoBorder, borderRadius: '8px', marginBottom: '10px', fontSize: '12px' }}>
                        📐 <b style={{ color: C.text }}>Заявка была на {matchedRequest.quantity} {matchedRequest.unit}</b>, склад в {newTransfer.unit}. Это ≈ <b style={{ color: C.accent }}>{conversion.qty.toFixed(2)} {newTransfer.unit}</b>.
                        <p style={{ margin: '4px 0 6px', color: C.textSec, fontSize: '11px' }}>{conversion.note}</p>
                        <button onClick={() => setNewTransfer({ ...newTransfer, quantity: Number(conversion.qty.toFixed(3)) })} style={{ ...btnGr, padding: '4px 10px', fontSize: '11px' }}>
                          <Check size={11} />
                          Подставить {conversion.qty.toFixed(2)} {newTransfer.unit}
                        </button>
                      </div>
                    );
                  }
                  return (
                    <div style={{ padding: '10px 12px', backgroundColor: C.warningLight, border: '1.5px solid ' + C.warningBorder, borderRadius: '8px', marginBottom: '10px', fontSize: '12px', color: C.text }}>
                      ⚠️ Заявка в <b>{matchedRequest.quantity} {matchedRequest.unit}</b>, на складе в <b>{newTransfer.unit}</b>. Конверсия не задана — пересчитайте вручную.
                    </div>
                  );
                })()}
              </>
            )}
            <select
              value={newTransfer.toPerson}
              onChange={event => {
                const staffRow = (staff || []).find(item => item.name === event.target.value);
                setNewTransfer({ ...newTransfer, toPerson: event.target.value, toPersonRole: staffRow ? staffRow.role : '' });
              }}
              style={inp}
            >
              <option value=''>Кому передать *</option>
              {(() => {
                const materialName = (newTransfer.materialName || '').toLowerCase().trim();
                const requesters = new Map();
                (supplyRequests || [])
                  .filter(request => request.project === selectedWarehouseProject && (request.status === 'Утверждена' || request.status === 'Подтверждена прорабом' || request.status === 'Новая'))
                  .forEach(request => {
                    if (materialName) {
                      const requestName = (request.materialName || '').toLowerCase();
                      if (!requestName.includes(materialName.split(' ')[0]) && !materialName.includes(requestName.split(' ')[0] || '')) return;
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
                          <option key={'wreq-' + index} value={requester.name}>
                            ⭐ {requester.name} ({requester.role}) — просил {requester.quantity} {requester.unit}
                          </option>
                        ))}
                      </optgroup>
                    )}
                    <optgroup label={requesters.size > 0 ? '👥 Остальные' : '👥 Мастера и прорабы'}>
                      {(staff || []).filter(item => ['мастер', 'прораб', 'бригадир', 'субподрядчик'].includes((item.role || '').toLowerCase()) && !requesterNames.has(item.name)).map(item => (
                        <option key={item.id} value={item.name}>{item.name} ({item.role})</option>
                      ))}
                    </optgroup>
                  </>
                );
              })()}
            </select>
            <input type='date' value={newTransfer.transferDate} onChange={event => setNewTransfer({ ...newTransfer, transferDate: event.target.value })} style={inp} />
            <input placeholder='Примечание' value={newTransfer.notes} onChange={event => setNewTransfer({ ...newTransfer, notes: event.target.value })} style={inp} />
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={async () => {
                  if (!newTransfer.materialName || !newTransfer.quantity || !newTransfer.toPerson) {
                    window.alert('Заполните: материал, количество, кому');
                    return;
                  }
                  const data = { ...newTransfer, projectName: selectedWarehouseProject, createdBy: user.name };
                  const response = await fetch(API + '/material-transfers', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data),
                  });
                  const saved = await response.json();
                  if (!response.ok || !saved.ok) {
                    window.alert('Ошибка: ' + (saved.detail || saved.error || 'не удалось списать со склада'));
                    return;
                  }
                  setMaterialTransfers(prev => [{ ...data, id: saved.id, signed: false }, ...prev]);
                  const quantity = Number(newTransfer.quantity);
                  if (newTransfer.fromLocation === 'Основной склад') {
                    setWarehouseMain(prev => prev.map(material => material.name === newTransfer.materialName ? { ...material, quantity: Number(material.quantity || 0) - quantity } : material));
                  } else {
                    setMaterials(prev => prev.map(material => (
                      material.name === newTransfer.materialName &&
                      material.project === newTransfer.fromLocation &&
                      (material.workPackage || material.work_package || '') === (newTransfer.workPackage || '')
                    ) ? { ...material, quantity: Number(material.quantity || 0) - quantity } : material));
                  }
                  setShowTransferForm(false);
                  setNewTransfer({ materialName: '', quantity: '', unit: 'шт', workPackage: '', toPerson: '', toPersonRole: '', fromLocation: 'Основной склад', notes: '', transferDate: new Date().toISOString().split('T')[0] });
                  notify('Передал ' + (saved.materialName || newTransfer.materialName) + ' (' + newTransfer.quantity + ' ' + newTransfer.unit + ') → ' + newTransfer.toPerson, 'material');
                }}
                style={btnO}
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

import React from 'react';
import { Check, Edit2, Eye, Plus, Trash2, X } from 'lucide-react';
import { API } from '../api';

export default function WarehouseOperationsPanel({
  warehouseTab,
  C,
  card,
  inp,
  btnO,
  btnG,
  btnB,
  btnGr,
  btnR,
  badge,
  tbl,
  tblH,
  tblC,
  showForm,
  setShowForm,
  projects,
  visibleActiveProjects,
  warehouseMain,
  materials,
  warehouseMovements,
  newMovement,
  setNewMovement,
  applyWarehouseMovement,
  buildMovementDoc,
  showPreview,
  toolsTab,
  setToolsTab,
  editingItem,
  setEditingItem,
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
  user,
  isMobile = false,
}) {
  const touchCompact = typeof window !== 'undefined'
    && (window.visualViewport?.width || window.innerWidth || 0) < 1100
    && (
      (typeof window.matchMedia === 'function' && window.matchMedia('(pointer: coarse)').matches)
      || (typeof navigator !== 'undefined' && /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || ''))
    );
  const compactRows = isMobile || touchCompact;

  if (warehouseTab === 'move') {
    const sourceMaterials = newMovement.fromLocation === 'Основной склад'
      ? warehouseMain
      : materials.filter(material => material.project === newMovement.fromLocation);
    const visibleSourceMaterials = compactRows ? sourceMaterials.slice(0, 40) : sourceMaterials;
    const movementMaterialKey = (material = {}) => [
      material.id || '',
      material.name || '',
      material.project || '',
      material.workPackage || material.work_package || '',
      material.unit || '',
    ].join('|');

    return (
      <div>
        <h3 style={{ color: C.text, marginBottom: '15px', fontSize: '15px', fontWeight: '700' }}>
          Перемещение материалов
        </h3>
        <div style={{ ...card, padding: compactRows ? '14px' : '20px', marginBottom: '16px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: compactRows ? '1fr' : '1fr 1fr', gap: '10px', marginBottom: '15px' }}>
            <div>
              <label style={{ fontSize: '12px', color: C.textSec, display: 'block', marginBottom: '5px' }}>
                Откуда:
              </label>
              <select
                value={newMovement.fromLocation}
                onChange={e => setNewMovement({ ...newMovement, fromLocation: e.target.value, selectedMaterials: [] })}
                style={inp}
              >
                <option value="Основной склад">Основной склад</option>
                {visibleActiveProjects(projects).map(project => (
                  <option key={project.id} value={project.name}>{project.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={{ fontSize: '12px', color: C.textSec, display: 'block', marginBottom: '5px' }}>
                Куда:
              </label>
              <select
                value={newMovement.toLocation}
                onChange={e => setNewMovement({ ...newMovement, toLocation: e.target.value })}
                style={inp}
              >
                <option value="">Выберите...</option>
                <option value="Основной склад">Основной склад</option>
                {visibleActiveProjects(projects)
                  .filter(project => project.name !== newMovement.fromLocation)
                  .map(project => (
                    <option key={project.id} value={project.name}>{project.name}</option>
                  ))}
              </select>
            </div>
          </div>

          <b style={{ color: C.text, fontSize: '13px', display: 'block', marginBottom: '10px' }}>
            Выберите материалы:
          </b>
          {visibleSourceMaterials.map(material => {
            const materialKey = movementMaterialKey(material);
            const selected = newMovement.selectedMaterials?.find(item => movementMaterialKey(item) === materialKey);
            return (
              <div
                key={material.id}
                style={{
                  padding: '10px',
                  borderRadius: '8px',
                  marginBottom: '6px',
                  border: '1.5px solid ' + (selected ? C.accent : C.border),
                  backgroundColor: selected ? C.accentLight : C.bgWhite,
                  display: 'flex',
                  flexDirection: compactRows ? 'column' : 'row',
                  alignItems: 'center',
                  ...(compactRows ? {alignItems:'stretch'} : {}),
                  gap: '10px',
                }}
              >
                <label style={{display:'flex',alignItems:'flex-start',gap:'10px',minWidth:0,cursor:'pointer'}}>
                  <input
                    type="checkbox"
                    checked={!!selected}
                    onChange={e => {
                      if (e.target.checked) {
                        setNewMovement(prev => ({
                          ...prev,
                          selectedMaterials: [...(prev.selectedMaterials || []), { ...material, quantity: '' }],
                        }));
                        return;
                      }
                      setNewMovement(prev => ({
                        ...prev,
                        selectedMaterials: (prev.selectedMaterials || []).filter(item => movementMaterialKey(item) !== materialKey),
                      }));
                    }}
                    style={{ width: '16px', height: '16px', accentColor: C.accent, flex:'0 0 auto', marginTop:'2px' }}
                  />
                  <span style={{ flex: 1, minWidth:0, fontSize: '13px', color: C.text, overflowWrap:'anywhere', lineHeight:'1.35' }}>
                    {material.name}
                    <small style={{ display: 'block', color: C.textSec, marginTop: '3px' }}>
                      Есть: {material.quantity} {material.unit}
                    </small>
                    {(material.workPackage || material.work_package) && (
                      <small style={{ display: 'block', color: C.textSec, marginTop: '2px' }}>
                        Пакет: {material.workPackage || material.work_package}
                      </small>
                    )}
                  </span>
                </label>
                {selected && (
                  <input
                    placeholder="Кол-во"
                    type="number"
                    step="any"
                    inputMode="decimal"
                    value={selected.quantity}
                    onChange={e => setNewMovement(prev => ({
                      ...prev,
                      selectedMaterials: prev.selectedMaterials.map(item => (
                        movementMaterialKey(item) === materialKey ? { ...item, quantity: e.target.value } : item
                      )),
                    }))}
                    style={{
                      width: compactRows ? '100%' : '100px',
                      boxSizing:'border-box',
                      padding: '5px 8px',
                      border: '1.5px solid ' + C.accent,
                      borderRadius: '6px',
                      fontSize: '12px',
                    }}
                  />
                )}
              </div>
            );
          })}
          {visibleSourceMaterials.length < sourceMaterials.length && (
            <div style={{ padding: '10px 12px', color: C.textMuted, fontSize: '11px', textAlign: 'center' }}>
              Показаны первые {visibleSourceMaterials.length} из {sourceMaterials.length}. Для полного списка откройте склад на компьютере или уточните источник перемещения.
            </div>
          )}

          <input
            placeholder="Примечание"
            value={newMovement.notes}
            onChange={e => setNewMovement({ ...newMovement, notes: e.target.value })}
            style={{ ...inp, marginTop: '10px' }}
          />
          <div style={{ display: 'flex', gap: '8px', marginTop: '10px', flexWrap:'wrap' }}>
            <button
              onClick={async () => {
                await applyWarehouseMovement();
                showPreview(
                  buildMovementDoc(newMovement, (newMovement.selectedMaterials || []).filter(item => item.quantity)),
                  'Накладная М-11'
                );
              }}
              style={{...btnO,...(compactRows ? {flex:'1 1 100%',justifyContent:'center'} : {})}}
            >
              <Check size={14} />
              Переместить и распечатать
            </button>
            <button onClick={applyWarehouseMovement} style={{...btnG,...(compactRows ? {flex:'1 1 100%',justifyContent:'center'} : {})}}>Переместить</button>
          </div>
        </div>

        <h3 style={{ color: C.text, marginBottom: '10px', fontSize: '14px', fontWeight: '700' }}>
          История перемещений
        </h3>
        {compactRows ? (
          <div style={{display:'grid',gap:'10px'}}>
            {warehouseMovements.slice(0, 20).map((movement, index) => (
              <div key={index} style={{padding:'12px',borderRadius:'12px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,display:'grid',gap:'8px'}}>
                <b style={{color:C.text,fontSize:'13px',lineHeight:'1.35',overflowWrap:'anywhere'}}>{movement.materialName}</b>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',fontSize:'12px',color:C.textSec}}>
                  <span style={{overflowWrap:'anywhere'}}><b style={{color:C.text}}>Откуда:</b> {movement.fromLocation || '—'}</span>
                  <span style={{overflowWrap:'anywhere'}}><b style={{color:C.text}}>Куда:</b> {movement.toLocation || '—'}</span>
                  <span><b style={{color:C.text}}>Кол-во:</b> {movement.quantity} {movement.unit}</span>
                  <span><b style={{color:C.text}}>Дата:</b> {movement.date || '—'}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
        <table style={tbl}>
          <thead>
            <tr>
              <th style={tblH}>Материал</th>
              <th style={tblH}>Откуда</th>
              <th style={tblH}>Куда</th>
              <th style={tblH}>Кол-во</th>
              <th style={tblH}>Дата</th>
            </tr>
          </thead>
          <tbody>
            {warehouseMovements.slice(0, 20).map((movement, index) => (
              <tr key={index}>
                <td style={tblC}>{movement.materialName}</td>
                <td style={tblC}>{movement.fromLocation}</td>
                <td style={tblC}>{movement.toLocation}</td>
                <td style={tblC}>{movement.quantity + ' ' + movement.unit}</td>
                <td style={tblC}>{movement.date}</td>
              </tr>
            ))}
          </tbody>
        </table>
        )}
      </div>
    );
  }

  if (warehouseTab === 'tools') {
    return (
      <div>
        <div style={{ display: 'flex', gap: '8px', marginBottom: '15px', flexWrap: 'wrap' }}>
          {['list', 'history'].map(tab => (
            <button
              key={tab}
              onClick={() => setToolsTab(tab)}
              style={{ ...(toolsTab === tab ? btnO : btnG), fontSize: '12px', padding: '6px 14px' }}
            >
              {{ list: 'Список', history: 'История' }[tab]}
            </button>
          ))}
          <button
            onClick={() => {
              setShowForm(!showForm);
              setEditingItem(null);
              setNewTool({
                name: '',
                inventoryNumber: '',
                cost: '',
                status: 'На складе',
                location: 'Основной склад',
                project: '',
                masterId: '',
                masterName: '',
                issueType: '',
                notes: '',
              });
            }}
            style={btnO}
          >
            <Plus size={14} />
            Добавить
          </button>
        </div>

        {showForm && (
          <div style={{ ...card, padding: '20px', marginBottom: '15px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <input
                placeholder="Название *"
                value={newTool.name}
                onChange={e => setNewTool({ ...newTool, name: e.target.value })}
                style={{ ...inp, marginBottom: 0 }}
              />
              <input
                placeholder="Инв. №"
                value={newTool.inventoryNumber}
                onChange={e => setNewTool({ ...newTool, inventoryNumber: e.target.value })}
                style={{ ...inp, marginBottom: 0 }}
              />
              <input
                placeholder="Стоимость (₽)"
                type="number"
                step="any"
                inputMode="decimal"
                value={newTool.cost}
                onChange={e => setNewTool({ ...newTool, cost: e.target.value })}
                style={{ ...inp, marginBottom: 0 }}
              />
              <select
                value={newTool.status}
                onChange={e => setNewTool({ ...newTool, status: e.target.value })}
                style={{ ...inp, marginBottom: 0 }}
              >
                {TOOL_STATUSES.map(status => <option key={status}>{status}</option>)}
              </select>
              <textarea
                placeholder="Примечание"
                value={newTool.notes}
                onChange={e => setNewTool({ ...newTool, notes: e.target.value })}
                style={{ ...inp, marginBottom: 0, gridColumn: 'span 2', height: '60px', resize: 'vertical' }}
              />
            </div>
            <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
              <button onClick={saveTool} style={btnO}>
                <Check size={14} />
                {editingItem ? 'Сохранить' : 'Добавить'}
              </button>
              <button onClick={() => { setShowForm(false); setEditingItem(null); }} style={btnG}>
                <X size={14} />
                Отмена
              </button>
            </div>
          </div>
        )}

        {toolsTab === 'list' && (
          <table style={tbl}>
            <thead>
              <tr>
                <th style={tblH}>Инструмент</th>
                <th style={tblH}>Инв. №</th>
                <th style={tblH}>Статус</th>
                <th style={tblH}>У кого</th>
                <th style={tblH}>Стоимость</th>
                <th style={tblH}></th>
              </tr>
            </thead>
            <tbody>
              {tools.map(tool => (
                <tr key={tool.id}>
                  <td style={tblC}>
                    <b style={{ fontSize: '13px' }}>{tool.name}</b>
                    {tool.notes && <p style={{ color: C.textMuted, margin: '1px 0', fontSize: '11px' }}>{tool.notes}</p>}
                  </td>
                  <td style={tblC}>{tool.inventoryNumber || '—'}</td>
                  <td style={tblC}>
                    <span style={badge(
                      tool.status === 'На складе' ? C.success : tool.status.includes('У мастера') ? C.accent : tool.status === 'На ремонте' ? C.warning : C.danger,
                      tool.status === 'На складе' ? C.successLight : tool.status.includes('У мастера') ? C.accentLight : tool.status === 'На ремонте' ? C.warningLight : C.dangerLight,
                      tool.status === 'На складе' ? C.successBorder : tool.status.includes('У мастера') ? C.accentBorder : tool.status === 'На ремонте' ? C.warningBorder : C.dangerBorder
                    )}>
                      {tool.status}
                    </span>
                  </td>
                  <td style={tblC}>{tool.masterName ? tool.masterName + (tool.project ? ' (' + tool.project + ')' : '') : '—'}</td>
                  <td style={tblC}>
                    {tool.cost ? tool.cost.toLocaleString() + ' ₽' : '—'}
                    {tool.issueType === 'В счёт зарплаты' && (
                      <span style={{ ...badge(C.danger, C.dangerLight, C.dangerBorder), marginLeft: '4px', fontSize: '10px' }}>
                        Удержание
                      </span>
                    )}
                  </td>
                  <td style={tblC}>
                    <div style={{ display: 'flex', gap: '4px' }}>
                      {tool.status === 'На складе' && isProrab() && (
                        <button onClick={() => setShowIssueToolModal(tool)} style={{ ...btnO, padding: '4px 8px', fontSize: '11px' }}>
                          Выдать
                        </button>
                      )}
                      {tool.status.includes('У мастера') && isProrab() && (
                        <button onClick={() => setShowReturnToolModal(tool)} style={{ ...btnGr, padding: '4px 8px', fontSize: '11px' }}>
                          Вернуть
                        </button>
                      )}
                      <button
                        onClick={() => {
                          setEditingItem(tool);
                          setNewTool({ ...tool, cost: String(tool.cost) });
                          setShowForm(true);
                        }}
                        style={{ ...btnG, padding: '4px 8px' }}
                      >
                        <Edit2 size={11} />
                      </button>
                      <button onClick={() => deleteTool(tool.id)} style={{ ...btnR, padding: '4px 8px' }}>
                        <Trash2 size={11} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {toolsTab === 'history' && (
          <table style={tbl}>
            <thead>
              <tr>
                <th style={tblH}>Инструмент</th>
                <th style={tblH}>Действие</th>
                <th style={tblH}>Мастер</th>
                <th style={tblH}>Объект</th>
                <th style={tblH}>Состояние</th>
                <th style={tblH}>Дата</th>
              </tr>
            </thead>
            <tbody>
              {toolHistory.map((row, index) => (
                <tr key={index}>
                  <td style={tblC}>{row.toolName}</td>
                  <td style={tblC}>
                    <span style={badge(
                      row.action === 'Выдача' ? C.accent : C.success,
                      row.action === 'Выдача' ? C.accentLight : C.successLight,
                      row.action === 'Выдача' ? C.accentBorder : C.successBorder
                    )}>
                      {row.action}
                    </span>
                  </td>
                  <td style={tblC}>{row.masterName}</td>
                  <td style={tblC}>{row.project}</td>
                  <td style={tblC}>{row.condition}</td>
                  <td style={tblC}>{row.date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    );
  }

  if (warehouseTab === 'inventory') {
    return (
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
          <b style={{ color: C.text, fontSize: '15px', fontWeight: '700' }}>Инвентаризация</b>
          <button onClick={() => setShowForm(!showForm)} style={btnO}>
            <Plus size={14} />
            Новая
          </button>
        </div>

        {showForm && (
          <div style={{ ...card, padding: '20px', marginBottom: '15px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <select
                value={newInventory.project}
                onChange={e => setNewInventory({ ...newInventory, project: e.target.value })}
                style={{ ...inp, marginBottom: 0 }}
              >
                <option value="">Выберите объект</option>
                {projects.map(project => <option key={project.id} value={project.name}>{project.name}</option>)}
              </select>
              <input
                type="date"
                value={newInventory.date}
                onChange={e => setNewInventory({ ...newInventory, date: e.target.value })}
                style={{ ...inp, marginBottom: 0 }}
              />
            </div>
            <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
              <button
                onClick={async () => {
                  if (!newInventory.project || !newInventory.date) return;
                  const res = await fetch(API + '/inventory', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ...newInventory, createdBy: user.name }),
                  });
                  const inv = await res.json();
                  await refreshData();
                  setSelectedInventory(inv);
                  setShowForm(false);
                }}
                style={btnO}
              >
                <Check size={14} />
                Создать
              </button>
              <button onClick={() => setShowForm(false)} style={btnG}>
                <X size={14} />
                Отмена
              </button>
            </div>
          </div>
        )}

        {selectedInventory && (
          <div style={{ ...card, padding: '20px', marginBottom: '15px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
              <b style={{ color: C.text }}>{'Инвентаризация: ' + selectedInventory.project}</b>
              <div style={{ display: 'flex', gap: '6px' }}>
                <button
                  onClick={async () => {
                    const items = await fetch(API + '/inventory/' + selectedInventory.id + '/items').then(r => r.json());
                    showPreview(buildInventoryDoc(selectedInventory, items), 'Акт инвентаризации');
                  }}
                  style={btnB}
                >
                  <Eye size={14} />
                  Акт
                </button>
                <button onClick={() => setSelectedInventory(null)} style={btnG}>
                  <X size={14} />
                  Закрыть
                </button>
              </div>
            </div>
            <p style={{ color: C.textSec, fontSize: '13px', marginBottom: '15px' }}>Введите фактические остатки:</p>
            {materials
              .filter(material => material.project === selectedInventory.project)
              .map(material => (
                <div
                  key={material.id}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '3fr 1fr 1fr',
                    gap: '8px',
                    alignItems: 'center',
                    marginBottom: '8px',
                    padding: '10px',
                    backgroundColor: C.bg,
                    borderRadius: '8px',
                    border: '1.5px solid ' + C.border,
                  }}
                >
                  <span style={{ fontSize: '13px', color: C.text }}>{material.name}</span>
                  <span style={{ fontSize: '12px', color: C.textSec }}>{'По учёту: ' + material.quantity + ' ' + material.unit}</span>
                  <input
                    placeholder="Факт"
                    type="number"
                    step="any"
                    inputMode="decimal"
                    defaultValue={material.quantity}
                    onBlur={async e => {
                      const actual = Number(e.target.value);
                      await fetch(API + '/inventory/' + selectedInventory.id + '/items', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                          materialName: material.name,
                          unit: material.unit,
                          expected: material.quantity,
                          actual,
                          difference: actual - material.quantity,
                          price: material.price,
                        }),
                      });
                    }}
                    style={{ ...inp, marginBottom: 0, fontSize: '12px' }}
                  />
                </div>
              ))}
          </div>
        )}

        {inventory.map(inv => (
          <div
            key={inv.id}
            style={{ ...card, padding: '14px', marginBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
          >
            <div>
              <b style={{ color: C.text, fontSize: '13px' }}>{'Инвентаризация: ' + inv.project}</b>
              <p style={{ color: C.textSec, margin: '2px 0', fontSize: '12px' }}>{inv.date}</p>
            </div>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button onClick={() => setSelectedInventory(inv)} style={btnG}>
                <Edit2 size={13} />
                Открыть
              </button>
              <button
                onClick={async () => {
                  const items = await fetch(API + '/inventory/' + inv.id + '/items').then(r => r.json());
                  showPreview(buildInventoryDoc(inv, items), 'Акт инвентаризации');
                }}
                style={btnB}
              >
                <Eye size={13} />
                Акт
              </button>
            </div>
          </div>
        ))}
      </div>
    );
  }

  return null;
}

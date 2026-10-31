import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import WarehousePage from './WarehousePage';
import { navigationHref } from '../features/navigation/navigationTarget';
jest.mock('./WarehouseTabsNav',()=>()=>null);
jest.mock('./WarehouseObjectsPanel',()=>props=><div data-testid="material">{props.focusedMaterial?.id}</div>);
jest.mock('./WarehouseOperationsPanel',()=>props=><div data-testid="tool">{props.focusedToolId}</div>);
jest.mock('../features/tool-custody/ToolCustodyPanel',()=>({toolCustodyEnabled:()=>false}));
jest.mock('../features/inventory-reconciliation/InventoryWorkspace',()=>({__esModule:true,default:()=>null,inventoryReconciliationEnabled:()=>false}));
const props={warehouseTab:'objects',C:{},projects:[],materials:[{id:41,name:'Кабель',companyId:3,project:'Объект'},{id:42,name:'Кабель',companyId:3,project:'Объект'}],tools:[{id:51,name:'Дрель',companyId:3}],companyContext:{mode:'company',selectedCompanyId:3},user:{role:'директор'},setWarehouseTab:jest.fn(),setSelectedWarehouseProject:jest.fn(),setToolsTab:jest.fn()};
beforeEach(()=>jest.clearAllMocks());
afterEach(()=>window.history.replaceState({},'','/app'));
test('material search opens exact ID despite equal names and restores normal list on clear',()=>{
  window.history.replaceState({},'',navigationHref({type:'material',id:42,companyId:3}));
  render(<WarehousePage {...props}/>);
  expect(screen.getByTestId('material')).toHaveTextContent('42');
  expect(props.setSelectedWarehouseProject).toHaveBeenCalledWith('Объект');
  fireEvent.click(screen.getByText('Показать все позиции'));
  expect(screen.getByTestId('material')).toBeEmptyDOMElement();
});
test('tool target selects tool tab and exact item',()=>{
  window.history.replaceState({},'',navigationHref({type:'tool',id:51,companyId:3}));
  render(<WarehousePage {...props} warehouseTab="tools"/>);
  expect(props.setWarehouseTab).toHaveBeenCalledWith('tools');
  expect(screen.getByTestId('tool')).toHaveTextContent('51');
});
test.each([[42,4],[99,3]])('wrong company or missing ID never falls back to a same-name item', (id,companyId)=>{
  window.history.replaceState({},'',navigationHref({type:'material',id,companyId}));
  render(<WarehousePage {...props}/>);
  expect(screen.queryByTestId('material')).not.toBeInTheDocument();
  expect(props.setSelectedWarehouseProject).not.toHaveBeenCalled();
  expect(screen.getByRole('status')).toBeInTheDocument();
});
test('switching company hides previously selected stock before new data loads',()=>{
  window.history.replaceState({},'',navigationHref({type:'material',id:42,companyId:3}));
  const view=render(<WarehousePage {...props}/>);
  view.rerender(<WarehousePage {...props} companyContext={{mode:'company',selectedCompanyId:4}}/>);
  expect(screen.queryByTestId('material')).not.toBeInTheDocument();
});

test('warehouse link with wrong object cannot silently change the return context',()=>{
  window.history.replaceState({},'',navigationHref({type:'material',id:42,companyId:3,projectId:8}));
  render(<WarehousePage {...props} projects={[{id:8,companyId:3,name:'Другой объект'}]}/>);
  expect(screen.queryByTestId('material')).not.toBeInTheDocument();
  expect(props.setSelectedWarehouseProject).not.toHaveBeenCalled();
});

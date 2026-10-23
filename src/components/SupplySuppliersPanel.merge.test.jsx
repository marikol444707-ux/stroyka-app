import React from 'react';
import {fireEvent, render, screen} from '@testing-library/react';
import SupplySuppliersPanel from './SupplySuppliersPanel';

jest.mock('./DocumentRecognitionPanel', () => () => null);
jest.mock('../features/supply/SupplierCardDetails', () => ({supplier}) => <div data-testid="opened-supplier">{supplier.id}:{supplier.companyId}</div>);

const primary = {id:12,companyId:2,companySupplierLinkId:21,name:'Основной',phone:'',category:'Прочее',relationshipVersion:2};
const source = {id:4,companyId:2,companySupplierLinkId:20,name:'Из накладной',phone:'',category:'Прочее',relationshipVersion:1};
const merged = [source, primary].map(row=>({...row,canonicalSupplierId:12,relatedSupplierIds:[4,12]}));
const props = () => ({C:{},card:{},inp:{},btnO:{},btnG:{},btnB:{},btnGr:{},btnR:{},
  user:{role:'директор'},companyId:2,suppliers:[source,primary],supplierCategories:['Прочее'],
  showForm:false,setShowForm:jest.fn(),editingItem:null,setEditingItem:jest.fn(),newSupplier:{},setNewSupplier:jest.fn(),
  saveSupplier:jest.fn(),deleteSupplier:jest.fn(),listSearch:'',setListSearch:jest.fn(),matchSearch:()=>true,
  setSupplierInviteForm:jest.fn(),setGeneratedInviteLink:jest.fn(),setShowSupplierInviteModal:jest.fn(),loadAll:jest.fn()});

test('merged catalog has one canonical row, both original document histories and a single total', () => {
  const invoices=[{id:41,supplierId:4,companyId:2,number:'OLD',date:'2026-10-01',totalWithVat:100},
    {id:42,supplierId:12,companyId:2,number:'NEW',date:'2026-10-02',totalWithVat:200},
    {id:43,supplierId:99,companyId:2,supplierName:'Основной',number:'UNRELATED',totalWithVat:500},
    {id:44,supplierId:4,companyId:3,number:'FOREIGN',totalWithVat:900}];
  const before=JSON.stringify(invoices);
  render(<SupplySuppliersPanel {...props()} suppliers={merged} invoices={invoices}/>);
  expect(screen.getByRole('button',{name:'Все · 1'})).toBeInTheDocument();
  expect(screen.getAllByRole('button',{name:'Редактировать поставщика'})).toHaveLength(1);
  expect(screen.getByText('300 ₽')).toBeInTheDocument();
  expect(screen.getByText('объединено карточек: 2')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Основной'));
  expect(screen.getByTestId('opened-supplier')).toHaveTextContent('12:2');
  expect(screen.getByText('Складская накладная · № OLD')).toBeInTheDocument();
  expect(screen.getByText('Складская накладная · № NEW')).toBeInTheDocument();
  expect(screen.queryByText(/№ UNRELATED|№ FOREIGN/)).not.toBeInTheDocument();
  expect(JSON.stringify(invoices)).toBe(before);
});

test('refresh after merge redirects an open source to canonical card and actions use canonical ID', () => {
  const p=props();
  const {rerender}=render(<SupplySuppliersPanel {...p}/>);
  fireEvent.click(screen.getByText('Из накладной'));
  expect(screen.getByTestId('opened-supplier')).toHaveTextContent('4:2');
  rerender(<SupplySuppliersPanel {...p} suppliers={merged}/>);
  expect(screen.getByTestId('opened-supplier')).toHaveTextContent('12:2');
  fireEvent.click(screen.getByRole('button',{name:'Редактировать поставщика'}));
  expect(p.setEditingItem.mock.calls[0][0].id).toBe(12);
  expect(p.setEditingItem.mock.calls[0][0].relationshipVersion).toBe(2);
});

test('company change closes merge review and opened card even when supplier ID is reused', () => {
  const p=props();
  const {rerender}=render(<SupplySuppliersPanel {...p} suppliers={[primary]}/>);
  fireEvent.click(screen.getByText('Основной'));
  fireEvent.click(screen.getByRole('button',{name:'Объединить'}));
  expect(screen.getByRole('dialog')).toBeInTheDocument();
  rerender(<SupplySuppliersPanel {...p} companyId={3} suppliers={[{...primary,companyId:3}]}/>);
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.queryByTestId('opened-supplier')).not.toBeInTheDocument();
});

test('new company selection hides stale old-company catalog while refresh is pending', () => {
  const p=props();
  const {rerender}=render(<SupplySuppliersPanel {...p}/>);
  rerender(<SupplySuppliersPanel {...p} companyId={3}/>);
  expect(screen.queryByText('Основной')).not.toBeInTheDocument();
  expect(screen.queryByText('Из накладной')).not.toBeInTheDocument();
});

test('stale company-scoped link focus cannot open same supplier in the next company', () => {
  render(<SupplySuppliersPanel {...props()} companyId={3} suppliers={[{...primary,companyId:3}]}
    supplierLinkFocus={{supplierId:12,companyId:2}}/>);
  expect(screen.queryByTestId('opened-supplier')).not.toBeInTheDocument();
});

import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import WarehouseOperationsPanel from './WarehouseOperationsPanel';

test('mobile search finds a material beyond the first forty positions', () => {
  const warehouseMain = Array.from({length: 45}, (_, index) => ({
    id: index + 1, name: index === 44 ? 'Кабель ВВГнг' : `Материал ${index + 1}`, quantity: 10, unit: 'м',
  }));
  render(<WarehouseOperationsPanel warehouseTab="move" isMobile C={{}} card={{}} inp={{}}
    projects={[]} visibleActiveProjects={value => value} warehouseMain={warehouseMain} materials={[]}
    newMovement={{fromLocation:'Основной склад',toLocation:'',notes:'',selectedMaterials:[]}}
    warehouseMovements={[]} warehouseInvoices={[]} />);

  fireEvent.change(screen.getByRole('searchbox', {name:'Поиск материала'}), {target:{value:'ВВГнг'}});

  expect(screen.getByText('Кабель ВВГнг')).toBeInTheDocument();
  expect(screen.queryByText('Материал 1')).not.toBeInTheDocument();
});

test.each([false, true])('movement history includes source and unlinked states, compact=%s', isMobile => {
  render(<WarehouseOperationsPanel warehouseTab="move" isMobile={isMobile} C={{}} card={{}} inp={{}}
    projects={[]} visibleActiveProjects={value => value} warehouseMain={[]} materials={[]}
    newMovement={{ fromLocation: 'Основной склад', toLocation: '', notes: '', selectedMaterials: [] }}
    warehouseInvoices={[{ id: 5, companyId: 2, number: 'НК-5', supplierName: 'Без кабинета', items: [{ name: 'Кабель', invoiceLineIndex: 0 }] }]}
    warehouseMovements={[
      { id: 1, companyId: 2, sourceInvoiceId: 5, sourceInvoiceLineIndex: 0, materialName: 'Кабель', fromLocation: 'Основной склад', toLocation: 'Школа', quantity: 10, unit: 'м' },
      { id: 2, companyId: 2, materialName: 'Краска', fromLocation: 'Основной склад', toLocation: 'Школа', quantity: 3, unit: 'л' },
    ]} />);
  expect(screen.getByText(/НК-5/)).toHaveTextContent('строка 1');
  expect(screen.getByText('Без кабинета')).toBeInTheDocument();
  expect(screen.getByText('Источник поступления не указан')).toBeInTheDocument();
  expect(screen.getByText(/не создаёт новый долг/)).toBeInTheDocument();
});

test('selector excludes unidentified and duplicate indices and sends original visible line index', () => {
  const material = { id: 1, name: 'Кабель', unit: 'м', quantity: 10 };
  const state = { fromLocation: 'Основной склад', toLocation: '', notes: '', selectedMaterials: [{ ...material, quantity: '1' }] };
  const setNewMovement = jest.fn();
  const indices = [2, undefined, null, -1, 1.5, '0', true, Number.MAX_SAFE_INTEGER + 1, 4, 4];
  render(<WarehouseOperationsPanel warehouseTab="move" C={{}} card={{}} inp={{}}
    projects={[]} visibleActiveProjects={v => v} warehouseMain={[material]} materials={[]}
    newMovement={state} setNewMovement={setNewMovement} warehouseMovements={[]}
    warehouseInvoices={[{ id: 5, companyId: 2, location: 'Основной склад', items: indices.map(invoiceLineIndex => ({ ...material, invoiceLineIndex })) }]} />);
  const option = screen.getByRole('option', { name: /Накладная/ });
  expect(option).toHaveValue('5:2');
  fireEvent.change(option.parentElement, { target: { value: '5:2' } });
  expect(setNewMovement.mock.calls[0][0](state).selectedMaterials[0]).toMatchObject({ invoiceId: 5, invoiceLineIndex: 2 });
});

test('unidentified source offers no selector and explains why', () => {
  const material = { id: 1, name: 'Кабель', unit: 'м', quantity: 10 };
  render(<WarehouseOperationsPanel warehouseTab="move" C={{}} card={{}} inp={{}}
    projects={[]} visibleActiveProjects={v => v} warehouseMain={[material]} materials={[]}
    newMovement={{ fromLocation: 'Основной склад', selectedMaterials: [{ ...material, quantity: '1' }] }} warehouseMovements={[]}
    warehouseInvoices={[{ id: 5, location: 'Основной склад', items: [material] }]} />);
  expect(screen.queryByRole('option', { name: /Накладная/ })).not.toBeInTheDocument();
  expect(screen.getByText(/Накладная не найдена/)).toBeInTheDocument();
});

test('a rejected receipt is not offered as a source even when matching good stock exists', () => {
  const material = { id:1,name:'Кабель',unit:'м',quantity:10 };
  render(<WarehouseOperationsPanel warehouseTab="move" C={{}} card={{}} inp={{}}
    projects={[]} visibleActiveProjects={v=>v} warehouseMain={[material]} materials={[]}
    newMovement={{fromLocation:'Основной склад',selectedMaterials:[{...material,quantity:'1'}]}}
    warehouseMovements={[]} warehouseInvoices={[{id:5,location:'Основной склад',receiptAccepted:false,
      items:[{...material,invoiceLineIndex:0}]}]} />);
  expect(screen.queryByRole('option',{name:/Накладная/})).not.toBeInTheDocument();
});

test('does not open M-11 preview when the movement was rejected', async () => {
  const material = {id:1,name:'Кабель',unit:'м',quantity:10};
  const applyWarehouseMovement = jest.fn(async () => ({success:false}));
  const showPreview = jest.fn();
  render(<WarehouseOperationsPanel warehouseTab="move" C={{}} card={{}} inp={{}}
    projects={[]} visibleActiveProjects={v=>v} warehouseMain={[material]} materials={[]}
    newMovement={{fromLocation:'Основной склад',toLocation:'Объект 1',notes:'',selectedMaterials:[{...material,quantity:'1'}]}}
    warehouseMovements={[]} warehouseInvoices={[]} applyWarehouseMovement={applyWarehouseMovement}
    buildMovementDoc={jest.fn()} showPreview={showPreview} />);

  fireEvent.click(screen.getByRole('button',{name:'Переместить и распечатать'}));

  await waitFor(() => expect(applyWarehouseMovement).toHaveBeenCalledTimes(1));
  expect(showPreview).not.toHaveBeenCalled();
});

test('opens M-11 preview after the server confirms the movement', async () => {
  const material = {id:1,name:'Кабель',unit:'м',quantity:10};
  const draft = {fromLocation:'Основной склад',toLocation:'Объект 1',notes:'',selectedMaterials:[{...material,quantity:'1'}]};
  const document = '<p>М-11</p>';
  const applyWarehouseMovement = jest.fn(async () => ({success:true,moved:1}));
  const buildMovementDoc = jest.fn(() => document);
  const showPreview = jest.fn();
  render(<WarehouseOperationsPanel warehouseTab="move" C={{}} card={{}} inp={{}}
    projects={[]} visibleActiveProjects={v=>v} warehouseMain={[material]} materials={[]}
    newMovement={draft} warehouseMovements={[]} warehouseInvoices={[]}
    applyWarehouseMovement={applyWarehouseMovement} buildMovementDoc={buildMovementDoc} showPreview={showPreview} />);

  fireEvent.click(screen.getByRole('button',{name:'Переместить и распечатать'}));

  await waitFor(() => expect(showPreview).toHaveBeenCalledWith(document,'Накладная М-11'));
  expect(buildMovementDoc).toHaveBeenCalledWith(draft,draft.selectedMaterials);
});

test('shows the missing quantity before submit and prevents a repeated movement while sending', async () => {
  const material = {id:1,name:'Кабель',unit:'м',quantity:10};
  const draft = {fromLocation:'Основной склад',toLocation:'Объект 1',notes:'',selectedMaterials:[{...material,quantity:''}]};
  const applyWarehouseMovement = jest.fn(() => new Promise(() => {}));
  const {rerender} = render(<WarehouseOperationsPanel warehouseTab="move" C={{}} card={{}} inp={{}}
    projects={[]} visibleActiveProjects={v=>v} warehouseMain={[material]} materials={[]}
    newMovement={draft} warehouseMovements={[]} warehouseInvoices={[]}
    applyWarehouseMovement={applyWarehouseMovement} />);

  expect(screen.getByText('Укажите количество для 1 позиции.')).toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Переместить 1 позицию'})).toBeDisabled();
  rerender(<WarehouseOperationsPanel warehouseTab="move" C={{}} card={{}} inp={{}}
    projects={[]} visibleActiveProjects={v=>v} warehouseMain={[material]} materials={[]}
    newMovement={{...draft,selectedMaterials:[{...material,quantity:'2'}]}} warehouseMovements={[]}
    warehouseInvoices={[]} applyWarehouseMovement={applyWarehouseMovement} />);

  fireEvent.click(screen.getByRole('button',{name:'Переместить 1 позицию'}));
  expect(screen.getByRole('button',{name:'Перемещаем…'})).toBeDisabled();
  expect(screen.getByRole('button',{name:'Переместить и распечатать'})).toBeDisabled();
  expect(applyWarehouseMovement).toHaveBeenCalledTimes(1);
});

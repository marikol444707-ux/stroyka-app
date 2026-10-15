import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import ProjectBrigadeWorkEntryPanel from './ProjectBrigadeWorkEntryPanel';


test('does not offer the legacy estimate import through the manual item endpoint', () => {
  render(
    <ProjectBrigadeWorkEntryPanel
      project={{id: 19, name: 'Лицей'}}
      selectedBrigadeContract={{id: 7, workPackage: 'Отделка'}}
      estimatesList={[{
        id: 9,
        name: 'Смета',
        projectId: 19,
        workPackage: 'Отделка',
        sections: [{name: 'Стены', items: [{name: 'Штукатурка'}]}],
      }]}
      newBrigadeItem={{
        name: '', unit: 'м2', quantity: '', priceSmeta: '', priceBrigade: '', workPackage: 'Отделка',
      }}
      setNewBrigadeItem={jest.fn()}
      setBrigadeContractItems={jest.fn()}
      UNITS={['м2']}
      C={{text: '#111', textSec: '#666'}}
      card={{}}
      inp={{}}
      btnG={{}}
      btnO={{}}
      showLeadership
    />,
  );

  expect(screen.queryByText('Загрузить из сметы:')).not.toBeInTheDocument();
  expect(screen.getByText('Добавить работу вручную')).toBeInTheDocument();
});

test('manual fields open in a dialog and failed saving keeps the draft without adding a row', async () => {
  const originalFetch = global.fetch;
  global.fetch = jest.fn().mockResolvedValue({ok:false,json:async()=>({detail:'Нет доступа'})});
  const setItems = jest.fn();
  const reset = jest.fn();
  try {
    render(<ProjectBrigadeWorkEntryPanel selectedBrigadeContract={{id:7,workPackage:'Отделка'}}
      newBrigadeItem={{name:'Штукатурка',unit:'м2',quantity:'5',priceSmeta:'100',priceBrigade:'60'}}
      setNewBrigadeItem={reset} setBrigadeContractItems={setItems} UNITS={['м2']}
      C={{text:'#111'}} card={{}} inp={{}} btnO={{}} showLeadership/>);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    screen.getByRole('button',{name:'Добавить работу вручную'}).focus();
    fireEvent.click(screen.getByRole('button',{name:'Добавить работу вручную'}));
    expect(screen.getByRole('dialog',{name:'Новая работа'})).toBeInTheDocument();
    expect(screen.getByLabelText('Наименование работы')).toHaveFocus();
    fireEvent.submit(screen.getByRole('dialog'));
    await waitFor(()=>expect(screen.getByRole('alert')).toHaveTextContent('Нет доступа'));
    expect(setItems).not.toHaveBeenCalled(); expect(reset).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Объём')).toHaveValue(5);
    fireEvent.keyDown(screen.getByRole('dialog'),{key:'Escape'});
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByRole('button',{name:'Добавить работу вручную'})).toHaveFocus();
  } finally { global.fetch=originalFetch; }
});

test('repeated submit while saving sends one request and closes only on success', async () => {
  const originalFetch=global.fetch;
  let finish;
  global.fetch=jest.fn(()=>new Promise(resolve=>{finish=resolve;}));
  const setItems=jest.fn(), reset=jest.fn();
  try {
    render(<ProjectBrigadeWorkEntryPanel selectedBrigadeContract={{id:7,workPackage:'Отделка'}}
      newBrigadeItem={{name:'Штукатурка',unit:'м2',quantity:'5',priceSmeta:'100',priceBrigade:'60'}}
      setNewBrigadeItem={reset} setBrigadeContractItems={setItems} UNITS={['м2']}
      C={{text:'#111'}} card={{}} inp={{}} btnO={{}} showLeadership/>);
    fireEvent.click(screen.getByRole('button',{name:'Добавить работу вручную'}));
    fireEvent.submit(screen.getByRole('dialog')); fireEvent.submit(screen.getByRole('dialog'));
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button',{name:'Сохраняем…'})).toBeDisabled();
    finish({ok:true,json:async()=>({id:91})});
    await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(setItems).toHaveBeenCalledTimes(1); expect(reset).toHaveBeenCalledTimes(1);
  } finally {global.fetch=originalFetch;}
});

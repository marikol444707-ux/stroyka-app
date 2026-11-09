import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';

import AccountablePaymentModal from './AccountablePaymentModal';
import { createAccountablePaymentForm } from '../features/payments/paymentInitialForms';


function Harness({ close=jest.fn(), load=jest.fn(), visible=true }={}) {
  const [form, setForm] = React.useState(createAccountablePaymentForm());
  return (
    <AccountablePaymentModal
      showAccountableForm={visible}
      setShowAccountableForm={close}
      C={{text: '#111', textSec: '#666'}}
      card={{}}
      inp={{}}
      btnO={{}}
      btnG={{}}
      projects={[{id: 19, name: 'Лицей'}]}
      users={[{id: 999, name: 'Устаревший пользователь', role: 'мастер'}]}
      staff={[{id: 23, name: 'Точный сотрудник', role: 'мастер'}]}
      newAccountable={form}
      setNewAccountable={setForm}
      API=""
      user={{id: 8, name: 'Клиентская подмена'}}
      loadAll={load}
    />
  );
}


describe('AccountablePaymentModal ownership payload', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({ok: true, json: async () => ({ok:true,id:7})});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('submits exact project and staff IDs instead of client-authored names', async () => {
    render(<Harness />);
    const selects = screen.getAllByRole('combobox');
    fireEvent.change(selects[1], {target: {value: '19'}});
    fireEvent.change(selects[2], {target: {value: '23'}});
    fireEvent.change(screen.getByPlaceholderText('Сумма *'), {target: {value: '5000'}});
    fireEvent.click(screen.getByRole('button', {name: /Выдать/}));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    const [, request] = global.fetch.mock.calls[0];
    expect(JSON.parse(request.body)).toEqual(expect.objectContaining({
      projectId: 19,
      givenToId: 23,
      amount: 5000,
      paymentKind: 'expense',
    }));
    expect(request.body).not.toContain('Устаревший пользователь');
    expect(request.body).not.toContain('Клиентская подмена');
  });

  it('preserves the draft and does not close or refresh on server refusal', async()=>{
    const close=jest.fn(),load=jest.fn();
    global.fetch.mockResolvedValue({ok:false,status:409,json:async()=>({detail:'Выберите тип выдачи'})});
    render(<Harness close={close} load={load} />);
    const selects=screen.getAllByRole('combobox');
    fireEvent.change(selects[1],{target:{value:'19'}});fireEvent.change(selects[2],{target:{value:'23'}});
    fireEvent.change(screen.getByPlaceholderText('Сумма *'),{target:{value:'5000'}});
    fireEvent.click(screen.getByRole('button',{name:/Выдать/}));
    await screen.findByRole('alert');
    expect(screen.getByPlaceholderText('Сумма *')).toHaveValue(5000);
    expect(close).not.toHaveBeenCalled();expect(load).not.toHaveBeenCalled();
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });
});


test('late issue response cannot close a reopened form',async()=>{
 let finish;global.fetch=jest.fn().mockReturnValue(new Promise(resolve=>{finish=resolve;}));
 const close=jest.fn(),load=jest.fn();const {rerender}=render(<Harness close={close} load={load}/>);
 const selects=screen.getAllByRole('combobox');
 fireEvent.change(selects[1],{target:{value:'19'}});fireEvent.change(selects[2],{target:{value:'23'}});
 fireEvent.change(screen.getByPlaceholderText('Сумма *'),{target:{value:'5000'}});
 fireEvent.click(screen.getByRole('button',{name:/Выдать/}));
 rerender(<Harness close={close} load={load} visible={false}/>);
 rerender(<Harness close={close} load={load}/>);
 fireEvent.change(screen.getByPlaceholderText('Сумма *'),{target:{value:'7000'}});
 await act(async()=>finish({ok:true,json:async()=>({ok:true,id:9})}));
 expect(screen.getByPlaceholderText('Сумма *')).toHaveValue(7000);
 expect(close).not.toHaveBeenCalled();expect(load).not.toHaveBeenCalled();
});

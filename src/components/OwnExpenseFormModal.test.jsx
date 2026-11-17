import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';

import OwnExpenseFormModal from './OwnExpenseFormModal';
import { createOwnExpenseForm } from '../features/payments/paymentInitialForms';


function Harness({setShowOwnExpenseForm = jest.fn(), loadAll = jest.fn(), notify = jest.fn(), appendPhotos, fileSrc = value => value}) {
  const [form, setForm] = React.useState(createOwnExpenseForm());
  return (
    <OwnExpenseFormModal
      showOwnExpenseForm
      setShowOwnExpenseForm={setShowOwnExpenseForm}
      C={{text: '#111', textSec: '#666', textMuted: '#888', border: '#ddd', bg: '#fff', accent: '#f60'}}
      card={{}}
      inp={{}}
      btnO={{}}
      btnG={{}}
      projectOptions={[{id: 41, name: 'Объект'}]}
      expenseCategories={[{id: 'other', label: 'Прочее'}]}
      newOwnExpense={form}
      setNewOwnExpense={setForm}
      API=""
      user={{id: 999, name: 'Клиентская подмена'}}
      loadAll={loadAll}
      notify={notify}
      appendPhotos={appendPhotos}
      fileSrc={fileSrc}
    />
  );
}


describe('OwnExpenseFormModal ownership payload', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({ok: true});
    window.alert = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('submits an exact project ID and no client-authored employee identity', async () => {
    render(<Harness />);
    fireEvent.change(screen.getAllByRole('combobox')[0], {target: {value: '41'}});
    fireEvent.change(screen.getByPlaceholderText('За что потрачено *'), {
      target: {value: 'Бензин'},
    });
    fireEvent.change(screen.getByPlaceholderText('Сумма (₽) *'), {
      target: {value: '500'},
    });
    fireEvent.click(screen.getByRole('button', {name: /Отправить/}));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    const [, request] = global.fetch.mock.calls[0];
    const body = JSON.parse(request.body);
    expect(body).toEqual(expect.objectContaining({projectId: 41, amount: 500}));
    expect(body).not.toHaveProperty('projectName');
    expect(body).not.toHaveProperty('employeeId');
    expect(body).not.toHaveProperty('employeeName');
    expect(request.body).not.toContain('Клиентская подмена');
  });

  it('keeps the form open and shows the backend detail when creation is rejected', async () => {
    const setShowOwnExpenseForm = jest.fn();
    const loadAll = jest.fn();
    const notify = jest.fn();
    global.fetch.mockResolvedValue({
      ok: false,
      status: 409,
      json: jest.fn().mockResolvedValue({
        detail: 'Аккаунт не связан с карточкой сотрудника',
      }),
    });

    render(
      <Harness
        setShowOwnExpenseForm={setShowOwnExpenseForm}
        loadAll={loadAll}
        notify={notify}
      />
    );
    fireEvent.change(screen.getByPlaceholderText('За что потрачено *'), {
      target: {value: 'Бензин'},
    });
    fireEvent.change(screen.getByPlaceholderText('Сумма (₽) *'), {
      target: {value: '500'},
    });
    fireEvent.click(screen.getByRole('button', {name: /Отправить/}));

    await waitFor(() => expect(window.alert).toHaveBeenCalledWith(
      'Аккаунт не связан с карточкой сотрудника'
    ));
    expect(setShowOwnExpenseForm).not.toHaveBeenCalled();
    expect(loadAll).not.toHaveBeenCalled();
    expect(notify).not.toHaveBeenCalled();
    expect(screen.getByPlaceholderText('За что потрачено *')).toHaveValue('Бензин');
  });
});

describe('OwnExpenseFormModal receipt previews and pending submission', () => {
  const originalFetch = global.fetch;
  const originalAlert = window.alert;
  const originalCreateObjectURL = URL.createObjectURL;
  const originalRevokeObjectURL = URL.revokeObjectURL;

  beforeEach(() => {
    global.fetch = jest.fn();
    window.alert = jest.fn();
    URL.createObjectURL = jest.fn().mockReturnValue('blob:expense-receipt');
    URL.revokeObjectURL = jest.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    window.alert = originalAlert;
    if (originalCreateObjectURL) URL.createObjectURL = originalCreateObjectURL;
    else delete URL.createObjectURL;
    if (originalRevokeObjectURL) URL.revokeObjectURL = originalRevokeObjectURL;
    else delete URL.revokeObjectURL;
  });

  it('loads an uploaded tenant receipt with authenticated blob fetch before rendering its preview', async () => {
    const receiptUrl = '/tenant-files/91/content';
    const blob = new Blob(['receipt'], {type: 'image/png'});
    global.fetch.mockResolvedValue({ok: true, blob: async () => blob});
    const appendPhotos = jest.fn().mockResolvedValue(receiptUrl);
    const {container, unmount} = render(
      <Harness appendPhotos={appendPhotos} fileSrc={value => 'https://api.test' + value}/>,
    );
    const file = new File(['receipt'], 'receipt.png', {type: 'image/png'});
    fireEvent.change(container.querySelector('input[type="file"][multiple]'), {target: {files: [file]}});

    await waitFor(() => expect(appendPhotos).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      'https://api.test' + receiptUrl,
      expect.objectContaining({credentials: 'include', cache: 'no-store'}),
    ));
    await waitFor(() => expect(container.querySelector('img')).toHaveAttribute('src', 'blob:expense-receipt'));
    expect(URL.createObjectURL).toHaveBeenCalledWith(blob);
    expect(global.fetch.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
    unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:expense-receipt');
  });

  it('disables pending submission and does not create two expenses when send is clicked twice', async () => {
    let resolvePost;
    global.fetch.mockReturnValue(new Promise(resolve => { resolvePost = resolve; }));
    const notify = jest.fn();
    const loadAll = jest.fn().mockResolvedValue(undefined);
    const setShowOwnExpenseForm = jest.fn();
    render(<Harness notify={notify} loadAll={loadAll} setShowOwnExpenseForm={setShowOwnExpenseForm}/>);
    fireEvent.change(screen.getByPlaceholderText('За что потрачено *'), {target: {value: 'Бензин'}});
    fireEvent.change(screen.getByPlaceholderText('Сумма (₽) *'), {target: {value: '500'}});
    const submit = screen.getByRole('button', {name: /Отправить/});
    fireEvent.click(submit);
    const disabledDuringRequest = submit.disabled;
    fireEvent.click(submit);
    const requestsDuringPending = global.fetch.mock.calls.length;
    expect(notify).not.toHaveBeenCalled();
    expect(loadAll).not.toHaveBeenCalled();
    expect(setShowOwnExpenseForm).not.toHaveBeenCalled();
    await act(async () => { resolvePost({ok: true}); });

    expect({requestsDuringPending, disabledDuringRequest}).toEqual({
      requestsDuringPending: 1, disabledDuringRequest: true,
    });
    expect(notify).toHaveBeenCalledTimes(1);
    expect(loadAll).toHaveBeenCalledTimes(1);
    expect(setShowOwnExpenseForm).toHaveBeenCalledTimes(1);
  });
});

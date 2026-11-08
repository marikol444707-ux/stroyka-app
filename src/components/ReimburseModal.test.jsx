import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';

import ReimburseModal from './ReimburseModal';


describe('ReimburseModal ownership payload', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({ok: true});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('submits only the status and lets the server derive the approver', async () => {
    render(
      <ReimburseModal
        showReimburseModal
        setShowReimburseModal={jest.fn()}
        C={{text:'#111',textSec:'#666',textMuted:'#888',warning:'#a60',warningLight:'#fff',warningBorder:'#ddd',accent:'#f60',bg:'#fff',bgWhite:'#fff',border:'#ddd'}}
        card={{}}
        btnG={{}}
        btnO={{}}
        btnR={{}}
        ownExpenses={[{id:9,status:'Ожидает',employeeId:23,employeeName:'Мастер',description:'Бензин',amount:500,projectName:''}]}
        users={[]}
        staff={[]}
        roleLabels={{}}
        expenseCategories={[]}
        fileSrc={value => value}
        setShowPhotoModal={jest.fn()}
        API=""
        user={{name:'Клиентская подмена'}}
        loadAll={jest.fn()}
      />
    );
    fireEvent.click(screen.getByRole('button', {name:'✅'}));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    const [, request] = global.fetch.mock.calls[0];
    expect(JSON.parse(request.body)).toEqual({status:'Возмещено'});
    expect(request.body).not.toContain('Клиентская подмена');
  });
});

function renderProjectExpense(overrides = {}) {
  const loadAll = jest.fn().mockResolvedValue(undefined);
  const setShowPhotoModal = jest.fn();
  const setShowReimburseModal = jest.fn();
  const result = render(<ReimburseModal
    showReimburseModal setShowReimburseModal={setShowReimburseModal}
    C={{}} users={[]} staff={[]} roleLabels={{}} expenseCategories={[]}
    ownExpenses={[{
      id: 9, status: 'Ожидает', employeeId: 23, employeeName: 'Мастер',
      description: 'Бензин', amount: 500, projectId: 41, projectName: 'Объект', ...overrides,
    }]}
    fileSrc={value => 'https://api.test' + value} setShowPhotoModal={setShowPhotoModal}
    API="/api" user={{name: 'Бухгалтер'}} loadAll={loadAll}
  />);
  return {...result, loadAll, setShowPhotoModal, setShowReimburseModal};
}

describe('ReimburseModal reimbursement and receipt regressions', () => {
  const originalFetch = global.fetch;
  const originalCreateObjectURL = URL.createObjectURL;
  const originalRevokeObjectURL = URL.revokeObjectURL;

  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({ok: true, json: async () => ({ok: true})});
    URL.createObjectURL = jest.fn().mockReturnValueOnce('blob:receipt-one').mockReturnValueOnce('blob:receipt-two');
    URL.revokeObjectURL = jest.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    if (originalCreateObjectURL) URL.createObjectURL = originalCreateObjectURL;
    else delete URL.createObjectURL;
    if (originalRevokeObjectURL) URL.revokeObjectURL = originalRevokeObjectURL;
    else delete URL.revokeObjectURL;
  });

  it('reimburses a project expense with one PUT and leaves project payment creation to the server', async () => {
    const {loadAll} = renderProjectExpense();
    fireEvent.click(screen.getByRole('button', {name: '✅'}));
    await waitFor(() => expect(loadAll).toHaveBeenCalledTimes(1));
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith('/api/own-expenses/9', expect.objectContaining({
      method: 'PUT', body: JSON.stringify({status: 'Возмещено'}),
    }));
    expect(global.fetch.mock.calls.some(([url]) => url.includes('/project-payments'))).toBe(false);
  });

  it('shows the server message on HTTP 403 and does not refresh or create a payment', async () => {
    const message = 'Недостаточно прав для возмещения расхода';
    global.fetch.mockResolvedValue({ok: false, status: 403, json: async () => ({detail: message})});
    const {loadAll, setShowReimburseModal} = renderProjectExpense();
    fireEvent.click(screen.getByRole('button', {name: '✅'}));
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(loadAll).not.toHaveBeenCalled();
    expect(setShowReimburseModal).not.toHaveBeenCalled();
    expect(global.fetch.mock.calls.some(([url]) => url.includes('/project-payments'))).toBe(false);
    expect(screen.getByRole('button', {name: '✅'})).toBeEnabled();
  });

  it('blocks a second approval while its PUT is pending', async () => {
    let resolvePut;
    const pending = new Promise(resolve => { resolvePut = resolve; });
    global.fetch.mockImplementation((_url, options) => options?.method === 'PUT'
      ? pending : Promise.resolve({ok: true, json: async () => ({ok: true})}));
    const {loadAll} = renderProjectExpense();
    const approve = screen.getByRole('button', {name: '✅'});
    fireEvent.click(approve);
    const disabledWhilePending = approve.disabled;
    fireEvent.click(approve);
    const putCountWhilePending = global.fetch.mock.calls.filter(([, options]) => options.method === 'PUT').length;
    expect(loadAll).not.toHaveBeenCalled();
    await act(async () => { resolvePut({ok: true, json: async () => ({ok: true})}); });
    expect({disabledWhilePending, putCountWhilePending}).toEqual({disabledWhilePending: true, putCountWhilePending: 1});
    expect(loadAll).toHaveBeenCalledTimes(1);
  });

  it('loads each protected receipt with credentials and opens its blob preview', async () => {
    global.fetch.mockResolvedValue({ok: true, blob: async () => new Blob(['receipt'], {type: 'image/png'})});
    const {container, unmount, setShowPhotoModal} = renderProjectExpense({
      photoUrl: '/tenant-files/91/content, /tenant-files/92/content',
    });
    try {
      for (const id of [91, 92]) {
        await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
          `https://api.test/tenant-files/${id}/content`,
          expect.objectContaining({credentials: 'include', cache: 'no-store'}),
        ));
      }
      await waitFor(() => expect(Array.from(container.querySelectorAll('img')).map(img => img.getAttribute('src')))
        .toEqual(['blob:receipt-one', 'blob:receipt-two']));
      const images = container.querySelectorAll('img');
      fireEvent.click(images[0]);
      fireEvent.click(images[1]);
      expect(setShowPhotoModal.mock.calls).toEqual([['blob:receipt-one'], ['blob:receipt-two']]);
    } finally {
      unmount();
    }
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:receipt-one');
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:receipt-two');
  });
});

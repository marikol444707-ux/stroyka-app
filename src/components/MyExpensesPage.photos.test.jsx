import React from 'react';
import {fireEvent, render, screen, waitFor} from '@testing-library/react';

import MyExpensesPage from './MyExpensesPage';

function renderExpense(photoUrl) {
  const setShowPhotoModal = jest.fn();
  const result = render(<MyExpensesPage
    C={{}} EXPENSE_CATEGORIES={[{id: 'other', label: 'Прочее'}]}
    user={{id: 9, name: 'Мастер', role: 'мастер'}}
    ownExpenses={[{
      id: 31, employeeId: 9, employeeName: 'Мастер', category: 'other',
      description: 'Бензин', amount: 500, status: 'Ожидает', photoUrl,
    }]}
    fileSrc={value => 'https://api.test' + value}
    setShowPhotoModal={setShowPhotoModal}
  />);
  fireEvent.click(screen.getByRole('button', {name: /Мастер/}));
  return {...result, setShowPhotoModal};
}

describe('MyExpensesPage protected receipt photos', () => {
  const originalFetch = global.fetch;
  const originalCreateObjectURL = URL.createObjectURL;
  const originalRevokeObjectURL = URL.revokeObjectURL;

  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({ok: true, blob: async () => new Blob(['receipt'], {type: 'image/png'})});
    URL.createObjectURL = jest.fn()
      .mockReturnValueOnce('blob:receipt-one')
      .mockReturnValueOnce('blob:receipt-two');
    URL.revokeObjectURL = jest.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    if (originalCreateObjectURL) URL.createObjectURL = originalCreateObjectURL;
    else delete URL.createObjectURL;
    if (originalRevokeObjectURL) URL.revokeObjectURL = originalRevokeObjectURL;
    else delete URL.revokeObjectURL;
  });

  it('loads a tenant receipt with credentials and opens the resolved blob preview', async () => {
    const {container, unmount, setShowPhotoModal} = renderExpense('/tenant-files/91/content');
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      'https://api.test/tenant-files/91/content',
      expect.objectContaining({credentials: 'include', cache: 'no-store'}),
    ));
    await waitFor(() => expect(container.querySelector('img')).toHaveAttribute('src', 'blob:receipt-one'));
    fireEvent.click(container.querySelector('img'));
    expect(setShowPhotoModal).toHaveBeenCalledWith('blob:receipt-one');
    unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:receipt-one');
  });

  it('renders and opens each comma-separated receipt separately', async () => {
    const {container, unmount, setShowPhotoModal} = renderExpense('/tenant-files/91/content, /tenant-files/92/content');
    await waitFor(() => expect(container.querySelectorAll('img')).toHaveLength(2));
    for (const id of [91, 92]) {
      expect(global.fetch).toHaveBeenCalledWith(
        `https://api.test/tenant-files/${id}/content`,
        expect.objectContaining({credentials: 'include', cache: 'no-store'}),
      );
    }
    const images = Array.from(container.querySelectorAll('img'));
    expect(images.map(image => image.getAttribute('src'))).toEqual(['blob:receipt-one', 'blob:receipt-two']);
    fireEvent.click(images[0]);
    fireEvent.click(images[1]);
    expect(setShowPhotoModal.mock.calls).toEqual([['blob:receipt-one'], ['blob:receipt-two']]);
    expect(global.fetch.mock.calls.every(([url]) => !url.includes(','))).toBe(true);
    unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:receipt-one');
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:receipt-two');
  });
});

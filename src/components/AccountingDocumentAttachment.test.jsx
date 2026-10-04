import React from 'react';
import {render, screen, fireEvent, waitFor} from '@testing-library/react';
import AccountingDocumentAttachment from './AccountingDocumentAttachment';

const C = {border:'#ddd',bg:'#fff',text:'#111',textMuted:'#555'};
const originalFetch = global.fetch;
const originalCreate = URL.createObjectURL;
const originalRevoke = URL.revokeObjectURL;
beforeEach(() => {
  global.fetch = jest.fn();
  URL.createObjectURL = jest.fn(() => 'blob:accounting-file');
  URL.revokeObjectURL = jest.fn();
});
afterEach(() => {
  global.fetch = originalFetch;
  URL.createObjectURL = originalCreate;
  URL.revokeObjectURL = originalRevoke;
});

test('protected PDF downloads as a document instead of opening the photo modal', async () => {
  fetch.mockResolvedValue({ok:true,blob:async () => new Blob(['pdf'],{type:'application/pdf'})});
  const onPhoto = jest.fn();
  const view = render(<AccountingDocumentAttachment url="/tenant-files/31/content" C={C} onPhoto={onPhoto}/>);
  const link = await screen.findByRole('link', {name:'Скачать PDF'});
  expect(link).toHaveAttribute('href','blob:accounting-file');
  expect(link).toHaveAttribute('download','Накладная.pdf');
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
  expect(onPhoto).not.toHaveBeenCalled();
  expect(fetch).toHaveBeenCalledWith('/tenant-files/31/content',expect.objectContaining({credentials:'include'}));
  view.unmount();
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:accounting-file');
});

test('protected photo opens the loaded image', async () => {
  fetch.mockResolvedValue({ok:true,blob:async () => new Blob(['photo'],{type:'image/jpeg'})});
  const onPhoto = jest.fn();
  render(<AccountingDocumentAttachment url="/tenant-files/32/content" C={C} onPhoto={onPhoto}/>);
  await screen.findByRole('img', {name:'Фото накладной'});
  fireEvent.click(screen.getByRole('button', {name:'Открыть фото накладной'}));
  expect(onPhoto).toHaveBeenCalledWith('blob:accounting-file');
});

test('legacy PDF never renders as an image', () => {
  render(<AccountingDocumentAttachment url="/uploads/invoice.pdf" C={C}/>);
  expect(screen.getByRole('link',{name:'Скачать PDF'})).toHaveAttribute('href','/uploads/invoice.pdf');
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
});

test('unreadable image replaces the broken preview with a file link', () => {
  render(<AccountingDocumentAttachment url="/uploads/photo.jpg" C={C}/>);
  fireEvent.error(screen.getByRole('img'));
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
  expect(screen.getByRole('link',{name:'Скачать файл'})).toHaveAttribute('href','/uploads/photo.jpg');
});

test('denied protected file shows an error without exposing an image or download', async () => {
  fetch.mockResolvedValue({ok:false,status:403});
  render(<AccountingDocumentAttachment url="/tenant-files/33/content" C={C}/>);
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Файл недоступен'));
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
});

import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import CustomerDocuments from './CustomerDocuments';
import CustomerWarranty from './CustomerWarranty';
import { customerRecordsScope } from './useCustomerRecordsLoader';

const project = { id: 3, companyId: 2 };
const user = { id: 7, projectId: 3, companyId: 2 };
const ready = { scope: customerRecordsScope(user, 2), status: 'ready' };
const base = { project, user, C: {}, card: {}, inp: {}, fileSrc: value => value, refresh: jest.fn(async () => {}) };
afterEach(() => jest.restoreAllMocks());

test('documents expose only published exact-owner records and safe attachment paths', () => {
  const doc = { id: 1, companyId: 2, projectId: 3, side: 'customer', docType: 'Visible', scanUrl: '/tenant-files/1/content' };
  render(<CustomerDocuments {...base} loadState={{ documents: ready, letters: ready }} documents={[
    doc, { ...doc, id: 2, companyId: 4, docType: 'Foreign' }, { ...doc, id: 3, side: 'contractor', docType: 'Private' },
    { ...doc, id: 4, signStatus: 'Аннулирован', docType: 'Voided' },
    { ...doc, id: 5, docType: 'Unsafe', scanUrl: 'javascript:alert(1)' },
  ]} />);
  expect(screen.getByText('Visible')).toBeTruthy();
  for (const text of ['Foreign', 'Private', 'Voided']) expect(screen.queryByText(text)).toBeNull();
  expect(screen.getAllByRole('link')).toHaveLength(1);
  expect(screen.getByRole('link').getAttribute('href')).toBe('/tenant-files/1/content');
});
test('customer sees frozen KS parties and the exact contract basis', () => {
  const doc={id:6,companyId:2,projectId:3,side:'customer',docType:'Акт КС-2',number:'2',
    signStatus:'Подписан',scanUrl:'/tenant-files/6/content',partySnapshot:{
      documentKind:'customerWorkAct',executor:{fullName:'ООО Исполнитель'},
      customer:{fullName:'ООО Заказчик'},contractBasis:{documentId:1,number:'15',version:2},
    }};
  render(<CustomerDocuments {...base} loadState={{documents:ready,letters:ready}} documents={[doc]}/>);
  expect(screen.getByText('ООО Исполнитель → ООО Заказчик · договор № 15')).toBeTruthy();
});
test('unconfirmed document load is not reported as an empty registry', () => {
  render(<CustomerDocuments {...base} loadState={{ documents: { ...ready, status: 'error', error: 'Offline' } }} />);
  expect(screen.getByText('Offline')).toBeTruthy();
  expect(screen.queryByText('Опубликованных документов пока нет.')).toBeNull();
});
test('warranty submission preserves draft on denial, then clears only after acknowledged save', async () => {
  global.fetch = jest.fn(async () => ({ ok: false, status: 403, json: async () => ({ detail: 'Denied' }) }));
  const refresh = jest.fn(async () => {});
  render(<CustomerWarranty {...base} refresh={refresh} loadState={{ warranty: ready }} />);
  const text = screen.getByLabelText('Что нужно исправить');
  fireEvent.change(text, { target: { value: 'Crack in wall' } });
  fireEvent.click(screen.getByText('Отправить обращение'));
  await screen.findByText('Denied');
  expect(text.value).toBe('Crack in wall');
  expect(refresh).not.toHaveBeenCalled();
  fetch.mockImplementation(async () => ({ ok: true, json: async () => ({ ok: true, id: 8 }) }));
  fireEvent.click(screen.getByText('Отправить обращение'));
  await screen.findByText('Обращение сохранено.');
  expect(text.value).toBe('');
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toMatchObject({ projectId: 3, description: 'Crack in wall' });
  expect(fetch.mock.calls[1][1].headers['X-Company-Id']).toBe('2');
});
test('a photo is bound to this project and canonical protected URL before the warranty POST', async () => {
  global.fetch = jest.fn(async url => ({ ok: true, json: async () => url.endsWith('/upload-photo')
    ? { companyId: 2, projectId: 3, contentUrl: '/tenant-files/9/content' } : { ok: true, id: 8 } }));
  render(<CustomerWarranty {...base} loadState={{ warranty: ready }} />);
  fireEvent.change(screen.getByLabelText('Что нужно исправить'), { target: { value: 'Crack' } });
  fireEvent.change(screen.getByLabelText('Фотография (до 10 МБ)'), { target: { files: [new File(['png'], 'photo.png', { type: 'image/png' })] } });
  await screen.findByText('Посмотреть фотографию');
  expect(fetch.mock.calls[0][1].body.get('projectId')).toBe('3');
  fireEvent.click(screen.getByText('Отправить обращение'));
  await screen.findByText('Обращение сохранено.');
  expect(JSON.parse(fetch.mock.calls[1][1].body).photoUrl).toBe('/tenant-files/9/content');
});
test('an uncertain save blocks a duplicate and hides another author warranty record', async () => {
  let finish;
  global.fetch = jest.fn(() => new Promise(resolve => { finish = resolve; }));
  render(<CustomerWarranty {...base} loadState={{ warranty: ready }} records={[
    { id: 1, companyId: 2, projectId: 3, createdByUserId: 8, description: 'Other author' },
  ]} />);
  expect(screen.queryByText('Other author')).toBeNull();
  fireEvent.change(screen.getByLabelText('Что нужно исправить'), { target: { value: 'Crack' } });
  const send = screen.getByText('Отправить обращение');
  fireEvent.click(send); fireEvent.click(send);
  expect(fetch).toHaveBeenCalledTimes(1);
  finish({ ok: false, status: 500, json: async () => ({}) });
  await waitFor(() => expect(screen.getByRole('alert')).toBeTruthy());
  fireEvent.click(send);
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('one library filters contracts and letters without exposing other owners', () => {
  const doc={id:1,companyId:2,projectId:3,side:'customer',docType:'Договор',number:'362',scanUrl:'/tenant-files/1/content'};
  render(<CustomerDocuments {...base} loadState={{documents:ready,letters:ready}}
    documents={[doc,{...doc,id:2,docType:'Акт',number:'ACT'},{...doc,id:3,companyId:9,number:'FOREIGN'}]}
    letters={[{...doc,id:4,subject:'Письмо о сроках',body:'Согласование'}]}/>);
  fireEvent.click(screen.getByRole('button',{name:'Договоры',exact:true}));
  expect(screen.getByText('Договор № 362')).toBeTruthy();expect(screen.queryByText('Акт № ACT')).toBeNull();
  expect(screen.queryByText('Письмо о сроках')).toBeNull();expect(screen.queryByText(/FOREIGN/)).toBeNull();
  fireEvent.change(screen.getByRole('searchbox'),{target:{value:'нет совпадений'}});
  expect(screen.queryByText('Договор № 362')).toBeNull();
  fireEvent.change(screen.getByRole('searchbox'),{target:{value:''}});
  fireEvent.click(screen.getByRole('button',{name:'Письма',exact:true}));
  expect(screen.getByText('Письмо о сроках')).toBeTruthy();expect(screen.queryByText('Договор № 362')).toBeNull();
});

test('project switch clears search and type and does not show late old records', () => {
  const view=render(<CustomerDocuments {...base} loadState={{documents:ready,letters:ready}}/>);
  fireEvent.click(screen.getByRole('button',{name:'Договоры',exact:true}));
  fireEvent.change(screen.getByRole('searchbox'),{target:{value:'старый'}});
  view.rerender(<CustomerDocuments {...base} project={{id:4,companyId:2}} loadState={{documents:ready,letters:ready}}
    documents={[{id:1,companyId:2,projectId:3,side:'customer',docType:'Договор',number:'OLD'}]}/>);
  expect(screen.getByRole('searchbox').value).toBe('');
  expect(screen.getByRole('button',{name:'Все документы'}).getAttribute('aria-pressed')).toBe('true');
  expect(screen.queryByText(/OLD/)).toBeNull();
});

test('customer sees a plain correction reason and the preserved version history', () => {
  render(<CustomerDocuments {...base} loadState={{documents:ready,letters:ready}} letters={[
    {id:1,companyId:2,projectId:3,side:'customer',direction:'incoming',subject:'Старый файл',
      correctionReason:'Не видна подпись на последней странице',correctionRequestedAt:'2026-09-29',correctedByLetterId:2},
    {id:2,companyId:2,projectId:3,side:'customer',direction:'incoming',subject:'Новая версия',replacesLetterId:1},
  ]}/>);
  expect(screen.getByText('Нужно исправить: Не видна подпись на последней странице')).toBeTruthy();
  expect(screen.getByText('Исправленная версия отправлена')).toBeTruthy();
  expect(screen.getByText('Исправленная версия')).toBeTruthy();
  expect(screen.queryByRole('button',{name:'Загрузить исправленный файл'})).toBeNull();
});

test('customer sees an addressed outgoing file as received from the company', () => {
  render(<CustomerDocuments {...base} loadState={{documents:ready,letters:ready}} letters={[
    {id:5,companyId:2,projectId:3,side:'customer',direction:'outgoing',subject:'Акт обследования',
      deliveryStatus:'sent',publishedAt:'2026-09-29T08:30:00Z',publishedByName:'Директор',partySnapshot:{
        sender:{fullName:'ООО Альянс',inn:'2611008712'},recipient:{fullName:'Лицей №4'},
      },
      fileUrl:'/tenant-files/51/content'},
  ]}/>);
  expect(screen.getByText(/Получено от ООО Альянс/)).toBeTruthy();
  expect(screen.getByText(/Для Лицей №4/)).toBeTruthy();
  expect(screen.getByText(/Директор/)).toBeTruthy();
  expect(screen.getByRole('link',{name:'Открыть вложение'}).getAttribute('href')).toBe('/tenant-files/51/content');
});

import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import WarehouseTransfersPanel from './WarehouseTransfersPanel';
import { DistributionWorkspace } from './WarehouseDistributionPanel';

const allocation = { id: 8, companyId: 2, projectId: 11, projectName: 'Школа', materialName: 'Кабель', unit: 'м', netQuantity: '15' };
const transfer = { id: 30, companyId: 2, sourceAllocationId: 8, fromProjectId: 11, fromProjectName: 'Школа', toProjectId: 13, toProjectName: 'Сад', warehouseInvoiceId: 10, lotId: 5, materialName: 'Кабель', unit: 'м', quantity: '10', receivedQuantity: '0', inTransitQuantity: '10', status: 'in_transit', receipts: [], reason: 'По заявке' };
const empty = () => ({ kind: null, allocationId: null, transferId: null, toProjectId: null, quantity: '', expectedQuantity: '', reason: '' });
const dispatch = () => ({ ...empty(), kind: 'dispatch', allocationId: 8, toProjectId: 13, quantity: '2', reason: 'Для другого устройства' });
const receipt = () => ({ ...empty(), kind: 'receipt', transferId: 30, quantity: '2', expectedQuantity: '3', reason: 'Частичная приёмка' });
const ok = (data, status = 200) => ({ ok: status < 400, status, json: async () => data });
const oldFlag = process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED;
const oldCrypto = global.crypto, oldFetch = global.fetch;
let userId = 200, props, server, writes, commands, operations, loseSave, losePost;
beforeAll(() => Object.defineProperty(global, 'crypto', { configurable: true, value: require('crypto').webcrypto }));
afterAll(() => {
  Object.defineProperty(global, 'crypto', { configurable: true, value: oldCrypto });
  if (oldFlag === undefined) delete process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED;
  else process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED = oldFlag;
  global.fetch = oldFetch;
});
beforeEach(() => {
  sessionStorage.clear(); process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED = 'true';
  props = { companyId: 2, userId: userId++, editable: true, projects: [{ id: 13, companyId: 2, name: 'Сад' }] };
  server = { companyId: 2, userId: props.userId, revision: 0, document: empty(), source: null, lastOperation: null };
  writes = []; commands = []; operations = new Map(); loseSave = false; losePost = false;
  global.fetch = jest.fn(async (url, options = {}) => {
    const path = new URL(url, 'http://localhost').pathname;
    if (path.endsWith('/transfer-draft')) {
      if (options.method === 'PUT') {
        const body = JSON.parse(options.body); writes.push(body);
        if (server.lastSave === body.requestId && server.revision === body.expectedRevision + 1) return ok({ ...server });
        if (body.expectedRevision !== server.revision) return ok({ detail: { code: 'warehouse_transfer_draft_conflict', message: 'Черновик перемещения изменён в другой вкладке' } }, 409);
        server = { ...server, revision: server.revision + 1, document: body.document, lastSave: body.requestId,
          source: body.document.kind === 'dispatch' ? allocation : body.document.kind === 'receipt' ? transfer : null };
        if (loseSave) { loseSave = false; throw Error('Ответ сохранения потерян'); }
      }
      return ok(JSON.parse(JSON.stringify(server)));
    }
    if (options.method === 'POST') {
      commands.push(options); const body = JSON.parse(options.body);
      let result = operations.get(body.requestId);
      if (!result) {
        if (Number(options.headers['X-Warehouse-Transfer-Draft-Revision']) !== server.revision) return ok({ detail: { code: 'warehouse_transfer_draft_conflict', message: 'Черновик перемещения изменён в другой вкладке' } }, 409);
        result = { ok: true, requestId: body.requestId, item: { ...transfer, ...(path.endsWith('/receipts') ? {} : { quantity: body.quantity }) } };
        operations.set(body.requestId, result);
        server = { ...server, revision: server.revision + 1, document: empty(), source: null, lastSave: null, lastOperation: { requestId: body.requestId, operationId: 70 } };
      }
      if (losePost) { losePost = false; throw Error('Ответ перемещения потерян'); }
      return ok(result);
    }
    return ok({ items: [transfer], truncated: false, nextCursor: null });
  });
});
function seed(document) { server = { ...server, revision: 1, document, source: document.kind === 'dispatch' ? allocation : transfer }; }
test('dispatch restores exact saved input without a parent source on another device', async () => {
  seed({ ...dispatch(), quantity: '2.' });
  render(<WarehouseTransfersPanel {...props} />);
  await waitFor(() => expect(screen.getByLabelText('Количество отправки')).toHaveValue('2.'));
  expect(screen.getByLabelText('Объект назначения')).toHaveValue('13');
  expect(screen.getByLabelText('Основание отправки')).toHaveValue('Для другого устройства');
  expect(commands).toHaveLength(0);
});
test('receipt restores exact transfer but requires a new physical confirmation', async () => {
  seed(receipt()); render(<WarehouseTransfersPanel {...props} />);
  await waitFor(() => expect(screen.getByLabelText('Фактически принято')).toHaveValue('2'));
  expect(screen.getByLabelText('Ожидалось в этой приёмке')).toHaveValue('3');
  expect(screen.getByLabelText(/Подтверждаю фактическую приёмку/)).not.toBeChecked();
  expect(screen.getByRole('button', { name: 'Подтвердить приёмку', exact: true })).toBeDisabled();
  expect(commands).toHaveLength(0);
});
async function loaded(label = 'Количество отправки') { await screen.findByLabelText(label); }
const submitDispatch = () => fireEvent.click(screen.getByRole('button', { name: 'Подтвердить отправку', exact: true }));
test('editing dispatch persists before posting and survives remount with empty browser storage', async () => {
  const first = render(<WarehouseTransfersPanel {...props} source={allocation} />);
  await loaded();
  fireEvent.change(screen.getByLabelText('Объект назначения'), { target: { value: '13' } });
  fireEvent.change(screen.getByLabelText('Количество отправки'), { target: { value: '2.' } });
  fireEvent.change(screen.getByLabelText('Основание отправки'), { target: { value: 'Черновик' } });
  await waitFor(() => expect(server.document.reason).toBe('Черновик'));
  first.unmount(); sessionStorage.clear(); render(<WarehouseTransfersPanel {...props} />); await loaded();
  expect(screen.getByLabelText('Количество отправки')).toHaveValue('2.'); expect(commands).toHaveLength(0);
});
test('two editors keep losing local input on CAS conflict without automatic overwrite', async () => {
  seed(dispatch()); const a = render(<WarehouseTransfersPanel {...props} />), b = render(<WarehouseTransfersPanel {...props} />);
  await within(a.container).findByLabelText('Количество отправки'); await within(b.container).findByLabelText('Количество отправки');
  fireEvent.change(within(a.container).getByLabelText('Количество отправки'), { target: { value: '3' } });
  await waitFor(() => expect(server.document.quantity).toBe('3'));
  fireEvent.change(within(b.container).getByLabelText('Количество отправки'), { target: { value: '4' } });
  await within(b.container).findByText('Черновик перемещения изменён в другой вкладке');
  expect(within(b.container).getByLabelText('Количество отправки')).toHaveValue('4');
  expect(within(b.container).getByRole('button', { name: 'Подтвердить отправку', exact: true })).toBeDisabled();
  const n = writes.length; await act(async () => new Promise(r => setTimeout(r, 500))); expect(writes).toHaveLength(n);
});
test('lost save reply is retried with same request before newer input', async () => {
  seed(dispatch()); render(<WarehouseTransfersPanel {...props} />); await loaded(); loseSave = true;
  fireEvent.change(screen.getByLabelText('Количество отправки'), { target: { value: '3' } });
  await screen.findByText('Ответ сохранения потерян');
  fireEvent.change(screen.getByLabelText('Количество отправки'), { target: { value: '4' } });
  fireEvent.click(screen.getByText('Сохранить черновик перемещения'));
  await waitFor(() => expect(server.document.quantity).toBe('4'));
  expect(writes).toHaveLength(3); expect(writes[1]).toEqual(writes[0]); expect(commands).toHaveLength(0);
});
test.each(['dispatch', 'receipt'])('lost %s reply safely retries same command/revision only once', async kind => {
  seed(kind === 'dispatch' ? dispatch() : receipt()); render(<WarehouseTransfersPanel {...props} />);
  await loaded(kind === 'dispatch' ? 'Количество отправки' : 'Фактически принято');
  if (kind === 'receipt') fireEvent.click(screen.getByLabelText(/Подтверждаю фактическую приёмку/));
  losePost = true;
  fireEvent.click(screen.getByRole('button', { name: kind === 'dispatch' ? 'Подтвердить отправку' : 'Подтвердить приёмку', exact: true }));
  await screen.findByText('Ответ перемещения потерян'); fireEvent.click(screen.getByText('Повторить перемещение безопасно'));
  await screen.findByText(/Предыдущее перемещение сохранено/);
  expect(commands).toHaveLength(2); expect(commands[1].body).toBe(commands[0].body);
  expect(commands[1].headers['X-Warehouse-Transfer-Draft-Revision']).toBe(commands[0].headers['X-Warehouse-Transfer-Draft-Revision']);
  expect(operations.size).toBe(1); expect(server.document).toEqual(empty());
});
test('completed dispatch never reappears on another device after lost reply', async () => {
  seed(dispatch()); const first = render(<WarehouseTransfersPanel {...props} />); await loaded(); losePost = true; submitDispatch();
  await screen.findByText('Ответ перемещения потерян'); first.unmount(); sessionStorage.clear();
  render(<WarehouseTransfersPanel {...props} />); await screen.findByText(/Предыдущее перемещение сохранено/);
  expect(screen.queryByLabelText('Количество отправки')).not.toBeInTheDocument(); expect(commands).toHaveLength(1);
});
test('posting a stale revision preserves input and blocks further stock commands', async () => {
  seed(dispatch()); render(<WarehouseTransfersPanel {...props} />); await loaded(); server.revision += 1; submitDispatch();
  await screen.findByText('Загрузить серверное перемещение');
  expect(screen.getByLabelText('Количество отправки')).toHaveValue('2');
  expect(screen.getByRole('button', { name: 'Подтвердить отправку', exact: true })).toBeDisabled(); expect(operations.size).toBe(0);
});
test('explicit cancel persists empty draft without stock mutation', async () => {
  seed(receipt()); render(<WarehouseTransfersPanel {...props} />); await loaded('Фактически принято');
  fireEvent.click(screen.getByText('Отменить приёмку')); await waitFor(() => expect(server.document).toEqual(empty()));
  expect(server.revision).toBe(2); expect(commands).toHaveLength(0);
});
test('old save reply cannot overwrite edits made during the request', async () => {
  seed(dispatch()); const fetcher = global.fetch; let release;
  global.fetch = jest.fn(async (url, options = {}) => {
    const result = await fetcher(url, options);
    if (options.method === 'PUT' && writes.length === 1) await new Promise(resolve => { release = resolve; });
    return result;
  });
  render(<WarehouseTransfersPanel {...props} />); await loaded();
  fireEvent.change(screen.getByLabelText('Количество отправки'), { target: { value: '3' } });
  await waitFor(() => expect(release).toBeDefined());
  fireEvent.change(screen.getByLabelText('Количество отправки'), { target: { value: '4' } });
  await act(async () => release()); await waitFor(() => expect(server.document.quantity).toBe('4'));
  expect(screen.getByLabelText('Количество отправки')).toHaveValue('4'); expect(writes).toHaveLength(2);
});
test('in-app navigation recovers input not yet saved, without restoring receipt confirmation', async () => {
  seed(receipt()); const first = render(<WarehouseTransfersPanel {...props} />); await loaded('Фактически принято');
  fireEvent.change(screen.getByLabelText('Фактически принято'), { target: { value: '1.' } });
  fireEvent.click(screen.getByLabelText(/Подтверждаю фактическую приёмку/)); first.unmount();
  render(<WarehouseTransfersPanel {...props} />); await loaded('Фактически принято');
  expect(screen.getByLabelText('Фактически принято')).toHaveValue('1.');
  expect(screen.getByLabelText(/Подтверждаю фактическую приёмку/)).not.toBeChecked();
  await waitFor(() => expect(server.document.quantity).toBe('1.'));
});
test('foreign source rejected even with matching user/company envelope', async () => {
  seed(dispatch()); server.source = { ...allocation, companyId: 3 };
  render(<WarehouseTransfersPanel {...props} />); await screen.findByText(/Сервер не подтвердил черновик перемещения/);
  expect(screen.queryByLabelText('Количество отправки')).not.toBeInTheDocument(); expect(writes).toHaveLength(0);
});
test('late load after user switch cannot restore previous identity draft', async () => {
  seed(dispatch()); const old = { ...server }; const fetcher = global.fetch; let release;
  global.fetch = jest.fn((url, options) => url.endsWith('/transfer-draft') && !release
    ? new Promise(resolve => { release = () => resolve(ok(old)); }) : fetcher(url, options));
  const view = render(<WarehouseTransfersPanel {...props} />); await waitFor(() => expect(release).toBeDefined());
  server = { ...server, userId: props.userId + 1000, document: empty(), source: null };
  view.rerender(<WarehouseTransfersPanel {...props} userId={server.userId} />);
  await screen.findByText('Черновик перемещения сохранён на сервере.'); await act(async () => release());
  expect(screen.queryByLabelText('Количество отправки')).not.toBeInTheDocument(); expect(writes).toHaveLength(0);
});
test('failed draft save prevents dependent dispatch and retains input', async () => {
  seed(dispatch()); const fetcher = global.fetch;
  global.fetch = jest.fn((url, options = {}) => options.method === 'PUT'
    ? Promise.resolve(ok({ detail: 'Черновик временно недоступен' }, 503)) : fetcher(url, options));
  render(<WarehouseTransfersPanel {...props} />); await loaded();
  fireEvent.change(screen.getByLabelText('Количество отправки'), { target: { value: '3' } }); submitDispatch();
  await screen.findAllByText('Черновик временно недоступен');
  expect(screen.getByLabelText('Количество отправки')).toHaveValue('3'); expect(commands).toHaveLength(0);
});
test('late save after close and reopen cannot overwrite the reopened draft', async () => {
  seed(dispatch()); const fetcher = global.fetch; let release;
  global.fetch = jest.fn(async (url, options = {}) => {
    const result = await fetcher(url, options);
    if (options.method === 'PUT' && writes.length === 1) await new Promise(resolve => { release = resolve; });
    return result;
  });
  const first = render(<WarehouseTransfersPanel {...props} />); await loaded();
  fireEvent.change(screen.getByLabelText('Количество отправки'), { target: { value: '3' } });
  await waitFor(() => expect(release).toBeDefined()); first.unmount();
  render(<WarehouseTransfersPanel {...props} />); await loaded();
  fireEvent.change(screen.getByLabelText('Количество отправки'), { target: { value: '4' } });
  await act(async () => release());
  await waitFor(() => expect(server.document.quantity).toBe('4'));
  expect(screen.getByLabelText('Количество отправки')).toHaveValue('4'); expect(commands).toHaveLength(0);
});

test('restored return and transfer drafts cannot lock each other out of explicit cancellation', async () => {
  seed(dispatch()); const fetcher = global.fetch;
  global.fetch = jest.fn((url, options = {}) => {
    const path = new URL(url, 'http://localhost').pathname;
    if (path.endsWith('/return-draft')) return Promise.resolve(ok({ companyId: 2, userId: props.userId, revision: 2,
      document: { allocationId: 8, quantity: '1', reason: 'Возврат с другого устройства' }, source: allocation, lastOperation: null }));
    if (path.endsWith('/draft')) return Promise.resolve(ok({ companyId: 2, userId: props.userId, revision: 0,
      document: { rows: [{ lotId: null, projectId: null, quantity: '' }], reason: '' }, sources: [], lastOperation: null }));
    if (path.endsWith('/sources')) return Promise.resolve(ok({ items: [], truncated: false, nextCursor: null }));
    if (path === '/warehouse-distributions') return Promise.resolve(ok({ items: [{ ...allocation, quantity: '15', returnedQuantity: '0', returns: [] }], truncated: false, nextCursor: null }));
    return fetcher(url, options);
  });
  render(<DistributionWorkspace user={{ id: props.userId }} companyContext={{ mode: 'company', selectedCompanyId: 2, companies: [{ companyId: 2, role: 'директор' }] }} projects={props.projects} />);
  await loaded(); await screen.findByLabelText('Количество возврата');
  expect(screen.getByLabelText('Количество возврата')).toHaveValue('1');
  expect(screen.getByRole('button', { name: 'Отменить отправку', exact: true })).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'Отменить отправку', exact: true }));
  await waitFor(() => expect(server.document.kind).toBeNull());
  expect(screen.getByLabelText('Количество возврата')).toHaveValue('1'); expect(commands).toHaveLength(0);
});

/* Synthetic localhost only. Run with:
 * node scripts/preview-warehouse-distribution.cjs
 * node scripts/preview-warehouse-distribution.cjs --self-test
 * /?readOnly=1 hides commands and rejects writes from that preview.
 * Restart or use the reset button to restore seed data; nothing is persisted.
 */
const assert = require('node:assert/strict');
const { transferCommand, transferList } = require('./fixtures/warehouse-transfer-state.cjs');

function selfTest() {
  const state = createState();
  const batch = { companyId: 2, requestId: 'batch-1', reason: 'По заявке', rows: [
    { lotId: 5, projectId: 11, quantity: '10' },
    { lotId: 5, projectId: 12, quantity: '2.5' },
  ] };
  const result = command(state, '/warehouse-distributions', batch);
  assert.equal(result.ok, true);
  assert.equal(result.requestId, batch.requestId);
  assert.ok(Array.isArray(result.items));
  assert.equal(state.sources[0].availableQuantity, '87.5');
  assert.equal(state.records.length, 3);
  assert.deepEqual(command(state, '/warehouse-distributions', batch), result);
  assert.equal(state.sources[0].availableQuantity, '87.5');
  const id = result.items[0].id;
  const returnBody = {
    companyId: 2, requestId: 'return-1', reason: 'Не потребовалось', quantity: '3',
  };
  const returned = command(state, `/warehouse-distributions/${id}/returns`, returnBody);
  assert.equal(returned.ok, true);
  assert.equal(returned.requestId, returnBody.requestId);
  assert.equal(returned.item.id, id);
  assert.deepEqual(command(state, `/warehouse-distributions/${id}/returns`, returnBody), returned);
  const record = state.records.find(row => row.id === id);
  assert.equal(record.netQuantity, '7');
  assert.equal(record.returnedQuantity, '3');
  assert.equal(record.returns.length, 1);
  assert.equal(state.sources[0].availableQuantity, '90.5');
  const before = JSON.stringify(state);
  for (const rows of [
    [{ lotId: 5, projectId: 11, quantity: '50' }, { lotId: 5, projectId: 12, quantity: '50' }],
    [{ lotId: 5, projectId: 99, quantity: '1' }],
    [{ lotId: 5, projectId: 11, quantity: '-1' }],
  ]) assert.throws(() => command(state, '/warehouse-distributions', { ...batch, requestId: 'bad', rows }));
  assert.throws(() => command(state, `/warehouse-distributions/${id}/returns`, {
    companyId: 2, requestId: 'bad-return', reason: 'Лишнее', quantity: '8',
  }));
  assert.throws(() => command(state, '/warehouse-distributions', { ...batch, reason: 'Changed' }));
  assert.throws(() => command(state, '/warehouse-distributions', { ...batch, companyId: 3 }));
  assert.equal(JSON.stringify(state), before, 'Rejected commands must be atomic');
  const first = list(state, false, new URLSearchParams('limit=1'));
  assert.equal(first.items.length, 1);
  assert.equal(first.nextCursor, first.items[0].id);
  const second = list(state, false, new URLSearchParams(`limit=1&beforeId=${first.nextCursor}`));
  assert.ok(second.items[0].id < first.items[0].id);
  assert.equal(list(state, false, new URLSearchParams('q=missing')).items.length, 0);
  assert.equal(list(state, false, new URLSearchParams('projectId=12')).items.length, 1);
  assert.equal(list(state, true, new URLSearchParams('q=Цемент')).items.length, 1);
  const transitState = createState();
  const rootAvailable = transitState.sources[0].availableQuantity;
  const dispatchBody = { companyId: 2, requestId: 'send-1', allocationId: 8,
    toProjectId: 12, quantity: '6', reason: 'На другой объект' };
  const dispatched = command(transitState, '/warehouse-distributions/transfers', dispatchBody);
  assert.equal(dispatched.item.inTransitQuantity, '6');
  assert.equal(transitState.records.find(r => r.id === 8).netQuantity, '9');
  assert.deepEqual(command(transitState, '/warehouse-distributions/transfers', dispatchBody), dispatched);
  const receiptPath = `/warehouse-distributions/transfers/${dispatched.item.id}/receipts`;
  const partial = { companyId: 2, requestId: 'receive-1', quantity: '4', expectedQuantity: '6', reason: 'Два метра пока не доставлены' };
  const accepted = command(transitState, receiptPath, partial);
  assert.equal(accepted.item.inTransitQuantity, '2');
  assert.equal(accepted.item.status, 'discrepancy');
  assert.equal(accepted.item.receipts[0].discrepancyQuantity, '2');
  assert.equal(transitState.records.find(r => r.id === accepted.item.receipts[0].allocationId).netQuantity, '4');
  assert.deepEqual(command(transitState, receiptPath, partial), accepted);
  const unresolved = command(transitState, receiptPath, { ...partial, requestId: 'report-1', quantity: '0', expectedQuantity: '2' });
  assert.equal(unresolved.item.inTransitQuantity, '2');
  assert.equal(unresolved.item.receipts[1].allocationId, null);
  const done = command(transitState, receiptPath, { ...partial, requestId: 'receive-2', quantity: '2', expectedQuantity: '2' });
  assert.equal(done.item.inTransitQuantity, '0');
  assert.equal(done.item.status, 'received');
  assert.equal(transitState.sources[0].availableQuantity, rootAvailable);
  assert.throws(() => command(transitState, receiptPath, { ...partial, requestId: 'over-receive', quantity: '1', expectedQuantity: '1' }));
  const childId = accepted.item.receipts[0].allocationId;
  const childReturn = command(transitState, `/warehouse-distributions/${childId}/returns`, {
    companyId: 2, requestId: 'child-return', quantity: '1', reason: 'Излишек на общем складе',
  });
  assert.equal(childReturn.item.netQuantity, '3');
  const onward = command(transitState, '/warehouse-distributions/transfers', {
    ...dispatchBody, requestId: 'child-send', allocationId: childId, toProjectId: 11, quantity: '2',
  });
  assert.equal(onward.item.fromProjectId, 12);
  assert.equal(transitState.records.find(row => row.id === childId).netQuantity, '1');
  assert.equal(transitState.sources[0].availableQuantity, decimal(balance(rootAvailable) + units('1')));
  console.log('PASS: batch, returns, replay, transit, partial/discrepancy receipt, child return/redispatch and rejection');
}

function fail(detail, status = 400) { throw Object.assign(new Error(detail), { status }); }
function units(value) {
  if (typeof value !== 'string' || !/^\d+(\.\d{1,6})?$/.test(value)
      || Number(value) <= 0 || Number(value) >= 100000000) fail('Укажите положительное количество (до 6 знаков после точки)');
  const [whole, fraction = ''] = value.split('.');
  return Number(whole) * 1000000 + Number(fraction.padEnd(6, '0'));
}
function decimal(value) { return (value / 1000000).toFixed(6).replace(/\.?0+$/, '') || '0'; }
function balance(value) { return value === '0' ? 0 : units(value); }
function list(state, source, params) {
  const id = row => source ? row.lotId : row.id;
  const limit = Math.min(200, Math.max(1, Number(params.get('limit')) || (source ? 200 : 100)));
  const before = Number(params.get('beforeId'));
  const q = (params.get('q') || '').trim().toLocaleLowerCase('ru');
  const filtered = (source ? state.sources : state.records).filter(row => {
    if (source && balance(row.availableQuantity) <= 0) return false;
    if (before && id(row) >= before) return false;
    const searchable = source ? [row.invoiceNumber, row.materialName] : [row.projectName, row.materialName, row.invoiceNumber, row.id];
    if (!searchable.join(' ').toLocaleLowerCase('ru').includes(q)) return false;
    if (!source && params.get('projectId') && row.projectId !== Number(params.get('projectId'))) return false;
    if (!source && params.get('dateFrom') && row.createdAt.slice(0, 10) < params.get('dateFrom')) return false;
    if (!source && params.get('dateTo') && row.createdAt.slice(0, 10) > params.get('dateTo')) return false;
    return true;
  }).sort((a, b) => id(b) - id(a));
  const items = filtered.slice(0, limit);
  const truncated = filtered.length > limit;
  return { items, truncated, nextCursor: truncated ? id(items[items.length - 1]) : null };
}
function createState() {
  return {
    sources: [
      { lotId: 5, warehouseInvoiceId: 10, invoiceNumber: 'НК-10', invoiceLineIndex: 0, materialName: 'Кабель', unit: 'м', availableQuantity: '100' },
      { lotId: 6, warehouseInvoiceId: 10, invoiceNumber: 'НК-10', invoiceLineIndex: 1, materialName: 'Цемент', unit: 'кг', availableQuantity: '250' },
      { lotId: 7, warehouseInvoiceId: 11, invoiceNumber: 'НК-11', invoiceLineIndex: 0, materialName: 'Кабель', unit: 'м', availableQuantity: '40.5' },
    ],
    records: [{ id: 8, lotId: 5, warehouseInvoiceId: 10, invoiceNumber: 'НК-10', projectId: 11, projectName: 'Школа', materialName: 'Кабель', unit: 'м', quantity: '20', returnedQuantity: '5', netQuantity: '15', reason: 'Начальная синтетическая выдача', createdAt: '2026-09-16 09:00', createdBy: 'Анна — preview',
      returns: [{ id: 1, quantity: '5', reason: 'Синтетический возврат излишка', createdAt: '2026-09-16 10:00', createdBy: 'Анна — preview' }] }],
    nextId: 9, nextReturnId: 2, requests: {}, transfers: [], nextTransferId: 1, nextTransferReceiptId: 1,
  };
}
function command(state, pathname, body) {
  if (!body || body.companyId !== 2) fail('В preview доступна только компания 2', 403);
  if (typeof body.reason !== 'string' || !body.reason.trim() || body.reason.length > 1000) fail('Укажите основание');
  if (typeof body.requestId !== 'string' || !body.requestId || body.requestId.length > 100) fail('Нужен requestId');
  const signature = JSON.stringify({ pathname, body });
  const previous = Object.hasOwn(state.requests, body.requestId) && state.requests[body.requestId];
  if (previous) {
    if (previous.signature !== signature) fail('requestId уже использован для другой операции', 409);
    return previous.result;
  }
  const createdAt = new Date().toISOString();
  let result;
  if (pathname.startsWith('/warehouse-distributions/transfers')) {
    result = transferCommand(state, pathname, body, { fail, units, decimal, balance });
  } else if (pathname === '/warehouse-distributions') {
    if (!Array.isArray(body.rows) || !body.rows.length || body.rows.length > 50) fail('Нужно от 1 до 50 строк');
    const totals = new Map();
    const planned = body.rows.map(row => {
      const source = state.sources.find(s => s.lotId === row.lotId);
      if (!source || ![11, 12].includes(row.projectId)) fail('Неизвестная партия или объект');
      const quantity = units(row.quantity);
      totals.set(source.lotId, (totals.get(source.lotId) || 0) + quantity);
      return { source, row, quantity };
    });
    for (const [id, total] of totals) {
      if (total > balance(state.sources.find(s => s.lotId === id).availableQuantity)) fail('Недостаточно остатка партии для всего пакета', 409);
    }
    const items = planned.map(({ source, row, quantity }) => ({
      id: state.nextId++, lotId: source.lotId, warehouseInvoiceId: source.warehouseInvoiceId,
      invoiceNumber: source.invoiceNumber, materialName: source.materialName, unit: source.unit,
      projectId: row.projectId, projectName: row.projectId === 11 ? 'Школа' : 'Больница',
      quantity: decimal(quantity), returnedQuantity: '0', netQuantity: decimal(quantity),
      reason: body.reason.trim(), createdAt, createdBy: 'Анна — preview', returns: [],
    }));
    for (const [id, total] of totals) {
      const source = state.sources.find(s => s.lotId === id);
      source.availableQuantity = decimal(balance(source.availableQuantity) - total);
    }
    state.records.unshift(...items);
    result = { ok: true, requestId: body.requestId, items: structuredClone(items), synthetic: true };
  } else {
    const match = pathname.match(/^\/warehouse-distributions\/(\d+)\/returns$/);
    const record = match && state.records.find(r => r.id === Number(match[1]));
    if (!record) fail('Распределение не найдено', 404);
    const quantity = units(body.quantity);
    if (quantity > balance(record.netQuantity)) fail('Возврат превышает не возвращённое количество', 409);
    const source = state.sources.find(s => s.lotId === record.lotId);
    const returned = { id: state.nextReturnId++, quantity: decimal(quantity), reason: body.reason.trim(), createdAt, createdBy: 'Анна — preview' };
    source.availableQuantity = decimal(balance(source.availableQuantity) + quantity);
    record.returnedQuantity = decimal(balance(record.returnedQuantity) + quantity);
    record.netQuantity = decimal(balance(record.netQuantity) - quantity);
    record.returns.push(returned);
    result = { ok: true, requestId: body.requestId, item: structuredClone(record), synthetic: true };
  }
  Object.defineProperty(state.requests, body.requestId, { value: { signature, result }, enumerable: true });
  return result;
}

async function start() {
  const port = Number(process.env.WAREHOUSE_PREVIEW_PORT || 4410);
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('Invalid local preview port');
  const origin = `http://127.0.0.1:${port}`;
  const http = require('node:http');
  const path = require('node:path');
  const root = path.resolve(__dirname, '..');
  const webpack = require('webpack');
  const { createFsFromVolume, Volume } = require('memfs');
  const entry = `
      import React, {useState} from 'react';
      import {createRoot} from 'react-dom/client';
      import {DistributionWorkspace} from ${JSON.stringify(path.join(root, 'src/features/warehouse/WarehouseDistributionPanel.jsx'))};
      const readOnly = new URLSearchParams(location.search).get('readOnly') === '1';
      function Preview() {
        const [revision, setRevision] = useState(0);
        const [refreshes, setRefreshes] = useState(0);
        const [error, setError] = useState('');
        return <main><h1>Склад · синтетический preview</h1>
          <p>Только локальная память. Нет реальных API, авторизации, журналов качества и поставщицкого долга. Доступное количество в mock равно остатку распределения после возвратов и отправок; расход на объекте не моделируется.</p>
          <nav><a href="/">Выдача и возврат</a> · <a href="/?readOnly=1">Только чтение</a></nav>
          {!readOnly && <button onClick={async () => { try {
            const response = await fetch('/__fixture/reset', {method:'POST'});
            if (!response.ok) throw new Error('Не удалось сбросить fixture');
            setRevision(v => v + 1); setRefreshes(0); setError('');
          } catch (e) { setError(e.message); } }}>Сбросить синтетические данные</button>}
          {error && <p role="alert">{error}</p>}
          <p>Режим: {readOnly ? 'только чтение' : 'директор'} · refreshData: {refreshes}</p>
          <DistributionWorkspace key={revision} readOnly={readOnly}
            companyContext={{mode:'company',selectedCompanyId:2,companies:[{companyId:2,role:'директор'}]}}
            projects={[{id:11,companyId:2,name:'Школа'},{id:12,companyId:2,name:'Больница'}]}
            C={{text:'#172033',textMuted:'#596579',border:'#cdd5df',card:'#fff',accent:'#2259c5'}}
            refreshData={async () => setRefreshes(v => v + 1)} />
        </main>;
      }
      createRoot(document.getElementById('root')).render(<Preview />);
    `;
  const babel = { loader: require.resolve('babel-loader'), options: { presets: [require.resolve('@babel/preset-react')] } };
  const output = path.join(root, 'scripts', '.warehouse-preview-memory');
  const compiler = webpack({
    mode: 'development', context: root, devtool: false,
    entry: 'data:text/javascript;base64,' + Buffer.from(entry).toString('base64'),
    output: { path: output, filename: 'bundle.js' },
    resolve: { extensions: ['.js', '.jsx'] },
    plugins: [
      new webpack.DefinePlugin({
        'process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_ENABLED': JSON.stringify('true'),
        'process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED': JSON.stringify('true'),
      }),
      new webpack.NormalModuleReplacementPlugin(/^\.\.\/\.\.\/api$/, resource => {
        resource.request = 'data:text/javascript,' + encodeURIComponent("export const API = new URLSearchParams(location.search).get('readOnly') === '1' ? '/fixture-readonly' : '';");
      }),
    ],
    module: { rules: [
      { test: /\.jsx?$/, exclude: /node_modules/, use: babel },
      { mimetype: 'text/javascript', use: babel },
      { test: /\.css$/, use: [require.resolve('style-loader'), require.resolve('css-loader')] },
    ] },
  });
  // Match the existing webpack fixture, but keep all emitted files in memory.
  compiler.outputFileSystem = createFsFromVolume(new Volume());
  await new Promise((resolve, reject) => compiler.run((error, stats) => {
    compiler.close(() => {});
    if (error || stats.hasErrors()) reject(error || new Error(stats.toString('errors-only')));
    else resolve();
  }));
  const bundle = compiler.outputFileSystem.readFileSync(path.join(output, 'bundle.js'));
  let state = createState();
  const server = http.createServer(async (req, res) => {
    const send = (status, data) => { res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' }); res.end(JSON.stringify(data)); };
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'");
    try {
      const url = new URL(req.url, origin);
      const readOnly = url.pathname.startsWith('/fixture-readonly/');
      const pathname = readOnly ? url.pathname.slice('/fixture-readonly'.length) : url.pathname;
      if (req.method === 'POST') {
        if (req.headers.origin && req.headers.origin !== origin) fail('Local preview only', 403);
        if (readOnly || (req.headers.referer && new URL(req.headers.referer).searchParams.get('readOnly') === '1')) fail('Режим только чтения', 403);
        if (pathname === '/__fixture/reset') { state = createState(); send(200, { ok: true }); return; }
        if (!/^\/warehouse-distributions(?:\/\d+\/returns|\/transfers(?:\/\d+\/receipts)?)?$/.test(pathname)) fail('Unknown synthetic endpoint', 404);
        let raw = '';
        for await (const chunk of req) { raw += chunk; if (raw.length > 64000) fail('Request too large', 413); }
        let body;
        try { body = JSON.parse(raw); } catch (_) { fail('Invalid JSON'); }
        send(200, command(state, pathname, body)); return;
      }
      if (req.method !== 'GET') fail('Method not allowed', 405);
      if (pathname === '/warehouse-distributions/transfers') { send(200, transferList(state, url.searchParams)); return; }
      if (pathname === '/warehouse-distributions/sources') { send(200, list(state, true, url.searchParams)); return; }
      if (pathname === '/warehouse-distributions') { send(200, list(state, false, url.searchParams)); return; }
      if (pathname === '/favicon.ico') { res.writeHead(204); res.end(); return; }
      if (pathname === '/bundle.js') {
        res.writeHead(200, { 'Content-Type': 'text/javascript' }); res.end(bundle); return;
      }
      if (pathname !== '/') fail('Only the synthetic warehouse preview is available', 404);
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Склад — локальный preview</title><style>body{margin:0;background:#f3f5f8;font:15px system-ui;color:#172033}main{max-width:1200px;margin:auto;padding:24px}nav{margin:16px 0}button{cursor:pointer}h1{font-size:24px}</style></head><body><div id="root"></div><script src="/bundle.js"></script></body></html>');
    } catch (error) { send(error.status || 500, { detail: error.message }); }
  });
  server.on('error', error => { console.error(error.message); process.exitCode = 1; });
  server.listen(port, '127.0.0.1', () => console.log(`Synthetic warehouse preview: ${origin} (readOnly: /?readOnly=1)`));
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close());
}

if (process.argv.includes('--self-test')) selfTest();
else start().catch(error => { console.error(error.message); process.exitCode = 1; });

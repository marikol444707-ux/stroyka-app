/* Isolated synthetic HTTP fixture: memory only, no database, email or upstream. */
const http = require('http');
const fs = require('fs');
const os = require('os');
const path = require('path');
const webpack = require('webpack');
const output = fs.mkdtempSync(path.join(os.tmpdir(), 'stroyka-ledger-preview-'));
const companies = new Map();
const compiler = webpack({
  mode: 'development', devtool: false, context: path.resolve(__dirname, '..'),
  entry: path.join(__dirname, 'fixtures/supplier-ledger.jsx'),
  output: { path: output, filename: 'bundle.js' },
  resolve: { extensions: ['.js', '.jsx'] },
  plugins: [new webpack.DefinePlugin({
    'process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED': JSON.stringify('true'),
    'process.env.REACT_APP_API_URL': JSON.stringify('/synthetic-api'),
    'process.env.REACT_APP_CLIENT_ERROR_LOGGING': JSON.stringify('false'),
  })],
  module: { rules: [{ test: /\.jsx?$/, exclude: /node_modules/, use: {
    loader: require.resolve('babel-loader'), options: { presets: [require.resolve('@babel/preset-react')] },
  } }, { test: /\.css$/, use: [require.resolve('style-loader'), require.resolve('css-loader')] }] },
});
compiler.run((error, stats) => {
  compiler.close(() => {});
  if (error || stats.hasErrors()) { console.error(error || stats.toString('errors-only')); process.exitCode = 1; return; }
  const server = http.createServer(async (req, res) => {
    res.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:");
    res.setHeader('Cache-Control', 'no-store');
    const json = (data, code = 200) => { res.writeHead(code, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(data)); };
    const url = new URL(req.url, 'http://127.0.0.1');
    if (url.pathname === '/bundle.js') { res.setHeader('Content-Type', 'text/javascript'); fs.createReadStream(path.join(output, 'bundle.js')).pipe(res); return; }
    if (url.pathname === '/favicon.ico') { res.writeHead(204); res.end(); return; }
    if (url.pathname === '/' && req.method === 'GET') {
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      res.end('<!doctype html><html lang="ru"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Synthetic supplier ledger</title><div id="root"></div><script src="/bundle.js"></script></html>'); return;
    }
    const match = url.pathname.match(/^\/synthetic-api\/companies\/(2|3|4)\/(supplier-payments(?:\/cancel-request)?|supplier-payment-documents\/invoice\/9)$/);
    if (!match) { json({ detail: 'Synthetic preview only' }, 403); return; }
    const companyId = Number(match[1]);
    if (req.headers['x-company-id'] !== String(companyId) || req.headers['x-company-mode'] !== 'company') {
      json({ detail: 'Wrong synthetic company headers' }, 409); return;
    }
    if (!companies.has(companyId)) companies.set(companyId, { cents: 0, operations: [], cancelled: new Map(), lost: false });
    const state = companies.get(companyId);
    const money = cents => (cents / 100).toFixed(2);
    if (req.method === 'GET' && match[2].includes('payment-documents')) {
      json({ schemaVersion: 1, companyId, documentKind: 'invoice', documentId: 9,
        canonicalTarget: { documentKind: 'invoice', documentId: 9 },
        scope: { payerCompanyId: companyId, supplierId: 3, projectName: 'Тестовый объект', workPackage: 'Основная' },
        amount: '200.00', paidAmount: money(state.cents), remainingAmount: money(20000 - state.cents),
        openingPaidAmount: state.operations.length ? '0.00' : null, registered: !!state.operations.length,
        isMirror: false, status: state.cents ? 'Частично оплачен' : 'Утверждён', accountingStatus: null }); return;
    }
    if (req.method === 'GET') {
      json({ schemaVersion: 1, companyId, items: [...state.operations].reverse().map(({ command, ...row }) => row),
        hasMore: false, nextCursor: null }); return;
    }
    if (req.method !== 'POST' || !match[2].startsWith('supplier-payments')) { json({ detail: 'Unsupported synthetic request' }, 405); return; }
    try {
      let raw = '';
      for await (const chunk of req) { raw += chunk; if (raw.length > 8192) throw new Error('Synthetic request too large'); }
      const command = JSON.parse(raw);
      let operation = state.operations.find(row => row.requestId === command.requestId);
      if (operation && JSON.stringify(operation.command) !== JSON.stringify(command)) { json({ detail: 'UUID conflict' }, 409); return; }
      const cancelled = state.cancelled.get(command.requestId);
      if (cancelled && JSON.stringify(cancelled.command) !== JSON.stringify(command)) { json({ detail: 'UUID conflict' }, 409); return; }
      if (match[2].endsWith('/cancel-request')) {
        const identity = { companyId, requestId: command.requestId, documentKind: command.documentKind,
          documentId: command.documentId, kind: command.kind };
        if (operation) {
          json({ ...identity, status: 'confirmed', result: { operationId: operation.operationId,
            projectPaymentId: operation.projectPaymentId, kind: operation.kind, amount: operation.amount } });
        } else {
          const record = cancelled || { command, cancelledAt: new Date().toISOString() };
          state.cancelled.set(command.requestId, record);
          json({ ...identity, status: 'cancelled', cancelledAt: record.cancelledAt });
        }
        return;
      }
      if (cancelled) { json({ detail: { code: 'request_cancelled', message: 'Попытка отменена' } }, 409); return; }
      if (!operation) {
        if (companyId === 4) { json({ detail: 'Тестовый отказ: документ требует сверки' }, 409); return; }
        const original = command.kind === 'reversal' && state.operations.find(row => row.operationId === command.reversesId);
        const cents = Math.round(Number(original ? original.amount : command.amount) * 100);
        const delta = command.kind === 'reversal' ? -cents : cents;
        if (!['payment', 'reversal'].includes(command.kind) || command.documentKind !== 'invoice' || command.documentId !== 9
          || !Number.isSafeInteger(cents) || cents <= 0 || state.cents + delta > 20000 || state.cents + delta < 0
          || (command.kind === 'reversal' && (!original || original.kind !== 'payment' || original.reversedById))) {
          json({ detail: 'Synthetic payment rejected' }, 422); return;
        }
        const id = state.operations.length + 1;
        operation = { ...command, companyId, operationId: id, projectPaymentId: id,
          amount: money(cents), signedAmount: money(delta), actorId: 4, actorName: 'Тестовый бухгалтер',
          createdAt: new Date().toISOString(), reversesId: original ? original.operationId : null, reversedById: null,
          payerCompanyId: companyId, supplierId: 3, projectName: 'Тестовый объект', workPackage: 'Основная', command };
        state.operations.push(operation); state.cents += delta;
        if (original) original.reversedById = id;
        // Company 3 loses exactly the first committed response; retry must use the same UUID.
        if (companyId === 3 && !state.lost) { state.lost = true; req.socket.destroy(); return; }
      }
      const { command: ignored, ...result } = operation;
      json(result);
    } catch (_) { if (!res.destroyed) json({ detail: 'Invalid synthetic request' }, 400); }
  });
  server.listen(Number(process.env.SUPPLIER_LEDGER_PREVIEW_PORT || 4418), '127.0.0.1', () => {
    console.log('Synthetic supplier ledger: http://127.0.0.1:' + server.address().port);
  });
  process.on('SIGTERM', () => server.close());
  process.on('SIGINT', () => server.close());
});

/* Localhost-only browser fixture, synthetic in-memory API. Not a backend substitute. */
const http = require('http');
const fs = require('fs');
const os = require('os');
const path = require('path');
const webpack = require('webpack');
const root = path.resolve(__dirname, '..');
const output = fs.mkdtempSync(path.join(os.tmpdir(), 'stroyka-alias-preview-'));
const port = Number(process.env.ALIAS_PREVIEW_PORT || 4393);
const compiler = webpack({mode: 'development', context: root, devtool: false,
  entry: path.join(__dirname, 'fixtures/owned-material-aliases.jsx'),
  output: {path: output, filename: 'bundle.js'}, resolve: {extensions: ['.js', '.jsx']},
  plugins: [new webpack.DefinePlugin({'process.env.REACT_APP_COMPANY_MATERIAL_ALIASES_ENABLED': JSON.stringify('1')})],
  module: {rules: [
    {test: /\.jsx?$/, exclude: /node_modules/, use: {loader: require.resolve('babel-loader'), options: {presets: [require.resolve('@babel/preset-react')]}}},
    {test: /\.css$/, use: [require.resolve('style-loader'), require.resolve('css-loader')]},
  ]},
});
let nextId = 1;
const rows = [];
const key = value => String(value).toLowerCase().replace(/[.,;:()«»"'`/\\]+/g, ' ').replace(/\s+/g, ' ').trim();
function add(companyId, projectId, aliasName, canonicalName, previousId = null) {
  const row = {id: 'cma:'+nextId++, companyId, projectId, aliasName, canonicalName, canonicalUnit: 'шт',
    createdById: 9, createdAt: new Date().toISOString(), active: true, previousId};
  rows.push(row); return row;
}
add(2, 7, 'Марка поставщика', 'Материал компании А');
add(2, null, 'Общее название', 'Материал всей компании');
add(3, 8, 'Марка поставщика', 'Материал компании Б');
compiler.run((error, stats) => {
  compiler.close(() => {});
  if (error || stats.hasErrors()) {console.error(error || stats.toString('errors-only')); process.exitCode = 1; return;}
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://127.0.0.1');
    const reply = (status, data) => {res.writeHead(status, {'Content-Type': 'application/json'}); res.end(JSON.stringify(data));};
    if (url.pathname === '/fixture-concurrent-edit' && req.method === 'POST') {
      const old = rows.find(r => r.active && r.projectId !== null && r.companyId === Number(url.searchParams.get('companyId')));
      if (old) {old.active = false; add(old.companyId, old.projectId, old.aliasName, 'Версия другого сотрудника', old.id);}
      reply(200, {ok: true}); return;
    }
    if (url.pathname === '/company-material-aliases' && req.method === 'GET') {
      const companyId = Number(url.searchParams.get('companyId'));
      const projectId = Number(url.searchParams.get('projectId')) || null;
      const limit = Number(url.searchParams.get('limit')) || 25;
      const offset = Number(url.searchParams.get('offset')) || 0;
      const filtered = rows.filter(r => r.active && r.companyId === companyId && (r.projectId === null || r.projectId === projectId));
      reply(200, {items: filtered.slice(offset, offset+limit), limit, offset, revision: String(nextId)}); return;
    }
    if (url.pathname === '/company-material-aliases' && req.method === 'POST') {
      let body = '';
      req.on('data', chunk => {body += chunk; if (body.length > 32000) req.destroy();});
      req.on('end', () => {
        try {
          const value = JSON.parse(body);
          const old = rows.find(r => r.active && r.companyId === value.companyId && r.projectId === value.projectId && key(r.aliasName) === key(value.aliasName));
          if ((old?.id || null) !== value.expectedAliasId) {reply(409, {detail: 'Версия изменилась'}); return;}
          if (old) old.active = false;
          reply(201, add(value.companyId, value.projectId, value.aliasName, value.canonicalName, old?.id));
        } catch (_) {reply(400, {detail: 'Некорректные данные'});}
      }); return;
    }
    if (url.pathname.startsWith('/company-material-aliases/') && req.method === 'DELETE') {
      const row = rows.find(r => r.id === decodeURIComponent(url.pathname.split('/').pop()) && r.companyId === Number(url.searchParams.get('companyId')));
      if (!row) reply(404, {detail: 'Не найдено'}); else {row.active = false; reply(200, {ok: true});} return;
    }
    if (url.pathname === '/bundle.js') {res.setHeader('Content-Type', 'text/javascript'); fs.createReadStream(path.join(output, 'bundle.js')).pipe(res); return;}
    if (url.pathname === '/favicon.ico') {res.writeHead(204); res.end(); return;}
    if (url.pathname !== '/') {res.writeHead(404); res.end(); return;}
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.end('<!doctype html><html lang="ru"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Соответствия материалов — тест</title><style>body{font-family:Arial,sans-serif;margin:0}main{max-width:1200px;margin:auto;padding:16px}h1{font-size:20px}select,button{padding:8px;margin:8px 0}*{box-sizing:border-box}</style><div id="root"></div><script src="/bundle.js"></script></html>');
  });
  server.listen(port, '127.0.0.1', () => console.log('Synthetic alias preview: http://127.0.0.1:'+port));
  process.on('SIGTERM', () => server.close()); process.on('SIGINT', () => server.close());
});

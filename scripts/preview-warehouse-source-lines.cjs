/* Synthetic only: node scripts/preview-warehouse-source-lines.cjs; port 4411.
 * No backend, auth, storage, or emitted files. Browser checks owned by main.
 */
const http = require('node:http');
const path = require('node:path');
const webpack = require('webpack');
const { createFsFromVolume, Volume } = require('memfs');
const root = path.resolve(__dirname, '..');
const component = name => JSON.stringify(path.join(root, 'src/components', name));
const entry = `
import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import Source from ${component('WarehouseMovementSource.jsx')};
import Operations from ${component('WarehouseOperationsPanel.jsx')};
import Invoices from ${component('WarehouseInvoicesPanel.jsx')};
import Objects from ${component('WarehouseObjectsPanel.jsx')};
const C={text:'#172033',textSec:'#526077',textMuted:'#526077',bg:'#f4f6f8',border:'#ccd3dd',accent:'#2259c5',warning:'#915700',success:'#176b38'};
const material={id:1,name:'Кабель',unit:'м',quantity:10,workPackage:'Электрика'};
const line=index=>({...material,quantity:2,invoiceLineIndex:index});
const receipt={id:10,companyId:2,number:'TEST-10',date:'2026-09-16',acceptedBy:'Анна — preview',vat:'Без НДС',supplierName:'Синтетический поставщик',location:'Основной склад',items:[line(2)]};
const movement={companyId:2,sourceInvoiceId:10,sourceInvoiceLineIndex:2};
function Preview(){
 const [isMobile,setIsMobile]=useState(window.innerWidth<768);
 React.useEffect(()=>{
   const resize=()=>setIsMobile(window.innerWidth<768);
   window.addEventListener('resize',resize);
   return ()=>window.removeEventListener('resize',resize);
 },[]);
 const [form,setForm]=useState({fromLocation:'Основной склад',toLocation:'',notes:'',selectedMaterials:[{...material,quantity:'1'}]});
 const [transfer,setTransfer]=useState(null);
 const [showEditor,setShowEditor]=useState(false);
 const [requests,setRequests]=useState([]);
 const [ambiguous,setAmbiguous]=useState(false);
 const [unidentified,setUnidentified]=useState(false);
 React.useEffect(()=>{
   const originalFetch=window.fetch;
   window.fetch=async(url,options={})=>{
     const body=options.body?JSON.parse(options.body):null;
     setRequests(rows=>[...rows,{url,body}]);
     if(url==='/disabled/material-transfers') return {ok:true,json:async()=>({ok:true,id:Date.now()})};
     if(url==='/disabled/material-packaging-corrections/preview') return {ok:true,json:async()=>({preview:{stored:{quantity:2,unit:'уп'},proposed:{quantity:20,unit:'м'},reason:'Синтетическая сверка'}})};
     if(url==='/disabled/material-packaging-corrections/reviews') return {ok:true,json:async()=>({ok:true})};
     if(String(url).startsWith('/disabled/material-packaging-reviews')) return {ok:true,json:async()=>([])};
     return {ok:false,json:async()=>({detail:'Недоступно в синтетической проверке'})};
   };
   return ()=>{window.fetch=originalFetch;};
 },[]);
 const receipts=unidentified?[{...receipt,items:[{...material}]}]:[receipt];
 return <main><h1>Исходные строки — синтетическая проверка</h1>
 <p>Нет реальных запросов или сохранения. Разрешённая строка имеет индекс 2, скрытая 0 отсутствует.</p>
 <h2>История</h2>
 <div>Видимая строка 2:<Source movement={movement} invoices={[receipt]} C={C}/></div>
 <div>Скрытая строка 0:<Source movement={{...movement,sourceInvoiceLineIndex:0}} invoices={[receipt]} C={C}/></div>
 <div>Дубли индекса:<Source movement={movement} invoices={[{...receipt,items:[line(2),line(2)]}]} C={C}/></div>
 <div>Другая компания:<Source movement={{...movement,companyId:3}} invoices={[receipt]} C={C}/></div>
 <h2>Выбор источника</h2>
 <label><input type="checkbox" checked={unidentified} onChange={e=>{setUnidentified(e.target.checked);setForm(f=>({...f,selectedMaterials:[{...material,quantity:'1'}]}));}}/>Накладная без индексов</label>
 <Operations isMobile={isMobile} warehouseTab="move" C={C} card={{}} inp={{}} projects={[]} visibleActiveProjects={v=>v}
 warehouseMain={[material]} materials={[]} warehouseInvoices={receipts} warehouseMovements={[]}
 newMovement={form} setNewMovement={setForm} applyWarehouseMovement={()=>{}}/>
 <pre aria-label="Movement payload">{JSON.stringify(form.selectedMaterials,null,2)}</pre>
 <h2>Выдача: две одноимённые строки 2 и 5</h2>
 <p>Общий складской остаток 3 м: предложенные количества должны быть 2 + 1.</p>
 <label><input type="checkbox" checked={ambiguous} onChange={e=>setAmbiguous(e.target.checked)}/>Добавить старую выдачу без индекса</label>
 <Invoices isMobile={isMobile} C={C} card={{}} inp={{}} newInvoice={{items:[]}} suppliers={[]} projects={[]} user={{role:'директор'}}
 invoices={[{...receipt,id:20,number:'TEST-20',project:'Школа',location:'Школа',items:(unidentified?[{...material}]:[line(2),line(5)]).map(row=>({...row,conversionStatus:'needs_review'}))}]}
 warehouseInvoiceItems={inv=>({items:inv.items})} isSupplyDeliveryInvoice={()=>false}
 materials={[{...material,project:'Школа',quantity:3}]} setNewTransfer={setTransfer} setShowTransferForm={setShowEditor}
 materialTransfers={[{invoiceId:20,companyId:2,invoiceLineIndex:2,quantity:1},
 {invoiceId:20,companyId:2,invoiceLineIndex:5,quantity:0.5},
 {invoiceId:20,companyId:3,invoiceLineIndex:2,quantity:99},
 ...(ambiguous?[{invoiceId:20,companyId:2,materialName:'Кабель',workPackage:'Электрика',unit:'м',quantity:1}]:[])]}
 showPreview={()=>{}} buildInvoiceContent={()=>''} setShowQRModal={()=>{}}/>
 {transfer && <Objects isMobile={isMobile} C={C} card={{backgroundColor:'#fff'}} inp={{}} selectedWarehouseProject="Школа"
 projects={[{id:1,companyId:2,name:'Школа'}]} visibleActiveProjects={v=>v}
 materials={[{...material,project:'Школа',quantity:3}]} user={{role:'кладовщик',name:'Синтетический сотрудник'}}
 renderMaterialReconciliationPanel={()=>null} newTransfer={transfer} setNewTransfer={setTransfer}
 showTransferForm={showEditor} setShowTransferForm={setShowEditor} supplyRequests={[]}
 staff={[{id:1,name:'Иван',role:'мастер',project:'Школа'}]} setMaterialTransfers={()=>{}} setMaterials={()=>{}} notify={()=>{}}/>}
 <pre aria-label="Transfer payload">{JSON.stringify(transfer,null,2)}</pre>
 <pre aria-label="Synthetic requests">{JSON.stringify(requests,null,2)}</pre>
 </main>;
}
createRoot(document.getElementById('root')).render(<Preview/>);
`;
async function start() {
  const babel = { loader: require.resolve('babel-loader'), options: { presets: [require.resolve('@babel/preset-react')] } };
  const output = path.join(root, 'scripts', '.source-lines-memory');
  const compiler = webpack({
    mode: 'development', context: root, devtool: false,
    entry: 'data:text/javascript;base64,' + Buffer.from(entry).toString('base64'),
    output: { path: output, filename: 'bundle.js' },
    resolve: { extensions: ['.js', '.jsx'] },
    plugins: [new webpack.NormalModuleReplacementPlugin(/(?:^|\/)api$/, resource => {
      resource.request = 'data:text/javascript,' + encodeURIComponent("export const API = '/disabled';");
    })],
    module: { rules: [
      { test: /\.jsx?$/, exclude: /node_modules/, use: babel },
      { mimetype: 'text/javascript', use: babel },
      { test: /\.css$/, use: [require.resolve('style-loader'), require.resolve('css-loader')] },
    ] },
  });
  compiler.outputFileSystem = createFsFromVolume(new Volume());
  await new Promise((resolve, reject) => compiler.run((error, stats) => {
    compiler.close(() => {});
    if (error || stats.hasErrors()) reject(error || new Error(stats.toString('errors-only')));
    else resolve();
  }));
  const bundle = compiler.outputFileSystem.readFileSync(path.join(output, 'bundle.js'));
  const server = http.createServer((req, res) => {
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'none'; img-src data:; base-uri 'none'; frame-ancestors 'none'");
    if (req.method !== 'GET') { res.writeHead(405); res.end(); return; }
    if (req.url === '/favicon.ico') { res.writeHead(204); res.end(); return; }
    if (req.url === '/bundle.js') { res.writeHead(200, { 'Content-Type': 'text/javascript' }); res.end(bundle); return; }
    if (req.url !== '/') { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Source lines fixture</title><style>body{font:15px system-ui;margin:20px;color:#172033}main{max-width:1000px;margin:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere}h2{margin-top:32px}button{cursor:pointer}</style></head><body><div id="root"></div><script src="/bundle.js"></script></body></html>');
  });
  server.on('error', error => { console.error(error.message); process.exitCode = 1; });
  server.listen(4411, '127.0.0.1', () => console.log('Synthetic source lines: http://127.0.0.1:4411'));
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close());
}
start().catch(error => { console.error(error.message); process.exitCode = 1; });

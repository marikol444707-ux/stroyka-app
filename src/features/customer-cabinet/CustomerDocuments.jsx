import React, {useState} from 'react';
import { customerProjectRecord } from './projectSelection';
import { customerRecordsScope } from './useCustomerRecordsLoader';

export function recordLoadIssue(state, kind, project, user) {
  const entry = state?.[kind];
  if (entry?.scope !== customerRecordsScope(user, project.companyId ?? project.company_id, project.id)) return 'Загрузка данных…';
  if (entry.status === 'error') return entry.error || 'Данные временно недоступны.';
  return entry.status === 'ready' ? '' : 'Загрузка данных…';
}

export function CustomerAttachment({ value, fileSrc, label = 'Открыть вложение' }) {
  if (!value) return null;
  // External storage URLs must first be registered and published through the API.
  const safe = typeof value === 'string' && (/^\/tenant-files\/[1-9]\d*\/content$/.test(value)
    || /^\/uploads\/[^?#]+$/.test(value));
  return safe ? <a href={fileSrc(value)} target="_blank" rel="noopener noreferrer">{label}</a>
    : <p>Для вложения требуется защищённая ссылка. Обратитесь к подрядчику.</p>;
}

export default function CustomerDocuments(props) {
  return <DocumentLibrary key={customerRecordsScope(props.user, props.project.companyId ?? props.project.company_id, props.project.id)} {...props}/>;
}
function DocumentLibrary({ project, user, documents = [], letters = [], loadState, refresh, fileSrc, C, card, btnG }) {
  const [kindFilter, setKindFilter] = useState('all');
  const [search, setSearch] = useState('');
  const query = search.trim().toLocaleLowerCase('ru-RU');
  const renderRows = (kind, rows) => {
    const issue = recordLoadIssue(loadState, kind, project, user);
    if (issue) return <p role="status">{issue}</p>;
    const visible = rows.filter(row => customerProjectRecord(row, project) && row.side === 'customer'
      && row.signStatus !== 'Аннулирован' && row.status !== 'Аннулировано')
      .filter(row => kindFilter !== 'contracts' || ['Договор', 'Доп.соглашение'].includes(row.docType))
      .filter(row => !query || [row.docType, row.number, row.subject, row.body].filter(Boolean).join(' ').toLocaleLowerCase('ru-RU').includes(query));
    if (!visible.length) return <p style={{ color: C.textMuted }}>{query ? 'По вашему запросу ничего не найдено.' : kindFilter === 'contracts' ? 'Опубликованных договоров пока нет.' : kind === 'documents' ? 'Опубликованных документов пока нет.' : 'Писем по объекту пока нет.'}</p>;
    return visible.map(row => <article key={row.id} style={{ padding: '12px 0', borderBottom: `1px solid ${C.border}`, overflowWrap: 'anywhere' }}>
      <b>{kind === 'documents' ? [row.docType || 'Документ', row.number].filter(Boolean).join(' № ') : row.subject || 'Письмо'}</b>
      <p style={{ color: C.textSec, fontSize: 12 }}>{[row.docDate || row.letterDate, row.signStatus || row.status].filter(Boolean).join(' · ')}</p>
      {kind === 'letters' && row.body && <p style={{ whiteSpace: 'pre-wrap' }}>{row.body}</p>}
      {row.scanUrl || row.fileUrl ? <CustomerAttachment value={row.scanUrl || row.fileUrl} fileSrc={fileSrc} /> : kind === 'documents' && <p>Файл документа ещё не опубликован.</p>}
    </article>);
  };
  return <section style={{ ...card, padding: 20, marginBottom: 16 }} aria-label="Документы и письма">
    <h3 style={{ marginTop: 0 }}>Документы и письма</h3>
    <button type="button" style={btnG} onClick={() => refresh().catch(() => {})}>Обновить документы</button>
    <div role="group" aria-label="Вид документов" style={{display:'flex',gap:8,flexWrap:'wrap',margin:'16px 0'}}>
      {[['all','Все документы'],['contracts','Договоры'],['letters','Письма']].map(([value,label]) =>
        <button type="button" key={value} aria-pressed={kindFilter===value} onClick={()=>setKindFilter(value)}
          style={{...btnG,minHeight:44,border: `1px solid ${kindFilter===value ? C.primary || C.text : C.border}`,fontWeight:kindFilter===value ? 700 : 400}}>{label}</button>)}
    </div>
    <label style={{display:'block'}}>Поиск по номеру или названию
      <input type="search" value={search} onChange={event=>setSearch(event.target.value)}
        style={{display:'block',boxSizing:'border-box',width:'100%',minHeight:44,marginTop:8,padding:10,borderRadius:8,border:`1px solid ${C.border}`,background:C.bg,color:C.text}}/>
    </label>
    {kindFilter !== 'letters' && <><h4>{kindFilter==='contracts' ? 'Договоры и допсоглашения' : 'Документы объекта'}</h4>{renderRows('documents', documents)}</>}
    {kindFilter !== 'contracts' && <><h4>Переписка по объекту</h4>{renderRows('letters', letters)}</>}
  </section>;
}

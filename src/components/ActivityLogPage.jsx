import React, {useEffect, useMemo, useState} from 'react';
import {API} from '../api';

const parseAuditDate = (value) => {
  if (!value) return null;
  const direct = new Date(value);
  if (!Number.isNaN(direct.getTime())) return direct;
  const parts = String(value).match(/(\d{2})\.(\d{2})\.(\d{4})(?:,\s*|\s+)?(\d{2})?:?(\d{2})?/);
  if (!parts) return null;
  const [, dd, mm, yyyy, hh = '00', min = '00'] = parts;
  const date = new Date(Number(yyyy), Number(mm) - 1, Number(dd), Number(hh), Number(min));
  return Number.isNaN(date.getTime()) ? null : date;
};

const formatAuditTime = (value) => {
  const date = parseAuditDate(value);
  if (!date) return value ? String(value) : '—';
  return date.toLocaleTimeString('ru-RU', {hour: '2-digit', minute: '2-digit', second: '2-digit'});
};

const formatAuditDate = (value) => {
  const date = parseAuditDate(value);
  if (!date) return 'Без даты';
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  const sameDay = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  if (sameDay(date, today)) return 'Сегодня';
  if (sameDay(date, yesterday)) return 'Вчера';
  return date.toLocaleDateString('ru-RU', {day: '2-digit', month: 'long', year: 'numeric'});
};

const auditActionText = (entry) => {
  const action = entry.action || '—';
  const description = entry.description || '';
  return `${action}${description ? ` — ${description}` : ''}`;
};

const normalizeEntry = (entry, index) => ({
  id: entry.id || `local-${index}`,
  userName: entry.userName || entry.user || '',
  userRole: entry.userRole || entry.role || '',
  action: entry.action || '',
  entityType: entry.entityType || '',
  entityId: entry.entityId,
  description: entry.description || '',
  projectName: entry.projectName || '',
  createdAt: entry.createdAt || entry.time || '',
});

const mergeRows = (auditLog, activityLog) => {
  const rows = [
    ...(Array.isArray(auditLog) ? auditLog : []),
    ...(Array.isArray(activityLog) ? activityLog : []),
  ].map(normalizeEntry);
  const seen = new Set();
  return rows
    .filter((entry) => {
      const key = `${entry.id}|${entry.action}|${entry.description}|${entry.userName}|${entry.createdAt}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort((a, b) => {
      const da = parseAuditDate(a.createdAt)?.getTime() || 0;
      const db = parseAuditDate(b.createdAt)?.getTime() || 0;
      if (db !== da) return db - da;
      return String(b.id).localeCompare(String(a.id), 'ru');
    });
};

const uniqueOptions = (rows, field) => (
  Array.from(new Set(rows.map(row => String(row[field] || '').trim()).filter(Boolean)))
    .sort((a, b) => a.localeCompare(b, 'ru'))
);

const inputStyle = (C, isMobile) => ({
  minWidth: isMobile ? '100%' : 180,
  height: 42,
  borderRadius: 10,
  border: `1.5px solid ${C.border}`,
  background: C.bgWhite,
  color: C.text,
  padding: '0 12px',
  fontSize: 14,
  boxSizing: 'border-box',
});

const matchesDate = (row, from, to) => {
  if (!from && !to) return true;
  const date = parseAuditDate(row.createdAt);
  if (!date) return false;
  if (from) {
    const start = new Date(from + 'T00:00:00');
    if (date < start) return false;
  }
  if (to) {
    const end = new Date(to + 'T23:59:59');
    if (date > end) return false;
  }
  return true;
};

const buildAuditQuery = (filters) => {
  const params = new URLSearchParams();
  params.set('limit', '300');
  const mapping = {
    search: 'search',
    userName: 'user_name',
    userRole: 'user_role',
    action: 'action',
    projectName: 'project_name',
    dateFrom: 'date_from',
    dateTo: 'date_to',
  };
  Object.entries(mapping).forEach(([filterKey, queryKey]) => {
    const value = String(filters[filterKey] || '').trim();
    if (value) params.set(queryKey, value);
  });
  return params.toString();
};

export default function ActivityLogPage({C, activityLog, auditLog, roleLabels, isMobile = false}) {
  const [filters, setFilters] = useState({search:'', userName:'', userRole:'', action:'', projectName:'', dateFrom:'', dateTo:''});
  const [visibleCount, setVisibleCount] = useState(isMobile ? 40 : 80);
  const [serverRows, setServerRows] = useState([]);
  const [serverLoaded, setServerLoaded] = useState(false);
  const [serverLoading, setServerLoading] = useState(false);
  const [serverError, setServerError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setServerLoading(true);
      setServerError('');
      try {
        const token = localStorage.getItem('authToken');
        const headers = token ? {Authorization: 'Bearer ' + token} : undefined;
        const response = await fetch(API + '/audit-log?' + buildAuditQuery(filters), {
          headers,
          signal: controller.signal,
        });
        if (!response.ok) throw new Error('HTTP ' + response.status);
        const data = await response.json();
        setServerRows(Array.isArray(data) ? data : []);
        setServerLoaded(true);
      } catch (error) {
        if (error.name !== 'AbortError') {
          setServerError('Не удалось обновить журнал');
        }
      } finally {
        if (!controller.signal.aborted) setServerLoading(false);
      }
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [filters]);

  const auditRows = serverLoaded ? serverRows : auditLog;
  const allRows = useMemo(() => mergeRows(auditRows, activityLog), [auditRows, activityLog]);
  const optionRows = useMemo(() => mergeRows(auditLog, activityLog), [auditLog, activityLog]);
  const setFilter = (key, value) => {
    setVisibleCount(isMobile ? 40 : 80);
    setFilters(prev => ({...prev, [key]: value}));
  };

  const userOptions = useMemo(() => uniqueOptions(optionRows, 'userName'), [optionRows]);
  const roleOptions = useMemo(() => uniqueOptions(optionRows, 'userRole'), [optionRows]);
  const actionOptions = useMemo(() => uniqueOptions(optionRows, 'action'), [optionRows]);
  const projectOptions = useMemo(() => uniqueOptions(optionRows, 'projectName'), [optionRows]);

  const filteredRows = useMemo(() => {
    const search = filters.search.trim().toLowerCase();
    return allRows.filter(row => {
      if (filters.userName && row.userName !== filters.userName) return false;
      if (filters.userRole && row.userRole !== filters.userRole) return false;
      if (filters.action && row.action !== filters.action) return false;
      if (filters.projectName && row.projectName !== filters.projectName) return false;
      if (!matchesDate(row, filters.dateFrom, filters.dateTo)) return false;
      if (!search) return true;
      const haystack = [
        row.action,
        row.description,
        row.userName,
        row.userRole,
        row.projectName,
        row.entityType,
        row.entityId,
      ].join(' ').toLowerCase();
      return haystack.includes(search);
    });
  }, [allRows, filters]);

  const visibleRows = filteredRows.slice(0, visibleCount);
  const groupedRows = useMemo(() => {
    const groups = [];
    visibleRows.forEach(row => {
      const label = formatAuditDate(row.createdAt);
      let group = groups[groups.length - 1];
      if (!group || group.label !== label) {
        group = {label, rows: []};
        groups.push(group);
      }
      group.rows.push(row);
    });
    return groups;
  }, [visibleRows]);

  const resetFilters = () => {
    setFilters({search:'', userName:'', userRole:'', action:'', projectName:'', dateFrom:'', dateTo:''});
    setVisibleCount(isMobile ? 40 : 80);
  };

  const filterPanel = (
    <div style={{
      display:'grid',
      gridTemplateColumns:isMobile ? '1fr' : 'minmax(220px, 1.4fr) repeat(3, minmax(160px, 1fr))',
      gap:10,
      margin:'0 0 16px',
      alignItems:'center',
    }}>
      <input
        value={filters.search}
        onChange={e => setFilter('search', e.target.value)}
        placeholder="Поиск: действие, работник, объект, описание"
        style={inputStyle(C, isMobile)}
      />
      <select value={filters.userName} onChange={e => setFilter('userName', e.target.value)} style={inputStyle(C, isMobile)}>
        <option value="">Все работники</option>
        {userOptions.map(name => <option key={name} value={name}>{name}</option>)}
      </select>
      <select value={filters.action} onChange={e => setFilter('action', e.target.value)} style={inputStyle(C, isMobile)}>
        <option value="">Все действия</option>
        {actionOptions.map(action => <option key={action} value={action}>{action}</option>)}
      </select>
      <select value={filters.projectName} onChange={e => setFilter('projectName', e.target.value)} style={inputStyle(C, isMobile)}>
        <option value="">Все объекты</option>
        {projectOptions.map(project => <option key={project} value={project}>{project}</option>)}
      </select>
      <select value={filters.userRole} onChange={e => setFilter('userRole', e.target.value)} style={inputStyle(C, isMobile)}>
        <option value="">Все роли</option>
        {roleOptions.map(role => <option key={role} value={role}>{roleLabels[role] || role}</option>)}
      </select>
      <input type="date" value={filters.dateFrom} onChange={e => setFilter('dateFrom', e.target.value)} style={inputStyle(C, isMobile)} />
      <input type="date" value={filters.dateTo} onChange={e => setFilter('dateTo', e.target.value)} style={inputStyle(C, isMobile)} />
      <button
        type="button"
        onClick={resetFilters}
        style={{
          height:42,
          borderRadius:10,
          border:`1.5px solid ${C.border}`,
          background:C.bgWhite,
          color:C.textSec,
          fontWeight:700,
          cursor:'pointer',
        }}
      >
        Сбросить
      </button>
    </div>
  );

  const rowCard = (row) => (
    <div key={row.id} style={{backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,borderRadius:'14px',padding:'14px',boxSizing:'border-box'}}>
      <div style={{display:'flex',gap:10,justifyContent:'space-between',alignItems:'flex-start'}}>
        <div style={{color:C.text,fontSize:'14px',fontWeight:'800',lineHeight:1.35,overflowWrap:'anywhere'}}>
          {auditActionText(row)}
        </div>
        <div style={{color:C.accent,fontSize:'12px',fontWeight:800,whiteSpace:'nowrap'}}>{formatAuditTime(row.createdAt)}</div>
      </div>
      <div style={{marginTop:'10px',display:'grid',gridTemplateColumns:isMobile ? '1fr' : 'repeat(2, minmax(0, 1fr))',gap:'6px 14px',color:C.textSec,fontSize:'12px',lineHeight:1.3}}>
        <span><b style={{color:C.textMuted}}>Работник:</b> {row.userName || '—'}</span>
        <span><b style={{color:C.textMuted}}>Роль:</b> {roleLabels[row.userRole] || row.userRole || '—'}</span>
        <span><b style={{color:C.textMuted}}>Объект:</b> {row.projectName || '—'}</span>
        <span><b style={{color:C.textMuted}}>Тип:</b> {row.entityType || '—'}{row.entityId ? ` №${row.entityId}` : ''}</span>
      </div>
    </div>
  );

  return (
    <div style={{paddingBottom:isMobile ? '84px' : 0}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:12,marginBottom:14,flexWrap:'wrap'}}>
        <div>
          <h3 style={{color:C.text,margin:'0 0 6px',fontSize:isMobile ? '20px' : '18px',fontWeight:'800'}}>Журнал активности</h3>
          <div style={{color:C.textMuted,fontSize:13}}>
            Показано {visibleRows.length} из {filteredRows.length}; всего записей {allRows.length}
            {serverLoading ? ' · обновляю...' : ''}
            {serverError ? ` · ${serverError}` : ''}
          </div>
        </div>
      </div>

      {filterPanel}

      {groupedRows.length === 0 ? (
        <p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Журнал пуст или записи не подходят под фильтры</p>
      ) : (
        <div style={{display:'grid',gap:18}}>
          {groupedRows.map(group => (
            <section key={group.label}>
              <div style={{display:'flex',alignItems:'center',gap:10,margin:'0 0 10px'}}>
                <div style={{color:C.text,fontWeight:900,fontSize:15}}>{group.label}</div>
                <div style={{height:1,background:C.border,flex:1}} />
                <div style={{color:C.textMuted,fontSize:12}}>{group.rows.length}</div>
              </div>
              {isMobile ? (
                <div style={{display:'grid',gap:10}}>{group.rows.map(rowCard)}</div>
              ) : (
                <div style={{overflowX:'auto',border:`1.5px solid ${C.border}`,borderRadius:14}}>
                  <table style={{width:'100%',borderCollapse:'collapse',minWidth:980}}>
                    <thead>
                      <tr>
                        <th style={{padding:'12px',textAlign:'left',color:C.textMuted,fontSize:12,textTransform:'uppercase',borderBottom:`1px solid ${C.border}`}}>Время</th>
                        <th style={{padding:'12px',textAlign:'left',color:C.textMuted,fontSize:12,textTransform:'uppercase',borderBottom:`1px solid ${C.border}`}}>Действие</th>
                        <th style={{padding:'12px',textAlign:'left',color:C.textMuted,fontSize:12,textTransform:'uppercase',borderBottom:`1px solid ${C.border}`}}>Работник</th>
                        <th style={{padding:'12px',textAlign:'left',color:C.textMuted,fontSize:12,textTransform:'uppercase',borderBottom:`1px solid ${C.border}`}}>Роль</th>
                        <th style={{padding:'12px',textAlign:'left',color:C.textMuted,fontSize:12,textTransform:'uppercase',borderBottom:`1px solid ${C.border}`}}>Объект</th>
                        <th style={{padding:'12px',textAlign:'left',color:C.textMuted,fontSize:12,textTransform:'uppercase',borderBottom:`1px solid ${C.border}`}}>Сущность</th>
                      </tr>
                    </thead>
                    <tbody>
                      {group.rows.map(row => (
                        <tr key={row.id}>
                          <td style={{padding:'12px',color:C.accent,fontWeight:800,whiteSpace:'nowrap',borderBottom:`1px solid ${C.border}`}}>{formatAuditTime(row.createdAt)}</td>
                          <td style={{padding:'12px',color:C.text,whiteSpace:'normal',lineHeight:1.35,borderBottom:`1px solid ${C.border}`}}>{auditActionText(row)}</td>
                          <td style={{padding:'12px',color:C.textSec,borderBottom:`1px solid ${C.border}`}}>{row.userName || '—'}</td>
                          <td style={{padding:'12px',color:C.textSec,borderBottom:`1px solid ${C.border}`}}>{roleLabels[row.userRole] || row.userRole || '—'}</td>
                          <td style={{padding:'12px',color:C.textSec,borderBottom:`1px solid ${C.border}`}}>{row.projectName || '—'}</td>
                          <td style={{padding:'12px',color:C.textSec,borderBottom:`1px solid ${C.border}`}}>{row.entityType || '—'}{row.entityId ? ` №${row.entityId}` : ''}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          ))}
        </div>
      )}

      {filteredRows.length > visibleRows.length && (
        <button
          type="button"
          onClick={() => setVisibleCount(count => count + (isMobile ? 40 : 80))}
          style={{
            marginTop:18,
            width:isMobile ? '100%' : 260,
            height:44,
            borderRadius:12,
            border:`1.5px solid ${C.border}`,
            background:C.bgWhite,
            color:C.text,
            fontWeight:800,
            cursor:'pointer',
          }}
        >
          Показать ещё
        </button>
      )}
    </div>
  );
}

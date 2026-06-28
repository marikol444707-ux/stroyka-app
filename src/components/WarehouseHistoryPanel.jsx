import React from 'react';
import { Download, Search } from 'lucide-react';

export default function WarehouseHistoryPanel({
  history,
  listSearch,
  setListSearch,
  matchSearch,
  exportToExcel,
  C,
  btnG,
  tbl,
  tblH,
  tblC,
  badge,
  isMobile = false,
}) {
  const [visibleRows, setVisibleRows] = React.useState(isMobile ? 40 : 100);
  const [mobileTypeFilter, setMobileTypeFilter] = React.useState('all');
  const rowsStep = isMobile ? 40 : 100;
  const searchedRows = React.useMemo(
    () => (history || []).filter(item => matchSearch(listSearch, item.material, item.project, item.type)),
    [history, listSearch, matchSearch],
  );
  const rows = React.useMemo(() => (
    searchedRows.filter(item => {
      if (mobileTypeFilter === 'income') return String(item.type || '').toLowerCase() === 'приход';
      if (mobileTypeFilter === 'outcome') return String(item.type || '').toLowerCase() !== 'приход';
      return true;
    })
  ), [searchedRows, mobileTypeFilter]);
  const displayedRows = rows.slice(0, visibleRows);
  const hiddenRows = Math.max(0, rows.length - displayedRows.length);
  const mobileStats = React.useMemo(() => {
    const income = searchedRows.filter(item => String(item.type || '').toLowerCase() === 'приход').length;
    const outcome = searchedRows.length - income;
    const projects = new Set(searchedRows.map(item => item.project || 'Без объекта'));
    return { income, outcome, projects: projects.size };
  }, [searchedRows]);
  const mobileGroups = React.useMemo(() => {
    const grouped = new Map();
    displayedRows.forEach(item => {
      const project = item.project || 'Без объекта';
      if (!grouped.has(project)) grouped.set(project, []);
      grouped.get(project).push(item);
    });
    return Array.from(grouped.entries()).map(([project, items]) => ({
      project,
      items,
      income: items.filter(item => String(item.type || '').toLowerCase() === 'приход').length,
      outcome: items.filter(item => String(item.type || '').toLowerCase() !== 'приход').length,
    }));
  }, [displayedRows]);

  React.useEffect(() => {
    setVisibleRows(isMobile ? 40 : 100);
  }, [isMobile, listSearch, history?.length, mobileTypeFilter]);

  const typeFilterButton = (value, label, count) => (
    <button
      type="button"
      onClick={() => setMobileTypeFilter(value)}
      style={{
        border: '1.5px solid ' + (mobileTypeFilter === value ? C.accent : C.border),
        backgroundColor: mobileTypeFilter === value ? C.accent : C.bgWhite,
        color: mobileTypeFilter === value ? 'white' : C.text,
        borderRadius: '999px',
        padding: '8px 10px',
        fontSize: '12px',
        fontWeight: 800,
        minWidth: 0,
        display: 'inline-flex',
        justifyContent: 'center',
        gap: '6px',
      }}
    >
      {label}
      <span style={{opacity: 0.8}}>{count}</span>
    </button>
  );

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap',marginBottom:'15px'}}>
        <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>История движения</b>
        <button onClick={() => exportToExcel((history || []).map(item => ({
          Материал:item.material,
          Тип:item.type,
          Количество:item.quantity,
          Дата:item.date,
          Проект:item.project,
          Кому:item.issuedTo||'',
        })), 'История_склада')} style={{...btnG,...(isMobile ? {width:'100%',justifyContent:'center'} : {})}}><Download size={14}/>Excel</button>
      </div>
      {isMobile ? (
        <div style={{display:'grid',gap:'10px'}}>
          <div style={{padding:'12px',borderRadius:'14px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,display:'grid',gap:'10px'}}>
            <div style={{display:'grid',gridTemplateColumns:'repeat(3,minmax(0,1fr))',gap:'8px'}}>
              <div>
                <span style={{display:'block',color:C.textMuted,fontSize:'10px',fontWeight:800,textTransform:'uppercase'}}>Записей</span>
                <b style={{display:'block',color:C.text,fontSize:'15px'}}>{searchedRows.length}</b>
              </div>
              <div>
                <span style={{display:'block',color:C.textMuted,fontSize:'10px',fontWeight:800,textTransform:'uppercase'}}>Приход</span>
                <b style={{display:'block',color:C.success,fontSize:'15px'}}>{mobileStats.income}</b>
              </div>
              <div>
                <span style={{display:'block',color:C.textMuted,fontSize:'10px',fontWeight:800,textTransform:'uppercase'}}>Объекты</span>
                <b style={{display:'block',color:C.text,fontSize:'15px'}}>{mobileStats.projects}</b>
              </div>
            </div>
            {typeof setListSearch === 'function' && (
              <div style={{position:'relative'}}>
                <Search size={14} style={{position:'absolute',left:'11px',top:'50%',transform:'translateY(-50%)',color:C.textMuted}}/>
                <input
                  value={listSearch}
                  onChange={event => setListSearch(event.target.value)}
                  placeholder="Найти материал, объект или тип"
                  style={{
                    width:'100%',
                    border:'1.5px solid '+C.border,
                    borderRadius:'12px',
                    backgroundColor:C.bg,
                    color:C.text,
                    padding:'10px 12px 10px 34px',
                    fontSize:'13px',
                    outline:'none',
                  }}
                />
              </div>
            )}
            <div style={{display:'grid',gridTemplateColumns:'repeat(3,minmax(0,1fr))',gap:'8px'}}>
              {typeFilterButton('all', 'Все', searchedRows.length)}
              {typeFilterButton('income', 'Приход', mobileStats.income)}
              {typeFilterButton('outcome', 'Расход', mobileStats.outcome)}
            </div>
          </div>
          {mobileGroups.map((group, groupIndex) => (
            <details key={group.project} open={groupIndex === 0 || mobileGroups.length === 1} style={{border:'1.5px solid '+C.border,borderRadius:'14px',backgroundColor:C.bgWhite,overflow:'hidden'}}>
              <summary style={{listStyle:'none',padding:'12px',display:'grid',gap:'5px',cursor:'pointer'}}>
                <b style={{color:C.text,fontSize:'13px',lineHeight:1.25,overflowWrap:'anywhere'}}>{group.project}</b>
                <span style={{color:C.textMuted,fontSize:'11px'}}>
                  {group.items.length} движ. · приход {group.income} · расход {group.outcome}
                </span>
              </summary>
              <div style={{display:'grid',gap:'8px',padding:'0 10px 10px'}}>
                {group.items.map((item, index) => {
                  const isIncome = String(item.type || '').toLowerCase() === 'приход';
                  return (
                    <div key={item.id || `${group.project}-${index}`} style={{padding:'10px',borderRadius:'11px',backgroundColor:C.bg,border:'1px solid '+C.border,display:'grid',gap:'8px'}}>
                      <div style={{display:'flex',justifyContent:'space-between',gap:'8px',alignItems:'flex-start'}}>
                        <b
                          title={item.material || 'Материал'}
                          style={{
                            color:C.text,
                            fontSize:'13px',
                            lineHeight:1.25,
                            minWidth:0,
                            overflow:'hidden',
                            display:'-webkit-box',
                            WebkitLineClamp:2,
                            WebkitBoxOrient:'vertical',
                          }}
                        >
                          {item.material || 'Материал'}
                        </b>
                        <span style={badge(isIncome?C.success:C.danger,isIncome?C.successLight:C.dangerLight,isIncome?C.successBorder:C.dangerBorder)}>{item.type || 'движение'}</span>
                      </div>
                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',fontSize:'12px',color:C.textSec}}>
                        <span><b style={{color:C.text}}>Кол-во:</b> {item.quantity || '—'}</span>
                        <span><b style={{color:C.text}}>Дата:</b> {item.date || '—'}</span>
                        {item.issuedTo && <span style={{gridColumn:'1 / -1',overflowWrap:'anywhere'}}><b style={{color:C.text}}>Кому:</b> {item.issuedTo}</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </details>
          ))}
          {!rows.length && (
            <div style={{padding:'18px',borderRadius:'12px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,color:C.textMuted,textAlign:'center'}}>
              {searchedRows.length ? 'По выбранному фильтру движений нет' : 'История пуста'}
            </div>
          )}
        </div>
      ) : (
      <table style={tbl}>
        <thead>
          <tr><th style={tblH}>Материал</th><th style={tblH}>Тип</th><th style={tblH}>Кол-во</th><th style={tblH}>Проект</th><th style={tblH}>Дата</th></tr>
        </thead>
        <tbody>
          {displayedRows.map((item, index) => (
            <tr key={index}>
              <td style={tblC}>{item.material}</td>
              <td style={tblC}><span style={badge(item.type==='приход'?C.success:C.danger,item.type==='приход'?C.successLight:C.dangerLight,item.type==='приход'?C.successBorder:C.dangerBorder)}>{item.type}</span></td>
              <td style={tblC}>{item.quantity}</td>
              <td style={tblC}>{item.project}</td>
              <td style={tblC}>{item.date}</td>
            </tr>
          ))}
        </tbody>
      </table>
      )}
      {hiddenRows > 0 && (
        <button
          type="button"
          onClick={() => setVisibleRows(limit => Math.min(rows.length, limit + rowsStep))}
          style={{...btnG, width:'100%', justifyContent:'center', marginTop:'10px'}}
        >
          Показать ещё {Math.min(hiddenRows, rowsStep)} записей
        </button>
      )}
    </div>
  );
}

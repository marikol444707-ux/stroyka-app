import React from 'react';
import { Building2, RefreshCw } from 'lucide-react';
import { C as DEFAULT_C } from '../../constants/uiTheme';

const asCompanyId = (value) => {
  const id = Number(value);
  return Number.isFinite(id) && id > 0 ? id : null;
};

export default function CompanyContextSwitcher({
  C,
  companyContext,
  dashboard = false,
  isMobile = false,
}) {
  const theme = C || DEFAULT_C;
  const ctx = companyContext || {};
  const companies = Array.isArray(ctx.companies) ? ctx.companies : [];
  if (!companies.length && !ctx.loading && !ctx.error) return null;

  const phoneLike = Boolean(isMobile);
  const canUseAll = Boolean(ctx.canUseAllCompanies);
  const currentValue = ctx.mode === 'all_companies'
    ? 'all'
    : String(ctx.selectedCompanyId || asCompanyId(ctx.selectedCompany?.companyId) || '');
  const selectedCompanyName = ctx.mode === 'all_companies'
    ? 'Все компании'
    : (ctx.selectedCompany?.companyName || ctx.selectedCompany?.shortName || companies[0]?.companyName || 'Компания');
  const bg = dashboard ? 'rgba(30,41,59,.78)' : theme.bgGray;
  const border = dashboard ? '1px solid rgba(148,163,184,.18)' : '1.5px solid ' + theme.border;
  const color = dashboard ? '#cbd5e1' : theme.textSec;
  const textColor = dashboard ? '#f8fafc' : theme.text;
  const selectBg = dashboard ? 'rgba(15,23,42,.82)' : theme.bgWhite;
  const disabled = ctx.loading || typeof ctx.setSelectedCompanyId !== 'function';

  return (
    <div
      style={{
        display:'flex',
        alignItems:'center',
        gap:'8px',
        flex:'0 1 auto',
        minWidth:0,
        maxWidth:phoneLike?'100%':'320px',
        padding:phoneLike?'7px 9px':'7px 10px',
        background:bg,
        border,
        borderRadius:'12px',
        color,
      }}
      title={ctx.error || selectedCompanyName}
    >
      <Building2 size={17} color={dashboard ? '#fdba74' : '#f97316'} style={{flex:'0 0 auto'}}/>
      <span style={{fontSize:'12px',fontWeight:800,color:textColor,whiteSpace:'nowrap',display:phoneLike?'none':'inline'}}>
        Компания
      </span>
      <select
        value={currentValue}
        disabled={disabled}
        onChange={(event) => ctx.setSelectedCompanyId?.(event.target.value)}
        style={{
          border:'none',
          outline:'none',
          background:selectBg,
          color:textColor,
          fontSize:'12px',
          fontWeight:800,
          minWidth:phoneLike?'128px':'150px',
          maxWidth:phoneLike?'calc(100vw - 150px)':'210px',
          overflow:'hidden',
          textOverflow:'ellipsis',
          borderRadius:'8px',
          padding:'6px 8px',
          cursor:disabled?'default':'pointer',
        }}
      >
        {!companies.length && <option value="">{ctx.loading ? 'Загрузка' : 'Компания'}</option>}
        {canUseAll && <option value="all">Все компании</option>}
        {companies.map((company) => {
          const id = asCompanyId(company.companyId);
          if (!id) return null;
          const name = company.shortName || company.companyName || `Компания #${id}`;
          return <option key={id} value={String(id)}>{name}</option>;
        })}
      </select>
      {ctx.loading && <RefreshCw size={14} style={{flex:'0 0 auto',opacity:.75}}/>}
      {ctx.error && <span style={{fontSize:'12px',fontWeight:800,color:'#ef4444'}}>!</span>}
    </div>
  );
}

// Colors are read from CSS variables in App.css.
// Theme switching uses document.documentElement.dataset.theme = 'light'|'dark'.
export const C = {
  bg: 'var(--c-bg)',
  bgWhite: 'var(--c-bg-white)',
  bgGray: 'var(--c-bg-gray)',
  border: 'var(--c-border)',
  borderDark: 'var(--c-border-dark)',
  text: 'var(--c-text)',
  textSec: 'var(--c-text-sec)',
  textMuted: 'var(--c-text-muted)',
  accent: 'var(--c-accent)',
  accentDark: 'var(--c-accent-dark)',
  accentLight: 'var(--c-accent-light)',
  accentBorder: 'var(--c-accent-border)',
  success: 'var(--c-success)',
  successLight: 'var(--c-success-light)',
  successBorder: 'var(--c-success-border)',
  danger: 'var(--c-danger)',
  dangerLight: 'var(--c-danger-light)',
  dangerBorder: 'var(--c-danger-border)',
  warning: 'var(--c-warning)',
  warningLight: 'var(--c-warning-light)',
  warningBorder: 'var(--c-warning-border)',
  info: 'var(--c-info)',
  infoLight: 'var(--c-info-light)',
  infoBorder: 'var(--c-info-border)',
  purple: 'var(--c-purple)',
  purpleLight: 'var(--c-purple-light)',
  sidebar: 'var(--c-sidebar)',
  sidebarHover: 'var(--c-sidebar-hover)',
};

export const inp = {width:'100%',padding:'10px 12px',marginBottom:'10px',border:'1.5px solid '+C.border,borderRadius:'8px',boxSizing:'border-box',fontSize:'14px',outline:'none',backgroundColor:C.bgWhite,color:C.text,transition:'border-color 0.2s'};
export const btnO = {padding:'9px 18px',background:'linear-gradient(135deg,#f97316,#ea580c)',color:'white',border:'none',borderRadius:'8px',cursor:'pointer',fontSize:'13px',fontWeight:'600',display:'inline-flex',alignItems:'center',gap:'6px'};
export const btnG = {padding:'7px 14px',backgroundColor:C.bgGray,color:C.textSec,border:'1.5px solid '+C.border,borderRadius:'8px',cursor:'pointer',fontSize:'13px',display:'inline-flex',alignItems:'center',gap:'6px'};
export const btnR = {padding:'7px 14px',backgroundColor:C.danger,color:'white',border:'1.5px solid '+C.danger,borderRadius:'8px',cursor:'pointer',fontSize:'13px',fontWeight:'600',display:'inline-flex',alignItems:'center',gap:'6px'};
export const btnGr = {padding:'7px 14px',backgroundColor:C.success,color:'white',border:'1.5px solid '+C.success,borderRadius:'8px',cursor:'pointer',fontSize:'13px',fontWeight:'600',display:'inline-flex',alignItems:'center',gap:'6px'};
export const btnB = {padding:'7px 14px',backgroundColor:C.info,color:'white',border:'1.5px solid '+C.info,borderRadius:'8px',cursor:'pointer',fontSize:'13px',fontWeight:'600',display:'inline-flex',alignItems:'center',gap:'6px'};
export const btnDisabledReadable = {background:'none',backgroundColor:'#334155',color:'#f8fafc',border:'1.5px solid #64748b',cursor:'not-allowed',opacity:1};
export const btnState = (base, disabled=false, overrides={}) => ({...base,...overrides,...(disabled?btnDisabledReadable:{})});
export const card = {backgroundColor:C.bgWhite,borderRadius:'12px',border:'1.5px solid '+C.border,overflow:'hidden'};
export const badge = (color,bg,border) => ({backgroundColor:bg,color:color,border:'1.5px solid '+border,padding:'3px 10px',borderRadius:'20px',fontSize:'11px',fontWeight:'600',display:'inline-flex',alignItems:'center',gap:'4px'});
export const aiNotice = {marginBottom:'14px',padding:'12px 14px',backgroundColor:'#ecfdf5',border:'1.5px solid #10b981',borderRadius:'10px',display:'flex',alignItems:'flex-start',gap:'10px',boxShadow:'0 1px 0 rgba(16,185,129,0.08)'};
export const aiNoticeIcon = {fontSize:'20px',lineHeight:'1.2',flex:'0 0 auto'};
export const aiNoticeText = {fontSize:'13px',color:'#064e3b',lineHeight:1.45,fontWeight:'500'};
export const tbl = {width:'100%',borderCollapse:'collapse',fontSize:'13px'};
export const tblH = {padding:'8px 12px',backgroundColor:C.bg,color:C.textSec,fontWeight:'600',fontSize:'11px',textTransform:'uppercase',borderBottom:'1.5px solid '+C.border,textAlign:'left'};
export const tblC = {padding:'8px 12px',borderBottom:'1px solid '+C.border,color:C.text,fontSize:'13px'};

export const detectMobileLayout = () => {
  if (typeof window === 'undefined') return false;
  const width = window.visualViewport?.width || window.innerWidth || 0;
  const coarsePointer = typeof window.matchMedia === 'function' && window.matchMedia('(pointer: coarse)').matches;
  const mobileUa = typeof navigator !== 'undefined' && /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || '');
  return width < 768 || ((coarsePointer || mobileUa) && width < 1100);
};

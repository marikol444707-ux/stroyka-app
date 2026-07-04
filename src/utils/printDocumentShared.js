export const companyTitle = (companyRequisites = {}, companyName = '', fallback = '_____') => (
  companyRequisites.fullName || companyRequisites.shortName || companyName || fallback
);

const MONTHS_RU = [
  'января',
  'февраля',
  'марта',
  'апреля',
  'мая',
  'июня',
  'июля',
  'августа',
  'сентября',
  'октября',
  'ноября',
  'декабря',
];

export const formatPrescriptionDate = (value) => {
  if (!value) return '«___» __________ 20__ г.';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `«${String(date.getDate()).padStart(2, '0')}» ${MONTHS_RU[date.getMonth()]} ${date.getFullYear()} г.`;
};

export const formatShortDate = (value) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${String(date.getDate()).padStart(2, '0')}.${String(date.getMonth() + 1).padStart(2, '0')}.${date.getFullYear()}`;
};

export const formatHiddenActDate = (value) => {
  if (!value) return '«___» __________ 20__ г.';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `«${String(date.getDate()).padStart(2, '0')}» ${MONTHS_RU[date.getMonth()]} ${date.getFullYear()} г.`;
};

export const formatJournalDate = (value) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${String(date.getDate()).padStart(2, '0')}.${String(date.getMonth() + 1).padStart(2, '0')}.${date.getFullYear()}`;
};

export const fmtDocMoney = (value) => `${Math.round(Number(value || 0)).toLocaleString('ru-RU')} ₽`;

export const directorDocStyles = () => '<style>'
  + '.dir-title{text-align:center;font-weight:800;font-size:17px;margin:0 0 4px;color:#111827}'
  + '.dir-sub{text-align:center;font-size:11px;color:#6b7280;margin:0 0 16px}'
  + '.dir-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:12px 0 16px}'
  + '.dir-card{border:1px solid #cbd5e1;border-radius:8px;padding:8px;background:#f8fafc}'
  + '.dir-card span{display:block;color:#64748b;font-size:10px}'
  + '.dir-card b{display:block;font-size:15px;margin-top:2px;color:#111827}'
  + '.dir-section{margin-top:18px;border-top:1.5px solid #334155;padding-top:9px;break-inside:avoid}'
  + '.dir-section h3{font-size:13px;margin:0 0 8px;color:#111827}'
  + '.dir-table{width:100%;border-collapse:collapse;font-size:10.5px;margin:6px 0}'
  + '.dir-table th,.dir-table td{border:1px solid #64748b;padding:4px 5px;vertical-align:top}'
  + '.dir-table th{background:#f1f5f9;font-weight:700;color:#111827}'
  + '.dir-risk{border:1px solid #f59e0b;background:#fffbeb;border-radius:6px;padding:6px 8px;margin:5px 0;font-size:11px}'
  + '.dir-danger{border-color:#ef4444;background:#fef2f2}'
  + '.dir-ok{border:1px solid #22c55e;background:#f0fdf4;border-radius:6px;padding:6px 8px;margin:5px 0;font-size:11px}'
  + '.dir-muted{color:#64748b}'
  + '</style>';

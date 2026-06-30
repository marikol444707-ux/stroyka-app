export const docEsc = (value) => String(value ?? '')
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;');

export const normalizeDocDate = (value) => {
  const raw = String(value || '').trim();
  if (!raw) return '';

  let match = raw.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (match) return `${match[1]}-${match[2].padStart(2, '0')}-${match[3].padStart(2, '0')}`;

  match = raw.match(/(\d{1,2})[./-](\d{1,2})[./-](\d{4})/);
  if (match) return `${match[3]}-${match[2].padStart(2, '0')}-${match[1].padStart(2, '0')}`;

  const parsed = new Date(raw);
  if (!Number.isNaN(parsed.getTime())) {
    const yyyy = parsed.getFullYear();
    const mm = String(parsed.getMonth() + 1).padStart(2, '0');
    const dd = String(parsed.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  }

  return raw.split('T')[0].split(' ')[0];
};

export const workDocDate = (work = {}) => (
  normalizeDocDate(work.date) || normalizeDocDate(work.confirmedAt)
);

export const parseWorkMaterials = (value) => {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  if (typeof value === 'string') {
    const text = value.trim();
    if (!text) return [];
    try {
      const parsed = JSON.parse(text);
      return Array.isArray(parsed) ? parsed : [parsed];
    } catch (e) {
      return [{ name: text }];
    }
  }
  return [value];
};

export const photoCount = (value) => (
  String(value || '').split(/[,\s;]+/).filter(Boolean).length
);

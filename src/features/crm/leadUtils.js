const PUBLIC_COMPARISON_LABEL = 'Ссылка на сравнение:';
const PUBLIC_SITE_ORIGINS = new Set(['https://stroyka26.pro', 'https://www.stroyka26.pro']);

export const publicComparisonUrlFromLeadNotes = (notes = '') => {
  const line = String(notes).split(/\r?\n/).find(value => value.trim().startsWith(PUBLIC_COMPARISON_LABEL));
  const rawUrl = line?.trim().slice(PUBLIC_COMPARISON_LABEL.length).trim() || '';
  if (!rawUrl) return '';
  try {
    const url = new URL(rawUrl);
    if (!PUBLIC_SITE_ORIGINS.has(url.origin) || url.pathname !== '/') return '';
    if (!url.searchParams.get('project') || !url.searchParams.get('compare')) return '';
    return url.toString();
  } catch {
    return '';
  }
};

export const buildLeadPayload = (lead = {}, { createdBy = '', createdAt = '', includeCreateMeta = false } = {}) => {
  const body = {
    name: lead.name || '',
    phone: lead.phone || '',
    email: lead.email || '',
    source: lead.source || '',
    budget: Number(lead.budget) || 0,
    notes: lead.notes || '',
    stage: lead.stage || 'Новый',
    photoUrl: lead.photoUrl || '',
    leadType: lead.leadType || 'Клиент',
    counterpartyType: lead.counterpartyType || '',
    responsibleName: lead.responsibleName || '',
    nextContactAt: lead.nextContactAt || '',
    address: lead.address || '',
    workType: lead.workType || '',
    area: Number(lead.area) || 0,
    priority: lead.priority || 'Обычный',
    lossReason: lead.lossReason || '',
    legalForm: lead.legalForm || '',
    passportData: lead.passportData || '',
    inn: lead.inn || '',
    kpp: lead.kpp || '',
    ogrn: lead.ogrn || '',
    legalAddress: lead.legalAddress || '',
    contractSubject: lead.contractSubject || '',
    bank: lead.bank || '',
    bik: lead.bik || '',
    bankAccount: lead.bankAccount || '',
    corrAccount: lead.corrAccount || '',
    signerName: lead.signerName || '',
    signerBasis: lead.signerBasis || '',
    estimateId: Number(lead.estimateId) || null,
    documentStatus: lead.documentStatus || 'Не собраны',
    reviewStatus: lead.reviewStatus || 'Новая',
  };

  return includeCreateMeta ? { ...body, createdBy, createdAt } : body;
};

export const CRM_LEAD_LINK_KEY = 'stroykaOpenCrmLead';

export const rememberCrmLeadFromLocation = (search, storage) => {
  if (!storage) return '';
  try {
    const params = new URLSearchParams(String(search || '').replace(/^\?/, ''));
    const leadId = String(params.get('lead') || '');
    if (params.get('page') !== 'crm' || !/^\d+$/.test(leadId)) return '';
    storage.setItem(CRM_LEAD_LINK_KEY, leadId);
    return leadId;
  } catch {
    return '';
  }
};

export const takeRememberedCrmLead = (storage) => {
  if (!storage) return '';
  try {
    const leadId = String(storage.getItem(CRM_LEAD_LINK_KEY) || '');
    if (!/^\d+$/.test(leadId)) return '';
    storage.removeItem(CRM_LEAD_LINK_KEY);
    return leadId;
  } catch {
    return '';
  }
};

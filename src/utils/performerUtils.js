export const normalizePersonKey = (value) => String(value || '').trim().toLowerCase().replace(/\s+/g, ' ');

export const staffPassportText = (staff = {}) => {
  const number = [staff.passportSeries, staff.passportNumber].filter(Boolean).join(' ').trim();
  const issued = [staff.passportIssuedBy, staff.passportIssuedDate].filter(Boolean).join(', ');
  return [number, issued].filter(Boolean).join('; ');
};

export const performerMissingRequisites = (performer = {}, contractType = '') => {
  const type = String(contractType || performer.contractType || '').toLowerCase();
  const missing = [];
  if (!performer.fullName || performer.fullName === 'Исполнитель не выбран') missing.push('ФИО/название');
  if (!performer.inn) missing.push('ИНН');
  if ((type.includes('самозан') || type.includes('гпх')) && !performer.passport) missing.push('паспорт');
  if (type.includes('ип') && !performer.ogrnip) missing.push('ОГРНИП');
  if (!type.includes('труд') && !performer.bankAccount) missing.push('расчётный счёт');
  if (!type.includes('труд') && !performer.bankName) missing.push('банк');
  return missing;
};

export const contractRequisitesWarning = (performer = {}, contractType = '') => {
  const missing = performerMissingRequisites(performer, contractType);
  return missing.length
    ? 'Не хватает реквизитов: ' + missing.join(', ') + '. Заполните карточку исполнителя, чтобы договор печатался без пустых полей.'
    : '';
};

export const findStaffForPerformer = (contract = {}, staffRows = []) => {
  const id = Number(contract.masterId || contract.contractorId || 0);
  if (id) {
    const byId = (staffRows || []).find(s => Number(s.id) === id);
    if (byId) return byId;
  }
  const name = normalizePersonKey(contract.masterName || contract.brigadeName || contract.performerName);
  if (!name) return null;
  return (staffRows || []).find(s => normalizePersonKey(s.name) === name || normalizePersonKey(s.brigade) === name) || null;
};

export const findUserForStaff = (staffRow, users = []) => {
  if (!staffRow) return null;
  const emails = [staffRow.emailWork, staffRow.emailPersonal, staffRow.email]
    .map(e => String(e || '').trim().toLowerCase())
    .filter(Boolean);
  const byEmail = (users || []).find(u => emails.includes(String(u.email || '').trim().toLowerCase()));
  if (byEmail) return byEmail;
  const name = normalizePersonKey(staffRow.name);
  return (users || []).find(u => normalizePersonKey(u.name) === name) || null;
};

export const findProfileForPerformer = (contract = {}, staffRow = null, preferredProfile = null, masterProfiles = [], users = []) => {
  if (preferredProfile) return preferredProfile;
  const id = Number(contract.masterId || contract.contractorId || 0);
  const userRow = findUserForStaff(staffRow, users);
  const name = normalizePersonKey(contract.masterName || contract.brigadeName || staffRow?.name);
  return (masterProfiles || []).find(p => Number(p.userId) === id)
    || (userRow ? (masterProfiles || []).find(p => Number(p.userId) === Number(userRow.id)) : null)
    || (name ? (masterProfiles || []).find(p => normalizePersonKey(p.fullName) === name) : null)
    || null;
};

export const resolveContractPerformer = ({
  contract = {},
  preferredProfile = null,
  staffRows = [],
  users = [],
  masterProfiles = [],
} = {}) => {
  const staffRow = findStaffForPerformer(contract, staffRows);
  const userRow = findUserForStaff(staffRow, users);
  const profile = findProfileForPerformer(contract, staffRow, preferredProfile, masterProfiles, users);
  const type = contract.contractType || contract.contractorType || profile?.contractType || staffRow?.employmentType || 'ГПХ';
  const fullName = profile?.fullName || staffRow?.name || contract.masterName || contract.brigadeName || 'Исполнитель не выбран';
  return {
    ...(staffRow || {}),
    ...(profile || {}),
    userId: profile?.userId || userRow?.id || staffRow?.userId || contract.masterId || contract.contractorId || '',
    staffId: staffRow?.id || contract.masterId || contract.contractorId || '',
    fullName,
    name: fullName,
    brigadeName: contract.brigadeName || staffRow?.brigade || fullName,
    passport: profile?.passport || staffPassportText(staffRow) || '',
    inn: profile?.inn || staffRow?.inn || '',
    bankAccount: profile?.bankAccount || staffRow?.bankAccount || '',
    bankName: profile?.bankName || staffRow?.bankName || '',
    ogrnip: profile?.ogrnip || staffRow?.ogrnip || '',
    phone: profile?.phone || staffRow?.phone || '',
    specialization: profile?.specialization || staffRow?.specialization || staffRow?.role || '',
    contractType: type,
    _staff: staffRow,
    _user: userRow,
    _profile: profile,
  };
};

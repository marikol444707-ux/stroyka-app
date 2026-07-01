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

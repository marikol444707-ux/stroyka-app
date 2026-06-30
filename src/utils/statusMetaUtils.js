import { C } from '../constants/uiTheme';

export const estimateReconciliationStatusView = (status) => {
  if (status === 'Утверждена') return {label:'Утверждена', color:C.success, bg:C.successLight, border:C.successBorder};
  if (status === 'Отклонена') return {label:'Отклонена', color:C.danger, bg:C.dangerLight, border:C.dangerBorder};
  if (status === 'На проверке') return {label:'На проверке', color:C.warning, bg:C.warningLight, border:C.warningBorder};
  return {label:status || 'Черновик', color:C.info, bg:C.infoLight, border:C.infoBorder};
};

export const measurementEstimateStatusMeta = (status) => {
  if (status==='Сходится') return {color:C.success,bg:C.successLight,border:C.successBorder};
  if (status==='Сверх сметы') return {color:C.danger,bg:C.dangerLight,border:C.dangerBorder};
  if (status==='В смете больше') return {color:C.warning,bg:C.warningLight,border:C.warningBorder};
  if (status==='Нет обмера') return {color:C.warning,bg:C.warningLight,border:C.warningBorder};
  return {color:C.info,bg:C.infoLight,border:C.infoBorder};
};

export const workJournalEstimateStatusMeta = (status) => {
  if (status==='Из сметы' || status==='Найдено') return {color:C.success,bg:C.successLight,border:C.successBorder};
  if (status==='Превышение объёма' || status==='Вне сметы') return {color:C.danger,bg:C.dangerLight,border:C.dangerBorder};
  if (status==='На проверку' || status==='Нет активной сметы') return {color:C.warning,bg:C.warningLight,border:C.warningBorder};
  return {color:C.info,bg:C.infoLight,border:C.infoBorder};
};

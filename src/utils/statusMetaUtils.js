import { C } from '../constants/uiTheme';
import { activeEstimateFromList } from './estimateUtils';
import { fmtMeasure, toNum } from './measureUtils';

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

export const estimateStatusView = (est, groupItems = []) => {
  const status = est?.status || 'Черновик';
  if (status === 'Активная') return {label:'Активная', color:C.success, bg:C.successLight, border:C.successBorder};
  if (status === 'Архив') return {label:'Архив', color:C.textMuted, bg:C.bgGray, border:C.border};
  if (activeEstimateFromList(groupItems)?.id === est?.id) return {label:'Используется', color:C.info, bg:C.infoLight, border:C.infoBorder};
  return {label:'Черновик', color:C.warning, bg:C.warningLight, border:C.warningBorder};
};

export const isOpenAiStatus = (status) => !['Закрыто', 'Отклонено'].includes(status || '');

export const aiSeverityMeta = (severity) => {
  const value = severity || 'Проверить';
  if (value === 'Критично') return {color:C.danger,bg:C.dangerLight,border:C.dangerBorder};
  if (value === 'Не хватает данных') return {color:C.warning,bg:C.warningLight,border:C.warningBorder};
  return {color:C.info,bg:C.infoLight,border:C.infoBorder};
};

export const materialNormStatus = (material) => {
  const norm = toNum(material?.normQuantity);
  const qty = toNum(material?.quantity);
  if (!norm || !qty) return null;
  const tolerance = Math.max(0.001, norm * 0.1);
  const diff = qty - norm;
  if (Math.abs(diff) <= tolerance) return {label:material.autoNorm ? 'по норме' : 'около нормы', color:C.success, bg:C.successLight, border:C.successBorder};
  if (diff > 0) return {label:'перерасход ' + fmtMeasure(diff, material.unit), color:C.danger, bg:C.dangerLight, border:C.dangerBorder};
  return {label:'экономия ' + fmtMeasure(Math.abs(diff), material.unit), color:C.info, bg:C.infoLight, border:C.infoBorder};
};

export const materialControlStatus = (row = {}) => {
  if (row.reviewRequired || row.invalidPlanCount > 0 || row.unitMismatch) return {label:'Проверить', color:C.warning, bg:C.warningLight, border:C.warningBorder};
  if (row.stockMismatch) return {label:'Расхождение склада', color:C.danger, bg:C.dangerLight, border:C.dangerBorder};
  if (row.issued > 0 && row.usedWithoutIssue > 0) return {label:'Списано сверх выдачи', color:C.danger, bg:C.dangerLight, border:C.dangerBorder};
  if (row.usedOverControlQty > 0) return {label:'Расход сверх нормы', color:C.danger, bg:C.dangerLight, border:C.dangerBorder};
  if (row.usedOverEstimateQty > 0) return {label:'Списано сверх сметы', color:C.warning, bg:C.warningLight, border:C.warningBorder};
  if (row.isOutsideEstimate) return {label:'Вне сметы', color:C.danger, bg:C.dangerLight, border:C.dangerBorder};
  if (row.normWithoutEstimateQty > 0) return {label:'Норма без сметы', color:C.warning, bg:C.warningLight, border:C.warningBorder};
  if (row.normOverEstimateQty > 0) return {label:'Норма выше сметы', color:C.warning, bg:C.warningLight, border:C.warningBorder};
  if (row.toBuy > 0) return {label:'Докупить', color:C.warning, bg:C.warningLight, border:C.warningBorder};
  if (row.shortage > 0) return {label:'Закрывается', color:C.info, bg:C.infoLight, border:C.infoBorder};
  if (row.masterBalance > 0) return {label:'У мастеров', color:C.info, bg:C.infoLight, border:C.infoBorder};
  if (row.over > 0) return {label:'Сверх сметы', color:C.info, bg:C.infoLight, border:C.infoBorder};
  return {label:'Закрыто', color:C.success, bg:C.successLight, border:C.successBorder};
};

export const materialNormCoverageMeta = (status) => {
  if (['Норма применена', 'Поправка объекта', 'Поправка сметы'].includes(status)) return {color:C.success,bg:C.successLight,border:C.successBorder};
  if (status === 'Норма не нужна') return {color:C.textSec,bg:C.bgGray,border:C.border};
  if (status === 'Некорректное количество') return {color:C.danger,bg:C.dangerLight,border:C.dangerBorder};
  if (status === 'Нет нормы' || status === 'Материал без работы' || status === 'Материал без количества' || status === 'Нехватка материала по норме') return {color:C.warning,bg:C.warningLight,border:C.warningBorder};
  return {color:C.info,bg:C.infoLight,border:C.infoBorder};
};

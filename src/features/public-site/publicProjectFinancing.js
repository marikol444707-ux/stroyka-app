const clampNumber = (value, min, max, fallback) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return fallback;
  return Math.min(max, Math.max(min, number));
};

const formatYears = (years) => {
  const lastTwo = years % 100;
  const last = years % 10;
  if (lastTwo >= 11 && lastTwo <= 14) return `${years} лет`;
  if (last === 1) return `${years} год`;
  if (last >= 2 && last <= 4) return `${years} года`;
  return `${years} лет`;
};

const formatMonths = (months) => {
  const lastTwo = months % 100;
  const last = months % 10;
  if (lastTwo >= 11 && lastTwo <= 14) return `${months} месяцев`;
  if (last === 1) return `${months} месяц`;
  if (last >= 2 && last <= 4) return `${months} месяца`;
  return `${months} месяцев`;
};

const getAnnuityPayment = (principal, annualRate, months) => {
  if (!principal || !months) return 0;
  const monthlyRate = annualRate / 100 / 12;
  if (!monthlyRate) return principal / months;
  const factor = Math.pow(1 + monthlyRate, months);
  return principal * ((monthlyRate * factor) / (factor - 1));
};

export const calculatePublicProjectFinancing = ({
  mode = 'mortgage',
  estimateMin = 0,
  estimateMax = 0,
  downPaymentPercent,
  term,
  annualRate,
} = {}) => {
  const financingMode = mode === 'installment' ? 'installment' : 'mortgage';
  const min = Math.max(0, Number(estimateMin) || 0);
  const max = Math.max(min, Number(estimateMax) || min);
  const downPercent = clampNumber(
    downPaymentPercent,
    0,
    90,
    financingMode === 'mortgage' ? 20 : 30,
  );
  const termValue = Math.round(clampNumber(
    term,
    financingMode === 'mortgage' ? 1 : 2,
    financingMode === 'mortgage' ? 30 : 36,
    financingMode === 'mortgage' ? 20 : 12,
  ));
  const rate = financingMode === 'mortgage'
    ? clampNumber(annualRate, 0, 50, 20)
    : null;
  const months = financingMode === 'mortgage' ? termValue * 12 : termValue;
  const financedShare = (100 - downPercent) / 100;
  const financedMin = Math.round(min * financedShare);
  const financedMax = Math.round(max * financedShare);
  const monthlyPayment = financingMode === 'mortgage'
    ? (amount) => getAnnuityPayment(amount, rate, months)
    : (amount) => amount / months;

  return {
    status: 'indicative',
    mode: financingMode,
    modeLabel: financingMode === 'mortgage' ? 'Ипотека на строительство' : 'Рассрочка по договору',
    downPaymentPercent: downPercent,
    downPaymentMin: Math.round(min - financedMin),
    downPaymentMax: Math.round(max - financedMax),
    financedMin,
    financedMax,
    term: termValue,
    termLabel: financingMode === 'mortgage' ? formatYears(termValue) : formatMonths(termValue),
    annualRate: rate,
    monthlyMin: Math.round(monthlyPayment(financedMin)),
    monthlyMax: Math.round(monthlyPayment(financedMax)),
  };
};

export const serializePublicProjectFinancing = (financing, formatMoney = null) => {
  if (!financing || financing.status !== 'indicative') return null;
  const formatRange = (min, max, suffix = '') => {
    if (typeof formatMoney !== 'function') return undefined;
    return `${formatMoney(min)} - ${formatMoney(max)}${suffix}`;
  };

  return {
    status: 'indicative',
    mode: financing.mode,
    modeLabel: financing.modeLabel,
    downPaymentPercent: financing.downPaymentPercent,
    downPaymentMin: financing.downPaymentMin,
    downPaymentMax: financing.downPaymentMax,
    downPaymentRange: formatRange(financing.downPaymentMin, financing.downPaymentMax),
    financedMin: financing.financedMin,
    financedMax: financing.financedMax,
    term: financing.term,
    termLabel: financing.termLabel,
    annualRate: financing.annualRate,
    monthlyMin: financing.monthlyMin,
    monthlyMax: financing.monthlyMax,
    monthlyRange: formatRange(financing.monthlyMin, financing.monthlyMax, '/мес.'),
  };
};

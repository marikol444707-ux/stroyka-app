import { ESTIMATE_PACKAGES } from '../constants/catalogs';

const PACKAGE_RULES = [
  { pkg: 'Кондиционирование', patterns: [/кондиц/i, /\bvrf\b/i, /\bvrv\b/i, /чиллер/i, /фанкойл/i, /сплит/i] },
  { pkg: 'Вентиляция', patterns: [/вентиляц/i, /воздуховод/i, /дымоудален/i, /противодым/i] },
  { pkg: 'Слаботочка', patterns: [/слаботоч/i, /\bскс\b/i, /\bскуд\b/i, /\bапс\b/i, /\bсоуэ\b/i, /пожарн.*сигнал/i, /видеонаблюд/i, /охранн.*сигнал/i] },
  { pkg: 'Электрика', patterns: [/электрик/i, /электромонтаж/i, /освещен/i, /силов/i, /розет/i, /выключател/i, /щит/i, /кабельн/i] },
  { pkg: 'Отопление', patterns: [/отоплен/i, /теплоснабж/i, /радиатор/i, /котел/i, /тепл[ыо]й пол/i] },
  { pkg: 'ВК / канализация', patterns: [/\bвк\b/i, /водоснабж/i, /канализ/i, /водопровод/i, /сантех/i] },
  { pkg: 'Благоустройство', patterns: [/благоустрой/i, /мусор/i, /асфальт/i, /тротуар/i, /бордюр/i, /озеленен/i] },
  { pkg: 'Отделка', patterns: [/отделк/i, /штукатур/i, /шпакл/i, /грунтов/i, /покраск/i, /обои/i, /плитк/i, /керамогранит/i, /линолеум/i, /ламинат/i, /натяжн.*потол/i] },
  { pkg: 'Общестрой', patterns: [/общестро/i, /демонтаж/i, /монолит/i, /бетон/i, /кирпич/i, /кровл/i, /фасад/i, /гкл/i] },
];

const normalizeText = (value) => String(value || '')
  .toLowerCase()
  .replace(/ё/g, 'е')
  .replace(/\s+/g, ' ')
  .trim();

export const normalizeEstimatePackage = (value) => {
  const normalized = String(value || '').trim();
  return ESTIMATE_PACKAGES.includes(normalized) ? normalized : '';
};

export const guessEstimatePackage = (...texts) => {
  const text = normalizeText(texts.filter(Boolean).join(' '));
  if (!text) return '';
  for (const rule of PACKAGE_RULES) {
    if (rule.patterns.some((pattern) => pattern.test(text))) return rule.pkg;
  }
  return '';
};

export const resolveEstimatePackage = (selectedPackage, ...texts) => {
  const explicit = normalizeEstimatePackage(selectedPackage);
  if (explicit && explicit !== 'Основная') return explicit;
  return guessEstimatePackage(...texts) || explicit || 'Основная';
};

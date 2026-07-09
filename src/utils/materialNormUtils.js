import { _normalizeUnit, fmtMeasure, normalizeMeasure, toNum } from './measureUtils';
import { materialLookupText } from './materialMatchUtils';

export const WORK_MATERIAL_NORM_RULES = [
  {id:'plaster_mix', work:['штукатур'], blockWork:['демонтаж','разбор'], material:['штукатур','ротбанд','гипсов'], workUnit:'м2', materialUnit:'кг', qtyPerUnit:8.5, thicknessBaseMm:10, defaultThicknessMm:10, label:'штукатурная смесь 8.5 кг/м2 на 10 мм'},
  {id:'screed_mix', work:['стяжк','наливн'], blockWork:['демонтаж','разбор'], material:['пескобетон','смесь','стяжк'], workUnit:'м2', materialUnit:'кг', qtyPerUnit:18, thicknessBaseMm:10, defaultThicknessMm:40, label:'смесь для стяжки 18 кг/м2 на 10 мм'},
  {id:'putty_mix', work:['шпаклев','шпатлев'], blockWork:['демонтаж','разбор'], material:['шпаклев','шпатлев'], workUnit:'м2', materialUnit:'кг', qtyPerUnit:1.2, label:'шпаклевка 1.2 кг/м2'},
  {id:'tile_glue', work:['плитк','керамогранит','облицов'], blockWork:['демонтаж','разбор'], material:['клей','плиточ'], workUnit:'м2', materialUnit:'кг', qtyPerUnit:4.5, label:'плиточный клей 4.5 кг/м2'},
  {id:'tile_grout', work:['плитк','керамогранит','облицов'], blockWork:['демонтаж','разбор'], material:['затир'], workUnit:'м2', materialUnit:'кг', qtyPerUnit:0.3, label:'затирка 0.3 кг/м2'},
  {id:'paint', work:['окраск','покраск'], blockWork:['демонтаж','разбор'], material:['краск','эмал'], workUnit:'м2', materialUnit:'л', qtyPerUnit:0.2, label:'краска 0.2 л/м2'},
  {id:'primer', work:['грунтов','окраск','шпаклев','шпатлев'], blockWork:['демонтаж','разбор'], material:['грунтов'], workUnit:'м2', materialUnit:'л', qtyPerUnit:0.12, label:'грунтовка 0.12 л/м2'},
  {id:'gkl_sheet', work:['гипсокарт','гкл','обшив'], blockWork:['демонтаж','разбор'], material:['гипсокарт','гкл','лист'], workUnit:'м2', materialUnit:'шт', qtyPerUnit:0.35, label:'ГКЛ 0.35 листа/м2'},
  {id:'gkl_profile', work:['гипсокарт','гкл','обшив'], blockWork:['демонтаж','разбор'], material:['профиль'], workUnit:'м2', materialUnit:'м', qtyPerUnit:1.6, label:'профиль 1.6 м/м2'},
  {id:'gkl_screws', work:['гипсокарт','гкл','обшив'], blockWork:['демонтаж','разбор'], material:['саморез'], workUnit:'м2', materialUnit:'шт', qtyPerUnit:20, label:'саморезы 20 шт/м2'},
  {id:'cable_line', work:['кабел','провод','проклад'], blockWork:['демонтаж','разбор'], material:['кабель','провод','utp','ftp','f-utp','u-utp','кпс','ксвв','кспв','ввг','nym'], workUnit:'м', materialUnit:'м', qtyPerUnit:1.05, label:'кабель 1.05 м на 1 м трассы'},
  {id:'cable_protection', work:['кабел','провод','проклад'], blockWork:['демонтаж','разбор'], material:['гофр','труба пнд','кабель-канал','кабель канал'], workUnit:'м', materialUnit:'м', qtyPerUnit:1.05, label:'защита кабеля 1.05 м на 1 м трассы'},
  {id:'cable_channel_box', work:['короб','кабель-канал','кабель канал','проклад'], blockWork:['демонтаж','разбор'], material:['короб','кабель-канал','кабель канал'], workUnit:'м', materialUnit:'м', qtyPerUnit:1.05, label:'короб/кабель-канал 1.05 м на 1 м трассы'},
  {id:'cable_fasteners', work:['кабел','провод','гофр','кабель-канал','кабель канал','короб','лоток','проклад'], blockWork:['демонтаж','разбор'], material:['скоб','клипс','держатель','хомут','креплен','крепеж'], workUnit:'м', materialUnit:'шт', qtyPerUnit:2, label:'крепеж кабельной трассы 2 шт/м'},
  {id:'junction_box', work:['коробка ответв','распаечн','распределительн короб'], blockWork:['демонтаж','разбор'], material:['коробка ответв','распаечн','распределительн короб'], workUnit:'шт', materialUnit:'шт', qtyPerUnit:1, label:'коробка 1 шт на точку'},
  {id:'luminaire', work:['светильник','табло','транспарант'], blockWork:['демонтаж','разбор'], material:['светильник','табло','транспарант'], workUnit:'шт', materialUnit:'шт', qtyPerUnit:1, label:'светильник/табло 1 шт на точку'},
  {id:'socket_switch', work:['розет','выключател','штепсель'], blockWork:['демонтаж','разбор'], material:['розет','выключател','штепсель'], workUnit:'шт', materialUnit:'шт', qtyPerUnit:1, label:'механизм 1 шт на точку'},
  {id:'electric_panel', work:['щит','шкаф','распределительн'], blockWork:['демонтаж','разбор'], material:['щит','шкаф','бокс распредел'], workUnit:'шт', materialUnit:'шт', qtyPerUnit:1, label:'щит/шкаф 1 шт на точку'},
  {id:'pipe_pp', work:['трубопровод','водоснаб','отоплен'], blockWork:['демонтаж','разбор'], material:['труба полипропилен','трубы полипропилен','полипропилен','ppr','pprc','ppr-c'], workUnit:'м', materialUnit:'м', qtyPerUnit:1.03, label:'труба 1.03 м на 1 м трассы'},
  {id:'pipe_fittings', work:['соединен','сварк','узл','трубопровод'], blockWork:['демонтаж','разбор'], material:['муфта','угольник','угол','тройник','переход','кран','фитинг'], workUnit:'соединений', materialUnit:'шт', qtyPerUnit:1, label:'фитинг 1 шт на соединение'},
  {id:'pipe_clamps', work:['трубопровод','водоснаб','отоплен'], blockWork:['демонтаж','разбор'], material:['хомут','креплен','кронштейн'], workUnit:'м', materialUnit:'шт', qtyPerUnit:1.2, label:'крепление трубы 1.2 шт/м'},
  {id:'pipe_insulation', work:['изоляц','трубопровод'], blockWork:['демонтаж','разбор'], material:['изоляц','энергофлекс','пенополиэтилен'], workUnit:'м', materialUnit:'м', qtyPerUnit:1.05, label:'изоляция трубы 1.05 м/м'},
  {id:'thermal_insulation_board', work:['изоляция изделиями','теплоизоляц','изоляц'], blockWork:['демонтаж','разбор'], material:['пенополиэтилен','минераловат','теплоизоляц','изовер','технониколь','вата'], workUnit:'м2', materialUnit:'м2', qtyPerUnit:1.05, label:'теплоизоляция 1.05 м2/м2'},
  {id:'thermal_insulation_fasteners', work:['изоляция изделиями','теплоизоляц','изоляц'], blockWork:['демонтаж','разбор'], material:['дюбель-гвозд','дюбел','креплен','для теплоизоляции'], workUnit:'м2', materialUnit:'шт', qtyPerUnit:5, label:'крепеж теплоизоляции 5 шт/м2'},
  {id:'radiator_device', work:['радиатор'], blockWork:['демонтаж','разбор'], material:['радиатор'], workUnit:'шт', materialUnit:'шт', qtyPerUnit:1, label:'радиатор 1 шт на прибор'},
  {id:'radiator_mount', work:['радиатор'], blockWork:['демонтаж','разбор'], material:['кронштейн','креплен','крепеж'], workUnit:'шт', materialUnit:'шт', qtyPerUnit:4, label:'крепление радиатора 4 шт на прибор'},
  {id:'radiator_connection_kit', work:['радиатор'], blockWork:['демонтаж','разбор'], material:['комплект монтаж','комплект подключ','подключения радиатор','радиаторный комплект'], workUnit:'шт', materialUnit:'компл', qtyPerUnit:1, label:'комплект подключения радиатора 1 компл/прибор'},
  {id:'plaster_mesh', work:['сетка','штукатур'], blockWork:['демонтаж','разбор'], material:['сетка'], workUnit:'м2', materialUnit:'м2', qtyPerUnit:1.1, label:'штукатурная сетка 1.1 м2/м2'},
  {id:'plaster_beacon', work:['маяк','маяч'], blockWork:['демонтаж','разбор'], material:['маяк','маяч','профиль маяч'], workUnit:'м2', materialUnit:'м', qtyPerUnit:0.85, label:'маячный профиль 0.85 м/м2'},
  {id:'linoleum_sheet', work:['линолеум'], blockWork:['демонтаж','разбор'], material:['линолеум'], workUnit:'м2', materialUnit:'м2', qtyPerUnit:1.02, label:'линолеум 1.02 м2/м2'},
  {id:'linoleum_glue', work:['линолеум'], blockWork:['демонтаж','разбор'], material:['клей','мастик'], workUnit:'м2', materialUnit:'кг', qtyPerUnit:0.5, label:'клей для линолеума 0.5 кг/м2'},
  {id:'pvc_plinth', work:['плинтус'], blockWork:['демонтаж','разбор'], material:['плинтус'], workUnit:'м', materialUnit:'м', qtyPerUnit:1.03, label:'плинтус 1.03 м/м'},
  {id:'plywood_subfloor', work:['фанер','основания полов','оснований полов'], blockWork:['демонтаж','разбор'], material:['фанер'], workUnit:'м2', materialUnit:'м3', qtyPerUnit:0.025, label:'фанера 0.025 м3/м2 основания'},
  {id:'osb_subfloor', work:['фанер','основания полов','оснований полов'], blockWork:['демонтаж','разбор'], material:['osb','осп','древесноструж','ориентированной стружкой'], workUnit:'м2', materialUnit:'м2', qtyPerUnit:2.04, label:'OSB/плита 2.04 м2/м2 основания'},
  {id:'wood_frame', work:['каркас','брус'], blockWork:['демонтаж','разбор'], material:['брус'], workUnit:'м3', materialUnit:'м3', qtyPerUnit:1.05, label:'брус 1.05 м3/м3 каркаса'},
  {id:'door_block', work:['дверн','двер'], blockWork:['демонтаж','разбор','снятие'], material:['блок двер','дверн блок','дверь','полотно'], workUnit:'м2', materialUnit:'м2', qtyPerUnit:1, label:'дверной блок 1 м2/м2'},
  {id:'windowsill', work:['подокон'], blockWork:['демонтаж','разбор'], material:['подокон'], workUnit:'м', materialUnit:'м', qtyPerUnit:1, label:'подоконник 1 м/м'},
  {id:'windowsill_end_caps', work:['подокон'], blockWork:['демонтаж','разбор'], material:['заглушк','торцев','подокон'], workUnit:'м', materialUnit:'шт', qtyPerUnit:1, label:'заглушки подоконника 1 шт/м'},
  {id:'brick_masonry', work:['кладк'], blockWork:['демонтаж','разбор'], material:['кирпич'], workUnit:'м2', materialUnit:'шт', qtyPerUnit:51, label:'кирпич 51 шт/м2 кладки в 1/2 кирпича'},
  {id:'concrete', work:['бетон'], blockWork:['демонтаж','разбор'], material:['бетон'], workUnit:'м3', materialUnit:'м3', qtyPerUnit:1, label:'бетон 1 м3/м3'}
];

export const EMPTY_MATERIAL_NORM_FORM = {
  ruleKey:'',
  name:'',
  workText:'',
  blockWorkText:'демонтаж, разбор',
  materialText:'',
  workUnit:'м2',
  materialUnit:'кг',
  qtyPerUnit:'',
  thicknessBaseMm:'',
  defaultThicknessMm:'',
  label:'',
};

export const normTextIncludes = (text, words = []) => {
  const t = materialLookupText(text);
  return words.some(w => t.includes(materialLookupText(w)));
};

export const normHasAny = (text, words = []) => {
  const t = materialLookupText(text);
  return words.some(w => t.includes(materialLookupText(w)));
};

export const normWorkRuleMatches = (rule, workText = '') => {
  const text = materialLookupText(workText);
  const sourceWork = materialLookupText(rule?.workName || '');
  if (sourceWork && ['project', 'estimate'].includes(rule?.scope)) {
    return text.includes(sourceWork);
  }
  const keywords = (rule?.work || []).map(materialLookupText).filter(Boolean);
  const ruleKey = materialLookupText(rule?.ruleKey || rule?.id || '');
  if (ruleKey.startsWith('ai_')) return keywords.length > 0 && keywords.every(word => text.includes(word));
  return keywords.some(word => text.includes(word));
};

export const workNoMaterialNormReason = (workName = '', sectionName = '') => {
  const t = materialLookupText(workName + ' ' + sectionName);
  if (['демонтаж', 'разбор', 'разборка', 'снятие', 'отбивка'].some(w => t.includes(w))) {
    return 'Демонтажная/разборочная работа — материал по норме не требуется';
  }
  if (['очистка', 'обеспыливание', 'пробивка', 'погрузка', 'перевозка', 'затаривание'].some(w => t.includes(w))) {
    return 'Подготовительная или транспортная операция — материал по норме не требуется';
  }
  if (t.includes('без стоимости оборудования') || t.includes('ранее демонтирован')) {
    return 'Установка ранее демонтированного оборудования — новый материал по норме не требуется';
  }
  return '';
};

export const materialNoNormCoverageReason = (materialName = '') => {
  const t = materialLookupText(materialName);
  if (['сверло', 'бур', 'диск отрез', 'круг отрез', 'коронка алмаз', 'оснастк', 'инструмент'].some(w => t.includes(w))) {
    return 'Расходный инструмент/оснастка — не участвует в подборе нормы строительного материала';
  }
  return '';
};

export const normSpecText = (value = '') => String(value || '').toLowerCase()
  .replace(/ё/g, 'е')
  .replace(/,/g, '.')
  .replace(/[×x]/g, 'х')
  .replace(/[Øø]/g, ' диаметр ')
  .replace(/[–—]/g, '-')
  .replace(/\s+/g, ' ')
  .trim();

export const normSpecNum = (value) => {
  const n = Number(String(value || '').replace(',', '.'));
  return Number.isFinite(n) ? Math.round(n * 1000) / 1000 : null;
};

export const normUniqueNums = (items = []) => (
  [...new Set(items.filter(n => n !== null && n !== undefined).map(n => String(n)))]
    .map(Number)
    .sort((a, b) => a - b)
);

export const normExtractDiameters = (value = '') => {
  const text = normSpecText(value);
  const out = [];
  const re = /(?:диаметр(?:ом)?|диам\.?|ф)\D{0,45}(\d{1,3}(?:\.\d+)?)(?:\s*х\s*(\d{1,3}(?:\.\d+)?))?/g;
  let m;
  while ((m = re.exec(text))) {
    [m[1], m[2]].forEach(v => {
      const n = normSpecNum(v);
      if (n >= 6 && n <= 250) out.push(n);
    });
  }
  return normUniqueNums(out);
};

export const normExtractRectSizes = (value = '') => {
  const text = normSpecText(value);
  const out = [];
  const re = /(\d{1,4})\s*х\s*(\d{1,4})(?:\s*х\s*(\d{1,4}))?\s*мм/g;
  let m;
  while ((m = re.exec(text))) {
    const nums = [m[1], m[2], m[3]].filter(Boolean).map(Number);
    if (nums.length >= 2 && nums.every(n => n > 0 && n <= 2000)) out.push(nums.join('х'));
  }
  return [...new Set(out)];
};

export const normExtractCableSections = (value = '') => {
  const text = normSpecText(value);
  const out = [];
  const re = /(\d{1,2})\s*х\s*(\d{1,2}(?:\.\d+)?)(?:\s*х\s*(\d{1,2}(?:\.\d+)?))?(?=\s*(?:мм2|мм²|кв\.?\s*мм|ок|нг|fr|ls|hf|$))/g;
  let m;
  while ((m = re.exec(text))) {
    const parts = [m[1], m[2], m[3]].filter(Boolean).map(v => {
      const n = normSpecNum(v);
      return n === null ? '' : String(n).replace('.', ',');
    }).filter(Boolean);
    if (parts.length >= 2) out.push(parts.join('х'));
  }
  return [...new Set(out)];
};

export const normSpecsOverlap = (left = [], right = []) => (
  !left.length || !right.length || left.some(v => right.includes(v))
);

export const materialNormSpecCompatible = (rule, workText = '', materialName = '') => {
  const ruleKey = materialLookupText(rule?.ruleKey || rule?.id || '');
  const workDiameters = normExtractDiameters(workText);
  const materialDiameters = normExtractDiameters(materialName);
  const diameterRules = ['pipe_pp', 'pipe_fittings', 'pipe_clamps', 'pipe_insulation', 'cable_protection'];
  if (diameterRules.some(k => ruleKey.includes(k)) && !normSpecsOverlap(workDiameters, materialDiameters)) return false;
  if (ruleKey.includes('cable_line') && !normSpecsOverlap(normExtractCableSections(workText), normExtractCableSections(materialName))) return false;
  if ((ruleKey.includes('cable_channel_box') || ruleKey.includes('cable_protection')) && !normSpecsOverlap(normExtractRectSizes(workText), normExtractRectSizes(materialName))) return false;
  return true;
};

export const normRuleSpecificEnough = (rule, workText = '') => {
  const t = materialLookupText(workText);
  const words = t.split(' ');
  const hasWordStem = (stem) => words.some(word => word.startsWith(stem));
  const hasCableWord = words.some(w => (
    w.startsWith('кабел')
    || w.startsWith('гофр')
    || w.startsWith('короб')
    || w.startsWith('лоток')
    || w.startsWith('металлорукав')
    || (w.startsWith('провод') && !w.startsWith('трубопровод'))
  ));
  const ruleKey = materialLookupText(rule.ruleKey || rule.id || '');
  const mat = materialLookupText([ruleKey, rule.name, ...(rule.material || [])].join(' '));
  const matWords = mat.split(' ');
  const plasterWordIndex = words.findIndex(word => word.startsWith('штукатур'));
  const plasterPrefix = plasterWordIndex > 0 ? words.slice(Math.max(0, plasterWordIndex - 2), plasterWordIndex) : [];
  const plasterIsFinishReference = plasterPrefix.includes('по')
    || plasterPrefix.includes('под')
    || normHasAny(t, ['окраск', 'покраск', 'шпаклев', 'шпатлев', 'грунтов']);
  const isPlasterOperation = words.some(word => word.startsWith('оштукатурив'))
    || (plasterWordIndex >= 0 && !plasterIsFinishReference);
  const isCableRule = ['cable', 'кабел', 'utp', 'ftp', 'гофр', 'кабель канал'].some(w => mat.includes(w))
    || matWords.some(w => w.startsWith('провод') && !w.startsWith('трубопровод'));
  if (ruleKey.includes('brick_masonry') && !hasWordStem('кладк')) return false;
  if (ruleKey.includes('plaster_mix') && !isPlasterOperation) return false;
  if (ruleKey.includes('plaster_mesh')) {
    if (!isPlasterOperation && !normHasAny(t, ['сетка', 'армир'])) return false;
  }
  if (ruleKey.includes('screed_mix') && normHasAny(t, ['на каждые', 'добавлять или исключать', 'изменения толщины'])) return false;
  if (isCableRule && !hasCableWord) return false;
  if (ruleKey.includes('cable_line') && normHasAny(t, ['труба гофр', 'гофрирован', 'кабель-канал', 'кабель канал', 'короб', 'лоток', 'металлорукав']) && !normHasAny(t, ['затягивание', 'прокладка кабел', 'прокладка провод', 'провод в короб', 'кабель в короб'])) return false;
  if (ruleKey.includes('pipe_insulation') && !normHasAny(t, ['изоляц', 'теплоизоляц', 'утепл', 'энергофлекс'])) return false;
  if ((ruleKey.includes('thermal_insulation_board') || ruleKey.includes('thermal_insulation_fasteners'))
    && normHasAny(t, ['пароизоляц', 'гидроизоляц', 'обертывание'])) return false;
  return true;
};

export const materialNormUnitCompatible = (rule, materialName = '', materialUnit = '') => {
  const ruleUnit = _normalizeUnit(rule?.materialUnit || '');
  const unit = _normalizeUnit(materialUnit || '');
  if (!ruleUnit || !unit || ruleUnit === unit) return true;
  return !!convertUnits(materialName, 1, rule.materialUnit, materialUnit);
};

export const materialNormFamilyCompatible = (rule, materialName = '') => {
  const ruleKey = materialLookupText(rule?.ruleKey || rule?.id || '');
  const ruleText = materialLookupText([ruleKey, rule?.name, ...(rule?.material || [])].join(' '));
  const materialText = materialLookupText(materialName);
  const has = (words) => normHasAny(materialText, words);
  const fittingWords = ['муфта', 'угольник', 'угол', 'тройник', 'переход', 'кран', 'фитинг', 'отвод', 'вентиль', 'клапан'];
  const pipeWords = ['труба', 'трубы', 'трубн', 'ppr', 'pprc', 'ppr c', 'ppr-c', 'полипропилен'];
  const pipeClampWords = ['хомут', 'кронштейн', 'клипс', 'клипса', 'скоба', 'держатель', 'опора', 'подвес', 'консоль'];
  const insulationWords = ['изоляц', 'теплоизоляц', 'утепл', 'утеплител', 'минераловат', 'минвата', 'вата', 'изовер', 'технониколь', 'пенополиэтилен', 'энергофлекс'];
  const fastenerWords = ['дюбел', 'дюбель', 'саморез', 'шуруп', 'анкер', 'гвозд', 'болт'];
  const cableWords = ['кабель', 'провод', 'utp', 'ftp', 'sftp', 'f-utp', 'u-utp', 'кпс', 'ксвв', 'кспв', 'квп', 'ввг', 'nym', 'frls', 'frhf'];
  const cableProtectionWords = ['кабель-канал', 'кабель канал', 'короб', 'гофр', 'гофра', 'гофрирован', 'труба пнд', 'труба пвх', 'трубы гибкие', 'лоток', 'металлорукав'];
  const cableFastenerWords = ['скоб', 'хомут', 'крепеж', 'креплен', 'клипс', 'держатель', 'дюбел', 'дюбель', 'саморез', 'анкер', 'болт', 'шуруп'];
  if (ruleKey.includes('cable_fasteners')) return has(cableFastenerWords);
  if (ruleKey.includes('cable_line')) return has(cableWords) && !has(cableProtectionWords) && !has(cableFastenerWords);
  if (ruleKey.includes('cable_protection')) return has(cableProtectionWords);
  if (ruleKey.includes('cable_channel_box')) return has(['кабель-канал', 'кабель канал', 'короб']);
  if (ruleKey.includes('pipe_pp')) return has(pipeWords) && !has(fittingWords) && !has(pipeClampWords) && !has(fastenerWords);
  if (ruleKey.includes('pipe_fittings')) return has(fittingWords);
  if (ruleKey.includes('pipe_clamps')) return has(pipeClampWords);
  if (ruleKey.includes('pipe_insulation')) return has(insulationWords) && !has(fastenerWords);
  if (ruleKey.includes('thermal_insulation_board')) return has(insulationWords) && !has(fastenerWords);
  if (ruleKey.includes('thermal_insulation_fasteners')) return has(fastenerWords) && has(['теплоизоляц', 'изоляц']);
  if (ruleKey.includes('radiator_connection_kit')) return has(['комплект монтаж', 'комплект подключ', 'подключения радиатор', 'радиаторный комплект']);
  if (ruleKey.includes('radiator_mount')) return has(['кронштейн', 'консоль', 'крепление радиатор', 'крепеж радиатор', 'комплект крепления']);
  if (ruleText.includes('изоляция труб')) return has(insulationWords) && !has(fastenerWords);
  if (ruleText.includes('трубопровод') && has(fastenerWords) && !has(pipeClampWords)) return false;
  return true;
};

export const materialNormMatchesMaterial = (rule, materialName = '', materialUnit = '', workText = '') => (
  normTextIncludes(materialName, rule?.material || [])
  && materialNormUnitCompatible(rule, materialName, materialUnit)
  && materialNormFamilyCompatible(rule, materialName)
  && materialNormSpecCompatible(rule, workText, materialName)
);

export const normListFromText = (value) => String(value || '').split(/[,;\n]/).map(v => v.trim()).filter(Boolean);
export const normListToText = (value) => Array.isArray(value) ? value.join(', ') : String(value || '');

export const materialTitleForNormRule = (rule) => ({
  plaster_mix: 'Штукатурная смесь',
  screed_mix: 'Смесь для стяжки',
  putty_mix: 'Шпаклевка',
  tile_glue: 'Плиточный клей',
  tile_grout: 'Затирка',
  paint: 'Краска',
  primer: 'Грунтовка',
  gkl_sheet: 'ГКЛ лист',
  gkl_profile: 'Профиль ГКЛ',
  gkl_screws: 'Саморезы ГКЛ',
  cable_line: 'Кабель / провод',
  cable_protection: 'Гофра / кабель-канал',
  cable_channel_box: 'Короб / кабель-канал',
  cable_fasteners: 'Крепеж кабельной трассы',
  junction_box: 'Коробка ответвительная',
  luminaire: 'Светильник / табло',
  socket_switch: 'Розетка / выключатель',
  electric_panel: 'Щит / шкаф распределительный',
  pipe_pp: 'Труба полипропиленовая',
  pipe_fittings: 'Фитинги трубопроводов',
  pipe_clamps: 'Крепление трубопроводов',
  pipe_insulation: 'Изоляция труб',
  thermal_insulation_board: 'Теплоизоляция плитная/рулонная',
  radiator_device: 'Радиатор отопления',
  radiator_mount: 'Крепление радиатора',
  radiator_connection_kit: 'Комплект подключения радиатора',
  plaster_mesh: 'Штукатурная сетка',
  plaster_beacon: 'Маячный профиль',
  linoleum_sheet: 'Линолеум',
  linoleum_glue: 'Клей для линолеума',
  pvc_plinth: 'Плинтус',
  plywood_subfloor: 'Фанера / основание пола',
  osb_subfloor: 'OSB / древесная плита',
  wood_frame: 'Брус каркаса',
  door_block: 'Дверной блок',
  windowsill: 'Подоконник',
  windowsill_end_caps: 'Заглушки подоконника',
  thermal_insulation_fasteners: 'Крепеж теплоизоляции',
  brick_masonry: 'Кирпич',
  concrete: 'Бетон',
}[rule?.ruleKey || rule?.id] || rule?.name || rule?.material?.[0] || 'Материал по норме');

export const materialNormSupplyMarker = (row) => {
  const ruleKey = row?.rule?.ruleKey || row?.rule?.id || '';
  return 'NORM_COVERAGE_REQUEST:' + [row?.estimateId || '', row?.sectionIdx ?? '', row?.itemIdx ?? '', ruleKey].join('|');
};

export const materialNormCanCreateSupply = (row) => (
  ['Нет материала в смете', 'Материал без количества', 'Некорректное количество', 'Нехватка материала по норме'].includes(row?.status)
  && row?.rule
  && toNum(row?.shortageQty || row?.requiredQty) > 0
);

export const materialNormSupplyNotes = (rows, summaryTitle = 'Создано из ведомости «Вся смета по нормам»: материал нужен по норме, но отсутствует в смете или указан без количества.') => {
  const lines = [summaryTitle];
  (rows || []).forEach((row, idx) => {
    const materialName = row.materialName || materialTitleForNormRule(row.rule) || 'материал';
    const requestQty = toNum(row.shortageQty || row.requiredQty);
    lines.push(
      '',
      '#' + (idx + 1) + ' ' + materialName + ' — ' + (requestQty ? fmtMeasure(requestQty, row.requiredUnit) : 'количество не рассчитано'),
      materialNormSupplyMarker(row),
      'Объект: ' + (row.projectName || ''),
      'Смета: ' + (row.estimateName || ''),
      'Раздел: ' + (row.sectionName || ''),
      'Работа: ' + (row.workName || ''),
      'Объём работы: ' + (row.workQty ? fmtMeasure(row.workQty, row.workUnit) : 'не указан'),
      'Норма: ' + (row.rule?.label || row.rule?.ruleKey || materialName),
    );
  });
  return lines.filter(Boolean).join('\n');
};

export const materialNormRuleForCalc = (rule) => ({
  ...rule,
  dbId: Number(rule.id) || null,
  id: rule.ruleKey || rule.id,
  ruleKey: rule.ruleKey || rule.id,
  name: rule.name || materialTitleForNormRule(rule),
  work: Array.isArray(rule.work) ? rule.work : normListFromText(rule.work),
  blockWork: Array.isArray(rule.blockWork) ? rule.blockWork : normListFromText(rule.blockWork),
  material: Array.isArray(rule.material) ? rule.material : normListFromText(rule.material),
  qtyPerUnit: toNum(rule.qtyPerUnit),
  thicknessBaseMm: toNum(rule.thicknessBaseMm),
  defaultThicknessMm: toNum(rule.defaultThicknessMm),
  projectName: rule.projectName || '',
  estimateId: rule.estimateId || null,
  baseNormId: rule.baseNormId || (rule.scope ? null : (Number(rule.id) || null)),
  reason: rule.reason || '',
  scope: rule.scope || '',
});

export const buildMaterialNormRulesForCalculation = ({
  projectName = '',
  estimateId = null,
  materialNorms = [],
  materialNormOverrides = [],
  baseRules = WORK_MATERIAL_NORM_RULES,
} = {}) => {
  const dbRules = (materialNorms || [])
    .filter(r => r.active !== false)
    .map(materialNormRuleForCalc)
    .filter(r => r.qtyPerUnit > 0 && r.work?.length && r.material?.length);
  const normalizedBaseRules = dbRules.length ? dbRules : (baseRules || []).map(materialNormRuleForCalc);
  if (!projectName) return normalizedBaseRules;
  const overrides = (materialNormOverrides || [])
    .filter(r => (
      r.active !== false
      && r.projectName === projectName
      && (!r.estimateId || !estimateId || Number(r.estimateId) === Number(estimateId))
    ))
    .map(r => materialNormRuleForCalc({
      ...r,
      ruleKey: 'override_' + r.id,
      name: r.materialName || r.name || 'Поправка нормы',
      scope: r.estimateId ? 'estimate' : 'project',
    }))
    .filter(r => r.qtyPerUnit > 0 && r.work?.length && r.material?.length);
  const replacedBaseIds = new Set(overrides.map(rule => Number(rule.baseNormId)).filter(id => id > 0));
  const activeBaseRules = normalizedBaseRules.filter(rule => !replacedBaseIds.has(Number(rule.dbId)));
  return [...overrides, ...activeBaseRules];
};

export const workNormRulesForCalculation = ({
  workName = '',
  sectionName = '',
  projectName = '',
  estimateId = null,
  materialNorms = [],
  materialNormOverrides = [],
  baseRules = WORK_MATERIAL_NORM_RULES,
} = {}) => {
  const text = workName + ' ' + sectionName;
  if (workNoMaterialNormReason(workName, sectionName)) return [];
  return buildMaterialNormRulesForCalculation({
    projectName,
    estimateId,
    materialNorms,
    materialNormOverrides,
    baseRules,
  }).filter(rule => (
    normWorkRuleMatches(rule, text)
    && !normTextIncludes(text, rule.blockWork || [])
    && normRuleSpecificEnough(rule, text)
  ));
};

export const roundNormQty = (qty) => {
  const q = Number(qty) || 0;
  if (q <= 0) return 0;
  if (q >= 100) return Math.ceil(q);
  if (q >= 10) return Math.round(q * 10) / 10;
  return Math.round(q * 100) / 100;
};

export const calculateMaterialNormForWork = ({
  projectName = '',
  workName = '',
  sectionName = '',
  workQty = 0,
  workUnit = '',
  material = null,
  params = {},
  materialNorms = [],
  materialNormOverrides = [],
  baseRules = WORK_MATERIAL_NORM_RULES,
} = {}) => {
  if (!projectName || !material?.name || toNum(workQty) <= 0) return null;
  const normalizedWork = normalizeMeasure(workQty, workUnit);
  const rules = workNormRulesForCalculation({
    workName,
    sectionName,
    projectName,
    estimateId: params.estimateId,
    materialNorms,
    materialNormOverrides,
    baseRules,
  }).filter(rule => (
    _normalizeUnit(normalizedWork.unit) === _normalizeUnit(rule.workUnit)
    && materialNormMatchesMaterial(rule, material.name, material.unit, workName + ' ' + sectionName)
  ));
  if (!rules.length) return null;
  const rule = rules[0];
  let qty = normalizedWork.qty * Number(rule.qtyPerUnit || 0);
  let label = rule.label;
  if (rule.thicknessBaseMm) {
    const thickness = toNum(params.thicknessMm) || Number(rule.defaultThicknessMm || rule.thicknessBaseMm);
    qty *= thickness / Number(rule.thicknessBaseMm);
    label += ' · слой ' + thickness + ' мм';
  }
  const targetUnit = material.unit || rule.materialUnit;
  let outQty = qty;
  let outUnit = targetUnit;
  if (_normalizeUnit(rule.materialUnit) !== _normalizeUnit(targetUnit)) {
    const conv = convertUnits(material.name, qty, rule.materialUnit, targetUnit);
    if (!conv) return null;
    outQty = conv.qty;
    label += ' · ' + conv.note;
  }
  const rounded = roundNormQty(outQty);
  return {
    ruleId: rule.ruleKey || rule.id,
    scope: rule.scope || 'base',
    quantity: rounded,
    unit: outUnit,
    normQuantity: rounded,
    normSource: label,
    autoNorm: true,
  };
};

export const calculateNormRequirementsForWork = ({
  workName = '',
  sectionName = '',
  workQty = 0,
  workUnit = '',
  params = {},
  materialNorms = [],
  materialNormOverrides = [],
  baseRules = WORK_MATERIAL_NORM_RULES,
} = {}) => {
  const normalizedWork = normalizeMeasure(workQty, workUnit);
  if (toNum(normalizedWork.qty) <= 0) return [];
  return workNormRulesForCalculation({
    workName,
    sectionName,
    projectName: params.projectName || '',
    estimateId: params.estimateId || null,
    materialNorms,
    materialNormOverrides,
    baseRules,
  })
    .filter(rule => _normalizeUnit(normalizedWork.unit) === _normalizeUnit(rule.workUnit))
    .map(rule => {
      let qty = normalizedWork.qty * Number(rule.qtyPerUnit || 0);
      let label = rule.label;
      if (rule.thicknessBaseMm) {
        const thickness = toNum(params.thicknessMm) || Number(rule.defaultThicknessMm || rule.thicknessBaseMm);
        qty *= thickness / Number(rule.thicknessBaseMm);
        label += ' · слой ' + thickness + ' мм';
      }
      return {
        ruleId: rule.ruleKey || rule.id,
        scope: rule.scope || 'base',
        rule,
        name: materialTitleForNormRule(rule),
        quantity: roundNormQty(qty),
        unit: rule.materialUnit,
        normSource: label,
      };
    })
    .filter(r => r.quantity > 0);
};

export const materialNormCoverageSpecText = (row) => {
  const ruleKey = materialLookupText(row?.rule?.ruleKey || row?.rule?.id || '');
  const workText = [row?.workName, row?.sectionName].filter(Boolean).join(' ');
  const materialText = row?.materialName || '';
  const spec = (label, left, right) => {
    if (left.length && right.length) return label + ': ' + left.join('/') + ' ↔ ' + right.join('/');
    if (left.length) return label + ': в работе ' + left.join('/') + ', в материале не указано';
    if (right.length) return label + ': в материале ' + right.join('/') + ', в работе не указано';
    return '';
  };
  const parts = [];
  const diameters = ['pipe_pp', 'pipe_fittings', 'pipe_clamps', 'pipe_insulation', 'cable_protection'];
  if (diameters.some(k => ruleKey.includes(k))) {
    parts.push(spec('диаметр', normExtractDiameters(workText), normExtractDiameters(materialText)));
  }
  if (ruleKey.includes('cable_line')) {
    parts.push(spec('сечение кабеля', normExtractCableSections(workText), normExtractCableSections(materialText)));
  }
  if (ruleKey.includes('cable_channel_box') || ruleKey.includes('cable_protection')) {
    parts.push(spec('размер короба/гофры', normExtractRectSizes(workText), normExtractRectSizes(materialText)));
  }
  return parts.filter(Boolean).join('; ');
};

export const materialNormCoverageComment = (row) => {
  const base = row?.message || '';
  if (!row?.rule) return base;
  const pieces = [];
  const ruleName = materialTitleForNormRule(row.rule);
  if (ruleName) pieces.push('норма "' + ruleName + '"');
  if (row.rule.materialUnit) pieces.push('ед. материала ' + row.rule.materialUnit);
  const spec = materialNormCoverageSpecText(row);
  if (spec) pieces.push(spec);
  if (row.status === 'Нет материала в смете') pieces.push('подходящая строка материала в этом разделе не найдена');
  if (row.status === 'Нехватка материала по норме') {
    pieces.push('не хватает ' + fmtMeasure(row.shortageQty || 0, row.requiredUnit || row.materialUnit || row.rule.materialUnit));
  }
  if (row.status === 'Некорректное количество') pieces.push('количество материала в смете отрицательное или некорректное');
  if (row.status === 'Материал без количества') pieces.push('материал найден, но количество в смете пустое или 0');
  if (!pieces.length) return base;
  return base + '. Проверено: ' + pieces.join('; ');
};

export const materialNormCoveragePriority = (status) => ({
  'Некорректное количество': 0,
  'Нехватка материала по норме': 1,
  'Нет материала в смете': 2,
  'Материал без количества': 3,
  'Нет нормы': 4,
  'Материал без работы': 5,
  'Поправка объекта': 6,
  'Поправка сметы': 6,
  'Норма применена': 7,
  'Норма не нужна': 8,
}[status] ?? 9);

export const materialNormCoverageDisplayRows = (rows = []) => [...rows].sort((a, b) => {
  const pa = materialNormCoveragePriority(a.status);
  const pb = materialNormCoveragePriority(b.status);
  if (pa !== pb) return pa - pb;
  return String(a.sectionName || '').localeCompare(String(b.sectionName || ''), 'ru')
    || String(a.workName || '').localeCompare(String(b.workName || ''), 'ru');
});

export const materialNormCoverageExportRows = (rows = []) => rows.map(r => ({
  Статус: r.status || '',
  Смета: r.estimateName || '',
  Пакет: r.packageName || '',
  Раздел: r.sectionName || '',
  Работа: r.workName || '',
  'Объем работы': r.workQty ? fmtMeasure(r.workQty, r.workUnit) : '',
  'Материал / норма': r.materialName || materialTitleForNormRule(r.rule) || '',
  'Потребность': r.requiredQty ? fmtMeasure(r.requiredQty, r.requiredUnit) : '',
  'В смете': r.materialQty ? fmtMeasure(r.materialQty, r.materialUnit) : '',
  'Нехватка': r.shortageQty ? fmtMeasure(r.shortageQty, r.requiredUnit || r.materialUnit) : '',
  'Код нормы': r.rule?.ruleKey || r.rule?.id || '',
  Комментарий: materialNormCoverageComment(r),
}));

// Арматура: вес погонного метра в зависимости от диаметра (ГОСТ 5781-82)
const REBAR_KG_PER_M = { 6:0.222, 8:0.395, 10:0.617, 12:0.888, 14:1.21, 16:1.58, 18:2.0, 20:2.47, 22:2.98, 25:3.85, 28:4.83, 32:6.31 };
const _rebarDiameter = (name) => { const m = (name||'').match(/[ØФø]?\s*(\d{1,2})\s*мм/i); return m ? Number(m[1]) : null; };

// Возвращает {qty, factor, note} или null если конверсия не известна.
export const convertUnits = (materialName, qty, fromUnit, toUnit) => {
  const from = _normalizeUnit(fromUnit);
  const to = _normalizeUnit(toUnit);
  qty = Number(qty)||0;
  if (from === to) return { qty: qty, factor: 1, note: 'единицы совпадают' };
  const n = (materialName||'').toLowerCase();
  // Арматура: м ↔ кг
  if (n.includes('арматур') || n.includes('арм.')) {
    const d = _rebarDiameter(n);
    const f = d && REBAR_KG_PER_M[d];
    if (f) {
      if (from === 'м' && to === 'кг') return { qty: qty*f, factor: f, note: '1 м ≈ '+f+' кг (Ø'+d+' мм)' };
      if (from === 'кг' && to === 'м') return { qty: qty/f, factor: 1/f, note: '1 кг ≈ '+(1/f).toFixed(3)+' м (Ø'+d+' мм)' };
    }
  }
  // Краска/эмаль/грунтовка: л ↔ кг (плотность ~1.4)
  if (n.includes('краск') || n.includes('эмал') || n.includes('грунтов') || n.includes('лак')) {
    const d = 1.4;
    if (from === 'л' && to === 'кг') return { qty: qty*d, factor: d, note: '1 л ≈ '+d+' кг (плотность краски)' };
    if (from === 'кг' && to === 'л') return { qty: qty/d, factor: 1/d, note: '1 кг ≈ '+(1/d).toFixed(2)+' л (плотность краски)' };
  }
  // Цемент: мешок ↔ кг (50 кг)
  if (n.includes('цемент')) {
    if (from === 'мешок' && to === 'кг') return { qty: qty*50, factor: 50, note: '1 мешок = 50 кг' };
    if (from === 'кг' && to === 'мешок') return { qty: qty/50, factor: 1/50, note: '50 кг = 1 мешок' };
  }
  // Сухие строительные смеси чаще всего учитываются мешками по 25 кг.
  if (n.includes('штукатур') || n.includes('шпаклев') || n.includes('шпатлев') || n.includes('клей') || n.includes('пескобетон') || n.includes('стяжк')) {
    if (from === 'мешок' && to === 'кг') return { qty: qty*25, factor: 25, note: '1 мешок ≈ 25 кг' };
    if (from === 'кг' && to === 'мешок') return { qty: qty/25, factor: 1/25, note: '25 кг ≈ 1 мешок' };
  }
  // Бетон: м3 ↔ т ↔ кг (2400 кг/м3)
  if (n.includes('бетон')) {
    if (from === 'м3' && to === 'т') return { qty: qty*2.4, factor: 2.4, note: '1 м³ ≈ 2.4 т (бетон)' };
    if (from === 'т' && to === 'м3') return { qty: qty/2.4, factor: 1/2.4, note: '1 т ≈ 0.42 м³ (бетон)' };
    if (from === 'м3' && to === 'кг') return { qty: qty*2400, factor: 2400, note: '1 м³ ≈ 2400 кг (бетон)' };
    if (from === 'кг' && to === 'м3') return { qty: qty/2400, factor: 1/2400, note: '1 кг ≈ 0.0004 м³' };
  }
  // Раствор/стяжка: м3 ↔ кг (2000 кг/м3)
  if (n.includes('раствор') || n.includes('стяжк') || n.includes('пескобетон')) {
    if (from === 'м3' && to === 'кг') return { qty: qty*2000, factor: 2000, note: '1 м³ ≈ 2000 кг' };
    if (from === 'кг' && to === 'м3') return { qty: qty/2000, factor: 1/2000, note: '1 кг ≈ 0.0005 м³' };
  }
  // Песок: м3 ↔ т (1600 кг/м3)
  if (n.includes('песок') || n.includes('щебен')) {
    if (from === 'м3' && to === 'т') return { qty: qty*1.6, factor: 1.6, note: '1 м³ ≈ 1.6 т (сыпучие)' };
    if (from === 'т' && to === 'м3') return { qty: qty/1.6, factor: 1/1.6, note: '1 т ≈ 0.625 м³' };
    if (from === 'м3' && to === 'кг') return { qty: qty*1600, factor: 1600, note: '1 м³ ≈ 1600 кг' };
  }
  // Универсально: т ↔ кг
  if (from === 'т' && to === 'кг') return { qty: qty*1000, factor: 1000, note: '1 т = 1000 кг' };
  if (from === 'кг' && to === 'т') return { qty: qty/1000, factor: 1/1000, note: '1000 кг = 1 т' };
  return null;
};

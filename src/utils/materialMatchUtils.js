export const materialLookupText = (name) => String(name || '').toLowerCase().replace(/[.,;:()«»"']/g, ' ').replace(/\s+/g, ' ').trim();

const MATERIAL_MATCH_STOPWORDS = new Set([
  'гост', 'ту', 'сорт', 'марка', 'тип', 'вид', 'цвет', 'размер', 'разм',
  'мм', 'см', 'м', 'шт', 'кг', 'л', 'т', 'для', 'при', 'под', 'над', 'без',
  'основная', 'объект', 'материал', 'материалы', 'позиция', 'работы', 'работа',
  'комплект', 'комплекта', 'комплектов', 'изделие', 'изделия', 'серия',
  'упак', 'упаковка', 'пач', 'пачка', 'пар', 'рул', 'рулон', 'бухта',
  'белый', 'белая', 'белое', 'черный', 'черная', 'черное', 'серый', 'серая',
]);

const materialMatchTokens = (name) => {
  const tokens = new Set();
  const add = (...values) => values.forEach(value => tokens.add(value));
  materialLookupText(name).split(' ').forEach(raw => {
    const token = raw.trim();
    if (token.length < 2 || MATERIAL_MATCH_STOPWORDS.has(token)) return;
    if (/^\d$/.test(token)) return;
    if (/^\d{4,}$/.test(token) && /^(13|20)/.test(token)) return;
    const dimensionToken = token.replace(/х/g, 'x').replace(/\*/g, 'x');
    if (/^\d+(?:x\d+){1,3}$/.test(dimensionToken)) {
      tokens.add(dimensionToken);
      return;
    }
    if (token.startsWith('керамогран')) add('керамогранит', 'гранит', 'керамическ');
    else if (token.startsWith('gres') || token.startsWith('porcelain')) add('керамическ', 'плитка');
    else if (token.startsWith('livorno') || token.startsWith('ливорн')) add('livorno', 'керамогранит', 'плитка');
    else if (token.startsWith('axima') || token.startsWith('аксима')) add('axima', 'керамогранит', 'плитка');
    else if (token.startsWith('керамич')) tokens.add('керамическ');
    else if (token.startsWith('гранит')) tokens.add('гранит');
    else if (token.startsWith('металлочереп') || token.startsWith('черепиц')) add('металлочерепица', 'черепица', 'кровля');
    else if (token.startsWith('монтер') || token.startsWith('monter')) add('монтеррей', 'металлочерепица', 'черепица', 'кровля');
    else if (token.startsWith('гкл') || token.startsWith('гипсокарт')) add('гкл', 'гипсокартон');
    else if (token.startsWith('гипрок')) add('гкл', 'гипсокартон');
    else if (token.startsWith('гвл') || token.startsWith('гипсовол')) add('гвл', 'гипсоволокно');
    else if (token.startsWith('аквапан')) add('аквапанель', 'лист');
    else if (token.includes('цемент')) tokens.add('цемент');
    else if (token.startsWith('смес')) tokens.add('смесь');
    else if (token.startsWith('пескобетон')) add('пескобетон', 'бетон', 'смесь');
    else if (token.startsWith('наливн')) add('наливной', 'смесь');
    else if (token.startsWith('ровнител')) add('ровнитель', 'смесь');
    else if (token.startsWith('затир')) add('затирка', 'смесь');
    else if (token.startsWith('ротб')) add('ротбанд', 'штукатурка', 'смесь');
    else if (token.startsWith('хабез')) add('хабез', 'штукатурка', 'смесь');
    else if (token.startsWith('старт')) add('старт', 'штукатурка', 'шпатлевка', 'смесь');
    else if (token.startsWith('кнауф') || token.startsWith('knauf')) tokens.add('кнауф');
    else if (token.startsWith('песк')) tokens.add('песок');
    else if (token.startsWith('бетон')) tokens.add('бетон');
    else if (token.startsWith('глаз')) tokens.add('глазур');
    else if (token.startsWith('матов') || token.startsWith('неполир')) tokens.add('матов');
    else if (token.startsWith('полир')) tokens.add('полир');
    else if (token.startsWith('плит')) tokens.add('плитка');
    else if (token.startsWith('кле')) tokens.add('клей');
    else if (token.startsWith('грунт')) tokens.add('грунтовка');
    else if (token.startsWith('штукатур')) tokens.add('штукатурка');
    else if (token.startsWith('шпатлев') || token.startsWith('шпаклев')) tokens.add('шпатлевка');
    else if (token.startsWith('профил')) tokens.add('профиль');
    else if (['пн', 'пп', 'пс', 'псу', 'cd', 'ud', 'cw', 'uw'].includes(token)) add('профиль', token);
    else if (token.startsWith('угол')) add('уголок', 'профиль');
    else if (token.startsWith('подвес')) add('подвес', 'профиль');
    else if (token.startsWith('маяк') || token.startsWith('маяч')) add('маяк', 'профиль');
    else if (token.startsWith('рейк')) tokens.add('рейка');
    else if (token.startsWith('лент')) tokens.add('лента');
    else if (token.startsWith('серпян')) tokens.add('серпянка');
    else if (token.startsWith('саморез') || token.startsWith('самонар')) add('саморез', 'крепеж');
    else if (token.startsWith('шуруп')) add('саморез', 'крепеж');
    else if (token.startsWith('прессшайб')) add('прессшайба', 'саморез', 'крепеж');
    else if (token.startsWith('анкер')) add('анкер', 'крепеж');
    else if (token.startsWith('болт')) add('болт', 'крепеж');
    else if (token.startsWith('гайк')) add('гайка', 'крепеж');
    else if (token.startsWith('шайб')) add('шайба', 'крепеж');
    else if (token.startsWith('кабел')) tokens.add('кабель');
    else if (token.startsWith('провод')) tokens.add('провод');
    else if (token.startsWith('светиль') || token.startsWith('табло')) add('светильник', 'свет');
    else if (token.startsWith('светодиод') || ['led', 'лед'].includes(token)) add('светильник', 'светодиод', 'свет');
    else if (token.startsWith('ламп')) add('лампа', 'свет');
    else if (token.startsWith('прожектор')) add('прожектор', 'светильник', 'свет');
    else if (token.startsWith('розет')) tokens.add('розетка');
    else if (token.startsWith('выключ')) tokens.add('выключатель');
    else if (token.startsWith('автомат') || token.startsWith('узо') || token.startsWith('дифавтомат')) add('автомат', 'электрика');
    else if (token.startsWith('щит')) add('щит', 'электрика');
    else if (token.startsWith('гофр')) add('гофра', 'труба', 'электрика');
    else if (token.startsWith('втул')) tokens.add('втулка');
    else if (token.startsWith('хомут')) add('хомут', 'крепеж');
    else if (token.startsWith('скоб')) add('скоба', 'крепеж');
    else if (token.startsWith('труб')) tokens.add('труба');
    else if (token.startsWith('ппр') || token.startsWith('ppr') || token.startsWith('полипроп')) add('труба', 'полипропилен');
    else if (token.startsWith('канализ')) add('труба', 'канализация');
    else if (token.startsWith('радиатор')) tokens.add('радиатор');
    else if (token.startsWith('бимет')) add('радиатор', 'биметалл');
    else if (token.startsWith('фитинг')) add('фитинг', 'инженерия');
    else if (token.startsWith('муфт')) add('муфта', 'фитинг', 'инженерия');
    else if (token.startsWith('тройник')) add('тройник', 'фитинг', 'инженерия');
    else if (token.startsWith('отвод')) add('отвод', 'фитинг', 'инженерия');
    else if (token.startsWith('нипп')) add('ниппель', 'фитинг', 'инженерия');
    else if (token.startsWith('переход')) add('переход', 'фитинг', 'инженерия');
    else if (token.startsWith('заглуш')) add('заглушка', 'фитинг', 'инженерия');
    else if (token.startsWith('коллект')) add('коллектор', 'инженерия');
    else if (token.startsWith('клапан')) add('клапан', 'инженерия');
    else if (token.startsWith('американ')) add('американка', 'фитинг', 'инженерия');
    else if (token.startsWith('воздухоотв')) add('воздухоотводчик', 'радиатор', 'инженерия');
    else if (token.startsWith('кран')) add('кран', 'инженерия');
    else if (token.startsWith('креп')) tokens.add('крепеж');
    else if (token.startsWith('скреп')) add('скрепа', 'крепеж');
    else if (token.startsWith('дюб') || token.includes('дюб')) add('дюбель', 'крепеж');
    else if (token.startsWith('клин')) add('клин', 'крепеж');
    else if (token.startsWith('кроншт')) add('кронштейн', 'крепеж');
    else if (token.startsWith('направл')) add('направляющая', 'профиль');
    else if (token.startsWith('доск')) tokens.add('доска');
    else if (token.startsWith('брус')) tokens.add('брус');
    else if (token.startsWith('фанер')) tokens.add('фанера');
    else if (token.startsWith('осп') || token.startsWith('osb')) tokens.add('осп');
    else if (token.startsWith('армат')) tokens.add('арматура');
    else if (token.startsWith('гвозд')) add('гвоздь', 'крепеж');
    else if (token.startsWith('шпил')) add('шпилька', 'крепеж');
    else if (token.startsWith('перф')) tokens.add('перфолента');
    else if (token.startsWith('краск') || token.startsWith('окрас')) tokens.add('краска');
    else if (token.startsWith('эмал')) tokens.add('эмаль');
    else if (token.startsWith('лак')) tokens.add('лак');
    else if (token.startsWith('гермет')) tokens.add('герметик');
    else if (token.startsWith('силикон')) tokens.add('силикон');
    else if (token.startsWith('пен')) tokens.add('пена');
    else if (token.startsWith('раствор')) tokens.add('раствор');
    else if (token.startsWith('алебастр')) tokens.add('алебастр');
    else if (token.startsWith('гипс')) tokens.add('гипс');
    else if (token.startsWith('извест')) tokens.add('известь');
    else tokens.add(token);
  });
  return tokens;
};

const materialFamilyTags = (tokens) => {
  const t = new Set(tokens || []);
  const families = new Set();
  if (t.has('клей')) families.add('adhesive');
  if (t.has('штукатурка') || t.has('ротбанд') || (t.has('смесь') && (t.has('хабез') || t.has('старт')))) families.add('plaster');
  if (t.has('шпатлевка') && !t.has('штукатурка')) families.add('putty');
  if (t.has('грунтовка')) families.add('primer');
  if (t.has('цемент') && !['plaster', 'putty', 'adhesive'].some(f => families.has(f))) families.add('cement');
  if (t.has('бетон')) families.add('concrete');
  if (t.has('песок')) families.add('sand');
  if (!t.has('клей') && ['керамогранит', 'плитка', 'гранит', 'керамическ'].some(x => t.has(x))) families.add('tile');
  if (t.has('гкл') || t.has('гипсокартон')) families.add('gkl');
  if (t.has('гвл') || t.has('гипсоволокно')) families.add('gvl');
  if (['профиль', 'уголок', 'подвес', 'маяк', 'рейка', 'направляющая', 'пн', 'пп', 'пс', 'псу', 'cd', 'ud', 'cw', 'uw'].some(x => t.has(x))) families.add('metal_profile');
  if (['саморез', 'анкер', 'болт', 'гайка', 'шайба', 'дюбель', 'крепеж', 'гвоздь', 'шпилька', 'скрепа', 'прессшайба', 'скоба', 'хомут', 'клин', 'кронштейн'].some(x => t.has(x))) families.add('fastener');
  if (t.has('кабель') || t.has('провод')) families.add('cable');
  if (['труба', 'фитинг', 'муфта', 'клапан', 'американка', 'хомут', 'кран', 'полипропилен', 'канализация', 'тройник', 'отвод', 'ниппель', 'переход', 'заглушка', 'коллектор', 'инженерия'].some(x => t.has(x))) families.add('pipe');
  if (['светильник', 'лампа', 'свет', 'светодиод', 'прожектор'].some(x => t.has(x))) families.add('light');
  if (['розетка', 'выключатель', 'автомат', 'щит', 'электрика'].some(x => t.has(x))) families.add('electrical_device');
  if (['радиатор', 'биметалл', 'воздухоотводчик'].some(x => t.has(x))) families.add('heating');
  if (['металлочерепица', 'черепица', 'кровля', 'монтеррей'].some(x => t.has(x))) families.add('roofing');
  if (['доска', 'брус', 'фанера', 'осп'].some(x => t.has(x))) families.add('wood_sheet');
  if (t.has('арматура')) families.add('rebar');
  if (['краска', 'эмаль', 'лак'].some(x => t.has(x))) families.add('paint');
  if (['герметик', 'силикон', 'пена'].some(x => t.has(x))) families.add('sealant');
  if (['раствор', 'алебастр', 'гипс', 'известь'].some(x => t.has(x)) && !families.has('plaster') && !families.has('putty')) families.add('binder_mix');
  return families;
};

const materialSetIntersection = (left, right) => new Set([...left].filter(x => right.has(x)));

export const materialNameMatchScore = (left, right) => {
  const leftKey = materialLookupText(left);
  const rightKey = materialLookupText(right);
  if (!leftKey || !rightKey) return 0;
  if (leftKey === rightKey) return 1;
  if (leftKey.length >= 10 && rightKey.length >= 10 && (leftKey.includes(rightKey) || rightKey.includes(leftKey))) return 0.92;
  const leftTokens = materialMatchTokens(leftKey);
  const rightTokens = materialMatchTokens(rightKey);
  if (!leftTokens.size || !rightTokens.size) return 0;
  const common = materialSetIntersection(leftTokens, rightTokens);
  const commonFamilies = materialSetIntersection(materialFamilyTags(leftTokens), materialFamilyTags(rightTokens));
  const familyScore = commonFamilies.size ? (['tile', 'plaster', 'putty', 'primer', 'cement', 'gkl', 'gvl', 'metal_profile', 'fastener', 'cable', 'pipe', 'roofing', 'paint', 'sealant', 'adhesive', 'light', 'heating', 'electrical_device'].some(f => commonFamilies.has(f)) ? 0.82 : 0.76) : 0;
  if (!common.size) return familyScore;
  if ((leftTokens.has('металлочерепица') || leftTokens.has('черепица')) && (rightTokens.has('металлочерепица') || rightTokens.has('черепица'))) return 0.84;
  if (['керамогранит', 'плитка'].some(x => leftTokens.has(x)) && ['керамогранит', 'плитка'].some(x => rightTokens.has(x)) && ['livorno', 'axima', 'гранит', 'керамическ', 'матов', 'глазур'].some(x => common.has(x))) return 0.86;
  if (['ротбанд', 'кнауф', 'смесь', 'хабез', 'старт'].some(x => leftTokens.has(x)) && ['ротбанд', 'кнауф', 'смесь', 'хабез', 'старт'].some(x => rightTokens.has(x)) && ['штукатурка', 'шпатлевка', 'смесь', 'ротбанд', 'кнауф'].some(x => common.has(x))) return 0.84;
  if (common.has('гранит') && common.has('керамическ')) return 0.86;
  if (['гкл', 'гипсокартон'].some(x => leftTokens.has(x)) && ['гкл', 'гипсокартон'].some(x => rightTokens.has(x))) return 0.84;
  if (['гвл', 'гипсоволокно'].some(x => leftTokens.has(x)) && ['гвл', 'гипсоволокно'].some(x => rightTokens.has(x))) return 0.84;
  if (familyScore) return Math.max(familyScore, 0.78);
  const score = common.size / Math.max(1, Math.min(leftTokens.size, rightTokens.size));
  const longCommon = [...common].filter(t => t.length >= 6);
  const strongCommon = materialSetIntersection(common, new Set(['цемент', 'бетон', 'песок', 'саморез', 'анкер', 'болт', 'гайка', 'шайба', 'кабель', 'провод', 'труба', 'радиатор', 'кран', 'клей', 'плитка', 'керамогранит', 'гранит', 'керамическ']));
  if (strongCommon.size && common.size >= 2) return Math.min(0.82, Math.max(score + 0.2, 0.62));
  if (common.size >= 3 && score >= 0.45) return Math.min(0.9, score + 0.15);
  if (common.size >= 2 && longCommon.length && score >= 0.4) return Math.min(0.82, score + 0.1);
  if (longCommon.length && score >= 0.65) return Math.min(0.72, score);
  return score >= 0.7 ? score : 0;
};

export const materialAutoMatchSafe = (left, right, score) => {
  const leftKey = materialLookupText(left);
  const rightKey = materialLookupText(right);
  if (leftKey && rightKey && leftKey === rightKey) return true;
  if (leftKey.length >= 10 && rightKey.length >= 10 && (leftKey.includes(rightKey) || rightKey.includes(leftKey))) return true;
  const leftTokens = materialMatchTokens(left);
  const rightTokens = materialMatchTokens(right);
  const common = materialSetIntersection(leftTokens, rightTokens);
  const commonFamilies = materialSetIntersection(materialFamilyTags(leftTokens), materialFamilyTags(rightTokens));
  if (score >= 0.86 && (common.size >= 2 || commonFamilies.size > 0)) return true;
  const broadSafeFamilies = new Set([
    'tile', 'plaster', 'putty', 'primer', 'cement', 'concrete', 'sand',
    'gkl', 'gvl', 'metal_profile', 'fastener', 'cable', 'pipe', 'roofing',
    'wood_sheet', 'rebar', 'sealant', 'binder_mix', 'adhesive', 'paint',
    'light', 'heating', 'electrical_device',
  ]);
  if (score >= 0.82 && common.size === 0 && [...commonFamilies].some(f => broadSafeFamilies.has(f))) return true;
  if (score >= 0.82 && common.size >= 1 && [...commonFamilies].some(f => broadSafeFamilies.has(f))) return true;
  if (score >= 0.82 && common.size >= 2) return true;
  return false;
};

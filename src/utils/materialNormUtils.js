import { _normalizeUnit } from './measureUtils';

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

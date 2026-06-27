#!/usr/bin/env node

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');
const { pathToFileURL } = require('url');

const root = path.resolve(__dirname, '..', 'public', 'site-assets', 'projects');
const tmpRoot = path.join(os.tmpdir(), 'stroyka-public-project-assets');
const chromeBin = process.env.CHROME_BIN || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const projects = [
  ['h2-01', 'twoFloorModern', 'Дом 165 м2', 'узкий участок', '165 м2'],
  ['h2-02', 'twoFloorModern', 'Дом 190 м2', 'второй свет', '190 м2'],
  ['h2-03', 'twoFloorModern', 'Дом 215 м2', 'балкон и терраса', '215 м2'],
  ['fam-01', 'familyHouse', 'Семейный дом 150 м2', '4 спальни', '150 м2'],
  ['fam-02', 'familyHouseModern', 'Коттедж 170 м2', 'второй свет', '170 м2'],
  ['fam-03', 'familyHouseTerrace', 'Коттедж 185 м2', 'терраса', '185 м2'],
  ['b2-01', 'twoFloorBrick', 'Кирпичный дом 180 м2', 'классический фасад', '180 м2'],
  ['b2-02', 'twoFloorBrickGarage', 'Дом 210 м2', 'гаражная зона', '210 м2'],
  ['b2-03', 'twoFloorBrickClassic', 'Классический дом 240 м2', 'кирпич и цоколь', '240 м2'],
  ['gar-01', 'garage', 'Дом 190 м2', 'гараж 1 авто', '190 м2'],
  ['gar-02', 'garageDouble', 'Дом 230 м2', 'гараж 2 авто', '230 м2'],
  ['gar-03', 'garageWorkshop', 'Дом 210 м2', 'гараж + мастерская', '210 м2'],
  ['town-01', 'townhouse', 'Таунхаус 95 м2', '2 спальни', '95 м2'],
  ['town-02', 'townhouseFamily', 'Таунхаус 120 м2', 'семейная секция', '120 м2'],
  ['town-03', 'townhouseOffice', 'Таунхаус 135 м2', 'кабинет', '135 м2'],
  ['rec-01', 'reconstruction', 'Реконструкция 140 м2', 'фасад и кровля', '140 м2'],
  ['rec-02', 'attic', 'Мансарда 80 м2', 'утепление кровли', '80 м2'],
  ['rec-03', 'extension', 'Пристройка 35 м2', 'кухня + терраса', '+35 м2'],
  ['fac-01', 'facade', 'Фасад 180 м2', 'утепление', '180 м2'],
  ['fac-02', 'facadeWood', 'Фасад 220 м2', 'штукатурка + дерево', '220 м2'],
  ['fac-03', 'facadeClinker', 'Клинкерный фасад', 'цоколь и отливы', '200 м2'],
  ['roof-01', 'roof', 'Кровля 160 м2', 'металлочерепица', '160 м2'],
  ['roof-02', 'roofAttic', 'Мансардная кровля', 'утепление', '190 м2'],
  ['roof-03', 'roofSoft', 'Мягкая кровля', 'примыкания', '145 м2'],
  ['apt-01', 'apartment', 'Квартира 45 м2', '2 комнаты', '45 м2'],
  ['apt-02', 'apartmentFamily', 'Квартира 72 м2', '2 спальни', '72 м2'],
  ['apt-03', 'apartmentLarge', 'Квартира 95 м2', '3 спальни', '95 м2'],
  ['fin-01', 'finishHouse', 'Отделка 120 м2', '3 спальни', '120 м2'],
  ['fin-02', 'finishHouseStairs', 'Отделка 160 м2', 'лестница', '160 м2'],
  ['fin-03', 'finishHouseLarge', 'Отделка 210 м2', '2 этажа', '210 м2'],
  ['bath-01', 'bathroom', 'Санузел 4 м2', 'душевая зона', '4 м2'],
  ['bath-02', 'bathroomTub', 'Ванная 6 м2', 'ванна + инсталляция', '6 м2'],
  ['bath-03', 'bathroomHouse', 'Санузел 9 м2', 'дом', '9 м2'],
  ['kit-01', 'kitchen', 'Кухня-гостиная 28 м2', 'линейная кухня', '28 м2'],
  ['kit-02', 'kitchenIsland', 'Кухня-гостиная 42 м2', 'остров', '42 м2'],
  ['kit-03', 'kitchenHouse', 'Кухня-гостиная 55 м2', 'выход на террасу', '55 м2'],
  ['off-01', 'officeOpen', 'Офис 120 м2', 'open space', '120 м2'],
  ['off-02', 'officeCabinet', 'Офис 180 м2', 'кабинеты', '180 м2'],
  ['off-03', 'officeClient', 'Офис 260 м2', 'клиентская зона', '260 м2'],
];

const esc = (value) => String(value).replace(/[&<>"]/g, (char) => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
}[char]));

const wrapSvg = (body) => `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1536" height="864" viewBox="0 0 1536 864" role="img">
  <defs>
    <linearGradient id="sky" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#d8f0ff"/>
      <stop offset="1" stop-color="#f7fbff"/>
    </linearGradient>
    <linearGradient id="glass" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0" stop-color="#bfe4f4"/>
      <stop offset="1" stop-color="#33485e"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="18" stdDeviation="18" flood-color="#1d2733" flood-opacity=".22"/>
    </filter>
  </defs>
  ${body}
</svg>
`;

const labelBlock = (title, subtitle, area) => `
  <rect x="64" y="52" width="470" height="112" rx="22" fill="#ffffff" opacity=".9"/>
  <text x="96" y="106" font-family="Arial, sans-serif" font-size="34" font-weight="700" fill="#132033">${esc(title)}</text>
  <text x="96" y="144" font-family="Arial, sans-serif" font-size="24" fill="#607087">${esc(subtitle)} · ${esc(area)}</text>
`;

const siteBase = (title, subtitle, area) => `
  <rect width="1536" height="864" fill="url(#sky)"/>
  <circle cx="1338" cy="118" r="54" fill="#ffe49a" opacity=".75"/>
  <path d="M0 612 C260 545 430 590 645 548 C900 500 1120 555 1536 500 L1536 864 L0 864 Z" fill="#dfeecf"/>
  <path d="M0 705 C250 652 526 690 745 646 C1012 594 1250 650 1536 606 L1536 864 L0 864 Z" fill="#eef0dd"/>
  <path d="M165 730 C410 682 835 690 1198 744" stroke="#ffffff" stroke-width="18" stroke-linecap="round" opacity=".8"/>
  ${labelBlock(title, subtitle, area)}
`;

const houseSvg = ({ title, subtitle, area, style, side = false }) => {
  const brick = style.includes('Brick');
  const garage = style.includes('garage') || style.includes('Garage') || style.includes('gar');
  const townhouse = style.includes('townhouse');
  const upperShift = side ? 58 : 0;
  const wall = brick ? '#b06a43' : '#f2f0e9';
  const accent = brick ? '#7b3f2a' : '#9a6b43';
  const roof = brick ? '#363133' : '#1c2738';
  const body = siteBase(title, subtitle, area) + `
  <g filter="url(#shadow)">
    <ellipse cx="790" cy="684" rx="460" ry="42" fill="#26313d" opacity=".18"/>
    ${townhouse ? `
      <rect x="324" y="340" width="744" height="250" fill="${wall}"/>
      <rect x="320" y="306" width="752" height="50" fill="${roof}"/>
      ${[0, 1, 2].map((n) => `<rect x="${360 + n * 220}" y="378" width="166" height="96" rx="8" fill="url(#glass)"/><rect x="${412 + n * 220}" y="496" width="62" height="94" rx="7" fill="#243142"/><line x1="${580 + n * 220}" y1="340" x2="${580 + n * 220}" y2="590" stroke="#ffffff" stroke-width="7" opacity=".55"/>`).join('')}
    ` : `
      <rect x="${320 + upperShift}" y="348" width="${garage ? 810 : 760}" height="250" fill="${wall}"/>
      <rect x="${420 + upperShift}" y="248" width="550" height="158" fill="${wall}"/>
      <polygon points="${290 + upperShift},346 ${706 + upperShift},255 ${1122 + upperShift},346" fill="${roof}"/>
      <rect x="${405 + upperShift}" y="384" width="180" height="112" rx="8" fill="url(#glass)"/>
      <rect x="${646 + upperShift}" y="384" width="210" height="112" rx="8" fill="url(#glass)"/>
      <rect x="${900 + upperShift}" y="385" width="78" height="213" rx="8" fill="#243142"/>
      <rect x="${934 + upperShift}" y="414" width="24" height="80" rx="4" fill="#c6e3ec"/>
      ${garage ? `<rect x="${1030 + upperShift}" y="418" width="210" height="180" rx="10" fill="#2a313a"/><rect x="${1060 + upperShift}" y="454" width="150" height="72" fill="#52606d"/>` : ''}
      <rect x="${500 + upperShift}" y="286" width="118" height="78" rx="6" fill="url(#glass)"/>
      <rect x="${704 + upperShift}" y="286" width="142" height="78" rx="6" fill="url(#glass)"/>
      ${style.includes('Modern') ? `<rect x="${330 + upperShift}" y="350" width="72" height="248" fill="${accent}"/><rect x="${846 + upperShift}" y="248" width="126" height="350" fill="${accent}" opacity=".8"/>` : ''}
    `}
    <rect x="${320 + upperShift}" y="598" width="${garage ? 920 : 780}" height="34" fill="#b7b0a4"/>
  </g>
  <g opacity=".95">
    <circle cx="230" cy="644" r="30" fill="#217257"/>
    <circle cx="1230" cy="635" r="36" fill="#217257"/>
    <circle cx="1300" cy="628" r="26" fill="#6aa052"/>
  </g>
`;
  return wrapSvg(body);
};

const reconstructionSvg = ({ title, subtitle, area, style }) => {
  const base = siteBase(title, subtitle, area);
  const overlay = style.includes('roof') || style.includes('attic') ? '#9b273d' : '#0b7a61';
  return wrapSvg(base + `
  <g filter="url(#shadow)">
    <rect x="360" y="360" width="780" height="246" fill="#efe9dc"/>
    <polygon points="320,360 760,244 1180,360" fill="#34333a"/>
    <rect x="440" y="404" width="160" height="96" rx="8" fill="url(#glass)"/>
    <rect x="680" y="404" width="190" height="96" rx="8" fill="url(#glass)"/>
    <rect x="940" y="410" width="82" height="196" rx="7" fill="#243142"/>
    <rect x="358" y="606" width="784" height="32" fill="#b8b0a3"/>
    <rect x="1050" y="278" width="280" height="82" rx="16" fill="${overlay}" opacity=".94"/>
    <text x="1080" y="330" font-family="Arial, sans-serif" font-size="30" font-weight="700" fill="#fff">${style.includes('roof') ? 'КРОВЛЯ' : style.includes('extension') ? 'ПРИСТРОЙКА' : 'ДО / ПОСЛЕ'}</text>
  </g>
  <path d="M440 680 H1120" stroke="${overlay}" stroke-width="9" stroke-dasharray="18 18"/>
  <text x="474" y="724" font-family="Arial, sans-serif" font-size="26" fill="#26313d">Схема работ и обновления объекта</text>
  `);
};

const interiorSvg = ({ title, subtitle, area, style }) => {
  const accent = style.includes('bath') ? '#5c8fab' : style.includes('office') ? '#0c6f61' : style.includes('kitchen') ? '#b66a2d' : '#2f6f8f';
  const isBath = style.includes('bath');
  const isOffice = style.includes('office');
  return wrapSvg(`
  <rect width="1536" height="864" fill="#f5f7f8"/>
  <rect x="0" y="0" width="1536" height="340" fill="#dfe9ee"/>
  <path d="M0 340 L1536 340 L1380 864 L155 864 Z" fill="#e8ded2"/>
  ${labelBlock(title, subtitle, area)}
  <g filter="url(#shadow)">
    <rect x="334" y="238" width="870" height="420" rx="18" fill="#ffffff"/>
    <rect x="334" y="238" width="870" height="210" rx="18" fill="#eef3f5"/>
    <rect x="398" y="300" width="260" height="118" rx="12" fill="url(#glass)"/>
    <rect x="710" y="300" width="386" height="118" rx="12" fill="url(#glass)"/>
    ${isBath ? `
      <rect x="438" y="494" width="270" height="92" rx="46" fill="#ffffff" stroke="${accent}" stroke-width="12"/>
      <rect x="780" y="490" width="130" height="118" rx="18" fill="#d6e8ef"/>
      <rect x="964" y="500" width="100" height="92" rx="20" fill="#f7f7f1"/>
    ` : isOffice ? `
      ${[0, 1, 2, 3].map((n) => `<rect x="${430 + n * 155}" y="488" width="112" height="58" rx="10" fill="#ffffff" stroke="${accent}" stroke-width="6"/><rect x="${454 + n * 155}" y="562" width="64" height="58" rx="12" fill="#34414b"/>`).join('')}
      <rect x="960" y="482" width="130" height="116" rx="12" fill="#ffffff" stroke="${accent}" stroke-width="6"/>
    ` : `
      <rect x="414" y="486" width="310" height="86" rx="14" fill="#ffffff" stroke="${accent}" stroke-width="8"/>
      <rect x="766" y="480" width="186" height="104" rx="22" fill="${accent}" opacity=".9"/>
      <rect x="982" y="502" width="98" height="80" rx="12" fill="#303b47"/>
    `}
    <rect x="334" y="638" width="870" height="34" fill="${accent}" opacity=".85"/>
  </g>
  <text x="432" y="730" font-family="Arial, sans-serif" font-size="26" fill="#4f5f72">Визуал помещения и базовая расстановка</text>
`);
};

const planSvg = ({ title, subtitle, area, floor = 1, style }) => {
  const isOffice = style.includes('office');
  const isBath = style.includes('bath');
  const rooms = floor === 2
    ? ['Холл', 'Мастер', 'Спальня', 'Спальня', 'Санузел', 'Гардероб']
    : isOffice
      ? ['Open space', 'Ресепшен', 'Переговорная', 'Кабинеты', 'Кухня', 'Санузлы']
      : isBath
        ? ['Душ', 'Ванна', 'Раковина', 'Инсталляция', 'Стиральная зона']
        : ['Кухня-гостиная', 'Спальня', 'Спальня', 'Санузел', 'Котельная', 'Холл'];
  return wrapSvg(`
  <rect width="1536" height="864" fill="#f7f8f6"/>
  ${labelBlock(`${title} · план`, floor > 1 ? `этаж ${floor}` : subtitle, area)}
  <g transform="translate(230 190)" filter="url(#shadow)">
    <rect x="0" y="0" width="1080" height="560" rx="18" fill="#ffffff" stroke="#1d2835" stroke-width="10"/>
    <rect x="38" y="38" width="520" height="230" fill="#eaf2f5" stroke="#1d2835" stroke-width="6"/>
    <rect x="558" y="38" width="484" height="230" fill="#f5eee7" stroke="#1d2835" stroke-width="6"/>
    <rect x="38" y="268" width="330" height="252" fill="#eef5ea" stroke="#1d2835" stroke-width="6"/>
    <rect x="368" y="268" width="330" height="252" fill="#f5f1e4" stroke="#1d2835" stroke-width="6"/>
    <rect x="698" y="268" width="344" height="252" fill="#edf0f6" stroke="#1d2835" stroke-width="6"/>
    ${rooms.map((room, index) => {
      const coords = [[74, 112], [600, 112], [74, 346], [404, 346], [734, 346], [760, 478]][index] || [92, 92];
      return `<text x="${coords[0]}" y="${coords[1]}" font-family="Arial, sans-serif" font-size="30" font-weight="700" fill="#152132">${esc(room)}</text>`;
    }).join('')}
    <path d="M520 268 C520 306 552 332 590 332" fill="none" stroke="#0b7a61" stroke-width="6"/>
    <path d="M698 420 C738 420 764 388 764 350" fill="none" stroke="#0b7a61" stroke-width="6"/>
  </g>
  <text x="260" y="805" font-family="Arial, sans-serif" font-size="25" fill="#64748b">Предпроектная схема: зоны, комнаты и логика движения</text>
`);
};

const schemeSvg = ({ title, subtitle, area, style }) => (
  style.includes('roof') || style.includes('facade') || style.includes('reconstruction') || style.includes('attic') || style.includes('extension')
    ? reconstructionSvg({ title, subtitle, area, style })
    : interiorSvg({ title, subtitle, area, style })
);

const renderPng = (outDir, fileName, svg) => {
  fs.mkdirSync(tmpRoot, { recursive: true });
  const tmpSvg = path.join(tmpRoot, `${path.basename(outDir)}-${fileName}.svg`);
  const outPng = path.join(outDir, fileName);
  fs.writeFileSync(tmpSvg, svg);

  const result = spawnSync(chromeBin, [
    '--headless=new',
    '--disable-gpu',
    '--no-sandbox',
    '--hide-scrollbars',
    `--screenshot=${outPng}`,
    '--window-size=1536,864',
    pathToFileURL(tmpSvg).href,
  ], { encoding: 'utf8' });

  if (result.status !== 0) {
    throw new Error([
      `Failed to render ${outPng}`,
      result.stderr,
      result.stdout,
    ].filter(Boolean).join('\n'));
  }
};

const renderFiles = (slug, style, title, subtitle, area) => {
  const out = path.join(root, slug);
  fs.mkdirSync(out, { recursive: true });
  const twoFloor = ['h2-', 'b2-', 'gar-', 'town-'].some((prefix) => slug.startsWith(prefix));
  const isInterior = ['apt-', 'fin-', 'bath-', 'kit-', 'off-'].some((prefix) => slug.startsWith(prefix));
  const isScheme = ['rec-', 'fac-', 'roof-'].some((prefix) => slug.startsWith(prefix));

  if (isInterior) {
    renderPng(out, 'facade.png', interiorSvg({ title, subtitle, area, style }));
    renderPng(out, 'side.png', interiorSvg({ title, subtitle: `${subtitle} · второй ракурс`, area, style }));
    renderPng(out, 'plan.png', planSvg({ title, subtitle, area, style }));
    return;
  }

  if (isScheme) {
    renderPng(out, 'facade.png', schemeSvg({ title, subtitle, area, style }));
    renderPng(out, 'side.png', reconstructionSvg({ title, subtitle: `${subtitle} · узел`, area, style: `${style} roof` }));
    renderPng(out, 'plan.png', planSvg({ title, subtitle, area, style }));
    return;
  }

  renderPng(out, 'facade.png', houseSvg({ title, subtitle, area, style }));
  renderPng(out, 'side.png', houseSvg({ title, subtitle: `${subtitle} · боковой ракурс`, area, style, side: true }));
  if (twoFloor) {
    renderPng(out, 'plan-1.png', planSvg({ title, subtitle, area, floor: 1, style }));
    renderPng(out, 'plan-2.png', planSvg({ title, subtitle, area, floor: 2, style }));
  } else {
    renderPng(out, 'plan.png', planSvg({ title, subtitle, area, style }));
  }
};

const requestedSlugs = new Set(process.argv.slice(2).map((item) => item.toLowerCase()));
const targetProjects = requestedSlugs.size
  ? projects.filter(([slug]) => requestedSlugs.has(slug))
  : projects;

if (!targetProjects.length) {
  throw new Error(`No matching project slugs: ${[...requestedSlugs].join(', ')}`);
}

targetProjects.forEach(([slug, style, title, subtitle, area]) => {
  renderFiles(slug, style, title, subtitle, area);
});

console.log(`Generated ${targetProjects.length} public project PNG asset sets in ${root}`);

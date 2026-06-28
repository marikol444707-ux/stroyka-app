#!/usr/bin/env node

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync, spawn } = require('child_process');
const { pathToFileURL } = require('url');

const root = path.resolve(__dirname, '..', 'public', 'site-assets', 'projects');
const tmpRoot = path.join(os.tmpdir(), 'stroyka-public-project-plans');
const chromeBin = process.env.CHROME_BIN || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const W = 1600;
const H = 900;

const fills = {
  living: '#f3eee4',
  kitchen: '#f5efe5',
  bed: '#fff8ee',
  bath: '#eaf4f7',
  service: '#edf0f4',
  hall: '#f7f3e8',
  garage: '#eceff1',
  terrace: '#f2efe4',
  work: '#eef5f0',
  void: '#f7fafc',
  scheme: '#f4f7f3',
};

const esc = (value) => String(value).replace(/[&<>"]/g, (char) => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
}[char]));

const svg = (body) => `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img">
  <defs>
    <filter id="paperShadow" x="-15%" y="-20%" width="130%" height="140%">
      <feDropShadow dx="0" dy="22" stdDeviation="24" flood-color="#1d2733" flood-opacity=".16"/>
    </filter>
    <pattern id="tileGrid" width="34" height="34" patternUnits="userSpaceOnUse">
      <path d="M34 0H0V34" fill="none" stroke="#d5dde5" stroke-width="1.4"/>
    </pattern>
    <pattern id="hatch" width="18" height="18" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <line x1="0" y1="0" x2="0" y2="18" stroke="#23856d" stroke-width="4" opacity=".35"/>
    </pattern>
  </defs>
  ${body}
</svg>`;

const textBlock = (x, y, lines, opts = {}) => {
  const size = opts.size || 22;
  const weight = opts.weight || 700;
  const fill = opts.fill || '#172033';
  const anchor = opts.anchor || 'middle';
  const gap = Math.round(size * 1.12);
  return lines.map((line, index) => (
    `<text x="${x}" y="${y + index * gap}" font-family="Arial, sans-serif" font-size="${size}" font-weight="${weight}" fill="${fill}" text-anchor="${anchor}">${esc(line)}</text>`
  )).join('');
};

const wrapLabel = (label, max = 14) => {
  const words = String(label).split(/\s+/);
  const lines = [];
  let current = '';
  words.forEach((word) => {
    const next = current ? `${current} ${word}` : word;
    if (next.length > max && current) {
      lines.push(current);
      current = word;
    } else {
      current = next;
    }
  });
  if (current) lines.push(current);
  return lines.slice(0, 3);
};

const titleCard = ({ code, title, subtitle, area, level }) => `
  <rect x="70" y="48" width="740" height="118" rx="24" fill="#ffffff" opacity=".96"/>
  <text x="100" y="95" font-family="Arial, sans-serif" font-size="26" font-weight="800" letter-spacing="2" fill="#176b56">${esc(code)}</text>
  <text x="100" y="132" font-family="Arial, sans-serif" font-size="30" font-weight="800" fill="#101828">${esc(title)}</text>
  <text x="100" y="158" font-family="Arial, sans-serif" font-size="21" font-weight="600" fill="#667085">${esc([level, subtitle, area].filter(Boolean).join(' · '))}</text>
`;

const backdrop = (def) => `
  <rect width="${W}" height="${H}" fill="#f7f8f6"/>
  <path d="M0 0H1600V242H0Z" fill="#eef3f1"/>
  <path d="M0 242C250 220 370 270 545 246C850 202 1000 258 1600 214V900H0Z" fill="#fbfaf6"/>
  ${titleCard(def)}
`;

const drawFixture = (room, fixture, box) => {
  const fx = box.x + box.w * (fixture.x ?? 0.08);
  const fy = box.y + box.h * (fixture.y ?? 0.08);
  const fw = box.w * (fixture.w ?? 0.32);
  const fh = box.h * (fixture.h ?? 0.28);
  const stroke = '#6f7784';
  const light = '#ffffff';

  if (fixture.type === 'bed') {
    return `
      <rect x="${fx}" y="${fy}" width="${fw}" height="${fh}" rx="8" fill="${light}" stroke="${stroke}" stroke-width="2"/>
      <rect x="${fx + fw * .08}" y="${fy + fh * .08}" width="${fw * .34}" height="${fh * .22}" rx="4" fill="#f4f4f0" stroke="${stroke}" stroke-width="1.4"/>
      <rect x="${fx + fw * .58}" y="${fy + fh * .08}" width="${fw * .34}" height="${fh * .22}" rx="4" fill="#f4f4f0" stroke="${stroke}" stroke-width="1.4"/>
    `;
  }
  if (fixture.type === 'singleBed') {
    return `
      <rect x="${fx}" y="${fy}" width="${fw}" height="${fh}" rx="8" fill="${light}" stroke="${stroke}" stroke-width="2"/>
      <rect x="${fx + fw * .08}" y="${fy + fh * .08}" width="${fw * .36}" height="${fh * .28}" rx="4" fill="#f4f4f0" stroke="${stroke}" stroke-width="1.4"/>
    `;
  }
  if (fixture.type === 'sofa') {
    return `
      <rect x="${fx}" y="${fy + fh * .36}" width="${fw}" height="${fh * .48}" rx="10" fill="${light}" stroke="${stroke}" stroke-width="2"/>
      <rect x="${fx}" y="${fy}" width="${fw * .36}" height="${fh * .84}" rx="10" fill="${light}" stroke="${stroke}" stroke-width="2"/>
      <rect x="${fx + fw * .46}" y="${fy + fh * .02}" width="${fw * .32}" height="${fh * .28}" rx="6" fill="#fffaf2" stroke="${stroke}" stroke-width="1.5"/>
    `;
  }
  if (fixture.type === 'table') {
    return `
      <rect x="${fx}" y="${fy}" width="${fw}" height="${fh}" rx="8" fill="${light}" stroke="${stroke}" stroke-width="2"/>
      ${[0, 1, 2].map((i) => `<rect x="${fx + fw * (.12 + i * .28)}" y="${fy - 13}" width="${fw * .13}" height="20" rx="4" fill="#fff" stroke="${stroke}" stroke-width="1.4"/>`).join('')}
      ${[0, 1, 2].map((i) => `<rect x="${fx + fw * (.12 + i * .28)}" y="${fy + fh - 7}" width="${fw * .13}" height="20" rx="4" fill="#fff" stroke="${stroke}" stroke-width="1.4"/>`).join('')}
    `;
  }
  if (fixture.type === 'kitchen') {
    return `
      <rect x="${box.x + box.w * .05}" y="${box.y + box.h * .06}" width="${box.w * .9}" height="${Math.max(24, box.h * .13)}" fill="#ffffff" stroke="${stroke}" stroke-width="2"/>
      <rect x="${box.x + box.w * .58}" y="${box.y + box.h * .075}" width="${box.w * .11}" height="${Math.max(14, box.h * .07)}" rx="4" fill="#eef7fb" stroke="${stroke}" stroke-width="1.4"/>
      <circle cx="${box.x + box.w * .78}" cy="${box.y + box.h * .125}" r="${Math.max(5, box.h * .025)}" fill="none" stroke="${stroke}" stroke-width="1.4"/>
      <circle cx="${box.x + box.w * .84}" cy="${box.y + box.h * .125}" r="${Math.max(5, box.h * .025)}" fill="none" stroke="${stroke}" stroke-width="1.4"/>
    `;
  }
  if (fixture.type === 'bath') {
    return `
      <rect x="${fx}" y="${fy}" width="${fw}" height="${fh * .45}" rx="18" fill="#ffffff" stroke="${stroke}" stroke-width="2"/>
      <circle cx="${fx + fw * .18}" cy="${fy + fh * .72}" r="${Math.max(9, fh * .13)}" fill="#ffffff" stroke="${stroke}" stroke-width="2"/>
      <rect x="${fx + fw * .58}" y="${fy + fh * .58}" width="${fw * .32}" height="${fh * .27}" rx="5" fill="#ffffff" stroke="${stroke}" stroke-width="2"/>
    `;
  }
  if (fixture.type === 'shower') {
    return `
      <rect x="${fx}" y="${fy}" width="${fw}" height="${fh}" rx="5" fill="#ffffff" stroke="${stroke}" stroke-width="2"/>
      <path d="M${fx + 8} ${fy + fh - 8}L${fx + fw - 8} ${fy + 8}" stroke="#9cb5c2" stroke-width="2"/>
    `;
  }
  if (fixture.type === 'wc') {
    return `
      <circle cx="${fx + fw * .5}" cy="${fy + fh * .52}" r="${Math.min(fw, fh) * .28}" fill="#ffffff" stroke="${stroke}" stroke-width="2"/>
      <rect x="${fx + fw * .25}" y="${fy}" width="${fw * .5}" height="${fh * .24}" rx="4" fill="#ffffff" stroke="${stroke}" stroke-width="2"/>
    `;
  }
  if (fixture.type === 'wardrobe') {
    return `
      <rect x="${fx}" y="${fy}" width="${fw}" height="${fh}" fill="#ffffff" stroke="${stroke}" stroke-width="2"/>
      ${[1, 2, 3, 4].map((i) => `<line x1="${fx + fw * i / 5}" y1="${fy}" x2="${fx + fw * i / 5}" y2="${fy + fh}" stroke="${stroke}" stroke-width="1.2"/>`).join('')}
    `;
  }
  if (fixture.type === 'stairs') {
    return `
      <rect x="${fx}" y="${fy}" width="${fw}" height="${fh}" fill="#ffffff" stroke="${stroke}" stroke-width="2"/>
      ${[1, 2, 3, 4, 5, 6].map((i) => `<line x1="${fx}" y1="${fy + fh * i / 7}" x2="${fx + fw}" y2="${fy + fh * i / 7}" stroke="${stroke}" stroke-width="1.4"/>`).join('')}
      <path d="M${fx + fw * .2} ${fy + fh * .78}L${fx + fw * .78} ${fy + fh * .22}" stroke="#176b56" stroke-width="3" marker-end="none"/>
    `;
  }
  if (fixture.type === 'car') {
    return `
      <rect x="${fx}" y="${fy}" width="${fw}" height="${fh}" rx="18" fill="#ffffff" stroke="${stroke}" stroke-width="2.5"/>
      <rect x="${fx + fw * .18}" y="${fy + fh * .18}" width="${fw * .64}" height="${fh * .35}" rx="10" fill="#edf4f7" stroke="${stroke}" stroke-width="1.5"/>
      <circle cx="${fx + fw * .18}" cy="${fy + fh * .88}" r="${fh * .08}" fill="#606b76"/>
      <circle cx="${fx + fw * .82}" cy="${fy + fh * .88}" r="${fh * .08}" fill="#606b76"/>
    `;
  }
  if (fixture.type === 'desks') {
    const rows = fixture.rows || 2;
    const cols = fixture.cols || 4;
    const deskW = fw / cols * .72;
    const deskH = fh / rows * .42;
    let out = '';
    for (let r = 0; r < rows; r += 1) {
      for (let c = 0; c < cols; c += 1) {
        const dx = fx + c * (fw / cols) + fw / cols * .12;
        const dy = fy + r * (fh / rows) + fh / rows * .18;
        out += `<rect x="${dx}" y="${dy}" width="${deskW}" height="${deskH}" rx="5" fill="#ffffff" stroke="${stroke}" stroke-width="1.7"/><rect x="${dx + deskW * .28}" y="${dy + deskH + 5}" width="${deskW * .4}" height="${deskH * .45}" rx="5" fill="#3c4854"/>`;
      }
    }
    return out;
  }
  if (fixture.type === 'meeting') {
    return `
      <rect x="${fx}" y="${fy}" width="${fw}" height="${fh}" rx="14" fill="#ffffff" stroke="${stroke}" stroke-width="2"/>
      ${[0, 1, 2, 3].map((i) => `<rect x="${fx + fw * (.12 + i * .2)}" y="${fy - 14}" width="${fw * .09}" height="22" rx="4" fill="#fff" stroke="${stroke}" stroke-width="1.2"/>`).join('')}
      ${[0, 1, 2, 3].map((i) => `<rect x="${fx + fw * (.12 + i * .2)}" y="${fy + fh - 8}" width="${fw * .09}" height="22" rx="4" fill="#fff" stroke="${stroke}" stroke-width="1.2"/>`).join('')}
    `;
  }
  if (fixture.type === 'laundry') {
    return `
      <rect x="${fx}" y="${fy}" width="${fw * .44}" height="${fh}" rx="5" fill="#ffffff" stroke="${stroke}" stroke-width="2"/>
      <circle cx="${fx + fw * .22}" cy="${fy + fh * .56}" r="${Math.min(fw, fh) * .12}" fill="none" stroke="${stroke}" stroke-width="2"/>
      <rect x="${fx + fw * .54}" y="${fy}" width="${fw * .44}" height="${fh}" rx="5" fill="#ffffff" stroke="${stroke}" stroke-width="2"/>
      <circle cx="${fx + fw * .76}" cy="${fy + fh * .56}" r="${Math.min(fw, fh) * .12}" fill="none" stroke="${stroke}" stroke-width="2"/>
    `;
  }
  return '';
};

const autoFixtures = (room) => {
  if (room.fixtures) return room.fixtures;
  const label = room.label.toLowerCase();
  if (room.type === 'garage') return [{ type: 'car', x: .16, y: .18, w: .66, h: .56 }];
  if (label.includes('лест')) return [{ type: 'stairs', x: .18, y: .14, w: .64, h: .72 }];
  if (label.includes('кухня-гостиная')) return [
    { type: 'kitchen' },
    { type: 'sofa', x: .53, y: .47, w: .31, h: .28 },
    { type: 'table', x: .34, y: .43, w: .25, h: .19 },
  ];
  if (label.includes('гостиная')) return [
    { type: 'sofa', x: .14, y: .38, w: .36, h: .28 },
    { type: 'table', x: .56, y: .38, w: .28, h: .2 },
  ];
  if (label.includes('кухня')) return [{ type: 'kitchen' }, { type: 'table', x: .42, y: .42, w: .36, h: .22 }];
  if (label.includes('мастер')) return [{ type: 'bed', x: .12, y: .16, w: .45, h: .44 }, { type: 'wardrobe', x: .65, y: .12, w: .18, h: .62 }];
  if (label.includes('спаль') || label.includes('детск') || label.includes('гостевая')) return [{ type: 'bed', x: .12, y: .18, w: .48, h: .42 }, { type: 'wardrobe', x: .68, y: .18, w: .18, h: .5 }];
  if (label.includes('кабинет')) return [{ type: 'desks', x: .18, y: .22, w: .58, h: .48, rows: 1, cols: 1 }];
  if (label.includes('сануз') || label.includes('ванн')) return [{ type: 'bath', x: .12, y: .18, w: .72, h: .58 }];
  if (label.includes('душ')) return [{ type: 'shower', x: .12, y: .18, w: .34, h: .46 }, { type: 'wc', x: .58, y: .19, w: .24, h: .36 }];
  if (label.includes('постир') || label.includes('хоз')) return [{ type: 'laundry', x: .16, y: .22, w: .58, h: .46 }];
  if (label.includes('open space')) return [{ type: 'desks', x: .08, y: .16, w: .82, h: .64, rows: room.rows || 2, cols: room.cols || 4 }];
  if (label.includes('переговор')) return [{ type: 'meeting', x: .16, y: .24, w: .68, h: .42 }];
  return [];
};

const drawRoom = (room, m) => {
  const x = m.ox + room.x * m.s;
  const y = m.oy + room.y * m.s;
  const w = room.w * m.s;
  const h = room.h * m.s;
  const fill = fills[room.type] || fills.hall;
  const stroke = room.outdoor ? '#b7b0a4' : '#252a2f';
  const sw = room.outdoor ? 3 : Math.max(6, 0.085 * m.s);
  const dash = room.outdoor ? ' stroke-dasharray="10 10"' : '';
  const wrapLimit = w < 180 ? 9 : w < 260 ? 12 : 15;
  const labelLines = wrapLabel(room.label, wrapLimit);
  const longestLabel = Math.max(...labelLines.map((line) => line.length), 1);
  const labelSize = Math.max(12, Math.min(23, w / (longestLabel * .72), h / (labelLines.length * 1.65)));
  const tile = room.tile ? `url(#tileGrid)` : fill;
  const windows = (room.windows || []).map((side) => {
    if (side === 'top') return `<line x1="${x + w * .18}" y1="${y + sw / 2}" x2="${x + w * .82}" y2="${y + sw / 2}" stroke="#dff6ff" stroke-width="${Math.max(5, sw * .8)}" stroke-linecap="round"/>`;
    if (side === 'bottom') return `<line x1="${x + w * .18}" y1="${y + h - sw / 2}" x2="${x + w * .82}" y2="${y + h - sw / 2}" stroke="#dff6ff" stroke-width="${Math.max(5, sw * .8)}" stroke-linecap="round"/>`;
    if (side === 'left') return `<line x1="${x + sw / 2}" y1="${y + h * .2}" x2="${x + sw / 2}" y2="${y + h * .8}" stroke="#dff6ff" stroke-width="${Math.max(5, sw * .8)}" stroke-linecap="round"/>`;
    if (side === 'right') return `<line x1="${x + w - sw / 2}" y1="${y + h * .2}" x2="${x + w - sw / 2}" y2="${y + h * .8}" stroke="#dff6ff" stroke-width="${Math.max(5, sw * .8)}" stroke-linecap="round"/>`;
    return '';
  }).join('');
  const fixtureSvg = autoFixtures(room).map((fixture) => drawFixture(room, fixture, { x, y, w, h })).join('');
  const labelSvg = room.hideLabel ? '' : textBlock(x + w / 2, y + h * .55, labelLines, {
    size: labelSize,
    weight: 700,
    fill: room.outdoor ? '#585f68' : '#1c2530',
  });

  return `
    <rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${tile}" stroke="${stroke}" stroke-width="${sw}"${dash}/>
    ${fixtureSvg}
    ${labelSvg}
    ${windows}
  `;
};

const drawPlan = (def) => {
  const maxW = 1140;
  const maxH = 600;
  const allZones = [...def.rooms, ...(def.outdoor || [])];
  const contentW = Math.max(def.width, ...allZones.map((room) => room.x + room.w));
  const contentH = Math.max(def.height, ...allZones.map((room) => room.y + room.h));
  const s = Math.min(maxW / contentW, maxH / contentH);
  const planW = contentW * s;
  const planH = contentH * s;
  const ox = (W - planW) / 2;
  const oy = 195 + (maxH - planH) / 2;
  const m = { s, ox, oy };
  const outdoor = (def.outdoor || []).map((room) => drawRoom({ ...room, outdoor: true }, m)).join('');
  const rooms = def.rooms.map((room) => drawRoom(room, m)).join('');
  const dimTop = `<line x1="${ox}" y1="${oy - 24}" x2="${ox + planW}" y2="${oy - 24}" stroke="#6b7280" stroke-width="2"/><text x="${ox + planW / 2}" y="${oy - 34}" font-family="Arial, sans-serif" font-size="20" font-weight="700" fill="#4b5563" text-anchor="middle">${esc(def.dimX || `${Math.round(def.width)} м`)}</text>`;
  const dimSide = `<line x1="${ox + planW + 28}" y1="${oy}" x2="${ox + planW + 28}" y2="${oy + planH}" stroke="#6b7280" stroke-width="2"/><text x="${ox + planW + 58}" y="${oy + planH / 2}" font-family="Arial, sans-serif" font-size="20" font-weight="700" fill="#4b5563" text-anchor="middle" transform="rotate(90 ${ox + planW + 58} ${oy + planH / 2})">${esc(def.dimY || `${Math.round(def.height)} м`)}</text>`;

  return svg(`
    ${backdrop(def)}
    <g filter="url(#paperShadow)">
      <rect x="${ox - 32}" y="${oy - 44}" width="${planW + 84}" height="${planH + 92}" rx="22" fill="#ffffff"/>
      ${dimTop}
      ${dimSide}
      ${outdoor}
      ${rooms}
    </g>
    <text x="110" y="828" font-family="Arial, sans-serif" font-size="22" font-weight="700" fill="#176b56">${esc(def.note || 'Предпроектная схема: помещения, мебель и логика движения')}</text>
    <text x="1490" y="828" font-family="Arial, sans-serif" font-size="18" font-weight="700" fill="#98a2b3" text-anchor="end">${esc(def.code)} · ${esc(def.file)}</text>
  `);
};

const r = (x, y, w, h, label, type, opts = {}) => ({ x, y, w, h, label, type, ...opts });

const definitions = [];
const add = (slug, file, def) => {
  definitions.push({
    slug,
    file,
    code: slug.toUpperCase(),
    ...def,
  });
};

const addHome = (slug, title, area, subtitle, width, height, rooms, outdoor = [], opts = {}) => add(slug, 'plan.png', {
  title, area, subtitle, width, height, rooms, outdoor, ...opts,
});

addHome('h1-01', 'Дом 105 м2 с террасой', '105 м2', '1 этаж', 14, 9.4, [
  r(0, 0, 3.4, 3.2, 'Спальня', 'bed', { windows: ['top'] }),
  r(3.4, 0, 2.1, 2.5, 'Санузел', 'bath', { tile: true, windows: ['top'] }),
  r(5.5, 0, 3.1, 3.2, 'Спальня', 'bed', { windows: ['top'] }),
  r(8.6, 0, 5.4, 6.2, 'Кухня-гостиная', 'living', { windows: ['top', 'right'] }),
  r(0, 3.2, 3.4, 3.4, 'Спальня', 'bed', { windows: ['left'] }),
  r(3.4, 2.5, 3.2, 4.1, 'Холл', 'hall'),
  r(6.6, 3.2, 2, 2.1, 'Котельная', 'service', { windows: ['bottom'] }),
  r(3.4, 6.6, 3.2, 2.2, 'Тамбур', 'hall'),
], [r(8.6, 6.2, 5.4, 2.3, 'Терраса', 'terrace')]);

addHome('h1-02', 'Дом 128 м2 с панорамной гостиной', '128 м2', '1 этаж', 16, 8.6, [
  r(0, 0, 4.4, 3.3, 'Мастер-спальня', 'bed', { windows: ['top'] }),
  r(4.4, 0, 2, 2.1, 'Санузел', 'bath', { tile: true }),
  r(6.4, 0, 2.3, 2.1, 'Гардероб', 'service', { fixtures: [{ type: 'wardrobe', x: .12, y: .18, w: .76, h: .46 }] }),
  r(8.7, 0, 7.3, 5.4, 'Кухня-гостиная', 'living', { windows: ['top', 'right'] }),
  r(0, 3.3, 4.1, 3.4, 'Спальня', 'bed', { windows: ['left'] }),
  r(4.1, 3.3, 3.2, 3.4, 'Спальня', 'bed'),
  r(6.4, 2.1, 2.3, 1.8, 'Котельная', 'service'),
  r(7.3, 3.9, 1.4, 2.8, 'Холл', 'hall'),
  r(4.1, 6.7, 4.6, 1.7, 'Тамбур', 'hall'),
], [r(10.2, 5.4, 4.8, 2.1, 'Панорамная терраса', 'terrace')], { dimX: '16 м', dimY: '8,6 м' });

addHome('h1-03', 'L-образный дом 145 м2', '145 м2', '1 этаж', 14.6, 10.2, [
  r(0, 0, 3.2, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(3.2, 0, 3.3, 3.1, 'Мастер-спальня', 'bed', { windows: ['top'] }),
  r(6.5, 0, 6.6, 4.7, 'Кухня-гостиная', 'living', { windows: ['top', 'right'] }),
  r(0, 3.1, 3.2, 3.2, 'Спальня', 'bed', { windows: ['left'] }),
  r(3.2, 3.1, 3.3, 3.2, 'Холл', 'hall'),
  r(6.5, 4.7, 2.2, 2.4, 'Санузел', 'bath', { tile: true }),
  r(0, 6.3, 4.3, 3.2, 'Спальня', 'bed', { windows: ['left', 'bottom'] }),
  r(4.3, 6.3, 2.2, 3.2, 'Постирочная', 'service'),
  r(8.7, 4.7, 2.6, 2.4, 'Котельная', 'service'),
], [r(6.5, 7.1, 5.2, 2.6, 'Внутренняя терраса', 'terrace')]);

addHome('b1-01', 'Кирпичный дом 120 м2', '120 м2', '1 этаж', 14.4, 8.8, [
  r(0, 0, 3.5, 3.2, 'Спальня', 'bed', { windows: ['top'] }),
  r(3.5, 0, 2.2, 2.4, 'Санузел', 'bath', { tile: true }),
  r(5.7, 0, 3.3, 3.2, 'Спальня', 'bed', { windows: ['top'] }),
  r(9, 0, 5.4, 5.8, 'Кухня-гостиная', 'living', { windows: ['top', 'right'] }),
  r(0, 3.2, 3.5, 3.2, 'Спальня', 'bed', { windows: ['left'] }),
  r(3.5, 2.4, 3.2, 4, 'Холл', 'hall'),
  r(6.7, 3.2, 2.3, 2.6, 'Котельная', 'service'),
  r(3.5, 6.4, 3.2, 2, 'Тамбур', 'hall'),
], [r(9.4, 5.8, 4.2, 1.7, 'Крыльцо', 'terrace')]);

addHome('b1-02', 'Дом 138 м2 с эркером', '138 м2', '1 этаж', 15.6, 9, [
  r(0, 0, 3.7, 3.2, 'Мастер-спальня', 'bed', { windows: ['top'] }),
  r(3.7, 0, 2.1, 2.1, 'Санузел', 'bath', { tile: true }),
  r(5.8, 0, 3.1, 3.2, 'Кабинет', 'work', { windows: ['top'] }),
  r(8.9, 0, 6.7, 5.5, 'Гостиная с эркером', 'living', { windows: ['top', 'right'] }),
  r(0, 3.2, 3.6, 3.1, 'Спальня', 'bed', { windows: ['left'] }),
  r(3.6, 2.1, 3.2, 4.2, 'Холл', 'hall'),
  r(6.8, 3.2, 2.1, 2.3, 'Санузел', 'bath', { tile: true }),
  r(0, 6.3, 3.6, 2.4, 'Спальня', 'bed', { windows: ['bottom'] }),
  r(3.6, 6.3, 5.3, 1.9, 'Тамбур / гардероб', 'hall'),
], [r(12.2, 5.5, 2.8, 1.7, 'Эркер', 'terrace')]);

addHome('b1-03', 'Кирпичный дом 155 м2 с террасой', '155 м2', '1 этаж', 16.2, 9.7, [
  r(0, 0, 3.4, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(3.4, 0, 3.2, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(6.6, 0, 2.2, 2.4, 'Санузел', 'bath', { tile: true }),
  r(8.8, 0, 7.4, 5.7, 'Кухня-гостиная', 'living', { windows: ['top', 'right'] }),
  r(0, 3.1, 3.4, 3.4, 'Мастер-спальня', 'bed', { windows: ['left'] }),
  r(3.4, 3.1, 3.2, 3.4, 'Спальня', 'bed'),
  r(6.6, 2.4, 2.2, 2.7, 'Санузел', 'bath', { tile: true }),
  r(3.4, 6.5, 3.2, 2.5, 'Холл', 'hall'),
  r(6.6, 5.1, 2.2, 2.2, 'Котельная', 'service'),
], [r(9.1, 5.7, 5.8, 2.3, 'Большая терраса', 'terrace')]);

addHome('fam-01', 'Коттедж 150 м2 для семьи', '150 м2', '1 этаж', 15.4, 9.4, [
  r(0, 0, 3.4, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(3.4, 0, 3.1, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(6.5, 0, 2.2, 2.4, 'Санузел', 'bath', { tile: true }),
  r(8.7, 0, 6.7, 5.8, 'Кухня-гостиная', 'living', { windows: ['top', 'right'] }),
  r(0, 3.1, 3.4, 3.2, 'Спальня', 'bed', { windows: ['left'] }),
  r(3.4, 3.1, 3.1, 3.2, 'Спальня', 'bed'),
  r(6.5, 2.4, 2.2, 2.3, 'Санузел', 'bath', { tile: true }),
  r(3.4, 6.3, 3.1, 2.3, 'Холл', 'hall'),
  r(6.5, 4.7, 2.2, 2.2, 'Кладовая', 'service'),
], [r(9.1, 5.8, 4.8, 2.1, 'Семейная терраса', 'terrace')]);

addHome('fam-02', 'Коттедж 170 м2 со вторым светом', '170 м2', '1 этаж', 16.2, 9.6, [
  r(0, 0, 3.8, 3.3, 'Мастер-спальня', 'bed', { windows: ['top'] }),
  r(3.8, 0, 2.3, 2.3, 'Санузел', 'bath', { tile: true }),
  r(6.1, 0, 3.2, 3.3, 'Кабинет', 'work', { windows: ['top'] }),
  r(9.3, 0, 6.9, 5.9, 'Гостиная второй свет', 'living', { windows: ['top', 'right'] }),
  r(0, 3.3, 3.6, 3.1, 'Спальня', 'bed', { windows: ['left'] }),
  r(3.6, 3.3, 2.5, 3.1, 'Спальня', 'bed'),
  r(6.1, 3.3, 3.2, 2.6, 'Холл / лестница', 'hall', { fixtures: [{ type: 'stairs', x: .24, y: .16, w: .5, h: .64 }] }),
  r(3.6, 6.4, 2.5, 2.1, 'Санузел', 'bath', { tile: true }),
  r(6.1, 5.9, 3.2, 2.2, 'Котельная', 'service'),
], [r(10.2, 5.9, 4.8, 2.1, 'Терраса', 'terrace')]);

addHome('fam-03', 'Коттедж 185 м2 с гостевой комнатой', '185 м2', '1 этаж', 17, 10, [
  r(0, 0, 3.3, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(3.3, 0, 3.2, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(6.5, 0, 3.1, 3.1, 'Гостевая', 'bed', { windows: ['top'] }),
  r(9.6, 0, 7.4, 5.8, 'Кухня-гостиная', 'living', { windows: ['top', 'right'] }),
  r(0, 3.1, 3.3, 3.3, 'Мастер-спальня', 'bed', { windows: ['left'] }),
  r(3.3, 3.1, 3.2, 3.3, 'Спальня', 'bed'),
  r(6.5, 3.1, 2.2, 2.3, 'Санузел', 'bath', { tile: true }),
  r(8.7, 3.1, .9, 2.3, 'Холл', 'hall'),
  r(3.3, 6.4, 3.2, 2.5, 'Постирочная', 'service'),
  r(6.5, 5.4, 3.1, 3.5, 'Холл / кладовая', 'hall'),
], [r(10, 5.8, 5.7, 2.4, 'Терраса', 'terrace')]);

const addTwoFloor = (slug, title, area, subtitle, width, height, floor1, floor2, outdoor1 = [], outdoor2 = [], opts = {}) => {
  add(slug, 'plan-1.png', { title, area, subtitle, level: '1 этаж', width, height, rooms: floor1, outdoor: outdoor1, ...opts });
  add(slug, 'plan-2.png', { title, area, subtitle, level: '2 этаж', width, height, rooms: floor2, outdoor: outdoor2, ...opts });
};

const floorOneBase = [
  r(0, 0, 2.2, 2.2, 'Кабинет', 'work', { windows: ['top'] }),
  r(2.2, 0, 1.8, 2.2, 'Санузел', 'bath', { tile: true }),
  r(4, 0, 2, 2.2, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .18, y: .13, w: .64, h: .72 }] }),
  r(0, 2.2, 2.8, 2.4, 'Холл', 'hall'),
  r(2.8, 2.2, 3.2, 2.4, 'Котельная', 'service'),
  r(0, 4.6, 6, 5.2, 'Кухня-гостиная', 'living', { windows: ['left', 'bottom', 'right'] }),
];

const floorTwoBase = [
  r(0, 0, 3, 3.2, 'Мастер-спальня', 'bed', { windows: ['top'] }),
  r(3, 0, 3, 3.2, 'Спальня', 'bed', { windows: ['top'] }),
  r(0, 3.2, 2.1, 2.2, 'Санузел', 'bath', { tile: true }),
  r(2.1, 3.2, 1.8, 2.2, 'Гардероб', 'service', { fixtures: [{ type: 'wardrobe', x: .16, y: .18, w: .68, h: .5 }] }),
  r(3.9, 3.2, 2.1, 2.2, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .18, y: .13, w: .64, h: .72 }] }),
  r(0, 5.4, 3, 3.1, 'Спальня', 'bed', { windows: ['left', 'bottom'] }),
  r(3, 5.4, 3, 3.1, 'Холл', 'hall'),
];

addTwoFloor('h2-01', 'Дом 165 м2 на узкий участок', '165 м2', 'узкий участок', 6, 10.1, floorOneBase, floorTwoBase, [r(.5, 9.8, 5, 1.5, 'Терраса', 'terrace')]);

addTwoFloor('h2-02', 'Дом 190 м2 со вторым светом', '190 м2', 'второй свет', 9.2, 8.8, [
  r(0, 0, 2.6, 2.4, 'Кабинет', 'work', { windows: ['top'] }),
  r(2.6, 0, 1.8, 2.4, 'Санузел', 'bath', { tile: true }),
  r(4.4, 0, 2.1, 2.4, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .2, y: .13, w: .6, h: .72 }] }),
  r(6.5, 0, 2.7, 2.4, 'Котельная', 'service', { windows: ['top'] }),
  r(0, 2.4, 9.2, 5.7, 'Кухня-гостиная', 'living', { windows: ['left', 'right', 'bottom'] }),
], [
  r(0, 0, 3.1, 3.2, 'Мастер-спальня', 'bed', { windows: ['top'] }),
  r(3.1, 0, 3.1, 3.2, 'Детская', 'bed', { windows: ['top'] }),
  r(6.2, 0, 3, 3.2, 'Детская', 'bed', { windows: ['top'] }),
  r(0, 3.2, 2.1, 2.2, 'Санузел', 'bath', { tile: true }),
  r(2.1, 3.2, 2.1, 2.2, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .2, y: .13, w: .6, h: .72 }] }),
  r(4.2, 3.2, 5, 2.2, 'Второй свет', 'void', { hideLabel: false }),
  r(0, 5.4, 4.2, 2.7, 'Холл', 'hall'),
  r(4.2, 5.4, 2, 2.7, 'Гардероб', 'service'),
], [r(1.2, 8.1, 6.8, 1.6, 'Терраса', 'terrace')]);

addTwoFloor('h2-03', 'Дом 215 м2 с балконом', '215 м2', 'балкон и терраса', 10.2, 9.2, [
  r(0, 0, 2.8, 2.6, 'Кабинет', 'work', { windows: ['top'] }),
  r(2.8, 0, 2.2, 2.6, 'Санузел', 'bath', { tile: true }),
  r(5, 0, 2.2, 2.6, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .2, y: .13, w: .6, h: .72 }] }),
  r(7.2, 0, 3, 2.6, 'Котельная', 'service', { windows: ['top'] }),
  r(0, 2.6, 10.2, 6.1, 'Большая кухня-гостиная', 'living', { windows: ['left', 'right', 'bottom'] }),
], [
  r(0, 0, 3, 3.1, 'Мастер-спальня', 'bed', { windows: ['top'] }),
  r(3, 0, 2.4, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(5.4, 0, 2.4, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(7.8, 0, 2.4, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(0, 3.1, 2.2, 2.4, 'Санузел', 'bath', { tile: true }),
  r(2.2, 3.1, 2.1, 2.4, 'Гардероб', 'service'),
  r(4.3, 3.1, 2.1, 2.4, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .2, y: .13, w: .6, h: .72 }] }),
  r(6.4, 3.1, 3.8, 2.4, 'Холл', 'hall'),
], [r(1.2, 8.7, 7.8, 1.6, 'Терраса', 'terrace')], [r(6.4, 5.5, 2.8, 1.4, 'Балкон', 'terrace')]);

addTwoFloor('b2-01', 'Кирпичный дом 180 м2', '180 м2', 'классический фасад', 9.2, 8.9, [
  r(0, 0, 2.4, 2.4, 'Гостевая', 'bed', { windows: ['top'] }),
  r(2.4, 0, 1.9, 2.4, 'Санузел', 'bath', { tile: true }),
  r(4.3, 0, 2.1, 2.4, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .2, y: .13, w: .6, h: .72 }] }),
  r(6.4, 0, 2.8, 2.4, 'Котельная', 'service', { windows: ['top'] }),
  r(0, 2.4, 9.2, 5.8, 'Кухня-гостиная', 'living', { windows: ['left', 'right', 'bottom'] }),
], floorTwoBase, [r(1.2, 8.2, 6.8, 1.4, 'Терраса', 'terrace')]);

addTwoFloor('b2-02', 'Дом 210 м2 с гаражной зоной', '210 м2', 'хозблок и спальни', 11.2, 9, [
  r(0, 0, 3.4, 3.3, 'Гаражная зона', 'garage', { windows: ['top'] }),
  r(3.4, 0, 2.2, 2.2, 'Хозблок', 'service'),
  r(5.6, 0, 2.1, 2.2, 'Санузел', 'bath', { tile: true }),
  r(7.7, 0, 3.5, 2.2, 'Кабинет', 'work', { windows: ['top'] }),
  r(3.4, 2.2, 2.2, 2.8, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .2, y: .13, w: .6, h: .72 }] }),
  r(5.6, 2.2, 5.6, 5.7, 'Кухня-гостиная', 'living', { windows: ['right', 'bottom'] }),
  r(0, 3.3, 3.4, 4.6, 'Холл', 'hall'),
], [
  r(0, 0, 3.2, 3.1, 'Мастер-спальня', 'bed', { windows: ['top'] }),
  r(3.2, 0, 2.7, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(5.9, 0, 2.7, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(8.6, 0, 2.6, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(0, 3.1, 2.2, 2.3, 'Санузел', 'bath', { tile: true }),
  r(2.2, 3.1, 2.2, 2.3, 'Гардероб', 'service'),
  r(4.4, 3.1, 2.2, 2.3, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .2, y: .13, w: .6, h: .72 }] }),
  r(6.6, 3.1, 4.6, 2.3, 'Холл', 'hall'),
], [r(5.9, 7.9, 4.2, 1.5, 'Терраса', 'terrace')]);

addTwoFloor('b2-03', 'Классический дом 240 м2', '240 м2', '5 спален и кабинет', 11.5, 9.4, [
  r(0, 0, 2.8, 2.7, 'Кабинет', 'work', { windows: ['top'] }),
  r(2.8, 0, 2.2, 2.7, 'Санузел', 'bath', { tile: true }),
  r(5, 0, 2.4, 2.7, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .2, y: .13, w: .6, h: .72 }] }),
  r(7.4, 0, 4.1, 2.7, 'Гостевая', 'bed', { windows: ['top'] }),
  r(0, 2.7, 11.5, 6, 'Кухня-гостиная', 'living', { windows: ['left', 'right', 'bottom'] }),
], [
  r(0, 0, 3, 3.1, 'Мастер-спальня', 'bed', { windows: ['top'] }),
  r(3, 0, 2.8, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(5.8, 0, 2.8, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(8.6, 0, 2.9, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(0, 3.1, 2.4, 2.3, 'Санузел', 'bath', { tile: true }),
  r(2.4, 3.1, 2.2, 2.3, 'Санузел', 'bath', { tile: true }),
  r(4.6, 3.1, 2.3, 2.3, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .2, y: .13, w: .6, h: .72 }] }),
  r(6.9, 3.1, 4.6, 2.3, 'Холл', 'hall'),
], [r(1.4, 8.7, 8.5, 1.5, 'Терраса', 'terrace')]);

addTwoFloor('gar-01', 'Дом 190 м2 с гаражом', '190 м2', 'гараж 1 авто', 11.5, 8.8, [
  r(0, 0, 3.7, 4.8, 'Гараж', 'garage', { windows: ['top'] }),
  r(3.7, 0, 2, 2.4, 'Котельная', 'service'),
  r(5.7, 0, 2, 2.4, 'Санузел', 'bath', { tile: true }),
  r(7.7, 0, 3.8, 2.4, 'Кабинет', 'work', { windows: ['top'] }),
  r(3.7, 2.4, 2, 2.4, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .2, y: .13, w: .6, h: .72 }] }),
  r(5.7, 2.4, 5.8, 5.6, 'Кухня-гостиная', 'living', { windows: ['right', 'bottom'] }),
  r(0, 4.8, 5.7, 3.2, 'Холл', 'hall'),
], [
  r(0, 0, 3.1, 3.1, 'Мастер-спальня', 'bed', { windows: ['top'] }),
  r(3.1, 0, 2.8, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(5.9, 0, 2.8, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(8.7, 0, 2.8, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(0, 3.1, 2.2, 2.2, 'Санузел', 'bath', { tile: true }),
  r(2.2, 3.1, 2.2, 2.2, 'Гардероб', 'service'),
  r(4.4, 3.1, 2.2, 2.2, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .2, y: .13, w: .6, h: .72 }] }),
  r(6.6, 3.1, 4.9, 2.2, 'Холл', 'hall'),
], [r(6.1, 8, 4.6, 1.4, 'Терраса', 'terrace')]);

addTwoFloor('gar-02', 'Дом 230 м2 с гаражом на 2 авто', '230 м2', 'гараж 2 авто', 13, 9.3, [
  r(0, 0, 4.8, 5, 'Гараж 2 авто', 'garage', { fixtures: [{ type: 'car', x: .08, y: .18, w: .38, h: .54 }, { type: 'car', x: .54, y: .18, w: .38, h: .54 }], windows: ['top'] }),
  r(4.8, 0, 2.1, 2.5, 'Хоззона', 'service'),
  r(6.9, 0, 2.1, 2.5, 'Санузел', 'bath', { tile: true }),
  r(9, 0, 4, 2.5, 'Кабинет', 'work', { windows: ['top'] }),
  r(4.8, 2.5, 2.1, 2.5, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .2, y: .13, w: .6, h: .72 }] }),
  r(6.9, 2.5, 6.1, 5.8, 'Кухня-гостиная', 'living', { windows: ['right', 'bottom'] }),
  r(0, 5, 6.9, 3.3, 'Холл', 'hall'),
], [
  r(0, 0, 3.2, 3.1, 'Мастер-спальня', 'bed', { windows: ['top'] }),
  r(3.2, 0, 3, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(6.2, 0, 3, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(9.2, 0, 3.8, 3.1, 'Кабинет / спальня', 'bed', { windows: ['top'] }),
  r(0, 3.1, 2.3, 2.4, 'Санузел', 'bath', { tile: true }),
  r(2.3, 3.1, 2.3, 2.4, 'Гардероб', 'service'),
  r(4.6, 3.1, 2.3, 2.4, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .2, y: .13, w: .6, h: .72 }] }),
  r(6.9, 3.1, 6.1, 2.4, 'Холл', 'hall'),
], [r(7.6, 8.3, 4.6, 1.4, 'Терраса', 'terrace')]);

addTwoFloor('gar-03', 'Дом 210 м2 с мастерской', '210 м2', 'гараж и мастерская', 12.4, 9.1, [
  r(0, 0, 3.6, 4.4, 'Гараж', 'garage', { windows: ['top'] }),
  r(3.6, 0, 2.7, 4.4, 'Мастерская', 'work', { fixtures: [{ type: 'desks', x: .1, y: .2, w: .75, h: .5, rows: 1, cols: 2 }], windows: ['top'] }),
  r(6.3, 0, 2, 2.3, 'Котельная', 'service'),
  r(8.3, 0, 2, 2.3, 'Санузел', 'bath', { tile: true }),
  r(10.3, 0, 2.1, 2.3, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .2, y: .13, w: .6, h: .72 }] }),
  r(6.3, 2.3, 6.1, 5.9, 'Кухня-гостиная', 'living', { windows: ['right', 'bottom'] }),
  r(0, 4.4, 6.3, 3.8, 'Холл', 'hall'),
], [
  r(0, 0, 3.4, 3.1, 'Мастер-спальня', 'bed', { windows: ['top'] }),
  r(3.4, 0, 3, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(6.4, 0, 3, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(9.4, 0, 3, 3.1, 'Гостевая', 'bed', { windows: ['top'] }),
  r(0, 3.1, 2.3, 2.4, 'Санузел', 'bath', { tile: true }),
  r(2.3, 3.1, 2.2, 2.4, 'Гардероб', 'service'),
  r(4.5, 3.1, 2.3, 2.4, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .2, y: .13, w: .6, h: .72 }] }),
  r(6.8, 3.1, 5.6, 2.4, 'Холл', 'hall'),
], [r(7.1, 8.2, 4.4, 1.4, 'Терраса', 'terrace')]);

addTwoFloor('town-01', 'Таунхаус 95 м2', '95 м2', 'секция', 5.4, 10.5, [
  r(0, 0, 2.1, 2.2, 'Прихожая', 'hall'),
  r(2.1, 0, 1.5, 2.2, 'Санузел', 'bath', { tile: true }),
  r(3.6, 0, 1.8, 2.2, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .14, y: .12, w: .7, h: .72 }] }),
  r(0, 2.2, 5.4, 6.8, 'Кухня-гостиная', 'living', { windows: ['left', 'right', 'bottom'] }),
], [
  r(0, 0, 2.7, 3.4, 'Спальня', 'bed', { windows: ['top'] }),
  r(2.7, 0, 2.7, 3.4, 'Спальня', 'bed', { windows: ['top'] }),
  r(0, 3.4, 1.8, 2.2, 'Санузел', 'bath', { tile: true }),
  r(1.8, 3.4, 1.8, 2.2, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .14, y: .12, w: .7, h: .72 }] }),
  r(3.6, 3.4, 1.8, 2.2, 'Гардероб', 'service'),
], [r(.6, 9, 4.2, 1.4, 'Дворик', 'terrace')]);

addTwoFloor('town-02', 'Таунхаус 120 м2 для семьи', '120 м2', 'семейная секция', 6.2, 11, [
  r(0, 0, 2.2, 2.2, 'Прихожая', 'hall'),
  r(2.2, 0, 1.7, 2.2, 'Санузел', 'bath', { tile: true }),
  r(3.9, 0, 2.3, 2.2, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .16, y: .12, w: .68, h: .72 }] }),
  r(0, 2.2, 6.2, 7.1, 'Кухня-гостиная', 'living', { windows: ['left', 'right', 'bottom'] }),
], [
  r(0, 0, 3.1, 3.3, 'Мастер-спальня', 'bed', { windows: ['top'] }),
  r(3.1, 0, 3.1, 3.3, 'Детская', 'bed', { windows: ['top'] }),
  r(0, 3.3, 2.3, 3, 'Детская', 'bed', { windows: ['left'] }),
  r(2.3, 3.3, 1.9, 2.2, 'Санузел', 'bath', { tile: true }),
  r(4.2, 3.3, 2, 2.2, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .16, y: .12, w: .68, h: .72 }] }),
], [r(.7, 9.3, 4.8, 1.4, 'Дворик', 'terrace')]);

addTwoFloor('town-03', 'Таунхаус 135 м2 с кабинетом', '135 м2', 'кабинет и 3 спальни', 6.6, 11.2, [
  r(0, 0, 2.1, 2.2, 'Кабинет', 'work', { windows: ['top'] }),
  r(2.1, 0, 1.7, 2.2, 'Санузел', 'bath', { tile: true }),
  r(3.8, 0, 2.8, 2.2, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .18, y: .12, w: .64, h: .72 }] }),
  r(0, 2.2, 6.6, 7.2, 'Кухня-гостиная', 'living', { windows: ['left', 'right', 'bottom'] }),
], [
  r(0, 0, 3.3, 3.2, 'Мастер-спальня', 'bed', { windows: ['top'] }),
  r(3.3, 0, 3.3, 3.2, 'Спальня', 'bed', { windows: ['top'] }),
  r(0, 3.2, 2.4, 3, 'Спальня', 'bed', { windows: ['left'] }),
  r(2.4, 3.2, 2.1, 2.2, 'Санузел', 'bath', { tile: true }),
  r(4.5, 3.2, 2.1, 2.2, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .18, y: .12, w: .64, h: .72 }] }),
], [r(.7, 9.4, 5.2, 1.4, 'Дворик', 'terrace')]);

const addApartment = (slug, title, area, rooms, width, height, subtitle = 'квартира') => addHome(slug, title, area, subtitle, width, height, rooms, [], { note: 'План ремонта: помещения, мебель и мокрые зоны' });

addApartment('apt-01', 'Ремонт квартиры 45 м2', '45 м2', [
  r(0, 0, 2.4, 2.2, 'Прихожая', 'hall'),
  r(2.4, 0, 2, 2.2, 'Санузел', 'bath', { tile: true }),
  r(4.4, 0, 4.2, 3.4, 'Кухня', 'kitchen', { windows: ['top'] }),
  r(0, 2.2, 4.4, 4.2, 'Спальня', 'bed', { windows: ['left', 'bottom'] }),
  r(4.4, 3.4, 4.2, 3, 'Гостиная', 'living', { windows: ['right', 'bottom'] }),
], 8.6, 6.4);

addApartment('apt-02', 'Ремонт квартиры 72 м2', '72 м2', [
  r(0, 0, 2.4, 2.3, 'Прихожая', 'hall'),
  r(2.4, 0, 2.1, 2.3, 'Санузел', 'bath', { tile: true }),
  r(4.5, 0, 3.2, 3.2, 'Спальня', 'bed', { windows: ['top'] }),
  r(7.7, 0, 3.2, 3.2, 'Спальня', 'bed', { windows: ['top'] }),
  r(0, 2.3, 4.5, 4.9, 'Холл / хранение', 'hall'),
  r(4.5, 3.2, 6.4, 4, 'Кухня-гостиная', 'living', { windows: ['right', 'bottom'] }),
], 10.9, 7.2);

addApartment('apt-03', 'Ремонт квартиры 95 м2', '95 м2', [
  r(0, 0, 2.6, 2.4, 'Прихожая', 'hall'),
  r(2.6, 0, 2.2, 2.4, 'Санузел', 'bath', { tile: true }),
  r(4.8, 0, 3.2, 3.2, 'Спальня', 'bed', { windows: ['top'] }),
  r(8, 0, 3.2, 3.2, 'Спальня', 'bed', { windows: ['top'] }),
  r(0, 2.4, 3.2, 3.3, 'Мастер-спальня', 'bed', { windows: ['left'] }),
  r(3.2, 2.4, 1.8, 2.2, 'Санузел', 'bath', { tile: true }),
  r(5, 3.2, 6.2, 4.4, 'Кухня-гостиная', 'living', { windows: ['right', 'bottom'] }),
  r(0, 5.7, 5, 1.9, 'Холл / гардероб', 'hall'),
], 11.2, 7.6);

addHome('fin-01', 'Отделка дома 120 м2', '120 м2', 'дом', 14, 8.8, [
  r(0, 0, 3.4, 3.2, 'Спальня', 'bed', { windows: ['top'] }),
  r(3.4, 0, 3.2, 3.2, 'Спальня', 'bed', { windows: ['top'] }),
  r(6.6, 0, 2.1, 2.3, 'Санузел', 'bath', { tile: true }),
  r(8.7, 0, 5.3, 5.5, 'Кухня-гостиная', 'living', { windows: ['right', 'top'] }),
  r(0, 3.2, 3.4, 3.2, 'Спальня', 'bed', { windows: ['left'] }),
  r(3.4, 3.2, 3.2, 3.2, 'Холл', 'hall'),
  r(6.6, 2.3, 2.1, 2.4, 'Котельная', 'service'),
], [r(9, 5.5, 4.3, 1.8, 'Терраса', 'terrace')], { note: 'План отделки: комнаты, мокрые зоны и чистовые покрытия' });

addHome('fin-02', 'Отделка дома 160 м2', '160 м2', 'дом с лестницей', 10.5, 9.5, [
  r(0, 0, 3.1, 3, 'Спальня', 'bed', { windows: ['top'] }),
  r(3.1, 0, 2.1, 2.3, 'Санузел', 'bath', { tile: true }),
  r(5.2, 0, 2.2, 2.3, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .2, y: .13, w: .6, h: .72 }] }),
  r(7.4, 0, 3.1, 3, 'Спальня', 'bed', { windows: ['top'] }),
  r(0, 3, 2.8, 3, 'Спальня', 'bed', { windows: ['left'] }),
  r(2.8, 2.3, 2.4, 3.7, 'Холл', 'hall'),
  r(5.2, 2.3, 5.3, 5.5, 'Кухня-гостиная', 'living', { windows: ['right', 'bottom'] }),
  r(0, 6, 2.8, 2.5, 'Санузел', 'bath', { tile: true }),
  r(2.8, 6, 2.4, 2.5, 'Постирочная', 'service'),
], [r(5.8, 7.8, 3.9, 1.5, 'Терраса', 'terrace')], { note: 'План отделки: лестница, теплые полы и мокрые зоны' });

addHome('fin-03', 'Отделка дома 210 м2', '210 м2', '2 этажа', 15.8, 8.8, [
  r(0, 0, 2.8, 2.6, '1 этаж: кабинет', 'work', { windows: ['top'] }),
  r(2.8, 0, 2.1, 2.6, 'Санузел', 'bath', { tile: true }),
  r(4.9, 0, 2.2, 2.6, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .2, y: .13, w: .6, h: .72 }] }),
  r(0, 2.6, 7.1, 5.6, '1 этаж: кухня-гостиная', 'living', { windows: ['left', 'bottom'] }),
  r(7.8, 0, 3, 3.1, '2 этаж: мастер', 'bed', { windows: ['top'] }),
  r(10.8, 0, 2.5, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(13.3, 0, 2.5, 3.1, 'Спальня', 'bed', { windows: ['top'] }),
  r(7.8, 3.1, 2, 2.2, 'Санузел', 'bath', { tile: true }),
  r(9.8, 3.1, 2, 2.2, 'Санузел', 'bath', { tile: true }),
  r(11.8, 3.1, 2.2, 2.2, 'Лестница', 'hall', { fixtures: [{ type: 'stairs', x: .2, y: .13, w: .6, h: .72 }] }),
  r(14, 3.1, 1.8, 2.2, 'Холл', 'hall'),
  r(7.8, 5.3, 3.2, 2.8, 'Спальня', 'bed', { windows: ['bottom'] }),
  r(11, 5.3, 4.8, 2.8, 'Постирочная / хранение', 'service'),
], [r(1.2, 8.2, 5.4, 1.2, 'Терраса', 'terrace')], { note: 'Комбинированный план отделки: 1 и 2 этаж в одной карточке' });

const addSmallRoom = (slug, title, area, width, height, rooms) => addHome(slug, title, area, 'мебель и раскладка', width, height, rooms, [], { note: 'План помещения: сантехника, мебель и рабочие зоны' });

addSmallRoom('bath-01', 'Санузел 4 м2', '4 м2', 2.2, 1.8, [
  r(0, 0, .9, 1.8, 'Душ', 'bath', { tile: true, fixtures: [{ type: 'shower', x: .14, y: .12, w: .68, h: .56 }] }),
  r(.9, 0, .65, .9, 'Унитаз', 'bath', { tile: true, fixtures: [{ type: 'wc', x: .23, y: .18, w: .5, h: .56 }] }),
  r(1.55, 0, .65, .9, 'Раковина', 'bath', { tile: true, fixtures: [{ type: 'bath', x: .1, y: .14, w: .7, h: .45 }] }),
  r(.9, .9, 1.3, .9, 'Стиральная зона', 'service', { fixtures: [{ type: 'laundry', x: .18, y: .16, w: .62, h: .52 }] }),
]);

addSmallRoom('bath-02', 'Ванная 6 м2', '6 м2', 3, 2, [
  r(0, 0, 1.55, 1, 'Ванна', 'bath', { tile: true, fixtures: [{ type: 'bath', x: .08, y: .15, w: .72, h: .55 }] }),
  r(1.55, 0, .75, 1, 'Инсталляция', 'bath', { tile: true, fixtures: [{ type: 'wc', x: .2, y: .18, w: .56, h: .58 }] }),
  r(2.3, 0, .7, 1, 'Тумба', 'bath', { tile: true, fixtures: [{ type: 'bath', x: .12, y: .2, w: .68, h: .42 }] }),
  r(0, 1, 3, 1, 'Теплый пол / проход', 'hall', { tile: true }),
]);

addSmallRoom('bath-03', 'Санузел 9 м2 в доме', '9 м2', 3.4, 2.7, [
  r(0, 0, 1.2, 1.3, 'Душ', 'bath', { tile: true, fixtures: [{ type: 'shower', x: .14, y: .12, w: .68, h: .58 }] }),
  r(1.2, 0, 1.4, 1.3, 'Ванна', 'bath', { tile: true, fixtures: [{ type: 'bath', x: .08, y: .15, w: .78, h: .55 }] }),
  r(2.6, 0, .8, 1.3, 'Унитаз', 'bath', { tile: true, fixtures: [{ type: 'wc', x: .18, y: .18, w: .58, h: .56 }] }),
  r(0, 1.3, 1.8, 1.4, 'Две раковины', 'bath', { tile: true, fixtures: [{ type: 'bath', x: .12, y: .18, w: .68, h: .42 }] }),
  r(1.8, 1.3, 1.6, 1.4, 'Скрытые люки', 'service'),
]);

addSmallRoom('kit-01', 'Кухня-гостиная 28 м2', '28 м2', 6.2, 4.5, [
  r(0, 0, 6.2, 1.2, 'Кухонная линия', 'kitchen', { fixtures: [{ type: 'kitchen' }], windows: ['top'] }),
  r(0, 1.2, 2.8, 3.3, 'Столовая', 'living', { fixtures: [{ type: 'table', x: .2, y: .3, w: .55, h: .24 }] }),
  r(2.8, 1.2, 3.4, 3.3, 'ТВ-зона', 'living', { fixtures: [{ type: 'sofa', x: .18, y: .25, w: .58, h: .34 }], windows: ['right'] }),
]);

addSmallRoom('kit-02', 'Кухня-гостиная 42 м2', '42 м2', 7.8, 5.4, [
  r(0, 0, 7.8, 1.3, 'Кухня + остров', 'kitchen', { fixtures: [{ type: 'kitchen' }, { type: 'table', x: .42, y: .44, w: .24, h: .24 }], windows: ['top'] }),
  r(0, 1.3, 3.6, 4.1, 'Столовая', 'living', { fixtures: [{ type: 'table', x: .2, y: .35, w: .55, h: .22 }], windows: ['left'] }),
  r(3.6, 1.3, 4.2, 4.1, 'Диванная зона', 'living', { fixtures: [{ type: 'sofa', x: .16, y: .28, w: .5, h: .3 }], windows: ['right', 'bottom'] }),
]);

addSmallRoom('kit-03', 'Кухня-гостиная в доме 55 м2', '55 м2', 8.6, 6.2, [
  r(0, 0, 8.6, 1.4, 'Кухня + остров', 'kitchen', { fixtures: [{ type: 'kitchen' }, { type: 'table', x: .42, y: .44, w: .24, h: .24 }], windows: ['top'] }),
  r(0, 1.4, 3.8, 4.8, 'Столовая', 'living', { fixtures: [{ type: 'table', x: .18, y: .32, w: .58, h: .22 }], windows: ['left'] }),
  r(3.8, 1.4, 4.8, 4.8, 'Камин / ТВ-зона', 'living', { fixtures: [{ type: 'sofa', x: .15, y: .3, w: .5, h: .3 }], windows: ['right', 'bottom'] }),
], [r(5, 6.2, 3.2, 1.2, 'Выход на террасу', 'terrace')]);

const addOffice = (slug, title, area, width, height, rooms) => addHome(slug, title, area, 'коммерция', width, height, rooms, [], { note: 'План офиса: рабочие места, переговорные и клиентские зоны' });

addOffice('off-01', 'Офис open space 120 м2', '120 м2', 13, 8.5, [
  r(0, 0, 2.6, 2.2, 'Ресепшен', 'work', { fixtures: [{ type: 'desks', x: .18, y: .25, w: .58, h: .38, rows: 1, cols: 1 }] }),
  r(2.6, 0, 3.2, 2.2, 'Переговорная', 'work', { fixtures: [{ type: 'meeting', x: .14, y: .25, w: .72, h: .42 }] }),
  r(5.8, 0, 1.9, 2.2, 'Кухня', 'kitchen'),
  r(7.7, 0, 1.8, 2.2, 'Санузел', 'bath', { tile: true }),
  r(0, 2.2, 13, 5.6, 'Open space 18 мест', 'work', { fixtures: [{ type: 'desks', x: .08, y: .16, w: .82, h: .64, rows: 3, cols: 6 }], windows: ['left', 'right', 'bottom'] }),
]);

addOffice('off-02', 'Кабинетный офис 180 м2', '180 м2', 14.4, 9.2, [
  r(0, 0, 2.6, 2.2, 'Ресепшен', 'work', { fixtures: [{ type: 'desks', x: .18, y: .25, w: .58, h: .38, rows: 1, cols: 1 }] }),
  r(2.6, 0, 3.4, 2.2, 'Переговорная', 'work', { fixtures: [{ type: 'meeting', x: .14, y: .25, w: .72, h: .42 }] }),
  r(6, 0, 2, 2.2, 'Архив', 'service'),
  r(8, 0, 2, 2.2, 'Кухня', 'kitchen'),
  r(10, 0, 2, 2.2, 'Санузлы', 'bath', { tile: true }),
  r(0, 2.2, 3.6, 3, 'Кабинет 1-2', 'work', { fixtures: [{ type: 'desks', x: .15, y: .22, w: .66, h: .48, rows: 1, cols: 2 }] }),
  r(3.6, 2.2, 3.6, 3, 'Кабинет 3-4', 'work', { fixtures: [{ type: 'desks', x: .15, y: .22, w: .66, h: .48, rows: 1, cols: 2 }] }),
  r(7.2, 2.2, 3.6, 3, 'Кабинет 5-6', 'work', { fixtures: [{ type: 'desks', x: .15, y: .22, w: .66, h: .48, rows: 1, cols: 2 }] }),
  r(10.8, 2.2, 3.6, 3, 'Кабинет 7-8', 'work', { fixtures: [{ type: 'desks', x: .15, y: .22, w: .66, h: .48, rows: 1, cols: 2 }] }),
  r(0, 5.2, 14.4, 3.2, 'Коридор и ожидание', 'hall'),
]);

addOffice('off-03', 'Офис 260 м2 с клиентской зоной', '260 м2', 16, 10.2, [
  r(0, 0, 3.2, 2.4, 'Клиентская зона', 'work', { fixtures: [{ type: 'sofa', x: .12, y: .28, w: .55, h: .32 }] }),
  r(3.2, 0, 3.4, 2.4, 'Ресепшен', 'work', { fixtures: [{ type: 'desks', x: .18, y: .25, w: .58, h: .38, rows: 1, cols: 1 }] }),
  r(6.6, 0, 3.4, 2.4, 'Переговорная', 'work', { fixtures: [{ type: 'meeting', x: .14, y: .25, w: .72, h: .42 }] }),
  r(10, 0, 2, 2.4, 'Кухня', 'kitchen'),
  r(12, 0, 2, 2.4, 'Санузлы', 'bath', { tile: true }),
  r(0, 2.4, 9.2, 5.4, 'Open space', 'work', { fixtures: [{ type: 'desks', x: .08, y: .16, w: .84, h: .64, rows: 3, cols: 5 }], windows: ['left', 'bottom'] }),
  r(9.2, 2.4, 3.4, 2.7, 'Кабинеты', 'work', { fixtures: [{ type: 'desks', x: .15, y: .22, w: .66, h: .48, rows: 1, cols: 2 }] }),
  r(12.6, 2.4, 3.4, 2.7, 'Переговорная 2', 'work', { fixtures: [{ type: 'meeting', x: .14, y: .25, w: .72, h: .42 }] }),
  r(9.2, 5.1, 6.8, 2.7, 'Кабинеты руководства', 'work', { fixtures: [{ type: 'desks', x: .1, y: .22, w: .76, h: .5, rows: 1, cols: 3 }] }),
  r(0, 7.8, 16, 1.8, 'Коридор / хранение', 'hall'),
]);

const schemeTitle = (def) => `
  ${backdrop(def)}
  <g filter="url(#paperShadow)">
    <rect x="170" y="205" width="1260" height="560" rx="22" fill="#ffffff"/>
`;

const drawReconstruction = (def, body, note) => svg(`
  ${schemeTitle(def)}
    ${body}
  </g>
  <text x="110" y="828" font-family="Arial, sans-serif" font-size="22" font-weight="700" fill="#176b56">${esc(note)}</text>
  <text x="1490" y="828" font-family="Arial, sans-serif" font-size="18" font-weight="700" fill="#98a2b3" text-anchor="end">${esc(def.code)} · ${esc(def.file)}</text>
`);

const addScheme = (slug, title, area, subtitle, file, body, note) => add(slug, file, {
  title, area, subtitle, level: 'схема', customSvg: (def) => drawReconstruction(def, body, note),
});

addScheme('rec-01', 'Реконструкция дома 140 м2', '140 м2', 'фасад, кровля, планировка', 'plan.png', `
  <rect x="245" y="330" width="520" height="250" fill="#efe9dc" stroke="#252a2f" stroke-width="8"/>
  <polygon points="225,330 505,250 785,330" fill="#34333a"/>
  <rect x="835" y="330" width="400" height="250" fill="#f6efe3" stroke="#252a2f" stroke-width="8"/>
  <polygon points="815,330 1035,250 1255,330" fill="#2f3338"/>
  <rect x="1035" y="330" width="200" height="250" fill="url(#hatch)" stroke="#176b56" stroke-width="5"/>
  <text x="505" y="620" font-family="Arial, sans-serif" font-size="26" font-weight="800" fill="#667085" text-anchor="middle">существующий дом</text>
  <text x="1035" y="620" font-family="Arial, sans-serif" font-size="26" font-weight="800" fill="#176b56" text-anchor="middle">обновление + инженерия</text>
  <path d="M785 455H835" stroke="#176b56" stroke-width="7" marker-end="none"/>
  <rect x="905" y="395" width="90" height="58" rx="8" fill="#dff6ff" stroke="#252a2f" stroke-width="4"/>
  <rect x="1095" y="395" width="90" height="58" rx="8" fill="#dff6ff" stroke="#252a2f" stroke-width="4"/>
`, 'Схема реконструкции: что остается, что усиливается и где меняется планировка');

addScheme('rec-02', 'Мансарда вместо чердака', '80 м2', 'утепление кровли', 'plan.png', `
  <polygon points="280,610 510,280 740,610" fill="#f7fafc" stroke="#252a2f" stroke-width="8"/>
  <polygon points="860,610 1090,280 1320,610" fill="#f7fafc" stroke="#252a2f" stroke-width="8"/>
  <rect x="405" y="430" width="210" height="150" fill="#fff8ee" stroke="#252a2f" stroke-width="5"/>
  <rect x="965" y="430" width="250" height="150" fill="#fff8ee" stroke="#252a2f" stroke-width="5"/>
  <rect x="615" y="430" width="80" height="150" fill="#eaf4f7" stroke="#252a2f" stroke-width="5"/>
  <rect x="885" y="430" width="80" height="150" fill="#f7f3e8" stroke="#252a2f" stroke-width="5"/>
  <path d="M330 336L510 280L690 336" stroke="#176b56" stroke-width="12" fill="none"/>
  <path d="M910 336L1090 280L1270 336" stroke="#176b56" stroke-width="12" fill="none"/>
  <text x="510" y="650" font-family="Arial, sans-serif" font-size="26" font-weight="800" fill="#176b56" text-anchor="middle">спальни / кабинет</text>
  <text x="1090" y="650" font-family="Arial, sans-serif" font-size="26" font-weight="800" fill="#176b56" text-anchor="middle">утепленный контур</text>
`, 'Схема мансарды: полезная зона, лестница, утепленный кровельный пирог');

addScheme('rec-03', 'Пристройка террасы и кухни', '+35 м2', 'кухня + терраса', 'plan.png', `
  <rect x="285" y="315" width="470" height="260" fill="#efe9dc" stroke="#252a2f" stroke-width="8"/>
  <rect x="755" y="315" width="280" height="260" fill="url(#hatch)" stroke="#176b56" stroke-width="8"/>
  <rect x="755" y="575" width="470" height="120" fill="#f2efe4" stroke="#b7b0a4" stroke-width="5" stroke-dasharray="12 10"/>
  <text x="520" y="455" font-family="Arial, sans-serif" font-size="30" font-weight="800" fill="#1c2530" text-anchor="middle">существующий дом</text>
  <text x="895" y="455" font-family="Arial, sans-serif" font-size="28" font-weight="800" fill="#176b56" text-anchor="middle">новая кухня</text>
  <text x="990" y="650" font-family="Arial, sans-serif" font-size="28" font-weight="800" fill="#667085" text-anchor="middle">терраса</text>
`, 'Схема пристройки: новая кухня-гостиная и связанная терраса');

addScheme('fac-01', 'Утепление фасада 180 м2', '180 м2 фасада', 'утепление и штукатурка', 'plan.png', `
  <rect x="250" y="330" width="560" height="260" fill="#f6efe3" stroke="#252a2f" stroke-width="8"/>
  <polygon points="230,330 530,250 830,330" fill="#34333a"/>
  <rect x="300" y="390" width="110" height="80" fill="#dff6ff" stroke="#252a2f" stroke-width="4"/>
  <rect x="515" y="390" width="110" height="80" fill="#dff6ff" stroke="#252a2f" stroke-width="4"/>
  <rect x="690" y="420" width="70" height="170" fill="#2d3742"/>
  <rect x="930" y="280" width="290" height="370" fill="#f7fafc" stroke="#252a2f" stroke-width="7"/>
  <rect x="970" y="315" width="210" height="55" fill="#e7f2ef" stroke="#176b56" stroke-width="4"/>
  <rect x="970" y="390" width="210" height="55" fill="#fbf2df" stroke="#c7782e" stroke-width="4"/>
  <rect x="970" y="465" width="210" height="55" fill="#f3f4f6" stroke="#6b7280" stroke-width="4"/>
  <text x="1075" y="565" font-family="Arial, sans-serif" font-size="24" font-weight="800" fill="#1c2530" text-anchor="middle">узел стены</text>
`, 'Схема фасада: контур утепления, окна, откосы и слои стены');

addScheme('fac-02', 'Фасад штукатурка + дерево', '220 м2 фасада', 'комбинированная отделка', 'plan.png', `
  <rect x="240" y="330" width="640" height="265" fill="#f6efe3" stroke="#252a2f" stroke-width="8"/>
  <polygon points="220,330 560,245 900,330" fill="#34333a"/>
  <rect x="240" y="330" width="210" height="265" fill="#b99067" opacity=".82"/>
  <rect x="510" y="380" width="120" height="82" fill="#dff6ff" stroke="#252a2f" stroke-width="4"/>
  <rect x="675" y="380" width="120" height="82" fill="#dff6ff" stroke="#252a2f" stroke-width="4"/>
  <rect x="960" y="295" width="310" height="265" fill="#fff" stroke="#252a2f" stroke-width="7"/>
  <rect x="990" y="330" width="250" height="72" fill="#e8eee9" stroke="#176b56" stroke-width="4"/>
  <rect x="990" y="422" width="250" height="72" fill="#b99067" stroke="#8a5d38" stroke-width="4"/>
  <text x="1115" y="612" font-family="Arial, sans-serif" font-size="24" font-weight="800" fill="#1c2530" text-anchor="middle">карта материалов</text>
`, 'Схема фасада: зоны штукатурки, дерева, подсветки и откосов');

addScheme('fac-03', 'Клинкерный фасад', '200 м2 фасада', 'цоколь и отливы', 'plan.png', `
  <rect x="250" y="330" width="610" height="265" fill="#ad6846" stroke="#252a2f" stroke-width="8"/>
  <polygon points="230,330 555,248 880,330" fill="#34333a"/>
  <rect x="250" y="545" width="610" height="50" fill="#6e4b3a"/>
  <rect x="330" y="390" width="120" height="82" fill="#dff6ff" stroke="#252a2f" stroke-width="4"/>
  <rect x="560" y="390" width="120" height="82" fill="#dff6ff" stroke="#252a2f" stroke-width="4"/>
  ${Array.from({ length: 8 }).map((_, i) => `<line x1="${270 + i * 72}" y1="342" x2="${270 + i * 72}" y2="545" stroke="#8f5439" stroke-width="3" opacity=".45"/>`).join('')}
  <rect x="965" y="305" width="300" height="250" fill="#fff" stroke="#252a2f" stroke-width="7"/>
  <rect x="1000" y="340" width="230" height="70" fill="#ad6846" stroke="#8f5439" stroke-width="4"/>
  <rect x="1000" y="430" width="230" height="55" fill="#6e4b3a" stroke="#473126" stroke-width="4"/>
  <text x="1115" y="610" font-family="Arial, sans-serif" font-size="24" font-weight="800" fill="#1c2530" text-anchor="middle">клинкер + цоколь</text>
`, 'Схема фасада: клинкерная плитка, цоколь, отливы и примыкания');

addScheme('roof-01', 'Замена кровли 160 м2', '160 м2 кровли', 'металлочерепица', 'plan.png', `
  <polygon points="315,300 730,300 840,445 730,590 315,590 205,445" fill="#eef2f5" stroke="#252a2f" stroke-width="8"/>
  <line x1="205" y1="445" x2="840" y2="445" stroke="#176b56" stroke-width="6"/>
  <line x1="520" y1="300" x2="520" y2="590" stroke="#176b56" stroke-width="6"/>
  <path d="M390 380L455 445L390 510" stroke="#c7782e" stroke-width="5" fill="none"/>
  <path d="M650 380L585 445L650 510" stroke="#c7782e" stroke-width="5" fill="none"/>
  <rect x="930" y="315" width="300" height="260" fill="#fff" stroke="#252a2f" stroke-width="7"/>
  <rect x="970" y="355" width="220" height="48" fill="#dce7ed" stroke="#6b7280" stroke-width="4"/>
  <rect x="970" y="423" width="220" height="48" fill="#f5efe5" stroke="#c7782e" stroke-width="4"/>
  <rect x="970" y="491" width="220" height="48" fill="#eef5f0" stroke="#176b56" stroke-width="4"/>
`, 'Схема кровли: скаты, конек, водосток и слои замены');

addScheme('roof-02', 'Утепленная мансардная кровля', '190 м2 кровли', 'утепление и окна', 'plan.png', `
  <polygon points="285,610 535,260 785,610" fill="#f7fafc" stroke="#252a2f" stroke-width="8"/>
  <path d="M330 545L535 300L740 545" stroke="#176b56" stroke-width="18" fill="none"/>
  <rect x="462" y="400" width="145" height="82" fill="#dff6ff" stroke="#252a2f" stroke-width="5" transform="rotate(-24 535 441)"/>
  <rect x="905" y="295" width="330" height="285" fill="#fff" stroke="#252a2f" stroke-width="7"/>
  <rect x="945" y="335" width="250" height="48" fill="#eef5f0" stroke="#176b56" stroke-width="4"/>
  <rect x="945" y="403" width="250" height="48" fill="#fbf2df" stroke="#c7782e" stroke-width="4"/>
  <rect x="945" y="471" width="250" height="48" fill="#eaf4f7" stroke="#6b7280" stroke-width="4"/>
  <text x="1070" y="620" font-family="Arial, sans-serif" font-size="24" font-weight="800" fill="#1c2530" text-anchor="middle">утепленный пирог</text>
`, 'Схема кровли: утепление, пароизоляция, мансардные окна и подшива');

addScheme('roof-03', 'Мягкая кровля 145 м2', '145 м2 кровли', 'примыкания', 'plan.png', `
  <rect x="280" y="320" width="540" height="255" fill="#eef2f5" stroke="#252a2f" stroke-width="8"/>
  <line x1="280" y1="448" x2="820" y2="448" stroke="#176b56" stroke-width="6"/>
  <path d="M340 380H760M340 430H760M340 480H760M340 530H760" stroke="#9b273d" stroke-width="5" opacity=".8"/>
  <circle cx="660" cy="448" r="46" fill="#fff" stroke="#252a2f" stroke-width="6"/>
  <rect x="930" y="310" width="310" height="280" fill="#fff" stroke="#252a2f" stroke-width="7"/>
  <rect x="970" y="350" width="230" height="44" fill="#9b273d" opacity=".78"/>
  <rect x="970" y="414" width="230" height="44" fill="#f4f4f0" stroke="#6b7280" stroke-width="4"/>
  <rect x="970" y="478" width="230" height="44" fill="#eaf4f7" stroke="#6b7280" stroke-width="4"/>
  <text x="1085" y="635" font-family="Arial, sans-serif" font-size="24" font-weight="800" fill="#1c2530" text-anchor="middle">узел примыкания</text>
`, 'Схема мягкой кровли: основание, ковер, примыкания и водоотвод');

const renderPngSync = (outDir, fileName, svgContent) => {
  fs.mkdirSync(tmpRoot, { recursive: true });
  fs.mkdirSync(outDir, { recursive: true });
  const tmpSvg = path.join(tmpRoot, `${path.basename(outDir)}-${fileName}.svg`);
  const outPng = path.join(outDir, fileName);
  fs.writeFileSync(tmpSvg, svgContent);

  const result = spawnSync(chromeBin, [
    '--headless=new',
    '--disable-gpu',
    '--no-sandbox',
    '--hide-scrollbars',
    `--user-data-dir=${path.join(tmpRoot, 'chrome-profile')}`,
    `--screenshot=${outPng}`,
    `--window-size=${W},${H}`,
    pathToFileURL(tmpSvg).href,
  ], { encoding: 'utf8', timeout: 45000 });

  if (result.status !== 0) {
    throw new Error([
      `Failed to render ${outPng}`,
      result.stderr,
      result.stdout,
    ].filter(Boolean).join('\n'));
  }
};

class CdpClient {
  constructor(ws) {
    this.ws = ws;
    this.nextId = 1;
    this.pending = new Map();
    this.eventWaiters = new Map();

    ws.addEventListener('message', (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) {
          reject(new Error(`${msg.error.message}${msg.error.data ? `: ${msg.error.data}` : ''}`));
        } else {
          resolve(msg.result || {});
        }
        return;
      }
      if (msg.method && this.eventWaiters.has(msg.method)) {
        const waiters = this.eventWaiters.get(msg.method);
        this.eventWaiters.delete(msg.method);
        waiters.forEach((resolve) => resolve(msg.params || {}));
      }
    });
  }

  send(method, params = {}) {
    const id = this.nextId;
    this.nextId += 1;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`CDP timeout: ${method}`));
      }, 30000);
      this.pending.set(id, {
        resolve: (result) => {
          clearTimeout(timer);
          resolve(result);
        },
        reject: (error) => {
          clearTimeout(timer);
          reject(error);
        },
      });
    });
  }

  waitEvent(method) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        const waiters = this.eventWaiters.get(method) || [];
        this.eventWaiters.set(method, waiters.filter((item) => item !== wrappedResolve));
        reject(new Error(`CDP event timeout: ${method}`));
      }, 30000);
      const wrappedResolve = (params) => {
        clearTimeout(timer);
        resolve(params);
      };
      const waiters = this.eventWaiters.get(method) || [];
      waiters.push(wrappedResolve);
      this.eventWaiters.set(method, waiters);
    });
  }

  close() {
    this.ws.close();
  }
}

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const launchChromeRenderer = async () => {
  fs.mkdirSync(tmpRoot, { recursive: true });
  const profileDir = path.join(tmpRoot, `chrome-profile-${process.pid}`);
  fs.rmSync(profileDir, { recursive: true, force: true });

  const chrome = spawn(chromeBin, [
    '--headless=new',
    '--disable-gpu',
    '--no-sandbox',
    '--hide-scrollbars',
    '--disable-background-networking',
    '--disable-default-apps',
    '--disable-extensions',
    '--disable-sync',
    '--no-first-run',
    '--no-default-browser-check',
    '--remote-debugging-port=0',
    `--user-data-dir=${profileDir}`,
    'about:blank',
  ], { stdio: ['ignore', 'ignore', 'pipe'] });

  const browserWs = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Chrome DevTools endpoint timeout')), 30000);
    chrome.on('error', (error) => {
      clearTimeout(timer);
      reject(error);
    });
    chrome.on('exit', (code) => {
      if (code !== null) {
        clearTimeout(timer);
        reject(new Error(`Chrome exited before DevTools endpoint was ready: ${code}`));
      }
    });
    chrome.stderr.on('data', (chunk) => {
      const match = String(chunk).match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (match) {
        clearTimeout(timer);
        resolve(match[1]);
      }
    });
  });

  const host = new URL(browserWs).host;
  const targetResponse = await fetch(`http://${host}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' });
  if (!targetResponse.ok) {
    throw new Error(`Failed to create Chrome target: ${targetResponse.status}`);
  }
  const target = await targetResponse.json();
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener('open', resolve, { once: true });
    ws.addEventListener('error', reject, { once: true });
  });

  const client = new CdpClient(ws);
  await client.send('Page.enable');
  await client.send('Emulation.setDeviceMetricsOverride', {
    width: W,
    height: H,
    deviceScaleFactor: 1,
    mobile: false,
  });

  return {
    async render(tmpSvg, outPng) {
      const loaded = client.waitEvent('Page.loadEventFired');
      await client.send('Page.navigate', { url: pathToFileURL(tmpSvg).href });
      await loaded;
      await wait(80);
      const { data } = await client.send('Page.captureScreenshot', {
        format: 'png',
        fromSurface: true,
        captureBeyondViewport: false,
      });
      fs.writeFileSync(outPng, Buffer.from(data, 'base64'));
    },
    async close() {
      client.close();
      chrome.kill('SIGTERM');
      fs.rmSync(profileDir, { recursive: true, force: true });
    },
  };
};

const renderJobs = async (jobs) => {
  if (process.env.STROYKA_PLAN_RENDERER === 'cli') {
    jobs.forEach((job) => renderPngSync(job.outDir, job.fileName, job.svgContent));
    return;
  }

  fs.mkdirSync(tmpRoot, { recursive: true });
  const renderer = await launchChromeRenderer();
  try {
    for (const job of jobs) {
      fs.mkdirSync(job.outDir, { recursive: true });
      const tmpSvg = path.join(tmpRoot, `${path.basename(job.outDir)}-${job.fileName}.svg`);
      const outPng = path.join(job.outDir, job.fileName);
      fs.writeFileSync(tmpSvg, job.svgContent);
      await renderer.render(tmpSvg, outPng);
    }
  } finally {
    await renderer.close();
  }
};

const requested = new Set(process.argv.slice(2).map((item) => item.toLowerCase()));
const selected = requested.size
  ? definitions.filter((def) => requested.has(def.slug))
  : definitions;

if (!selected.length) {
  throw new Error(`No matching project slugs: ${[...requested].join(', ')}`);
}

const jobs = selected.map((def) => ({
  outDir: path.join(root, def.slug),
  fileName: def.file,
  svgContent: def.customSvg ? def.customSvg(def) : drawPlan(def),
}));

renderJobs(jobs).then(() => {
  console.log(`Generated ${selected.length} public project plan PNG files in ${root}`);
}).catch((error) => {
  console.error(error);
  process.exit(1);
});

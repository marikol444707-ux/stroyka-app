#!/usr/bin/env node
// Render facade-informed conceptual zoning; these are not engineering drawings.
const fs = require('fs');
const path = require('path');
const { definitions, renderJobs } = require('./generate-public-project-plan-assets');
const { renderArchitecture, roomsForPresentation, outdoorForPresentation } = require('./public-plan-architectural-renderer');
const { layoutFor } = require('./public-plan-facade-layouts');
const root = path.resolve(__dirname, '..');
// Explicit list protects imported architectural drawings and retired concepts.
const codes = new Set(['b1-02', 'b1-03', 'fam-02', 'fam-03', 'h2-02', 'gar-01', 'gar-02', 'gar-03', 'town-01', 'town-02', 'town-03', 'apt-01', 'apt-02', 'apt-03', 'fin-01', 'fin-02', 'fin-03', 'bath-01', 'bath-02', 'bath-03', 'kit-01', 'kit-02', 'kit-03', 'off-01', 'off-02', 'off-03']);
const catalog = JSON.parse(fs.readFileSync(path.join(root, 'public/project-catalog.json')));
const cards = new Map(catalog.directions.flatMap(d => d.projects).map(p => [p.code.toLowerCase(), p]));
const escape = text => String(text).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c]));
const text = (x, y, value, size = 26, weight = 500) => `<text x="${x}" y="${y}" font-family="Arial,sans-serif" font-size="${size}" font-weight="${weight}" fill="#193d46">${escape(value)}</text>`;
const badge = (x, y, number, size = 19) => `<circle cx="${x}" cy="${y}" r="${size}" fill="white" stroke="#6e7a71" stroke-width="1"/><text x="${x}" y="${y + 7}" text-anchor="middle" font-family="Arial,sans-serif" font-size="20" font-weight="500" fill="#35473c">${number}</text>`;

function presentation(def) {
  const zones = [...roomsForPresentation(def), ...outdoorForPresentation(def)];
  const minX = Math.min(...zones.map(r => r.x));
  const minY = Math.min(...zones.map(r => r.y));
  const width = Math.max(...zones.map(r => r.x + r.w)) - minX;
  const height = Math.max(...zones.map(r => r.y + r.h)) - minY;
  const scale = Math.min(880 / width, 640 / height);
  const orientation = layoutFor(def) ? 'Главный фасад — снизу схемы' : null;
  const diagramW = Math.ceil(width * scale + 56), diagramH = Math.ceil(height * scale + (orientation ? 86 : 56));
  const m = { s: scale, ox: 28 - minX * scale, oy: 28 - minY * scale };
  const architecture = renderArchitecture(def, m);
  const roomSvg = architecture.body + (orientation ? `<path d="M${diagramW/2-65} ${diagramH-34}h130" stroke="#bd6a38" stroke-width="2"/>${text(diagramW/2-127, diagramH-12, orientation, 17, 600)}` : "");
  const numbers = '';
  const diagram = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${diagramW} ${diagramH}" width="${diagramW}" height="${diagramH}"><title>Эскизная планировка ${escape(def.code)}</title>${roomSvg}</svg>`;
  const heading = def.level ? `План ${def.level.replace('этаж', 'этажа')}` : 'Планировка помещений';
  const rows = zones.map((r, i) => `<line x1="1040" y1="${204 + i * 39}" x2="1532" y2="${204 + i * 39}" stroke="#e2e6e3"/>${badge(1060, 224 + i * 39, i + 1, 16)}${text(1087, 232 + i * 39, r.label, 21)}`).join('');
  const full = `<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900"><rect width="1600" height="900" fill="#fff"/>${text(48, 57, `${def.code} / ${heading}`, 34, 700)}${text(48, 94, cards.get(def.slug).title, 23)}<line x1="48" y1="125" x2="1552" y2="125" stroke="#d8e4e2"/> <svg x="${48 + (940 - diagramW) / 2}" y="${150 + (660 - diagramH) / 2}" width="${diagramW}" height="${diagramH}" viewBox="0 0 ${diagramW} ${diagramH}">${roomSvg}${numbers}</svg><rect x="1020" y="151" width="532" height="${Math.max(260, zones.length * 39 + 90)}" rx="2" fill="#fff" stroke="#cbd2cd"/>${text(1040, 190, 'Экспликация помещений', 25, 700)}${rows}${text(48, 853, 'Концепция зонирования. Размеры, проёмы и конструктив уточняются при проектировании.', 23)}</svg>`;
  return { diagram: diagram.replace(/[ \t]+$/gm, ''), full: full.replace(/[ \t]+$/gm, ''), heading, orientation, rooms: zones.map((r, i) => ({ number: i + 1, name: r.label })) };
}

async function main() {
  const manifest = {}, jobs = [];
  for (const def of definitions.filter(d => codes.has(d.slug))) {
    if (!cards.has(def.slug)) throw new Error(`Unpublished project: ${def.slug}`);
    const p = presentation(def);
    const outDir = path.join(root, 'public/site-assets/projects', def.slug);
    const stem = def.file.replace('.png', '');
    fs.writeFileSync(path.join(outDir, `${stem}-diagram.svg`), p.diagram);
    fs.writeFileSync(path.join(outDir, `${stem}-sheet.svg`), p.full);
    manifest[`/site-assets/projects/${def.slug}/${def.file}`] = {
      heading: p.heading, rooms: p.rooms, ...(p.orientation ? { orientation: p.orientation } : {}),
      diagram: `/site-assets/projects/${def.slug}/${stem}-diagram.svg`,
      sheet: `/site-assets/projects/${def.slug}/${stem}-sheet.svg`,
    };
    jobs.push({ outDir, fileName: def.file, svgContent: p.full });
  }
  await renderJobs(jobs);
  fs.writeFileSync(path.join(root, 'src/features/public-site/projectPlanPresentation.json'), JSON.stringify(manifest, null, 2) + '\n');
  console.log(`Updated ${jobs.length} conceptual plans; original drawings preserved.`);
}
if (require.main === module) main().catch(e => { console.error(e); process.exitCode = 1; });
module.exports = { presentation, codes };

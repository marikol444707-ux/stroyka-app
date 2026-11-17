import { readFileSync, statSync } from 'fs';
import path from 'path';

const root = path.resolve(__dirname, '../../..');
const publicDir = path.join(root, 'public');

const photos = [
  ['commerc_01', 'Коммерческое здание из газоблока, мощение плиткой'],
  ['commerc_06', 'Коммерческое здание из газоблока, мощение плиткой'],
  ['commerc_07', 'Коммерческое здание из газоблока, мощение плиткой'],
  ['commerc_fasad_18', 'Готовый фасад коммерческого здания'],
  ['dom_19', 'Одноэтажный дом: облицовочный кирпич, колонны, металлочерепица'],
  ['kladka_21', 'Кладка газоблока в монолитном каркасе'],
  ['monolit_23', 'Монолитный ж/б каркас, перекрытие'],
  ['monolit_25', 'Двухэтажный монолитный каркас, гидроизоляция цоколя'],
  ['monolit_opalubka_29', 'Колонны в опалубке'],
  ['metallokarkas_09', 'Металлокаркас здания'],
  ['metallokarkas_17', 'Металлокаркас здания'],
  ['fundament_gidroizol_32', 'Блочный цоколь с обмазочной гидроизоляцией'],
  ['fundament_zalivka_35', 'Заливка фундамента'],
  ['fundament_armatura_39', 'Армирование фундаментной плиты с коммуникациями'],
];

const read = (relativePath) => readFileSync(path.join(root, relativePath), 'utf8');

const webpSize = (filePath) => {
  const data = readFileSync(filePath);
  expect(data.subarray(0, 4).toString()).toBe('RIFF');
  expect(data.subarray(8, 12).toString()).toBe('WEBP');
  const chunk = data.subarray(12, 16).toString();
  if (chunk === 'VP8 ') {
    return {
      width: data.readUInt16LE(26) & 0x3fff,
      height: data.readUInt16LE(28) & 0x3fff,
    };
  }
  if (chunk === 'VP8X') {
    return {
      width: 1 + data.readUIntLE(24, 3),
      height: 1 + data.readUIntLE(27, 3),
    };
  }
  throw new Error(`unsupported webp chunk ${chunk}`);
};

test('public object gallery lists the approved photos and captions', () => {
  const page = read('public/our-objects.html');
  const script = read('public/our-objects.js');
  let totalBytes = 0;

  expect(page).toContain('<h1>Наши объекты</h1>');
  expect(page).toContain('id="object-lightbox"');
  expect(page).toContain('aria-labelledby="object-lightbox-caption"');
  expect(script).toContain('ArrowLeft');
  expect(script).toContain('ArrowRight');
  expect(script).toContain('dialog.close');
  expect((page.match(/<li>/g) || []).length).toBe(photos.length);

  photos.forEach(([slug, caption]) => {
    const full = path.join(publicDir, 'site-assets/our-objects', `${slug}.webp`);
    const thumb = path.join(publicDir, 'site-assets/our-objects/thumbs', `${slug}.webp`);
    expect(page).toContain(`data-caption="${caption}"`);
    expect(page).toContain(`alt="${caption}"`);
    expect(page).toContain(`src="/site-assets/our-objects/thumbs/${slug}.webp"`);
    expect(page).toContain('loading="lazy"');
    expect(webpSize(full).width).toBeLessThanOrEqual(1600);
    expect(webpSize(thumb).width).toBeLessThanOrEqual(600);
    totalBytes += statSync(full).size + statSync(thumb).size;
  });

  expect(totalBytes).toBeLessThan(8 * 1024 * 1024);
  expect(read('src/components/PublicSitePage.jsx')).toContain('href="/our-objects.html"');
  expect(read('public/index.html')).toContain('href="/our-objects.html"');
  expect(read('public/sitemap.xml')).toContain('https://stroyka26.pro/our-objects.html');
});

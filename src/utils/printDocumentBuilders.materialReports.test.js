import { buildM8DocContent, buildM29DocContent } from './printDocumentBuilders';

const row = {name:'Краска',unit:'кг',limit:10,plan:10,issued:7,accepted:5,pending:2,fact:4,historical:0};

test.each([
  ['M-8', () => buildM8DocContent({projectName:'Лицей',rows:[row]}, {companyName:'ООО Компания'})],
  ['M-29', () => buildM29DocContent({projectName:'Лицей',rows:[row]}, {companyName:'ООО Компания'})],
])('%s clearly separates draft and material responsibility states', (_name, build) => {
  const html = build();
  expect(html).toContain('Черновик — не подписан');
  expect(html).toContain('Отпущено со склада');
  expect(html).toContain('Подтверждено мастером');
  expect(html).toContain('Ожидает подписи');
  expect(html).toContain('Настройки → Документы');
});

test.each([
  ['M-8', () => buildM8DocContent({projectName:'<script>object</script>',masterName:'<b>master</b>',rows:[row]}, {companyName:'<i>company</i>'})],
  ['M-29', () => buildM29DocContent({projectName:'<script>object</script>',rows:[row]}, {companyName:'<i>company</i>'})],
])('%s escapes party and project names in printable HTML', (_name, build) => {
  const html = build();
  expect(html).not.toContain('<script>object</script>');
  expect(html).not.toContain('<i>company</i>');
  expect(html).toContain('&lt;script&gt;object&lt;/script&gt;');
  expect(html).toContain('&lt;i&gt;company&lt;/i&gt;');
});

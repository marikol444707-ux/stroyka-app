import { buildJPRDocContent, buildExecPackageDocContent, buildTBContentDoc } from './printDocumentBuilders';
const project={id:11,companyId:2,name:'Same name'};
const rows=[{id:1,companyId:2,projectId:11,project:'Old name'},
  {id:2,companyId:3,projectId:12,project:'Same name'},
  {id:3,project:'Same name'}];
test.each([buildJPRDocContent,buildExecPackageDocContent])('safety counts in related prints use exact ownership', build => {
  const doc=new DOMParser().parseFromString(build(project,{tbJournal:rows}),'text/html');
  const row=[...doc.querySelectorAll('tr')].find(row => row.textContent.includes('Журнал инструктажей ТБ'));
  expect(row).toBeTruthy();
  const cells=[...row.querySelectorAll('td')].map(cell => cell.textContent);
  expect(cells[cells.indexOf('Журнал инструктажей ТБ')+1]).toBe('1');
});

test('safety print preserves the saved program, instruction, instructor and participants as text', () => {
  const html=buildTBContentDoc({type:'Вводный инструктаж',project:'Object <b>one</b>',date:'2026-11-09',
    program:'Saved program\nSecond step',instructionText:'Saved instruction <img src=x onerror=alert(1)>',
    instructor:'Instructor <script>bad()</script>',participants:['Person <em>one</em>']});
  const doc=new DOMParser().parseFromString(html,'text/html');
  expect(doc.body.textContent).toContain('Saved program');
  expect(doc.body.textContent).toContain('Saved instruction <img src=x onerror=alert(1)>');
  expect(doc.body.textContent).toContain('Instructor <script>bad()</script>');
  expect(doc.body.textContent).toContain('Person <em>one</em>');
  expect(doc.body.textContent).toContain('Object <b>one</b>');
  expect(doc.querySelector('img,script,em')).toBeNull();
  expect(doc.body.textContent).not.toContain('Работник обязан соблюдать правила внутреннего');
});

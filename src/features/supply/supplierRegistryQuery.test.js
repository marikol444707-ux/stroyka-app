import { registryRows, filterRegistryRows, registryCsv } from './supplierRegistryQuery';

const requests = [{id:1,companyId:2,companyName:'Альфа',project:'Лицей',itemsJson:'[{"name":"Кабель ёлка"}]'}, {id:2,companyId:3,companyName:'Бета',materialName:'Труба'}];
const offers = [{requestId:1,status:'Получено'},{requestId:1,status:'Отозвано'}, {requestId:2,status:'Ожидает ответа'}, {requestId:999,status:'Получено'}];
it('searches Unicode materials, object and number while intersecting customer and quote status', () => {
  const rows=registryRows(requests,offers);
  expect(rows).toHaveLength(2);
  expect(filterRegistryRows(rows,{query:'КАБЕЛЬ ЕЛКА',company:'2',status:'Получено'}).map(r=>r.id)).toEqual([1]);
  expect(filterRegistryRows(rows,{query:'лицей',status:'Отозвано'})).toHaveLength(1);
  expect(filterRegistryRows(rows,{query:'№2'}).map(r=>r.id)).toEqual([2]);
  expect(filterRegistryRows(rows,{company:'3',status:'Получено'})).toEqual([]);
});
it('exports only the supplied filtered set and neutralizes formulas in quoted multiline CSV cells', () => {
  const rows=registryRows([{id:7,companyName:' =HYPERLINK("x")',project:'@SUM(1;2)',materialName:'Труба;"А"\nновая'}],[{requestId:7,status:'Получено'}]);
  const csv=registryCsv(rows);
  expect(csv.startsWith('\uFEFF')).toBe(true);
  expect(csv).toContain(`"' =HYPERLINK(""x"")"`);
  expect(csv).toContain(`"'@SUM(1;2)"`);
  expect(csv).toContain('"Труба;""А""\nновая"');
  expect(registryCsv(filterRegistryRows(registryRows(requests,offers),{company:'3'}))).not.toContain('Альфа');
});
it.each(['=1+1','+SUM(1)','-2+3','@SUM(1)','\t=1','\r=2','\n=3','  =4','＝1'])('neutralizes CSV prefix %p', value=>{
  const rows=registryRows([{id:1,materialName:value}],[{requestId:1}]);
  expect(registryCsv(rows)).toContain('"\''+value+'"');
});

import { buildM8Rows, buildM29Rows } from './materialDocumentUtils';

const project = {id: 17, name: 'Лицей'};
const frozen = (overrides = {}) => ({
  projectName: 'Старое название',
  projectId: 17,
  transferDate: '2026-10-02',
  signed: true,
  issuePartySnapshot: {
    project: {id: 17, name: 'Лицей'},
    intendedReceiver: {name: 'Мастер'},
    material: {name: 'Краска', quantity: '5', unit: 'кг'},
  },
  receiptPartySnapshot: {receiver: {name: 'Мастер'}},
  ...overrides,
});

test('M-8 uses exact project id, frozen material and separates pending receipt', () => {
  const rows = buildM8Rows({
    project,
    periodFrom: '2026-10-01',
    periodTo: '2026-10-31',
    materialTransfers: [
      frozen(),
      frozen({signed: false, issuePartySnapshot: {...frozen().issuePartySnapshot, material: {name:'Краска',quantity:'2',unit:'кг'}}}),
      frozen({status:'Аннулирована',issuePartySnapshot: {...frozen().issuePartySnapshot, material: {name:'Краска',quantity:'100',unit:'кг'}}}),
      frozen({projectId: 99, issuePartySnapshot: {...frozen().issuePartySnapshot, project:{id:99,name:'Лицей'}}}),
    ],
  });
  expect(rows).toHaveLength(1);
  expect(rows[0]).toMatchObject({name:'Краска',issued:7,accepted:5,pending:2,historical:0});
});

test('M-29 separates warehouse issue, master receipt and actual journal use', () => {
  const rows = buildM29Rows({
    project,
    periodFrom: '2026-10-01',
    periodTo: '2026-10-31',
    materialTransfers: [frozen(), frozen({signed:false}), frozen({status:'Аннулирована',issuePartySnapshot: {...frozen().issuePartySnapshot, material: {name:'Краска',quantity:'100',unit:'кг'}}})],
    workJournal: [
      {project:'Другое имя',projectId:17,date:'2026-10-02',status:'Принято',materialsUsed:[{name:'Краска',quantity:3,unit:'кг'}]},
      {project:'Другое имя',projectId:17,date:'2026-10-02',status:'Аннулировано',materialsUsed:[{name:'Краска',quantity:100,unit:'кг'}]},
    ],
  });
  expect(rows[0]).toMatchObject({name:'Краска',issued:10,accepted:5,pending:5,fact:3});
});

test('legacy rows without project id are excluded when a project name is ambiguous', () => {
  const rows = buildM8Rows({
    project,
    legacyNameMatchAllowed: false,
    periodFrom: '2026-10-01',
    periodTo: '2026-10-31',
    materialTransfers: [{projectName:'Лицей',transferDate:'2026-10-02',materialName:'Старый материал',quantity:9}],
  });
  expect(rows).toEqual([]);
});

import { buildM15DocContent } from './printDocumentBuilders';

const issue = {
  documentKind:'materialIssueM15',
  company:{companyId:3,fullName:'ООО Компания на дату выдачи',inn:'2611008712',legalAddress:'Старый адрес'},
  project:{id:17,name:'Лицей'},
  sender:{userId:5,name:'Петров П.П.',role:'прораб'},
  intendedReceiver:{userId:8,name:'Иванов И.И.',role:'мастер'},
  document:{transferId:41,date:'2026-10-01',fromLocation:'Лицей',workPackage:'Отделка',notes:'По заявке'},
  material:{name:'Краска',quantity:'5',unit:'кг'},
  source:{invoiceId:11,invoiceNumber:'77'},
};

test('M-15 prints frozen issue and receipt parties instead of current company profile', () => {
  const html=buildM15DocContent({id:41,signed:true,issuePartySnapshot:issue,
    receiptPartySnapshot:{receiver:{userId:8,name:'Иванов И.И.',role:'мастер'}},
    materialName:'Подменённый материал',quantity:999},
  {companyRequisites:{fullName:'Новое имя компании',inn:'0000000000'}});
  expect(html).toContain('ООО Компания на дату выдачи');
  expect(html).toContain('2611008712');
  expect(html).toContain('Петров П.П.');
  expect(html).toContain('Иванов И.И.');
  expect(html).toContain('Краска');
  expect(html).not.toContain('Новое имя компании');
  expect(html).not.toContain('Подменённый материал');
});

test('legacy signed M-15 does not impersonate current company requisites', () => {
  const html=buildM15DocContent({id:7,signed:true,toPerson:'Мастер'},
    {companyRequisites:{fullName:'Сегодняшняя компания'}});
  expect(html).toContain('Историческая запись');
  expect(html).toContain('Реквизиты не зафиксированы');
  expect(html).not.toContain('Сегодняшняя компания');
});

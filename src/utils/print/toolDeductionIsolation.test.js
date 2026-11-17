import {buildMasterActDocContent} from './contractorActDocumentBuilders';

const printedRemaining = (act, tools) => {
  const node=document.createElement('div');
  node.innerHTML=buildMasterActDocContent(act,{tools});
  const row=[...node.querySelectorAll('tr')].find(r=>r.textContent.includes('Остаток к выплате:'));
  return Number(row.lastElementChild.textContent.replace(/[^\d-]/g,''));
};
const savedAct={id:10,companyId:4,masterId:100,masterName:'Иван',project:'Объект',totalAmount:10000,paidAmount:0,remainingAmount:10000};

test('one unallocated tool cost is not charged repeatedly to two acts',()=>{
  const tools=[{id:1,companyId:4,masterId:100,masterName:'Иван',project:'Объект',issueType:'В счёт зарплаты',cost:1000}];
  expect([savedAct,{...savedAct,id:11}].map(act=>printedRemaining(act,tools))).toEqual([10000,10000]);
});

test.each([{companyId:5,masterId:100},{companyId:4,masterId:101}])('namesake tool does not reduce act balance: %j',identity=>{
  const tools=[{id:1,...identity,masterName:'Иван',issueType:'В счёт зарплаты',cost:1000}];
  expect(printedRemaining(savedAct,tools)).toBe(10000);
});

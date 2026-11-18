import React from 'react';
import {render,screen,fireEvent,waitFor,act} from '@testing-library/react';
import AccountingSalaryPanel from './AccountingSalaryPanel';

const props={C:{},card:{},inp:{},salaryEdits:{},payrollExtras:{},piecework:[],listSearch:'',matchSearch:()=>true,
  staff:[{id:100,companyId:4,name:'Иван',salary:10000,payType:'Оклад',employmentType:'Штат'}],
  tools:[{id:1,companyId:4,masterId:100,masterName:'Иван',cost:1000,issueType:'В счёт зарплаты'}]};

test('catalog cost cannot become a new deduction in each salary month',()=>{
  const paySalary=jest.fn();const view=render(<AccountingSalaryPanel {...props} salaryMonth="2026-10" paySalary={paySalary}/>);
  const hold = () => screen.getByText('Иван').closest('tr').querySelectorAll('td')[5].textContent;
  expect(hold()).not.toContain('(инстр.)');
  view.rerender(<AccountingSalaryPanel {...props} salaryMonth="2026-11" paySalary={paySalary}/>);
  expect(hold()).not.toContain('(инстр.)');
  expect(screen.getByRole('button',{name:'Выплатить',exact:true})).toBeDisabled();
});

test('confirmed deduction reduces net by exactly its amount and stale month responses are ignored',async()=>{
  let finishOld;
  global.fetch=jest.fn().mockImplementationOnce(()=>new Promise(r=>{finishOld=r;})).mockResolvedValue({ok:true,json:async()=>({companyId:4,month:'2026-11',rows:[{staffId:100,amount:1000,state:'new'}]})});
  const pay=jest.fn();const extra={companyContext:{mode:'company',selectedCompanyId:4},paySalary:pay};
  const view=render(<AccountingSalaryPanel {...props} {...extra} salaryMonth="2026-10"/>);
  view.rerender(<AccountingSalaryPanel {...props} {...extra} salaryMonth="2026-11"/>);
  await waitFor(()=>expect(screen.getByRole('button',{name:'Выплатить',exact:true})).toBeEnabled());
  await act(async()=>finishOld({ok:true,json:async()=>({companyId:4,month:'2026-10',rows:[{staffId:100,amount:9999,state:'old'}]})}));
  fireEvent.click(screen.getByRole('button',{name:'Выплатить',exact:true}));
  expect(pay).toHaveBeenCalledWith(expect.objectContaining({net:7700,accrued:10000,ndfl:1300,toolHold:1000,expectedToolState:'new'}),'2026-11');
});

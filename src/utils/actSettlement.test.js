import { actCashPaid, actAdvance, actRemaining } from './actSettlement';
import { buildMasterActDocContent } from './print/contractorActDocumentBuilders';

test('advance is separate from cash and deducted once in remaining and printed act',()=>{
  const act={id:1,totalAmount:10000,paidAmount:1000,advanceAmount:6000,remainingAmount:3000};
  expect(actCashPaid(act)).toBe(1000);expect(actAdvance(act)).toBe(6000);expect(actRemaining(act)).toBe(3000);
  expect(actRemaining({...act,remainingAmount:undefined})).toBe(3000);
  const node=document.createElement('div');node.innerHTML=buildMasterActDocContent(act);
  const row=[...node.querySelectorAll('tr')].find(r=>r.textContent.includes('Остаток к выплате:'));
  expect(row.textContent.replace(/[\s,]/g,'')).toContain('3000руб.');
  expect(node.textContent).toContain('Зачтён зарплатный аванс');
});

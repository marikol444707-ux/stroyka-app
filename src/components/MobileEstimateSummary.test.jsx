import React from 'react';
import {fireEvent,render,screen} from '@testing-library/react';
import MobileEstimateSummary,{parseEstimateSummary} from './MobileEstimateSummary';
import PreviewModal from './PreviewModal';
import {buildProjectEstimateDiffSummaryDocContent} from '../utils/print/estimateControlDocumentBuilders';
import {sanitizeDocumentHtml} from '../utils/safeHtml';

const rows = [
  {kind:'changed',workPackage:'Отделка',section:'Стены',name:'Штукатурка',baseQty:1,nextQty:2,baseUnitPrice:100,nextUnitPrice:100,baseSum:100,nextSum:200,impact:100},
  {kind:'removed',workPackage:'Отделка',section:'Стены',name:'Грунтовка',baseQty:1,nextQty:0,baseSum:30,nextSum:0,impact:-30},
  {kind:'added',workPackage:'Общестрой',section:'Стены',name:'Кирпич',baseQty:0,nextQty:1,baseSum:0,nextSum:50,impact:50},
];
const content=buildProjectEstimateDiffSummaryDocContent({projectName:'Лицей',packageCount:2,changedPackageCount:2,baseTotal:130,nextTotal:250,impact:120,rows});

test('groups sections by package and keeps before/after data and exact signed differences',()=>{
  const data=parseEstimateSummary(sanitizeDocumentHtml(content));
  expect(data.groups).toHaveLength(2);
  expect(data.groups.map(group=>group.difference)).toEqual([70,50]);
  expect(data.groups[0].rows[0].beforePrice).toBe('100 ₽');
  render(<MobileEstimateSummary content={content}/>);
  expect(screen.getByText('Изменение суммы')).toBeInTheDocument();
  expect(screen.getByText('Грунтовка')).toBeInTheDocument();
  expect(screen.getByText('Позиция исключена')).toBeInTheDocument();
  expect(screen.getByText(/3 позиций/)).toBeInTheDocument();
});

test('mobile presentation prints the complete original report, not collapsed cards',()=>{
  const print=jest.fn();
  render(<PreviewModal content={content} title="Свод изменений" onClose={jest.fn()} onPrint={print}/>);
  fireEvent.click(screen.getByRole('button',{name:'Распечатать'}));
  expect(print).toHaveBeenCalledWith(sanitizeDocumentHtml(content));
  expect(print.mock.calls[0][0]).toContain('eps-table');
  expect(print.mock.calls[0][0]).not.toContain('mobile-estimate-section');
});

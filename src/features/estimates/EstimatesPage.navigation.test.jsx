import React from 'react';
import { render, screen } from '@testing-library/react';
import EstimatesPage from './EstimatesPage';
import { navigationHref } from '../navigation/navigationTarget';
const companyContext={mode:'company',selectedCompanyId:3};
const row={id:41,companyId:3,projectName:'Объект'};
const ctx={companyContext,estimatesList:[row],projects:[{id:7,companyId:3,name:'Объект'}],visibleEstimatesForCurrentUser:rows=>rows,openEstimateDetail:jest.fn(),setSelectedEstimate:jest.fn(),setEstimatesTab:jest.fn(),EstimatesTabsNav:()=>null};
beforeEach(()=>jest.clearAllMocks());
afterEach(()=>window.history.replaceState({},'','/app'));
test('exact link opens existing estimate and clears selection on leave',()=>{
  window.history.replaceState({},'',navigationHref({type:'estimate',id:41,companyId:3,projectId:7}));
  const view=render(<EstimatesPage ctx={ctx}/>);
  expect(ctx.openEstimateDetail).toHaveBeenCalledWith(row);
  expect(ctx.setEstimatesTab).toHaveBeenCalledWith('list');
  view.unmount();
  expect(ctx.setSelectedEstimate).toHaveBeenLastCalledWith(null);
});
test.each([[41,4,7],[99,3,7],[41,3,8]])('foreign company, missing estimate and wrong project cannot open another record', (id,companyId,projectId)=>{
  window.history.replaceState({},'',navigationHref({type:'estimate',id,companyId,projectId}));
  render(<EstimatesPage ctx={ctx}/>);
  expect(ctx.openEstimateDetail).not.toHaveBeenCalled();
  expect(screen.getByRole('status')).toBeInTheDocument();
});

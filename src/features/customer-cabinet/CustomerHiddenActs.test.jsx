import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import CustomerHiddenActs from './CustomerHiddenActs';
const props={project:{id:3,companyId:2},user:{id:1},C:{},card:{},loadState:{hiddenActs:{scope:'1:2:3:',status:'ready'}},refresh:jest.fn()};
const row={id:5,companyId:2,projectId:3,workName:'My work',quantity:1,unit:'м2',revision:'r1'};
test('only own confirmed-work projection is shown and confirmation submits revision only',async()=>{
 global.fetch=jest.fn(async()=>({ok:true,json:async()=>({ok:true})}));
 render(<CustomerHiddenActs {...props} rows={[row,{...row,id:6,companyId:9,workName:'Foreign'}]}/>);
 expect(screen.queryByText('Foreign')).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'Подтвердить акт'}));
 await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(1));
 expect(fetch.mock.calls[0][0]).toContain('/hidden-works-acts/5/customer-confirm');
 expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({revision:'r1'});
 expect(fetch.mock.calls[0][1].headers['X-Company-Id']).toBe('2');
 await waitFor(()=>expect(screen.queryByRole('button',{name:'Подтвердить акт'})).not.toBeInTheDocument());
});
test('failed confirmation keeps act pending and displays server error',async()=>{
 global.fetch=jest.fn(async()=>({ok:false,status:409,json:async()=>({detail:'Акт изменился'})}));
 render(<CustomerHiddenActs {...props} rows={[row]}/>);
 fireEvent.click(screen.getByRole('button',{name:'Подтвердить акт'}));
 await screen.findByText('Акт изменился');
 expect(screen.getByRole('button',{name:'Подтвердить акт'})).toBeEnabled();
});

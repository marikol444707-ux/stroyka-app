import { act, fireEvent, render, screen } from '@testing-library/react';
import MyParticipantTickets from './MyParticipantTickets';

const props={API:'',companyId:2,C:{},btnG:{}};
test('saved result is readable after closing the invitation',async()=>{
  global.fetch=jest.fn(async()=>({ok:true,json:async()=>({items:[{id:42,status:'closed',reason:'Existing account',result:'Connection checked'}],hasMore:false})}));
  render(<MyParticipantTickets {...props}/>);
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button',{name:'Мои обращения'}));
  expect(await screen.findByText('Результат: Connection checked')).toBeInTheDocument();
  expect(fetch.mock.calls[0][1].headers).toMatchObject({'X-Company-Id':'2','X-Company-Mode':'company'});
});
test('late previous organization tickets cannot appear after switch',async()=>{
  let resolve;
  global.fetch=jest.fn(()=>new Promise(r=>{resolve=r;}));
  const view=render(<MyParticipantTickets key="2" {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Мои обращения'}));
  view.rerender(<MyParticipantTickets key="3" {...props} companyId={3}/>);
  await act(async()=>resolve({ok:true,json:async()=>({items:[{id:42,status:'new',reason:'PRIVATE A'}],hasMore:false})}));
  expect(screen.queryByText('PRIVATE A')).not.toBeInTheDocument();
});

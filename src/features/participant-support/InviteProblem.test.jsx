import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import InviteProblem from './InviteProblem';
import SupplierInviteForm from '../../components/SupplierInviteForm';
import { API } from '../../api';

const failure={message:'Карточка используется несколькими организациями',reasonCode:'SUPPLIER_SHARED_CARD',diagnosticId:'synthetic-diagnostic',companyId:2};
const style={C:{},inp:{},btnO:{},btnG:{}};

test('help is explicit, contains only evidence and comment, and never repeats invitation',async()=>{
  global.fetch=jest.fn(async()=>({ok:true,json:async()=>({id:42,status:'new'})}));
  render(<InviteProblem {...style} failure={failure}/>);
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('Сообщить о проблеме'));
  expect(await screen.findByText(/Обращение №42/)).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
  const [path,options]=fetch.mock.calls[0];
  expect(path).toBe(API+'/participant-support/tickets');
  expect(options.headers['X-Company-Id']).toBe('2');
  expect(Object.keys(JSON.parse(options.body)).sort()).toEqual(['comment','diagnosticId']);
});

test('invitation refusal is inline and changing selected card clears diagnostic',async()=>{
  const create=jest.fn(async()=>({inviteFailure:failure}));
  const form={supplierId:7,presetName:'Synthetic supplier',presetCategory:'Materials',expiresInDays:14};
  const props={...style,supplierInviteForm:form,setSupplierInviteForm:jest.fn(),suppliers:[],supplierCategories:['Materials'],createSupplierInvite:create,setShowSupplierInviteModal:jest.fn()};
  const view=render(<SupplierInviteForm {...props}/>);
  fireEvent.click(screen.getByText('Создать ссылку'));
  expect(await screen.findByText(failure.message)).toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
  view.rerender(<SupplierInviteForm {...props} supplierInviteForm={{...form,supplierId:8}}/>);
  await waitFor(()=>expect(screen.queryByText(failure.message)).not.toBeInTheDocument());
});

beforeEach(()=>{global.fetch=jest.fn();});

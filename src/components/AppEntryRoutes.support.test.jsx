import {fireEvent,render,screen} from '@testing-library/react';
import AppEntryRoutes from './AppEntryRoutes';
jest.mock('../app/lazyComponents',()=>({
  SystemOwnerCabinet:()=> <div>Обычный административный кабинет</div>,
  SupportWorkspace:({API,onLogout})=> <section>Назначенное рабочее место {API}<button onClick={onLogout}>Выйти</button></section>,
}));
const original=process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED;
afterEach(()=>{if(original===undefined)delete process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED;else process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED=original;});
test('enabled support role enters only the dedicated workspace',()=>{
  process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED='1';
  const logout=jest.fn();
  render(<AppEntryRoutes user={{role:'platform_support'}} ui={{API:'/api'}} actions={{handleLogout:logout}}/>);
  expect(screen.getByText('Назначенное рабочее место /api')).toBeInTheDocument();
  expect(screen.queryByText('Обычный административный кабинет')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Выйти'}));expect(logout).toHaveBeenCalledTimes(1);
});
test('administrator keeps ordinary independent authority',()=>{
  process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED='1';
  render(<AppEntryRoutes user={{role:'system_owner'}}/>);
  expect(screen.getByText('Обычный административный кабинет')).toBeInTheDocument();
});
test('disabled feature preserves previous support entry',()=>{
  delete process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED;
  render(<AppEntryRoutes user={{role:'platform_support'}}/>);
  expect(screen.getByText('Обычный административный кабинет')).toBeInTheDocument();
});

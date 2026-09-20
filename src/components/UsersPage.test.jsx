import { fireEvent, render, screen, within } from '@testing-library/react';
import UsersPage from './UsersPage';
import { ROLES, ROLE_LABELS, ROLE_GROUPS } from '../constants/roles';

test('employee form offers company roles only', () => {
  render(<UsersPage C={{}} users={[]} projects={[]} user={{role:'директор'}}
    ROLES={ROLES} ROLE_LABELS={ROLE_LABELS} ROLE_GROUPS={ROLE_GROUPS}
    searchUser="" showForm newUser={{name:'',email:'',password:'',role:'бухгалтер'}} />);
  const options = within(screen.getByLabelText('Роль сотрудника')).getAllByRole('option').map(option => option.value);
  expect(options).toContain('бухгалтер');
  expect(options).toContain('заказчик');
  for (const role of ['поставщик','system_owner','platform_admin','platform_support','billing_admin','account_owner','account_admin']) {
    expect(options).not.toContain(role);
  }
});

test('company invitation includes the selected project and excludes platform roles', () => {
  const createInvite = jest.fn();
  render(<UsersPage C={{}} users={[]} projects={[{id:7,name:'Test object'}]} user={{role:'директор'}}
    ROLES={ROLES} ROLE_LABELS={ROLE_LABELS} ROLE_GROUPS={ROLE_GROUPS}
    searchUser="" showInvites inviteCodes={[]} newInviteRole="заказчик" createInvite={createInvite} />);
  const roleOptions = within(screen.getByLabelText('Роль приглашённого')).getAllByRole('option').map(option=>option.value);
  expect(roleOptions).not.toContain('system_owner');
  fireEvent.change(screen.getByLabelText('Объект приглашённого'), {target:{value:'7'}});
  fireEvent.click(screen.getByRole('button',{name:'Создать код'}));
  expect(createInvite).toHaveBeenCalledWith({projectId:'7',assignedPackages:[]});
});

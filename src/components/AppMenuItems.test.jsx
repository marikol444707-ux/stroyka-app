import { buildAppMenuItems } from './AppMenuItems';
import { ROLES } from '../constants/roles';

test('company user management is reachable for leadership only',()=>{
  expect(buildAppMenuItems().find(item=>item.id==='users').label).toBe('Пользователи');
  const allowed=Object.entries(ROLES).filter(([,pages])=>pages.includes('users')).map(([role])=>role).sort();
  expect(allowed).toEqual(['директор','зам_директора']);
});

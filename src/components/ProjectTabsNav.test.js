import { projectTabGroupsForRole } from './ProjectTabsNav';

describe('projectTabGroupsForRole', () => {
  it('keeps project materials under Object instead of Finance for leadership', () => {
    const groups = projectTabGroupsForRole('директор');
    const finance = groups.find(group => group.id === 'finance');
    const object = groups.find(group => group.id === 'object');

    expect(finance.tabs).toEqual(['Финансы', 'Смета']);
    expect(object.tabs).toContain('Материалы');
  });

  it('keeps project materials available to the foreman under Object', () => {
    const groups = projectTabGroupsForRole('прораб');
    const object = groups.find(group => group.id === 'object');

    expect(object.tabs).toContain('Материалы');
  });
});

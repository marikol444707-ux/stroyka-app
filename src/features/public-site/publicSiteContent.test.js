import { normalizeSiteProject } from './publicSiteContent';

test('does not replace missing public fields with internal or stock content', () => {
  const project = normalizeSiteProject({
    id: 17,
    projectName: 'ул. Частная, заказчик Иванов',
    publicTitle: '',
    images: [],
  });

  expect(project.title).toBe('');
  expect(project.images).toEqual([]);
  expect(JSON.stringify(project)).not.toContain('ул. Частная');
});

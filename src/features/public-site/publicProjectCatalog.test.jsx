import { referenceDirections, getReferenceProjectCards, getProjectMediaOptions, findReferenceProjectByCode, getProjectSpecs } from './publicSiteContent';

test('does not publish retired duplicate house concepts', () => {
  const cards = referenceDirections.flatMap(getReferenceProjectCards);
  expect(cards).toHaveLength(43);
  expect(new Set(cards.map(({ code }) => code)).size).toBe(cards.length);
  expect(findReferenceProjectByCode('H2-03')).toBeNull();
  expect(findReferenceProjectByCode('B2-03')).toBeNull();
});

test('garage facade concept has no unverified floor plans', () => {
  const { direction, project } = findReferenceProjectByCode('B2-02');
  const media = getProjectMediaOptions(direction, project);
  expect(media).toHaveLength(2);
  expect(media.every(({ role }) => role === 'render')).toBe(true);
  expect(project.visuals).toContain('Планировка пока не разработана');
  expect(getProjectSpecs(direction, project).map(([label]) => label)).not.toContain('Размеры');
  expect(getProjectSpecs(direction, project)).toContainEqual(['Планировка и конструктив', 'требуют разработки']);
});

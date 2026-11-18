import React from 'react';
import { render, screen } from '@testing-library/react';
import PublicProjectPlan, { getPlanPresentation } from './PublicProjectPlan';
import { findReferenceProjectByCode, getProjectMediaOptions, ProjectConceptVisual } from './publicSiteContent';

test('floor switch renders the matching readable room list and full sheet', () => {
  const { direction, project } = findReferenceProjectByCode('TOWN-02');
  const media = getProjectMediaOptions(direction, project).filter(m => m.role === 'plan');
  const { rerender } = render(<ProjectConceptVisual direction={direction} project={project} media={media[0]} />);
  expect(screen.getByText('Кухня-гостиная')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Открыть крупно/ })).toHaveAttribute('href', expect.stringContaining('plan-1-sheet.svg'));
  rerender(<ProjectConceptVisual direction={direction} project={project} media={media[1]} />);
  expect(screen.queryByText('Кухня-гостиная')).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Открыть крупно/ })).toHaveAttribute('href', expect.stringContaining('plan-2-sheet.svg'));
});

test('thumbnails stay noninteractive and original drawings are not replaced', () => {
  render(<PublicProjectPlan plan={getPlanPresentation('/site-assets/projects/town-02/plan-1.png')} title="Таунхаус" compact />);
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
  expect(screen.getByRole('img')).toHaveAttribute('src', expect.stringContaining('diagram.svg'));
  expect(getPlanPresentation('/site-assets/projects/h1-01/plan.png')).toBeUndefined();
  expect(getPlanPresentation('/site-assets/projects/b2-02/plan-1.png')).toBeUndefined();
});

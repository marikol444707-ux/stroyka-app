import React from 'react';
import { render, screen } from '@testing-library/react';
import {
  ProjectConceptThumb,
  ProjectConceptVisual,
  getReferenceProjectCards,
  normalizeSiteProject,
  referenceDirections,
} from './publicSiteContent';

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

test('loads project card images lazily without blocking the catalog', () => {
  const direction = referenceDirections[0];
  const project = getReferenceProjectCards(direction)[0];
  const media = project.media.find((item) => item.src);

  render(
    <>
      <ProjectConceptThumb direction={direction} project={project} />
      <ProjectConceptVisual direction={direction} project={project} media={media} />
    </>,
  );

  screen.getAllByRole('img').forEach((image) => {
    expect(image).toHaveAttribute('loading', 'lazy');
    expect(image).toHaveAttribute('decoding', 'async');
  });
});

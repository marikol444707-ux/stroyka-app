import React from 'react';
import { render, screen } from '@testing-library/react';
import PublicSitePage from './PublicSitePage';

test('public site links to the object gallery without login', () => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: false,
    json: async () => ({}),
  });

  render(<PublicSitePage onLogin={jest.fn()} />);

  const links = screen.getAllByRole('link', { name: 'Наши объекты' });
  expect(links.length).toBeGreaterThanOrEqual(2);
  links.forEach((link) => {
    expect(link).toHaveAttribute('href', '/our-objects.html');
  });
});

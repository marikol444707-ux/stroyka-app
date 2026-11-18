import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { PublicSiteHero } from './PublicSiteHero';

test('mobile navigation closes on Escape and restores focus to its button', () => {
  render(<PublicSiteHero onLogin={jest.fn()} scrollTo={jest.fn()} onChooseDirection={jest.fn()} />);
  const menu = screen.getByRole('button', { name: 'Меню ☰' });
  fireEvent.click(menu);
  const projects = screen.getByRole('button', { name: 'Проекты', exact: true });
  projects.focus();
  fireEvent.keyDown(projects, { key: 'Escape' });
  expect(menu).toHaveAttribute('aria-expanded', 'false');
  expect(menu).toHaveFocus();
});

test('hero navigation uses the working page callbacks, including mobile login', () => {
  const onLogin = jest.fn();
  const scrollTo = jest.fn();
  const onChooseDirection = jest.fn();
  const { container } = render(<PublicSiteHero {...{ onLogin, scrollTo, onChooseDirection }} />);
  fireEvent.click(screen.getByRole('button', { name: /Сделать ремонт/ }));
  expect(onChooseDirection).toHaveBeenCalledWith('apartment-repair');
  fireEvent.click(screen.getByRole('button', { name: 'Меню ☰' }));
  fireEvent.click(screen.getByRole('button', { name: 'Партнёрам', exact: true }));
  expect(scrollTo).toHaveBeenCalledWith('suppliers');
  expect(screen.getByRole('button', { name: 'Меню ☰' })).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(container.querySelector('button.public-design-mobile-contact'));
  expect(onLogin).toHaveBeenCalledTimes(1);
});

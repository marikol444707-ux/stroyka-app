import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { PublicProjectPackageSelector } from './PublicProjectPackageSelector';

test('renders package estimates and selects a package', () => {
  const onSelect = jest.fn();
  const packages = [
    { value: 'box', label: 'Коробка', estimateFrom: 'от 4 млн ₽', duration: '3 месяца', description: 'Основа', includes: ['Стены'] },
    { value: 'warm', label: 'Тёплый контур', estimateFrom: 'от 6 млн ₽', duration: '5 месяцев', description: 'Закрытый дом', includes: ['Окна'] },
    { value: 'turnkey', label: 'Под ключ', estimateFrom: 'от 9 млн ₽', duration: '8 месяцев', description: 'Готовый дом', includes: ['Отделка'] },
  ];

  render(<PublicProjectPackageSelector packages={packages} selectedValue="box" onSelect={onSelect} />);

  expect(screen.getAllByRole('radio')).toHaveLength(3);
  expect(screen.getByRole('radio', { name: /Коробка/ })).toHaveAttribute('aria-checked', 'true');
  expect(screen.getByRole('radio', { name: /Тёплый контур/ })).toHaveTextContent('от 6 млн ₽');

  fireEvent.click(screen.getByRole('radio', { name: /Тёплый контур/ }));
  expect(onSelect).toHaveBeenCalledWith(packages[1]);
});

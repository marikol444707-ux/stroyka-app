import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { PublicLayoutRequestEditor } from './PublicLayoutRequestEditor';

test('uses rooms and zones for non-house projects', () => {
  const onApply = jest.fn();
  render(
    <PublicLayoutRequestEditor
      projectTitle="Ремонт офисных помещений"
      initialSpaces={3}
      initialBathrooms={1}
      isHouseLayout={false}
      onApply={onApply}
      onCancel={jest.fn()}
    />
  );

  expect(screen.getByRole('spinbutton', { name: 'Комнат / зон' })).toHaveValue(3);
  expect(screen.queryByRole('checkbox', { name: 'Нужен гараж' })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'Добавить в заявку' }));
  expect(onApply).toHaveBeenCalledWith({ spaces: 3, bathrooms: 1, garage: false, notes: '' });
});

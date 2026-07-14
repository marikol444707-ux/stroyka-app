import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { PublicProjectFilePicker } from './PublicProjectFilePicker';

test('shows selected project files and allows one file to be removed', () => {
  const removeFile = jest.fn();
  render(
    <PublicProjectFilePicker
      files={[
        new File(['%PDF-1.7'], 'project.pdf', { type: 'application/pdf' }),
        new File(['photo'], 'facade.jpg', { type: 'image/jpeg' }),
      ]}
      onChoose={jest.fn()}
      onRemove={removeFile}
    />
  );

  expect(screen.getByRole('region', { name: 'Загрузка собственного проекта' })).toHaveTextContent('2 из 5 файлов');
  expect(screen.getByText('project.pdf')).toBeInTheDocument();
  expect(screen.getByText('facade.jpg')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'Удалить project.pdf' }));
  expect(removeFile).toHaveBeenCalledWith(0);
});

test('shows a file validation error next to the picker', () => {
  render(
    <PublicProjectFilePicker
      files={[]}
      error="Разрешены только PDF, JPEG, PNG или WebP."
      onChoose={jest.fn()}
      onRemove={jest.fn()}
    />
  );

  expect(screen.getByRole('alert')).toHaveTextContent('Разрешены только PDF');
});

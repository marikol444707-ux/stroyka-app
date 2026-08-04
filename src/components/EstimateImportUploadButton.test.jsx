import React from 'react';
import { render, screen } from '@testing-library/react';
import EstimateImportUploadButton from './EstimateImportUploadButton';

describe('EstimateImportUploadButton', () => {
  const C = {accent:'#f60',accentLight:'#321',textMuted:'#888'};

  it('requires a project and only accepts parser-supported Excel files', () => {
    render(<EstimateImportUploadButton C={C} onFileChange={jest.fn()} disabled disabledReason="Сначала выберите объект" />);

    const input = screen.getByLabelText('Сначала выберите объект');
    expect(input).toBeDisabled();
    expect(input).toHaveAttribute('accept', '.xlsx,.xlsm');
    expect(screen.getByText('Сначала выберите объект')).toBeInTheDocument();
  });
});

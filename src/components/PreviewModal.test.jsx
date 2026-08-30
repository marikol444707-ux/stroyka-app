import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import PreviewModal from './PreviewModal';

describe('PreviewModal HTML boundary', () => {
  test('removes executable markup before previewing or printing', () => {
    const onPrint = jest.fn();
    const {container} = render(
      <PreviewModal
        content={'<p>Безопасный текст</p><img src="x" onerror="window.__xss=1"><script>window.__xss=2</script>'}
        title="Смета"
        onClose={jest.fn()}
        onPrint={onPrint}
      />,
    );

    expect(screen.getByText('Безопасный текст')).toBeInTheDocument();
    expect(container.querySelector('script')).toBeNull();
    expect(container.querySelector('img')).not.toHaveAttribute('onerror');

    fireEvent.click(screen.getByRole('button', {name:/распечатать/i}));
    expect(onPrint).toHaveBeenCalledTimes(1);
    expect(onPrint.mock.calls[0][0]).not.toMatch(/<script|onerror/i);
  });
});

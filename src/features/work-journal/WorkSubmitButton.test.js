import React from 'react';
import {act, fireEvent, render, screen, waitFor} from '@testing-library/react';
import WorkSubmitButton from './WorkSubmitButton';

it('sends once during a pending request and unlocks after completion', async () => {
  let resolve;
  const submit = jest.fn(() => new Promise(done => { resolve = done; }));
  render(<WorkSubmitButton onSubmit={submit} />);
  const button = screen.getByRole('button', {name: 'Отправить'});
  fireEvent.click(button);
  expect(button.disabled).toBe(true);
  expect(button.textContent).toBe('Отправляем…');
  fireEvent.click(button);
  expect(submit).toHaveBeenCalledTimes(1);
  await act(async () => resolve());
  expect(button.disabled).toBe(false);
  expect(button.textContent).toBe('Отправить');
});

it('shows a connection failure and permits another attempt', async () => {
  const alert = jest.spyOn(window, 'alert').mockImplementation(() => {});
  const submit = jest.fn().mockRejectedValueOnce(new Error('Failed to fetch')).mockResolvedValueOnce();
  try {
    render(<WorkSubmitButton onSubmit={submit} />);
    const button = screen.getByRole('button', {name: 'Отправить'});
    fireEvent.click(button);
    await waitFor(() => expect(alert).toHaveBeenCalledWith('Не удалось подтвердить отправку. Проверьте интернет и журнал работ перед повторной отправкой.'));
    expect(button.disabled).toBe(false);
    fireEvent.click(button);
    await waitFor(() => expect(button.disabled).toBe(false));
    expect(submit).toHaveBeenCalledTimes(2);
  } finally { alert.mockRestore(); }
});

it('does not submit a work without an execution price', () => {
  const submit = jest.fn();
  render(<WorkSubmitButton disabled onSubmit={submit} />);
  fireEvent.click(screen.getByRole('button'));
  expect(submit).not.toHaveBeenCalled();
});

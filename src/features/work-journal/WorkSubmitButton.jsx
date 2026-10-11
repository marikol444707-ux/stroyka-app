import React from 'react';
import useAsyncSubmit from '../../hooks/useAsyncSubmit';

export default function WorkSubmitButton({onSubmit, disabled, style}) {
  const {submit, pending} = useAsyncSubmit(async () => {
    if (disabled) return;
    try {
      await onSubmit();
    } catch (error) {
      window.alert('Не удалось подтвердить отправку. Проверьте интернет и журнал работ перед повторной отправкой.');
    }
  });
  return <button type="button" onClick={submit} disabled={disabled || pending} aria-busy={pending} style={style}>
    {pending ? 'Отправляем…' : 'Отправить'}
  </button>;
}

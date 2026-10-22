import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import CompanyFeaturesPanel from './CompanyFeaturesPanel';

test('platform admin can enable JEV for one company and save a monthly price', async () => {
  const sendJson = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ ok: true }),
  });
  const onReload = jest.fn();
  render(
    <CompanyFeaturesPanel
      API="/api"
      C={{ text: '#111', textSec: '#555', border: '#ddd' }}
      sendJson={sendJson}
      onReload={onReload}
      data={{
        enabledCompanies: 0,
        potentialMonthlyRevenue: '0.00',
        companies: [{
          companyId: 18,
          companyName: 'ООО Тестовая организация',
          inn: '2635000000',
          platformAccountName: 'Группа Строй',
          companyActive: true,
          enabled: false,
          monthlyFee: '0.00',
        }],
      }}
    />
  );

  expect(screen.getByText(/Серверный сбор JEV настроен на: B2B-Center · Росэлторг · Фабрикант · ЭТП ГПБ/)).toBeInTheDocument();
  expect(screen.getByText(/ЕИС пока не входит в текущую серверную команду JEV/)).toBeInTheDocument();

  fireEvent.click(screen.getByLabelText('Подключить JEV'));
  fireEvent.change(screen.getByLabelText('Цена в месяц, ₽'), { target: { value: '9900' } });
  fireEvent.change(screen.getByPlaceholderText('Например: школа, кровля, благоустройство'), { target: { value: 'школа, кровля' } });
  fireEvent.click(screen.getByLabelText('Росэлторг'));
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

  await waitFor(() => expect(sendJson).toHaveBeenCalledWith(
    '/api/system/companies/18/features/jev',
    expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify({
        enabled: true, monthlyFee: '9900', searchTerms: ['школа', 'кровля'],
        sourceProviders: ['B2B-Center', 'Фабрикант', 'ЭТП ГПБ', 'Сбер А', 'ТЭК-Торг', 'Торги Федерации', 'Р-ТЕНДЕР'],
      }),
    })
  ));
  await waitFor(() => expect(onReload).toHaveBeenCalled());
});

test('search filters organizations by name or account', () => {
  render(
    <CompanyFeaturesPanel
      data={{ companies: [
        { companyId: 1, companyName: 'Альфа', platformAccountName: 'Первая группа', companyActive: true },
        { companyId: 2, companyName: 'Бета', platformAccountName: 'Вторая группа', companyActive: true },
      ] }}
      sendJson={jest.fn()}
    />
  );

  fireEvent.change(screen.getByLabelText('Найти организацию'), { target: { value: 'Вторая' } });
  expect(screen.getByText('Бета')).toBeInTheDocument();
  expect(screen.queryByText('Альфа')).not.toBeInTheDocument();
});

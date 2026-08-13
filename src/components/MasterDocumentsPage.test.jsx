import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import MasterDocumentsPage from './MasterDocumentsPage';
import { buildPerformerContractHtml } from '../utils/contractTemplates';

const renderPage = (overrides = {}) => {
  const buildContractContent = jest.fn(() => '<p>Договор мастера</p>');
  const showPreview = jest.fn();
  const ownProfile = {
    userId: 17,
    fullName: 'Иванов Иван Иванович',
    inn: '123456789012',
  };
  const contractItems = [{
    contractId: 91,
    name: 'Штукатурка стен',
    unit: 'м²',
    quantity: 10,
    priceBrigade: 500,
    priceSmeta: 9900,
  }];

  render(
    <MasterDocumentsPage
      API="/api"
      C={{
        text: '#111', textSec: '#333', textMuted: '#777', bg: '#fff', border: '#ddd',
        success: '#080', successLight: '#efe', successBorder: '#8c8',
        info: '#057', infoLight: '#eef', infoBorder: '#9bd',
      }}
      btnB={{}}
      btnG={{}}
      btnO={{}}
      buildActContent={jest.fn()}
      buildContractContent={buildContractContent}
      buildHiddenActContent={jest.fn()}
      card={{}}
      doPrint={jest.fn()}
      hiddenActs={[]}
      masterProfile={ownProfile}
      masterProfiles={[]}
      myActs={[]}
      myContract={{
        id: 91,
        contractNumber: 'Д-17',
        contractType: 'ГПХ',
        project: 'Лицей',
      }}
      myContractItems={contractItems}
      myTools={[]}
      pdConsents={[]}
      PD_CONSENT_TEXT={jest.fn(() => '<p>Согласие</p>')}
      refreshData={jest.fn()}
      setEditingHiddenAct={jest.fn()}
      setHiddenActs={jest.fn()}
      showPreview={showPreview}
      uploadPhoto={jest.fn()}
      user={{id: 17, name: 'Иванов Иван Иванович', role: 'мастер'}}
      {...overrides}
    />,
  );

  return {buildContractContent, contractItems, ownProfile, showPreview};
};

test('opens the master contract with the separately loaded own profile', () => {
  const {buildContractContent, contractItems, ownProfile, showPreview} = renderPage();
  const contractCard = screen.getByText(/Договор № Д-17/).parentElement;

  fireEvent.click(within(contractCard).getByRole('button', {name: 'Просмотр'}));

  expect(buildContractContent).toHaveBeenCalledWith(
    ownProfile,
    expect.objectContaining({contractNumber: 'Д-17', project: 'Лицей'}),
    contractItems,
  );
  expect(showPreview).toHaveBeenCalledWith('<p>Договор мастера</p>', 'Договор');
});

test('opens the contract while the own profile is still unavailable', () => {
  const {buildContractContent, contractItems, showPreview} = renderPage({
    masterProfile: null,
    masterProfiles: [],
  });
  const contractCard = screen.getByText(/Договор № Д-17/).parentElement;

  fireEvent.click(within(contractCard).getByRole('button', {name: 'Просмотр'}));

  expect(buildContractContent).toHaveBeenCalledWith(
    null,
    expect.objectContaining({contractNumber: 'Д-17'}),
    contractItems,
  );
  expect(showPreview).toHaveBeenCalledWith('<p>Договор мастера</p>', 'Договор');
});

test('rejects a stale own profile and uses the matching directory profile', () => {
  const matchingProfile = {user_id: '17', fullName: 'Иванов Иван Иванович'};
  const {buildContractContent, contractItems} = renderPage({
    masterProfile: {userId: 99, fullName: 'Профиль другого пользователя'},
    masterProfiles: [matchingProfile],
  });
  const contractCard = screen.getByText(/Договор № Д-17/).parentElement;

  fireEvent.click(within(contractCard).getByRole('button', {name: 'Просмотр'}));

  expect(buildContractContent).toHaveBeenCalledWith(
    matchingProfile,
    expect.objectContaining({contractNumber: 'Д-17'}),
    contractItems,
  );
});

test('renders the brigade rate and line total in the opened contract', () => {
  const {showPreview} = renderPage({
    buildContractContent: (profile, contract, items) => buildPerformerContractHtml({
      company: 'ООО Заказчик',
      performer: profile,
      contract,
      items,
    }),
  });
  const contractCard = screen.getByText(/Договор № Д-17/).parentElement;

  fireEvent.click(within(contractCard).getByRole('button', {name: 'Просмотр'}));

  const html = showPreview.mock.calls[0][0];
  expect(html).toContain('<th>Цена</th>');
  expect(html).toContain('Штукатурка стен');
  expect(html).toMatch(/>500</);
  expect(html).toMatch(/>5(?:\s|&nbsp;| )*000</);
  expect(html).not.toContain('9 900');
  expect(html).not.toContain('99 000');
});

import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import MasterDocumentsPage from './MasterDocumentsPage';

const renderPage = (overrides = {}) => {
  const buildContractContent = jest.fn(() => '<p>Договор мастера</p>');
  const showPreview = jest.fn();
  const ownProfile = {
    userId: 17,
    fullName: 'Иванов Иван Иванович',
    inn: '123456789012',
  };

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

  return {buildContractContent, ownProfile, showPreview};
};

test('opens the master contract with the separately loaded own profile', () => {
  const {buildContractContent, ownProfile, showPreview} = renderPage();
  const contractCard = screen.getByText(/Договор № Д-17/).parentElement;

  fireEvent.click(within(contractCard).getByRole('button', {name: 'Просмотр'}));

  expect(buildContractContent).toHaveBeenCalledWith(
    ownProfile,
    expect.objectContaining({contractNumber: 'Д-17', project: 'Лицей'}),
  );
  expect(showPreview).toHaveBeenCalledWith('<p>Договор мастера</p>', 'Договор');
});

test('opens the contract while the own profile is still unavailable', () => {
  const {buildContractContent, showPreview} = renderPage({
    masterProfile: null,
    masterProfiles: [],
  });
  const contractCard = screen.getByText(/Договор № Д-17/).parentElement;

  fireEvent.click(within(contractCard).getByRole('button', {name: 'Просмотр'}));

  expect(buildContractContent).toHaveBeenCalledWith(
    null,
    expect.objectContaining({contractNumber: 'Д-17'}),
  );
  expect(showPreview).toHaveBeenCalledWith('<p>Договор мастера</p>', 'Договор');
});

test('rejects a stale own profile and uses the matching directory profile', () => {
  const matchingProfile = {user_id: '17', fullName: 'Иванов Иван Иванович'};
  const {buildContractContent} = renderPage({
    masterProfile: {userId: 99, fullName: 'Профиль другого пользователя'},
    masterProfiles: [matchingProfile],
  });
  const contractCard = screen.getByText(/Договор № Д-17/).parentElement;

  fireEvent.click(within(contractCard).getByRole('button', {name: 'Просмотр'}));

  expect(buildContractContent).toHaveBeenCalledWith(
    matchingProfile,
    expect.objectContaining({contractNumber: 'Д-17'}),
  );
});

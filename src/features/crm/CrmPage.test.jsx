import { render, screen } from '@testing-library/react';
import CrmPage from './CrmPage';

test('shows a direct comparison action for a public-site lead', () => {
  const comparisonUrl = 'https://stroyka26.pro/?project=H1-02&compare=H1-01%2CH1-02#projects';
  render(
    <CrmPage
      API=""
      C={{
        accent: '#06715c', accentLight: '#e8f5f1', accentBorder: '#b7ddd3',
        bg: '#fff', border: '#ddd', danger: '#b42318', dangerLight: '#fee4e2', dangerBorder: '#fecdca',
        success: '#067647', successLight: '#ecfdf3', successBorder: '#abefc6',
        warning: '#b54708', warningLight: '#fffaeb', warningBorder: '#fedf89',
        text: '#101828', textSec: '#475467', textMuted: '#667085',
      }}
      CRM_STAGES={['Новый']}
      btnG={{}}
      btnB={{}}
      btnO={{}}
      btnR={{}}
      card={{}}
      leads={[{
        id: 1,
        name: 'Заявка с сайта',
        leadType: 'Клиент',
        stage: 'Новый',
        notes: `Ссылка на сравнение: ${comparisonUrl}`,
      }]}
      newLead={{}}
      inp={{}}
      setEditingItem={jest.fn()}
      setLeads={jest.fn()}
      setNewLead={jest.fn()}
      setShowForm={jest.fn()}
      showForm={false}
      isMobile
    />,
  );

  expect(screen.getByRole('link', { name: 'Открыть сравнение' })).toHaveAttribute('href', comparisonUrl);
});

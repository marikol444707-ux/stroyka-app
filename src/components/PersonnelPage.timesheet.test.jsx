import { fireEvent, render, screen } from '@testing-library/react';
import PersonnelPage from './PersonnelPage';

const C = { text: '#111', textSec: '#666', textMuted: '#999', success: 'green', border: '#ccc' };

function renderTimesheet(companyContext) {
  const toggleDay = jest.fn();
  render(
    <PersonnelPage
      C={C}
      btnG={{}}
      btnO={{}}
      calcSalary={() => 0}
      companyContext={companyContext}
      daysInMonth={['2026-07-01']}
      matchSearch={() => true}
      personnelTab="timesheet"
      setPersonnelTab={() => {}}
      setShowForm={() => {}}
      staff={[{ id: 5, name: 'Анна', role: 'мастер' }]}
      tbl={{}}
      tblC={{}}
      tblH={{}}
      timesheet={{}}
      toggleDay={toggleDay}
      workedDays={() => 0}
    />
  );
  return toggleDay;
}

describe('timesheet grid follows the selected company', () => {
  it('keeps day cells read-only while every company is selected', () => {
    const toggleDay = renderTimesheet({ mode: 'all_companies', selectedCompanyId: null });
    expect(screen.getByText(/табель только для просмотра/)).toBeInTheDocument();
    fireEvent.click(screen.getByText('Анна').closest('tr').querySelector('td:nth-child(2)'));
    expect(toggleDay).not.toHaveBeenCalled();
  });

  it('lets a single selected company mark a day', () => {
    const toggleDay = renderTimesheet({ mode: 'company', selectedCompanyId: 10 });
    expect(screen.queryByText(/табель только для просмотра/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('Анна').closest('tr').querySelector('td:nth-child(2)'));
    expect(toggleDay).toHaveBeenCalledWith(5, '2026-07-01');
  });
});

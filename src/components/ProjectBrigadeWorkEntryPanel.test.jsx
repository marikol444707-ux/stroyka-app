import { render, screen } from '@testing-library/react';

import ProjectBrigadeWorkEntryPanel from './ProjectBrigadeWorkEntryPanel';


test('does not offer the legacy estimate import through the manual item endpoint', () => {
  render(
    <ProjectBrigadeWorkEntryPanel
      project={{id: 19, name: 'Лицей'}}
      selectedBrigadeContract={{id: 7, workPackage: 'Отделка'}}
      estimatesList={[{
        id: 9,
        name: 'Смета',
        projectId: 19,
        workPackage: 'Отделка',
        sections: [{name: 'Стены', items: [{name: 'Штукатурка'}]}],
      }]}
      newBrigadeItem={{
        name: '', unit: 'м2', quantity: '', priceSmeta: '', priceBrigade: '', workPackage: 'Отделка',
      }}
      setNewBrigadeItem={jest.fn()}
      setBrigadeContractItems={jest.fn()}
      UNITS={['м2']}
      C={{text: '#111', textSec: '#666'}}
      card={{}}
      inp={{}}
      btnG={{}}
      btnO={{}}
      showLeadership
    />,
  );

  expect(screen.queryByText('Загрузить из сметы:')).not.toBeInTheDocument();
  expect(screen.getByText('Добавить работу вручную')).toBeInTheDocument();
});

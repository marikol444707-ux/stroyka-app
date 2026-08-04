import React from 'react';
import { render, screen } from '@testing-library/react';
import EstimateProjectGroupCard from './EstimateProjectGroupCard';

const estimate = {
  id: 1,
  name: 'Объектная смета',
  projectName: 'Тестовый объект',
  smetaType: 'Заказчик',
  workPackage: 'Основная',
  status: 'Активная',
  version: '1.0',
  sections: [],
};

describe('EstimateProjectGroupCard', () => {
  it('keeps the expanded estimate list compact without repeating active estimate details', () => {
    render(
      <EstimateProjectGroupCard
        C={{bg:'#111',bgWhite:'#222',bgGray:'#333',border:'#444',text:'#fff',textSec:'#bbb',textMuted:'#888',success:'#2d9',info:'#59f',infoLight:'#123',infoBorder:'#456',warning:'#fa0'}}
        card={{}}
        badge={() => ({})}
        projectName="Тестовый объект"
        groups={[["group", [estimate]]]}
        isOpen
        onToggle={jest.fn()}
        setSelectedEstimate={jest.fn()}
        estimateTypeIcon={() => 'S'}
        estimateKind={row => row.smetaType}
        estimatePackage={row => row.workPackage}
        estimateUpdatedTs={() => 1}
        estimateTotal={() => 1000}
        estimateStatusView={() => ({label:'Активная'})}
        estimateDisplayVersion={() => 'v1.0'}
        isArchivedEstimate={() => false}
        setEstimateStatusRemote={jest.fn()}
      />,
    );

    expect(screen.getByText(/Объектная смета/)).toBeInTheDocument();
    expect(screen.queryByText(/Сейчас в расчётах/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Цепочка:/)).not.toBeInTheDocument();
  });
});

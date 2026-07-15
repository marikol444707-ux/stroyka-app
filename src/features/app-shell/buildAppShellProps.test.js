import React from 'react';
import { render, screen } from '@testing-library/react';
import { buildAppShellProps } from './buildAppShellProps';
import WorkAssignmentModal from '../work-assignment/WorkAssignmentModal';

describe('buildAppShellProps work assignment modal', () => {
  test('passes the selected estimate from app state to the modal', () => {
    const selectedEstimate = {
      id: 25,
      name: 'Электрика',
      projectName: 'Объект',
      sections: [],
    };

    const props = buildAppShellProps({
      API: '/api',
      appMainState: {
        selectedEstimate,
        staff: [],
        users: [],
      },
      estimateWorkflowState: {
        showWorkAssignment: true,
        setShowWorkAssignment: jest.fn(),
      },
      ui: {},
    });

    expect(props.workAssignmentProps.show).toBe(true);
    expect(props.workAssignmentProps.selectedEstimate).toBe(selectedEstimate);
  });

  test('renders the work assignment modal for the selected estimate', () => {
    const props = buildAppShellProps({
      API: '/api',
      appMainState: {
        selectedEstimate: {
          id: 25,
          name: 'Электрика',
          projectName: 'Объект',
          sections: [],
        },
        staff: [],
        users: [],
      },
      estimateWorkflowState: {
        showWorkAssignment: true,
        setShowWorkAssignment: jest.fn(),
      },
      ui: { C: {} },
    });

    render(<WorkAssignmentModal {...props.workAssignmentProps} />);

    expect(screen.getByText('Назначить работы исполнителю')).toBeInTheDocument();
  });
});

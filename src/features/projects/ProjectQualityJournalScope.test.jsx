import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import ProjectMaterialInspectionTab from './ProjectMaterialInspectionTab';
import ProjectCableJournalTab from './ProjectCableJournalTab';
import ProjectJournalsHubTab from './ProjectJournalsHubTab';

test.each([['inspection', ProjectMaterialInspectionTab], ['cable', ProjectCableJournalTab]])('%s tab and print keep exact project identity', (_kind, Tab) => {
  const project = { id: 11, companyId: 2, name: 'Школа' };
  const own = { id: 1, companyId: 2, projectId: 11, projectName: 'Старое имя', materialName: 'OWN', cableBrand: 'OWN' };
  const foreign = { ...own, id: 2, companyId: 3, projectName: 'Школа', materialName: 'FOREIGN', cableBrand: 'FOREIGN' };
  const build = jest.fn(() => 'HTML');
  render(<Tab project={project} materialInspections={[own, foreign]} cableJournal={[own, foreign]}
    C={{}} Eye={() => null} badge={() => ({})} cableTypeOf={() => 'Кабель'} toNum={Number}
    journalDiagnosticMode="all" projectJournalDiagnostics={() => ({ stockWithoutInspection: [], cableWithoutJournal: [] })}
    buildMaterialInspectionContent={build} buildCableJournalContent={build} showPreview={jest.fn()} />);
  expect(screen.getByText('OWN')).toBeInTheDocument();
  expect(screen.queryByText('FOREIGN')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Печать журнала/ }));
  expect(build).toHaveBeenCalledWith([own], project, '', '');
});

test('journal hub does not show fake counts or diagnostic success when loading failed', () => {
  const diagnostics = {
    inspectionIssue: 'Входной контроль: ошибка 409', cableIssue: 'Кабельный журнал не загружен',
    inspections: [], cables: [], projectStock: [], cableStock: [], stockWithoutInspection: [], cableWithoutJournal: [],
    smetaRows: [], smetaOutsideRows: [], aliasNeededRows: [], smetaInPlanRows: [], smetaOverRows: [],
  };
  const { container } = render(<ProjectJournalsHubTab C={{}} card={{}} project={{ name: 'Школа' }}
    hiddenActs={[]} prescriptionsList={[]} workJournal={[]} projectJournalDiagnostics={() => diagnostics} />);
  expect(screen.getByText(diagnostics.inspectionIssue)).toBeInTheDocument();
  expect(screen.getByText(diagnostics.cableIssue)).toBeInTheDocument();
  for (const title of ['Входной контроль материалов', 'Кабельная продукция']) {
    const card = screen.getByText(title).parentElement.parentElement;
    expect(card.textContent).not.toContain('0 записей');
    expect(card.textContent).not.toContain('не связано');
  }
  expect(container.textContent).not.toContain('Есть несвязанные позиции');
});

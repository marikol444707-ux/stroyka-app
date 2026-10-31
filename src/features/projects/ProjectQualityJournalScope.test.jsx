import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import ProjectMaterialInspectionTab from './ProjectMaterialInspectionTab';
import ProjectCableJournalTab from './ProjectCableJournalTab';
import ProjectJournalsHubTab from './ProjectJournalsHubTab';

test.each([
  ['inspection', ProjectMaterialInspectionTab, '🖨 Печать полного журнала'],
  ['cable', ProjectCableJournalTab, '🖨 Печать журнала'],
])('%s tab and print keep exact project identity', (_kind, Tab, printLabel) => {
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
  fireEvent.click(screen.getByRole('button', { name: printLabel }));
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

test('pending inspection filter keeps closed own records in the full printed journal', () => {
  const project = { id: 11, companyId: 2, name: 'Школа' };
  const pending = { id: 1, companyId: 2, projectId: 11, projectName: 'Старое имя', materialName: 'PENDING' };
  const closed = { ...pending, id: 2, materialName: 'CLOSED', inspected: true, status: 'Закрыта' };
  const foreign = { ...closed, id: 3, companyId: 3, projectName: 'Школа', materialName: 'FOREIGN' };
  const otherProject = { ...closed, id: 4, projectId: 12, projectName: 'Школа', materialName: 'OTHER' };
  const build = jest.fn(() => 'HTML');
  const preview = jest.fn();
  render(<ProjectMaterialInspectionTab project={project} materialInspections={[pending, closed, foreign, otherProject]}
    C={{}} Eye={() => null} badge={() => ({})} toNum={Number}
    journalDiagnosticMode="pending" projectJournalDiagnostics={() => ({ stockWithoutInspection: [] })}
    buildMaterialInspectionContent={build} showPreview={preview} />);
  expect(screen.getByText('PENDING')).toBeInTheDocument();
  for (const label of ['CLOSED', 'FOREIGN', 'OTHER']) {
    expect(screen.queryByText(label)).not.toBeInTheDocument();
  }
  fireEvent.click(screen.getByRole('button', { name: '🖨 Печать полного журнала' }));
  expect(build).toHaveBeenCalledTimes(1);
  expect(build).toHaveBeenCalledWith([pending, closed], project, '', '');
  expect(preview).toHaveBeenCalledWith('HTML', 'Журнал входного контроля — Школа');
});

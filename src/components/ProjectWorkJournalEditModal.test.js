import {render, screen} from '@testing-library/react';

import ProjectWorkJournalEditModal from './ProjectWorkJournalEditModal';


jest.mock('./PhotoAttachmentField', () => function MockPhotoAttachmentField(props) {
  return (
    <div
      data-testid="work-journal-photo-field"
      data-protected-preview={String(Boolean(props.protectedPreview))}
      data-context={props.context}
    />
  );
});


it('opts only the work-journal edit photo field into protected preview', () => {
  const colors = {
    accent: '#f97316',
    bg: '#0f172a',
    bgWhite: '#ffffff',
    border: '#cbd5e1',
    danger: '#dc2626',
    success: '#16a34a',
    text: '#0f172a',
    textMuted: '#64748b',
  };
  render(
    <ProjectWorkJournalEditModal
      journal={{
        id: 11,
        project: 'Тестовый объект',
        date: '2026-07-11',
        description: 'Штукатурка стен',
        masterName: 'Мастер',
        quantity: 10,
        unit: 'м2',
        total: 1000,
        photoUrl: '/tenant-files/74/content',
      }}
      setEditingJournal={jest.fn()}
      setWorkJournal={jest.fn()}
      setEditingAct={jest.fn()}
      showPreview={jest.fn()}
      buildWorkJournalContent={jest.fn()}
      fmtMeasure={(quantity, unit) => quantity + ' ' + unit}
      C={colors}
      card={{}}
      inp={{}}
      btnB={{}}
      btnG={{}}
      btnO={{}}
    />,
  );

  expect(screen.getByTestId('work-journal-photo-field')).toHaveAttribute('data-protected-preview', 'true');
  expect(screen.getByTestId('work-journal-photo-field')).toHaveAttribute('data-context', 'work-journal');
});

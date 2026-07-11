import {fireEvent, render, waitFor} from '@testing-library/react';

import ProjectLettersPanel from './ProjectLettersPanel';


const buildProps = (overrides = {}) => ({
  projectId: 17,
  projectName: 'Лицей',
  projectLetters: [],
  newLetter: {
    side: 'customer',
    direction: 'outgoing',
    subject: '',
    body: '',
    counterparty: '',
    letterDate: '',
    fileUrl: '',
  },
  setNewLetter: jest.fn(),
  showLetterForm: true,
  setShowLetterForm: jest.fn(),
  uploadingLetter: false,
  setUploadingLetter: jest.fn(),
  uploadPhoto: jest.fn().mockResolvedValue('/tenant-files/31/content'),
  fileSrc: value => value,
  loadAll: jest.fn(),
  user: {name: 'Прораб'},
  C: {
    accent: '#2563eb',
    accentBorder: '#bfdbfe',
    accentLight: '#eff6ff',
    border: '#e5e7eb',
    success: '#15803d',
    successLight: '#f0fdf4',
    text: '#111827',
    textMuted: '#6b7280',
    textSec: '#4b5563',
    warning: '#b45309',
  },
  card: {},
  inp: {},
  btnO: {},
  btnG: {},
  btnB: {},
  btnR: {},
  ...overrides,
});


describe('ProjectLettersPanel', () => {
  it('requests a protected URL for a new letter attachment', async () => {
    const props = buildProps();
    const {container} = render(<ProjectLettersPanel {...props}/>);
    const file = new File(['letter'], 'letter.pdf', {type: 'application/pdf'});

    fireEvent.change(container.querySelector('input[type="file"]'), {
      target: {files: [file]},
    });

    await waitFor(() => expect(props.uploadPhoto).toHaveBeenCalledWith(file, {
      projectId: 17,
      projectName: 'Лицей',
      context: 'project-letters',
      preferProtectedUrl: true,
    }));
  });
});

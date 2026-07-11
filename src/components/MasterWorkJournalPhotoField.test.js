import {fireEvent, render, screen, waitFor} from '@testing-library/react';

import MasterWorkJournalPhotoField from './MasterWorkJournalPhotoField';


describe('MasterWorkJournalPhotoField', () => {
  const originalFetch = global.fetch;
  const originalCreateObjectUrl = global.URL.createObjectURL;
  const originalRevokeObjectUrl = global.URL.revokeObjectURL;

  beforeEach(() => {
    global.fetch = jest.fn();
    global.URL.createObjectURL = jest.fn(() => 'blob:master-work-photo');
    global.URL.revokeObjectURL = jest.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    if (originalCreateObjectUrl) global.URL.createObjectURL = originalCreateObjectUrl;
    else delete global.URL.createObjectURL;
    if (originalRevokeObjectUrl) global.URL.revokeObjectURL = originalRevokeObjectUrl;
    else delete global.URL.revokeObjectURL;
  });

  it('loads protected work-journal photos through the authenticated preview', async () => {
    const blob = new Blob(['master-work-photo'], {type: 'image/png'});
    global.fetch.mockResolvedValue({ok: true, blob: async () => blob});

    const {unmount} = render(
      <MasterWorkJournalPhotoField
        value="/tenant-files/81/content"
        fileSrc={value => 'https://api.test' + value}
      />,
    );

    expect(screen.getByRole('status', {name: 'Фото загружается'})).toBeInTheDocument();
    expect(await screen.findByRole('img')).toHaveAttribute('src', 'blob:master-work-photo');
    expect(global.fetch).toHaveBeenCalledWith(
      'https://api.test/tenant-files/81/content',
      expect.objectContaining({credentials: 'include', cache: 'no-store'}),
    );
    unmount();
    expect(global.URL.revokeObjectURL).toHaveBeenCalledWith('blob:master-work-photo');
  });

  it('keeps the master work-submission upload contract on work-journal context', async () => {
    const appendPhotos = jest.fn().mockResolvedValue('/uploads/company-1/master-work.png');
    const onChange = jest.fn();
    const {container} = render(
      <MasterWorkJournalPhotoField
        value=""
        appendPhotos={appendPhotos}
        onChange={onChange}
        projectName="Тестовый объект"
        context="wrong-context"
      />,
    );
    const file = new File(['photo'], 'master-work.png', {type: 'image/png'});

    fireEvent.change(container.querySelector('input[multiple]'), {target: {files: [file]}});

    await waitFor(() => expect(appendPhotos).toHaveBeenCalledWith(
      '',
      [file],
      {projectName: 'Тестовый объект', context: 'work-journal'},
    ));
    expect(onChange).toHaveBeenCalledWith('/uploads/company-1/master-work.png');
  });
});

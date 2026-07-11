import {fireEvent, render, screen, waitFor} from '@testing-library/react';

import PhotoAttachmentField from './PhotoAttachmentField';


describe('PhotoAttachmentField protected preview opt-in', () => {
  const originalFetch = global.fetch;
  const originalCreateObjectUrl = global.URL.createObjectURL;
  const originalRevokeObjectUrl = global.URL.revokeObjectURL;

  beforeEach(() => {
    global.fetch = jest.fn();
    global.URL.createObjectURL = jest.fn(() => 'blob:attachment-photo');
    global.URL.revokeObjectURL = jest.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    if (originalCreateObjectUrl) global.URL.createObjectURL = originalCreateObjectUrl;
    else delete global.URL.createObjectURL;
    if (originalRevokeObjectUrl) global.URL.revokeObjectURL = originalRevokeObjectUrl;
    else delete global.URL.revokeObjectURL;
  });

  it('keeps protected URLs direct by default for existing callers', () => {
    render(
      <PhotoAttachmentField
        value="/tenant-files/71/content"
        fileSrc={value => 'https://api.test' + value}
      />,
    );

    expect(screen.getByRole('img')).toHaveAttribute('src', 'https://api.test/tenant-files/71/content');
    expect(global.fetch).not.toHaveBeenCalled();
    expect(global.URL.createObjectURL).not.toHaveBeenCalled();
  });

  it('loads protected content through authenticated Blob preview when opted in', async () => {
    const blob = new Blob(['protected-photo'], {type: 'image/png'});
    const setShowPhotoModal = jest.fn();
    global.fetch.mockResolvedValue({ok: true, blob: async () => blob});
    const {unmount} = render(
      <PhotoAttachmentField
        value="/tenant-files/72/content"
        fileSrc={value => 'https://api.test' + value}
        setShowPhotoModal={setShowPhotoModal}
        protectedPreview
      />,
    );

    expect(screen.getByRole('status', {name: 'Фото загружается'})).toBeInTheDocument();
    const image = await screen.findByRole('img');
    expect(image).toHaveAttribute('src', 'blob:attachment-photo');
    expect(global.fetch).toHaveBeenCalledWith(
      'https://api.test/tenant-files/72/content',
      expect.objectContaining({credentials: 'include', cache: 'no-store'}),
    );
    expect(global.URL.createObjectURL).toHaveBeenCalledWith(blob);

    fireEvent.click(image);
    expect(setShowPhotoModal).toHaveBeenCalledWith('blob:attachment-photo');

    unmount();
    expect(global.URL.revokeObjectURL).toHaveBeenCalledWith('blob:attachment-photo');
  });

  it('keeps compatibility uploads direct even when protected preview is enabled', () => {
    render(
      <PhotoAttachmentField
        value="/uploads/company-1/photo.png"
        fileSrc={value => 'https://api.test' + value}
        protectedPreview
      />,
    );

    expect(screen.getByRole('img')).toHaveAttribute('src', 'https://api.test/uploads/company-1/photo.png');
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('fails closed when protected content is forbidden', async () => {
    global.fetch.mockResolvedValue({ok: false, status: 403});
    render(<PhotoAttachmentField value="/tenant-files/73/content" protectedPreview/>);

    await waitFor(() => expect(screen.getByRole('status', {name: 'Фото недоступно'})).toBeInTheDocument());
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(global.URL.createObjectURL).not.toHaveBeenCalled();
  });

  it('preserves the compatibility upload contract', async () => {
    const appendPhotos = jest.fn().mockResolvedValue('/uploads/company-1/new-photo.png');
    const onChange = jest.fn();
    const {container} = render(
      <PhotoAttachmentField
        value=""
        appendPhotos={appendPhotos}
        onChange={onChange}
        projectName="Тестовый объект"
        context="work-journal"
        protectedPreview
      />,
    );
    const file = new File(['photo'], 'photo.png', {type: 'image/png'});

    fireEvent.change(container.querySelector('input[multiple]'), {target: {files: [file]}});

    await waitFor(() => expect(appendPhotos).toHaveBeenCalledWith(
      '',
      [file],
      {projectName: 'Тестовый объект', context: 'work-journal'},
    ));
    expect(onChange).toHaveBeenCalledWith('/uploads/company-1/new-photo.png');
  });
});

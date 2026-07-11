import {fireEvent, render, screen, waitFor} from '@testing-library/react';

import CompanyChatMessageBubble from './CompanyChatMessageBubble';


const buildProps = (photoUrl, overrides = {}) => ({
  msg: {
    id: 7,
    author_name: 'Прораб',
    author_role: 'prorab',
    photo_url: photoUrl,
    text: '',
  },
  user: {name: 'Директор'},
  C: {
    accent: '#2563eb',
    bg: '#f8fafc',
    bgWhite: '#ffffff',
    border: '#e2e8f0',
    danger: '#dc2626',
    text: '#0f172a',
    textMuted: '#64748b',
  },
  roleColor: () => '#2563eb',
  fileSrc: value => 'https://api.test' + value,
  setShowPhotoModal: jest.fn(),
  ...overrides,
});


describe('CompanyChatMessageBubble protected photo preview', () => {
  const originalFetch = global.fetch;
  const originalCreateObjectUrl = global.URL.createObjectURL;
  const originalRevokeObjectUrl = global.URL.revokeObjectURL;

  beforeEach(() => {
    global.fetch = jest.fn();
    global.URL.createObjectURL = jest.fn(() => 'blob:company-chat-photo');
    global.URL.revokeObjectURL = jest.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    if (originalCreateObjectUrl) global.URL.createObjectURL = originalCreateObjectUrl;
    else delete global.URL.createObjectURL;
    if (originalRevokeObjectUrl) global.URL.revokeObjectURL = originalRevokeObjectUrl;
    else delete global.URL.revokeObjectURL;
  });

  it('loads a protected message photo and opens the resolved Blob URL', async () => {
    const blob = new Blob(['protected-photo'], {type: 'image/png'});
    global.fetch.mockResolvedValue({ok: true, blob: async () => blob});
    const props = buildProps('/tenant-files/41/content');
    const {unmount} = render(<CompanyChatMessageBubble {...props}/>);

    expect(screen.getByLabelText('Фото загружается')).toBeInTheDocument();
    const image = await screen.findByRole('img', {name: 'Фото в сообщении'});
    expect(image).toHaveAttribute('src', 'blob:company-chat-photo');
    expect(global.fetch).toHaveBeenCalledWith(
      'https://api.test/tenant-files/41/content',
      expect.objectContaining({credentials: 'include'}),
    );

    fireEvent.click(image);
    expect(props.setShowPhotoModal).toHaveBeenCalledWith('blob:company-chat-photo');

    unmount();
    expect(global.URL.revokeObjectURL).toHaveBeenCalledWith('blob:company-chat-photo');
  });

  it('fails closed when a protected message photo is forbidden', async () => {
    global.fetch.mockResolvedValue({ok: false, status: 403});
    const props = buildProps('/tenant-files/42/content');
    render(<CompanyChatMessageBubble {...props}/>);

    await waitFor(() => expect(screen.getByLabelText('Не удалось загрузить фото')).toBeInTheDocument());
    expect(screen.queryByRole('img', {name: 'Фото в сообщении'})).not.toBeInTheDocument();
    expect(props.setShowPhotoModal).not.toHaveBeenCalled();
  });

  it('keeps a compatibility photo direct without a Blob request', () => {
    const props = buildProps('/uploads/company-1/chat-photo.png');
    render(<CompanyChatMessageBubble {...props}/>);

    const image = screen.getByRole('img', {name: 'Фото в сообщении'});
    expect(image).toHaveAttribute('src', 'https://api.test/uploads/company-1/chat-photo.png');
    expect(global.fetch).not.toHaveBeenCalled();

    fireEvent.click(image);
    expect(props.setShowPhotoModal).toHaveBeenCalledWith('https://api.test/uploads/company-1/chat-photo.png');
  });
});

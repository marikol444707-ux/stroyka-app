import {fireEvent, render, waitFor} from '@testing-library/react';

import FloatingCompanyChatPanel from './FloatingCompanyChatPanel';


const renderPanel = (overrides = {}) => {
  const props = {
    showChatPanel: true,
    setShowChatPanel: jest.fn(),
    companyMessages: [],
    user: {name: 'Директор'},
    companyChatInput: 'Не потерять этот текст',
    setCompanyChatInput: jest.fn(),
    sendCompanyChatMessage: jest.fn().mockResolvedValue(true),
    uploadPhoto: jest.fn(),
    ...overrides,
  };
  return {props, ...render(<FloatingCompanyChatPanel {...props}/>)};
};


describe('FloatingCompanyChatPanel company isolation', () => {
  test('keeps the draft when message delivery fails', async () => {
    const {props, getByPlaceholderText} = renderPanel({
      sendCompanyChatMessage: jest.fn().mockResolvedValue(false),
    });

    fireEvent.keyDown(getByPlaceholderText('Сообщение...'), {key: 'Enter'});

    await waitFor(() => expect(props.sendCompanyChatMessage).toHaveBeenCalledWith('Не потерять этот текст', ''));
    expect(props.setCompanyChatInput).not.toHaveBeenCalledWith('');
  });

  test('uploads a protected company-level photo outside any open project', async () => {
    const uploadPhoto = jest.fn().mockResolvedValue('/tenant-files/71/content');
    const {container, props} = renderPanel({uploadPhoto});
    const file = new File(['photo'], 'chat.jpg', {type: 'image/jpeg'});

    fireEvent.change(container.querySelector('input[accept="image/*"]'), {
      target: {files: [file]},
    });

    await waitFor(() => expect(uploadPhoto).toHaveBeenCalledWith(file, {
      context: 'company-chat',
      preferProtectedUrl: true,
      projectScoped: false,
    }));
    expect(props.sendCompanyChatMessage).toHaveBeenCalledWith('[Фото]', '/tenant-files/71/content');
  });
});

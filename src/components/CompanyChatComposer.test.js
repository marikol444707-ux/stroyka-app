import {fireEvent, render, waitFor} from '@testing-library/react';

import CompanyChatComposer from './CompanyChatComposer';

describe('CompanyChatComposer', () => {
  test('uploads chat photos as company-level files', async () => {
    const uploadPhoto = jest.fn().mockResolvedValue('/uploads/chat.jpg');
    const sendCompanyChatMessage = jest.fn();
    const {container} = render(
      <CompanyChatComposer
        C={{border: '#ccc', bgWhite: '#fff', bgGray: '#eee', textSec: '#333'}}
        inp={{}}
        btnO={{}}
        companyChatMessage=""
        setCompanyChatMessage={jest.fn()}
        uploadPhoto={uploadPhoto}
        sendCompanyChatMessage={sendCompanyChatMessage}
      />,
    );
    const file = new File(['photo'], 'chat.jpg', {type: 'image/jpeg'});

    fireEvent.change(container.querySelector('input[type="file"]'), {
      target: {files: [file]},
    });

    await waitFor(() => expect(uploadPhoto).toHaveBeenCalledWith(file, {
      context: 'company-chat',
      projectScoped: false,
    }));
    expect(sendCompanyChatMessage).toHaveBeenCalledWith('', '/uploads/chat.jpg');
  });
});

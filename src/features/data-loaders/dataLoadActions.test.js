import { createDataLoadActions } from './dataLoadActions';

describe('createDataLoadActions', () => {
  const originalFetch = window.fetch;

  afterEach(() => {
    window.fetch = originalFetch;
    jest.restoreAllMocks();
  });

  it('loads the authenticated worker profile and opens incomplete profile form', async () => {
    const setMasterProfile = jest.fn();
    const setShowProfileForm = jest.fn();
    window.fetch = jest.fn().mockResolvedValue(new Response(JSON.stringify({
      id: 17,
      profileCompleted: false,
    }), { status: 200 }));

    const actions = createDataLoadActions({
      API: '/api',
      setChecklistItems: jest.fn(),
      setMasterProfile,
      setPricelistItems: jest.fn(),
      setProjectChatMessages: jest.fn(),
      setShowProfileForm,
      user: { id: 17 },
    });

    await actions.loadMasterProfile();

    expect(window.fetch).toHaveBeenCalledWith('/api/master-profile/17');
    expect(setMasterProfile).toHaveBeenCalledWith({ id: 17, profileCompleted: false });
    expect(setShowProfileForm).toHaveBeenCalledWith(true);
  });

  it('stores an empty project chat list when the endpoint response is malformed', async () => {
    const setProjectChatMessages = jest.fn(updater => updater({ Existing: [{ id: 1 }] }));
    window.fetch = jest.fn().mockResolvedValue(new Response('{"detail":"bad payload"}', { status: 200 }));

    const actions = createDataLoadActions({
      API: '/api',
      setChecklistItems: jest.fn(),
      setMasterProfile: jest.fn(),
      setPricelistItems: jest.fn(),
      setProjectChatMessages,
      setShowProfileForm: jest.fn(),
      user: { id: 17 },
    });

    await actions.loadProjectChat('Объект № 1');

    expect(window.fetch).toHaveBeenCalledWith('/api/project-chat/%D0%9E%D0%B1%D1%8A%D0%B5%D0%BA%D1%82%20%E2%84%96%201');
    const nextState = setProjectChatMessages.mock.results[0].value;
    expect(nextState).toEqual({ Existing: [{ id: 1 }], 'Объект № 1': [] });
  });
});

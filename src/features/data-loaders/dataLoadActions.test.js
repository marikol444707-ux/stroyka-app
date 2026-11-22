import {createDataLoadActions, projectChatCacheKey, projectChatFeed} from './dataLoadActions';

describe('project chat cache', () => {
  test('keeps the same project name separate for two companies', () => {
    const cache = {
      [projectChatCacheKey(7, 'Лицей')]: [{id: 1, text: 'компания A'}],
    };
    expect(projectChatFeed(cache, 7, 'Лицей').messages).toEqual([{id: 1, text: 'компания A'}]);
    expect(projectChatFeed(cache, 8, 'Лицей')).toEqual({
      key: '8:Лицей',
      messages: [],
      loaded: false,
    });
    expect(projectChatCacheKey(null, 'Лицей')).toBe('');
  });

  test('stores a loaded feed under the selected company', async () => {
    const saved = [];
    global.fetch = jest.fn().mockResolvedValue({
      json: async () => [{id: 4, text: 'компания B'}],
    });
    const {loadProjectChat} = createDataLoadActions({
      API: '',
      companyId: 8,
      setChecklistItems: jest.fn(),
      setMasterProfile: jest.fn(),
      setPricelistItems: jest.fn(),
      setProjectChatMessages: updater => saved.push(updater({})),
      setShowProfileForm: jest.fn(),
      user: {id: 1},
    });
    await loadProjectChat('Лицей');
    expect(saved[0]).toEqual({'8:Лицей': [{id: 4, text: 'компания B'}]});
    expect(saved[0]['Лицей']).toBeUndefined();
  });
});

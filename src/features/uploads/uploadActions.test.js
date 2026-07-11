import { createUploadActions } from './uploadActions';


describe('upload actions project identity', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  test('sends projectId when the project name has one exact match', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      json: async () => ({ url: '/files/10' }),
    });
    const actions = createUploadActions({
      API: '',
      activePage: 'projects',
      activeProjectTab: 'documents',
      expandedProject: '',
      masterProjectId: '',
      projects: [{ id: 17, name: 'Лицей' }],
    });

    await actions.uploadPhoto(new File(['photo'], 'photo.jpg', { type: 'image/jpeg' }), {
      projectName: 'Лицей',
      context: 'project-documents',
    });

    const request = global.fetch.mock.calls[0][1];
    expect(request.body.get('projectName')).toBe('Лицей');
    expect(request.body.get('projectId')).toBe('17');
  });

  test('does not guess projectId for a non-project or duplicate name', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      json: async () => ({ url: '/files/11' }),
    });
    const actions = createUploadActions({
      API: '',
      activePage: 'crm',
      activeProjectTab: '',
      expandedProject: '',
      masterProjectId: '',
      projects: [{ id: 21, name: 'Дубль' }, { id: 22, name: 'Дубль' }],
    });

    await actions.uploadPhoto(new File(['doc'], 'doc.pdf', { type: 'application/pdf' }), {
      projectName: 'CRM',
      context: 'crm-documents',
    });
    const crmRequest = global.fetch.mock.calls[0][1];
    expect(crmRequest.body.get('projectId')).toBeNull();

    await actions.uploadPhoto(new File(['doc'], 'doc.pdf', { type: 'application/pdf' }), {
      projectName: 'Дубль',
      context: 'project-documents',
    });
    const duplicateRequest = global.fetch.mock.calls[1][1];
    expect(duplicateRequest.body.get('projectId')).toBeNull();
  });

  test('keeps a company-level upload outside the previously opened project', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      json: async () => ({url: '/files/company-chat'}),
    });
    const actions = createUploadActions({
      API: '',
      activePage: 'companychat',
      activeProjectTab: 'documents',
      expandedProject: 17,
      masterProjectId: 17,
      projects: [{id: 17, name: 'Лицей'}],
    });

    await actions.uploadPhoto(new File(['photo'], 'chat.jpg', {type: 'image/jpeg'}), {
      context: 'company-chat',
      projectScoped: false,
    });

    const request = global.fetch.mock.calls[0][1];
    expect(request.body.get('context')).toBe('company-chat');
    expect(request.body.get('projectName')).toBeNull();
    expect(request.body.get('projectId')).toBeNull();
  });

  test('returns protected content URL only for explicitly migrated consumers', async () => {
    global.fetch = jest.fn()
      .mockResolvedValueOnce({
        json: async () => ({
          url: '/uploads/company-4/file.pdf',
          contentUrl: '/tenant-files/31/content',
        }),
      })
      .mockResolvedValueOnce({
        json: async () => ({
          url: '/uploads/company-4/file.pdf',
          contentUrl: '/tenant-files/32/content',
        }),
      })
      .mockResolvedValueOnce({
        json: async () => ({url: '/uploads/company-4/legacy.pdf'}),
      });
    const actions = createUploadActions({
      API: '',
      activePage: 'projects',
      activeProjectTab: 'letters',
      expandedProject: '',
      masterProjectId: '',
      projects: [{id: 17, name: 'Лицей'}],
    });
    const file = new File(['letter'], 'letter.pdf', {type: 'application/pdf'});

    const compatibilityUrl = await actions.uploadPhoto(file, {projectId: 17});
    const protectedUrl = await actions.uploadPhoto(file, {projectId: 17, preferProtectedUrl: true});
    const protectedFallback = await actions.uploadPhoto(file, {projectId: 17, preferProtectedUrl: true});

    expect(compatibilityUrl).toBe('/uploads/company-4/file.pdf');
    expect(protectedUrl).toBe('/tenant-files/32/content');
    expect(protectedFallback).toBe('/uploads/company-4/legacy.pdf');
  });
});

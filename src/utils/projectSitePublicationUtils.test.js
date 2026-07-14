import {
  isProjectSitePublicationReady,
  projectSitePublicationDraft,
  projectSitePublicationPayload,
} from './projectSitePublicationUtils';

test('does not copy an internal project name into public fields', () => {
  const project = { id: 7, name: 'ул. Частная, заказчик Иванов' };
  const draft = projectSitePublicationDraft(project, {});
  const payload = projectSitePublicationPayload(project, draft);

  expect(draft.publicTitle).toBe('');
  expect(payload.publicTitle).toBe('');
});

test('requires a public title and at least one public image', () => {
  expect(isProjectSitePublicationReady({ publicTitle: '', publicMainImageUrl: '' })).toEqual({
    ready: false,
    missing: ['публичное название', 'фото'],
  });
  expect(isProjectSitePublicationReady({
    publicTitle: 'Дом с террасой',
    publicOriginalImagesText: 'https://cdn.example.test/house.webp',
  })).toEqual({ ready: true, missing: [] });
});

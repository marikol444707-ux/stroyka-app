import { createProjectOperationActions } from './projectOperationActions';
import { createProjectMeasurementActions } from '../project-measurements/projectMeasurementActions';
import { recordMatchesProject } from '../../utils/roomMeasurementUtils';


afterEach(() => jest.restoreAllMocks());


test('a room save sends the exact project id with the name', async () => {
  global.fetch = jest.fn(async () => ({ok: true, json: async () => ({id: 9})}));
  const actions = createProjectOperationActions({
    API: '/api',
    newRoom: {project: 'Объект', projectId: 12, name: 'Кухня', roomType: 'Комната'},
    draftRoomWindows: [],
    draftRoomDoors: [],
    customRoomTypes: [],
    refreshData: jest.fn(async () => {}),
    setCustomRoomTypes: jest.fn(),
    setDraftRoomDoors: jest.fn(),
    setDraftRoomWindows: jest.fn(),
    setEditingItem: jest.fn(),
    setExpandedRoom: jest.fn(),
    setNewRoom: jest.fn(),
    setShowRoomForm: jest.fn(),
  });

  await actions.saveRoom();

  const body = JSON.parse(global.fetch.mock.calls[0][1].body);
  expect(body.project).toBe('Объект');
  expect(body.projectId).toBe(12);
});


test('a measurement source save sends the exact project id', async () => {
  global.fetch = jest.fn(async () => ({ok: true, json: async () => ({})}));
  const actions = createProjectMeasurementActions({
    API: '/api',
    newMeasurementDoc: {title: 'Обмер', fileUrl: '', photoUrl: '', roomsCreated: 0},
    project: {id: 12, name: 'Объект'},
    refreshData: jest.fn(async () => {}),
    setMeasurementDraftLoadingId: jest.fn(),
    setNewMeasurementDoc: jest.fn(),
    setShowMeasurementForm: jest.fn(),
    user: {name: 'Директор'},
  });

  await actions.saveMeasurement();

  const body = JSON.parse(global.fetch.mock.calls[0][1].body);
  expect(body.projectName).toBe('Объект');
  expect(body.projectId).toBe(12);
});


test('same project name in two companies stays on its own project id', () => {
  const first = {id: 12, name: 'Объект'};
  const second = {id: 13, name: 'Объект'};
  const room = {id: 1, project: 'Объект', projectId: 12};
  expect(recordMatchesProject(room, first)).toBe(true);
  expect(recordMatchesProject(room, second)).toBe(false);
});

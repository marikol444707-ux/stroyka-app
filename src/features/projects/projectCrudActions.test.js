import { createProjectCrudActions } from './projectCrudActions';

test('project creation does not create a second account or submit old password fields', async () => {
  const props = {
    API:'/api',newProject:{name:'Object',budget:0,clientEmail:'old@example.test',clientPassword:'old-secret'},
    readApiResult:async response=>response.json(),notify:jest.fn(),refreshData:jest.fn(),addActivity:jest.fn(),
    setNewProject:jest.fn(),setEditingItem:jest.fn(),setShowForm:jest.fn(),
  };
  global.fetch=jest.fn(async()=>({ok:true,json:async()=>({id:1,companyId:7,name:'Object'})}));
  await createProjectCrudActions(props).saveProject();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][0]).toBe('/api/projects');
  const body=JSON.parse(fetch.mock.calls[0][1].body);
  expect(body.clientEmail).toBeUndefined();expect(body.clientPassword).toBeUndefined();
  expect(props.setShowForm).toHaveBeenCalledWith(false);
});

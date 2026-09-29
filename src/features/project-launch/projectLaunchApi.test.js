import { fetchProjectLaunchReadiness, fetchProjectLaunchDrafts, createProjectLaunchDraft, rejectProjectLaunchDraft } from './projectLaunchApi';
const project={id:11,companyId:7,name:'Same'};
beforeEach(()=>{global.fetch=jest.fn(async()=>({ok:true,json:async()=>({items:[],draft:{id:1},readiness:{}})}));});
test('all launch calls carry the selected project company, independent of profile default',async()=>{
 await fetchProjectLaunchReadiness('/api',project);
 await fetchProjectLaunchDrafts('/api',project);
 await createProjectLaunchDraft('/api',{projectName:'Same'},project);
 await rejectProjectLaunchDraft('/api',1,'Reason',project);
 for(const [,options] of fetch.mock.calls) expect(options.headers).toMatchObject({'X-Company-Id':'7','X-Company-Mode':'company'});
 expect(fetch.mock.calls[0][0]).toContain('project_id=11');
 expect(JSON.parse(fetch.mock.calls[2][1].body)).toMatchObject({projectId:11,projectName:'Same'});
});
test('missing project ownership never falls back to the default company',async()=>{
 await expect(fetchProjectLaunchDrafts('/api',{id:11,name:'Same'})).rejects.toThrow();
 expect(fetch).not.toHaveBeenCalled();
});

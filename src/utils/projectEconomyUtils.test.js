import {buildProjectEconomy, projectExpenseCategories, projectAccountableSummary, projectRealProgressValue, projectBudgetSpentSummary} from './projectEconomyUtils';
import {ks2ItemsFromActiveEstimates} from './projectEstimateItemsUtils';
import {buildMaterialControlSummary, buildMaterialReconciliationRows} from './materialReconciliationUtils';
const project={name:'Объект',budget:1000};
const estimate={id:10,sections:[{name:'Работы',items:[{itemType:'work',name:'Сетка',unit:'м²',quantity:5841,priceWork:1,doneQuantity:4944}]}]};
const journal=[{project:project.name,estimateItemKey:'10:0:0',quantity:4930,status:'Подтверждено',customerTotal:4930,executionTotal:2465},{project:project.name,estimateItemKey:'10:0:0',quantity:14,status:'На проверке',customerTotal:14}];
test('customer closure matches KS2, excludes pending imported quantity',()=>{
 const result=buildProjectEconomy({project,projectPlanDone:()=>({plan:5841,done:4944}),activeEstimatesForProject:()=>[estimate],workJournal:journal});
 expect(result.customerClosed).toBe(4930);
 expect(result.customerClosed).toBe(ks2ItemsFromActiveEstimates({project,activeEstimates:[estimate],workJournal:journal}).reduce((s,r)=>s+r.total,0));
});
test('pending-only linked journal has no closed amount',()=>{
 expect(buildProjectEconomy({project,projectPlanDone:()=>({plan:5841,done:4944}),activeEstimatesForProject:()=>[estimate],workJournal:journal.slice(1)}).customerClosed).toBe(0);
});
test('unlinked legacy estimate fallback remains exactly the KS2 amount',()=>{
 const options={project,activeEstimates:[estimate],workJournal:[]};
 expect(buildProjectEconomy({project,activeEstimatesForProject:()=>[estimate]}).customerClosed).toBe(ks2ItemsFromActiveEstimates(options).reduce((s,r)=>s+r.total,0));
});
test('without estimate only confirmed journal closes, never planDone maximum',()=>{
 expect(buildProjectEconomy({project,projectPlanDone:()=>({plan:0,done:9999}),workJournal:journal}).customerClosed).toBe(4930);
});
test('accountable summary separates issued funds from expense and excludes other projects',()=>{
 const payments=[{projectName:'Объект',amount:10000,spentAmount:2000},{projectName:'Другой',amount:50000,spentAmount:50000}];
 expect(projectAccountableSummary(project.name,payments)).toEqual({issued:10000,spent:2000});
 expect(projectExpenseCategories({project,projectName:project.name,accountablePayments:payments}).accountable).toBe(2000);
});
test('unspent advance contributes no category cost',()=>expect(projectExpenseCategories({project,projectName:project.name,accountablePayments:[{projectName:project.name,amount:10000,spentAmount:0}]}).accountable).toBe(0));
test.each([[undefined,0],[0,0],[35,35],[200,100],[-10,0],['bad',0]])('without estimate uses only stored card progress %s', (progress, expected)=>{
 const fact=jest.fn(()=>({total:200}));
 expect(projectRealProgressValue({project:{...project,progress},projectFactSpent:fact})).toBe(expected);expect(fact).not.toHaveBeenCalled();
});
test('estimate-backed progress remains supported',()=>expect(projectRealProgressValue({project,projectPlanDone:()=>({plan:1000,done:300})})).toBe(30));

test.each([[{}, {}, 'Прогресс не указан'], [{progress:0},{},'Из карточки объекта'], [{progress:25},{},'Из карточки объекта'], [{progress:null},{},'Прогресс не указан'], [{progress:12},{plan:100},'По смете']])('labels progress source separately from numeric fallback', (p, plan, expected)=> {
 const {projectProgressSourceLabel}=require('./projectEconomyUtils');
 expect(projectProgressSourceLabel(p,plan)).toBe(expected);
});

test.each([[4, 400], [0, 0], [10, 1000]])('accepted material cost reaches project margin without rewriting supplier invoice (%s)', (receivedQuantity, expectedCost) => {
 const supplierInvoice = Object.freeze({id: 71, amount: 1000, paidAmount: 200, status: 'Частично оплачен'});
 const delivery = Object.freeze({id: 81, project: project.name, materialName: 'Кабель', unit: 'м',
   status: 'Проблема', plannedQuantity: 10, shippedQuantity: 10, receivedQuantity, pricePerUnit: 100, totalPrice: 1000});
 const rows = buildMaterialReconciliationRows({project, supplyDeliveries: [delivery],
   activeEstimatesForProject: () => [], canonicalMaterialMeta: (_project, name, unit) => ({name, unit}),
   warehouseInvoiceItems: invoice => ({items: invoice.items || []}), isSupplyDeliveryInvoice: () => false,
   estimateWorkNormRequirementRows: () => [], parseSupplyItems: () => []});
 const materialControlSummaryForProject = () => buildMaterialControlSummary(rows);
 const categories = projectExpenseCategories({project, projectName: project.name, materialControlSummaryForProject});
 const spent = projectBudgetSpentSummary(project, categories);
 const economy = buildProjectEconomy({project, projectPlanDone: () => ({plan: 2000, done: 0}),
   materialControlSummaryForProject, projectBudgetSpent: () => spent,
   workJournal: [{project: project.name, status: 'Подтверждено', customerTotal: 1500, executionTotal: 0}]});
 expect(categories.materials).toBe(expectedCost);
 expect(spent.materials).toBe(expectedCost);
 expect(economy).toMatchObject({materialCost: expectedCost, marginClosed: 1500 - expectedCost, marginForecast: 2000 - expectedCost});
 expect(delivery.totalPrice).toBe(1000);
 expect(supplierInvoice).toEqual({id: 71, amount: 1000, paidAmount: 200, status: 'Частично оплачен'});
});

import assert from 'node:assert/strict';
import * as THREE from 'three';
import {roofSchemes} from './roof-schemes.js';
import {buildRoofStudy} from './roof-study-model.js';
import {materials,makeProjectBrief} from './materials-data.js';
const ids=materials.filter(m=>m.category==='roof').map(m=>m.id);assert.deepEqual(Object.keys(roofSchemes),ids);assert.equal(ids.length,3);const shapes=[];
for(const id of ids){
 const spec=roofSchemes[id];for(const key of ['scale','thickness','pitch','thermalValue','price'])assert.equal(spec[key],null);assert.equal(spec.reviewStatus,'draft');
 const model=buildRoofStudy(id);let meshes=0,vertices=0;model.roles.core.traverse(o=>{if(o.isMesh){meshes++;vertices+=o.geometry.attributes.position.count;const a=o.geometry.attributes.position.array;assert(Array.from(a).every(Number.isFinite),'Finite actual geometry');}});shapes.push([id,meshes,vertices]);
 for(const key of ['base','protection'])assert(model.roles[key].children.every(o=>o.isLine),'No unapproved sheathing or membrane filled in');
 assert.equal(model.roles.structure.children.length,5);const before=Object.fromEntries(Object.entries(model.roles).map(([k,g])=>[k,g.position.y]));model.spread(1);
 assert(model.roles.core.position.y>model.roles.base.position.y&&model.roles.base.position.y>model.roles.protection.position.y&&model.roles.protection.position.y>model.roles.structure.position.y,'Ordered disassembly');assert(model.roles.core.position.y>before.core);
 model.spread(0);for(const [key,g] of Object.entries(model.roles))assert.equal(g.position.y,before[key],'Original assembly positions');
 const gs=new Set(),ms=new Set();model.root.traverse(o=>{if(o.geometry)gs.add(o.geometry);if(o.material)ms.add(o.material);});let dg=0,dm=0;for(const g of gs)g.addEventListener('dispose',()=>dg++);for(const m of ms)m.addEventListener('dispose',()=>dm++);model.dispose();assert.equal(dg,gs.size);assert.equal(dm,ms.size);
 const brief=makeProjectBrief({wall:'brick',roof:id});assert(brief.includes('Стены: Кирпич — пожелание'));assert(brief.includes(materials.find(m=>m.id===id).title+' — пожелание'));
}
assert.equal(new Set(shapes.map(s=>s.slice(1).join(':'))).size,3,'Three distinct shapes');
console.log(JSON.stringify({passed:true,shapes,checks:['three actual cover geometries','finite geometry','ordered disassembly and exact reassembly','empty base and underlay placeholders','no invented pitch/thickness/thermal values/price','category-safe preferences','all attached resources released']},null,2));

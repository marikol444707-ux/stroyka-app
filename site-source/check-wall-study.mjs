import assert from 'node:assert/strict';
import * as THREE from 'three';
import {wallSchemes} from './wall-schemes.js';
import {buildWallStudy} from './wall-study-model.js';
import {materials} from './materials-data.js';
const ids=materials.filter(m=>m.category==='wall').map(m=>m.id);assert.deepEqual(Object.keys(wallSchemes),ids);
const shapes=[];
for(const id of ids){
 const s=wallSchemes[id];for(const key of ['scale','thickness','thermalValue','price'])assert.equal(s[key],null);assert.equal(s.reviewStatus,'draft');
 const model=buildWallStudy(id);let meshes=0,vertices=0;const geometries=new Set(),mats=new Set();model.root.traverse(o=>{if(o.geometry)geometries.add(o.geometry);if(o.material)mats.add(o.material);});
 model.roles.core.traverse(o=>{if(o.isMesh){meshes++;vertices+=o.geometry.attributes.position.count;}});shapes.push([id,meshes,vertices]);
 assert(meshes>0);assert(model.roles.outside.children.every(o=>o.isLine),'No guessed exterior material');
 const positions=Object.fromEntries(Object.entries(model.roles).map(([k,g])=>[k,g.position.clone()]));model.spread(1);assert(model.roles.inside.position.z<positions.inside.z);assert(model.roles.outside.position.z>positions.outside.z);assert.deepEqual(model.roles.core.position.toArray(),positions.core.toArray());model.spread(0);for(const [k,g] of Object.entries(model.roles))assert(g.position.equals(positions[k]),'Reassembly restores role '+k);
 const bounds=new THREE.Box3().setFromObject(model.roles.core);assert(bounds.min.y>=-.01&&bounds.max.y<=2.61&&bounds.min.x>=-1.81&&bounds.max.x<=1.81,'Core geometry bounds');
 if(id==='ceramic')assert(model.roles.core.children[0].geometry.parameters.shapes.holes.length===10,'Actual hollow shape');
 if(id==='concrete')assert(model.roles.core.children.some(o=>o.geometry.type==='CylinderGeometry'),'Actual reinforcing rods');
 if(id==='frame')assert(new Set(model.roles.core.children.map(o=>o.material)).size>=2,'Frame and filling are separate geometry/materials');
 let disposedG=0,disposedM=0;for(const g of geometries)g.addEventListener('dispose',()=>disposedG++);for(const m of mats)m.addEventListener('dispose',()=>disposedM++);model.dispose();assert.equal(disposedG,geometries.size);assert.equal(disposedM,mats.size);
}
assert(new Set(shapes.map(s=>s.slice(1).join(':'))).size===ids.length,'Different shapes, not paint variants');
console.log(JSON.stringify({passed:true,shapes,checks:['five distinct core geometries','actual ceramic voids and reinforcement','unfilled exterior placeholder','draft with no dimensions/prices/thermal values','disassembly and reassembly positions','all geometry/material resources released']},null,2));

import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {buildHouseRoof,createHouseRoof,makeRoofMaterial,roofLooks} from './house-roof.js';
const stats=[];
for(const id of Object.keys(roofLooks)){
 const m=buildHouseRoof(id),box=new THREE.Box3().setFromObject(m.root);let triangles=0;
 assert(Math.abs(box.min.x+7.7)<.001&&Math.abs(box.max.x-7.7)<.001);assert(box.min.y>3.1&&box.max.y<4.9);assert(box.min.z< -5.49&&box.max.z>5.49);
 m.root.traverse(o=>{if(!o.isMesh)return;const g=o.geometry,p=g.attributes.position,n=g.attributes.normal;assert(Array.from(p.array).every(Number.isFinite));assert(Array.from(n.array).every(Number.isFinite));triangles+=(g.index?.count||p.count)/3;
 const index=g.index;let upward=0,total=0;for(let k=0;k<(index?.count||p.count);k+=3){const a=index?index.getX(k):k,b=index?index.getX(k+1):k+1,c=index?index.getX(k+2):k+2;const v1=new THREE.Vector3().fromBufferAttribute(p,b).sub(new THREE.Vector3().fromBufferAttribute(p,a)),v2=new THREE.Vector3().fromBufferAttribute(p,c).sub(new THREE.Vector3().fromBufferAttribute(p,a));const area=v1.cross(v2).length();if(area>1e-10){total+=area;if((n.getY(a)+n.getY(b)+n.getY(c))/3>0)upward+=area;}}assert(total>0,'Nonempty surface area');if(!o.name.startsWith('visual perimeter'))assert(upward/total>.45,'Cover has outward upward-facing surface area');});
 const geometries=new Set(),materials=new Set();m.root.traverse(o=>{if(o.geometry)geometries.add(o.geometry);if(o.material)materials.add(o.material);});let gd=0,md=0;for(const g of geometries)g.addEventListener('dispose',()=>gd++);for(const mat of materials)mat.addEventListener('dispose',()=>md++);m.dispose();assert.equal(gd,geometries.size);assert.equal(md,materials.size);stats.push({id,triangles});
}
assert.equal(new Set(stats.map(s=>s.triangles)).size,3);
// Read the genuine GLB; omit only its images in this Node-only geometry test.
// Browsers below load the unmodified GLB with the actual textures.
const file=fs.readFileSync(new URL('./stroyka-polished.glb',import.meta.url)),jsonLength=file.readUInt32LE(12),doc=JSON.parse(file.subarray(20,20+jsonLength).toString());delete doc.images;delete doc.textures;
for(const m of doc.materials){delete m.normalTexture;delete m.occlusionTexture;delete m.emissiveTexture;if(m.pbrMetallicRoughness){delete m.pbrMetallicRoughness.baseColorTexture;delete m.pbrMetallicRoughness.metallicRoughnessTexture;}}
let json=Buffer.from(JSON.stringify(doc));json=Buffer.concat([json,Buffer.alloc((4-json.length%4)%4,32)]);const bin=file.subarray(20+jsonLength);const packed=Buffer.alloc(20+json.length+bin.length);packed.writeUInt32LE(0x46546c67);packed.writeUInt32LE(2,4);packed.writeUInt32LE(packed.length,8);packed.writeUInt32LE(json.length,12);packed.writeUInt32LE(0x4e4f534a,16);json.copy(packed,20);bin.copy(packed,20+json.length);
const gltf=await new GLTFLoader().parseAsync(packed.buffer.slice(packed.byteOffset,packed.byteOffset+packed.byteLength),'');
const house=gltf.scene,roof=house.getObjectByName('05_roof'),originalChildren=roof.children.length;let geometryDisposed=0,textureDisposed=0;
const controller=createHouseRoof(house,{makeMaterial:(id,spec)=>{const mat=makeRoofMaterial(id,spec);for(const t of mat.userData.ownedTextures)t.addEventListener('dispose',()=>textureDisposed++);return mat;}});
for(const id of [...Object.keys(roofLooks),'metal-tile',null]){controller.select(id);const state=controller.audit();assert.equal(state.id,id||'standing-seam');assert.equal(state.preference,id);assert(state.sourceCoverHidden);assert(state.guttersVertices>0);assert.equal(roof.children.length,originalChildren+2,'No variant accumulation');house.traverse(o=>o.visible=true);controller.enforce();assert(controller.audit().sourceCoverHidden);}
assert(textureDisposed>=4,'Obsolete textures released');roof.position.y=5.1;house.updateMatrixWorld(true);const moved=new THREE.Box3().setFromObject(roof.getObjectByName('selected roof envelope'));assert(moved.min.y>8.2,'Selected cover follows existing exploded roof parent');controller.dispose();assert.equal(roof.children.length,originalChildren);assert(textureDisposed>=5);
const report={passed:true,stats,checks:['three genuinely different covers on both existing slopes','finite positions/normals and matching envelope','upward surface orientation','genuine GLB gutter extraction','source cover hidden after mode resets','default versus explicit preference','no variant/texture accumulation','cover follows existing roof explosion','owned geometry/material/texture disposal'],assemblyApproved:false};fs.writeFileSync('house-roof-model-check.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));

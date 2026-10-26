import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {createNavigator} from './walk-navigation.js';
async function load(filename){
const file=fs.readFileSync(new URL(filename,import.meta.url)),jsonLength=file.readUInt32LE(12),doc=JSON.parse(file.subarray(20,20+jsonLength).toString());delete doc.images;delete doc.textures;
for(const m of doc.materials){delete m.normalTexture;delete m.occlusionTexture;delete m.emissiveTexture;if(m.pbrMetallicRoughness){delete m.pbrMetallicRoughness.baseColorTexture;delete m.pbrMetallicRoughness.metallicRoughnessTexture;}}
let json=Buffer.from(JSON.stringify(doc));json=Buffer.concat([json,Buffer.alloc((4-json.length%4)%4,32)]);const bin=file.subarray(20+jsonLength);const packed=Buffer.alloc(20+json.length+bin.length);packed.writeUInt32LE(0x46546c67);packed.writeUInt32LE(2,4);packed.writeUInt32LE(packed.length,8);packed.writeUInt32LE(json.length,12);packed.writeUInt32LE(0x4e4f534a,16);json.copy(packed,20);bin.copy(packed,20+json.length);
const gltf=await new GLTFLoader().parseAsync(packed.buffer.slice(packed.byteOffset,packed.byteOffset+packed.byteLength),'');
return gltf.scene;}
const old=await load('./previous-house.glb'),house=await load('./stroyka-polished.glb');old.updateMatrixWorld(true);house.updateMatrixWorld(true);
function vertices(group){const rows=[];group.traverse(o=>{if(!o.isMesh)return;const p=o.geometry.attributes.position;for(let i=0;i<p.count;i++){const v=new THREE.Vector3().fromBufferAttribute(p,i).applyMatrix4(o.matrixWorld);rows.push([v.x,v.y,v.z].map(n=>Math.round(n*100000)).join(','));}});return rows.sort();}
const groups=['01_foundation','02_structure','03_walls','04_ceiling','05_roof','06_facade','09_wall_core','10_insulation','11_vent_gap','12_cladding','13_inner_finish','14_rafters','15_roof_underlay','16_roof_battens','17_site'];
for(const key of groups)assert.deepEqual(vertices(house.getObjectByName(key)),vertices(old.getObjectByName(key)),'Unchanged building geometry: '+key);
assert.notDeepEqual(vertices(house.getObjectByName('07_interior')),vertices(old.getObjectByName('07_interior')));
const nav=JSON.parse(fs.readFileSync(new URL('./navigation.json',import.meta.url)));assert.equal(nav.modelSha256,crypto.createHash('sha256').update(fs.readFileSync(new URL('./stroyka-polished.glb',import.meta.url))).digest('hex'));
const find=name=>nav.colliders.find(x=>x.name===name),center=c=>[0,1].map(i=>c.polygon.reduce((n,p)=>n+p[i],0)/c.polygon.length),back=center(find('sofa back')),seat=center(find('sofa cushion'));
assert(back[1]>seat[1]+.3,'Sofa faces coffee table');const table=center(find('coffee table')),foot=center(find('table foot'));assert(Math.hypot(table[0]-foot[0],table[1]-foot[1])<1e-4,'Coffee pedestal remains centered');assert(Math.abs(table[0]-4.8)<1e-4&&Math.abs(table[1]-2.15)<1e-4);
const gap=Math.min(...find('sofa base').polygon.map(p=>p[1]))-Math.max(...find('coffee table').polygon.map(p=>p[1]));assert(gap>.25&&gap<.55,'Actual visual sofa/table gap');
const backs=nav.colliders.filter(x=>x.name.startsWith('dining curved chair back'));assert.equal(backs.length,4);for(const c of backs)for(const p of c.polygon){assert(p[0]<6.85&&p[1]> -1.1,'Chairs clear exterior and service walls');}
assert.equal(nav.colliders.filter(x=>x.name.startsWith('bed soft duvet')).length,3);assert.equal(nav.colliders.filter(x=>x.name.startsWith('bed foot throw')).length,3);
const solver=createNavigator(nav);for(const point of [[2.65,2.65],[3.75,1.8],[-3.55,4.1]])assert(!solver.blocked(...point),'Updated viewpoint is clear');
const report={passed:true,buildingGroupsCompared:groups.length,colliders:nav.colliders.length,visualSofaTableGap:gap,modelSha256:nav.modelSha256,checks:['source building/window/door/roof/site geometry unchanged at 1e-5 resolution','interior geometry changed','navigation hash matches actual exported model','sofa faces table and pedestal follows tabletop','four curved chair backs stay inside building','three actual soft duvets and foot throws','new viewpoints clear of furniture'],ergonomicsApproved:false};fs.writeFileSync('furniture-model-check.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));

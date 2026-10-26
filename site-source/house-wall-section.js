import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';
import * as THREE from 'three';
import {buildWallStudy} from './wall-study-model.js';
import {wallSchemes} from './wall-schemes.js';
import {makeFacadeMaterials} from './house-facade.js';

// Reuse the existing educational bay only. Fitting a schematic into this
// envelope is not a material thickness, block dimension or structural design.
export function createHouseWallSection(house,{onChange=()=>{}}={}){
 const names=['09_wall_core','10_insulation','11_vent_gap','12_cladding'];
 const groups=Object.fromEntries(names.map(n=>[n,house.getObjectByName(n)]));
 if(names.some(n=>!groups[n]))throw Error('Existing educational wall bay missing');
 const originals=[];for(const group of Object.values(groups))group.traverse(o=>{if(o.isMesh)originals.push([o,o.visible]);});
 const coreSlot=new THREE.Group();coreSlot.name='selected core in existing house bay';coreSlot.userData.houseWallSection=true;groups['09_wall_core'].add(coreSlot);
 const cover=new THREE.Group();cover.name='movable selected bay finish';cover.userData.houseWallSection=true;groups['12_cladding'].add(cover);
 const frames=[];
 function frame(parent,x,color,name){
  const p=[[x,0,-2.1],[x,3,-2.1],[x,3,-.6],[x,0,-.6],[x,0,-2.1]].map(v=>new THREE.Vector3(...v));
  const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(p),new THREE.LineDashedMaterial({color,dashSize:.085,gapSize:.06}));line.name=name;line.userData.houseWallSection=true;line.computeLineDistances();parent.add(line);frames.push(line);return line;
 }
 const empty=frame(groups['09_wall_core'],7.07,0xa37d4d,'material not yet selected');
 const insulation=frame(groups['10_insulation'],7.09,0x9a946e,'insulation solution pending');
 const protection=frame(groups['11_vent_gap'],7.13,0x6c9b96,'moisture solution pending');
 const data=new Uint8Array(128*128*4);let seed=71;for(let i=0;i<data.length;i+=4){seed=(seed*1664525+1013904223)>>>0;const c=205+seed/4294967296*50;data[i]=data[i+1]=data[i+2]=c;data[i+3]=255;}
 const grain=new THREE.DataTexture(data,128,128);grain.wrapS=grain.wrapT=THREE.RepeatWrapping;grain.repeat.set(3,3);grain.magFilter=THREE.LinearFilter;grain.minFilter=THREE.LinearMipmapLinearFilter;grain.generateMipmaps=true;grain.needsUpdate=true;
 const surface=(color,roughness=.93)=>new THREE.MeshStandardMaterial({color,roughness,map:grain,bumpMap:grain,bumpScale:.0015});
 let model=null,materialId=null,facadeId=undefined,finishes=null,progress=0,target=0,motion=null,context='assembled';
 function clearCover(){for(const child of [...cover.children]){child.geometry.dispose();cover.remove(child);}finishes?.dispose();finishes=null;}
 function makeCover(id){
  if(id!==null&&!['plaster-facade','timber-facade'].includes(id))throw Error('Invalid facade finish');if(facadeId===id)return;facadeId=id;clearCover();const timber=id!=='plaster-facade';finishes=makeFacadeMaterials(timber?'timber-facade':'plaster-facade');
  function box(x,z,w,depth,material,shade=1){const g=new THREE.BoxGeometry(depth,3,w);const p=g.attributes.position,uv=g.attributes.uv;for(let i=0;i<p.count;i++)uv.setXY(i,p.getZ(i)+z,p.getY(i));g.setAttribute('color',new THREE.Float32BufferAttribute(Array.from({length:p.count*3},()=>shade),3));const m=new THREE.Mesh(g,material);m.position.set(x,1.5,z);m.castShadow=m.receiveShadow=true;cover.add(m);}
  if(timber){box(-.014,0,1.5,.006,finishes.recess);for(let i=0;i<11;i++)box(0,-.75+(i+.5)*1.5/11,1.5/11-.013,.035,finishes.finish,.87+.12*Math.abs(Math.sin(i*31.7)));}
  else box(0,0,1.5,.012,finishes.finish);
  batchCore(cover);applyProgress(progress);enforce();notify();
 }
 function batchCore(core){
  core.updateWorldMatrix(true,true);const grouped=new Map(),oldGeometry=new Set(),objects=[];
  core.traverse(o=>{if(!o.isMesh)return;objects.push(o);oldGeometry.add(o.geometry);const g=o.geometry.index?o.geometry.toNonIndexed():o.geometry.clone();g.applyMatrix4(new THREE.Matrix4().copy(core.matrixWorld).invert().multiply(o.matrixWorld));if(!grouped.has(o.material))grouped.set(o.material,[]);grouped.get(o.material).push(g);});
  for(const o of objects)o.removeFromParent();for(const g of oldGeometry)g.dispose();
  for(const [material,pieces] of grouped){const g=mergeGeometries(pieces,false);for(const p of pieces)p.dispose();if(!g)throw Error('Core batching failed');const m=new THREE.Mesh(g,material);m.castShadow=m.receiveShadow=true;core.add(m);}
 }
 function select(id){
  if(id!==null&&!wallSchemes[id])throw Error('Invalid wall material');
  if(materialId!==id){model?.dispose();model=null;materialId=id;if(id){model=buildWallStudy(id,{surface,dimensions:{width:1.5,height:3,depth:.16,gap:.008,bevel:.003,aeratedRows:12,aeratedCols:3,brickRows:36,brickCols:6,ceramicRows:12,ceramicCols:4,bar:.09,stud:.07,studCount:4}});batchCore(model.roles.core);model.root.position.set(6.98,0,-1.35);model.root.rotation.y=Math.PI/2;model.root.scale.set(1,1,1);coreSlot.add(model.root);}}
  enforce();notify();
 }
 function applyProgress(value){progress=THREE.MathUtils.clamp(value,0,1);cover.position.set(7.18+.9*progress,0,-1.35-2.4*progress);cover.rotation.y=.32*progress;house.updateMatrixWorld(true);notify();}
 function seek(value){motion=null;target=THREE.MathUtils.clamp(value,0,1);applyProgress(target);}
 function moveTo(value,reduced=false){value=THREE.MathUtils.clamp(value,0,1);target=value;if(reduced){motion=null;applyProgress(value);}else motion={from:progress,to:value,time:0};}
 function setContext(mode,{reduced=false}={}){context=mode;if(mode==='wall-section')moveTo(1,reduced);else seek(0);enforce();notify();}
 function enforce(){for(const [o] of originals)o.visible=false;if(model){model.roles.inside.visible=false;model.roles.outside.visible=false;}const teaching=['wall-section','wall','exploded'].includes(context);empty.visible=teaching&&!materialId;insulation.visible=protection.visible=teaching;}
 function audit(){let meshes=0,vertices=0;model?.roles.core.traverse(o=>{if(o.isMesh){meshes++;vertices+=o.geometry.attributes.position.count;}});return{material:materialId,title:materialId?wallSchemes[materialId].title:'Материал пока не выбран',facade:facadeId,context,progress,target,moving:!!motion,coreMeshes:meshes,coreVertices:vertices,sourceLayersHidden:originals.every(([o])=>!o.visible),assemblyApproved:false,thickness:null,scale:null,coverPosition:cover.position.toArray()};}
 function notify(){onChange(audit());}
 function update(dt,reduced=false){if(!motion)return;if(reduced){motion=null;applyProgress(target);return;}motion.time+=Math.min(.1,dt);const t=Math.min(1,motion.time/.9),ease=t*t*t*(t*(t*6-15)+10),from=motion.from,to=motion.to;if(t===1)motion=null;applyProgress(THREE.MathUtils.lerp(from,to,ease));}
 // Build the reference exterior without choosing a facade or core preference.
 makeCover(null);enforce();
 return{select,selectFacade:id=>makeCover(id||null),setContext,seek,moveTo,update,enforce,audit,dispose(){motion=null;model?.dispose();coreSlot.removeFromParent();clearCover();cover.removeFromParent();for(const line of frames){line.geometry.dispose();line.material.dispose();line.removeFromParent();}grain.dispose();for(const [o,v] of originals)o.visible=v;}};
}

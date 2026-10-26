import furnitureLayout from './furniture-layout.json' with {type:'json'};
import * as THREE from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';
// Decorative proposals on existing surfaces, not new layout or specified products.
export function createInteriorDetails(house){
 const root=new THREE.Group();root.name='interior surface and furniture details';house.getObjectByName('07_interior').add(root);
 const groups={},materials=new Set(),textures=new Set();let current='warm',disposed=false;
 function texture(kind){
  const size=128,data=new Uint8Array(size*size*4);let seed=701;
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
   seed=(Math.imul(seed,1664525)+1013904223)>>>0;const noise=seed/4294967296;
   const v=kind==='stone'?229+8*Math.sin(x*.13+y*.06+4*Math.sin(y*.03))+noise*8:kind==='linen'?199+((x%4===0||y%4===0)?-20:12)+noise*12:211+Math.sin(y*.27+Math.sin(x*.08))*9+noise*10;
   const i=(y*size+x)*4;data[i]=data[i+1]=data[i+2]=v;data[i+3]=255;
  }
  const t=new THREE.DataTexture(data,size,size,THREE.RGBAFormat);t.wrapS=t.wrapT=THREE.RepeatWrapping;t.minFilter=THREE.LinearMipmapLinearFilter;t.magFilter=THREE.LinearFilter;t.generateMipmaps=true;t.colorSpace=THREE.SRGBColorSpace;t.needsUpdate=true;textures.add(t);return t;
 }
 const dining=furnitureLayout.dining;
 const stone=texture('stone'),linen=texture('linen'),grain=texture('wood');linen.repeat.set(24,24);
 function mat(color,more={}){const m=new THREE.MeshStandardMaterial({color,roughness:.8,...more});materials.add(m);return m;}
 const schemes={
  warm:{base:0xc6aa7d,edge:0xa48657,stone:0xe6dcc8,rug:0xb6aa93,pottery:0x997b5d,metal:0x554a3f},
  minimal:{base:0xd9d4c7,edge:0xd1cec4,stone:0xece9df,rug:0xd3d1c5,pottery:0xc3c5ba,metal:0x777b72},
  classic:{base:0xd5c8b0,edge:0xb4a077,stone:0xd8cbb6,rug:0x8b9386,pottery:0xe7ddc9,metal:0xa28a53}
 };
 function mesh(g,geometry,material,name,x,y,z){const o=new THREE.Mesh(geometry,material);o.name=name;o.position.set(x,y,z);o.receiveShadow=true;o.castShadow=true;o.userData.interiorDecoration=true;g.add(o);return o;}
 function box(g,m,n,x,y,z,w,h,d){return mesh(g,new THREE.BoxGeometry(w,h,d),m,n,x,y,z);}
 for(const [id,c] of Object.entries(schemes)){
  const g=new THREE.Group();g.name='interior details '+id;groups[id]=g;root.add(g);
  const base=mat(c.base,{map:id==='warm'?grain:null}),edge=mat(c.edge),counter=mat(c.stone,{map:stone,bumpMap:stone,bumpScale:.001,roughness:id==='classic'?.35:.55}),rug=mat(c.rug,{map:linen,bumpMap:linen,bumpScale:.0015}),pottery=mat(c.pottery),metal=mat(c.metal,{metalness:.55,roughness:.4});
  // Thin finishes over the existing island and kitchen surfaces.
  box(g,counter,'island stone finish',2.1,1.014,.75,2.28,.018,.88);
  box(g,counter,'kitchen stone finish',1.8,.973,-.88,2.88,.018,.59);
  box(g,base,'island panel finish',2.1,.49,1.207,2.27,.88,.014);
  if(id==='warm')for(let i=0;i<68;i++)box(g,edge,'timber fluting',.994+i*.033,.49,1.22,.016,.86,.018);
  if(id==='minimal')for(const x of [1.72,2.48])box(g,edge,'quiet panel seam',x,.49,1.217,.005,.86,.004);
  if(id==='classic')for(const x of [1.37,2.1,2.83]){
   for(const y of [.14,.84])box(g,edge,'framed panel horizontal',x,y,1.224,.61,.021,.018);
   for(const dx of [-.305,.305])box(g,edge,'framed panel vertical',x+dx,.49,1.224,.021,.72,.018);
  }
  // A walkable textile surface: no object is introduced into the walking route.
  box(g,rug,'living textile rug',4.72,.069,3.22,3.32,.012,2.42).castShadow=false;
  for(const z of [2.08,4.36])box(g,edge,'rug woven border',4.72,.076,z,3.1,.002,.022).castShadow=false;
  // Every table object stays over the existing dining tabletop, within its footprint.
  for(const a of [Math.PI/4,Math.PI*.75,Math.PI*1.25,Math.PI*1.75]){
   const x=dining.x+Math.cos(a)*.38,z=dining.z+Math.sin(a)*.38;
   mesh(g,new THREE.CylinderGeometry(.15,.15,.013,28),counter,'ceramic place setting',x,.827,z);
   const ring=mesh(g,new THREE.TorusGeometry(.132,.004,4,28),metal,'plate edge',x,.836,z);ring.rotation.x=Math.PI/2;
  }
  const profile=[[0,0],[.095,0],[.12,.06],[.13,.18],[.083,.28],[.052,.3],[.052,.32]].map(([x,y])=>new THREE.Vector2(x,y));
  mesh(g,new THREE.LatheGeometry(profile,24),pottery,'ceramic dining vase',dining.x,.82,dining.z);
  const branchMat=mat(id==='warm'?0x64715a:id==='minimal'?0x838b7a:0x776d51);
  for(let i=0;i<3;i++){
   const x=dining.x+(i-1)*.09,z=dining.z+(i-1)*.055;
   const curve=new THREE.CatmullRomCurve3([new THREE.Vector3(dining.x,1.11,dining.z),new THREE.Vector3(x,1.29,z),new THREE.Vector3(x+.05,1.47-i*.07,z+.025)]);
   mesh(g,new THREE.TubeGeometry(curve,8,.004,4,false),branchMat,'botanical stem',0,0,0);
   for(let j=0;j<3;j++){
    const leaf=mesh(g,new THREE.SphereGeometry(1,8,5),branchMat,'botanical leaf',x+(j%2?.04:-.02),1.23+j*.065-i*.04,z+.01);leaf.scale.set(.055,.012,.022);leaf.rotation.z=(j%2?.5:-.4);
   }
  }
  // Batch decorations by material. Transform is baked only within the new group.
  g.updateMatrixWorld(true);const byMaterial=new Map();
  for(const o of [...g.children]){o.updateMatrix();const geo=o.geometry.clone().applyMatrix4(o.matrix);const record=byMaterial.get(o.material)||{geometries:[],names:[]};record.geometries.push(geo);record.names.push(o.name);byMaterial.set(o.material,record);o.geometry.dispose();g.remove(o);}
  for(const [m,record] of byMaterial){const geo=mergeGeometries(record.geometries);record.geometries.forEach(x=>x.dispose());const o=mesh(g,geo,m,'surface details '+id,0,0,0);o.userData.detailNames=record.names;}
 }
 function apply(id){if(!groups[id])throw Error('Unknown interior details');current=id;for(const [key,g] of Object.entries(groups))g.visible=key===id;}
 function audit(){return {style:current,groups:Object.fromEntries(Object.entries(groups).map(([id,g])=>[id,{visible:g.visible,meshes:g.children.length,vertices:g.children.reduce((n,o)=>n+o.geometry.attributes.position.count,0)}])),textures:textures.size,layoutChanged:false,productsApproved:false};}
 function dispose(){if(disposed)return;disposed=true;root.traverse(o=>o.geometry?.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());root.removeFromParent();}
 apply('warm');return {apply,audit,dispose,linen};
}

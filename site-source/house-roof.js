import * as THREE from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';

// Visual envelopes fit the existing sketch, not a manufacturer's roof system.
// These values describe its geometry only; no pitch/product approval is implied.
export const roofLooks={
 'standing-seam':{title:'Фальцевая стальная кровля',color:0x46545a,roughness:.64,metalness:.72},
 'metal-tile':{title:'Металлочерепица',color:0x505b59,roughness:.62,metalness:.65},
 'bitumen-shingle':{title:'Гибкая битумная черепица',color:0x48453e,roughness:1,metalness:0}
};
const width=15.4,run=5.5,rise=1.5,ridge=4.735,length=Math.hypot(run,rise),sn=rise/length,cs=run/length;
const point=(x,v,h,side)=>[x,ridge-v*sn+h*cs,side*(v*cs+h*sn)];
export function makeRoofMaterial(id,spec=roofLooks[id]){
 const data=new Uint8Array(128*128*4);let seed=719;
 for(let i=0;i<data.length;i+=4){seed=(seed*1664525+1013904223)>>>0;const n=seed/4294967296,c=id==='bitumen-shingle'?170+n*85:225+n*30;data[i]=data[i+1]=data[i+2]=c;data[i+3]=255;}
 const grain=new THREE.DataTexture(data,128,128);grain.wrapS=grain.wrapT=THREE.RepeatWrapping;grain.repeat.set(id==='bitumen-shingle'?3:6,id==='bitumen-shingle'?3:6);grain.magFilter=THREE.LinearFilter;grain.minFilter=THREE.LinearMipmapLinearFilter;grain.generateMipmaps=true;grain.needsUpdate=true;
 const mat=new THREE.MeshStandardMaterial({color:spec.color,roughness:spec.roughness,metalness:spec.metalness,bumpMap:grain,bumpScale:id==='bitumen-shingle'?.003:.0007,vertexColors:id==='bitumen-shingle',side:THREE.DoubleSide,envMapIntensity:id==='bitumen-shingle'?.18:.7});
 if(id==='bitumen-shingle')mat.map=grain;
 mat.userData.ownedTextures=[grain];return mat;
}
function releaseMaterial(material){if(!material)return;for(const t of material.userData.ownedTextures||[])t.dispose();material.dispose();}
function transformed(g,side){
 const m=new THREE.Matrix4().set(1,0,0,0, 0,cs,-sn,ridge, 0,side*sn,side*cs,0, 0,0,0,1);
 g.applyMatrix4(m);
 if(side<0){if(g.index){const a=g.index.array;for(let i=0;i<a.length;i+=3)[a[i+1],a[i+2]]=[a[i+2],a[i+1]];}else{for(const attribute of Object.values(g.attributes)){const a=attribute.array,n=attribute.itemSize;for(let i=0;i<attribute.count;i+=3)for(let k=0;k<n;k++)[a[(i+1)*n+k],a[(i+2)*n+k]]=[a[(i+2)*n+k],a[(i+1)*n+k]];}}}
 g.computeVertexNormals();return g;
}
function surfaceGeometry(id){
 const pieces=[];
 if(id==='standing-seam'){
  const n=30,panel=width/n;
  const shape=new THREE.Shape();
  [[0,-.008],[panel,-.008],[panel,.043],[panel-.014,.043],[panel-.014,.004],[0,.004]].forEach(([x,y],i)=>i?shape.lineTo(x,y):shape.moveTo(x,y));shape.closePath();
  for(const side of [-1,1])for(let i=0;i<n;i++){
   const g=new THREE.ExtrudeGeometry(shape,{depth:length,steps:1,bevelEnabled:false,curveSegments:1});g.translate(-width/2+i*panel,0,0);pieces.push(transformed(g,side));
  }
 }
 if(id==='metal-tile'){
  for(const side of [-1,1]){
   const nx=240,rows=15,vs=[];for(let row=0;row<rows;row++)for(let k=0;k<=6;k++)vs.push({v:length*(row+k/6)/rows,phase:k/6});
   const nv=vs.length-1,g=new THREE.BufferGeometry(),positions=[],uvs=[],indices=[];
   for(let j=0;j<=nv;j++)for(let i=0;i<=nx;i++){
    const x=-width/2+width*i/nx,v=vs[j].v;
    const wave=.029*(1+Math.cos((x+width/2)/.35*Math.PI*2));
    const step=.032*(1-vs[j].phase);
    positions.push(...point(x,v,.009+wave+step,side));uvs.push(x,v);
   }
   for(let j=0;j<nv;j++)for(let i=0;i<nx;i++){const a=j*(nx+1)+i,b=a+1,c=a+nx+1,d=c+1;indices.push(...(side>0?[a,c,b,b,c,d]:[a,b,c,b,d,c]));}
   g.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));g.setAttribute('uv',new THREE.Float32BufferAttribute(uvs,2));g.setIndex(indices);g.computeVertexNormals();pieces.push(g.toNonIndexed());g.dispose();
  }
 }
 if(id==='bitumen-shingle'){
  const positions=[],uvs=[],colors=[],rows=20,cw=.64,step=length/rows;
  function triangle(a,b,c,side,shade){for(const [x,v,h] of side>0?[a,c,b]:[a,b,c]){positions.push(...point(x,v,h,side));uvs.push(x*4,v*4);colors.push(shade,shade*.98,shade*.94);}}
  for(const side of [-1,1])for(let row=0;row<rows;row++){
   let x=-width/2,index=0;
   while(x<width/2-.0001){const w=Math.min(index===0&&row%2?cw/2:cw,width/2-x),left=x+.002,right=x+w-.002,v0=Math.max(0,row*step-.065),v1=(row+1)*step;
    const h=.014+(rows-row)*.00065,shade=.84+.15*Math.abs(Math.sin(row*83+index*47+side*19));
    // A shallow notch and raised bottom edge produce real shadow lines.
    const mid=(left+right)/2,notch=Math.min(.008,w/8);
    const outline=[[left,v0,h],[right,v0,h],[right,v1,h],[mid+notch,v1,h],[mid,v1-.017,h],[mid-notch,v1,h],[left,v1,h]];
    for(let k=1;k<outline.length-1;k++)triangle(outline[0],outline[k],outline[k+1],side,shade);
    for(let k=2;k<outline.length;k++){const a=outline[k-1],b=outline[k],c=[b[0],b[1],h-.008],d=[a[0],a[1],h-.008];triangle(a,b,c,side,shade*.8);triangle(a,c,d,side,shade*.8);}
    x+=w;index++;
   }
  }
  const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));g.setAttribute('uv',new THREE.Float32BufferAttribute(uvs,2));g.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));g.computeVertexNormals();return g;
 }
 const merged=mergeGeometries(pieces,false);for(const g of pieces)g.dispose();if(!merged)throw Error('Roof geometry merge failed');return merged;
}

export function buildHouseRoof(id,{material=null}={}){
 const spec=roofLooks[id];if(!spec)throw Error('Unknown house roof appearance');
 const root=new THREE.Group();root.name='roof appearance '+id;root.userData.roofLook=id;
 const ownMaterial=!material;
 material??=new THREE.MeshStandardMaterial({color:spec.color,roughness:spec.roughness,metalness:spec.metalness,vertexColors:id==='bitumen-shingle',side:THREE.DoubleSide});
 const g=surfaceGeometry(id),cover=new THREE.Mesh(g,material);cover.name='visible covering '+id;cover.castShadow=cover.receiveShadow=true;root.add(cover);
 // A visual ridge cap follows the unchanged roof envelope, not a fastener detail.
 const ridgeShape=new THREE.BufferGeometry(),rp=[],ru=[];
 const half=id==='bitumen-shingle'?.14:.115;
 for(const side of [-1,1]){
  const a=point(-width/2,0,.055,side),b=point(width/2,0,.055,side),c=point(width/2,half,.035,side),d=point(-width/2,half,.035,side);
  for(const v of side>0?[a,c,b,a,d,c]:[a,b,c,a,c,d]){rp.push(...v);ru.push(v[0],v[2]);}
 }
 ridgeShape.setAttribute('position',new THREE.Float32BufferAttribute(rp,3));ridgeShape.setAttribute('uv',new THREE.Float32BufferAttribute(ru,2));
 if(id==='bitumen-shingle')ridgeShape.setAttribute('color',new THREE.Float32BufferAttribute(Array(rp.length).fill(.91),3));ridgeShape.computeVertexNormals();
 const cap=new THREE.Mesh(ridgeShape,material);cap.name='visual ridge cap '+id;cap.castShadow=cap.receiveShadow=true;root.add(cap);
 // Narrow perimeter silhouettes cover the formerly exposed slab edge. They
 // illustrate edge treatment, not an approved flashing or ventilation detail.
 const edges=new THREE.BufferGeometry(),ep=[],eu=[];
 function edge(a,b,c,d){for(const v of [a,b,c,a,c,d]){ep.push(...v);eu.push(v[0],v[2]);}}
 for(const side of [-1,1]){
  for(const x of [-width/2,width/2]){
   const a=point(x,0,.055,side),b=point(x,length,.055,side);edge(a,b,[b[0],b[1]-.17,b[2]],[a[0],a[1]-.17,a[2]]);
  }
  const a=point(-width/2,length,.045,side),b=point(width/2,length,.045,side);edge(a,b,[b[0],b[1]-.10,b[2]],[a[0],a[1]-.10,a[2]]);
 }
 edges.setAttribute('position',new THREE.Float32BufferAttribute(ep,3));edges.setAttribute('uv',new THREE.Float32BufferAttribute(eu,2));if(id==='bitumen-shingle')edges.setAttribute('color',new THREE.Float32BufferAttribute(Array(ep.length).fill(.9),3));edges.computeVertexNormals();const perimeter=new THREE.Mesh(edges,material);perimeter.name='visual perimeter trim '+id;perimeter.castShadow=perimeter.receiveShadow=true;root.add(perimeter);
 return{root,spec,dispose(){root.removeFromParent();g.dispose();ridgeShape.dispose();edges.dispose();if(ownMaterial)material.dispose();}};
}

export function createHouseRoof(house,{makeMaterial,onChange=()=>{}}={}){
 const roof=house.getObjectByName('05_roof');if(!roof)throw Error('House roof group missing');
 const originals=[];roof.traverse(o=>{if(o.isMesh&&['roof','anthracite'].includes(o.material?.name))originals.push([o,o.visible]);});
 if(originals.length!==2)throw Error('Unexpected source roof layout; refusing to hide unknown meshes');
 const trim=originals.find(([o])=>o.material.name==='anthracite')[0];
 house.updateMatrixWorld(true);const source=trim.geometry.index?trim.geometry.toNonIndexed():trim.geometry.clone();source.applyMatrix4(new THREE.Matrix4().copy(roof.matrixWorld).invert().multiply(trim.matrixWorld));
 const pos=source.attributes.position,keep=[];
 for(let i=0;i<pos.count;i+=3)if([i,i+1,i+2].every(j=>pos.getY(j)<3.18))keep.push(i,i+1,i+2);
 if(!keep.length){source.dispose();throw Error('Source gutter extraction empty');}
 const gutters=new THREE.BufferGeometry();for(const [key,a] of Object.entries(source.attributes)){const values=[];for(const i of keep)for(let k=0;k<a.itemSize;k++)values.push(a.array[i*a.itemSize+k]);gutters.setAttribute(key,new THREE.Float32BufferAttribute(values,a.itemSize));}source.dispose();
 const water=new THREE.Mesh(gutters,trim.material);water.name='preserved original gutters';water.castShadow=water.receiveShadow=true;roof.add(water);
 const slot=new THREE.Group();slot.name='selected roof envelope';roof.add(slot);
 let current=null,material=null,id=null,preference=null;
 function enforce(){for(const [o] of originals)o.visible=false;}
 function select(value){
  const next=value||'standing-seam';if(!roofLooks[next])throw Error('Invalid roof preference');preference=value||null;
  if(next!==id){current?.dispose();releaseMaterial(material);id=next;material=makeMaterial?.(next,roofLooks[next]);current=buildHouseRoof(next,{material});slot.add(current.root);}
  enforce();house.updateMatrixWorld(true);onChange(audit());
 }
 function audit(){let vertices=0,triangles=0;current?.root.traverse(o=>{if(o.isMesh){vertices+=o.geometry.attributes.position.count;triangles+=(o.geometry.index?.count||o.geometry.attributes.position.count)/3;}});return{id,preference,title:roofLooks[id]?.title,appearanceChanged:!!preference,assemblyApproved:false,sourceCoverHidden:originals.every(([o])=>!o.visible),guttersVertices:gutters.attributes.position.count,vertices,triangles};}
 return{select,enforce,audit,dispose(){current?.dispose();releaseMaterial(material);water.removeFromParent();gutters.dispose();slot.removeFromParent();for(const [o,v] of originals)o.visible=v;}};
}

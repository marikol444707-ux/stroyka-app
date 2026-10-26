import * as THREE from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';
// Decorative setting only. No cadastral boundaries, plant specification or site approval.
export const gardenTrees=[[-10.8,-9.5,4.7,1.8],[-3.8,-12.5,5.2,2.05],[5.7,-11.8,4.9,1.85],[12.5,-6.8,4.3,1.65],[-12.2,3,5.1,2.0],[13.7,6.8,4.4,1.7]];
export function createHouseGarden(scene){
 const root=new THREE.Group();root.name='proposed garden setting';scene.add(root);let mode='assembled',study=false,disposed=false,seed=61831;
 const geometries=new Set(),materials=new Set(),textures=new Set(),bounds=[],treeCentres=[];
 const rand=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
 const mat=(color,extra={})=>{const m=new THREE.MeshStandardMaterial({color,roughness:.95,...extra});materials.add(m);return m;};
 const mesh=(geometry,material,name)=>{geometries.add(geometry);const m=new THREE.Mesh(geometry,material);m.name=name;m.receiveShadow=true;root.add(m);return m;};
 // A continuous, softly varied lawn. Procedural data; no remote texture requests.
 const size=192,data=new Uint8Array(size*size*4);
 for(let z=0;z<size;z++)for(let x=0;x<size;x++){const wave=Math.sin(x*.12+Math.sin(z*.07))*3+Math.sin(z*.2)*2+(rand()-.5)*8,i=(z*size+x)*4;data[i]=137+wave;data[i+1]=151+wave;data[i+2]=106+wave;data[i+3]=255;}
 const lawnTexture=new THREE.DataTexture(data,size,size,THREE.RGBAFormat);lawnTexture.wrapS=lawnTexture.wrapT=THREE.RepeatWrapping;lawnTexture.repeat.set(10,10);lawnTexture.minFilter=THREE.LinearMipmapLinearFilter;lawnTexture.magFilter=THREE.LinearFilter;lawnTexture.generateMipmaps=true;lawnTexture.colorSpace=THREE.SRGBColorSpace;lawnTexture.needsUpdate=true;textures.add(lawnTexture);
 const lawn=mesh(new THREE.PlaneGeometry(180,180),mat(0xe3e5cf,{map:lawnTexture}),'soft garden lawn');lawn.rotation.x=-Math.PI/2;lawn.position.set(0,-.394,0);
 // Crown made from individually oriented curved leaves; no faceted sphere crowns.
 const leaf=new THREE.BufferGeometry();leaf.setAttribute('position',new THREE.Float32BufferAttribute([0,0,0,-.42,.02,.38,0,.08,.5,.42,.02,.38,0,.025,1],3));leaf.setIndex([0,2,1,0,3,2,1,2,4,2,3,4]);leaf.computeVertexNormals();geometries.add(leaf);
 const leafMaterials=[mat(0x506b39,{side:THREE.DoubleSide}),mat(0x6e8249,{side:THREE.DoubleSide}),mat(0x879359,{side:THREE.DoubleSide})];
 const matrices=[[],[],[]],branches=[],dummy=new THREE.Object3D();let treeLeaves=0;
 function branch(a,b,r1,r2){const direction=b.clone().sub(a),g=new THREE.CylinderGeometry(r2,r1,direction.length(),7,1);dummy.position.copy(a).add(b).multiplyScalar(.5);dummy.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),direction.normalize());dummy.scale.set(1,1,1);dummy.updateMatrix();g.applyMatrix4(dummy.matrix);branches.push(g);}
 function addLeaf(x,y,z,scale,color){dummy.position.set(x,y,z);dummy.rotation.set((rand()-.5)*2.6,rand()*Math.PI*2,(rand()-.5)*1.8);dummy.scale.set(scale*.65,scale,scale);dummy.updateMatrix();matrices[color].push(dummy.matrix.clone());}
 for(const [x,z,h,radius] of gardenTrees){
  treeCentres.push([x,z]);bounds.push({x,z,radius});const origin=new THREE.Vector3(x,-.37,z),top=new THREE.Vector3(x+.15,h*.64,z+.08);branch(origin,top,.11,.035);
  for(let j=0;j<7;j++){const a=j/7*Math.PI*2+.4,tip=new THREE.Vector3(x+Math.cos(a)*radius*.7,h*(.65+rand()*.2),z+Math.sin(a)*radius*.7);branch(new THREE.Vector3(x,h*.4,z),tip,.045,.009);}
  for(let i=0;i<1650;i++){const a=rand()*Math.PI*2,v=2*rand()-1,r=Math.cbrt(rand()),horizontal=Math.sqrt(1-v*v),lobe=i%3,phase=lobe*2.094+.6,xx=x+Math.cos(phase)*radius*.22+Math.cos(a)*horizontal*radius*r*.72,zz=z+Math.sin(phase)*radius*.22+Math.sin(a)*horizontal*radius*r*.72,yy=h*.73+Math.sin(phase+.7)*radius*.14+v*radius*.77*r;addLeaf(xx,yy,zz,.16+rand()*.12,i%3);treeLeaves++;}
 }
 // A distant informal planting edge frames views through the north windows.
 const shrubs=[[-11,-5,1.1],[-10,-1,1.05],[-8.7,-10.1,.95],[-.1,-10.8,1.1],[2.3,-11,.9],[8.8,-10.1,1.0],[11,-2.4,.9],[12,2.4,1.05]];
 let shrubLeaves=0;
 for(const [x,z,r] of shrubs){bounds.push({x,z,radius:r});for(let i=0;i<190;i++){const a=rand()*Math.PI*2,rr=Math.sqrt(rand())*r,yy=.05+Math.sqrt(Math.max(0,1-(rr/r)**2))*(.6+rand()*.45);addLeaf(x+Math.cos(a)*rr,yy,z+Math.sin(a)*rr,.22+rand()*.14,i%3);shrubLeaves++;}}
 const wood=mat(0x77654c);if(branches.length){const joined=mergeGeometries(branches);branches.forEach(g=>g.dispose());mesh(joined,wood,'tree trunks and branches').castShadow=true;}
 let drawGroups=0;
 matrices.forEach((list,index)=>{const m=new THREE.InstancedMesh(leaf,leafMaterials[index],list.length);m.name='garden leaf instances '+index;list.forEach((matrix,i)=>m.setMatrixAt(i,matrix));m.instanceMatrix.needsUpdate=true;m.castShadow=true;m.receiveShadow=true;m.computeBoundingSphere();root.add(m);drawGroups++;});
 function sync(){root.visible=!disposed&&!study&&['assembled','terrace','inside','walk','facade'].includes(mode);}
 function audit(){return {visible:root.visible,mode,study,treeCount:gardenTrees.length,treeLeaves,shrubLeaves,leafDrawGroups:drawGroups,meshes:root.children.length,textures:textures.size,treeCentres:treeCentres.map(p=>[...p]),plantingBounds:bounds.map(b=>({...b})),houseGeometryChanged:false,landscapeApproved:false,animatedVegetation:false,disposed};}
 function dispose(){if(disposed)return;disposed=true;root.visible=false;root.removeFromParent();for(const o of root.children)if(o.isInstancedMesh)o.dispose();geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());}
 sync();return {setMode:value=>{mode=value;sync();},setStudy:value=>{study=!!value;sync();},audit,dispose};
}

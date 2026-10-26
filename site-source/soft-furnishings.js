import * as THREE from 'three';
// Refine only the two existing sofa cushions. Keep positions, bounds and navigation.
export function createSoftFurnishings(house){
 const records=[];let disposed=false,changedVertices=0,cushionVertices=0,cushions=0;
 house.updateMatrixWorld(true);const interior=house.getObjectByName('07_interior');
 interior.traverse(o=>{
  if(!o.isMesh||Array.isArray(o.material)||o.material.name!=='sage'||!o.geometry.index)return;
  const source=o.geometry,position=source.attributes.position,index=source.index,parent=Array.from({length:position.count},(_,i)=>i),same=new Map();
  const find=x=>{while(parent[x]!==x){parent[x]=parent[parent[x]];x=parent[x];}return x;},union=(a,b)=>parent[find(a)]=find(b);
  for(let i=0;i<position.count;i++){const key=[position.getX(i),position.getY(i),position.getZ(i)].map(v=>Math.round(v*10000)).join(',');if(same.has(key))union(i,same.get(key));else same.set(key,i);}
  for(let i=0;i<index.count;i+=3){union(index.getX(i),index.getX(i+1));union(index.getX(i),index.getX(i+2));}
  const islands=new Map();for(let i=0;i<position.count;i++){const id=find(i);if(!islands.has(id))islands.set(id,[]);islands.get(id).push(i);}
  const chosen=[];
  for(const ids of islands.values()){if(ids.length<100)continue;const box=new THREE.Box3();for(const id of ids)box.expandByPoint(new THREE.Vector3().fromBufferAttribute(position,id).applyMatrix4(o.matrixWorld));const size=box.getSize(new THREE.Vector3());if(box.min.x>3.5&&box.max.x<6.1&&box.min.z>3.5&&box.max.z<4.1&&box.min.y>.5&&box.max.y<1.4&&size.x>.5&&size.x<.7&&size.y>.5&&size.y<.7&&size.z>.2&&size.z<.35)chosen.push({ids,box});}
  if(!chosen.length)return;
  const geometry=source.clone(),attribute=geometry.attributes.position,selected=new Set(),inverse=o.matrixWorld.clone().invert();
  for(const {ids,box} of chosen){const c=box.getCenter(new THREE.Vector3()),r=box.getSize(new THREE.Vector3()).multiplyScalar(.5);for(const id of ids){const v=new THREE.Vector3().fromBufferAttribute(position,id).applyMatrix4(o.matrixWorld),rounded=(v,e)=>Math.sign(v)*Math.pow(Math.abs(v),e);const x=rounded((v.x-c.x)/r.x,.55),y=rounded((v.y-c.y)/r.y,.55),z=rounded((v.z-c.z)/r.z,.75)*(1-.32*Math.pow(Math.max(Math.abs(x),Math.abs(y)),4));v.set(c.x+x*r.x,c.y+y*r.y,c.z+z*r.z).applyMatrix4(inverse);if(v.distanceTo(new THREE.Vector3().fromBufferAttribute(position,id))>1e-6)changedVertices++;attribute.setXYZ(id,v.x,v.y,v.z);selected.add(id);}cushions++;cushionVertices+=ids.length;}
  geometry.clearGroups();let start=0,last=null;for(let i=0;i<index.count;i+=3){const material=selected.has(index.getX(i))?1:0;if(last!==null&&last!==material){geometry.addGroup(start,i-start,last);start=i;}last=material;}geometry.addGroup(start,index.count-start,last);attribute.needsUpdate=true;geometry.computeVertexNormals();for(let id=0;id<position.count;id++)if(!selected.has(id)){const n=source.attributes.normal;geometry.attributes.normal.setXYZ(id,n.getX(id),n.getY(id),n.getZ(id));}geometry.computeBoundingBox();geometry.computeBoundingSphere();
  const textile=o.material.clone();textile.userData={...textile.userData,softTextile:true};textile.roughness=.95;records.push({object:o,geometry:source,material:o.material,ownedGeometry:geometry,textile});o.geometry=geometry;o.material=[o.material,textile];
 });
 function audit(){return {cushions,cushionVertices,changedVertices,sourceMeshes:records.length,layoutChanged:false,navigationChanged:false,disposed};}
 function dispose(){if(disposed)return;disposed=true;for(const r of records){r.object.geometry=r.geometry;r.object.material=r.material;r.ownedGeometry.dispose();r.textile.dispose();}}
 return {audit,dispose};
}

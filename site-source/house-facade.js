import * as THREE from 'three';

export const facadeLooks={
 'plaster-facade':{title:'Штукатурный фасад'},
 'timber-facade':{title:'Деревянная реечная отделка'}
};
const faces=[{axis:0,sign:1,edge:6.95,u:2},{axis:0,sign:-1,edge:6.95,u:2},{axis:2,sign:1,edge:4.95,u:0},{axis:2,sign:-1,edge:4.95,u:0}];
export function extractFacadeFaces(house){
 house.updateMatrixWorld(true);const inverse=new THREE.Matrix4().copy(house.matrixWorld).invert(),records=[];
 // Take copies before attaching finish meshes: never traverse our own output.
 const sources=[];for(const name of ['03_walls','05_roof'])house.getObjectByName(name)?.traverse(o=>{if(o.isMesh&&o.material?.name==='warm plaster')sources.push(o);});
 for(const object of sources){
  const localToHouse=new THREE.Matrix4().copy(inverse).multiply(object.matrixWorld);
  const g=object.geometry.index?object.geometry.toNonIndexed():object.geometry.clone();g.applyMatrix4(localToHouse);
  const a=g.attributes.position,triangles=[];
  for(let i=0;i<a.count;i+=3){
   const p=[0,1,2].map(k=>new THREE.Vector3().fromBufferAttribute(a,i+k)),normal=p[1].clone().sub(p[0]).cross(p[2].clone().sub(p[0])),area=normal.length()/2;if(area<1e-8)continue;normal.normalize();
   const f=faces.find(f=>normal.getComponent(f.axis)*f.sign>.999&&p.every(v=>v.getComponent(f.axis)*f.sign>f.edge));
   if(f)triangles.push({points:p.map(v=>v.toArray()),normal:normal.toArray(),u:f.u,area,side:f.axis+':'+f.sign});
  }
  g.dispose();if(triangles.length)records.push({object,triangles,toLocal:localToHouse.clone().invert()});
 }
 return records;
}
function clip(poly,axis,edge,sign){
 const out=[];for(let i=0;i<poly.length;i++){const a=poly[i],b=poly[(i+1)%poly.length],aa=sign*(a[axis]-edge)>=-1e-9,bb=sign*(b[axis]-edge)>=-1e-9;if(aa)out.push(a);if(aa!==bb){const t=(edge-a[axis])/(b[axis]-a[axis]);out.push(a.map((v,k)=>v+(b[k]-v)*t));}}return out;
}
export function buildFacadeGeometry(triangles,id){
 if(!facadeLooks[id])throw Error('Unknown facade appearance');
 const positions=[],uv=[],colors=[],shadow=[],su=[];
 function vertex(to,tu,p,n,offset,u){to.push(...p.map((v,k)=>v+n[k]*offset));tu.push(p[u],p[1]);}
 for(const t of triangles){
  const p=t.points,n=t.normal;
  if(id==='plaster-facade'){for(const v of p){vertex(positions,uv,v,n,.003,t.u);colors.push(1,1,1);}continue;}
  for(const v of p)vertex(shadow,su,v,n,.004,t.u);
  const pitch=.14,gap=.013,lo=Math.floor(Math.min(...p.map(v=>v[t.u]))/pitch),hi=Math.floor(Math.max(...p.map(v=>v[t.u]))/pitch);
  for(let strip=lo;strip<=hi;strip++){
   const left=strip*pitch+gap/2,right=(strip+1)*pitch-gap/2;
   let poly=clip(p,t.u,left,1);poly=clip(poly,t.u,right,-1);if(poly.length<3)continue;
   const shade=.85+.14*Math.abs(Math.sin(strip*31.7));
   const push=v=>{vertex(positions,uv,v,n,.027,t.u);colors.push(shade,shade*.98,shade*.94);};
   for(let i=1;i<poly.length-1;i++)for(const v of [poly[0],poly[i],poly[i+1]])push(v);
   // Close the two long sides of each strip. Do not create a bevel or cap
   // along every input triangle: that would draw false diagonal board seams.
   for(let i=0;i<poly.length;i++){
    const a=poly[i],b=poly[(i+1)%poly.length];if(![left,right].some(edge=>Math.abs(a[t.u]-edge)<1e-7&&Math.abs(b[t.u]-edge)<1e-7))continue;
    const aa=a.map((v,k)=>v-n[k]*.022),bb=b.map((v,k)=>v-n[k]*.022);for(const v of [a,aa,b,b,aa,bb])push(v);
   }
  }
 }
 function geometry(p,u,c){const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(p,3));g.setAttribute('uv',new THREE.Float32BufferAttribute(u,2));if(c)g.setAttribute('color',new THREE.Float32BufferAttribute(c,3));g.computeVertexNormals();return g;}
 return{finish:geometry(positions,uv,colors),recess:shadow.length?geometry(shadow,su):null};
}
export function makeFacadeMaterials(id){
 const timber=id==='timber-facade',data=new Uint8Array(128*256*4);let seed=331;
 for(let y=0;y<256;y++)for(let x=0;x<128;x++){
  seed=(seed*1664525+1013904223)>>>0;const grain=Math.sin(x*.7+Math.sin(y*.027)*1.2)+.35*Math.sin(x*2.7+y*.009),c=timber?205+grain*17+(seed/4294967296)*15:235+(seed/4294967296)*20;
  const i=(y*128+x)*4;data[i]=data[i+1]=data[i+2]=c;data[i+3]=255;
 }
 const texture=new THREE.DataTexture(data,128,256);texture.wrapS=texture.wrapT=THREE.RepeatWrapping;texture.repeat.set(timber?3:7,timber?.7:7);texture.magFilter=THREE.LinearFilter;texture.minFilter=THREE.LinearMipmapLinearFilter;texture.generateMipmaps=true;texture.needsUpdate=true;
 const finish=new THREE.MeshStandardMaterial({color:timber?0xb59164:0xe1d6c0,roughness:timber?.78:.96,metalness:0,map:timber?texture:null,bumpMap:texture,bumpScale:timber?.002:.0009,vertexColors:true,side:THREE.DoubleSide,envMapIntensity:.25});
 const recess=timber?new THREE.MeshStandardMaterial({color:0x4b493d,roughness:1,side:THREE.DoubleSide}):null;
 return{finish,recess,dispose(){finish.dispose();recess?.dispose();texture.dispose();}};
}
export function createHouseFacade(house,{onChange=()=>{}}={}){
 const records=extractFacadeFaces(house),area=records.reduce((s,r)=>s+r.triangles.reduce((s,t)=>s+t.area,0),0),sides=new Set(records.flatMap(r=>r.triangles.map(t=>t.side)));
 if(area<50||sides.size!==4)throw Error('Unexpected facade envelope; refusing to cover unknown house');
 let selected=null,materials=null,attached=[];
 function clear(){for(const m of attached){m.removeFromParent();m.geometry.dispose();}attached=[];materials?.dispose();materials=null;}
 function select(id){
  if(id!==null&&!facadeLooks[id])throw Error('Invalid facade preference');
  if(selected===id){onChange(audit());return;}clear();selected=id;
  if(id){materials=makeFacadeMaterials(id);house.updateMatrixWorld(true);
   for(const r of records){const built=buildFacadeGeometry(r.triangles,id),toLocal=r.toLocal;
    for(const [key,g] of Object.entries(built)){if(!g)continue;g.applyMatrix4(toLocal);const m=new THREE.Mesh(g,key==='finish'?materials.finish:materials.recess);m.name='facade '+id+' '+key;m.userData.facadeFinish=true;m.castShadow=m.receiveShadow=true;r.object.add(m);attached.push(m);}
   }
  }
  onChange(audit());
 }
 function audit(){return{id:selected,title:selected?facadeLooks[selected].title:'Исходная отделка эскиза',appearanceChanged:!!selected,assemblyApproved:false,sourceArea:area,sourceFaces:records.reduce((s,r)=>s+r.triangles.length,0),coveredSides:sides.size,meshes:attached.length,triangles:attached.reduce((s,m)=>s+m.geometry.attributes.position.count/3,0),visibleMeshes:attached.filter(m=>{let p=m;while(p){if(!p.visible)return false;p=p.parent;}return true;}).length};}
 return{select,audit,dispose(){clear();selected=null;}};
}

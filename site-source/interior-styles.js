import furnitureLayout from './furniture-layout.json' with {type:'json'};
import {createInteriorDetails} from './interior-details.js';
import * as THREE from 'three';
export const interiorStyles={
  warm:{title:'Тёплый современный',description:'Древесные фактуры, спокойный зелёный и мягкие натуральные оттенки.',colors:{'white':0xe7e1d3,'linen':0xcabda6,'fabric':0x978371,'sage':0x66765d,'oak':0xa99676,'light oak':0xc9bd9f},light:0xffe4c3},
  minimal:{title:'Светлый минимализм',description:'Светлые поверхности, сдержанные контрасты и более спокойная фактура дерева.',colors:{'white':0xf2f0e8,'linen':0xd8d9d1,'fabric':0xb4bab1,'sage':0xd0d4ca,'oak':0xc9c7bb,'light oak':0xe1dcd0},light:0xf7f2e5},
  classic:{title:'Современная классика',description:'Тёплые светлые стены, тёмное дерево, тонкие молдинги и латунные акценты.',colors:{'white':0xece4d4,'linen':0xd8c6ad,'fabric':0x7d827c,'sage':0xb5b1a0,'oak':0x76604c,'light oak':0xbdaa8d},light:0xffdfb5}
};
export function createInteriorStyles(house,scene){
  const records=[],cache=new Map(),extras=new THREE.Group();extras.name='interior style details';house.getObjectByName('07_interior').add(extras);
  // Clone only interior/partition materials. Shared facade materials stay intact.
  for(const group of ['07_interior','03_walls']){
    house.getObjectByName(group).traverse(o=>{
      if(!o.isMesh)return;
      const mats=Array.isArray(o.material)?o.material:[o.material];
      if(group==='03_walls'&&!mats.every(m=>['white','light oak'].includes(m.name)))return;
      records.push({object:o,original:o.material,materials:mats,array:Array.isArray(o.material)});
    });
  }
  const details=createInteriorDetails(house);
  const classic=new THREE.Group(),warm=new THREE.Group();extras.add(classic,warm);
  const trimMaterial=new THREE.MeshStandardMaterial({color:0xe6d8bd,roughness:.6});
  const brass=new THREE.MeshStandardMaterial({color:0xac8d50,metalness:.75,roughness:.32});
  const timber=new THREE.MeshStandardMaterial({color:0x8a704f,roughness:.65});
  function box(parent,x,y,z,w,h,d,material){const o=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),material);o.position.set(x,y,z);parent.add(o);return o;}
  // Applied trim on existing wall bays, clear of the actual door openings.
  for(const [x,w] of [[.38,.46],[2.1,.5],[4.3,.30],[6.6,.32]]){
    for(const y of [.45,2.25])box(classic,x,y,-1.222,w,.025,.022,trimMaterial);
    for(const dx of [-w/2,w/2])box(classic,x+dx,1.35,-1.222,.025,1.8,.022,trimMaterial);
  }
  // Three small pendant collars distinguish the classic fixture treatment.
  for(const [x,z] of [[furnitureLayout.dining.x,furnitureLayout.dining.z],[2.1,.75],[4.7,3.1]]){
    const ring=new THREE.Mesh(new THREE.TorusGeometry(.235,.012,6,32),brass);ring.rotation.x=Math.PI/2;ring.position.set(x,2.17,z);classic.add(ring);
  }
  for(let i=0;i<9;i++)box(warm,4.15+i*.034,1.45,-1.216,.014,2.35,.018,timber);
  // A thin decorative floor surface, clipped to the existing living-room bounds.
  // It never changes room dimensions, obstacle geometry or furniture positions.
  const positions=[],uvs=[],colors=[];
  function clip(poly,axis,edge,sign){
    const out=[];
    for(let i=0;i<poly.length;i++){
      const a=poly[i],b=poly[(i+1)%poly.length],aa=sign*(a[axis]-edge)>=0,bb=sign*(b[axis]-edge)>=0;
      if(aa)out.push(a);
      if(aa!==bb){const t=(edge-a[axis])/(b[axis]-a[axis]);out.push(a.map((v,k)=>v+(b[k]-v)*t));}
    }return out;
  }
  for(let i=-60;i<60;i++)for(let j=-60;j<60;j++){
    const mod=((i+j)%8+8)%8;if(mod!==0&&mod!==4)continue;
    const w=mod===0?.52:.13,d=mod===0?.13:.52;
    const angle=Math.PI/4,c=Math.cos(angle),sn=Math.sin(angle),gap=.0015;
    let poly=[[gap,gap],[w-gap,gap],[w-gap,d-gap],[gap,d-gap]].map(([x,z])=>{const a=i*.13+x,b=j*.13+z;return [3+a*c-b*sn,1.8+a*sn+b*c,x/w,z/d];});
    for(const [axis,edge,sign] of [[0,.03,1],[0,6.84,-1],[1,-1.21,1],[1,4.84,-1]]){poly=clip(poly,axis,edge,sign);if(poly.length<3)break;}
    if(poly.length<3)continue;
    const shade=.70+Math.abs(Math.sin(i*37+j*19))*.25;
    for(let k=1;k<poly.length-1;k++)for(const v of [poly[0],poly[k],poly[k+1]]){positions.push(v[0],.058,v[1]);uvs.push(v[2],v[3]);colors.push(shade,shade*.96,shade*.88);}
  }
  const parquet=new THREE.BufferGeometry();parquet.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));parquet.setAttribute('uv',new THREE.Float32BufferAttribute(uvs,2));parquet.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));parquet.computeVertexNormals();
  const wood=house.getObjectByName('07_interior').children.find(o=>o.material?.name==='light oak')?.material;
  const parquetMat=new THREE.MeshStandardMaterial({color:0xb5a080,map:wood?.map,vertexColors:true,roughness:.6,side:THREE.DoubleSide});
  const parquetMesh=new THREE.Mesh(parquet,parquetMat);parquetMesh.name='classic herringbone finish';parquetMesh.receiveShadow=true;classic.add(parquetMesh);
  const lights=[];
  for(const [x,z] of [[2.1,.75],[furnitureLayout.dining.x,furnitureLayout.dining.z],[-.8,0]]){
    const l=new THREE.PointLight(0xffe4c3,11,10,2);l.position.set(x,2.65,z);scene.add(l);lights.push(l);
  }
  let current='warm';
  function apply(id){
    if(!interiorStyles[id])throw Error('Unknown interior style');current=id;
    const style=interiorStyles[id];
    for(const r of records){
      const changed=r.materials.map(m=>{
        const key=id+':'+m.uuid;
        if(!cache.has(key)){
          const c=m.clone();if(['linen','fabric'].includes(m.name)||m.userData.softTextile){c.map=details.linen;c.bumpMap=details.linen;c.bumpScale=.0015;c.roughness=.95;}c.name='interior '+id+' / '+m.name;
          if(style.colors[m.name])c.color.setHex(style.colors[m.name]);
          if(id==='minimal'&&['oak','light oak'].includes(m.name)){
            c.color.setHex(style.colors[m.name]);c.roughness=.7;
            c.onBeforeCompile=shader=>{shader.fragmentShader=shader.fragmentShader.replace('#include <map_fragment>','#include <map_fragment>\ndiffuseColor.rgb=mix(diffuseColor.rgb,vec3(0.65,0.62,0.56),0.45);');};
            c.customProgramCacheKey=()=> 'stroyka-light-wood-v1';
          }
          cache.set(key,c);
        }
        return cache.get(key);
      });r.object.material=r.array?changed:changed[0];
    }
    classic.visible=id==='classic';warm.visible=id==='warm';details.apply(id);
    for(const l of lights)l.color.setHex(style.light);
    return style;
  }
  function dispose(){for(const r of records)r.object.material=r.original;for(const m of cache.values())m.dispose();cache.clear();details.dispose();const geometries=new Set(),materials=new Set();extras.traverse(o=>{if(o.geometry)geometries.add(o.geometry);if(o.material)materials.add(o.material);});geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());extras.removeFromParent();for(const l of lights){l.removeFromParent();l.dispose?.();}}
  return {apply,dispose,audit:()=>({...details.audit(),materialCount:cache.size,styleLights:lights.length}),get current(){return current;},get materialCount(){return cache.size;}};
}

import * as THREE from 'three';
import {RoundedBoxGeometry} from 'three/addons/geometries/RoundedBoxGeometry.js';
import {roofSchemes} from './roof-schemes.js';

export function buildRoofStudy(id,{surface=(color,roughness=.9)=>new THREE.MeshStandardMaterial({color,roughness})}={}){
 const spec=roofSchemes[id];if(!spec)throw Error('Unknown roof study');
 const root=new THREE.Group();root.name='roof study '+id;root.rotation.x=.23;root.position.y=.8;
 const roles=Object.fromEntries(spec.roles.map(r=>{const g=new THREE.Group();g.name=r.id;g.userData.wallRole=r.id;root.add(g);return[r.id,g];}));
 const w=4,d=3.2;
 const steel=surface(0x48555e,.62);steel.metalness=.7;
 function mesh(geometry,material,x=0,y=0,z=0,group=roles.core){const o=new THREE.Mesh(geometry,material);o.position.set(x,y,z);o.castShadow=true;o.receiveShadow=true;group.add(o);return o;}
 if(id==='standing-seam'){
  const count=6,pw=w/count,shape=new THREE.Shape();
  for(const [i,p] of [[-pw/2,0],[pw/2-.035,0],[pw/2-.035,.095],[pw/2,.095],[pw/2,-.012],[-pw/2,-.012]].entries())i?shape.lineTo(...p):shape.moveTo(...p);shape.closePath();
  const g=new THREE.ExtrudeGeometry(shape,{depth:d,bevelEnabled:false,steps:1,curveSegments:1});
  for(let i=0;i<count;i++)mesh(g,steel,-w/2+pw*(i+.5),0,-d/2);
 }
 if(id==='metal-tile'){
  const g=new THREE.PlaneGeometry(w,d,96,56);g.rotateX(-Math.PI/2);const p=g.attributes.position;
  for(let i=0;i<p.count;i++){const x=p.getX(i),z=p.getZ(i),phase=((z+d/2)/.46)%1;const y=.055+.08*Math.cos(x/.56*Math.PI*2)+.055*(1-phase);p.setY(i,y);}g.computeVertexNormals();steel.side=THREE.DoubleSide;mesh(g,steel);
 }
 if(id==='bitumen-shingle'){
  steel.dispose();const m=surface(0x575249,1,'granules'),rows=7,cw=.58,cd=d/rows;m.metalness=0;m.envMapIntensity=.15;
  for(let row=0;row<rows;row++){
   let x=-w/2;let next=row%2?cw/2:cw;
   while(x<w/2-.001){const width=Math.min(next,w/2-x);mesh(new RoundedBoxGeometry(width-.008,.025,cd+.09,1,.004),m,x+width/2,.012*(rows-row),-d/2+cd*(row+.5));x+=width;next=cw;}
  }
 }
 // Dashed empty placeholders deliberately avoid inventing a support or membrane.
 function placeholder(group,color,y){
  const points=[[-w/2,y,-d/2],[w/2,y,-d/2],[w/2,y,d/2],[-w/2,y,d/2],[-w/2,y,-d/2]].map(p=>new THREE.Vector3(...p));
  const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineDashedMaterial({color,dashSize:.13,gapSize:.08}));line.computeLineDistances();group.add(line);
 }
 placeholder(roles.base,0x9e8a67,0);placeholder(roles.protection,0x6b9d98,0);
 const wood=surface(0xb79569);for(let i=0;i<5;i++)mesh(new RoundedBoxGeometry(.14,.2,d,1,.008),wood,-w/2+.15+(w-.3)*i/4,0,0,roles.structure);
 const bases={core:.55,base:.38,protection:.22,structure:0};const offsets={core:1.35,base:.85,protection:.4,structure:0};let progress=0;
 function spread(value){progress=THREE.MathUtils.clamp(value,0,1);for(const [key,g] of Object.entries(roles))g.position.y=bases[key]+offsets[key]*progress;root.updateMatrixWorld(true);}
 spread(0);
 function dispose(){const gs=new Set(),ms=new Set();root.traverse(o=>{if(o.geometry)gs.add(o.geometry);if(o.material)ms.add(o.material);});for(const g of gs)g.dispose();for(const m of ms)m.dispose();root.removeFromParent();}
 return{root,roles,spec,spread,dispose,get progress(){return progress;}};
}

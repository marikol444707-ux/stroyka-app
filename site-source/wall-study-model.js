import * as THREE from 'three';
import {RoundedBoxGeometry} from 'three/addons/geometries/RoundedBoxGeometry.js';
import {wallSchemes} from './wall-schemes.js';

export function buildWallStudy(id,{surface=(color,roughness=.9)=>new THREE.MeshStandardMaterial({color,roughness}),dimensions=null}={}){
  const spec=wallSchemes[id];if(!spec)throw new Error('Unknown wall study');
  const root=new THREE.Group();root.name='wall study '+id;
  const roles=Object.fromEntries(spec.roles.map(r=>{const g=new THREE.Group();g.name=r.id;g.userData.wallRole=r.id;root.add(g);return[r.id,g];}));
  const width=dimensions?.width??3.6,height=dimensions?.height??2.6,depth=dimensions?.depth??.5;
  const materials=new Map();const mat=(color)=>{if(!materials.has(color))materials.set(color,surface(color));return materials.get(color);};
  function box(group,w,h,d,x,y,z,color,bevel=.008){const o=new THREE.Mesh(new RoundedBoxGeometry(w,h,d,1,bevel),mat(color));o.position.set(x,y,z);o.castShadow=true;o.receiveShadow=true;group.add(o);return o;}
  box(roles.inside,width,height,.035,0,height/2,0,0xe9e4d6);
  function masonry(rows,cols,color){
    const cw=width/cols,ch=height/rows,gap=dimensions?.gap??.018;
    for(let row=0;row<rows;row++){
      let x=-width/2,first=row%2?cw/2:cw;
      while(x<width/2-.001){const w=Math.min(first,width/2-x);box(roles.core,w-gap,ch-gap,depth,x+w/2,ch*(row+.5),0,color,dimensions?.bevel??.012);x+=w;first=cw;}
    }
  }
  if(id==='aerated')masonry(dimensions?.aeratedRows??4,dimensions?.aeratedCols??3,0xcfcfc1);
  if(id==='brick')masonry(dimensions?.brickRows??11,dimensions?.brickCols??7,0x9c5f47);
  if(id==='ceramic'){
    const rows=dimensions?.ceramicRows??4,cols=dimensions?.ceramicCols??4,cw=width/cols,ch=height/rows,blockW=cw-(dimensions?.gap??.022),blockD=depth,shape=new THREE.Shape();
    shape.moveTo(-blockW/2,-blockD/2);shape.lineTo(blockW/2,-blockD/2);shape.lineTo(blockW/2,blockD/2);shape.lineTo(-blockW/2,blockD/2);shape.closePath();
    for(let col=0;col<5;col++)for(let row=0;row<2;row++){
      const mx=dimensions?blockW*.074:.065,mz=dimensions?blockD*.11:.055,x=-blockW/2+mx+col*(blockW-2*mx)/5,z=-blockD/2+mz+row*(blockD-2*mz)/2,w=(blockW-2*mx)/5-(dimensions?blockW*.04:.035),d=(blockD-2*mz)/2-(dimensions?blockD*.07:.035);
      const hole=new THREE.Path();hole.moveTo(x,z);hole.lineTo(x,z+d);hole.lineTo(x+w,z+d);hole.lineTo(x+w,z);hole.closePath();shape.holes.push(hole);
    }
    const geometry=new THREE.ExtrudeGeometry(shape,{depth:ch-(dimensions?.gap??.02),bevelEnabled:true,bevelSize:.004,bevelThickness:.004,bevelSegments:1,steps:1});geometry.rotateX(-Math.PI/2);
    for(let row=0;row<rows;row++)for(let col=0;col<cols;col++){const o=new THREE.Mesh(geometry,mat(0xbd7956));o.position.set(-width/2+cw*(col+.5),row*ch,0);o.castShadow=true;o.receiveShadow=true;roles.core.add(o);}
  }
  if(id==='frame'){
    const wood=0xad8860,fill=0xaaa77f,bar=dimensions?.bar??.16,stud=dimensions?.stud??.14,count=dimensions?.studCount??6;
    for(const y of [bar/2,height-bar/2])box(roles.core,width,bar,depth,0,y,0,wood);
    const step=(width-bar)/(count-1);
    for(let i=0;i<count;i++)box(roles.core,stud,height-2*bar,depth,-width/2+bar/2+i*step,height/2,0,wood);
    for(let i=0;i<count-1;i++)box(roles.core,step-stud-.01,height-2*bar-.04,depth*.8,-width/2+bar/2+step*(i+.5),height/2,0,fill,.022);
  }
  if(id==='concrete'){
    // A schematic reveal, not a rebar design or transparency claim about concrete.
    box(roles.core,width*.57,height,depth,-width*.215,height/2,0,0xadafa5,.014);
    const steel=new THREE.MeshStandardMaterial({color:0x685c50,metalness:.65,roughness:.6});
    function rod(a,b){const delta=b.clone().sub(a),o=new THREE.Mesh(new THREE.CylinderGeometry(.022*depth/.5,.022*depth/.5,delta.length(),8),steel);o.position.copy(a).add(b).multiplyScalar(.5);o.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),delta.normalize());o.castShadow=true;roles.core.add(o);}
    for(const z of [-depth*.28,depth*.28]){
      for(let i=0;i<4;i++){const x=(.35+i*.39)*width/3.6;rod(new THREE.Vector3(x,.1,z),new THREE.Vector3(x,height-.1,z));}
      for(let i=0;i<6;i++){const y=(.2+i*.43)*height/2.6;rod(new THREE.Vector3(.25*width/3.6,y,z),new THREE.Vector3(width/2-.12*width/3.6,y,z));}
    }
  }
  // Deliberately empty: no guessed insulation, membrane or facade assembly.
  const points=[[-width/2,0,0],[width/2,0,0],[width/2,height,0],[-width/2,height,0],[-width/2,0,0]].map(p=>new THREE.Vector3(...p));
  const outline=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineDashedMaterial({color:0x8c9e7a,dashSize:.13,gapSize:.09}));outline.computeLineDistances();roles.outside.add(outline);
  const bases={inside:-depth/2-.03,core:0,outside:depth/2+.08};let progress=0;
  function spread(value){progress=THREE.MathUtils.clamp(value,0,1);roles.inside.position.z=bases.inside-progress*1.35;roles.outside.position.z=bases.outside+progress*1.35;root.updateMatrixWorld(true);}
  spread(0);
  function dispose(){const gs=new Set(),ms=new Set();root.traverse(o=>{if(o.geometry)gs.add(o.geometry);if(o.material)ms.add(o.material);});for(const g of gs)g.dispose();for(const m of ms)m.dispose();root.removeFromParent();}
  return{root,roles,spec,spread,dispose,get progress(){return progress;}};
}

import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createNavigator} from './walk-navigation.js';
const data=JSON.parse(fs.readFileSync(new URL('./navigation.json',import.meta.url)));
const nav=createNavigator(data);
for(const r of data.rooms)assert.equal(nav.blocked(...r.point),false,'Spawn blocked: '+r.title);
const start=data.rooms[0].point;
for(const delta of [[100,0],[-100,0],[0,100],[0,-100],[100,100]]){
 const p=nav.move(start,...delta);assert(!nav.blocked(...p),'Collision/tunnelling');
 assert(p[0]>-6.85&&p[0]<6.85&&p[1]>-4.85&&p[1]<4.85,'Outer boundary');
}
// Actual bedroom partition: a large movement cannot pass its solid segment.
const wallStart=[-.75,1.8];assert(!nav.blocked(...wallStart));
const wallEnd=nav.move(wallStart,-3,0);assert(wallEnd[0]>-1.55,'Bedroom wall tunnelling');
// Find walkable paths from the living room through the real exported openings.
const step=.13,loX=-6.5,loZ=-4.5,nx=101,nz=71;
const cells=new Uint8Array(nx*nz);
for(let z=0;z<nz;z++)for(let x=0;x<nx;x++)cells[z*nx+x]=nav.blocked(loX+x*step,loZ+z*step)?1:0;
const gridPoint=p=>[Math.round((p[0]-loX)/step),Math.round((p[1]-loZ)/step)];
const [sx,sz]=gridPoint(start),queue=[[sx,sz]],seen=new Set([sz*nx+sx]);
for(let i=0;i<queue.length;i++){
 const [x,z]=queue[i];
 for(const [dx,dz] of [[1,0],[-1,0],[0,1],[0,-1]]){
  const xx=x+dx,zz=z+dz,key=zz*nx+xx;if(xx<0||xx>=nx||zz<0||zz>=nz||cells[key]||seen.has(key))continue;
  // Verify edges as well as cells; no diagonal jumps or thin-wall shortcuts.
  const p=[loX+x*step,loZ+z*step],end=nav.move(p,dx*step,dz*step);
  if(Math.hypot(end[0]-(loX+xx*step),end[1]-(loZ+zz*step))>.001)continue;
  seen.add(key);queue.push([xx,zz]);
 }
}
for(const r of data.rooms){const [x,z]=gridPoint(r.point);assert(seen.has(z*nx+x),'No physical walking path: '+r.title);}
console.log(JSON.stringify({passed:true,colliders:data.colliders.length,radius:nav.radius,connectedRooms:data.rooms.map(r=>r.id),reachableCells:seen.size,checks:['clear room spawns','large-step tunnelling','wall collision','outer boundary','physical paths to every room']},null,2));

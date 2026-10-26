import fs from 'node:fs';import assert from 'node:assert/strict';import crypto from 'node:crypto';import {createNavigator} from './walk-navigation.js';
const data=JSON.parse(fs.readFileSync(new URL('./navigation.json',import.meta.url))),previous=JSON.parse(fs.readFileSync(new URL('./previous-navigation.json',import.meta.url))),layout=JSON.parse(fs.readFileSync(new URL('./furniture-layout.json',import.meta.url))),nav=createNavigator(data);
assert.equal(data.modelSha256,crypto.createHash('sha256').update(fs.readFileSync(new URL('./stroyka-polished.glb',import.meta.url))).digest('hex'));
const isBed=n=>/^(bed base|mattress|pillow|headboard|bed soft duvet|bed foot throw|bedside)/.test(n);const oldMap=new Map(previous.colliders.map(c=>[c.name,c]));let unchanged=0;
for(const c of data.colliders)if(!isBed(c.name)){assert.deepEqual(c,oldMap.get(c.name),'Unrelated collider changed: '+c.name);unchanged++;}
for(const c of previous.colliders)if(!isBed(c.name))assert(data.colliders.some(n=>n.name===c.name),'Unrelated obstacle missing');
function roomForZ(z){return z>1.55?'bedroom1':z< -1.55?'bedroom3':'bedroom2';}
function center(c){return [0,1].map(i=>c.polygon.reduce((n,p)=>n+p[i],0)/c.polygon.length);}
function bounds(c){return [0,1].map(i=>[Math.min(...c.polygon.map(p=>p[i])),Math.max(...c.polygon.map(p=>p[i]))]);}
const result=[];
for(const b of layout.bedrooms){
 const members=data.colliders.filter(c=>roomForZ(center(c)[1])===b.id),one=prefix=>members.find(c=>c.name===prefix||new RegExp('^'+prefix+'\\.\\d+$').test(c.name));
 const head=one('headboard'),base=one('bed base'),pillow=members.filter(c=>c.name.startsWith('pillow')),throw_=one('bed foot throw');assert(head&&base&&throw_);const h=bounds(head),bb=bounds(base),sign=b.headDirection==='positive-z'?1:-1;
 assert.equal(pillow.length,b.id==='bedroom2'?1:2,'One full-sized pillow on the single bed');
 const edge=b.id==='bedroom1'?1.615:b.id==='bedroom2'?1.485:-1.615,gap=b.id==='bedroom1'?h[1][0]-edge:edge-h[1][1];assert(gap>.04&&gap<.09,'Headboard is next to solid partition, clear of its surface');
 for(const p of pillow)assert((center(p)[1]-b.center[1])*sign>.4,'Pillows remain at headboard end');assert((center(throw_)[1]-b.center[1])*sign<-.45,'Folded throw remains at foot');
 assert(Math.abs((bb[1][1]-bb[1][0])-2.05)<.001,'Bed length preserved');
 for(const c of members.filter(c=>isBed(c.name)))for(const [x,z] of c.polygon){assert(x> -6.87&&x< -1.865&&z>(b.id==='bedroom1'?1.615:b.id==='bedroom2'?-1.485:-4.87)&&z<(b.id==='bedroom1'?4.87:b.id==='bedroom2'?1.485:-1.615),'No bedroom part crosses an actual wall or opening');}
 const foot=[b.center[0],b.center[1]-sign*1.375],left=[-6.58,b.center[1]],right=[-4.35,b.center[1]];for(const p of [foot,left,right])assert(!nav.blocked(...p),'Clear approach to bed');
 const r=data.rooms.find(r=>r.id===b.id),dx=b.center[0]-r.point[0],dz=b.center[1]-r.point[1],distance=Math.hypot(dx,dz);assert(Math.abs(-Math.sin(r.yaw)-dx/distance)<1e-6&&Math.abs(-Math.cos(r.yaw)-dz/distance)<1e-6,'Initial walk view faces actual bed');assert(r.pitch<-.3&&r.pitch>-.5,'Natural downward bed view');
 const table=one('bedside');assert(Math.hypot(...center(table).map((v,i)=>v-b.bedside[i]))<1e-4,'Light anchor matches moved table');
 result.push({id:b.id,headboardGap:gap,foot,left,right,pillowCount:pillow.length});
}
// Physical access to foot and both sides; not just free isolated spawn points.
const step=.13,loX=-6.5,loZ=-4.5,nx=101,nz=71,toGrid=p=>[Math.round((p[0]-loX)/step),Math.round((p[1]-loZ)/step)],start=toGrid(data.rooms[0].point),queue=[start],seen=new Set([start[1]*nx+start[0]]);
for(let n=0;n<queue.length;n++){const [x,z]=queue[n];for(const [dx,dz] of [[1,0],[-1,0],[0,1],[0,-1]]){const xx=x+dx,zz=z+dz,key=zz*nx+xx;if(xx<0||xx>=nx||zz<0||zz>=nz||seen.has(key))continue;const p=[loX+x*step,loZ+z*step],q=[loX+xx*step,loZ+zz*step],end=nav.move(p,dx*step,dz*step);if(Math.hypot(end[0]-q[0],end[1]-q[1])>.001)continue;seen.add(key);queue.push([xx,zz]);}}
for(const room of result)for(const key of ['foot','left','right']){const [x,z]=toGrid(room[key]);assert(seen.has(z*nx+x),'Connected approach '+room.id+' '+key);}
const report={passed:true,rooms:result,unrelatedCollidersUnchanged:unchanged,colliders:data.colliders.length,reachableCells:seen.size,checks:['solid partition headboards with real bounds','full bed assemblies and bedside tables move together','single-bed pillow corrected','unrelated obstacles preserved','actual eye-height views face beds','nine bed approaches connected from living room','collision export hash matches current GLB'],ergonomicsApproved:false};fs.writeFileSync('bedroom-model-check.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));

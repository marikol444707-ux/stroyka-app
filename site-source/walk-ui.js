import {createLookMotion} from './walk-look-motion.js';
import {roomForPoint} from './room-navigation.js';
import {createNavigator} from './walk-navigation.js';
export function createWalkUI({camera,canvas,data,isActive,onChange,isReduced=()=>false}){
  const nav=createNavigator(data),abort=new AbortController(),options={signal:abort.signal};
  const look=createLookMotion();const keys=new Set();let yaw=0,pitch=0,point=[...nav.rooms[0].point],drag=null,lastRoom='living',entered=false;
  const roomSelect=document.querySelector('#walk-room');roomSelect.replaceChildren();
  for(const r of nav.rooms){const o=document.createElement('option');o.value=r.id;o.textContent=r.title;roomSelect.append(o);}
  function report(){
    camera.position.set(point[0],nav.eyeHeight+(data.floorHeight||0),point[1]);camera.rotation.set(pitch,yaw,0,'YXZ');
    const [x,z]=point;
    const room=roomForPoint(x,z);
    const info=nav.rooms.find(r=>r.id===room);lastRoom=room;
    document.querySelector('#walk-title').textContent=info.title;
    document.querySelector('#walk-description').textContent=info.description;
    roomSelect.value=room;
    const marker=document.querySelector('#walk-marker');marker.setAttribute('transform',`translate(${(x+7)*20} ${(z+5)*20}) rotate(${-yaw*180/Math.PI})`);
    onChange({x,z,yaw,pitch,room,eyeHeight:nav.eyeHeight});
  }
  function goRoom(id){
    const r=nav.rooms.find(r=>r.id===id);if(!r)return;
    if(nav.blocked(...r.point))throw Error('Room viewpoint obstructed');
    point=[...r.point];yaw=r.yaw;pitch=Number.isFinite(r.pitch)?Math.max(-1.05,Math.min(1.05,r.pitch)):0;look.reset(yaw,pitch);keys.clear();report();canvas.focus({preventScroll:true});
  }
  function advance(forward,right,distance){
    const len=Math.hypot(forward,right);if(!len)return;
    const dx=(-Math.sin(yaw)*forward+Math.cos(yaw)*right)*distance/len;
    const dz=(-Math.cos(yaw)*forward-Math.sin(yaw)*right)*distance/len;
    point=nav.move(point,dx,dz);report();
  }
  const bindings={KeyW:[1,0],ArrowUp:[1,0],KeyS:[-1,0],ArrowDown:[-1,0],KeyA:[0,-1],ArrowLeft:[0,-1],KeyD:[0,1],ArrowRight:[0,1]};
  const reset=()=>{look.reset(yaw,pitch);keys.clear();const id=drag?.id;drag=null;if(id!==undefined&&canvas.hasPointerCapture(id))canvas.releasePointerCapture(id);};
  window.addEventListener('keydown',e=>{
    if(!isActive()||/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)||e.target.isContentEditable)return;
    if(bindings[e.code]){e.preventDefault();keys.add(e.code);}
  },options);
  window.addEventListener('keyup',e=>keys.delete(e.code),options);
  window.addEventListener('blur',reset,options);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)reset();},options);
  canvas.tabIndex=0;
  canvas.addEventListener('pointerdown',e=>{if(!isActive())return;drag={id:e.pointerId,x:e.clientX,y:e.clientY};canvas.setPointerCapture(e.pointerId);canvas.focus({preventScroll:true});},options);
  canvas.addEventListener('pointermove',e=>{
    if(!isActive()||!drag||drag.id!==e.pointerId)return;
    look.aim(e.clientX-drag.x,e.clientY-drag.y,{reduced:isReduced()});
    if(isReduced()){const pose=look.sample();yaw=pose.yaw;pitch=pose.pitch;report();}
    drag.x=e.clientX;drag.y=e.clientY;
  },options);
  for(const event of ['pointerup','lostpointercapture'])canvas.addEventListener(event,()=>{drag=null;},options);canvas.addEventListener('pointercancel',reset,options);
  for(const button of document.querySelectorAll('[data-walk-key]')){
    let downAt=0;
    button.addEventListener('pointerdown',e=>{if(!isActive())return;e.preventDefault();downAt=performance.now();keys.add(button.dataset.walkKey);button.setPointerCapture(e.pointerId);},options);
    for(const event of ['pointerup','pointercancel','lostpointercapture'])button.addEventListener(event,()=>keys.delete(button.dataset.walkKey),options);
    button.addEventListener('click',e=>{if(isActive()&&(e.detail===0||performance.now()-downAt<180)){const [f,r]=bindings[button.dataset.walkKey];advance(f,r,.28);}},options);
  }
  roomSelect.addEventListener('change',()=>{if(isActive())goRoom(roomSelect.value);},options);
  return {
    enter(id){if(id&&nav.rooms.some(r=>r.id===id))goRoom(id);else if(!entered)goRoom(lastRoom);else{reset();report();canvas.focus({preventScroll:true});}entered=true;},leave:reset,get hasEntered(){return entered;},readPose:()=>({point:[...point],yaw,pitch,room:lastRoom}),readLook:()=>look.sample(),
    update(dt){if(!isActive())return;if(look.update(dt,{reduced:isReduced()})){const pose=look.sample();yaw=pose.yaw;pitch=pose.pitch;report();}let f=0,r=0;for(const key of keys){const v=bindings[key];if(v){f+=v[0];r+=v[1];}}if(f||r)advance(f,r,Math.min(.12,dt)*1.45);},
    dispose(){reset();abort.abort();}
  };
}

import * as THREE from 'three';
import {buildWallStudy} from './wall-study-model.js';
import {ease,sampleEnter,sampleExit,enterSeconds,exitSeconds} from './scene-journey.js';

export function createWallStudyView({renderer,scene,camera,controls,house,markDirty,getHouseHelper,onResize,onLightingView=()=>{},syncHouseVisibility=()=>{},reduced,prefix="wall",buildModel=buildWallStudy,cameraPose=[5.6,3.8,6.5],viewLabel="Учебная 3D-схема выбранной стены без масштаба. Вращайте фрагмент или выбирайте части кнопками."}){
  const $=s=>document.querySelector(s.replaceAll('#wall-','#'+prefix+'-')),abort=new AbortController(),options={signal:abort.signal};
  const qaKey='__'+prefix.toUpperCase()+'_LAB_STATUS__',roleAttr='data-'+prefix+'-role',host=$('#wall-lab-viewport'),canvas=renderer.domElement;
  const pivot=new THREE.Vector3(0,1.4,0),anchor=prefix==='roof'?{position:new THREE.Vector3(11,9,11),target:new THREE.Vector3(1,3.5,0),fov:33}:{position:new THREE.Vector3(13.5,4.3,-5),target:new THREE.Vector3(7,1.5,-1.35),fov:34};
  let model=null,saved=null,helper=null,selected='core',fraction=.65,tween=null,lastLightsRestored=true,motion=null,returnCallback=null,view='study';
  const animatedNames=['04_ceiling','05_roof','14_rafters','15_roof_underlay','16_roof_battens','09_wall_core','10_insulation','11_vent_gap','12_cladding','13_inner_finish'];
  const textureCanvas=document.createElement('canvas');textureCanvas.width=textureCanvas.height=128;
  const ctx=textureCanvas.getContext('2d'),pixels=ctx.createImageData(128,128);let seed=37;
  for(let i=0;i<pixels.data.length;i+=4){seed=(seed*1664525+1013904223)>>>0;const c=232+(seed/4294967296)*23;pixels.data[i]=pixels.data[i+1]=pixels.data[i+2]=c;pixels.data[i+3]=255;}ctx.putImageData(pixels,0,0);
  const texture=new THREE.CanvasTexture(textureCanvas);texture.colorSpace=THREE.SRGBColorSpace;texture.wrapS=texture.wrapT=THREE.RepeatWrapping;texture.repeat.set(3,3);
  const grainCanvas=document.createElement('canvas');grainCanvas.width=grainCanvas.height=128;const grainCtx=grainCanvas.getContext('2d'),grainPixels=grainCtx.createImageData(128,128);
  for(let i=0;i<grainPixels.data.length;i+=4){seed=(seed*1664525+1013904223)>>>0;const c=95+(seed/4294967296)*160;grainPixels.data[i]=grainPixels.data[i+1]=grainPixels.data[i+2]=c;grainPixels.data[i+3]=255;}grainCtx.putImageData(grainPixels,0,0);
  const grainTexture=new THREE.CanvasTexture(grainCanvas);grainTexture.colorSpace=THREE.SRGBColorSpace;grainTexture.wrapS=grainTexture.wrapT=THREE.RepeatWrapping;grainTexture.repeat.set(2,2);
  function flushOrbit(){const damping=controls.enableDamping;controls.enableDamping=false;controls.update();controls.enableDamping=damping;}
  function surface(color,roughness=.93,kind='plain'){const map=kind==='granules'?grainTexture:texture;return new THREE.MeshStandardMaterial({color,roughness,map,bumpMap:map,bumpScale:kind==='granules'?.018:.007});}

  const prefersReduced=()=>matchMedia(reduced.media||'(prefers-reduced-motion: reduce)').matches;
  function coreStats(){let meshes=0,vertices=0;model?.roles.core.traverse(o=>{if(o.isMesh){meshes++;vertices+=o.geometry.attributes.position.count;}});return{coreMeshes:meshes,coreVertices:vertices};}
  function report(){
    if(!model){window[qaKey]={open:false,assemblyChanged:false,houseLightsRestored:lastLightsRestored,motion:null};return;}
    window[qaKey]={open:true,material:model.spec.id,spread:fraction,selectedRole:selected,...coreStats(),scale:null,assemblyChanged:false,houseLightCount:saved.lights.length,housePointLightCount:saved.lights.filter(([l])=>l.isPointLight).length,houseAreaLightCount:saved.lights.filter(([l])=>l.isRectAreaLight).length,houseLightsSuppressed:saved.lights.every(([l])=>!l.visible),motion:motion?{direction:motion.direction,phase:motion.sample.phase,progress:motion.progress,paused:motion.paused,view}:null};
  }
  function clearHelper(){if(helper){scene.remove(helper);helper.geometry.dispose();helper.material.dispose();helper=null;}}
  function selectRole(id){
    if(!model||!model.roles[id])return;selected=id;clearHelper();helper=new THREE.BoxHelper(model.roles[id],0xb96d3b);helper.material.transparent=true;helper.material.opacity=.45;helper.visible=view==='study';scene.add(helper);
    for(const b of document.querySelectorAll('['+roleAttr+']'))b.setAttribute('aria-pressed',String(b.getAttribute(roleAttr)===id));
    $('#wall-lab-caption').textContent=model.spec.roles.find(r=>r.id===id).description;report();markDirty();
  }
  function spread(value){fraction=THREE.MathUtils.clamp(value,0,1);if(!model)return;model.spread(fraction);if(helper)helper.setFromObject(model.roles[selected]);$('#wall-lab-spread').value=Math.round(fraction*100);$('#wall-lab-progress').textContent=Math.round(fraction*100)+'%';$('#wall-lab-toggle').textContent=fraction>.5?'Собрать фрагмент':'Разнести части';renderer.shadowMap.needsUpdate=true;report();markDirty();}
  function setView(next){
    const changed=view!==next;view=next;host.dataset.view=next;if(!saved)return;house.visible=next==='house'&&saved.houseVisible;model.root.visible=next==='study';if(helper)helper.visible=next==='study';
    for(const [light,visible] of saved.lights)light.visible=next==='study'?false:visible;onLightingView(next==='study');
    if(changed)renderer.shadowMap.needsUpdate=true;
  }
  function lock(value){
    controls.enabled=value?false:saved?.enabled??true;host.dataset.motion=String(value);$('#wall-journey-hud').hidden=!value;
    for(const b of [$('#wall-lab-spread'),$('#wall-lab-toggle'),...document.querySelectorAll('['+roleAttr+']')])b.disabled=value;
    $('#wall-options').disabled=!!motion&&motion.direction==='exit';
  }
  function arc(from,to,t){
    const a=new THREE.Spherical().setFromVector3(from.clone().sub(pivot)),b=new THREE.Spherical().setFromVector3(to.clone().sub(pivot));
    const delta=Math.atan2(Math.sin(b.theta-a.theta),Math.cos(b.theta-a.theta));
    const s=new THREE.Spherical(THREE.MathUtils.lerp(a.radius,b.radius,t),THREE.MathUtils.lerp(a.phi,b.phi,t),a.theta+delta*t);return new THREE.Vector3().setFromSpherical(s).add(pivot);
  }
  function pose(position,target,fov){camera.position.copy(position);controls.target.copy(target);camera.fov=fov;camera.lookAt(target);camera.updateProjectionMatrix();markDirty();}
  function diagramPose(){pose(new THREE.Vector3(...cameraPose),new THREE.Vector3(0,1.25,0),35);controls.minDistance=4;controls.maxDistance=16;}
  function hud(s){
    const returning=motion.direction==='exit',part=prefix==='roof'?'Кровля дома':'Стена дома';
    const write=(node,text)=>{if(node.textContent!==text)node.textContent=text;};
    write($('#wall-journey-title'),s.phase==='assemble'?'Собираем фрагмент':s.phase==='pullback'?'Возвращаемся к дому':s.phase==='unfold'?'Раскрываем слои':s.view==='house'?part:'От узла — к устройству');
    write($('#wall-journey-caption'),s.view==='house'?'Объём дома и выбранная часть.': 'Учебная схема материала · без масштаба.');
    write($('#wall-journey-skip'),returning?'Вернуться сразу':'Перейти к слоям');
  }
  function applyMotion(){
    if(!motion||!saved)return;const m=motion,s=m.direction==='enter'?sampleEnter(m.progress):sampleExit(m.progress,m.fromHouse);m.sample=s;
    setView(s.view);$('#wall-journey-veil').style.opacity=String(s.veil);hud(s);
    if(m.direction==='enter'){
      if(s.view==='house')pose(arc(saved.position,anchor.position,s.camera),saved.target.clone().lerp(anchor.target,s.camera),THREE.MathUtils.lerp(saved.fov,anchor.fov,s.camera));
      else{diagramPose();spread(m.revealTo*s.spread);}
    }else if(m.fromHouse){
      pose(arc(m.position,saved.position,s.camera),m.target.clone().lerp(saved.target,s.camera),THREE.MathUtils.lerp(m.fov,saved.fov,s.camera));
    }else if(s.view==='study'){
      spread(m.fromSpread*s.spread);pose(m.position.clone().lerp(new THREE.Vector3(...cameraPose),ease(Math.min(1,m.progress/.26))),m.target.clone().lerp(new THREE.Vector3(0,1.25,0),ease(Math.min(1,m.progress/.26))),35);
    }else pose(arc(anchor.position,saved.position,s.camera),anchor.target.clone().lerp(saved.target,s.camera),THREE.MathUtils.lerp(anchor.fov,saved.fov,s.camera));
    report();markDirty();
  }
  function ready(){
    if(!saved)return;const revealTo=motion?.revealTo??fraction;motion=null;returnCallback=null;$('#wall-journey-veil').style.opacity='0';setView('study');diagramPose();spread(revealTo);lock(false);report();
  }
  function finishReturn(){const callback=returnCallback;returnCallback=null;close();callback?.();}
  function open(id){
    const first=!saved;
    if(first){
      flushOrbit();saved={position:camera.position.clone(),target:controls.target.clone(),fov:camera.fov,zoom:camera.zoom,minDistance:controls.minDistance,maxDistance:controls.maxDistance,enabled:controls.enabled,houseVisible:house.visible,helperVisible:getHouseHelper()?.visible,label:canvas.getAttribute('aria-label'),lights:[],visibility:[],positions:[]};
      scene.traverse(o=>{if(o.isPointLight||o.userData.houseLighting)saved.lights.push([o,o.visible]);});house.traverse(o=>saved.visibility.push([o,o.visible]));
      for(const name of animatedNames){const o=house.getObjectByName(name);if(o){saved.positions.push([o,o.position.clone()]);o.position.set(0,0,0);o.visible=true;}}
      house.traverse(o=>{if(/^(south[_ ]facade|east[_ ]facade|pergola)/.test(o.name))o.visible=true;});syncHouseVisibility();house.updateMatrixWorld(true);
      if(getHouseHelper())getHouseHelper().visible=false;host.append(canvas);canvas.setAttribute('aria-label',viewLabel);controls.minDistance=4;controls.maxDistance=65;
    }
    if(model?.spec.id===id)return;
    clearHelper();model?.dispose();model=buildModel(id,{surface});scene.add(model.root);tween=null;$('#wall-lab-title').textContent=model.spec.title;document.querySelector('['+roleAttr+'=core]').textContent=model.spec.core;
    if(first&&!prefersReduced()){motion={direction:'enter',progress:0,revealTo:fraction>.05?fraction:.75,paused:false,sample:sampleEnter(0)};lock(true);applyMotion();}
    else if(motion)applyMotion();else{setView('study');if(first)diagramPose();spread(fraction);lock(false);}
    selectRole('core');onResize();renderer.shadowMap.needsUpdate=true;markDirty();
  }
  function close(){
    if(!saved)return;motion=null;returnCallback=null;tween=null;clearHelper();model?.dispose();model=null;lock(false);$('#wall-journey-veil').style.opacity='0';delete host.dataset.view;
    flushOrbit();$('#canvas').append(canvas);for(const [o,visible] of saved.visibility)o.visible=visible;for(const [o,position] of saved.positions)o.position.copy(position);house.visible=saved.houseVisible;syncHouseVisibility();house.updateMatrixWorld(true);if(getHouseHelper())getHouseHelper().visible=saved.helperVisible;
    for(const [light,visible] of saved.lights)light.visible=visible;onLightingView(false);lastLightsRestored=saved.lights.every(([light,visible])=>light.visible===visible);
    pose(saved.position,saved.target,saved.fov);camera.zoom=saved.zoom;controls.minDistance=saved.minDistance;controls.maxDistance=saved.maxDistance;controls.enabled=saved.enabled;canvas.setAttribute('aria-label',saved.label||'Трёхмерная модель дома');saved=null;onResize();renderer.shadowMap.needsUpdate=true;report();markDirty();
  }
  function returnHome(done){
    if(!saved){done?.();return;}if(prefersReduced()){close();done?.();return;}if(motion?.direction==='exit')return;
    flushOrbit();returnCallback=done;motion={direction:'exit',progress:0,fromHouse:view==='house',fromSpread:fraction,position:camera.position.clone(),target:controls.target.clone(),fov:camera.fov,paused:false,sample:sampleExit(0,view==='house')};tween=null;controls.maxDistance=65;lock(true);applyMotion();
  }
  $('#wall-journey-skip').addEventListener('click',()=>{if(motion?.direction==='exit')finishReturn();else if(motion)ready();},options);
  reduced.addEventListener('change',()=>{if(prefersReduced()&&motion){if(motion.direction==='exit')finishReturn();else ready();}},options);
  $('#wall-lab-spread').addEventListener('input',e=>{if(motion)return;tween=null;spread(Number(e.target.value)/100);},options);
  $('#wall-lab-toggle').addEventListener('click',()=>{if(motion)return;const to=fraction>.5?0:1;if(prefersReduced())spread(to);else tween={from:fraction,to,elapsed:0};},options);
  for(const b of document.querySelectorAll('['+roleAttr+']'))b.addEventListener('click',()=>{if(!motion)selectRole(b.getAttribute(roleAttr));},options);
  let down=null;const ray=new THREE.Raycaster(),pointer=new THREE.Vector2();ray.params.Line.threshold=.05;
  canvas.addEventListener('pointerdown',e=>{down=[e.clientX,e.clientY];},options);canvas.addEventListener('pointercancel',()=>down=null,options);
  canvas.addEventListener('pointerup',e=>{if(!saved||!down||motion)return;const distance=Math.hypot(e.clientX-down[0],e.clientY-down[1]);down=null;if(distance>6)return;const rect=canvas.getBoundingClientRect();pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);ray.setFromCamera(pointer,camera);const hit=ray.intersectObject(model.root,true)[0];if(!hit)return;let o=hit.object;while(o&&!o.userData.wallRole)o=o.parent;if(o)selectRole(o.userData.wallRole);},options);
  function update(dt){
    if(!saved)return;
    // Read the current preference as well as listening for changes: browsers may
    // defer media-query events while a visual frame is paused or backgrounded.
    if(motion&&prefersReduced()){if(motion.direction==='exit')finishReturn();else ready();return;}
    if(motion){if(!motion.paused){motion.progress=Math.min(1,motion.progress+Math.min(dt,.12)/(motion.direction==='enter'?enterSeconds:exitSeconds));applyMotion();if(motion.progress===1){if(motion.direction==='enter')ready();else finishReturn();}}return;}
    if(tween){tween.elapsed+=Math.min(dt,.1);const t=Math.min(1,tween.elapsed/.7);spread(prefersReduced()?tween.to:THREE.MathUtils.lerp(tween.from,tween.to,ease(t)));if(t===1||prefersReduced())tween=null;}
  }
  return{open,close,returnHome,update,get active(){return!!saved;},get busy(){return!!motion;},seekMotion(progress){if(motion){motion.paused=true;motion.progress=Math.min(1,Math.max(0,progress));applyMotion();}},resumeMotion(){if(motion){motion.paused=false;report();}},dispose(){close();abort.abort();texture.dispose();grainTexture.dispose();}};
}

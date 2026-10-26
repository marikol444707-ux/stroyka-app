import * as THREE from 'three';

const clamp=v=>Math.max(0,Math.min(1,v));
const ease=v=>{const t=clamp(v);return t*t*(3-2*t);};
const between=(t,a,b)=>ease((t-a)/(b-a));
export const buildSteps=[
  {at:0,title:'Из замысла — в дом',caption:'Начинаем с предложенной планировки. Комнаты и размеры ещё предстоит согласовать.'},
  {at:.14,title:'Основание дома',caption:'В эскизе показано условное основание. Его тип выбирают после изучения участка и расчёта.'},
  {at:.28,title:'Стены и комнаты',caption:'Линии плана становятся объёмом. Видны настоящие проёмы и расположение помещений этой модели.'},
  {at:.50,title:'Перекрытие и стропила',caption:'Появляются перекрытие и несущие элементы кровли. Сечения и соединения здесь не рассчитаны.'},
  {at:.66,title:'Дом получает кровлю',caption:'Показан предлагаемый вариант — фальцевая стальная кровля. Спецификацию покрытия ещё нужно выбрать.'},
  {at:.82,title:'Фасад, свет и интерьер',caption:'Добавляем остекление, деревянные детали, террасу и предложенное оформление помещений.'},
  {at:.98,title:'Теперь дом можно изучать',caption:'Разберите слои, снимите кровлю или зайдите внутрь. Это один и тот же дом.'}
];

export function createConstructionStory({house,scene,renderer,camera,controls,getRoofTitle=()=>'Фальцевая стальная кровля',onUpdate,onComplete}){
  const wireGroup=new THREE.Group();wireGroup.name='construction drawing';scene.add(wireGroup);wireGroup.visible=false;
  house.updateMatrixWorld(true);
  // Derive the drawing from the actual walls, including their real openings.
  const linePositions=[];
  for(const groupName of ['03_walls','09_wall_core'])house.getObjectByName(groupName).traverse(o=>{
    if(!o.isMesh)return;
    const edge=new THREE.EdgesGeometry(o.geometry,35);const pos=edge.getAttribute('position');
    for(let i=0;i<pos.count;i++){const v=new THREE.Vector3().fromBufferAttribute(pos,i).applyMatrix4(o.matrixWorld);linePositions.push(v.x,v.y,v.z);}
    edge.dispose();
  });
  const originalWire=new Float32Array(linePositions);
  const wireGeometry=new THREE.BufferGeometry();wireGeometry.setAttribute('position',new THREE.Float32BufferAttribute(originalWire.slice(),3));
  const wireMaterial=new THREE.LineBasicMaterial({color:0x365d6c,transparent:true,opacity:.9,depthWrite:false});
  const wire=new THREE.LineSegments(wireGeometry,wireMaterial);wire.frustumCulled=false;wireGroup.add(wire);
  const paper=new THREE.Mesh(new THREE.PlaneGeometry(16,12),new THREE.MeshBasicMaterial({color:0xf7f6ec,transparent:true,depthWrite:false}));
  paper.rotation.x=-Math.PI/2;paper.position.y=-.339;wireGroup.add(paper);
  const foundationBox=new THREE.Box3().setFromObject(house.getObjectByName('01_foundation'));
  const foundationSize=foundationBox.getSize(new THREE.Vector3()),foundationCentre=foundationBox.getCenter(new THREE.Vector3());
  const cap=new THREE.Mesh(new THREE.PlaneGeometry(foundationSize.x,foundationSize.z),new THREE.MeshStandardMaterial({color:0x99998e,roughness:.95}));
  cap.rotation.x=-Math.PI/2;cap.position.set(foundationCentre.x,0,foundationCentre.z);cap.visible=false;cap.receiveShadow=true;wireGroup.add(cap);
  const ranges={foundation:[.14,.28],walls:[.28,.50],ceiling:[.50,.58],rafters:[.55,.66],underlay:[.66,.71],battens:[.70,.75],roof:[.74,.82],finish:[.82,.98]};
  function classify(o){
    if(o.userData.facadeFinish)return 'finish';
    let group=o;while(group.parent&&group.parent!==house)group=group.parent;
    const name=group.name;
    if(name==='01_foundation')return 'foundation';
    if(name==='02_structure'||name==='04_ceiling')return 'ceiling';
    if(name==='14_rafters')return 'rafters';
    if(name==='15_roof_underlay')return 'underlay';
    if(name==='16_roof_battens')return 'battens';
    if(name==='05_roof')return 'roof';
    if(['09_wall_core','10_insulation','11_vent_gap','13_inner_finish'].includes(name))return 'walls';
    if(name==='03_walls'){
      const mats=Array.isArray(o.material)?o.material:[o.material];
      return mats.some(m=>/glass|anthracite|light oak/.test(m.name))?'finish':'walls';
    }
    return 'finish';
  }
  let active=false,playing=false,progress=0,entries=[],materials=new Map(),planes={},bounds={},previousClipping=false,previousControls=true;
  let lastRestored=true;
  function snapshot(){
    entries=[];materials=new Map();planes={};bounds={};lastRestored=false;
    house.traverse(o=>{
      if(!o.isMesh)return;
      const phase=classify(o),box=new THREE.Box3().setFromObject(o);
      if(!bounds[phase])bounds[phase]=[box.min.y,box.max.y];
      else{bounds[phase][0]=Math.min(bounds[phase][0],box.min.y);bounds[phase][1]=Math.max(bounds[phase][1],box.max.y);}
      entries.push({object:o,phase,original:o.material,visible:o.visible});
    });
    for(const phase of Object.keys(ranges))planes[phase]=new THREE.Plane(new THREE.Vector3(0,-1,0),-1);
    for(const e of entries){
      const array=Array.isArray(e.original),source=array?e.original:[e.original];
      const clones=source.map(original=>{
        const key=e.phase+':'+original.uuid;
        if(!materials.has(key)){
          const m=original.clone();m.onBeforeCompile=original.onBeforeCompile;
          m.customProgramCacheKey=()=>original.customProgramCacheKey();
          m.clippingPlanes=[planes[e.phase]];m.clipShadows=true;materials.set(key,m);
        }return materials.get(key);
      });e.object.material=array?clones:clones[0];
    }
  }
  function audit(){return {active,playing,progress,clipping:renderer.localClippingEnabled,restored:lastRestored,materialsRestored:entries.every(e=>e.object.material===e.original),visibleByPhase:Object.fromEntries(Object.keys(ranges).map(k=>[k,entries.filter(e=>e.phase===k&&e.object.visible).length])),clippingHeight:Object.fromEntries(Object.entries(planes).map(([k,p])=>[k,p.constant])),wireVertices:originalWire.length/3};}
  function notify(){
    let index=0;for(let i=0;i<buildSteps.length;i++)if(progress>=buildSteps[i].at)index=i;
    const step={...buildSteps[index]};if(index===4)step.caption='Внешний вид покрытия: '+getRoofTitle()+'. Полный состав и применимость ещё нужно проверить.';onUpdate({active,playing,progress,index,...step},audit());
  }
  function seek(value){
    if(!active)return;
    progress=clamp(value);
    for(const [phase,[a,b]] of Object.entries(ranges)){
      const amount=between(progress,a,b),bound=bounds[phase];
      if(bound)planes[phase].constant=THREE.MathUtils.lerp(bound[0]-.025,bound[1]+.025,amount);
      for(const e of entries)if(e.phase===phase)e.object.visible=e.visible&&amount>0;
    }
    const growth=between(progress,.20,.47),attribute=wireGeometry.getAttribute('position');
    for(let i=0;i<attribute.count;i++)attribute.setY(i,THREE.MathUtils.lerp(-.335,originalWire[i*3+1]+.006,growth));
    attribute.needsUpdate=true;
    wireMaterial.opacity=.92*(1-between(progress,.43,.62));
    paper.material.opacity=1-between(progress,.14,.28);paper.visible=progress<.28;
    cap.visible=progress>.14&&progress<.28;
    if(cap.visible)cap.position.y=Math.min(foundationBox.max.y,planes.foundation.constant)+.001;
    wireGeometry.setDrawRange(0,Math.min(attribute.count,2*Math.floor(attribute.count*Math.max(.03,between(progress,0,.14))/2)));
    wireGroup.visible=progress<.62;
    const cameraT=between(progress,.14,.94);
    camera.position.lerpVectors(new THREE.Vector3(14,24,17),new THREE.Vector3(18,9,22),cameraT);
    controls.target.lerpVectors(new THREE.Vector3(0,.1,1),new THREE.Vector3(0,1.4,3),cameraT);camera.lookAt(controls.target);
    renderer.shadowMap.needsUpdate=true;notify();
  }
  function cancel(){
    if(!active)return;
    active=false;playing=false;
    for(const e of entries){e.object.material=e.original;e.object.visible=e.visible;}
    for(const m of materials.values())m.dispose();materials.clear();
    renderer.localClippingEnabled=previousClipping;controls.enabled=previousControls;
    wireGroup.visible=false;renderer.shadowMap.needsUpdate=true;lastRestored=true;notify();
  }
  return {
    get active(){return active;},get playing(){return playing;},audit,
    start({autoplay=true}={}){cancel();previousClipping=renderer.localClippingEnabled;previousControls=controls.enabled;snapshot();active=true;playing=autoplay;renderer.localClippingEnabled=true;controls.enabled=false;seek(0);},
    seek(value){playing=false;seek(value);},
    pause(){if(active){playing=false;notify();}},
    toggle(){if(!active)return;if(progress>=1)seek(0);playing=!playing;notify();},
    update(dt,reduced){if(!active||!playing)return;if(reduced){playing=false;notify();return;}seek(progress+dt/10);if(progress>=1){cancel();onComplete();}},
    cancel,
    dispose(){cancel();scene.remove(wireGroup);wireGeometry.dispose();wireMaterial.dispose();paper.geometry.dispose();paper.material.dispose();cap.geometry.dispose();cap.material.dispose();}
  };
}

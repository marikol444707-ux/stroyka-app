import * as THREE from 'three';
import {EffectComposer} from 'three/addons/postprocessing/EffectComposer.js';
import {RenderPass} from 'three/addons/postprocessing/RenderPass.js';
import {GTAOPass} from 'three/addons/postprocessing/GTAOPass.js';
import {OutputPass} from 'three/addons/postprocessing/OutputPass.js';
import {ShaderPass} from 'three/addons/postprocessing/ShaderPass.js';
import {FXAAShader} from 'three/addons/shaders/FXAAShader.js';

// This view has a fixed daylight solution. Contact occlusion is a screen-space
// approximation; sunlight shadows are calculated from actual house geometry.
export function createDaylightPipeline(renderer,scene,camera,model){
 renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.VSMShadowMap;renderer.shadowMap.autoUpdate=false;renderer.shadowMap.needsUpdate=true;
 const sun=new THREE.DirectionalLight(0xfff0d8,1.7);sun.name='window sunlight with real geometry shadows';sun.position.set(-2,5,10);sun.target.position.set(4.5,.4,2.8);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);Object.assign(sun.shadow.camera,{left:-5,right:5,top:5,bottom:-5,near:.5,far:20});sun.shadow.bias=-.0001;sun.shadow.normalBias=.003;sun.shadow.radius=4;sun.shadow.blurSamples=8;scene.add(sun,sun.target);
 const glass=[];model.traverse(o=>{if(!o.isMesh)return;if(o.material.name==='glass'){glass.push(o);o.layers.set(1);o.castShadow=false;}else{o.castShadow=o.visible;o.receiveShadow=o.visible;}});camera.layers.enable(1);
 const composer=new EffectComposer(renderer);const base=new RenderPass(scene,camera),ao=new GTAOPass(scene,camera,1,1,undefined,{radius:.20,distanceExponent:1.5,thickness:.35,distanceFallOff:1.0,scale:1,samples:16},{radius:5,lumaPhi:10,depthPhi:2,normalPhi:3});ao.blendIntensity=.75;
 // Transparent glazing must not become an opaque depth occluder in GTAO.
 const normalRender=ao.renderOverride.bind(ao);ao.renderOverride=(...args)=>{const mask=camera.layers.mask;camera.layers.disable(1);try{return normalRender(...args);}finally{camera.layers.mask=mask;}};
 const output=new OutputPass(),fxaa=new ShaderPass(FXAAShader);composer.addPass(base);composer.addPass(ao);composer.addPass(output);composer.addPass(fxaa);
 let closed=false;
 return {render(){if(!closed)composer.render();},resize(width,height){if(closed)return;composer.setSize(width,height);const ratio=renderer.getPixelRatio();fxaa.uniforms.resolution.value.set(1/(width*ratio),1/(height*ratio));},audit(){return{contactOcclusion:true,transparentGlassExcludedFromAO:glass.length,staticShadowCache:!renderer.shadowMap.autoUpdate,sunShadowMapSize:sun.shadow.mapSize.x,screenSpaceApproximation:true,shadowTextureReady:!!sun.shadow.map?.texture,glassCameraLayerRestored:camera.layers.isEnabled(1),shaderProgramsValid:renderer.info.programs.every(p=>p.diagnostics?.runnable!==false),postprocessing:composer.passes.length};},dispose(){if(closed)return;closed=true;for(const pass of composer.passes)pass.dispose?.();ao.gtaoMaterial.dispose();ao.blendMaterial.dispose();ao.depthTexture.dispose();composer.dispose();sun.shadow.map?.dispose();sun.shadow.mapPass?.dispose();scene.remove(sun,sun.target);}};
}

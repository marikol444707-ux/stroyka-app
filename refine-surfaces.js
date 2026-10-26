import * as THREE from 'three';
// Authored tileable wool maps. These are procedural material details, not scans.
export function refineSurfaces(model){
 const size=512,height=new Float32Array(size*size),rgb=new Uint8Array(size*size*4),norm=new Uint8Array(size*size*4),rough=new Uint8Array(size*size*4);let seed=301;
 const random=()=>{seed=(1664525*seed+1013904223)>>>0;return seed/4294967296;};
 for(let y=0;y<size;y++)for(let x=0;x<size;x++){const i=y*size+x,u=x/size*Math.PI*2*48,v=y/size*Math.PI*2*48,loop=Math.sin(u+Math.sin(v)*.4)*Math.cos(v),noise=random();height[i]=loop*.35+noise*.12;const c=Math.round(205+loop*10+(noise-.5)*16);rgb.set([c,c-2,c-5,255],i*4);const r=Math.round(228+(noise-.5)*24);rough.set([r,r,r,255],i*4);}
 for(let y=0;y<size;y++)for(let x=0;x<size;x++){const i=y*size+x,dx=height[y*size+(x+1)%size]-height[y*size+(x+size-1)%size],dy=height[((y+1)%size)*size+x]-height[((y+size-1)%size)*size+x],n=new THREE.Vector3(-dx*.65,-dy*.65,1).normalize();norm.set([Math.round((n.x*.5+.5)*255),Math.round((n.y*.5+.5)*255),Math.round((n.z*.5+.5)*255),255],i*4);}
 const texture=(data,color=false)=>{const t=new THREE.DataTexture(data,size,size);t.wrapS=t.wrapT=THREE.RepeatWrapping;t.repeat.set(12,9);t.colorSpace=color?THREE.SRGBColorSpace:THREE.NoColorSpace;t.generateMipmaps=true;t.minFilter=THREE.LinearMipmapLinearFilter;t.magFilter=THREE.LinearFilter;t.needsUpdate=true;return t;};
 const wool=texture(rgb,true),normal=texture(norm),roughness=texture(rough);let rugs=0,wood=0,stone=0,velvet=0;
 model.traverse(o=>{if(!o.isMesh)return;const m=o.material;
 if(m.name==='studio undyed wool rug'){m.map=wool;m.normalMap=normal;m.normalScale.set(.65,.65);m.roughnessMap=roughness;m.roughness=1;m.color.setRGB(.47,.44,.38);m.sheen=.65;m.sheenRoughness=.9;rugs++;}
 if((m.name==='oak'||m.name==='light oak')&&m.map){m.bumpMap=m.map;m.bumpScale=.00065;m.roughness=.52;wood++;}
 if(m.name==='studio honed pale limestone'){m.roughnessMap=m.map;m.roughness=.78;m.bumpScale=.0008;stone++;}
 if(m.name==='licensed tailored velvet / warm grey'){m.roughness=.78;velvet++;}
 m.needsUpdate=true;
 });
 return {rugs,wood,stone,velvet,proceduralWool:true,geometryChanged:false};
}

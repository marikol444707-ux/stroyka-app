// Short, frame-rate independent look smoothing. Position stays in the collision solver.
export function createLookMotion(yaw=0,pitch=0){
 const limit=v=>Math.max(-1.05,Math.min(1.05,v));
 let y=Number.isFinite(yaw)?yaw:0,p=Number.isFinite(pitch)?limit(pitch):0,ty=y,tp=p;
 function reset(yaw=y,pitch=p){y=ty=Number.isFinite(yaw)?yaw:0;p=tp=Number.isFinite(pitch)?limit(pitch):0;}
 function aim(dx,dy,{reduced=false}={}){if(!Number.isFinite(dx)||!Number.isFinite(dy))return;ty-=dx*.004;tp=limit(tp-dy*.003);if(reduced){y=ty;p=tp;}}
 function update(dt,{reduced=false}={}){const oldY=y,oldP=p;if(reduced){y=ty;p=tp;}else if(Number.isFinite(dt)&&dt>0){const a=1-Math.exp(-dt/.065);y+=(ty-y)*a;p+=(tp-p)*a;if(Math.abs(ty-y)<1e-5)y=ty;if(Math.abs(tp-p)<1e-5)p=tp;}return y!==oldY||p!==oldP;}
 return {reset,aim,update,sample:()=>({yaw:y,pitch:p,targetYaw:ty,targetPitch:tp,moving:Math.abs(ty-y)+Math.abs(tp-p)>0})};
}

// Normalized visual timelines; distances/angles come from the actual scene.
// They carry no engineering dimensions or material properties.
export const enterSeconds=2.55,exitSeconds=1.95;
export function ease(t){t=Math.min(1,Math.max(0,t));return t*t*t*(t*(t*6-15)+10);}
const ramp=(p,a,b)=>ease((p-a)/(b-a));
export function sampleEnter(progress){
 const p=Math.min(1,Math.max(0,progress)),study=p>=.44;
 return{progress:p,view:study?'study':'house',phase:p<.34?'approach':p<.44?'cover':p<.53?'reveal':p<1?'unfold':'ready',camera:ramp(p,0,.39),veil:p<.44?ramp(p,.34,.44):1-ramp(p,.44,.53),spread:ramp(p,.53,1)};
}
export function sampleExit(progress,fromHouse=false){
 const p=Math.min(1,Math.max(0,progress));
 if(fromHouse)return{progress:p,view:'house',phase:p<1?'pullback':'complete',camera:ease(p),veil:0,spread:0};
 return{progress:p,view:p>=.36?'house':'study',phase:p<.26?'assemble':p<.36?'cover':p<.46?'reveal':p<1?'pullback':'complete',camera:ramp(p,.46,1),veil:p<.36?ramp(p,.26,.36):1-ramp(p,.36,.46),spread:1-ramp(p,0,.26)};
}

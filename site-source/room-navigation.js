// View navigation only: no room editing, dimension approval or route animation.
export function roomForPoint(x,z){return x<-1.8?(z>1.55?'bedroom1':z< -1.55?'bedroom3':'bedroom2'):x<0?'hall':z< -1.3?(x<2.6?'bath':x<4.6?'utility':'office'):'living';}
export function planZoom(aspect){const height=2*32*Math.tan(37*Math.PI/360);return Math.min(height*aspect/18,height/14);}
export function layoutRoomMarkers(points,{width,height,size=44,gap=4,selected=null}){
 const accepted=[],out=new Map();const sorted=[...points].sort((a,b)=>Number(b.id===selected)-Number(a.id===selected));
 for(const p of sorted){let visible=!!p.visible&&p.x>=size/2&&p.y>=size/2&&p.x<=width-size/2&&p.y<=height-size/2;
  if(visible&&accepted.some(q=>Math.abs(q.x-p.x)<size+gap&&Math.abs(q.y-p.y)<size+gap))visible=false;
  if(visible)accepted.push(p);out.set(p.id,{...p,visible});
 }return points.map(p=>out.get(p.id));
}

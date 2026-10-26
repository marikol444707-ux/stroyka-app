// No rendering dependency: the same collision solver is tested against exported geometry.
export function createNavigator(data) {
  const radius=data.radius;
  const shapes=data.colliders.map(c=>({...c,minX:Math.min(...c.polygon.map(p=>p[0])),maxX:Math.max(...c.polygon.map(p=>p[0])),minZ:Math.min(...c.polygon.map(p=>p[1])),maxZ:Math.max(...c.polygon.map(p=>p[1]))}));
  function blocked(x,z){
    const [a,b,c,d]=data.bounds;
    if(x<a+radius||x>b-radius||z<c+radius||z>d-radius)return true;
    for(const s of shapes){
      if(x<s.minX-radius||x>s.maxX+radius||z<s.minZ-radius||z>s.maxZ+radius)continue;
      let inside=false;
      for(let i=0,j=s.polygon.length-1;i<s.polygon.length;j=i++){
        const [ax,az]=s.polygon[j],[bx,bz]=s.polygon[i];
        if(((az>z)!==(bz>z))&&(x<(bx-ax)*(z-az)/(bz-az)+ax))inside=!inside;
        const dx=bx-ax,dz=bz-az,den=dx*dx+dz*dz;
        const t=den?Math.max(0,Math.min(1,((x-ax)*dx+(z-az)*dz)/den)):0;
        if((x-ax-t*dx)**2+(z-az-t*dz)**2<radius*radius)return true;
      }
      if(inside)return true;
    }
    return false;
  }
  function move(point,dx,dz){
    // Swept substeps prevent a long frame or fast command tunnelling through walls.
    const n=Math.max(1,Math.ceil(Math.hypot(dx,dz)/.065));let [x,z]=point;
    for(let i=0;i<n;i++){
      if(!blocked(x+dx/n,z))x+=dx/n;
      if(!blocked(x,z+dz/n))z+=dz/n;
    }
    return [x,z];
  }
  return {blocked,move,rooms:data.rooms,radius,eyeHeight:data.eyeHeight};
}

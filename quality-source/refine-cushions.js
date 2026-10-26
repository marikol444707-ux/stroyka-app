// Small cloth deformations of the existing scatter cushions only.
// Both cloth faces and their piping are in each material mesh. Folds fade at
// the perimeter, preserving the sewn edge. No house/sofa vertices are modified.
export function refineCushions(model){
 let parts=0,vertices=0,maximumMovement=0;
 model.traverse(o=>{if(!o.isMesh||!/^studio (clay|ivory) scatter cushion linen$/.test(o.material.name))return;
 const previous=o.geometry,g=previous.clone();o.geometry=g;previous.dispose();g.computeBoundingBox();const b=g.boundingBox,cx=(b.min.x+b.max.x)/2,cy=(b.min.y+b.max.y)/2,hx=(b.max.x-b.min.x)/2,hy=(b.max.y-b.min.y)/2,p=g.attributes.position,n=g.attributes.normal;
 for(let i=0;i<p.count;i++){
 const x=p.getX(i),y=p.getY(i),z=p.getZ(i),u=(x-cx)/hx,v=(y-cy)/hy;
 const edge=Math.max(0,(1-u*u)*(1-v*v)),face=Math.abs(n.getZ(i));
 const corner=Math.exp(-((Math.abs(u)-.64)**2)/.065-((Math.abs(v)-.62)**2)/.12);
 const folds=(Math.sin(u*26+v*5)*.0055*corner+Math.sin(v*32-u*6)*.0035*corner+Math.sin(u*7+v*4)*.002)*edge*face;
 const dy=-.009*edge,dx=n.getX(i)*folds,dz=n.getZ(i)*folds;
 p.setXYZ(i,x+dx,y+dy,z+dz);maximumMovement=Math.max(maximumMovement,Math.hypot(dx,dy,dz));vertices++;
 }
 p.needsUpdate=true;g.computeVertexNormals();g.computeBoundingBox();g.computeBoundingSphere();parts++;
 });
 return {parts,vertices,maximumMovement,scope:'scatter cushions only',runtimeGeometryChanged:true};
}

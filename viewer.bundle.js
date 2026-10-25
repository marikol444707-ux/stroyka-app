(()=>{var El="170",Ui={LEFT:0,MIDDLE:1,RIGHT:2,ROTATE:0,DOLLY:1,PAN:2},Ni={ROTATE:0,PAN:1,DOLLY_PAN:2,DOLLY_ROTATE:3},Ju=0,Oc=1,ju=2;var iu=1,Al=2,Fn=3,En=0,Ut=1,Jt=2,ui=0,is=1,Fc=2,Bc=3,zc=4,$u=5,Ci=100,Qu=101,ed=102,td=103,nd=104,id=200,sd=201,rd=202,od=203,da=204,fa=205,ad=206,ld=207,cd=208,hd=209,ud=210,dd=211,fd=212,pd=213,md=214,pa=0,ma=1,ga=2,ls=3,_a=4,xa=5,ya=6,va=7,su=0,gd=1,_d=2,di=0,xd=1,yd=2,vd=3,Tl=4,Md=5,Sd=6,bd=7,kc="attached",wd="detached",ru=300,cs=301,hs=302,Ma=303,Sa=304,bo=306,Hn=1e3,Bn=1001,Vs=1002,Nt=1003,Rl=1004;var ts=1005;var Vt=1006,zs=1007;var wn=1008;var Vn=1009,ou=1010,au=1011,Gs=1012,Cl=1013,Pi=1014,xn=1015,tr=1016,Il=1017,Pl=1018,us=1020,lu=35902,cu=1021,hu=1022,on=1023,uu=1024,du=1025,ss=1026,ds=1027,Ll=1028,Dl=1029,fu=1030,Ul=1031;var Nl=1033,Hr=33776,Vr=33777,Gr=33778,Wr=33779,ba=35840,wa=35841,Ea=35842,Aa=35843,Ta=36196,Ra=37492,Ca=37496,Ia=37808,Pa=37809,La=37810,Da=37811,Ua=37812,Na=37813,Oa=37814,Fa=37815,Ba=37816,za=37817,ka=37818,Ha=37819,Va=37820,Ga=37821,Xr=36492,Wa=36494,Xa=36495,pu=36283,qa=36284,Ya=36285,Za=36286;var fs=2300,ps=2301,Do=2302,Hc=2400,Vc=2401,Gc=2402,Ed=2500;var mu=0,wo=1,nr=2,Ad=3200,Td=3201;var gu=0,Rd=1,li="",gt="srgb",Ft="srgb-linear",Eo="linear",Qe="srgb";var ki=7680;var Wc=519,Cd=512,Id=513,Pd=514,_u=515,Ld=516,Dd=517,Ud=518,Nd=519,Ka=35044;var Xc="300 es",zn=2e3,qr=2001,Gn=class{addEventListener(e,t){this._listeners===void 0&&(this._listeners={});let n=this._listeners;n[e]===void 0&&(n[e]=[]),n[e].indexOf(t)===-1&&n[e].push(t)}hasEventListener(e,t){if(this._listeners===void 0)return!1;let n=this._listeners;return n[e]!==void 0&&n[e].indexOf(t)!==-1}removeEventListener(e,t){if(this._listeners===void 0)return;let s=this._listeners[e];if(s!==void 0){let r=s.indexOf(t);r!==-1&&s.splice(r,1)}}dispatchEvent(e){if(this._listeners===void 0)return;let n=this._listeners[e.type];if(n!==void 0){e.target=this;let s=n.slice(0);for(let r=0,o=s.length;r<o;r++)s[r].call(this,e);e.target=null}}},Pt=["00","01","02","03","04","05","06","07","08","09","0a","0b","0c","0d","0e","0f","10","11","12","13","14","15","16","17","18","19","1a","1b","1c","1d","1e","1f","20","21","22","23","24","25","26","27","28","29","2a","2b","2c","2d","2e","2f","30","31","32","33","34","35","36","37","38","39","3a","3b","3c","3d","3e","3f","40","41","42","43","44","45","46","47","48","49","4a","4b","4c","4d","4e","4f","50","51","52","53","54","55","56","57","58","59","5a","5b","5c","5d","5e","5f","60","61","62","63","64","65","66","67","68","69","6a","6b","6c","6d","6e","6f","70","71","72","73","74","75","76","77","78","79","7a","7b","7c","7d","7e","7f","80","81","82","83","84","85","86","87","88","89","8a","8b","8c","8d","8e","8f","90","91","92","93","94","95","96","97","98","99","9a","9b","9c","9d","9e","9f","a0","a1","a2","a3","a4","a5","a6","a7","a8","a9","aa","ab","ac","ad","ae","af","b0","b1","b2","b3","b4","b5","b6","b7","b8","b9","ba","bb","bc","bd","be","bf","c0","c1","c2","c3","c4","c5","c6","c7","c8","c9","ca","cb","cc","cd","ce","cf","d0","d1","d2","d3","d4","d5","d6","d7","d8","d9","da","db","dc","dd","de","df","e0","e1","e2","e3","e4","e5","e6","e7","e8","e9","ea","eb","ec","ed","ee","ef","f0","f1","f2","f3","f4","f5","f6","f7","f8","f9","fa","fb","fc","fd","fe","ff"],qc=1234567,rs=Math.PI/180,ms=180/Math.PI;function yn(){let i=Math.random()*4294967295|0,e=Math.random()*4294967295|0,t=Math.random()*4294967295|0,n=Math.random()*4294967295|0;return(Pt[i&255]+Pt[i>>8&255]+Pt[i>>16&255]+Pt[i>>24&255]+"-"+Pt[e&255]+Pt[e>>8&255]+"-"+Pt[e>>16&15|64]+Pt[e>>24&255]+"-"+Pt[t&63|128]+Pt[t>>8&255]+"-"+Pt[t>>16&255]+Pt[t>>24&255]+Pt[n&255]+Pt[n>>8&255]+Pt[n>>16&255]+Pt[n>>24&255]).toLowerCase()}function Ct(i,e,t){return Math.max(e,Math.min(t,i))}function Ol(i,e){return(i%e+e)%e}function Od(i,e,t,n,s){return n+(i-e)*(s-n)/(t-e)}function Fd(i,e,t){return i!==e?(t-i)/(e-i):0}function ks(i,e,t){return(1-t)*i+t*e}function Bd(i,e,t,n){return ks(i,e,1-Math.exp(-t*n))}function zd(i,e=1){return e-Math.abs(Ol(i,e*2)-e)}function kd(i,e,t){return i<=e?0:i>=t?1:(i=(i-e)/(t-e),i*i*(3-2*i))}function Hd(i,e,t){return i<=e?0:i>=t?1:(i=(i-e)/(t-e),i*i*i*(i*(i*6-15)+10))}function Vd(i,e){return i+Math.floor(Math.random()*(e-i+1))}function Gd(i,e){return i+Math.random()*(e-i)}function Wd(i){return i*(.5-Math.random())}function Xd(i){i!==void 0&&(qc=i);let e=qc+=1831565813;return e=Math.imul(e^e>>>15,e|1),e^=e+Math.imul(e^e>>>7,e|61),((e^e>>>14)>>>0)/4294967296}function qd(i){return i*rs}function Yd(i){return i*ms}function Zd(i){return(i&i-1)===0&&i!==0}function Kd(i){return Math.pow(2,Math.ceil(Math.log(i)/Math.LN2))}function Jd(i){return Math.pow(2,Math.floor(Math.log(i)/Math.LN2))}function jd(i,e,t,n,s){let r=Math.cos,o=Math.sin,a=r(t/2),l=o(t/2),c=r((e+n)/2),h=o((e+n)/2),u=r((e-n)/2),d=o((e-n)/2),f=r((n-e)/2),g=o((n-e)/2);switch(s){case"XYX":i.set(a*h,l*u,l*d,a*c);break;case"YZY":i.set(l*d,a*h,l*u,a*c);break;case"ZXZ":i.set(l*u,l*d,a*h,a*c);break;case"XZX":i.set(a*h,l*g,l*f,a*c);break;case"YXY":i.set(l*f,a*h,l*g,a*c);break;case"ZYZ":i.set(l*g,l*f,a*h,a*c);break;default:console.warn("THREE.MathUtils: .setQuaternionFromProperEuler() encountered an unknown order: "+s)}}function _n(i,e){switch(e.constructor){case Float32Array:return i;case Uint32Array:return i/4294967295;case Uint16Array:return i/65535;case Uint8Array:return i/255;case Int32Array:return Math.max(i/2147483647,-1);case Int16Array:return Math.max(i/32767,-1);case Int8Array:return Math.max(i/127,-1);default:throw new Error("Invalid component type.")}}function $e(i,e){switch(e.constructor){case Float32Array:return i;case Uint32Array:return Math.round(i*4294967295);case Uint16Array:return Math.round(i*65535);case Uint8Array:return Math.round(i*255);case Int32Array:return Math.round(i*2147483647);case Int16Array:return Math.round(i*32767);case Int8Array:return Math.round(i*127);default:throw new Error("Invalid component type.")}}var en={DEG2RAD:rs,RAD2DEG:ms,generateUUID:yn,clamp:Ct,euclideanModulo:Ol,mapLinear:Od,inverseLerp:Fd,lerp:ks,damp:Bd,pingpong:zd,smoothstep:kd,smootherstep:Hd,randInt:Vd,randFloat:Gd,randFloatSpread:Wd,seededRandom:Xd,degToRad:qd,radToDeg:Yd,isPowerOfTwo:Zd,ceilPowerOfTwo:Kd,floorPowerOfTwo:Jd,setQuaternionFromProperEuler:jd,normalize:$e,denormalize:_n},we=class i{constructor(e=0,t=0){i.prototype.isVector2=!0,this.x=e,this.y=t}get width(){return this.x}set width(e){this.x=e}get height(){return this.y}set height(e){this.y=e}set(e,t){return this.x=e,this.y=t,this}setScalar(e){return this.x=e,this.y=e,this}setX(e){return this.x=e,this}setY(e){return this.y=e,this}setComponent(e,t){switch(e){case 0:this.x=t;break;case 1:this.y=t;break;default:throw new Error("index is out of range: "+e)}return this}getComponent(e){switch(e){case 0:return this.x;case 1:return this.y;default:throw new Error("index is out of range: "+e)}}clone(){return new this.constructor(this.x,this.y)}copy(e){return this.x=e.x,this.y=e.y,this}add(e){return this.x+=e.x,this.y+=e.y,this}addScalar(e){return this.x+=e,this.y+=e,this}addVectors(e,t){return this.x=e.x+t.x,this.y=e.y+t.y,this}addScaledVector(e,t){return this.x+=e.x*t,this.y+=e.y*t,this}sub(e){return this.x-=e.x,this.y-=e.y,this}subScalar(e){return this.x-=e,this.y-=e,this}subVectors(e,t){return this.x=e.x-t.x,this.y=e.y-t.y,this}multiply(e){return this.x*=e.x,this.y*=e.y,this}multiplyScalar(e){return this.x*=e,this.y*=e,this}divide(e){return this.x/=e.x,this.y/=e.y,this}divideScalar(e){return this.multiplyScalar(1/e)}applyMatrix3(e){let t=this.x,n=this.y,s=e.elements;return this.x=s[0]*t+s[3]*n+s[6],this.y=s[1]*t+s[4]*n+s[7],this}min(e){return this.x=Math.min(this.x,e.x),this.y=Math.min(this.y,e.y),this}max(e){return this.x=Math.max(this.x,e.x),this.y=Math.max(this.y,e.y),this}clamp(e,t){return this.x=Math.max(e.x,Math.min(t.x,this.x)),this.y=Math.max(e.y,Math.min(t.y,this.y)),this}clampScalar(e,t){return this.x=Math.max(e,Math.min(t,this.x)),this.y=Math.max(e,Math.min(t,this.y)),this}clampLength(e,t){let n=this.length();return this.divideScalar(n||1).multiplyScalar(Math.max(e,Math.min(t,n)))}floor(){return this.x=Math.floor(this.x),this.y=Math.floor(this.y),this}ceil(){return this.x=Math.ceil(this.x),this.y=Math.ceil(this.y),this}round(){return this.x=Math.round(this.x),this.y=Math.round(this.y),this}roundToZero(){return this.x=Math.trunc(this.x),this.y=Math.trunc(this.y),this}negate(){return this.x=-this.x,this.y=-this.y,this}dot(e){return this.x*e.x+this.y*e.y}cross(e){return this.x*e.y-this.y*e.x}lengthSq(){return this.x*this.x+this.y*this.y}length(){return Math.sqrt(this.x*this.x+this.y*this.y)}manhattanLength(){return Math.abs(this.x)+Math.abs(this.y)}normalize(){return this.divideScalar(this.length()||1)}angle(){return Math.atan2(-this.y,-this.x)+Math.PI}angleTo(e){let t=Math.sqrt(this.lengthSq()*e.lengthSq());if(t===0)return Math.PI/2;let n=this.dot(e)/t;return Math.acos(Ct(n,-1,1))}distanceTo(e){return Math.sqrt(this.distanceToSquared(e))}distanceToSquared(e){let t=this.x-e.x,n=this.y-e.y;return t*t+n*n}manhattanDistanceTo(e){return Math.abs(this.x-e.x)+Math.abs(this.y-e.y)}setLength(e){return this.normalize().multiplyScalar(e)}lerp(e,t){return this.x+=(e.x-this.x)*t,this.y+=(e.y-this.y)*t,this}lerpVectors(e,t,n){return this.x=e.x+(t.x-e.x)*n,this.y=e.y+(t.y-e.y)*n,this}equals(e){return e.x===this.x&&e.y===this.y}fromArray(e,t=0){return this.x=e[t],this.y=e[t+1],this}toArray(e=[],t=0){return e[t]=this.x,e[t+1]=this.y,e}fromBufferAttribute(e,t){return this.x=e.getX(t),this.y=e.getY(t),this}rotateAround(e,t){let n=Math.cos(t),s=Math.sin(t),r=this.x-e.x,o=this.y-e.y;return this.x=r*n-o*s+e.x,this.y=r*s+o*n+e.y,this}random(){return this.x=Math.random(),this.y=Math.random(),this}*[Symbol.iterator](){yield this.x,yield this.y}},Ne=class i{constructor(e,t,n,s,r,o,a,l,c){i.prototype.isMatrix3=!0,this.elements=[1,0,0,0,1,0,0,0,1],e!==void 0&&this.set(e,t,n,s,r,o,a,l,c)}set(e,t,n,s,r,o,a,l,c){let h=this.elements;return h[0]=e,h[1]=s,h[2]=a,h[3]=t,h[4]=r,h[5]=l,h[6]=n,h[7]=o,h[8]=c,this}identity(){return this.set(1,0,0,0,1,0,0,0,1),this}copy(e){let t=this.elements,n=e.elements;return t[0]=n[0],t[1]=n[1],t[2]=n[2],t[3]=n[3],t[4]=n[4],t[5]=n[5],t[6]=n[6],t[7]=n[7],t[8]=n[8],this}extractBasis(e,t,n){return e.setFromMatrix3Column(this,0),t.setFromMatrix3Column(this,1),n.setFromMatrix3Column(this,2),this}setFromMatrix4(e){let t=e.elements;return this.set(t[0],t[4],t[8],t[1],t[5],t[9],t[2],t[6],t[10]),this}multiply(e){return this.multiplyMatrices(this,e)}premultiply(e){return this.multiplyMatrices(e,this)}multiplyMatrices(e,t){let n=e.elements,s=t.elements,r=this.elements,o=n[0],a=n[3],l=n[6],c=n[1],h=n[4],u=n[7],d=n[2],f=n[5],g=n[8],_=s[0],m=s[3],p=s[6],w=s[1],b=s[4],x=s[7],P=s[2],T=s[5],A=s[8];return r[0]=o*_+a*w+l*P,r[3]=o*m+a*b+l*T,r[6]=o*p+a*x+l*A,r[1]=c*_+h*w+u*P,r[4]=c*m+h*b+u*T,r[7]=c*p+h*x+u*A,r[2]=d*_+f*w+g*P,r[5]=d*m+f*b+g*T,r[8]=d*p+f*x+g*A,this}multiplyScalar(e){let t=this.elements;return t[0]*=e,t[3]*=e,t[6]*=e,t[1]*=e,t[4]*=e,t[7]*=e,t[2]*=e,t[5]*=e,t[8]*=e,this}determinant(){let e=this.elements,t=e[0],n=e[1],s=e[2],r=e[3],o=e[4],a=e[5],l=e[6],c=e[7],h=e[8];return t*o*h-t*a*c-n*r*h+n*a*l+s*r*c-s*o*l}invert(){let e=this.elements,t=e[0],n=e[1],s=e[2],r=e[3],o=e[4],a=e[5],l=e[6],c=e[7],h=e[8],u=h*o-a*c,d=a*l-h*r,f=c*r-o*l,g=t*u+n*d+s*f;if(g===0)return this.set(0,0,0,0,0,0,0,0,0);let _=1/g;return e[0]=u*_,e[1]=(s*c-h*n)*_,e[2]=(a*n-s*o)*_,e[3]=d*_,e[4]=(h*t-s*l)*_,e[5]=(s*r-a*t)*_,e[6]=f*_,e[7]=(n*l-c*t)*_,e[8]=(o*t-n*r)*_,this}transpose(){let e,t=this.elements;return e=t[1],t[1]=t[3],t[3]=e,e=t[2],t[2]=t[6],t[6]=e,e=t[5],t[5]=t[7],t[7]=e,this}getNormalMatrix(e){return this.setFromMatrix4(e).invert().transpose()}transposeIntoArray(e){let t=this.elements;return e[0]=t[0],e[1]=t[3],e[2]=t[6],e[3]=t[1],e[4]=t[4],e[5]=t[7],e[6]=t[2],e[7]=t[5],e[8]=t[8],this}setUvTransform(e,t,n,s,r,o,a){let l=Math.cos(r),c=Math.sin(r);return this.set(n*l,n*c,-n*(l*o+c*a)+o+e,-s*c,s*l,-s*(-c*o+l*a)+a+t,0,0,1),this}scale(e,t){return this.premultiply(Uo.makeScale(e,t)),this}rotate(e){return this.premultiply(Uo.makeRotation(-e)),this}translate(e,t){return this.premultiply(Uo.makeTranslation(e,t)),this}makeTranslation(e,t){return e.isVector2?this.set(1,0,e.x,0,1,e.y,0,0,1):this.set(1,0,e,0,1,t,0,0,1),this}makeRotation(e){let t=Math.cos(e),n=Math.sin(e);return this.set(t,-n,0,n,t,0,0,0,1),this}makeScale(e,t){return this.set(e,0,0,0,t,0,0,0,1),this}equals(e){let t=this.elements,n=e.elements;for(let s=0;s<9;s++)if(t[s]!==n[s])return!1;return!0}fromArray(e,t=0){for(let n=0;n<9;n++)this.elements[n]=e[n+t];return this}toArray(e=[],t=0){let n=this.elements;return e[t]=n[0],e[t+1]=n[1],e[t+2]=n[2],e[t+3]=n[3],e[t+4]=n[4],e[t+5]=n[5],e[t+6]=n[6],e[t+7]=n[7],e[t+8]=n[8],e}clone(){return new this.constructor().fromArray(this.elements)}},Uo=new Ne;function xu(i){for(let e=i.length-1;e>=0;--e)if(i[e]>=65535)return!0;return!1}function Ws(i){return document.createElementNS("http://www.w3.org/1999/xhtml",i)}function $d(){let i=Ws("canvas");return i.style.display="block",i}var Yc={};function Fs(i){i in Yc||(Yc[i]=!0,console.warn(i))}function Qd(i,e,t){return new Promise(function(n,s){function r(){switch(i.clientWaitSync(e,i.SYNC_FLUSH_COMMANDS_BIT,0)){case i.WAIT_FAILED:s();break;case i.TIMEOUT_EXPIRED:setTimeout(r,t);break;default:n()}}setTimeout(r,t)})}function ef(i){let e=i.elements;e[2]=.5*e[2]+.5*e[3],e[6]=.5*e[6]+.5*e[7],e[10]=.5*e[10]+.5*e[11],e[14]=.5*e[14]+.5*e[15]}function tf(i){let e=i.elements;e[11]===-1?(e[10]=-e[10]-1,e[14]=-e[14]):(e[10]=-e[10],e[14]=-e[14]+1)}var ke={enabled:!0,workingColorSpace:Ft,spaces:{},convert:function(i,e,t){return this.enabled===!1||e===t||!e||!t||(this.spaces[e].transfer===Qe&&(i.r=kn(i.r),i.g=kn(i.g),i.b=kn(i.b)),this.spaces[e].primaries!==this.spaces[t].primaries&&(i.applyMatrix3(this.spaces[e].toXYZ),i.applyMatrix3(this.spaces[t].fromXYZ)),this.spaces[t].transfer===Qe&&(i.r=os(i.r),i.g=os(i.g),i.b=os(i.b))),i},fromWorkingColorSpace:function(i,e){return this.convert(i,this.workingColorSpace,e)},toWorkingColorSpace:function(i,e){return this.convert(i,e,this.workingColorSpace)},getPrimaries:function(i){return this.spaces[i].primaries},getTransfer:function(i){return i===li?Eo:this.spaces[i].transfer},getLuminanceCoefficients:function(i,e=this.workingColorSpace){return i.fromArray(this.spaces[e].luminanceCoefficients)},define:function(i){Object.assign(this.spaces,i)},_getMatrix:function(i,e,t){return i.copy(this.spaces[e].toXYZ).multiply(this.spaces[t].fromXYZ)},_getDrawingBufferColorSpace:function(i){return this.spaces[i].outputColorSpaceConfig.drawingBufferColorSpace},_getUnpackColorSpace:function(i=this.workingColorSpace){return this.spaces[i].workingColorSpaceConfig.unpackColorSpace}};function kn(i){return i<.04045?i*.0773993808:Math.pow(i*.9478672986+.0521327014,2.4)}function os(i){return i<.0031308?i*12.92:1.055*Math.pow(i,.41666)-.055}var Zc=[.64,.33,.3,.6,.15,.06],Kc=[.2126,.7152,.0722],Jc=[.3127,.329],jc=new Ne().set(.4123908,.3575843,.1804808,.212639,.7151687,.0721923,.0193308,.1191948,.9505322),$c=new Ne().set(3.2409699,-1.5373832,-.4986108,-.9692436,1.8759675,.0415551,.0556301,-.203977,1.0569715);ke.define({[Ft]:{primaries:Zc,whitePoint:Jc,transfer:Eo,toXYZ:jc,fromXYZ:$c,luminanceCoefficients:Kc,workingColorSpaceConfig:{unpackColorSpace:gt},outputColorSpaceConfig:{drawingBufferColorSpace:gt}},[gt]:{primaries:Zc,whitePoint:Jc,transfer:Qe,toXYZ:jc,fromXYZ:$c,luminanceCoefficients:Kc,outputColorSpaceConfig:{drawingBufferColorSpace:gt}}});var Hi,Ja=class{static getDataURL(e){if(/^data:/i.test(e.src)||typeof HTMLCanvasElement>"u")return e.src;let t;if(e instanceof HTMLCanvasElement)t=e;else{Hi===void 0&&(Hi=Ws("canvas")),Hi.width=e.width,Hi.height=e.height;let n=Hi.getContext("2d");e instanceof ImageData?n.putImageData(e,0,0):n.drawImage(e,0,0,e.width,e.height),t=Hi}return t.width>2048||t.height>2048?(console.warn("THREE.ImageUtils.getDataURL: Image converted to jpg for performance reasons",e),t.toDataURL("image/jpeg",.6)):t.toDataURL("image/png")}static sRGBToLinear(e){if(typeof HTMLImageElement<"u"&&e instanceof HTMLImageElement||typeof HTMLCanvasElement<"u"&&e instanceof HTMLCanvasElement||typeof ImageBitmap<"u"&&e instanceof ImageBitmap){let t=Ws("canvas");t.width=e.width,t.height=e.height;let n=t.getContext("2d");n.drawImage(e,0,0,e.width,e.height);let s=n.getImageData(0,0,e.width,e.height),r=s.data;for(let o=0;o<r.length;o++)r[o]=kn(r[o]/255)*255;return n.putImageData(s,0,0),t}else if(e.data){let t=e.data.slice(0);for(let n=0;n<t.length;n++)t instanceof Uint8Array||t instanceof Uint8ClampedArray?t[n]=Math.floor(kn(t[n]/255)*255):t[n]=kn(t[n]);return{data:t,width:e.width,height:e.height}}else return console.warn("THREE.ImageUtils.sRGBToLinear(): Unsupported image type. No color space conversion applied."),e}},nf=0,Yr=class{constructor(e=null){this.isSource=!0,Object.defineProperty(this,"id",{value:nf++}),this.uuid=yn(),this.data=e,this.dataReady=!0,this.version=0}set needsUpdate(e){e===!0&&this.version++}toJSON(e){let t=e===void 0||typeof e=="string";if(!t&&e.images[this.uuid]!==void 0)return e.images[this.uuid];let n={uuid:this.uuid,url:""},s=this.data;if(s!==null){let r;if(Array.isArray(s)){r=[];for(let o=0,a=s.length;o<a;o++)s[o].isDataTexture?r.push(No(s[o].image)):r.push(No(s[o]))}else r=No(s);n.url=r}return t||(e.images[this.uuid]=n),n}};function No(i){return typeof HTMLImageElement<"u"&&i instanceof HTMLImageElement||typeof HTMLCanvasElement<"u"&&i instanceof HTMLCanvasElement||typeof ImageBitmap<"u"&&i instanceof ImageBitmap?Ja.getDataURL(i):i.data?{data:Array.from(i.data),width:i.width,height:i.height,type:i.data.constructor.name}:(console.warn("THREE.Texture: Unable to serialize Texture."),{})}var sf=0,Et=class i extends Gn{constructor(e=i.DEFAULT_IMAGE,t=i.DEFAULT_MAPPING,n=Bn,s=Bn,r=Vt,o=wn,a=on,l=Vn,c=i.DEFAULT_ANISOTROPY,h=li){super(),this.isTexture=!0,Object.defineProperty(this,"id",{value:sf++}),this.uuid=yn(),this.name="",this.source=new Yr(e),this.mipmaps=[],this.mapping=t,this.channel=0,this.wrapS=n,this.wrapT=s,this.magFilter=r,this.minFilter=o,this.anisotropy=c,this.format=a,this.internalFormat=null,this.type=l,this.offset=new we(0,0),this.repeat=new we(1,1),this.center=new we(0,0),this.rotation=0,this.matrixAutoUpdate=!0,this.matrix=new Ne,this.generateMipmaps=!0,this.premultiplyAlpha=!1,this.flipY=!0,this.unpackAlignment=4,this.colorSpace=h,this.userData={},this.version=0,this.onUpdate=null,this.isRenderTargetTexture=!1,this.pmremVersion=0}get image(){return this.source.data}set image(e=null){this.source.data=e}updateMatrix(){this.matrix.setUvTransform(this.offset.x,this.offset.y,this.repeat.x,this.repeat.y,this.rotation,this.center.x,this.center.y)}clone(){return new this.constructor().copy(this)}copy(e){return this.name=e.name,this.source=e.source,this.mipmaps=e.mipmaps.slice(0),this.mapping=e.mapping,this.channel=e.channel,this.wrapS=e.wrapS,this.wrapT=e.wrapT,this.magFilter=e.magFilter,this.minFilter=e.minFilter,this.anisotropy=e.anisotropy,this.format=e.format,this.internalFormat=e.internalFormat,this.type=e.type,this.offset.copy(e.offset),this.repeat.copy(e.repeat),this.center.copy(e.center),this.rotation=e.rotation,this.matrixAutoUpdate=e.matrixAutoUpdate,this.matrix.copy(e.matrix),this.generateMipmaps=e.generateMipmaps,this.premultiplyAlpha=e.premultiplyAlpha,this.flipY=e.flipY,this.unpackAlignment=e.unpackAlignment,this.colorSpace=e.colorSpace,this.userData=JSON.parse(JSON.stringify(e.userData)),this.needsUpdate=!0,this}toJSON(e){let t=e===void 0||typeof e=="string";if(!t&&e.textures[this.uuid]!==void 0)return e.textures[this.uuid];let n={metadata:{version:4.6,type:"Texture",generator:"Texture.toJSON"},uuid:this.uuid,name:this.name,image:this.source.toJSON(e).uuid,mapping:this.mapping,channel:this.channel,repeat:[this.repeat.x,this.repeat.y],offset:[this.offset.x,this.offset.y],center:[this.center.x,this.center.y],rotation:this.rotation,wrap:[this.wrapS,this.wrapT],format:this.format,internalFormat:this.internalFormat,type:this.type,colorSpace:this.colorSpace,minFilter:this.minFilter,magFilter:this.magFilter,anisotropy:this.anisotropy,flipY:this.flipY,generateMipmaps:this.generateMipmaps,premultiplyAlpha:this.premultiplyAlpha,unpackAlignment:this.unpackAlignment};return Object.keys(this.userData).length>0&&(n.userData=this.userData),t||(e.textures[this.uuid]=n),n}dispose(){this.dispatchEvent({type:"dispose"})}transformUv(e){if(this.mapping!==ru)return e;if(e.applyMatrix3(this.matrix),e.x<0||e.x>1)switch(this.wrapS){case Hn:e.x=e.x-Math.floor(e.x);break;case Bn:e.x=e.x<0?0:1;break;case Vs:Math.abs(Math.floor(e.x)%2)===1?e.x=Math.ceil(e.x)-e.x:e.x=e.x-Math.floor(e.x);break}if(e.y<0||e.y>1)switch(this.wrapT){case Hn:e.y=e.y-Math.floor(e.y);break;case Bn:e.y=e.y<0?0:1;break;case Vs:Math.abs(Math.floor(e.y)%2)===1?e.y=Math.ceil(e.y)-e.y:e.y=e.y-Math.floor(e.y);break}return this.flipY&&(e.y=1-e.y),e}set needsUpdate(e){e===!0&&(this.version++,this.source.needsUpdate=!0)}set needsPMREMUpdate(e){e===!0&&this.pmremVersion++}};Et.DEFAULT_IMAGE=null;Et.DEFAULT_MAPPING=ru;Et.DEFAULT_ANISOTROPY=1;var Ye=class i{constructor(e=0,t=0,n=0,s=1){i.prototype.isVector4=!0,this.x=e,this.y=t,this.z=n,this.w=s}get width(){return this.z}set width(e){this.z=e}get height(){return this.w}set height(e){this.w=e}set(e,t,n,s){return this.x=e,this.y=t,this.z=n,this.w=s,this}setScalar(e){return this.x=e,this.y=e,this.z=e,this.w=e,this}setX(e){return this.x=e,this}setY(e){return this.y=e,this}setZ(e){return this.z=e,this}setW(e){return this.w=e,this}setComponent(e,t){switch(e){case 0:this.x=t;break;case 1:this.y=t;break;case 2:this.z=t;break;case 3:this.w=t;break;default:throw new Error("index is out of range: "+e)}return this}getComponent(e){switch(e){case 0:return this.x;case 1:return this.y;case 2:return this.z;case 3:return this.w;default:throw new Error("index is out of range: "+e)}}clone(){return new this.constructor(this.x,this.y,this.z,this.w)}copy(e){return this.x=e.x,this.y=e.y,this.z=e.z,this.w=e.w!==void 0?e.w:1,this}add(e){return this.x+=e.x,this.y+=e.y,this.z+=e.z,this.w+=e.w,this}addScalar(e){return this.x+=e,this.y+=e,this.z+=e,this.w+=e,this}addVectors(e,t){return this.x=e.x+t.x,this.y=e.y+t.y,this.z=e.z+t.z,this.w=e.w+t.w,this}addScaledVector(e,t){return this.x+=e.x*t,this.y+=e.y*t,this.z+=e.z*t,this.w+=e.w*t,this}sub(e){return this.x-=e.x,this.y-=e.y,this.z-=e.z,this.w-=e.w,this}subScalar(e){return this.x-=e,this.y-=e,this.z-=e,this.w-=e,this}subVectors(e,t){return this.x=e.x-t.x,this.y=e.y-t.y,this.z=e.z-t.z,this.w=e.w-t.w,this}multiply(e){return this.x*=e.x,this.y*=e.y,this.z*=e.z,this.w*=e.w,this}multiplyScalar(e){return this.x*=e,this.y*=e,this.z*=e,this.w*=e,this}applyMatrix4(e){let t=this.x,n=this.y,s=this.z,r=this.w,o=e.elements;return this.x=o[0]*t+o[4]*n+o[8]*s+o[12]*r,this.y=o[1]*t+o[5]*n+o[9]*s+o[13]*r,this.z=o[2]*t+o[6]*n+o[10]*s+o[14]*r,this.w=o[3]*t+o[7]*n+o[11]*s+o[15]*r,this}divide(e){return this.x/=e.x,this.y/=e.y,this.z/=e.z,this.w/=e.w,this}divideScalar(e){return this.multiplyScalar(1/e)}setAxisAngleFromQuaternion(e){this.w=2*Math.acos(e.w);let t=Math.sqrt(1-e.w*e.w);return t<1e-4?(this.x=1,this.y=0,this.z=0):(this.x=e.x/t,this.y=e.y/t,this.z=e.z/t),this}setAxisAngleFromRotationMatrix(e){let t,n,s,r,l=e.elements,c=l[0],h=l[4],u=l[8],d=l[1],f=l[5],g=l[9],_=l[2],m=l[6],p=l[10];if(Math.abs(h-d)<.01&&Math.abs(u-_)<.01&&Math.abs(g-m)<.01){if(Math.abs(h+d)<.1&&Math.abs(u+_)<.1&&Math.abs(g+m)<.1&&Math.abs(c+f+p-3)<.1)return this.set(1,0,0,0),this;t=Math.PI;let b=(c+1)/2,x=(f+1)/2,P=(p+1)/2,T=(h+d)/4,A=(u+_)/4,R=(g+m)/4;return b>x&&b>P?b<.01?(n=0,s=.707106781,r=.707106781):(n=Math.sqrt(b),s=T/n,r=A/n):x>P?x<.01?(n=.707106781,s=0,r=.707106781):(s=Math.sqrt(x),n=T/s,r=R/s):P<.01?(n=.707106781,s=.707106781,r=0):(r=Math.sqrt(P),n=A/r,s=R/r),this.set(n,s,r,t),this}let w=Math.sqrt((m-g)*(m-g)+(u-_)*(u-_)+(d-h)*(d-h));return Math.abs(w)<.001&&(w=1),this.x=(m-g)/w,this.y=(u-_)/w,this.z=(d-h)/w,this.w=Math.acos((c+f+p-1)/2),this}setFromMatrixPosition(e){let t=e.elements;return this.x=t[12],this.y=t[13],this.z=t[14],this.w=t[15],this}min(e){return this.x=Math.min(this.x,e.x),this.y=Math.min(this.y,e.y),this.z=Math.min(this.z,e.z),this.w=Math.min(this.w,e.w),this}max(e){return this.x=Math.max(this.x,e.x),this.y=Math.max(this.y,e.y),this.z=Math.max(this.z,e.z),this.w=Math.max(this.w,e.w),this}clamp(e,t){return this.x=Math.max(e.x,Math.min(t.x,this.x)),this.y=Math.max(e.y,Math.min(t.y,this.y)),this.z=Math.max(e.z,Math.min(t.z,this.z)),this.w=Math.max(e.w,Math.min(t.w,this.w)),this}clampScalar(e,t){return this.x=Math.max(e,Math.min(t,this.x)),this.y=Math.max(e,Math.min(t,this.y)),this.z=Math.max(e,Math.min(t,this.z)),this.w=Math.max(e,Math.min(t,this.w)),this}clampLength(e,t){let n=this.length();return this.divideScalar(n||1).multiplyScalar(Math.max(e,Math.min(t,n)))}floor(){return this.x=Math.floor(this.x),this.y=Math.floor(this.y),this.z=Math.floor(this.z),this.w=Math.floor(this.w),this}ceil(){return this.x=Math.ceil(this.x),this.y=Math.ceil(this.y),this.z=Math.ceil(this.z),this.w=Math.ceil(this.w),this}round(){return this.x=Math.round(this.x),this.y=Math.round(this.y),this.z=Math.round(this.z),this.w=Math.round(this.w),this}roundToZero(){return this.x=Math.trunc(this.x),this.y=Math.trunc(this.y),this.z=Math.trunc(this.z),this.w=Math.trunc(this.w),this}negate(){return this.x=-this.x,this.y=-this.y,this.z=-this.z,this.w=-this.w,this}dot(e){return this.x*e.x+this.y*e.y+this.z*e.z+this.w*e.w}lengthSq(){return this.x*this.x+this.y*this.y+this.z*this.z+this.w*this.w}length(){return Math.sqrt(this.x*this.x+this.y*this.y+this.z*this.z+this.w*this.w)}manhattanLength(){return Math.abs(this.x)+Math.abs(this.y)+Math.abs(this.z)+Math.abs(this.w)}normalize(){return this.divideScalar(this.length()||1)}setLength(e){return this.normalize().multiplyScalar(e)}lerp(e,t){return this.x+=(e.x-this.x)*t,this.y+=(e.y-this.y)*t,this.z+=(e.z-this.z)*t,this.w+=(e.w-this.w)*t,this}lerpVectors(e,t,n){return this.x=e.x+(t.x-e.x)*n,this.y=e.y+(t.y-e.y)*n,this.z=e.z+(t.z-e.z)*n,this.w=e.w+(t.w-e.w)*n,this}equals(e){return e.x===this.x&&e.y===this.y&&e.z===this.z&&e.w===this.w}fromArray(e,t=0){return this.x=e[t],this.y=e[t+1],this.z=e[t+2],this.w=e[t+3],this}toArray(e=[],t=0){return e[t]=this.x,e[t+1]=this.y,e[t+2]=this.z,e[t+3]=this.w,e}fromBufferAttribute(e,t){return this.x=e.getX(t),this.y=e.getY(t),this.z=e.getZ(t),this.w=e.getW(t),this}random(){return this.x=Math.random(),this.y=Math.random(),this.z=Math.random(),this.w=Math.random(),this}*[Symbol.iterator](){yield this.x,yield this.y,yield this.z,yield this.w}},ja=class extends Gn{constructor(e=1,t=1,n={}){super(),this.isRenderTarget=!0,this.width=e,this.height=t,this.depth=1,this.scissor=new Ye(0,0,e,t),this.scissorTest=!1,this.viewport=new Ye(0,0,e,t);let s={width:e,height:t,depth:1};n=Object.assign({generateMipmaps:!1,internalFormat:null,minFilter:Vt,depthBuffer:!0,stencilBuffer:!1,resolveDepthBuffer:!0,resolveStencilBuffer:!0,depthTexture:null,samples:0,count:1},n);let r=new Et(s,n.mapping,n.wrapS,n.wrapT,n.magFilter,n.minFilter,n.format,n.type,n.anisotropy,n.colorSpace);r.flipY=!1,r.generateMipmaps=n.generateMipmaps,r.internalFormat=n.internalFormat,this.textures=[];let o=n.count;for(let a=0;a<o;a++)this.textures[a]=r.clone(),this.textures[a].isRenderTargetTexture=!0;this.depthBuffer=n.depthBuffer,this.stencilBuffer=n.stencilBuffer,this.resolveDepthBuffer=n.resolveDepthBuffer,this.resolveStencilBuffer=n.resolveStencilBuffer,this.depthTexture=n.depthTexture,this.samples=n.samples}get texture(){return this.textures[0]}set texture(e){this.textures[0]=e}setSize(e,t,n=1){if(this.width!==e||this.height!==t||this.depth!==n){this.width=e,this.height=t,this.depth=n;for(let s=0,r=this.textures.length;s<r;s++)this.textures[s].image.width=e,this.textures[s].image.height=t,this.textures[s].image.depth=n;this.dispose()}this.viewport.set(0,0,e,t),this.scissor.set(0,0,e,t)}clone(){return new this.constructor().copy(this)}copy(e){this.width=e.width,this.height=e.height,this.depth=e.depth,this.scissor.copy(e.scissor),this.scissorTest=e.scissorTest,this.viewport.copy(e.viewport),this.textures.length=0;for(let n=0,s=e.textures.length;n<s;n++)this.textures[n]=e.textures[n].clone(),this.textures[n].isRenderTargetTexture=!0;let t=Object.assign({},e.texture.image);return this.texture.source=new Yr(t),this.depthBuffer=e.depthBuffer,this.stencilBuffer=e.stencilBuffer,this.resolveDepthBuffer=e.resolveDepthBuffer,this.resolveStencilBuffer=e.resolveStencilBuffer,e.depthTexture!==null&&(this.depthTexture=e.depthTexture.clone()),this.samples=e.samples,this}dispose(){this.dispatchEvent({type:"dispose"})}},Wn=class extends ja{constructor(e=1,t=1,n={}){super(e,t,n),this.isWebGLRenderTarget=!0}},Zr=class extends Et{constructor(e=null,t=1,n=1,s=1){super(null),this.isDataArrayTexture=!0,this.image={data:e,width:t,height:n,depth:s},this.magFilter=Nt,this.minFilter=Nt,this.wrapR=Bn,this.generateMipmaps=!1,this.flipY=!1,this.unpackAlignment=1,this.layerUpdates=new Set}addLayerUpdate(e){this.layerUpdates.add(e)}clearLayerUpdates(){this.layerUpdates.clear()}};var $a=class extends Et{constructor(e=null,t=1,n=1,s=1){super(null),this.isData3DTexture=!0,this.image={data:e,width:t,height:n,depth:s},this.magFilter=Nt,this.minFilter=Nt,this.wrapR=Bn,this.generateMipmaps=!1,this.flipY=!1,this.unpackAlignment=1}};var Gt=class{constructor(e=0,t=0,n=0,s=1){this.isQuaternion=!0,this._x=e,this._y=t,this._z=n,this._w=s}static slerpFlat(e,t,n,s,r,o,a){let l=n[s+0],c=n[s+1],h=n[s+2],u=n[s+3],d=r[o+0],f=r[o+1],g=r[o+2],_=r[o+3];if(a===0){e[t+0]=l,e[t+1]=c,e[t+2]=h,e[t+3]=u;return}if(a===1){e[t+0]=d,e[t+1]=f,e[t+2]=g,e[t+3]=_;return}if(u!==_||l!==d||c!==f||h!==g){let m=1-a,p=l*d+c*f+h*g+u*_,w=p>=0?1:-1,b=1-p*p;if(b>Number.EPSILON){let P=Math.sqrt(b),T=Math.atan2(P,p*w);m=Math.sin(m*T)/P,a=Math.sin(a*T)/P}let x=a*w;if(l=l*m+d*x,c=c*m+f*x,h=h*m+g*x,u=u*m+_*x,m===1-a){let P=1/Math.sqrt(l*l+c*c+h*h+u*u);l*=P,c*=P,h*=P,u*=P}}e[t]=l,e[t+1]=c,e[t+2]=h,e[t+3]=u}static multiplyQuaternionsFlat(e,t,n,s,r,o){let a=n[s],l=n[s+1],c=n[s+2],h=n[s+3],u=r[o],d=r[o+1],f=r[o+2],g=r[o+3];return e[t]=a*g+h*u+l*f-c*d,e[t+1]=l*g+h*d+c*u-a*f,e[t+2]=c*g+h*f+a*d-l*u,e[t+3]=h*g-a*u-l*d-c*f,e}get x(){return this._x}set x(e){this._x=e,this._onChangeCallback()}get y(){return this._y}set y(e){this._y=e,this._onChangeCallback()}get z(){return this._z}set z(e){this._z=e,this._onChangeCallback()}get w(){return this._w}set w(e){this._w=e,this._onChangeCallback()}set(e,t,n,s){return this._x=e,this._y=t,this._z=n,this._w=s,this._onChangeCallback(),this}clone(){return new this.constructor(this._x,this._y,this._z,this._w)}copy(e){return this._x=e.x,this._y=e.y,this._z=e.z,this._w=e.w,this._onChangeCallback(),this}setFromEuler(e,t=!0){let n=e._x,s=e._y,r=e._z,o=e._order,a=Math.cos,l=Math.sin,c=a(n/2),h=a(s/2),u=a(r/2),d=l(n/2),f=l(s/2),g=l(r/2);switch(o){case"XYZ":this._x=d*h*u+c*f*g,this._y=c*f*u-d*h*g,this._z=c*h*g+d*f*u,this._w=c*h*u-d*f*g;break;case"YXZ":this._x=d*h*u+c*f*g,this._y=c*f*u-d*h*g,this._z=c*h*g-d*f*u,this._w=c*h*u+d*f*g;break;case"ZXY":this._x=d*h*u-c*f*g,this._y=c*f*u+d*h*g,this._z=c*h*g+d*f*u,this._w=c*h*u-d*f*g;break;case"ZYX":this._x=d*h*u-c*f*g,this._y=c*f*u+d*h*g,this._z=c*h*g-d*f*u,this._w=c*h*u+d*f*g;break;case"YZX":this._x=d*h*u+c*f*g,this._y=c*f*u+d*h*g,this._z=c*h*g-d*f*u,this._w=c*h*u-d*f*g;break;case"XZY":this._x=d*h*u-c*f*g,this._y=c*f*u-d*h*g,this._z=c*h*g+d*f*u,this._w=c*h*u+d*f*g;break;default:console.warn("THREE.Quaternion: .setFromEuler() encountered an unknown order: "+o)}return t===!0&&this._onChangeCallback(),this}setFromAxisAngle(e,t){let n=t/2,s=Math.sin(n);return this._x=e.x*s,this._y=e.y*s,this._z=e.z*s,this._w=Math.cos(n),this._onChangeCallback(),this}setFromRotationMatrix(e){let t=e.elements,n=t[0],s=t[4],r=t[8],o=t[1],a=t[5],l=t[9],c=t[2],h=t[6],u=t[10],d=n+a+u;if(d>0){let f=.5/Math.sqrt(d+1);this._w=.25/f,this._x=(h-l)*f,this._y=(r-c)*f,this._z=(o-s)*f}else if(n>a&&n>u){let f=2*Math.sqrt(1+n-a-u);this._w=(h-l)/f,this._x=.25*f,this._y=(s+o)/f,this._z=(r+c)/f}else if(a>u){let f=2*Math.sqrt(1+a-n-u);this._w=(r-c)/f,this._x=(s+o)/f,this._y=.25*f,this._z=(l+h)/f}else{let f=2*Math.sqrt(1+u-n-a);this._w=(o-s)/f,this._x=(r+c)/f,this._y=(l+h)/f,this._z=.25*f}return this._onChangeCallback(),this}setFromUnitVectors(e,t){let n=e.dot(t)+1;return n<Number.EPSILON?(n=0,Math.abs(e.x)>Math.abs(e.z)?(this._x=-e.y,this._y=e.x,this._z=0,this._w=n):(this._x=0,this._y=-e.z,this._z=e.y,this._w=n)):(this._x=e.y*t.z-e.z*t.y,this._y=e.z*t.x-e.x*t.z,this._z=e.x*t.y-e.y*t.x,this._w=n),this.normalize()}angleTo(e){return 2*Math.acos(Math.abs(Ct(this.dot(e),-1,1)))}rotateTowards(e,t){let n=this.angleTo(e);if(n===0)return this;let s=Math.min(1,t/n);return this.slerp(e,s),this}identity(){return this.set(0,0,0,1)}invert(){return this.conjugate()}conjugate(){return this._x*=-1,this._y*=-1,this._z*=-1,this._onChangeCallback(),this}dot(e){return this._x*e._x+this._y*e._y+this._z*e._z+this._w*e._w}lengthSq(){return this._x*this._x+this._y*this._y+this._z*this._z+this._w*this._w}length(){return Math.sqrt(this._x*this._x+this._y*this._y+this._z*this._z+this._w*this._w)}normalize(){let e=this.length();return e===0?(this._x=0,this._y=0,this._z=0,this._w=1):(e=1/e,this._x=this._x*e,this._y=this._y*e,this._z=this._z*e,this._w=this._w*e),this._onChangeCallback(),this}multiply(e){return this.multiplyQuaternions(this,e)}premultiply(e){return this.multiplyQuaternions(e,this)}multiplyQuaternions(e,t){let n=e._x,s=e._y,r=e._z,o=e._w,a=t._x,l=t._y,c=t._z,h=t._w;return this._x=n*h+o*a+s*c-r*l,this._y=s*h+o*l+r*a-n*c,this._z=r*h+o*c+n*l-s*a,this._w=o*h-n*a-s*l-r*c,this._onChangeCallback(),this}slerp(e,t){if(t===0)return this;if(t===1)return this.copy(e);let n=this._x,s=this._y,r=this._z,o=this._w,a=o*e._w+n*e._x+s*e._y+r*e._z;if(a<0?(this._w=-e._w,this._x=-e._x,this._y=-e._y,this._z=-e._z,a=-a):this.copy(e),a>=1)return this._w=o,this._x=n,this._y=s,this._z=r,this;let l=1-a*a;if(l<=Number.EPSILON){let f=1-t;return this._w=f*o+t*this._w,this._x=f*n+t*this._x,this._y=f*s+t*this._y,this._z=f*r+t*this._z,this.normalize(),this}let c=Math.sqrt(l),h=Math.atan2(c,a),u=Math.sin((1-t)*h)/c,d=Math.sin(t*h)/c;return this._w=o*u+this._w*d,this._x=n*u+this._x*d,this._y=s*u+this._y*d,this._z=r*u+this._z*d,this._onChangeCallback(),this}slerpQuaternions(e,t,n){return this.copy(e).slerp(t,n)}random(){let e=2*Math.PI*Math.random(),t=2*Math.PI*Math.random(),n=Math.random(),s=Math.sqrt(1-n),r=Math.sqrt(n);return this.set(s*Math.sin(e),s*Math.cos(e),r*Math.sin(t),r*Math.cos(t))}equals(e){return e._x===this._x&&e._y===this._y&&e._z===this._z&&e._w===this._w}fromArray(e,t=0){return this._x=e[t],this._y=e[t+1],this._z=e[t+2],this._w=e[t+3],this._onChangeCallback(),this}toArray(e=[],t=0){return e[t]=this._x,e[t+1]=this._y,e[t+2]=this._z,e[t+3]=this._w,e}fromBufferAttribute(e,t){return this._x=e.getX(t),this._y=e.getY(t),this._z=e.getZ(t),this._w=e.getW(t),this._onChangeCallback(),this}toJSON(){return this.toArray()}_onChange(e){return this._onChangeCallback=e,this}_onChangeCallback(){}*[Symbol.iterator](){yield this._x,yield this._y,yield this._z,yield this._w}},C=class i{constructor(e=0,t=0,n=0){i.prototype.isVector3=!0,this.x=e,this.y=t,this.z=n}set(e,t,n){return n===void 0&&(n=this.z),this.x=e,this.y=t,this.z=n,this}setScalar(e){return this.x=e,this.y=e,this.z=e,this}setX(e){return this.x=e,this}setY(e){return this.y=e,this}setZ(e){return this.z=e,this}setComponent(e,t){switch(e){case 0:this.x=t;break;case 1:this.y=t;break;case 2:this.z=t;break;default:throw new Error("index is out of range: "+e)}return this}getComponent(e){switch(e){case 0:return this.x;case 1:return this.y;case 2:return this.z;default:throw new Error("index is out of range: "+e)}}clone(){return new this.constructor(this.x,this.y,this.z)}copy(e){return this.x=e.x,this.y=e.y,this.z=e.z,this}add(e){return this.x+=e.x,this.y+=e.y,this.z+=e.z,this}addScalar(e){return this.x+=e,this.y+=e,this.z+=e,this}addVectors(e,t){return this.x=e.x+t.x,this.y=e.y+t.y,this.z=e.z+t.z,this}addScaledVector(e,t){return this.x+=e.x*t,this.y+=e.y*t,this.z+=e.z*t,this}sub(e){return this.x-=e.x,this.y-=e.y,this.z-=e.z,this}subScalar(e){return this.x-=e,this.y-=e,this.z-=e,this}subVectors(e,t){return this.x=e.x-t.x,this.y=e.y-t.y,this.z=e.z-t.z,this}multiply(e){return this.x*=e.x,this.y*=e.y,this.z*=e.z,this}multiplyScalar(e){return this.x*=e,this.y*=e,this.z*=e,this}multiplyVectors(e,t){return this.x=e.x*t.x,this.y=e.y*t.y,this.z=e.z*t.z,this}applyEuler(e){return this.applyQuaternion(Qc.setFromEuler(e))}applyAxisAngle(e,t){return this.applyQuaternion(Qc.setFromAxisAngle(e,t))}applyMatrix3(e){let t=this.x,n=this.y,s=this.z,r=e.elements;return this.x=r[0]*t+r[3]*n+r[6]*s,this.y=r[1]*t+r[4]*n+r[7]*s,this.z=r[2]*t+r[5]*n+r[8]*s,this}applyNormalMatrix(e){return this.applyMatrix3(e).normalize()}applyMatrix4(e){let t=this.x,n=this.y,s=this.z,r=e.elements,o=1/(r[3]*t+r[7]*n+r[11]*s+r[15]);return this.x=(r[0]*t+r[4]*n+r[8]*s+r[12])*o,this.y=(r[1]*t+r[5]*n+r[9]*s+r[13])*o,this.z=(r[2]*t+r[6]*n+r[10]*s+r[14])*o,this}applyQuaternion(e){let t=this.x,n=this.y,s=this.z,r=e.x,o=e.y,a=e.z,l=e.w,c=2*(o*s-a*n),h=2*(a*t-r*s),u=2*(r*n-o*t);return this.x=t+l*c+o*u-a*h,this.y=n+l*h+a*c-r*u,this.z=s+l*u+r*h-o*c,this}project(e){return this.applyMatrix4(e.matrixWorldInverse).applyMatrix4(e.projectionMatrix)}unproject(e){return this.applyMatrix4(e.projectionMatrixInverse).applyMatrix4(e.matrixWorld)}transformDirection(e){let t=this.x,n=this.y,s=this.z,r=e.elements;return this.x=r[0]*t+r[4]*n+r[8]*s,this.y=r[1]*t+r[5]*n+r[9]*s,this.z=r[2]*t+r[6]*n+r[10]*s,this.normalize()}divide(e){return this.x/=e.x,this.y/=e.y,this.z/=e.z,this}divideScalar(e){return this.multiplyScalar(1/e)}min(e){return this.x=Math.min(this.x,e.x),this.y=Math.min(this.y,e.y),this.z=Math.min(this.z,e.z),this}max(e){return this.x=Math.max(this.x,e.x),this.y=Math.max(this.y,e.y),this.z=Math.max(this.z,e.z),this}clamp(e,t){return this.x=Math.max(e.x,Math.min(t.x,this.x)),this.y=Math.max(e.y,Math.min(t.y,this.y)),this.z=Math.max(e.z,Math.min(t.z,this.z)),this}clampScalar(e,t){return this.x=Math.max(e,Math.min(t,this.x)),this.y=Math.max(e,Math.min(t,this.y)),this.z=Math.max(e,Math.min(t,this.z)),this}clampLength(e,t){let n=this.length();return this.divideScalar(n||1).multiplyScalar(Math.max(e,Math.min(t,n)))}floor(){return this.x=Math.floor(this.x),this.y=Math.floor(this.y),this.z=Math.floor(this.z),this}ceil(){return this.x=Math.ceil(this.x),this.y=Math.ceil(this.y),this.z=Math.ceil(this.z),this}round(){return this.x=Math.round(this.x),this.y=Math.round(this.y),this.z=Math.round(this.z),this}roundToZero(){return this.x=Math.trunc(this.x),this.y=Math.trunc(this.y),this.z=Math.trunc(this.z),this}negate(){return this.x=-this.x,this.y=-this.y,this.z=-this.z,this}dot(e){return this.x*e.x+this.y*e.y+this.z*e.z}lengthSq(){return this.x*this.x+this.y*this.y+this.z*this.z}length(){return Math.sqrt(this.x*this.x+this.y*this.y+this.z*this.z)}manhattanLength(){return Math.abs(this.x)+Math.abs(this.y)+Math.abs(this.z)}normalize(){return this.divideScalar(this.length()||1)}setLength(e){return this.normalize().multiplyScalar(e)}lerp(e,t){return this.x+=(e.x-this.x)*t,this.y+=(e.y-this.y)*t,this.z+=(e.z-this.z)*t,this}lerpVectors(e,t,n){return this.x=e.x+(t.x-e.x)*n,this.y=e.y+(t.y-e.y)*n,this.z=e.z+(t.z-e.z)*n,this}cross(e){return this.crossVectors(this,e)}crossVectors(e,t){let n=e.x,s=e.y,r=e.z,o=t.x,a=t.y,l=t.z;return this.x=s*l-r*a,this.y=r*o-n*l,this.z=n*a-s*o,this}projectOnVector(e){let t=e.lengthSq();if(t===0)return this.set(0,0,0);let n=e.dot(this)/t;return this.copy(e).multiplyScalar(n)}projectOnPlane(e){return Oo.copy(this).projectOnVector(e),this.sub(Oo)}reflect(e){return this.sub(Oo.copy(e).multiplyScalar(2*this.dot(e)))}angleTo(e){let t=Math.sqrt(this.lengthSq()*e.lengthSq());if(t===0)return Math.PI/2;let n=this.dot(e)/t;return Math.acos(Ct(n,-1,1))}distanceTo(e){return Math.sqrt(this.distanceToSquared(e))}distanceToSquared(e){let t=this.x-e.x,n=this.y-e.y,s=this.z-e.z;return t*t+n*n+s*s}manhattanDistanceTo(e){return Math.abs(this.x-e.x)+Math.abs(this.y-e.y)+Math.abs(this.z-e.z)}setFromSpherical(e){return this.setFromSphericalCoords(e.radius,e.phi,e.theta)}setFromSphericalCoords(e,t,n){let s=Math.sin(t)*e;return this.x=s*Math.sin(n),this.y=Math.cos(t)*e,this.z=s*Math.cos(n),this}setFromCylindrical(e){return this.setFromCylindricalCoords(e.radius,e.theta,e.y)}setFromCylindricalCoords(e,t,n){return this.x=e*Math.sin(t),this.y=n,this.z=e*Math.cos(t),this}setFromMatrixPosition(e){let t=e.elements;return this.x=t[12],this.y=t[13],this.z=t[14],this}setFromMatrixScale(e){let t=this.setFromMatrixColumn(e,0).length(),n=this.setFromMatrixColumn(e,1).length(),s=this.setFromMatrixColumn(e,2).length();return this.x=t,this.y=n,this.z=s,this}setFromMatrixColumn(e,t){return this.fromArray(e.elements,t*4)}setFromMatrix3Column(e,t){return this.fromArray(e.elements,t*3)}setFromEuler(e){return this.x=e._x,this.y=e._y,this.z=e._z,this}setFromColor(e){return this.x=e.r,this.y=e.g,this.z=e.b,this}equals(e){return e.x===this.x&&e.y===this.y&&e.z===this.z}fromArray(e,t=0){return this.x=e[t],this.y=e[t+1],this.z=e[t+2],this}toArray(e=[],t=0){return e[t]=this.x,e[t+1]=this.y,e[t+2]=this.z,e}fromBufferAttribute(e,t){return this.x=e.getX(t),this.y=e.getY(t),this.z=e.getZ(t),this}random(){return this.x=Math.random(),this.y=Math.random(),this.z=Math.random(),this}randomDirection(){let e=Math.random()*Math.PI*2,t=Math.random()*2-1,n=Math.sqrt(1-t*t);return this.x=n*Math.cos(e),this.y=t,this.z=n*Math.sin(e),this}*[Symbol.iterator](){yield this.x,yield this.y,yield this.z}},Oo=new C,Qc=new Gt,Ot=class{constructor(e=new C(1/0,1/0,1/0),t=new C(-1/0,-1/0,-1/0)){this.isBox3=!0,this.min=e,this.max=t}set(e,t){return this.min.copy(e),this.max.copy(t),this}setFromArray(e){this.makeEmpty();for(let t=0,n=e.length;t<n;t+=3)this.expandByPoint(pn.fromArray(e,t));return this}setFromBufferAttribute(e){this.makeEmpty();for(let t=0,n=e.count;t<n;t++)this.expandByPoint(pn.fromBufferAttribute(e,t));return this}setFromPoints(e){this.makeEmpty();for(let t=0,n=e.length;t<n;t++)this.expandByPoint(e[t]);return this}setFromCenterAndSize(e,t){let n=pn.copy(t).multiplyScalar(.5);return this.min.copy(e).sub(n),this.max.copy(e).add(n),this}setFromObject(e,t=!1){return this.makeEmpty(),this.expandByObject(e,t)}clone(){return new this.constructor().copy(this)}copy(e){return this.min.copy(e.min),this.max.copy(e.max),this}makeEmpty(){return this.min.x=this.min.y=this.min.z=1/0,this.max.x=this.max.y=this.max.z=-1/0,this}isEmpty(){return this.max.x<this.min.x||this.max.y<this.min.y||this.max.z<this.min.z}getCenter(e){return this.isEmpty()?e.set(0,0,0):e.addVectors(this.min,this.max).multiplyScalar(.5)}getSize(e){return this.isEmpty()?e.set(0,0,0):e.subVectors(this.max,this.min)}expandByPoint(e){return this.min.min(e),this.max.max(e),this}expandByVector(e){return this.min.sub(e),this.max.add(e),this}expandByScalar(e){return this.min.addScalar(-e),this.max.addScalar(e),this}expandByObject(e,t=!1){e.updateWorldMatrix(!1,!1);let n=e.geometry;if(n!==void 0){let r=n.getAttribute("position");if(t===!0&&r!==void 0&&e.isInstancedMesh!==!0)for(let o=0,a=r.count;o<a;o++)e.isMesh===!0?e.getVertexPosition(o,pn):pn.fromBufferAttribute(r,o),pn.applyMatrix4(e.matrixWorld),this.expandByPoint(pn);else e.boundingBox!==void 0?(e.boundingBox===null&&e.computeBoundingBox(),hr.copy(e.boundingBox)):(n.boundingBox===null&&n.computeBoundingBox(),hr.copy(n.boundingBox)),hr.applyMatrix4(e.matrixWorld),this.union(hr)}let s=e.children;for(let r=0,o=s.length;r<o;r++)this.expandByObject(s[r],t);return this}containsPoint(e){return e.x>=this.min.x&&e.x<=this.max.x&&e.y>=this.min.y&&e.y<=this.max.y&&e.z>=this.min.z&&e.z<=this.max.z}containsBox(e){return this.min.x<=e.min.x&&e.max.x<=this.max.x&&this.min.y<=e.min.y&&e.max.y<=this.max.y&&this.min.z<=e.min.z&&e.max.z<=this.max.z}getParameter(e,t){return t.set((e.x-this.min.x)/(this.max.x-this.min.x),(e.y-this.min.y)/(this.max.y-this.min.y),(e.z-this.min.z)/(this.max.z-this.min.z))}intersectsBox(e){return e.max.x>=this.min.x&&e.min.x<=this.max.x&&e.max.y>=this.min.y&&e.min.y<=this.max.y&&e.max.z>=this.min.z&&e.min.z<=this.max.z}intersectsSphere(e){return this.clampPoint(e.center,pn),pn.distanceToSquared(e.center)<=e.radius*e.radius}intersectsPlane(e){let t,n;return e.normal.x>0?(t=e.normal.x*this.min.x,n=e.normal.x*this.max.x):(t=e.normal.x*this.max.x,n=e.normal.x*this.min.x),e.normal.y>0?(t+=e.normal.y*this.min.y,n+=e.normal.y*this.max.y):(t+=e.normal.y*this.max.y,n+=e.normal.y*this.min.y),e.normal.z>0?(t+=e.normal.z*this.min.z,n+=e.normal.z*this.max.z):(t+=e.normal.z*this.max.z,n+=e.normal.z*this.min.z),t<=-e.constant&&n>=-e.constant}intersectsTriangle(e){if(this.isEmpty())return!1;this.getCenter(Cs),ur.subVectors(this.max,Cs),Vi.subVectors(e.a,Cs),Gi.subVectors(e.b,Cs),Wi.subVectors(e.c,Cs),ni.subVectors(Gi,Vi),ii.subVectors(Wi,Gi),Si.subVectors(Vi,Wi);let t=[0,-ni.z,ni.y,0,-ii.z,ii.y,0,-Si.z,Si.y,ni.z,0,-ni.x,ii.z,0,-ii.x,Si.z,0,-Si.x,-ni.y,ni.x,0,-ii.y,ii.x,0,-Si.y,Si.x,0];return!Fo(t,Vi,Gi,Wi,ur)||(t=[1,0,0,0,1,0,0,0,1],!Fo(t,Vi,Gi,Wi,ur))?!1:(dr.crossVectors(ni,ii),t=[dr.x,dr.y,dr.z],Fo(t,Vi,Gi,Wi,ur))}clampPoint(e,t){return t.copy(e).clamp(this.min,this.max)}distanceToPoint(e){return this.clampPoint(e,pn).distanceTo(e)}getBoundingSphere(e){return this.isEmpty()?e.makeEmpty():(this.getCenter(e.center),e.radius=this.getSize(pn).length()*.5),e}intersect(e){return this.min.max(e.min),this.max.min(e.max),this.isEmpty()&&this.makeEmpty(),this}union(e){return this.min.min(e.min),this.max.max(e.max),this}applyMatrix4(e){return this.isEmpty()?this:(Pn[0].set(this.min.x,this.min.y,this.min.z).applyMatrix4(e),Pn[1].set(this.min.x,this.min.y,this.max.z).applyMatrix4(e),Pn[2].set(this.min.x,this.max.y,this.min.z).applyMatrix4(e),Pn[3].set(this.min.x,this.max.y,this.max.z).applyMatrix4(e),Pn[4].set(this.max.x,this.min.y,this.min.z).applyMatrix4(e),Pn[5].set(this.max.x,this.min.y,this.max.z).applyMatrix4(e),Pn[6].set(this.max.x,this.max.y,this.min.z).applyMatrix4(e),Pn[7].set(this.max.x,this.max.y,this.max.z).applyMatrix4(e),this.setFromPoints(Pn),this)}translate(e){return this.min.add(e),this.max.add(e),this}equals(e){return e.min.equals(this.min)&&e.max.equals(this.max)}},Pn=[new C,new C,new C,new C,new C,new C,new C,new C],pn=new C,hr=new Ot,Vi=new C,Gi=new C,Wi=new C,ni=new C,ii=new C,Si=new C,Cs=new C,ur=new C,dr=new C,bi=new C;function Fo(i,e,t,n,s){for(let r=0,o=i.length-3;r<=o;r+=3){bi.fromArray(i,r);let a=s.x*Math.abs(bi.x)+s.y*Math.abs(bi.y)+s.z*Math.abs(bi.z),l=e.dot(bi),c=t.dot(bi),h=n.dot(bi);if(Math.max(-Math.max(l,c,h),Math.min(l,c,h))>a)return!1}return!0}var rf=new Ot,Is=new C,Bo=new C,jt=class{constructor(e=new C,t=-1){this.isSphere=!0,this.center=e,this.radius=t}set(e,t){return this.center.copy(e),this.radius=t,this}setFromPoints(e,t){let n=this.center;t!==void 0?n.copy(t):rf.setFromPoints(e).getCenter(n);let s=0;for(let r=0,o=e.length;r<o;r++)s=Math.max(s,n.distanceToSquared(e[r]));return this.radius=Math.sqrt(s),this}copy(e){return this.center.copy(e.center),this.radius=e.radius,this}isEmpty(){return this.radius<0}makeEmpty(){return this.center.set(0,0,0),this.radius=-1,this}containsPoint(e){return e.distanceToSquared(this.center)<=this.radius*this.radius}distanceToPoint(e){return e.distanceTo(this.center)-this.radius}intersectsSphere(e){let t=this.radius+e.radius;return e.center.distanceToSquared(this.center)<=t*t}intersectsBox(e){return e.intersectsSphere(this)}intersectsPlane(e){return Math.abs(e.distanceToPoint(this.center))<=this.radius}clampPoint(e,t){let n=this.center.distanceToSquared(e);return t.copy(e),n>this.radius*this.radius&&(t.sub(this.center).normalize(),t.multiplyScalar(this.radius).add(this.center)),t}getBoundingBox(e){return this.isEmpty()?(e.makeEmpty(),e):(e.set(this.center,this.center),e.expandByScalar(this.radius),e)}applyMatrix4(e){return this.center.applyMatrix4(e),this.radius=this.radius*e.getMaxScaleOnAxis(),this}translate(e){return this.center.add(e),this}expandByPoint(e){if(this.isEmpty())return this.center.copy(e),this.radius=0,this;Is.subVectors(e,this.center);let t=Is.lengthSq();if(t>this.radius*this.radius){let n=Math.sqrt(t),s=(n-this.radius)*.5;this.center.addScaledVector(Is,s/n),this.radius+=s}return this}union(e){return e.isEmpty()?this:this.isEmpty()?(this.copy(e),this):(this.center.equals(e.center)===!0?this.radius=Math.max(this.radius,e.radius):(Bo.subVectors(e.center,this.center).setLength(e.radius),this.expandByPoint(Is.copy(e.center).add(Bo)),this.expandByPoint(Is.copy(e.center).sub(Bo))),this)}equals(e){return e.center.equals(this.center)&&e.radius===this.radius}clone(){return new this.constructor().copy(this)}},Ln=new C,zo=new C,fr=new C,si=new C,ko=new C,pr=new C,Ho=new C,Xn=class{constructor(e=new C,t=new C(0,0,-1)){this.origin=e,this.direction=t}set(e,t){return this.origin.copy(e),this.direction.copy(t),this}copy(e){return this.origin.copy(e.origin),this.direction.copy(e.direction),this}at(e,t){return t.copy(this.origin).addScaledVector(this.direction,e)}lookAt(e){return this.direction.copy(e).sub(this.origin).normalize(),this}recast(e){return this.origin.copy(this.at(e,Ln)),this}closestPointToPoint(e,t){t.subVectors(e,this.origin);let n=t.dot(this.direction);return n<0?t.copy(this.origin):t.copy(this.origin).addScaledVector(this.direction,n)}distanceToPoint(e){return Math.sqrt(this.distanceSqToPoint(e))}distanceSqToPoint(e){let t=Ln.subVectors(e,this.origin).dot(this.direction);return t<0?this.origin.distanceToSquared(e):(Ln.copy(this.origin).addScaledVector(this.direction,t),Ln.distanceToSquared(e))}distanceSqToSegment(e,t,n,s){zo.copy(e).add(t).multiplyScalar(.5),fr.copy(t).sub(e).normalize(),si.copy(this.origin).sub(zo);let r=e.distanceTo(t)*.5,o=-this.direction.dot(fr),a=si.dot(this.direction),l=-si.dot(fr),c=si.lengthSq(),h=Math.abs(1-o*o),u,d,f,g;if(h>0)if(u=o*l-a,d=o*a-l,g=r*h,u>=0)if(d>=-g)if(d<=g){let _=1/h;u*=_,d*=_,f=u*(u+o*d+2*a)+d*(o*u+d+2*l)+c}else d=r,u=Math.max(0,-(o*d+a)),f=-u*u+d*(d+2*l)+c;else d=-r,u=Math.max(0,-(o*d+a)),f=-u*u+d*(d+2*l)+c;else d<=-g?(u=Math.max(0,-(-o*r+a)),d=u>0?-r:Math.min(Math.max(-r,-l),r),f=-u*u+d*(d+2*l)+c):d<=g?(u=0,d=Math.min(Math.max(-r,-l),r),f=d*(d+2*l)+c):(u=Math.max(0,-(o*r+a)),d=u>0?r:Math.min(Math.max(-r,-l),r),f=-u*u+d*(d+2*l)+c);else d=o>0?-r:r,u=Math.max(0,-(o*d+a)),f=-u*u+d*(d+2*l)+c;return n&&n.copy(this.origin).addScaledVector(this.direction,u),s&&s.copy(zo).addScaledVector(fr,d),f}intersectSphere(e,t){Ln.subVectors(e.center,this.origin);let n=Ln.dot(this.direction),s=Ln.dot(Ln)-n*n,r=e.radius*e.radius;if(s>r)return null;let o=Math.sqrt(r-s),a=n-o,l=n+o;return l<0?null:a<0?this.at(l,t):this.at(a,t)}intersectsSphere(e){return this.distanceSqToPoint(e.center)<=e.radius*e.radius}distanceToPlane(e){let t=e.normal.dot(this.direction);if(t===0)return e.distanceToPoint(this.origin)===0?0:null;let n=-(this.origin.dot(e.normal)+e.constant)/t;return n>=0?n:null}intersectPlane(e,t){let n=this.distanceToPlane(e);return n===null?null:this.at(n,t)}intersectsPlane(e){let t=e.distanceToPoint(this.origin);return t===0||e.normal.dot(this.direction)*t<0}intersectBox(e,t){let n,s,r,o,a,l,c=1/this.direction.x,h=1/this.direction.y,u=1/this.direction.z,d=this.origin;return c>=0?(n=(e.min.x-d.x)*c,s=(e.max.x-d.x)*c):(n=(e.max.x-d.x)*c,s=(e.min.x-d.x)*c),h>=0?(r=(e.min.y-d.y)*h,o=(e.max.y-d.y)*h):(r=(e.max.y-d.y)*h,o=(e.min.y-d.y)*h),n>o||r>s||((r>n||isNaN(n))&&(n=r),(o<s||isNaN(s))&&(s=o),u>=0?(a=(e.min.z-d.z)*u,l=(e.max.z-d.z)*u):(a=(e.max.z-d.z)*u,l=(e.min.z-d.z)*u),n>l||a>s)||((a>n||n!==n)&&(n=a),(l<s||s!==s)&&(s=l),s<0)?null:this.at(n>=0?n:s,t)}intersectsBox(e){return this.intersectBox(e,Ln)!==null}intersectTriangle(e,t,n,s,r){ko.subVectors(t,e),pr.subVectors(n,e),Ho.crossVectors(ko,pr);let o=this.direction.dot(Ho),a;if(o>0){if(s)return null;a=1}else if(o<0)a=-1,o=-o;else return null;si.subVectors(this.origin,e);let l=a*this.direction.dot(pr.crossVectors(si,pr));if(l<0)return null;let c=a*this.direction.dot(ko.cross(si));if(c<0||l+c>o)return null;let h=-a*si.dot(Ho);return h<0?null:this.at(h/o,r)}applyMatrix4(e){return this.origin.applyMatrix4(e),this.direction.transformDirection(e),this}equals(e){return e.origin.equals(this.origin)&&e.direction.equals(this.direction)}clone(){return new this.constructor().copy(this)}},Le=class i{constructor(e,t,n,s,r,o,a,l,c,h,u,d,f,g,_,m){i.prototype.isMatrix4=!0,this.elements=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],e!==void 0&&this.set(e,t,n,s,r,o,a,l,c,h,u,d,f,g,_,m)}set(e,t,n,s,r,o,a,l,c,h,u,d,f,g,_,m){let p=this.elements;return p[0]=e,p[4]=t,p[8]=n,p[12]=s,p[1]=r,p[5]=o,p[9]=a,p[13]=l,p[2]=c,p[6]=h,p[10]=u,p[14]=d,p[3]=f,p[7]=g,p[11]=_,p[15]=m,this}identity(){return this.set(1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1),this}clone(){return new i().fromArray(this.elements)}copy(e){let t=this.elements,n=e.elements;return t[0]=n[0],t[1]=n[1],t[2]=n[2],t[3]=n[3],t[4]=n[4],t[5]=n[5],t[6]=n[6],t[7]=n[7],t[8]=n[8],t[9]=n[9],t[10]=n[10],t[11]=n[11],t[12]=n[12],t[13]=n[13],t[14]=n[14],t[15]=n[15],this}copyPosition(e){let t=this.elements,n=e.elements;return t[12]=n[12],t[13]=n[13],t[14]=n[14],this}setFromMatrix3(e){let t=e.elements;return this.set(t[0],t[3],t[6],0,t[1],t[4],t[7],0,t[2],t[5],t[8],0,0,0,0,1),this}extractBasis(e,t,n){return e.setFromMatrixColumn(this,0),t.setFromMatrixColumn(this,1),n.setFromMatrixColumn(this,2),this}makeBasis(e,t,n){return this.set(e.x,t.x,n.x,0,e.y,t.y,n.y,0,e.z,t.z,n.z,0,0,0,0,1),this}extractRotation(e){let t=this.elements,n=e.elements,s=1/Xi.setFromMatrixColumn(e,0).length(),r=1/Xi.setFromMatrixColumn(e,1).length(),o=1/Xi.setFromMatrixColumn(e,2).length();return t[0]=n[0]*s,t[1]=n[1]*s,t[2]=n[2]*s,t[3]=0,t[4]=n[4]*r,t[5]=n[5]*r,t[6]=n[6]*r,t[7]=0,t[8]=n[8]*o,t[9]=n[9]*o,t[10]=n[10]*o,t[11]=0,t[12]=0,t[13]=0,t[14]=0,t[15]=1,this}makeRotationFromEuler(e){let t=this.elements,n=e.x,s=e.y,r=e.z,o=Math.cos(n),a=Math.sin(n),l=Math.cos(s),c=Math.sin(s),h=Math.cos(r),u=Math.sin(r);if(e.order==="XYZ"){let d=o*h,f=o*u,g=a*h,_=a*u;t[0]=l*h,t[4]=-l*u,t[8]=c,t[1]=f+g*c,t[5]=d-_*c,t[9]=-a*l,t[2]=_-d*c,t[6]=g+f*c,t[10]=o*l}else if(e.order==="YXZ"){let d=l*h,f=l*u,g=c*h,_=c*u;t[0]=d+_*a,t[4]=g*a-f,t[8]=o*c,t[1]=o*u,t[5]=o*h,t[9]=-a,t[2]=f*a-g,t[6]=_+d*a,t[10]=o*l}else if(e.order==="ZXY"){let d=l*h,f=l*u,g=c*h,_=c*u;t[0]=d-_*a,t[4]=-o*u,t[8]=g+f*a,t[1]=f+g*a,t[5]=o*h,t[9]=_-d*a,t[2]=-o*c,t[6]=a,t[10]=o*l}else if(e.order==="ZYX"){let d=o*h,f=o*u,g=a*h,_=a*u;t[0]=l*h,t[4]=g*c-f,t[8]=d*c+_,t[1]=l*u,t[5]=_*c+d,t[9]=f*c-g,t[2]=-c,t[6]=a*l,t[10]=o*l}else if(e.order==="YZX"){let d=o*l,f=o*c,g=a*l,_=a*c;t[0]=l*h,t[4]=_-d*u,t[8]=g*u+f,t[1]=u,t[5]=o*h,t[9]=-a*h,t[2]=-c*h,t[6]=f*u+g,t[10]=d-_*u}else if(e.order==="XZY"){let d=o*l,f=o*c,g=a*l,_=a*c;t[0]=l*h,t[4]=-u,t[8]=c*h,t[1]=d*u+_,t[5]=o*h,t[9]=f*u-g,t[2]=g*u-f,t[6]=a*h,t[10]=_*u+d}return t[3]=0,t[7]=0,t[11]=0,t[12]=0,t[13]=0,t[14]=0,t[15]=1,this}makeRotationFromQuaternion(e){return this.compose(of,e,af)}lookAt(e,t,n){let s=this.elements;return Yt.subVectors(e,t),Yt.lengthSq()===0&&(Yt.z=1),Yt.normalize(),ri.crossVectors(n,Yt),ri.lengthSq()===0&&(Math.abs(n.z)===1?Yt.x+=1e-4:Yt.z+=1e-4,Yt.normalize(),ri.crossVectors(n,Yt)),ri.normalize(),mr.crossVectors(Yt,ri),s[0]=ri.x,s[4]=mr.x,s[8]=Yt.x,s[1]=ri.y,s[5]=mr.y,s[9]=Yt.y,s[2]=ri.z,s[6]=mr.z,s[10]=Yt.z,this}multiply(e){return this.multiplyMatrices(this,e)}premultiply(e){return this.multiplyMatrices(e,this)}multiplyMatrices(e,t){let n=e.elements,s=t.elements,r=this.elements,o=n[0],a=n[4],l=n[8],c=n[12],h=n[1],u=n[5],d=n[9],f=n[13],g=n[2],_=n[6],m=n[10],p=n[14],w=n[3],b=n[7],x=n[11],P=n[15],T=s[0],A=s[4],R=s[8],M=s[12],v=s[1],I=s[5],G=s[9],O=s[13],X=s[2],Y=s[6],V=s[10],Q=s[14],B=s[3],H=s[7],j=s[11],ie=s[15];return r[0]=o*T+a*v+l*X+c*B,r[4]=o*A+a*I+l*Y+c*H,r[8]=o*R+a*G+l*V+c*j,r[12]=o*M+a*O+l*Q+c*ie,r[1]=h*T+u*v+d*X+f*B,r[5]=h*A+u*I+d*Y+f*H,r[9]=h*R+u*G+d*V+f*j,r[13]=h*M+u*O+d*Q+f*ie,r[2]=g*T+_*v+m*X+p*B,r[6]=g*A+_*I+m*Y+p*H,r[10]=g*R+_*G+m*V+p*j,r[14]=g*M+_*O+m*Q+p*ie,r[3]=w*T+b*v+x*X+P*B,r[7]=w*A+b*I+x*Y+P*H,r[11]=w*R+b*G+x*V+P*j,r[15]=w*M+b*O+x*Q+P*ie,this}multiplyScalar(e){let t=this.elements;return t[0]*=e,t[4]*=e,t[8]*=e,t[12]*=e,t[1]*=e,t[5]*=e,t[9]*=e,t[13]*=e,t[2]*=e,t[6]*=e,t[10]*=e,t[14]*=e,t[3]*=e,t[7]*=e,t[11]*=e,t[15]*=e,this}determinant(){let e=this.elements,t=e[0],n=e[4],s=e[8],r=e[12],o=e[1],a=e[5],l=e[9],c=e[13],h=e[2],u=e[6],d=e[10],f=e[14],g=e[3],_=e[7],m=e[11],p=e[15];return g*(+r*l*u-s*c*u-r*a*d+n*c*d+s*a*f-n*l*f)+_*(+t*l*f-t*c*d+r*o*d-s*o*f+s*c*h-r*l*h)+m*(+t*c*u-t*a*f-r*o*u+n*o*f+r*a*h-n*c*h)+p*(-s*a*h-t*l*u+t*a*d+s*o*u-n*o*d+n*l*h)}transpose(){let e=this.elements,t;return t=e[1],e[1]=e[4],e[4]=t,t=e[2],e[2]=e[8],e[8]=t,t=e[6],e[6]=e[9],e[9]=t,t=e[3],e[3]=e[12],e[12]=t,t=e[7],e[7]=e[13],e[13]=t,t=e[11],e[11]=e[14],e[14]=t,this}setPosition(e,t,n){let s=this.elements;return e.isVector3?(s[12]=e.x,s[13]=e.y,s[14]=e.z):(s[12]=e,s[13]=t,s[14]=n),this}invert(){let e=this.elements,t=e[0],n=e[1],s=e[2],r=e[3],o=e[4],a=e[5],l=e[6],c=e[7],h=e[8],u=e[9],d=e[10],f=e[11],g=e[12],_=e[13],m=e[14],p=e[15],w=u*m*c-_*d*c+_*l*f-a*m*f-u*l*p+a*d*p,b=g*d*c-h*m*c-g*l*f+o*m*f+h*l*p-o*d*p,x=h*_*c-g*u*c+g*a*f-o*_*f-h*a*p+o*u*p,P=g*u*l-h*_*l-g*a*d+o*_*d+h*a*m-o*u*m,T=t*w+n*b+s*x+r*P;if(T===0)return this.set(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0);let A=1/T;return e[0]=w*A,e[1]=(_*d*r-u*m*r-_*s*f+n*m*f+u*s*p-n*d*p)*A,e[2]=(a*m*r-_*l*r+_*s*c-n*m*c-a*s*p+n*l*p)*A,e[3]=(u*l*r-a*d*r-u*s*c+n*d*c+a*s*f-n*l*f)*A,e[4]=b*A,e[5]=(h*m*r-g*d*r+g*s*f-t*m*f-h*s*p+t*d*p)*A,e[6]=(g*l*r-o*m*r-g*s*c+t*m*c+o*s*p-t*l*p)*A,e[7]=(o*d*r-h*l*r+h*s*c-t*d*c-o*s*f+t*l*f)*A,e[8]=x*A,e[9]=(g*u*r-h*_*r-g*n*f+t*_*f+h*n*p-t*u*p)*A,e[10]=(o*_*r-g*a*r+g*n*c-t*_*c-o*n*p+t*a*p)*A,e[11]=(h*a*r-o*u*r-h*n*c+t*u*c+o*n*f-t*a*f)*A,e[12]=P*A,e[13]=(h*_*s-g*u*s+g*n*d-t*_*d-h*n*m+t*u*m)*A,e[14]=(g*a*s-o*_*s-g*n*l+t*_*l+o*n*m-t*a*m)*A,e[15]=(o*u*s-h*a*s+h*n*l-t*u*l-o*n*d+t*a*d)*A,this}scale(e){let t=this.elements,n=e.x,s=e.y,r=e.z;return t[0]*=n,t[4]*=s,t[8]*=r,t[1]*=n,t[5]*=s,t[9]*=r,t[2]*=n,t[6]*=s,t[10]*=r,t[3]*=n,t[7]*=s,t[11]*=r,this}getMaxScaleOnAxis(){let e=this.elements,t=e[0]*e[0]+e[1]*e[1]+e[2]*e[2],n=e[4]*e[4]+e[5]*e[5]+e[6]*e[6],s=e[8]*e[8]+e[9]*e[9]+e[10]*e[10];return Math.sqrt(Math.max(t,n,s))}makeTranslation(e,t,n){return e.isVector3?this.set(1,0,0,e.x,0,1,0,e.y,0,0,1,e.z,0,0,0,1):this.set(1,0,0,e,0,1,0,t,0,0,1,n,0,0,0,1),this}makeRotationX(e){let t=Math.cos(e),n=Math.sin(e);return this.set(1,0,0,0,0,t,-n,0,0,n,t,0,0,0,0,1),this}makeRotationY(e){let t=Math.cos(e),n=Math.sin(e);return this.set(t,0,n,0,0,1,0,0,-n,0,t,0,0,0,0,1),this}makeRotationZ(e){let t=Math.cos(e),n=Math.sin(e);return this.set(t,-n,0,0,n,t,0,0,0,0,1,0,0,0,0,1),this}makeRotationAxis(e,t){let n=Math.cos(t),s=Math.sin(t),r=1-n,o=e.x,a=e.y,l=e.z,c=r*o,h=r*a;return this.set(c*o+n,c*a-s*l,c*l+s*a,0,c*a+s*l,h*a+n,h*l-s*o,0,c*l-s*a,h*l+s*o,r*l*l+n,0,0,0,0,1),this}makeScale(e,t,n){return this.set(e,0,0,0,0,t,0,0,0,0,n,0,0,0,0,1),this}makeShear(e,t,n,s,r,o){return this.set(1,n,r,0,e,1,o,0,t,s,1,0,0,0,0,1),this}compose(e,t,n){let s=this.elements,r=t._x,o=t._y,a=t._z,l=t._w,c=r+r,h=o+o,u=a+a,d=r*c,f=r*h,g=r*u,_=o*h,m=o*u,p=a*u,w=l*c,b=l*h,x=l*u,P=n.x,T=n.y,A=n.z;return s[0]=(1-(_+p))*P,s[1]=(f+x)*P,s[2]=(g-b)*P,s[3]=0,s[4]=(f-x)*T,s[5]=(1-(d+p))*T,s[6]=(m+w)*T,s[7]=0,s[8]=(g+b)*A,s[9]=(m-w)*A,s[10]=(1-(d+_))*A,s[11]=0,s[12]=e.x,s[13]=e.y,s[14]=e.z,s[15]=1,this}decompose(e,t,n){let s=this.elements,r=Xi.set(s[0],s[1],s[2]).length(),o=Xi.set(s[4],s[5],s[6]).length(),a=Xi.set(s[8],s[9],s[10]).length();this.determinant()<0&&(r=-r),e.x=s[12],e.y=s[13],e.z=s[14],mn.copy(this);let c=1/r,h=1/o,u=1/a;return mn.elements[0]*=c,mn.elements[1]*=c,mn.elements[2]*=c,mn.elements[4]*=h,mn.elements[5]*=h,mn.elements[6]*=h,mn.elements[8]*=u,mn.elements[9]*=u,mn.elements[10]*=u,t.setFromRotationMatrix(mn),n.x=r,n.y=o,n.z=a,this}makePerspective(e,t,n,s,r,o,a=zn){let l=this.elements,c=2*r/(t-e),h=2*r/(n-s),u=(t+e)/(t-e),d=(n+s)/(n-s),f,g;if(a===zn)f=-(o+r)/(o-r),g=-2*o*r/(o-r);else if(a===qr)f=-o/(o-r),g=-o*r/(o-r);else throw new Error("THREE.Matrix4.makePerspective(): Invalid coordinate system: "+a);return l[0]=c,l[4]=0,l[8]=u,l[12]=0,l[1]=0,l[5]=h,l[9]=d,l[13]=0,l[2]=0,l[6]=0,l[10]=f,l[14]=g,l[3]=0,l[7]=0,l[11]=-1,l[15]=0,this}makeOrthographic(e,t,n,s,r,o,a=zn){let l=this.elements,c=1/(t-e),h=1/(n-s),u=1/(o-r),d=(t+e)*c,f=(n+s)*h,g,_;if(a===zn)g=(o+r)*u,_=-2*u;else if(a===qr)g=r*u,_=-1*u;else throw new Error("THREE.Matrix4.makeOrthographic(): Invalid coordinate system: "+a);return l[0]=2*c,l[4]=0,l[8]=0,l[12]=-d,l[1]=0,l[5]=2*h,l[9]=0,l[13]=-f,l[2]=0,l[6]=0,l[10]=_,l[14]=-g,l[3]=0,l[7]=0,l[11]=0,l[15]=1,this}equals(e){let t=this.elements,n=e.elements;for(let s=0;s<16;s++)if(t[s]!==n[s])return!1;return!0}fromArray(e,t=0){for(let n=0;n<16;n++)this.elements[n]=e[n+t];return this}toArray(e=[],t=0){let n=this.elements;return e[t]=n[0],e[t+1]=n[1],e[t+2]=n[2],e[t+3]=n[3],e[t+4]=n[4],e[t+5]=n[5],e[t+6]=n[6],e[t+7]=n[7],e[t+8]=n[8],e[t+9]=n[9],e[t+10]=n[10],e[t+11]=n[11],e[t+12]=n[12],e[t+13]=n[13],e[t+14]=n[14],e[t+15]=n[15],e}},Xi=new C,mn=new Le,of=new C(0,0,0),af=new C(1,1,1),ri=new C,mr=new C,Yt=new C,eh=new Le,th=new Gt,An=class i{constructor(e=0,t=0,n=0,s=i.DEFAULT_ORDER){this.isEuler=!0,this._x=e,this._y=t,this._z=n,this._order=s}get x(){return this._x}set x(e){this._x=e,this._onChangeCallback()}get y(){return this._y}set y(e){this._y=e,this._onChangeCallback()}get z(){return this._z}set z(e){this._z=e,this._onChangeCallback()}get order(){return this._order}set order(e){this._order=e,this._onChangeCallback()}set(e,t,n,s=this._order){return this._x=e,this._y=t,this._z=n,this._order=s,this._onChangeCallback(),this}clone(){return new this.constructor(this._x,this._y,this._z,this._order)}copy(e){return this._x=e._x,this._y=e._y,this._z=e._z,this._order=e._order,this._onChangeCallback(),this}setFromRotationMatrix(e,t=this._order,n=!0){let s=e.elements,r=s[0],o=s[4],a=s[8],l=s[1],c=s[5],h=s[9],u=s[2],d=s[6],f=s[10];switch(t){case"XYZ":this._y=Math.asin(Ct(a,-1,1)),Math.abs(a)<.9999999?(this._x=Math.atan2(-h,f),this._z=Math.atan2(-o,r)):(this._x=Math.atan2(d,c),this._z=0);break;case"YXZ":this._x=Math.asin(-Ct(h,-1,1)),Math.abs(h)<.9999999?(this._y=Math.atan2(a,f),this._z=Math.atan2(l,c)):(this._y=Math.atan2(-u,r),this._z=0);break;case"ZXY":this._x=Math.asin(Ct(d,-1,1)),Math.abs(d)<.9999999?(this._y=Math.atan2(-u,f),this._z=Math.atan2(-o,c)):(this._y=0,this._z=Math.atan2(l,r));break;case"ZYX":this._y=Math.asin(-Ct(u,-1,1)),Math.abs(u)<.9999999?(this._x=Math.atan2(d,f),this._z=Math.atan2(l,r)):(this._x=0,this._z=Math.atan2(-o,c));break;case"YZX":this._z=Math.asin(Ct(l,-1,1)),Math.abs(l)<.9999999?(this._x=Math.atan2(-h,c),this._y=Math.atan2(-u,r)):(this._x=0,this._y=Math.atan2(a,f));break;case"XZY":this._z=Math.asin(-Ct(o,-1,1)),Math.abs(o)<.9999999?(this._x=Math.atan2(d,c),this._y=Math.atan2(a,r)):(this._x=Math.atan2(-h,f),this._y=0);break;default:console.warn("THREE.Euler: .setFromRotationMatrix() encountered an unknown order: "+t)}return this._order=t,n===!0&&this._onChangeCallback(),this}setFromQuaternion(e,t,n){return eh.makeRotationFromQuaternion(e),this.setFromRotationMatrix(eh,t,n)}setFromVector3(e,t=this._order){return this.set(e.x,e.y,e.z,t)}reorder(e){return th.setFromEuler(this),this.setFromQuaternion(th,e)}equals(e){return e._x===this._x&&e._y===this._y&&e._z===this._z&&e._order===this._order}fromArray(e){return this._x=e[0],this._y=e[1],this._z=e[2],e[3]!==void 0&&(this._order=e[3]),this._onChangeCallback(),this}toArray(e=[],t=0){return e[t]=this._x,e[t+1]=this._y,e[t+2]=this._z,e[t+3]=this._order,e}_onChange(e){return this._onChangeCallback=e,this}_onChangeCallback(){}*[Symbol.iterator](){yield this._x,yield this._y,yield this._z,yield this._order}};An.DEFAULT_ORDER="XYZ";var Xs=class{constructor(){this.mask=1}set(e){this.mask=(1<<e|0)>>>0}enable(e){this.mask|=1<<e|0}enableAll(){this.mask=-1}toggle(e){this.mask^=1<<e|0}disable(e){this.mask&=~(1<<e|0)}disableAll(){this.mask=0}test(e){return(this.mask&e.mask)!==0}isEnabled(e){return(this.mask&(1<<e|0))!==0}},lf=0,nh=new C,qi=new Gt,Dn=new Le,gr=new C,Ps=new C,cf=new C,hf=new Gt,ih=new C(1,0,0),sh=new C(0,1,0),rh=new C(0,0,1),oh={type:"added"},uf={type:"removed"},Yi={type:"childadded",child:null},Vo={type:"childremoved",child:null},ht=class i extends Gn{constructor(){super(),this.isObject3D=!0,Object.defineProperty(this,"id",{value:lf++}),this.uuid=yn(),this.name="",this.type="Object3D",this.parent=null,this.children=[],this.up=i.DEFAULT_UP.clone();let e=new C,t=new An,n=new Gt,s=new C(1,1,1);function r(){n.setFromEuler(t,!1)}function o(){t.setFromQuaternion(n,void 0,!1)}t._onChange(r),n._onChange(o),Object.defineProperties(this,{position:{configurable:!0,enumerable:!0,value:e},rotation:{configurable:!0,enumerable:!0,value:t},quaternion:{configurable:!0,enumerable:!0,value:n},scale:{configurable:!0,enumerable:!0,value:s},modelViewMatrix:{value:new Le},normalMatrix:{value:new Ne}}),this.matrix=new Le,this.matrixWorld=new Le,this.matrixAutoUpdate=i.DEFAULT_MATRIX_AUTO_UPDATE,this.matrixWorldAutoUpdate=i.DEFAULT_MATRIX_WORLD_AUTO_UPDATE,this.matrixWorldNeedsUpdate=!1,this.layers=new Xs,this.visible=!0,this.castShadow=!1,this.receiveShadow=!1,this.frustumCulled=!0,this.renderOrder=0,this.animations=[],this.userData={}}onBeforeShadow(){}onAfterShadow(){}onBeforeRender(){}onAfterRender(){}applyMatrix4(e){this.matrixAutoUpdate&&this.updateMatrix(),this.matrix.premultiply(e),this.matrix.decompose(this.position,this.quaternion,this.scale)}applyQuaternion(e){return this.quaternion.premultiply(e),this}setRotationFromAxisAngle(e,t){this.quaternion.setFromAxisAngle(e,t)}setRotationFromEuler(e){this.quaternion.setFromEuler(e,!0)}setRotationFromMatrix(e){this.quaternion.setFromRotationMatrix(e)}setRotationFromQuaternion(e){this.quaternion.copy(e)}rotateOnAxis(e,t){return qi.setFromAxisAngle(e,t),this.quaternion.multiply(qi),this}rotateOnWorldAxis(e,t){return qi.setFromAxisAngle(e,t),this.quaternion.premultiply(qi),this}rotateX(e){return this.rotateOnAxis(ih,e)}rotateY(e){return this.rotateOnAxis(sh,e)}rotateZ(e){return this.rotateOnAxis(rh,e)}translateOnAxis(e,t){return nh.copy(e).applyQuaternion(this.quaternion),this.position.add(nh.multiplyScalar(t)),this}translateX(e){return this.translateOnAxis(ih,e)}translateY(e){return this.translateOnAxis(sh,e)}translateZ(e){return this.translateOnAxis(rh,e)}localToWorld(e){return this.updateWorldMatrix(!0,!1),e.applyMatrix4(this.matrixWorld)}worldToLocal(e){return this.updateWorldMatrix(!0,!1),e.applyMatrix4(Dn.copy(this.matrixWorld).invert())}lookAt(e,t,n){e.isVector3?gr.copy(e):gr.set(e,t,n);let s=this.parent;this.updateWorldMatrix(!0,!1),Ps.setFromMatrixPosition(this.matrixWorld),this.isCamera||this.isLight?Dn.lookAt(Ps,gr,this.up):Dn.lookAt(gr,Ps,this.up),this.quaternion.setFromRotationMatrix(Dn),s&&(Dn.extractRotation(s.matrixWorld),qi.setFromRotationMatrix(Dn),this.quaternion.premultiply(qi.invert()))}add(e){if(arguments.length>1){for(let t=0;t<arguments.length;t++)this.add(arguments[t]);return this}return e===this?(console.error("THREE.Object3D.add: object can't be added as a child of itself.",e),this):(e&&e.isObject3D?(e.removeFromParent(),e.parent=this,this.children.push(e),e.dispatchEvent(oh),Yi.child=e,this.dispatchEvent(Yi),Yi.child=null):console.error("THREE.Object3D.add: object not an instance of THREE.Object3D.",e),this)}remove(e){if(arguments.length>1){for(let n=0;n<arguments.length;n++)this.remove(arguments[n]);return this}let t=this.children.indexOf(e);return t!==-1&&(e.parent=null,this.children.splice(t,1),e.dispatchEvent(uf),Vo.child=e,this.dispatchEvent(Vo),Vo.child=null),this}removeFromParent(){let e=this.parent;return e!==null&&e.remove(this),this}clear(){return this.remove(...this.children)}attach(e){return this.updateWorldMatrix(!0,!1),Dn.copy(this.matrixWorld).invert(),e.parent!==null&&(e.parent.updateWorldMatrix(!0,!1),Dn.multiply(e.parent.matrixWorld)),e.applyMatrix4(Dn),e.removeFromParent(),e.parent=this,this.children.push(e),e.updateWorldMatrix(!1,!0),e.dispatchEvent(oh),Yi.child=e,this.dispatchEvent(Yi),Yi.child=null,this}getObjectById(e){return this.getObjectByProperty("id",e)}getObjectByName(e){return this.getObjectByProperty("name",e)}getObjectByProperty(e,t){if(this[e]===t)return this;for(let n=0,s=this.children.length;n<s;n++){let o=this.children[n].getObjectByProperty(e,t);if(o!==void 0)return o}}getObjectsByProperty(e,t,n=[]){this[e]===t&&n.push(this);let s=this.children;for(let r=0,o=s.length;r<o;r++)s[r].getObjectsByProperty(e,t,n);return n}getWorldPosition(e){return this.updateWorldMatrix(!0,!1),e.setFromMatrixPosition(this.matrixWorld)}getWorldQuaternion(e){return this.updateWorldMatrix(!0,!1),this.matrixWorld.decompose(Ps,e,cf),e}getWorldScale(e){return this.updateWorldMatrix(!0,!1),this.matrixWorld.decompose(Ps,hf,e),e}getWorldDirection(e){this.updateWorldMatrix(!0,!1);let t=this.matrixWorld.elements;return e.set(t[8],t[9],t[10]).normalize()}raycast(){}traverse(e){e(this);let t=this.children;for(let n=0,s=t.length;n<s;n++)t[n].traverse(e)}traverseVisible(e){if(this.visible===!1)return;e(this);let t=this.children;for(let n=0,s=t.length;n<s;n++)t[n].traverseVisible(e)}traverseAncestors(e){let t=this.parent;t!==null&&(e(t),t.traverseAncestors(e))}updateMatrix(){this.matrix.compose(this.position,this.quaternion,this.scale),this.matrixWorldNeedsUpdate=!0}updateMatrixWorld(e){this.matrixAutoUpdate&&this.updateMatrix(),(this.matrixWorldNeedsUpdate||e)&&(this.matrixWorldAutoUpdate===!0&&(this.parent===null?this.matrixWorld.copy(this.matrix):this.matrixWorld.multiplyMatrices(this.parent.matrixWorld,this.matrix)),this.matrixWorldNeedsUpdate=!1,e=!0);let t=this.children;for(let n=0,s=t.length;n<s;n++)t[n].updateMatrixWorld(e)}updateWorldMatrix(e,t){let n=this.parent;if(e===!0&&n!==null&&n.updateWorldMatrix(!0,!1),this.matrixAutoUpdate&&this.updateMatrix(),this.matrixWorldAutoUpdate===!0&&(this.parent===null?this.matrixWorld.copy(this.matrix):this.matrixWorld.multiplyMatrices(this.parent.matrixWorld,this.matrix)),t===!0){let s=this.children;for(let r=0,o=s.length;r<o;r++)s[r].updateWorldMatrix(!1,!0)}}toJSON(e){let t=e===void 0||typeof e=="string",n={};t&&(e={geometries:{},materials:{},textures:{},images:{},shapes:{},skeletons:{},animations:{},nodes:{}},n.metadata={version:4.6,type:"Object",generator:"Object3D.toJSON"});let s={};s.uuid=this.uuid,s.type=this.type,this.name!==""&&(s.name=this.name),this.castShadow===!0&&(s.castShadow=!0),this.receiveShadow===!0&&(s.receiveShadow=!0),this.visible===!1&&(s.visible=!1),this.frustumCulled===!1&&(s.frustumCulled=!1),this.renderOrder!==0&&(s.renderOrder=this.renderOrder),Object.keys(this.userData).length>0&&(s.userData=this.userData),s.layers=this.layers.mask,s.matrix=this.matrix.toArray(),s.up=this.up.toArray(),this.matrixAutoUpdate===!1&&(s.matrixAutoUpdate=!1),this.isInstancedMesh&&(s.type="InstancedMesh",s.count=this.count,s.instanceMatrix=this.instanceMatrix.toJSON(),this.instanceColor!==null&&(s.instanceColor=this.instanceColor.toJSON())),this.isBatchedMesh&&(s.type="BatchedMesh",s.perObjectFrustumCulled=this.perObjectFrustumCulled,s.sortObjects=this.sortObjects,s.drawRanges=this._drawRanges,s.reservedRanges=this._reservedRanges,s.visibility=this._visibility,s.active=this._active,s.bounds=this._bounds.map(a=>({boxInitialized:a.boxInitialized,boxMin:a.box.min.toArray(),boxMax:a.box.max.toArray(),sphereInitialized:a.sphereInitialized,sphereRadius:a.sphere.radius,sphereCenter:a.sphere.center.toArray()})),s.maxInstanceCount=this._maxInstanceCount,s.maxVertexCount=this._maxVertexCount,s.maxIndexCount=this._maxIndexCount,s.geometryInitialized=this._geometryInitialized,s.geometryCount=this._geometryCount,s.matricesTexture=this._matricesTexture.toJSON(e),this._colorsTexture!==null&&(s.colorsTexture=this._colorsTexture.toJSON(e)),this.boundingSphere!==null&&(s.boundingSphere={center:s.boundingSphere.center.toArray(),radius:s.boundingSphere.radius}),this.boundingBox!==null&&(s.boundingBox={min:s.boundingBox.min.toArray(),max:s.boundingBox.max.toArray()}));function r(a,l){return a[l.uuid]===void 0&&(a[l.uuid]=l.toJSON(e)),l.uuid}if(this.isScene)this.background&&(this.background.isColor?s.background=this.background.toJSON():this.background.isTexture&&(s.background=this.background.toJSON(e).uuid)),this.environment&&this.environment.isTexture&&this.environment.isRenderTargetTexture!==!0&&(s.environment=this.environment.toJSON(e).uuid);else if(this.isMesh||this.isLine||this.isPoints){s.geometry=r(e.geometries,this.geometry);let a=this.geometry.parameters;if(a!==void 0&&a.shapes!==void 0){let l=a.shapes;if(Array.isArray(l))for(let c=0,h=l.length;c<h;c++){let u=l[c];r(e.shapes,u)}else r(e.shapes,l)}}if(this.isSkinnedMesh&&(s.bindMode=this.bindMode,s.bindMatrix=this.bindMatrix.toArray(),this.skeleton!==void 0&&(r(e.skeletons,this.skeleton),s.skeleton=this.skeleton.uuid)),this.material!==void 0)if(Array.isArray(this.material)){let a=[];for(let l=0,c=this.material.length;l<c;l++)a.push(r(e.materials,this.material[l]));s.material=a}else s.material=r(e.materials,this.material);if(this.children.length>0){s.children=[];for(let a=0;a<this.children.length;a++)s.children.push(this.children[a].toJSON(e).object)}if(this.animations.length>0){s.animations=[];for(let a=0;a<this.animations.length;a++){let l=this.animations[a];s.animations.push(r(e.animations,l))}}if(t){let a=o(e.geometries),l=o(e.materials),c=o(e.textures),h=o(e.images),u=o(e.shapes),d=o(e.skeletons),f=o(e.animations),g=o(e.nodes);a.length>0&&(n.geometries=a),l.length>0&&(n.materials=l),c.length>0&&(n.textures=c),h.length>0&&(n.images=h),u.length>0&&(n.shapes=u),d.length>0&&(n.skeletons=d),f.length>0&&(n.animations=f),g.length>0&&(n.nodes=g)}return n.object=s,n;function o(a){let l=[];for(let c in a){let h=a[c];delete h.metadata,l.push(h)}return l}}clone(e){return new this.constructor().copy(this,e)}copy(e,t=!0){if(this.name=e.name,this.up.copy(e.up),this.position.copy(e.position),this.rotation.order=e.rotation.order,this.quaternion.copy(e.quaternion),this.scale.copy(e.scale),this.matrix.copy(e.matrix),this.matrixWorld.copy(e.matrixWorld),this.matrixAutoUpdate=e.matrixAutoUpdate,this.matrixWorldAutoUpdate=e.matrixWorldAutoUpdate,this.matrixWorldNeedsUpdate=e.matrixWorldNeedsUpdate,this.layers.mask=e.layers.mask,this.visible=e.visible,this.castShadow=e.castShadow,this.receiveShadow=e.receiveShadow,this.frustumCulled=e.frustumCulled,this.renderOrder=e.renderOrder,this.animations=e.animations.slice(),this.userData=JSON.parse(JSON.stringify(e.userData)),t===!0)for(let n=0;n<e.children.length;n++){let s=e.children[n];this.add(s.clone())}return this}};ht.DEFAULT_UP=new C(0,1,0);ht.DEFAULT_MATRIX_AUTO_UPDATE=!0;ht.DEFAULT_MATRIX_WORLD_AUTO_UPDATE=!0;var gn=new C,Un=new C,Go=new C,Nn=new C,Zi=new C,Ki=new C,ah=new C,Wo=new C,Xo=new C,qo=new C,Yo=new Ye,Zo=new Ye,Ko=new Ye,ci=class i{constructor(e=new C,t=new C,n=new C){this.a=e,this.b=t,this.c=n}static getNormal(e,t,n,s){s.subVectors(n,t),gn.subVectors(e,t),s.cross(gn);let r=s.lengthSq();return r>0?s.multiplyScalar(1/Math.sqrt(r)):s.set(0,0,0)}static getBarycoord(e,t,n,s,r){gn.subVectors(s,t),Un.subVectors(n,t),Go.subVectors(e,t);let o=gn.dot(gn),a=gn.dot(Un),l=gn.dot(Go),c=Un.dot(Un),h=Un.dot(Go),u=o*c-a*a;if(u===0)return r.set(0,0,0),null;let d=1/u,f=(c*l-a*h)*d,g=(o*h-a*l)*d;return r.set(1-f-g,g,f)}static containsPoint(e,t,n,s){return this.getBarycoord(e,t,n,s,Nn)===null?!1:Nn.x>=0&&Nn.y>=0&&Nn.x+Nn.y<=1}static getInterpolation(e,t,n,s,r,o,a,l){return this.getBarycoord(e,t,n,s,Nn)===null?(l.x=0,l.y=0,"z"in l&&(l.z=0),"w"in l&&(l.w=0),null):(l.setScalar(0),l.addScaledVector(r,Nn.x),l.addScaledVector(o,Nn.y),l.addScaledVector(a,Nn.z),l)}static getInterpolatedAttribute(e,t,n,s,r,o){return Yo.setScalar(0),Zo.setScalar(0),Ko.setScalar(0),Yo.fromBufferAttribute(e,t),Zo.fromBufferAttribute(e,n),Ko.fromBufferAttribute(e,s),o.setScalar(0),o.addScaledVector(Yo,r.x),o.addScaledVector(Zo,r.y),o.addScaledVector(Ko,r.z),o}static isFrontFacing(e,t,n,s){return gn.subVectors(n,t),Un.subVectors(e,t),gn.cross(Un).dot(s)<0}set(e,t,n){return this.a.copy(e),this.b.copy(t),this.c.copy(n),this}setFromPointsAndIndices(e,t,n,s){return this.a.copy(e[t]),this.b.copy(e[n]),this.c.copy(e[s]),this}setFromAttributeAndIndices(e,t,n,s){return this.a.fromBufferAttribute(e,t),this.b.fromBufferAttribute(e,n),this.c.fromBufferAttribute(e,s),this}clone(){return new this.constructor().copy(this)}copy(e){return this.a.copy(e.a),this.b.copy(e.b),this.c.copy(e.c),this}getArea(){return gn.subVectors(this.c,this.b),Un.subVectors(this.a,this.b),gn.cross(Un).length()*.5}getMidpoint(e){return e.addVectors(this.a,this.b).add(this.c).multiplyScalar(1/3)}getNormal(e){return i.getNormal(this.a,this.b,this.c,e)}getPlane(e){return e.setFromCoplanarPoints(this.a,this.b,this.c)}getBarycoord(e,t){return i.getBarycoord(e,this.a,this.b,this.c,t)}getInterpolation(e,t,n,s,r){return i.getInterpolation(e,this.a,this.b,this.c,t,n,s,r)}containsPoint(e){return i.containsPoint(e,this.a,this.b,this.c)}isFrontFacing(e){return i.isFrontFacing(this.a,this.b,this.c,e)}intersectsBox(e){return e.intersectsTriangle(this)}closestPointToPoint(e,t){let n=this.a,s=this.b,r=this.c,o,a;Zi.subVectors(s,n),Ki.subVectors(r,n),Wo.subVectors(e,n);let l=Zi.dot(Wo),c=Ki.dot(Wo);if(l<=0&&c<=0)return t.copy(n);Xo.subVectors(e,s);let h=Zi.dot(Xo),u=Ki.dot(Xo);if(h>=0&&u<=h)return t.copy(s);let d=l*u-h*c;if(d<=0&&l>=0&&h<=0)return o=l/(l-h),t.copy(n).addScaledVector(Zi,o);qo.subVectors(e,r);let f=Zi.dot(qo),g=Ki.dot(qo);if(g>=0&&f<=g)return t.copy(r);let _=f*c-l*g;if(_<=0&&c>=0&&g<=0)return a=c/(c-g),t.copy(n).addScaledVector(Ki,a);let m=h*g-f*u;if(m<=0&&u-h>=0&&f-g>=0)return ah.subVectors(r,s),a=(u-h)/(u-h+(f-g)),t.copy(s).addScaledVector(ah,a);let p=1/(m+_+d);return o=_*p,a=d*p,t.copy(n).addScaledVector(Zi,o).addScaledVector(Ki,a)}equals(e){return e.a.equals(this.a)&&e.b.equals(this.b)&&e.c.equals(this.c)}},yu={aliceblue:15792383,antiquewhite:16444375,aqua:65535,aquamarine:8388564,azure:15794175,beige:16119260,bisque:16770244,black:0,blanchedalmond:16772045,blue:255,blueviolet:9055202,brown:10824234,burlywood:14596231,cadetblue:6266528,chartreuse:8388352,chocolate:13789470,coral:16744272,cornflowerblue:6591981,cornsilk:16775388,crimson:14423100,cyan:65535,darkblue:139,darkcyan:35723,darkgoldenrod:12092939,darkgray:11119017,darkgreen:25600,darkgrey:11119017,darkkhaki:12433259,darkmagenta:9109643,darkolivegreen:5597999,darkorange:16747520,darkorchid:10040012,darkred:9109504,darksalmon:15308410,darkseagreen:9419919,darkslateblue:4734347,darkslategray:3100495,darkslategrey:3100495,darkturquoise:52945,darkviolet:9699539,deeppink:16716947,deepskyblue:49151,dimgray:6908265,dimgrey:6908265,dodgerblue:2003199,firebrick:11674146,floralwhite:16775920,forestgreen:2263842,fuchsia:16711935,gainsboro:14474460,ghostwhite:16316671,gold:16766720,goldenrod:14329120,gray:8421504,green:32768,greenyellow:11403055,grey:8421504,honeydew:15794160,hotpink:16738740,indianred:13458524,indigo:4915330,ivory:16777200,khaki:15787660,lavender:15132410,lavenderblush:16773365,lawngreen:8190976,lemonchiffon:16775885,lightblue:11393254,lightcoral:15761536,lightcyan:14745599,lightgoldenrodyellow:16448210,lightgray:13882323,lightgreen:9498256,lightgrey:13882323,lightpink:16758465,lightsalmon:16752762,lightseagreen:2142890,lightskyblue:8900346,lightslategray:7833753,lightslategrey:7833753,lightsteelblue:11584734,lightyellow:16777184,lime:65280,limegreen:3329330,linen:16445670,magenta:16711935,maroon:8388608,mediumaquamarine:6737322,mediumblue:205,mediumorchid:12211667,mediumpurple:9662683,mediumseagreen:3978097,mediumslateblue:8087790,mediumspringgreen:64154,mediumturquoise:4772300,mediumvioletred:13047173,midnightblue:1644912,mintcream:16121850,mistyrose:16770273,moccasin:16770229,navajowhite:16768685,navy:128,oldlace:16643558,olive:8421376,olivedrab:7048739,orange:16753920,orangered:16729344,orchid:14315734,palegoldenrod:15657130,palegreen:10025880,paleturquoise:11529966,palevioletred:14381203,papayawhip:16773077,peachpuff:16767673,peru:13468991,pink:16761035,plum:14524637,powderblue:11591910,purple:8388736,rebeccapurple:6697881,red:16711680,rosybrown:12357519,royalblue:4286945,saddlebrown:9127187,salmon:16416882,sandybrown:16032864,seagreen:3050327,seashell:16774638,sienna:10506797,silver:12632256,skyblue:8900331,slateblue:6970061,slategray:7372944,slategrey:7372944,snow:16775930,springgreen:65407,steelblue:4620980,tan:13808780,teal:32896,thistle:14204888,tomato:16737095,turquoise:4251856,violet:15631086,wheat:16113331,white:16777215,whitesmoke:16119285,yellow:16776960,yellowgreen:10145074},oi={h:0,s:0,l:0},_r={h:0,s:0,l:0};function Jo(i,e,t){return t<0&&(t+=1),t>1&&(t-=1),t<1/6?i+(e-i)*6*t:t<1/2?e:t<2/3?i+(e-i)*6*(2/3-t):i}var Ae=class{constructor(e,t,n){return this.isColor=!0,this.r=1,this.g=1,this.b=1,this.set(e,t,n)}set(e,t,n){if(t===void 0&&n===void 0){let s=e;s&&s.isColor?this.copy(s):typeof s=="number"?this.setHex(s):typeof s=="string"&&this.setStyle(s)}else this.setRGB(e,t,n);return this}setScalar(e){return this.r=e,this.g=e,this.b=e,this}setHex(e,t=gt){return e=Math.floor(e),this.r=(e>>16&255)/255,this.g=(e>>8&255)/255,this.b=(e&255)/255,ke.toWorkingColorSpace(this,t),this}setRGB(e,t,n,s=ke.workingColorSpace){return this.r=e,this.g=t,this.b=n,ke.toWorkingColorSpace(this,s),this}setHSL(e,t,n,s=ke.workingColorSpace){if(e=Ol(e,1),t=Ct(t,0,1),n=Ct(n,0,1),t===0)this.r=this.g=this.b=n;else{let r=n<=.5?n*(1+t):n+t-n*t,o=2*n-r;this.r=Jo(o,r,e+1/3),this.g=Jo(o,r,e),this.b=Jo(o,r,e-1/3)}return ke.toWorkingColorSpace(this,s),this}setStyle(e,t=gt){function n(r){r!==void 0&&parseFloat(r)<1&&console.warn("THREE.Color: Alpha component of "+e+" will be ignored.")}let s;if(s=/^(\w+)\(([^\)]*)\)/.exec(e)){let r,o=s[1],a=s[2];switch(o){case"rgb":case"rgba":if(r=/^\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*(\d*\.?\d+)\s*)?$/.exec(a))return n(r[4]),this.setRGB(Math.min(255,parseInt(r[1],10))/255,Math.min(255,parseInt(r[2],10))/255,Math.min(255,parseInt(r[3],10))/255,t);if(r=/^\s*(\d+)\%\s*,\s*(\d+)\%\s*,\s*(\d+)\%\s*(?:,\s*(\d*\.?\d+)\s*)?$/.exec(a))return n(r[4]),this.setRGB(Math.min(100,parseInt(r[1],10))/100,Math.min(100,parseInt(r[2],10))/100,Math.min(100,parseInt(r[3],10))/100,t);break;case"hsl":case"hsla":if(r=/^\s*(\d*\.?\d+)\s*,\s*(\d*\.?\d+)\%\s*,\s*(\d*\.?\d+)\%\s*(?:,\s*(\d*\.?\d+)\s*)?$/.exec(a))return n(r[4]),this.setHSL(parseFloat(r[1])/360,parseFloat(r[2])/100,parseFloat(r[3])/100,t);break;default:console.warn("THREE.Color: Unknown color model "+e)}}else if(s=/^\#([A-Fa-f\d]+)$/.exec(e)){let r=s[1],o=r.length;if(o===3)return this.setRGB(parseInt(r.charAt(0),16)/15,parseInt(r.charAt(1),16)/15,parseInt(r.charAt(2),16)/15,t);if(o===6)return this.setHex(parseInt(r,16),t);console.warn("THREE.Color: Invalid hex color "+e)}else if(e&&e.length>0)return this.setColorName(e,t);return this}setColorName(e,t=gt){let n=yu[e.toLowerCase()];return n!==void 0?this.setHex(n,t):console.warn("THREE.Color: Unknown color "+e),this}clone(){return new this.constructor(this.r,this.g,this.b)}copy(e){return this.r=e.r,this.g=e.g,this.b=e.b,this}copySRGBToLinear(e){return this.r=kn(e.r),this.g=kn(e.g),this.b=kn(e.b),this}copyLinearToSRGB(e){return this.r=os(e.r),this.g=os(e.g),this.b=os(e.b),this}convertSRGBToLinear(){return this.copySRGBToLinear(this),this}convertLinearToSRGB(){return this.copyLinearToSRGB(this),this}getHex(e=gt){return ke.fromWorkingColorSpace(Lt.copy(this),e),Math.round(Ct(Lt.r*255,0,255))*65536+Math.round(Ct(Lt.g*255,0,255))*256+Math.round(Ct(Lt.b*255,0,255))}getHexString(e=gt){return("000000"+this.getHex(e).toString(16)).slice(-6)}getHSL(e,t=ke.workingColorSpace){ke.fromWorkingColorSpace(Lt.copy(this),t);let n=Lt.r,s=Lt.g,r=Lt.b,o=Math.max(n,s,r),a=Math.min(n,s,r),l,c,h=(a+o)/2;if(a===o)l=0,c=0;else{let u=o-a;switch(c=h<=.5?u/(o+a):u/(2-o-a),o){case n:l=(s-r)/u+(s<r?6:0);break;case s:l=(r-n)/u+2;break;case r:l=(n-s)/u+4;break}l/=6}return e.h=l,e.s=c,e.l=h,e}getRGB(e,t=ke.workingColorSpace){return ke.fromWorkingColorSpace(Lt.copy(this),t),e.r=Lt.r,e.g=Lt.g,e.b=Lt.b,e}getStyle(e=gt){ke.fromWorkingColorSpace(Lt.copy(this),e);let t=Lt.r,n=Lt.g,s=Lt.b;return e!==gt?`color(${e} ${t.toFixed(3)} ${n.toFixed(3)} ${s.toFixed(3)})`:`rgb(${Math.round(t*255)},${Math.round(n*255)},${Math.round(s*255)})`}offsetHSL(e,t,n){return this.getHSL(oi),this.setHSL(oi.h+e,oi.s+t,oi.l+n)}add(e){return this.r+=e.r,this.g+=e.g,this.b+=e.b,this}addColors(e,t){return this.r=e.r+t.r,this.g=e.g+t.g,this.b=e.b+t.b,this}addScalar(e){return this.r+=e,this.g+=e,this.b+=e,this}sub(e){return this.r=Math.max(0,this.r-e.r),this.g=Math.max(0,this.g-e.g),this.b=Math.max(0,this.b-e.b),this}multiply(e){return this.r*=e.r,this.g*=e.g,this.b*=e.b,this}multiplyScalar(e){return this.r*=e,this.g*=e,this.b*=e,this}lerp(e,t){return this.r+=(e.r-this.r)*t,this.g+=(e.g-this.g)*t,this.b+=(e.b-this.b)*t,this}lerpColors(e,t,n){return this.r=e.r+(t.r-e.r)*n,this.g=e.g+(t.g-e.g)*n,this.b=e.b+(t.b-e.b)*n,this}lerpHSL(e,t){this.getHSL(oi),e.getHSL(_r);let n=ks(oi.h,_r.h,t),s=ks(oi.s,_r.s,t),r=ks(oi.l,_r.l,t);return this.setHSL(n,s,r),this}setFromVector3(e){return this.r=e.x,this.g=e.y,this.b=e.z,this}applyMatrix3(e){let t=this.r,n=this.g,s=this.b,r=e.elements;return this.r=r[0]*t+r[3]*n+r[6]*s,this.g=r[1]*t+r[4]*n+r[7]*s,this.b=r[2]*t+r[5]*n+r[8]*s,this}equals(e){return e.r===this.r&&e.g===this.g&&e.b===this.b}fromArray(e,t=0){return this.r=e[t],this.g=e[t+1],this.b=e[t+2],this}toArray(e=[],t=0){return e[t]=this.r,e[t+1]=this.g,e[t+2]=this.b,e}fromBufferAttribute(e,t){return this.r=e.getX(t),this.g=e.getY(t),this.b=e.getZ(t),this}toJSON(){return this.getHex()}*[Symbol.iterator](){yield this.r,yield this.g,yield this.b}},Lt=new Ae;Ae.NAMES=yu;var df=0,$t=class extends Gn{static get type(){return"Material"}get type(){return this.constructor.type}set type(e){}constructor(){super(),this.isMaterial=!0,Object.defineProperty(this,"id",{value:df++}),this.uuid=yn(),this.name="",this.blending=is,this.side=En,this.vertexColors=!1,this.opacity=1,this.transparent=!1,this.alphaHash=!1,this.blendSrc=da,this.blendDst=fa,this.blendEquation=Ci,this.blendSrcAlpha=null,this.blendDstAlpha=null,this.blendEquationAlpha=null,this.blendColor=new Ae(0,0,0),this.blendAlpha=0,this.depthFunc=ls,this.depthTest=!0,this.depthWrite=!0,this.stencilWriteMask=255,this.stencilFunc=Wc,this.stencilRef=0,this.stencilFuncMask=255,this.stencilFail=ki,this.stencilZFail=ki,this.stencilZPass=ki,this.stencilWrite=!1,this.clippingPlanes=null,this.clipIntersection=!1,this.clipShadows=!1,this.shadowSide=null,this.colorWrite=!0,this.precision=null,this.polygonOffset=!1,this.polygonOffsetFactor=0,this.polygonOffsetUnits=0,this.dithering=!1,this.alphaToCoverage=!1,this.premultipliedAlpha=!1,this.forceSinglePass=!1,this.visible=!0,this.toneMapped=!0,this.userData={},this.version=0,this._alphaTest=0}get alphaTest(){return this._alphaTest}set alphaTest(e){this._alphaTest>0!=e>0&&this.version++,this._alphaTest=e}onBeforeRender(){}onBeforeCompile(){}customProgramCacheKey(){return this.onBeforeCompile.toString()}setValues(e){if(e!==void 0)for(let t in e){let n=e[t];if(n===void 0){console.warn(`THREE.Material: parameter '${t}' has value of undefined.`);continue}let s=this[t];if(s===void 0){console.warn(`THREE.Material: '${t}' is not a property of THREE.${this.type}.`);continue}s&&s.isColor?s.set(n):s&&s.isVector3&&n&&n.isVector3?s.copy(n):this[t]=n}}toJSON(e){let t=e===void 0||typeof e=="string";t&&(e={textures:{},images:{}});let n={metadata:{version:4.6,type:"Material",generator:"Material.toJSON"}};n.uuid=this.uuid,n.type=this.type,this.name!==""&&(n.name=this.name),this.color&&this.color.isColor&&(n.color=this.color.getHex()),this.roughness!==void 0&&(n.roughness=this.roughness),this.metalness!==void 0&&(n.metalness=this.metalness),this.sheen!==void 0&&(n.sheen=this.sheen),this.sheenColor&&this.sheenColor.isColor&&(n.sheenColor=this.sheenColor.getHex()),this.sheenRoughness!==void 0&&(n.sheenRoughness=this.sheenRoughness),this.emissive&&this.emissive.isColor&&(n.emissive=this.emissive.getHex()),this.emissiveIntensity!==void 0&&this.emissiveIntensity!==1&&(n.emissiveIntensity=this.emissiveIntensity),this.specular&&this.specular.isColor&&(n.specular=this.specular.getHex()),this.specularIntensity!==void 0&&(n.specularIntensity=this.specularIntensity),this.specularColor&&this.specularColor.isColor&&(n.specularColor=this.specularColor.getHex()),this.shininess!==void 0&&(n.shininess=this.shininess),this.clearcoat!==void 0&&(n.clearcoat=this.clearcoat),this.clearcoatRoughness!==void 0&&(n.clearcoatRoughness=this.clearcoatRoughness),this.clearcoatMap&&this.clearcoatMap.isTexture&&(n.clearcoatMap=this.clearcoatMap.toJSON(e).uuid),this.clearcoatRoughnessMap&&this.clearcoatRoughnessMap.isTexture&&(n.clearcoatRoughnessMap=this.clearcoatRoughnessMap.toJSON(e).uuid),this.clearcoatNormalMap&&this.clearcoatNormalMap.isTexture&&(n.clearcoatNormalMap=this.clearcoatNormalMap.toJSON(e).uuid,n.clearcoatNormalScale=this.clearcoatNormalScale.toArray()),this.dispersion!==void 0&&(n.dispersion=this.dispersion),this.iridescence!==void 0&&(n.iridescence=this.iridescence),this.iridescenceIOR!==void 0&&(n.iridescenceIOR=this.iridescenceIOR),this.iridescenceThicknessRange!==void 0&&(n.iridescenceThicknessRange=this.iridescenceThicknessRange),this.iridescenceMap&&this.iridescenceMap.isTexture&&(n.iridescenceMap=this.iridescenceMap.toJSON(e).uuid),this.iridescenceThicknessMap&&this.iridescenceThicknessMap.isTexture&&(n.iridescenceThicknessMap=this.iridescenceThicknessMap.toJSON(e).uuid),this.anisotropy!==void 0&&(n.anisotropy=this.anisotropy),this.anisotropyRotation!==void 0&&(n.anisotropyRotation=this.anisotropyRotation),this.anisotropyMap&&this.anisotropyMap.isTexture&&(n.anisotropyMap=this.anisotropyMap.toJSON(e).uuid),this.map&&this.map.isTexture&&(n.map=this.map.toJSON(e).uuid),this.matcap&&this.matcap.isTexture&&(n.matcap=this.matcap.toJSON(e).uuid),this.alphaMap&&this.alphaMap.isTexture&&(n.alphaMap=this.alphaMap.toJSON(e).uuid),this.lightMap&&this.lightMap.isTexture&&(n.lightMap=this.lightMap.toJSON(e).uuid,n.lightMapIntensity=this.lightMapIntensity),this.aoMap&&this.aoMap.isTexture&&(n.aoMap=this.aoMap.toJSON(e).uuid,n.aoMapIntensity=this.aoMapIntensity),this.bumpMap&&this.bumpMap.isTexture&&(n.bumpMap=this.bumpMap.toJSON(e).uuid,n.bumpScale=this.bumpScale),this.normalMap&&this.normalMap.isTexture&&(n.normalMap=this.normalMap.toJSON(e).uuid,n.normalMapType=this.normalMapType,n.normalScale=this.normalScale.toArray()),this.displacementMap&&this.displacementMap.isTexture&&(n.displacementMap=this.displacementMap.toJSON(e).uuid,n.displacementScale=this.displacementScale,n.displacementBias=this.displacementBias),this.roughnessMap&&this.roughnessMap.isTexture&&(n.roughnessMap=this.roughnessMap.toJSON(e).uuid),this.metalnessMap&&this.metalnessMap.isTexture&&(n.metalnessMap=this.metalnessMap.toJSON(e).uuid),this.emissiveMap&&this.emissiveMap.isTexture&&(n.emissiveMap=this.emissiveMap.toJSON(e).uuid),this.specularMap&&this.specularMap.isTexture&&(n.specularMap=this.specularMap.toJSON(e).uuid),this.specularIntensityMap&&this.specularIntensityMap.isTexture&&(n.specularIntensityMap=this.specularIntensityMap.toJSON(e).uuid),this.specularColorMap&&this.specularColorMap.isTexture&&(n.specularColorMap=this.specularColorMap.toJSON(e).uuid),this.envMap&&this.envMap.isTexture&&(n.envMap=this.envMap.toJSON(e).uuid,this.combine!==void 0&&(n.combine=this.combine)),this.envMapRotation!==void 0&&(n.envMapRotation=this.envMapRotation.toArray()),this.envMapIntensity!==void 0&&(n.envMapIntensity=this.envMapIntensity),this.reflectivity!==void 0&&(n.reflectivity=this.reflectivity),this.refractionRatio!==void 0&&(n.refractionRatio=this.refractionRatio),this.gradientMap&&this.gradientMap.isTexture&&(n.gradientMap=this.gradientMap.toJSON(e).uuid),this.transmission!==void 0&&(n.transmission=this.transmission),this.transmissionMap&&this.transmissionMap.isTexture&&(n.transmissionMap=this.transmissionMap.toJSON(e).uuid),this.thickness!==void 0&&(n.thickness=this.thickness),this.thicknessMap&&this.thicknessMap.isTexture&&(n.thicknessMap=this.thicknessMap.toJSON(e).uuid),this.attenuationDistance!==void 0&&this.attenuationDistance!==1/0&&(n.attenuationDistance=this.attenuationDistance),this.attenuationColor!==void 0&&(n.attenuationColor=this.attenuationColor.getHex()),this.size!==void 0&&(n.size=this.size),this.shadowSide!==null&&(n.shadowSide=this.shadowSide),this.sizeAttenuation!==void 0&&(n.sizeAttenuation=this.sizeAttenuation),this.blending!==is&&(n.blending=this.blending),this.side!==En&&(n.side=this.side),this.vertexColors===!0&&(n.vertexColors=!0),this.opacity<1&&(n.opacity=this.opacity),this.transparent===!0&&(n.transparent=!0),this.blendSrc!==da&&(n.blendSrc=this.blendSrc),this.blendDst!==fa&&(n.blendDst=this.blendDst),this.blendEquation!==Ci&&(n.blendEquation=this.blendEquation),this.blendSrcAlpha!==null&&(n.blendSrcAlpha=this.blendSrcAlpha),this.blendDstAlpha!==null&&(n.blendDstAlpha=this.blendDstAlpha),this.blendEquationAlpha!==null&&(n.blendEquationAlpha=this.blendEquationAlpha),this.blendColor&&this.blendColor.isColor&&(n.blendColor=this.blendColor.getHex()),this.blendAlpha!==0&&(n.blendAlpha=this.blendAlpha),this.depthFunc!==ls&&(n.depthFunc=this.depthFunc),this.depthTest===!1&&(n.depthTest=this.depthTest),this.depthWrite===!1&&(n.depthWrite=this.depthWrite),this.colorWrite===!1&&(n.colorWrite=this.colorWrite),this.stencilWriteMask!==255&&(n.stencilWriteMask=this.stencilWriteMask),this.stencilFunc!==Wc&&(n.stencilFunc=this.stencilFunc),this.stencilRef!==0&&(n.stencilRef=this.stencilRef),this.stencilFuncMask!==255&&(n.stencilFuncMask=this.stencilFuncMask),this.stencilFail!==ki&&(n.stencilFail=this.stencilFail),this.stencilZFail!==ki&&(n.stencilZFail=this.stencilZFail),this.stencilZPass!==ki&&(n.stencilZPass=this.stencilZPass),this.stencilWrite===!0&&(n.stencilWrite=this.stencilWrite),this.rotation!==void 0&&this.rotation!==0&&(n.rotation=this.rotation),this.polygonOffset===!0&&(n.polygonOffset=!0),this.polygonOffsetFactor!==0&&(n.polygonOffsetFactor=this.polygonOffsetFactor),this.polygonOffsetUnits!==0&&(n.polygonOffsetUnits=this.polygonOffsetUnits),this.linewidth!==void 0&&this.linewidth!==1&&(n.linewidth=this.linewidth),this.dashSize!==void 0&&(n.dashSize=this.dashSize),this.gapSize!==void 0&&(n.gapSize=this.gapSize),this.scale!==void 0&&(n.scale=this.scale),this.dithering===!0&&(n.dithering=!0),this.alphaTest>0&&(n.alphaTest=this.alphaTest),this.alphaHash===!0&&(n.alphaHash=!0),this.alphaToCoverage===!0&&(n.alphaToCoverage=!0),this.premultipliedAlpha===!0&&(n.premultipliedAlpha=!0),this.forceSinglePass===!0&&(n.forceSinglePass=!0),this.wireframe===!0&&(n.wireframe=!0),this.wireframeLinewidth>1&&(n.wireframeLinewidth=this.wireframeLinewidth),this.wireframeLinecap!=="round"&&(n.wireframeLinecap=this.wireframeLinecap),this.wireframeLinejoin!=="round"&&(n.wireframeLinejoin=this.wireframeLinejoin),this.flatShading===!0&&(n.flatShading=!0),this.visible===!1&&(n.visible=!1),this.toneMapped===!1&&(n.toneMapped=!1),this.fog===!1&&(n.fog=!1),Object.keys(this.userData).length>0&&(n.userData=this.userData);function s(r){let o=[];for(let a in r){let l=r[a];delete l.metadata,o.push(l)}return o}if(t){let r=s(e.textures),o=s(e.images);r.length>0&&(n.textures=r),o.length>0&&(n.images=o)}return n}clone(){return new this.constructor().copy(this)}copy(e){this.name=e.name,this.blending=e.blending,this.side=e.side,this.vertexColors=e.vertexColors,this.opacity=e.opacity,this.transparent=e.transparent,this.blendSrc=e.blendSrc,this.blendDst=e.blendDst,this.blendEquation=e.blendEquation,this.blendSrcAlpha=e.blendSrcAlpha,this.blendDstAlpha=e.blendDstAlpha,this.blendEquationAlpha=e.blendEquationAlpha,this.blendColor.copy(e.blendColor),this.blendAlpha=e.blendAlpha,this.depthFunc=e.depthFunc,this.depthTest=e.depthTest,this.depthWrite=e.depthWrite,this.stencilWriteMask=e.stencilWriteMask,this.stencilFunc=e.stencilFunc,this.stencilRef=e.stencilRef,this.stencilFuncMask=e.stencilFuncMask,this.stencilFail=e.stencilFail,this.stencilZFail=e.stencilZFail,this.stencilZPass=e.stencilZPass,this.stencilWrite=e.stencilWrite;let t=e.clippingPlanes,n=null;if(t!==null){let s=t.length;n=new Array(s);for(let r=0;r!==s;++r)n[r]=t[r].clone()}return this.clippingPlanes=n,this.clipIntersection=e.clipIntersection,this.clipShadows=e.clipShadows,this.shadowSide=e.shadowSide,this.colorWrite=e.colorWrite,this.precision=e.precision,this.polygonOffset=e.polygonOffset,this.polygonOffsetFactor=e.polygonOffsetFactor,this.polygonOffsetUnits=e.polygonOffsetUnits,this.dithering=e.dithering,this.alphaTest=e.alphaTest,this.alphaHash=e.alphaHash,this.alphaToCoverage=e.alphaToCoverage,this.premultipliedAlpha=e.premultipliedAlpha,this.forceSinglePass=e.forceSinglePass,this.visible=e.visible,this.toneMapped=e.toneMapped,this.userData=JSON.parse(JSON.stringify(e.userData)),this}dispose(){this.dispatchEvent({type:"dispose"})}set needsUpdate(e){e===!0&&this.version++}onBuild(){console.warn("Material: onBuild() has been removed.")}},an=class extends $t{static get type(){return"MeshBasicMaterial"}constructor(e){super(),this.isMeshBasicMaterial=!0,this.color=new Ae(16777215),this.map=null,this.lightMap=null,this.lightMapIntensity=1,this.aoMap=null,this.aoMapIntensity=1,this.specularMap=null,this.alphaMap=null,this.envMap=null,this.envMapRotation=new An,this.combine=su,this.reflectivity=1,this.refractionRatio=.98,this.wireframe=!1,this.wireframeLinewidth=1,this.wireframeLinecap="round",this.wireframeLinejoin="round",this.fog=!0,this.setValues(e)}copy(e){return super.copy(e),this.color.copy(e.color),this.map=e.map,this.lightMap=e.lightMap,this.lightMapIntensity=e.lightMapIntensity,this.aoMap=e.aoMap,this.aoMapIntensity=e.aoMapIntensity,this.specularMap=e.specularMap,this.alphaMap=e.alphaMap,this.envMap=e.envMap,this.envMapRotation.copy(e.envMapRotation),this.combine=e.combine,this.reflectivity=e.reflectivity,this.refractionRatio=e.refractionRatio,this.wireframe=e.wireframe,this.wireframeLinewidth=e.wireframeLinewidth,this.wireframeLinecap=e.wireframeLinecap,this.wireframeLinejoin=e.wireframeLinejoin,this.fog=e.fog,this}};var mt=new C,xr=new we,pt=class{constructor(e,t,n=!1){if(Array.isArray(e))throw new TypeError("THREE.BufferAttribute: array should be a Typed Array.");this.isBufferAttribute=!0,this.name="",this.array=e,this.itemSize=t,this.count=e!==void 0?e.length/t:0,this.normalized=n,this.usage=Ka,this.updateRanges=[],this.gpuType=xn,this.version=0}onUploadCallback(){}set needsUpdate(e){e===!0&&this.version++}setUsage(e){return this.usage=e,this}addUpdateRange(e,t){this.updateRanges.push({start:e,count:t})}clearUpdateRanges(){this.updateRanges.length=0}copy(e){return this.name=e.name,this.array=new e.array.constructor(e.array),this.itemSize=e.itemSize,this.count=e.count,this.normalized=e.normalized,this.usage=e.usage,this.gpuType=e.gpuType,this}copyAt(e,t,n){e*=this.itemSize,n*=t.itemSize;for(let s=0,r=this.itemSize;s<r;s++)this.array[e+s]=t.array[n+s];return this}copyArray(e){return this.array.set(e),this}applyMatrix3(e){if(this.itemSize===2)for(let t=0,n=this.count;t<n;t++)xr.fromBufferAttribute(this,t),xr.applyMatrix3(e),this.setXY(t,xr.x,xr.y);else if(this.itemSize===3)for(let t=0,n=this.count;t<n;t++)mt.fromBufferAttribute(this,t),mt.applyMatrix3(e),this.setXYZ(t,mt.x,mt.y,mt.z);return this}applyMatrix4(e){for(let t=0,n=this.count;t<n;t++)mt.fromBufferAttribute(this,t),mt.applyMatrix4(e),this.setXYZ(t,mt.x,mt.y,mt.z);return this}applyNormalMatrix(e){for(let t=0,n=this.count;t<n;t++)mt.fromBufferAttribute(this,t),mt.applyNormalMatrix(e),this.setXYZ(t,mt.x,mt.y,mt.z);return this}transformDirection(e){for(let t=0,n=this.count;t<n;t++)mt.fromBufferAttribute(this,t),mt.transformDirection(e),this.setXYZ(t,mt.x,mt.y,mt.z);return this}set(e,t=0){return this.array.set(e,t),this}getComponent(e,t){let n=this.array[e*this.itemSize+t];return this.normalized&&(n=_n(n,this.array)),n}setComponent(e,t,n){return this.normalized&&(n=$e(n,this.array)),this.array[e*this.itemSize+t]=n,this}getX(e){let t=this.array[e*this.itemSize];return this.normalized&&(t=_n(t,this.array)),t}setX(e,t){return this.normalized&&(t=$e(t,this.array)),this.array[e*this.itemSize]=t,this}getY(e){let t=this.array[e*this.itemSize+1];return this.normalized&&(t=_n(t,this.array)),t}setY(e,t){return this.normalized&&(t=$e(t,this.array)),this.array[e*this.itemSize+1]=t,this}getZ(e){let t=this.array[e*this.itemSize+2];return this.normalized&&(t=_n(t,this.array)),t}setZ(e,t){return this.normalized&&(t=$e(t,this.array)),this.array[e*this.itemSize+2]=t,this}getW(e){let t=this.array[e*this.itemSize+3];return this.normalized&&(t=_n(t,this.array)),t}setW(e,t){return this.normalized&&(t=$e(t,this.array)),this.array[e*this.itemSize+3]=t,this}setXY(e,t,n){return e*=this.itemSize,this.normalized&&(t=$e(t,this.array),n=$e(n,this.array)),this.array[e+0]=t,this.array[e+1]=n,this}setXYZ(e,t,n,s){return e*=this.itemSize,this.normalized&&(t=$e(t,this.array),n=$e(n,this.array),s=$e(s,this.array)),this.array[e+0]=t,this.array[e+1]=n,this.array[e+2]=s,this}setXYZW(e,t,n,s,r){return e*=this.itemSize,this.normalized&&(t=$e(t,this.array),n=$e(n,this.array),s=$e(s,this.array),r=$e(r,this.array)),this.array[e+0]=t,this.array[e+1]=n,this.array[e+2]=s,this.array[e+3]=r,this}onUpload(e){return this.onUploadCallback=e,this}clone(){return new this.constructor(this.array,this.itemSize).copy(this)}toJSON(){let e={itemSize:this.itemSize,type:this.array.constructor.name,array:Array.from(this.array),normalized:this.normalized};return this.name!==""&&(e.name=this.name),this.usage!==Ka&&(e.usage=this.usage),e}};var Kr=class extends pt{constructor(e,t,n){super(new Uint16Array(e),t,n)}};var Jr=class extends pt{constructor(e,t,n){super(new Uint32Array(e),t,n)}};var dt=class extends pt{constructor(e,t,n){super(new Float32Array(e),t,n)}},ff=0,rn=new Le,jo=new ht,Ji=new C,Zt=new Ot,Ls=new Ot,wt=new C,yt=class i extends Gn{constructor(){super(),this.isBufferGeometry=!0,Object.defineProperty(this,"id",{value:ff++}),this.uuid=yn(),this.name="",this.type="BufferGeometry",this.index=null,this.indirect=null,this.attributes={},this.morphAttributes={},this.morphTargetsRelative=!1,this.groups=[],this.boundingBox=null,this.boundingSphere=null,this.drawRange={start:0,count:1/0},this.userData={}}getIndex(){return this.index}setIndex(e){return Array.isArray(e)?this.index=new(xu(e)?Jr:Kr)(e,1):this.index=e,this}setIndirect(e){return this.indirect=e,this}getIndirect(){return this.indirect}getAttribute(e){return this.attributes[e]}setAttribute(e,t){return this.attributes[e]=t,this}deleteAttribute(e){return delete this.attributes[e],this}hasAttribute(e){return this.attributes[e]!==void 0}addGroup(e,t,n=0){this.groups.push({start:e,count:t,materialIndex:n})}clearGroups(){this.groups=[]}setDrawRange(e,t){this.drawRange.start=e,this.drawRange.count=t}applyMatrix4(e){let t=this.attributes.position;t!==void 0&&(t.applyMatrix4(e),t.needsUpdate=!0);let n=this.attributes.normal;if(n!==void 0){let r=new Ne().getNormalMatrix(e);n.applyNormalMatrix(r),n.needsUpdate=!0}let s=this.attributes.tangent;return s!==void 0&&(s.transformDirection(e),s.needsUpdate=!0),this.boundingBox!==null&&this.computeBoundingBox(),this.boundingSphere!==null&&this.computeBoundingSphere(),this}applyQuaternion(e){return rn.makeRotationFromQuaternion(e),this.applyMatrix4(rn),this}rotateX(e){return rn.makeRotationX(e),this.applyMatrix4(rn),this}rotateY(e){return rn.makeRotationY(e),this.applyMatrix4(rn),this}rotateZ(e){return rn.makeRotationZ(e),this.applyMatrix4(rn),this}translate(e,t,n){return rn.makeTranslation(e,t,n),this.applyMatrix4(rn),this}scale(e,t,n){return rn.makeScale(e,t,n),this.applyMatrix4(rn),this}lookAt(e){return jo.lookAt(e),jo.updateMatrix(),this.applyMatrix4(jo.matrix),this}center(){return this.computeBoundingBox(),this.boundingBox.getCenter(Ji).negate(),this.translate(Ji.x,Ji.y,Ji.z),this}setFromPoints(e){let t=this.getAttribute("position");if(t===void 0){let n=[];for(let s=0,r=e.length;s<r;s++){let o=e[s];n.push(o.x,o.y,o.z||0)}this.setAttribute("position",new dt(n,3))}else{for(let n=0,s=t.count;n<s;n++){let r=e[n];t.setXYZ(n,r.x,r.y,r.z||0)}e.length>t.count&&console.warn("THREE.BufferGeometry: Buffer size too small for points data. Use .dispose() and create a new geometry."),t.needsUpdate=!0}return this}computeBoundingBox(){this.boundingBox===null&&(this.boundingBox=new Ot);let e=this.attributes.position,t=this.morphAttributes.position;if(e&&e.isGLBufferAttribute){console.error("THREE.BufferGeometry.computeBoundingBox(): GLBufferAttribute requires a manual bounding box.",this),this.boundingBox.set(new C(-1/0,-1/0,-1/0),new C(1/0,1/0,1/0));return}if(e!==void 0){if(this.boundingBox.setFromBufferAttribute(e),t)for(let n=0,s=t.length;n<s;n++){let r=t[n];Zt.setFromBufferAttribute(r),this.morphTargetsRelative?(wt.addVectors(this.boundingBox.min,Zt.min),this.boundingBox.expandByPoint(wt),wt.addVectors(this.boundingBox.max,Zt.max),this.boundingBox.expandByPoint(wt)):(this.boundingBox.expandByPoint(Zt.min),this.boundingBox.expandByPoint(Zt.max))}}else this.boundingBox.makeEmpty();(isNaN(this.boundingBox.min.x)||isNaN(this.boundingBox.min.y)||isNaN(this.boundingBox.min.z))&&console.error('THREE.BufferGeometry.computeBoundingBox(): Computed min/max have NaN values. The "position" attribute is likely to have NaN values.',this)}computeBoundingSphere(){this.boundingSphere===null&&(this.boundingSphere=new jt);let e=this.attributes.position,t=this.morphAttributes.position;if(e&&e.isGLBufferAttribute){console.error("THREE.BufferGeometry.computeBoundingSphere(): GLBufferAttribute requires a manual bounding sphere.",this),this.boundingSphere.set(new C,1/0);return}if(e){let n=this.boundingSphere.center;if(Zt.setFromBufferAttribute(e),t)for(let r=0,o=t.length;r<o;r++){let a=t[r];Ls.setFromBufferAttribute(a),this.morphTargetsRelative?(wt.addVectors(Zt.min,Ls.min),Zt.expandByPoint(wt),wt.addVectors(Zt.max,Ls.max),Zt.expandByPoint(wt)):(Zt.expandByPoint(Ls.min),Zt.expandByPoint(Ls.max))}Zt.getCenter(n);let s=0;for(let r=0,o=e.count;r<o;r++)wt.fromBufferAttribute(e,r),s=Math.max(s,n.distanceToSquared(wt));if(t)for(let r=0,o=t.length;r<o;r++){let a=t[r],l=this.morphTargetsRelative;for(let c=0,h=a.count;c<h;c++)wt.fromBufferAttribute(a,c),l&&(Ji.fromBufferAttribute(e,c),wt.add(Ji)),s=Math.max(s,n.distanceToSquared(wt))}this.boundingSphere.radius=Math.sqrt(s),isNaN(this.boundingSphere.radius)&&console.error('THREE.BufferGeometry.computeBoundingSphere(): Computed radius is NaN. The "position" attribute is likely to have NaN values.',this)}}computeTangents(){let e=this.index,t=this.attributes;if(e===null||t.position===void 0||t.normal===void 0||t.uv===void 0){console.error("THREE.BufferGeometry: .computeTangents() failed. Missing required attributes (index, position, normal or uv)");return}let n=t.position,s=t.normal,r=t.uv;this.hasAttribute("tangent")===!1&&this.setAttribute("tangent",new pt(new Float32Array(4*n.count),4));let o=this.getAttribute("tangent"),a=[],l=[];for(let R=0;R<n.count;R++)a[R]=new C,l[R]=new C;let c=new C,h=new C,u=new C,d=new we,f=new we,g=new we,_=new C,m=new C;function p(R,M,v){c.fromBufferAttribute(n,R),h.fromBufferAttribute(n,M),u.fromBufferAttribute(n,v),d.fromBufferAttribute(r,R),f.fromBufferAttribute(r,M),g.fromBufferAttribute(r,v),h.sub(c),u.sub(c),f.sub(d),g.sub(d);let I=1/(f.x*g.y-g.x*f.y);isFinite(I)&&(_.copy(h).multiplyScalar(g.y).addScaledVector(u,-f.y).multiplyScalar(I),m.copy(u).multiplyScalar(f.x).addScaledVector(h,-g.x).multiplyScalar(I),a[R].add(_),a[M].add(_),a[v].add(_),l[R].add(m),l[M].add(m),l[v].add(m))}let w=this.groups;w.length===0&&(w=[{start:0,count:e.count}]);for(let R=0,M=w.length;R<M;++R){let v=w[R],I=v.start,G=v.count;for(let O=I,X=I+G;O<X;O+=3)p(e.getX(O+0),e.getX(O+1),e.getX(O+2))}let b=new C,x=new C,P=new C,T=new C;function A(R){P.fromBufferAttribute(s,R),T.copy(P);let M=a[R];b.copy(M),b.sub(P.multiplyScalar(P.dot(M))).normalize(),x.crossVectors(T,M);let I=x.dot(l[R])<0?-1:1;o.setXYZW(R,b.x,b.y,b.z,I)}for(let R=0,M=w.length;R<M;++R){let v=w[R],I=v.start,G=v.count;for(let O=I,X=I+G;O<X;O+=3)A(e.getX(O+0)),A(e.getX(O+1)),A(e.getX(O+2))}}computeVertexNormals(){let e=this.index,t=this.getAttribute("position");if(t!==void 0){let n=this.getAttribute("normal");if(n===void 0)n=new pt(new Float32Array(t.count*3),3),this.setAttribute("normal",n);else for(let d=0,f=n.count;d<f;d++)n.setXYZ(d,0,0,0);let s=new C,r=new C,o=new C,a=new C,l=new C,c=new C,h=new C,u=new C;if(e)for(let d=0,f=e.count;d<f;d+=3){let g=e.getX(d+0),_=e.getX(d+1),m=e.getX(d+2);s.fromBufferAttribute(t,g),r.fromBufferAttribute(t,_),o.fromBufferAttribute(t,m),h.subVectors(o,r),u.subVectors(s,r),h.cross(u),a.fromBufferAttribute(n,g),l.fromBufferAttribute(n,_),c.fromBufferAttribute(n,m),a.add(h),l.add(h),c.add(h),n.setXYZ(g,a.x,a.y,a.z),n.setXYZ(_,l.x,l.y,l.z),n.setXYZ(m,c.x,c.y,c.z)}else for(let d=0,f=t.count;d<f;d+=3)s.fromBufferAttribute(t,d+0),r.fromBufferAttribute(t,d+1),o.fromBufferAttribute(t,d+2),h.subVectors(o,r),u.subVectors(s,r),h.cross(u),n.setXYZ(d+0,h.x,h.y,h.z),n.setXYZ(d+1,h.x,h.y,h.z),n.setXYZ(d+2,h.x,h.y,h.z);this.normalizeNormals(),n.needsUpdate=!0}}normalizeNormals(){let e=this.attributes.normal;for(let t=0,n=e.count;t<n;t++)wt.fromBufferAttribute(e,t),wt.normalize(),e.setXYZ(t,wt.x,wt.y,wt.z)}toNonIndexed(){function e(a,l){let c=a.array,h=a.itemSize,u=a.normalized,d=new c.constructor(l.length*h),f=0,g=0;for(let _=0,m=l.length;_<m;_++){a.isInterleavedBufferAttribute?f=l[_]*a.data.stride+a.offset:f=l[_]*h;for(let p=0;p<h;p++)d[g++]=c[f++]}return new pt(d,h,u)}if(this.index===null)return console.warn("THREE.BufferGeometry.toNonIndexed(): BufferGeometry is already non-indexed."),this;let t=new i,n=this.index.array,s=this.attributes;for(let a in s){let l=s[a],c=e(l,n);t.setAttribute(a,c)}let r=this.morphAttributes;for(let a in r){let l=[],c=r[a];for(let h=0,u=c.length;h<u;h++){let d=c[h],f=e(d,n);l.push(f)}t.morphAttributes[a]=l}t.morphTargetsRelative=this.morphTargetsRelative;let o=this.groups;for(let a=0,l=o.length;a<l;a++){let c=o[a];t.addGroup(c.start,c.count,c.materialIndex)}return t}toJSON(){let e={metadata:{version:4.6,type:"BufferGeometry",generator:"BufferGeometry.toJSON"}};if(e.uuid=this.uuid,e.type=this.type,this.name!==""&&(e.name=this.name),Object.keys(this.userData).length>0&&(e.userData=this.userData),this.parameters!==void 0){let l=this.parameters;for(let c in l)l[c]!==void 0&&(e[c]=l[c]);return e}e.data={attributes:{}};let t=this.index;t!==null&&(e.data.index={type:t.array.constructor.name,array:Array.prototype.slice.call(t.array)});let n=this.attributes;for(let l in n){let c=n[l];e.data.attributes[l]=c.toJSON(e.data)}let s={},r=!1;for(let l in this.morphAttributes){let c=this.morphAttributes[l],h=[];for(let u=0,d=c.length;u<d;u++){let f=c[u];h.push(f.toJSON(e.data))}h.length>0&&(s[l]=h,r=!0)}r&&(e.data.morphAttributes=s,e.data.morphTargetsRelative=this.morphTargetsRelative);let o=this.groups;o.length>0&&(e.data.groups=JSON.parse(JSON.stringify(o)));let a=this.boundingSphere;return a!==null&&(e.data.boundingSphere={center:a.center.toArray(),radius:a.radius}),e}clone(){return new this.constructor().copy(this)}copy(e){this.index=null,this.attributes={},this.morphAttributes={},this.groups=[],this.boundingBox=null,this.boundingSphere=null;let t={};this.name=e.name;let n=e.index;n!==null&&this.setIndex(n.clone(t));let s=e.attributes;for(let c in s){let h=s[c];this.setAttribute(c,h.clone(t))}let r=e.morphAttributes;for(let c in r){let h=[],u=r[c];for(let d=0,f=u.length;d<f;d++)h.push(u[d].clone(t));this.morphAttributes[c]=h}this.morphTargetsRelative=e.morphTargetsRelative;let o=e.groups;for(let c=0,h=o.length;c<h;c++){let u=o[c];this.addGroup(u.start,u.count,u.materialIndex)}let a=e.boundingBox;a!==null&&(this.boundingBox=a.clone());let l=e.boundingSphere;return l!==null&&(this.boundingSphere=l.clone()),this.drawRange.start=e.drawRange.start,this.drawRange.count=e.drawRange.count,this.userData=e.userData,this}dispose(){this.dispatchEvent({type:"dispose"})}},lh=new Le,wi=new Xn,yr=new jt,ch=new C,vr=new C,Mr=new C,Sr=new C,$o=new C,br=new C,hh=new C,wr=new C,tt=class extends ht{constructor(e=new yt,t=new an){super(),this.isMesh=!0,this.type="Mesh",this.geometry=e,this.material=t,this.updateMorphTargets()}copy(e,t){return super.copy(e,t),e.morphTargetInfluences!==void 0&&(this.morphTargetInfluences=e.morphTargetInfluences.slice()),e.morphTargetDictionary!==void 0&&(this.morphTargetDictionary=Object.assign({},e.morphTargetDictionary)),this.material=Array.isArray(e.material)?e.material.slice():e.material,this.geometry=e.geometry,this}updateMorphTargets(){let t=this.geometry.morphAttributes,n=Object.keys(t);if(n.length>0){let s=t[n[0]];if(s!==void 0){this.morphTargetInfluences=[],this.morphTargetDictionary={};for(let r=0,o=s.length;r<o;r++){let a=s[r].name||String(r);this.morphTargetInfluences.push(0),this.morphTargetDictionary[a]=r}}}}getVertexPosition(e,t){let n=this.geometry,s=n.attributes.position,r=n.morphAttributes.position,o=n.morphTargetsRelative;t.fromBufferAttribute(s,e);let a=this.morphTargetInfluences;if(r&&a){br.set(0,0,0);for(let l=0,c=r.length;l<c;l++){let h=a[l],u=r[l];h!==0&&($o.fromBufferAttribute(u,e),o?br.addScaledVector($o,h):br.addScaledVector($o.sub(t),h))}t.add(br)}return t}raycast(e,t){let n=this.geometry,s=this.material,r=this.matrixWorld;s!==void 0&&(n.boundingSphere===null&&n.computeBoundingSphere(),yr.copy(n.boundingSphere),yr.applyMatrix4(r),wi.copy(e.ray).recast(e.near),!(yr.containsPoint(wi.origin)===!1&&(wi.intersectSphere(yr,ch)===null||wi.origin.distanceToSquared(ch)>(e.far-e.near)**2))&&(lh.copy(r).invert(),wi.copy(e.ray).applyMatrix4(lh),!(n.boundingBox!==null&&wi.intersectsBox(n.boundingBox)===!1)&&this._computeIntersections(e,t,wi)))}_computeIntersections(e,t,n){let s,r=this.geometry,o=this.material,a=r.index,l=r.attributes.position,c=r.attributes.uv,h=r.attributes.uv1,u=r.attributes.normal,d=r.groups,f=r.drawRange;if(a!==null)if(Array.isArray(o))for(let g=0,_=d.length;g<_;g++){let m=d[g],p=o[m.materialIndex],w=Math.max(m.start,f.start),b=Math.min(a.count,Math.min(m.start+m.count,f.start+f.count));for(let x=w,P=b;x<P;x+=3){let T=a.getX(x),A=a.getX(x+1),R=a.getX(x+2);s=Er(this,p,e,n,c,h,u,T,A,R),s&&(s.faceIndex=Math.floor(x/3),s.face.materialIndex=m.materialIndex,t.push(s))}}else{let g=Math.max(0,f.start),_=Math.min(a.count,f.start+f.count);for(let m=g,p=_;m<p;m+=3){let w=a.getX(m),b=a.getX(m+1),x=a.getX(m+2);s=Er(this,o,e,n,c,h,u,w,b,x),s&&(s.faceIndex=Math.floor(m/3),t.push(s))}}else if(l!==void 0)if(Array.isArray(o))for(let g=0,_=d.length;g<_;g++){let m=d[g],p=o[m.materialIndex],w=Math.max(m.start,f.start),b=Math.min(l.count,Math.min(m.start+m.count,f.start+f.count));for(let x=w,P=b;x<P;x+=3){let T=x,A=x+1,R=x+2;s=Er(this,p,e,n,c,h,u,T,A,R),s&&(s.faceIndex=Math.floor(x/3),s.face.materialIndex=m.materialIndex,t.push(s))}}else{let g=Math.max(0,f.start),_=Math.min(l.count,f.start+f.count);for(let m=g,p=_;m<p;m+=3){let w=m,b=m+1,x=m+2;s=Er(this,o,e,n,c,h,u,w,b,x),s&&(s.faceIndex=Math.floor(m/3),t.push(s))}}}};function pf(i,e,t,n,s,r,o,a){let l;if(e.side===Ut?l=n.intersectTriangle(o,r,s,!0,a):l=n.intersectTriangle(s,r,o,e.side===En,a),l===null)return null;wr.copy(a),wr.applyMatrix4(i.matrixWorld);let c=t.ray.origin.distanceTo(wr);return c<t.near||c>t.far?null:{distance:c,point:wr.clone(),object:i}}function Er(i,e,t,n,s,r,o,a,l,c){i.getVertexPosition(a,vr),i.getVertexPosition(l,Mr),i.getVertexPosition(c,Sr);let h=pf(i,e,t,n,vr,Mr,Sr,hh);if(h){let u=new C;ci.getBarycoord(hh,vr,Mr,Sr,u),s&&(h.uv=ci.getInterpolatedAttribute(s,a,l,c,u,new we)),r&&(h.uv1=ci.getInterpolatedAttribute(r,a,l,c,u,new we)),o&&(h.normal=ci.getInterpolatedAttribute(o,a,l,c,u,new C),h.normal.dot(n.direction)>0&&h.normal.multiplyScalar(-1));let d={a,b:l,c,normal:new C,materialIndex:0};ci.getNormal(vr,Mr,Sr,d.normal),h.face=d,h.barycoord=u}return h}var qn=class i extends yt{constructor(e=1,t=1,n=1,s=1,r=1,o=1){super(),this.type="BoxGeometry",this.parameters={width:e,height:t,depth:n,widthSegments:s,heightSegments:r,depthSegments:o};let a=this;s=Math.floor(s),r=Math.floor(r),o=Math.floor(o);let l=[],c=[],h=[],u=[],d=0,f=0;g("z","y","x",-1,-1,n,t,e,o,r,0),g("z","y","x",1,-1,n,t,-e,o,r,1),g("x","z","y",1,1,e,n,t,s,o,2),g("x","z","y",1,-1,e,n,-t,s,o,3),g("x","y","z",1,-1,e,t,n,s,r,4),g("x","y","z",-1,-1,e,t,-n,s,r,5),this.setIndex(l),this.setAttribute("position",new dt(c,3)),this.setAttribute("normal",new dt(h,3)),this.setAttribute("uv",new dt(u,2));function g(_,m,p,w,b,x,P,T,A,R,M){let v=x/A,I=P/R,G=x/2,O=P/2,X=T/2,Y=A+1,V=R+1,Q=0,B=0,H=new C;for(let j=0;j<V;j++){let ie=j*I-O;for(let Te=0;Te<Y;Te++){let Re=Te*v-G;H[_]=Re*w,H[m]=ie*b,H[p]=X,c.push(H.x,H.y,H.z),H[_]=0,H[m]=0,H[p]=T>0?1:-1,h.push(H.x,H.y,H.z),u.push(Te/A),u.push(1-j/R),Q+=1}}for(let j=0;j<R;j++)for(let ie=0;ie<A;ie++){let Te=d+ie+Y*j,Re=d+ie+Y*(j+1),q=d+(ie+1)+Y*(j+1),ee=d+(ie+1)+Y*j;l.push(Te,Re,ee),l.push(Re,q,ee),B+=6}a.addGroup(f,B,M),f+=B,d+=Q}}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}static fromJSON(e){return new i(e.width,e.height,e.depth,e.widthSegments,e.heightSegments,e.depthSegments)}};function gs(i){let e={};for(let t in i){e[t]={};for(let n in i[t]){let s=i[t][n];s&&(s.isColor||s.isMatrix3||s.isMatrix4||s.isVector2||s.isVector3||s.isVector4||s.isTexture||s.isQuaternion)?s.isRenderTargetTexture?(console.warn("UniformsUtils: Textures of render targets cannot be cloned via cloneUniforms() or mergeUniforms()."),e[t][n]=null):e[t][n]=s.clone():Array.isArray(s)?e[t][n]=s.slice():e[t][n]=s}}return e}function zt(i){let e={};for(let t=0;t<i.length;t++){let n=gs(i[t]);for(let s in n)e[s]=n[s]}return e}function mf(i){let e=[];for(let t=0;t<i.length;t++)e.push(i[t].clone());return e}function vu(i){let e=i.getRenderTarget();return e===null?i.outputColorSpace:e.isXRRenderTarget===!0?e.texture.colorSpace:ke.workingColorSpace}var Fl={clone:gs,merge:zt},gf=`void main() {
	gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
}`,_f=`void main() {
	gl_FragColor = vec4( 1.0, 0.0, 0.0, 1.0 );
}`,ln=class extends $t{static get type(){return"ShaderMaterial"}constructor(e){super(),this.isShaderMaterial=!0,this.defines={},this.uniforms={},this.uniformsGroups=[],this.vertexShader=gf,this.fragmentShader=_f,this.linewidth=1,this.wireframe=!1,this.wireframeLinewidth=1,this.fog=!1,this.lights=!1,this.clipping=!1,this.forceSinglePass=!0,this.extensions={clipCullDistance:!1,multiDraw:!1},this.defaultAttributeValues={color:[1,1,1],uv:[0,0],uv1:[0,0]},this.index0AttributeName=void 0,this.uniformsNeedUpdate=!1,this.glslVersion=null,e!==void 0&&this.setValues(e)}copy(e){return super.copy(e),this.fragmentShader=e.fragmentShader,this.vertexShader=e.vertexShader,this.uniforms=gs(e.uniforms),this.uniformsGroups=mf(e.uniformsGroups),this.defines=Object.assign({},e.defines),this.wireframe=e.wireframe,this.wireframeLinewidth=e.wireframeLinewidth,this.fog=e.fog,this.lights=e.lights,this.clipping=e.clipping,this.extensions=Object.assign({},e.extensions),this.glslVersion=e.glslVersion,this}toJSON(e){let t=super.toJSON(e);t.glslVersion=this.glslVersion,t.uniforms={};for(let s in this.uniforms){let o=this.uniforms[s].value;o&&o.isTexture?t.uniforms[s]={type:"t",value:o.toJSON(e).uuid}:o&&o.isColor?t.uniforms[s]={type:"c",value:o.getHex()}:o&&o.isVector2?t.uniforms[s]={type:"v2",value:o.toArray()}:o&&o.isVector3?t.uniforms[s]={type:"v3",value:o.toArray()}:o&&o.isVector4?t.uniforms[s]={type:"v4",value:o.toArray()}:o&&o.isMatrix3?t.uniforms[s]={type:"m3",value:o.toArray()}:o&&o.isMatrix4?t.uniforms[s]={type:"m4",value:o.toArray()}:t.uniforms[s]={value:o}}Object.keys(this.defines).length>0&&(t.defines=this.defines),t.vertexShader=this.vertexShader,t.fragmentShader=this.fragmentShader,t.lights=this.lights,t.clipping=this.clipping;let n={};for(let s in this.extensions)this.extensions[s]===!0&&(n[s]=!0);return Object.keys(n).length>0&&(t.extensions=n),t}},jr=class extends ht{constructor(){super(),this.isCamera=!0,this.type="Camera",this.matrixWorldInverse=new Le,this.projectionMatrix=new Le,this.projectionMatrixInverse=new Le,this.coordinateSystem=zn}copy(e,t){return super.copy(e,t),this.matrixWorldInverse.copy(e.matrixWorldInverse),this.projectionMatrix.copy(e.projectionMatrix),this.projectionMatrixInverse.copy(e.projectionMatrixInverse),this.coordinateSystem=e.coordinateSystem,this}getWorldDirection(e){return super.getWorldDirection(e).negate()}updateMatrixWorld(e){super.updateMatrixWorld(e),this.matrixWorldInverse.copy(this.matrixWorld).invert()}updateWorldMatrix(e,t){super.updateWorldMatrix(e,t),this.matrixWorldInverse.copy(this.matrixWorld).invert()}clone(){return new this.constructor().copy(this)}},ai=new C,uh=new we,dh=new we,xt=class extends jr{constructor(e=50,t=1,n=.1,s=2e3){super(),this.isPerspectiveCamera=!0,this.type="PerspectiveCamera",this.fov=e,this.zoom=1,this.near=n,this.far=s,this.focus=10,this.aspect=t,this.view=null,this.filmGauge=35,this.filmOffset=0,this.updateProjectionMatrix()}copy(e,t){return super.copy(e,t),this.fov=e.fov,this.zoom=e.zoom,this.near=e.near,this.far=e.far,this.focus=e.focus,this.aspect=e.aspect,this.view=e.view===null?null:Object.assign({},e.view),this.filmGauge=e.filmGauge,this.filmOffset=e.filmOffset,this}setFocalLength(e){let t=.5*this.getFilmHeight()/e;this.fov=ms*2*Math.atan(t),this.updateProjectionMatrix()}getFocalLength(){let e=Math.tan(rs*.5*this.fov);return .5*this.getFilmHeight()/e}getEffectiveFOV(){return ms*2*Math.atan(Math.tan(rs*.5*this.fov)/this.zoom)}getFilmWidth(){return this.filmGauge*Math.min(this.aspect,1)}getFilmHeight(){return this.filmGauge/Math.max(this.aspect,1)}getViewBounds(e,t,n){ai.set(-1,-1,.5).applyMatrix4(this.projectionMatrixInverse),t.set(ai.x,ai.y).multiplyScalar(-e/ai.z),ai.set(1,1,.5).applyMatrix4(this.projectionMatrixInverse),n.set(ai.x,ai.y).multiplyScalar(-e/ai.z)}getViewSize(e,t){return this.getViewBounds(e,uh,dh),t.subVectors(dh,uh)}setViewOffset(e,t,n,s,r,o){this.aspect=e/t,this.view===null&&(this.view={enabled:!0,fullWidth:1,fullHeight:1,offsetX:0,offsetY:0,width:1,height:1}),this.view.enabled=!0,this.view.fullWidth=e,this.view.fullHeight=t,this.view.offsetX=n,this.view.offsetY=s,this.view.width=r,this.view.height=o,this.updateProjectionMatrix()}clearViewOffset(){this.view!==null&&(this.view.enabled=!1),this.updateProjectionMatrix()}updateProjectionMatrix(){let e=this.near,t=e*Math.tan(rs*.5*this.fov)/this.zoom,n=2*t,s=this.aspect*n,r=-.5*s,o=this.view;if(this.view!==null&&this.view.enabled){let l=o.fullWidth,c=o.fullHeight;r+=o.offsetX*s/l,t-=o.offsetY*n/c,s*=o.width/l,n*=o.height/c}let a=this.filmOffset;a!==0&&(r+=e*a/this.getFilmWidth()),this.projectionMatrix.makePerspective(r,r+s,t,t-n,e,this.far,this.coordinateSystem),this.projectionMatrixInverse.copy(this.projectionMatrix).invert()}toJSON(e){let t=super.toJSON(e);return t.object.fov=this.fov,t.object.zoom=this.zoom,t.object.near=this.near,t.object.far=this.far,t.object.focus=this.focus,t.object.aspect=this.aspect,this.view!==null&&(t.object.view=Object.assign({},this.view)),t.object.filmGauge=this.filmGauge,t.object.filmOffset=this.filmOffset,t}},ji=-90,$i=1,Qa=class extends ht{constructor(e,t,n){super(),this.type="CubeCamera",this.renderTarget=n,this.coordinateSystem=null,this.activeMipmapLevel=0;let s=new xt(ji,$i,e,t);s.layers=this.layers,this.add(s);let r=new xt(ji,$i,e,t);r.layers=this.layers,this.add(r);let o=new xt(ji,$i,e,t);o.layers=this.layers,this.add(o);let a=new xt(ji,$i,e,t);a.layers=this.layers,this.add(a);let l=new xt(ji,$i,e,t);l.layers=this.layers,this.add(l);let c=new xt(ji,$i,e,t);c.layers=this.layers,this.add(c)}updateCoordinateSystem(){let e=this.coordinateSystem,t=this.children.concat(),[n,s,r,o,a,l]=t;for(let c of t)this.remove(c);if(e===zn)n.up.set(0,1,0),n.lookAt(1,0,0),s.up.set(0,1,0),s.lookAt(-1,0,0),r.up.set(0,0,-1),r.lookAt(0,1,0),o.up.set(0,0,1),o.lookAt(0,-1,0),a.up.set(0,1,0),a.lookAt(0,0,1),l.up.set(0,1,0),l.lookAt(0,0,-1);else if(e===qr)n.up.set(0,-1,0),n.lookAt(-1,0,0),s.up.set(0,-1,0),s.lookAt(1,0,0),r.up.set(0,0,1),r.lookAt(0,1,0),o.up.set(0,0,-1),o.lookAt(0,-1,0),a.up.set(0,-1,0),a.lookAt(0,0,1),l.up.set(0,-1,0),l.lookAt(0,0,-1);else throw new Error("THREE.CubeCamera.updateCoordinateSystem(): Invalid coordinate system: "+e);for(let c of t)this.add(c),c.updateMatrixWorld()}update(e,t){this.parent===null&&this.updateMatrixWorld();let{renderTarget:n,activeMipmapLevel:s}=this;this.coordinateSystem!==e.coordinateSystem&&(this.coordinateSystem=e.coordinateSystem,this.updateCoordinateSystem());let[r,o,a,l,c,h]=this.children,u=e.getRenderTarget(),d=e.getActiveCubeFace(),f=e.getActiveMipmapLevel(),g=e.xr.enabled;e.xr.enabled=!1;let _=n.texture.generateMipmaps;n.texture.generateMipmaps=!1,e.setRenderTarget(n,0,s),e.render(t,r),e.setRenderTarget(n,1,s),e.render(t,o),e.setRenderTarget(n,2,s),e.render(t,a),e.setRenderTarget(n,3,s),e.render(t,l),e.setRenderTarget(n,4,s),e.render(t,c),n.texture.generateMipmaps=_,e.setRenderTarget(n,5,s),e.render(t,h),e.setRenderTarget(u,d,f),e.xr.enabled=g,n.texture.needsPMREMUpdate=!0}},$r=class extends Et{constructor(e,t,n,s,r,o,a,l,c,h){e=e!==void 0?e:[],t=t!==void 0?t:cs,super(e,t,n,s,r,o,a,l,c,h),this.isCubeTexture=!0,this.flipY=!1}get images(){return this.image}set images(e){this.image=e}},el=class extends Wn{constructor(e=1,t={}){super(e,e,t),this.isWebGLCubeRenderTarget=!0;let n={width:e,height:e,depth:1},s=[n,n,n,n,n,n];this.texture=new $r(s,t.mapping,t.wrapS,t.wrapT,t.magFilter,t.minFilter,t.format,t.type,t.anisotropy,t.colorSpace),this.texture.isRenderTargetTexture=!0,this.texture.generateMipmaps=t.generateMipmaps!==void 0?t.generateMipmaps:!1,this.texture.minFilter=t.minFilter!==void 0?t.minFilter:Vt}fromEquirectangularTexture(e,t){this.texture.type=t.type,this.texture.colorSpace=t.colorSpace,this.texture.generateMipmaps=t.generateMipmaps,this.texture.minFilter=t.minFilter,this.texture.magFilter=t.magFilter;let n={uniforms:{tEquirect:{value:null}},vertexShader:`

				varying vec3 vWorldDirection;

				vec3 transformDirection( in vec3 dir, in mat4 matrix ) {

					return normalize( ( matrix * vec4( dir, 0.0 ) ).xyz );

				}

				void main() {

					vWorldDirection = transformDirection( position, modelMatrix );

					#include <begin_vertex>
					#include <project_vertex>

				}
			`,fragmentShader:`

				uniform sampler2D tEquirect;

				varying vec3 vWorldDirection;

				#include <common>

				void main() {

					vec3 direction = normalize( vWorldDirection );

					vec2 sampleUV = equirectUv( direction );

					gl_FragColor = texture2D( tEquirect, sampleUV );

				}
			`},s=new qn(5,5,5),r=new ln({name:"CubemapFromEquirect",uniforms:gs(n.uniforms),vertexShader:n.vertexShader,fragmentShader:n.fragmentShader,side:Ut,blending:ui});r.uniforms.tEquirect.value=t;let o=new tt(s,r),a=t.minFilter;return t.minFilter===wn&&(t.minFilter=Vt),new Qa(1,10,this).update(e,o),t.minFilter=a,o.geometry.dispose(),o.material.dispose(),this}clear(e,t,n,s){let r=e.getRenderTarget();for(let o=0;o<6;o++)e.setRenderTarget(this,o),e.clear(t,n,s);e.setRenderTarget(r)}},Qo=new C,xf=new C,yf=new Ne,Kt=class{constructor(e=new C(1,0,0),t=0){this.isPlane=!0,this.normal=e,this.constant=t}set(e,t){return this.normal.copy(e),this.constant=t,this}setComponents(e,t,n,s){return this.normal.set(e,t,n),this.constant=s,this}setFromNormalAndCoplanarPoint(e,t){return this.normal.copy(e),this.constant=-t.dot(this.normal),this}setFromCoplanarPoints(e,t,n){let s=Qo.subVectors(n,t).cross(xf.subVectors(e,t)).normalize();return this.setFromNormalAndCoplanarPoint(s,e),this}copy(e){return this.normal.copy(e.normal),this.constant=e.constant,this}normalize(){let e=1/this.normal.length();return this.normal.multiplyScalar(e),this.constant*=e,this}negate(){return this.constant*=-1,this.normal.negate(),this}distanceToPoint(e){return this.normal.dot(e)+this.constant}distanceToSphere(e){return this.distanceToPoint(e.center)-e.radius}projectPoint(e,t){return t.copy(e).addScaledVector(this.normal,-this.distanceToPoint(e))}intersectLine(e,t){let n=e.delta(Qo),s=this.normal.dot(n);if(s===0)return this.distanceToPoint(e.start)===0?t.copy(e.start):null;let r=-(e.start.dot(this.normal)+this.constant)/s;return r<0||r>1?null:t.copy(e.start).addScaledVector(n,r)}intersectsLine(e){let t=this.distanceToPoint(e.start),n=this.distanceToPoint(e.end);return t<0&&n>0||n<0&&t>0}intersectsBox(e){return e.intersectsPlane(this)}intersectsSphere(e){return e.intersectsPlane(this)}coplanarPoint(e){return e.copy(this.normal).multiplyScalar(-this.constant)}applyMatrix4(e,t){let n=t||yf.getNormalMatrix(e),s=this.coplanarPoint(Qo).applyMatrix4(e),r=this.normal.applyMatrix3(n).normalize();return this.constant=-s.dot(r),this}translate(e){return this.constant-=e.dot(this.normal),this}equals(e){return e.normal.equals(this.normal)&&e.constant===this.constant}clone(){return new this.constructor().copy(this)}},Ei=new jt,Ar=new C,qs=class{constructor(e=new Kt,t=new Kt,n=new Kt,s=new Kt,r=new Kt,o=new Kt){this.planes=[e,t,n,s,r,o]}set(e,t,n,s,r,o){let a=this.planes;return a[0].copy(e),a[1].copy(t),a[2].copy(n),a[3].copy(s),a[4].copy(r),a[5].copy(o),this}copy(e){let t=this.planes;for(let n=0;n<6;n++)t[n].copy(e.planes[n]);return this}setFromProjectionMatrix(e,t=zn){let n=this.planes,s=e.elements,r=s[0],o=s[1],a=s[2],l=s[3],c=s[4],h=s[5],u=s[6],d=s[7],f=s[8],g=s[9],_=s[10],m=s[11],p=s[12],w=s[13],b=s[14],x=s[15];if(n[0].setComponents(l-r,d-c,m-f,x-p).normalize(),n[1].setComponents(l+r,d+c,m+f,x+p).normalize(),n[2].setComponents(l+o,d+h,m+g,x+w).normalize(),n[3].setComponents(l-o,d-h,m-g,x-w).normalize(),n[4].setComponents(l-a,d-u,m-_,x-b).normalize(),t===zn)n[5].setComponents(l+a,d+u,m+_,x+b).normalize();else if(t===qr)n[5].setComponents(a,u,_,b).normalize();else throw new Error("THREE.Frustum.setFromProjectionMatrix(): Invalid coordinate system: "+t);return this}intersectsObject(e){if(e.boundingSphere!==void 0)e.boundingSphere===null&&e.computeBoundingSphere(),Ei.copy(e.boundingSphere).applyMatrix4(e.matrixWorld);else{let t=e.geometry;t.boundingSphere===null&&t.computeBoundingSphere(),Ei.copy(t.boundingSphere).applyMatrix4(e.matrixWorld)}return this.intersectsSphere(Ei)}intersectsSprite(e){return Ei.center.set(0,0,0),Ei.radius=.7071067811865476,Ei.applyMatrix4(e.matrixWorld),this.intersectsSphere(Ei)}intersectsSphere(e){let t=this.planes,n=e.center,s=-e.radius;for(let r=0;r<6;r++)if(t[r].distanceToPoint(n)<s)return!1;return!0}intersectsBox(e){let t=this.planes;for(let n=0;n<6;n++){let s=t[n];if(Ar.x=s.normal.x>0?e.max.x:e.min.x,Ar.y=s.normal.y>0?e.max.y:e.min.y,Ar.z=s.normal.z>0?e.max.z:e.min.z,s.distanceToPoint(Ar)<0)return!1}return!0}containsPoint(e){let t=this.planes;for(let n=0;n<6;n++)if(t[n].distanceToPoint(e)<0)return!1;return!0}clone(){return new this.constructor().copy(this)}};function Mu(){let i=null,e=!1,t=null,n=null;function s(r,o){t(r,o),n=i.requestAnimationFrame(s)}return{start:function(){e!==!0&&t!==null&&(n=i.requestAnimationFrame(s),e=!0)},stop:function(){i.cancelAnimationFrame(n),e=!1},setAnimationLoop:function(r){t=r},setContext:function(r){i=r}}}function vf(i){let e=new WeakMap;function t(a,l){let c=a.array,h=a.usage,u=c.byteLength,d=i.createBuffer();i.bindBuffer(l,d),i.bufferData(l,c,h),a.onUploadCallback();let f;if(c instanceof Float32Array)f=i.FLOAT;else if(c instanceof Uint16Array)a.isFloat16BufferAttribute?f=i.HALF_FLOAT:f=i.UNSIGNED_SHORT;else if(c instanceof Int16Array)f=i.SHORT;else if(c instanceof Uint32Array)f=i.UNSIGNED_INT;else if(c instanceof Int32Array)f=i.INT;else if(c instanceof Int8Array)f=i.BYTE;else if(c instanceof Uint8Array)f=i.UNSIGNED_BYTE;else if(c instanceof Uint8ClampedArray)f=i.UNSIGNED_BYTE;else throw new Error("THREE.WebGLAttributes: Unsupported buffer data format: "+c);return{buffer:d,type:f,bytesPerElement:c.BYTES_PER_ELEMENT,version:a.version,size:u}}function n(a,l,c){let h=l.array,u=l.updateRanges;if(i.bindBuffer(c,a),u.length===0)i.bufferSubData(c,0,h);else{u.sort((f,g)=>f.start-g.start);let d=0;for(let f=1;f<u.length;f++){let g=u[d],_=u[f];_.start<=g.start+g.count+1?g.count=Math.max(g.count,_.start+_.count-g.start):(++d,u[d]=_)}u.length=d+1;for(let f=0,g=u.length;f<g;f++){let _=u[f];i.bufferSubData(c,_.start*h.BYTES_PER_ELEMENT,h,_.start,_.count)}l.clearUpdateRanges()}l.onUploadCallback()}function s(a){return a.isInterleavedBufferAttribute&&(a=a.data),e.get(a)}function r(a){a.isInterleavedBufferAttribute&&(a=a.data);let l=e.get(a);l&&(i.deleteBuffer(l.buffer),e.delete(a))}function o(a,l){if(a.isInterleavedBufferAttribute&&(a=a.data),a.isGLBufferAttribute){let h=e.get(a);(!h||h.version<a.version)&&e.set(a,{buffer:a.buffer,type:a.type,bytesPerElement:a.elementSize,version:a.version});return}let c=e.get(a);if(c===void 0)e.set(a,t(a,l));else if(c.version<a.version){if(c.size!==a.array.byteLength)throw new Error("THREE.WebGLAttributes: The size of the buffer attribute's array buffer does not match the original size. Resizing buffer attributes is not supported.");n(c.buffer,a,l),c.version=a.version}}return{get:s,remove:r,update:o}}var Yn=class i extends yt{constructor(e=1,t=1,n=1,s=1){super(),this.type="PlaneGeometry",this.parameters={width:e,height:t,widthSegments:n,heightSegments:s};let r=e/2,o=t/2,a=Math.floor(n),l=Math.floor(s),c=a+1,h=l+1,u=e/a,d=t/l,f=[],g=[],_=[],m=[];for(let p=0;p<h;p++){let w=p*d-o;for(let b=0;b<c;b++){let x=b*u-r;g.push(x,-w,0),_.push(0,0,1),m.push(b/a),m.push(1-p/l)}}for(let p=0;p<l;p++)for(let w=0;w<a;w++){let b=w+c*p,x=w+c*(p+1),P=w+1+c*(p+1),T=w+1+c*p;f.push(b,x,T),f.push(x,P,T)}this.setIndex(f),this.setAttribute("position",new dt(g,3)),this.setAttribute("normal",new dt(_,3)),this.setAttribute("uv",new dt(m,2))}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}static fromJSON(e){return new i(e.width,e.height,e.widthSegments,e.heightSegments)}},Mf=`#ifdef USE_ALPHAHASH
	if ( diffuseColor.a < getAlphaHashThreshold( vPosition ) ) discard;
#endif`,Sf=`#ifdef USE_ALPHAHASH
	const float ALPHA_HASH_SCALE = 0.05;
	float hash2D( vec2 value ) {
		return fract( 1.0e4 * sin( 17.0 * value.x + 0.1 * value.y ) * ( 0.1 + abs( sin( 13.0 * value.y + value.x ) ) ) );
	}
	float hash3D( vec3 value ) {
		return hash2D( vec2( hash2D( value.xy ), value.z ) );
	}
	float getAlphaHashThreshold( vec3 position ) {
		float maxDeriv = max(
			length( dFdx( position.xyz ) ),
			length( dFdy( position.xyz ) )
		);
		float pixScale = 1.0 / ( ALPHA_HASH_SCALE * maxDeriv );
		vec2 pixScales = vec2(
			exp2( floor( log2( pixScale ) ) ),
			exp2( ceil( log2( pixScale ) ) )
		);
		vec2 alpha = vec2(
			hash3D( floor( pixScales.x * position.xyz ) ),
			hash3D( floor( pixScales.y * position.xyz ) )
		);
		float lerpFactor = fract( log2( pixScale ) );
		float x = ( 1.0 - lerpFactor ) * alpha.x + lerpFactor * alpha.y;
		float a = min( lerpFactor, 1.0 - lerpFactor );
		vec3 cases = vec3(
			x * x / ( 2.0 * a * ( 1.0 - a ) ),
			( x - 0.5 * a ) / ( 1.0 - a ),
			1.0 - ( ( 1.0 - x ) * ( 1.0 - x ) / ( 2.0 * a * ( 1.0 - a ) ) )
		);
		float threshold = ( x < ( 1.0 - a ) )
			? ( ( x < a ) ? cases.x : cases.y )
			: cases.z;
		return clamp( threshold , 1.0e-6, 1.0 );
	}
#endif`,bf=`#ifdef USE_ALPHAMAP
	diffuseColor.a *= texture2D( alphaMap, vAlphaMapUv ).g;
#endif`,wf=`#ifdef USE_ALPHAMAP
	uniform sampler2D alphaMap;
#endif`,Ef=`#ifdef USE_ALPHATEST
	#ifdef ALPHA_TO_COVERAGE
	diffuseColor.a = smoothstep( alphaTest, alphaTest + fwidth( diffuseColor.a ), diffuseColor.a );
	if ( diffuseColor.a == 0.0 ) discard;
	#else
	if ( diffuseColor.a < alphaTest ) discard;
	#endif
#endif`,Af=`#ifdef USE_ALPHATEST
	uniform float alphaTest;
#endif`,Tf=`#ifdef USE_AOMAP
	float ambientOcclusion = ( texture2D( aoMap, vAoMapUv ).r - 1.0 ) * aoMapIntensity + 1.0;
	reflectedLight.indirectDiffuse *= ambientOcclusion;
	#if defined( USE_CLEARCOAT ) 
		clearcoatSpecularIndirect *= ambientOcclusion;
	#endif
	#if defined( USE_SHEEN ) 
		sheenSpecularIndirect *= ambientOcclusion;
	#endif
	#if defined( USE_ENVMAP ) && defined( STANDARD )
		float dotNV = saturate( dot( geometryNormal, geometryViewDir ) );
		reflectedLight.indirectSpecular *= computeSpecularOcclusion( dotNV, ambientOcclusion, material.roughness );
	#endif
#endif`,Rf=`#ifdef USE_AOMAP
	uniform sampler2D aoMap;
	uniform float aoMapIntensity;
#endif`,Cf=`#ifdef USE_BATCHING
	#if ! defined( GL_ANGLE_multi_draw )
	#define gl_DrawID _gl_DrawID
	uniform int _gl_DrawID;
	#endif
	uniform highp sampler2D batchingTexture;
	uniform highp usampler2D batchingIdTexture;
	mat4 getBatchingMatrix( const in float i ) {
		int size = textureSize( batchingTexture, 0 ).x;
		int j = int( i ) * 4;
		int x = j % size;
		int y = j / size;
		vec4 v1 = texelFetch( batchingTexture, ivec2( x, y ), 0 );
		vec4 v2 = texelFetch( batchingTexture, ivec2( x + 1, y ), 0 );
		vec4 v3 = texelFetch( batchingTexture, ivec2( x + 2, y ), 0 );
		vec4 v4 = texelFetch( batchingTexture, ivec2( x + 3, y ), 0 );
		return mat4( v1, v2, v3, v4 );
	}
	float getIndirectIndex( const in int i ) {
		int size = textureSize( batchingIdTexture, 0 ).x;
		int x = i % size;
		int y = i / size;
		return float( texelFetch( batchingIdTexture, ivec2( x, y ), 0 ).r );
	}
#endif
#ifdef USE_BATCHING_COLOR
	uniform sampler2D batchingColorTexture;
	vec3 getBatchingColor( const in float i ) {
		int size = textureSize( batchingColorTexture, 0 ).x;
		int j = int( i );
		int x = j % size;
		int y = j / size;
		return texelFetch( batchingColorTexture, ivec2( x, y ), 0 ).rgb;
	}
#endif`,If=`#ifdef USE_BATCHING
	mat4 batchingMatrix = getBatchingMatrix( getIndirectIndex( gl_DrawID ) );
#endif`,Pf=`vec3 transformed = vec3( position );
#ifdef USE_ALPHAHASH
	vPosition = vec3( position );
#endif`,Lf=`vec3 objectNormal = vec3( normal );
#ifdef USE_TANGENT
	vec3 objectTangent = vec3( tangent.xyz );
#endif`,Df=`float G_BlinnPhong_Implicit( ) {
	return 0.25;
}
float D_BlinnPhong( const in float shininess, const in float dotNH ) {
	return RECIPROCAL_PI * ( shininess * 0.5 + 1.0 ) * pow( dotNH, shininess );
}
vec3 BRDF_BlinnPhong( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, const in vec3 specularColor, const in float shininess ) {
	vec3 halfDir = normalize( lightDir + viewDir );
	float dotNH = saturate( dot( normal, halfDir ) );
	float dotVH = saturate( dot( viewDir, halfDir ) );
	vec3 F = F_Schlick( specularColor, 1.0, dotVH );
	float G = G_BlinnPhong_Implicit( );
	float D = D_BlinnPhong( shininess, dotNH );
	return F * ( G * D );
} // validated`,Uf=`#ifdef USE_IRIDESCENCE
	const mat3 XYZ_TO_REC709 = mat3(
		 3.2404542, -0.9692660,  0.0556434,
		-1.5371385,  1.8760108, -0.2040259,
		-0.4985314,  0.0415560,  1.0572252
	);
	vec3 Fresnel0ToIor( vec3 fresnel0 ) {
		vec3 sqrtF0 = sqrt( fresnel0 );
		return ( vec3( 1.0 ) + sqrtF0 ) / ( vec3( 1.0 ) - sqrtF0 );
	}
	vec3 IorToFresnel0( vec3 transmittedIor, float incidentIor ) {
		return pow2( ( transmittedIor - vec3( incidentIor ) ) / ( transmittedIor + vec3( incidentIor ) ) );
	}
	float IorToFresnel0( float transmittedIor, float incidentIor ) {
		return pow2( ( transmittedIor - incidentIor ) / ( transmittedIor + incidentIor ));
	}
	vec3 evalSensitivity( float OPD, vec3 shift ) {
		float phase = 2.0 * PI * OPD * 1.0e-9;
		vec3 val = vec3( 5.4856e-13, 4.4201e-13, 5.2481e-13 );
		vec3 pos = vec3( 1.6810e+06, 1.7953e+06, 2.2084e+06 );
		vec3 var = vec3( 4.3278e+09, 9.3046e+09, 6.6121e+09 );
		vec3 xyz = val * sqrt( 2.0 * PI * var ) * cos( pos * phase + shift ) * exp( - pow2( phase ) * var );
		xyz.x += 9.7470e-14 * sqrt( 2.0 * PI * 4.5282e+09 ) * cos( 2.2399e+06 * phase + shift[ 0 ] ) * exp( - 4.5282e+09 * pow2( phase ) );
		xyz /= 1.0685e-7;
		vec3 rgb = XYZ_TO_REC709 * xyz;
		return rgb;
	}
	vec3 evalIridescence( float outsideIOR, float eta2, float cosTheta1, float thinFilmThickness, vec3 baseF0 ) {
		vec3 I;
		float iridescenceIOR = mix( outsideIOR, eta2, smoothstep( 0.0, 0.03, thinFilmThickness ) );
		float sinTheta2Sq = pow2( outsideIOR / iridescenceIOR ) * ( 1.0 - pow2( cosTheta1 ) );
		float cosTheta2Sq = 1.0 - sinTheta2Sq;
		if ( cosTheta2Sq < 0.0 ) {
			return vec3( 1.0 );
		}
		float cosTheta2 = sqrt( cosTheta2Sq );
		float R0 = IorToFresnel0( iridescenceIOR, outsideIOR );
		float R12 = F_Schlick( R0, 1.0, cosTheta1 );
		float T121 = 1.0 - R12;
		float phi12 = 0.0;
		if ( iridescenceIOR < outsideIOR ) phi12 = PI;
		float phi21 = PI - phi12;
		vec3 baseIOR = Fresnel0ToIor( clamp( baseF0, 0.0, 0.9999 ) );		vec3 R1 = IorToFresnel0( baseIOR, iridescenceIOR );
		vec3 R23 = F_Schlick( R1, 1.0, cosTheta2 );
		vec3 phi23 = vec3( 0.0 );
		if ( baseIOR[ 0 ] < iridescenceIOR ) phi23[ 0 ] = PI;
		if ( baseIOR[ 1 ] < iridescenceIOR ) phi23[ 1 ] = PI;
		if ( baseIOR[ 2 ] < iridescenceIOR ) phi23[ 2 ] = PI;
		float OPD = 2.0 * iridescenceIOR * thinFilmThickness * cosTheta2;
		vec3 phi = vec3( phi21 ) + phi23;
		vec3 R123 = clamp( R12 * R23, 1e-5, 0.9999 );
		vec3 r123 = sqrt( R123 );
		vec3 Rs = pow2( T121 ) * R23 / ( vec3( 1.0 ) - R123 );
		vec3 C0 = R12 + Rs;
		I = C0;
		vec3 Cm = Rs - T121;
		for ( int m = 1; m <= 2; ++ m ) {
			Cm *= r123;
			vec3 Sm = 2.0 * evalSensitivity( float( m ) * OPD, float( m ) * phi );
			I += Cm * Sm;
		}
		return max( I, vec3( 0.0 ) );
	}
#endif`,Nf=`#ifdef USE_BUMPMAP
	uniform sampler2D bumpMap;
	uniform float bumpScale;
	vec2 dHdxy_fwd() {
		vec2 dSTdx = dFdx( vBumpMapUv );
		vec2 dSTdy = dFdy( vBumpMapUv );
		float Hll = bumpScale * texture2D( bumpMap, vBumpMapUv ).x;
		float dBx = bumpScale * texture2D( bumpMap, vBumpMapUv + dSTdx ).x - Hll;
		float dBy = bumpScale * texture2D( bumpMap, vBumpMapUv + dSTdy ).x - Hll;
		return vec2( dBx, dBy );
	}
	vec3 perturbNormalArb( vec3 surf_pos, vec3 surf_norm, vec2 dHdxy, float faceDirection ) {
		vec3 vSigmaX = normalize( dFdx( surf_pos.xyz ) );
		vec3 vSigmaY = normalize( dFdy( surf_pos.xyz ) );
		vec3 vN = surf_norm;
		vec3 R1 = cross( vSigmaY, vN );
		vec3 R2 = cross( vN, vSigmaX );
		float fDet = dot( vSigmaX, R1 ) * faceDirection;
		vec3 vGrad = sign( fDet ) * ( dHdxy.x * R1 + dHdxy.y * R2 );
		return normalize( abs( fDet ) * surf_norm - vGrad );
	}
#endif`,Of=`#if NUM_CLIPPING_PLANES > 0
	vec4 plane;
	#ifdef ALPHA_TO_COVERAGE
		float distanceToPlane, distanceGradient;
		float clipOpacity = 1.0;
		#pragma unroll_loop_start
		for ( int i = 0; i < UNION_CLIPPING_PLANES; i ++ ) {
			plane = clippingPlanes[ i ];
			distanceToPlane = - dot( vClipPosition, plane.xyz ) + plane.w;
			distanceGradient = fwidth( distanceToPlane ) / 2.0;
			clipOpacity *= smoothstep( - distanceGradient, distanceGradient, distanceToPlane );
			if ( clipOpacity == 0.0 ) discard;
		}
		#pragma unroll_loop_end
		#if UNION_CLIPPING_PLANES < NUM_CLIPPING_PLANES
			float unionClipOpacity = 1.0;
			#pragma unroll_loop_start
			for ( int i = UNION_CLIPPING_PLANES; i < NUM_CLIPPING_PLANES; i ++ ) {
				plane = clippingPlanes[ i ];
				distanceToPlane = - dot( vClipPosition, plane.xyz ) + plane.w;
				distanceGradient = fwidth( distanceToPlane ) / 2.0;
				unionClipOpacity *= 1.0 - smoothstep( - distanceGradient, distanceGradient, distanceToPlane );
			}
			#pragma unroll_loop_end
			clipOpacity *= 1.0 - unionClipOpacity;
		#endif
		diffuseColor.a *= clipOpacity;
		if ( diffuseColor.a == 0.0 ) discard;
	#else
		#pragma unroll_loop_start
		for ( int i = 0; i < UNION_CLIPPING_PLANES; i ++ ) {
			plane = clippingPlanes[ i ];
			if ( dot( vClipPosition, plane.xyz ) > plane.w ) discard;
		}
		#pragma unroll_loop_end
		#if UNION_CLIPPING_PLANES < NUM_CLIPPING_PLANES
			bool clipped = true;
			#pragma unroll_loop_start
			for ( int i = UNION_CLIPPING_PLANES; i < NUM_CLIPPING_PLANES; i ++ ) {
				plane = clippingPlanes[ i ];
				clipped = ( dot( vClipPosition, plane.xyz ) > plane.w ) && clipped;
			}
			#pragma unroll_loop_end
			if ( clipped ) discard;
		#endif
	#endif
#endif`,Ff=`#if NUM_CLIPPING_PLANES > 0
	varying vec3 vClipPosition;
	uniform vec4 clippingPlanes[ NUM_CLIPPING_PLANES ];
#endif`,Bf=`#if NUM_CLIPPING_PLANES > 0
	varying vec3 vClipPosition;
#endif`,zf=`#if NUM_CLIPPING_PLANES > 0
	vClipPosition = - mvPosition.xyz;
#endif`,kf=`#if defined( USE_COLOR_ALPHA )
	diffuseColor *= vColor;
#elif defined( USE_COLOR )
	diffuseColor.rgb *= vColor;
#endif`,Hf=`#if defined( USE_COLOR_ALPHA )
	varying vec4 vColor;
#elif defined( USE_COLOR )
	varying vec3 vColor;
#endif`,Vf=`#if defined( USE_COLOR_ALPHA )
	varying vec4 vColor;
#elif defined( USE_COLOR ) || defined( USE_INSTANCING_COLOR ) || defined( USE_BATCHING_COLOR )
	varying vec3 vColor;
#endif`,Gf=`#if defined( USE_COLOR_ALPHA )
	vColor = vec4( 1.0 );
#elif defined( USE_COLOR ) || defined( USE_INSTANCING_COLOR ) || defined( USE_BATCHING_COLOR )
	vColor = vec3( 1.0 );
#endif
#ifdef USE_COLOR
	vColor *= color;
#endif
#ifdef USE_INSTANCING_COLOR
	vColor.xyz *= instanceColor.xyz;
#endif
#ifdef USE_BATCHING_COLOR
	vec3 batchingColor = getBatchingColor( getIndirectIndex( gl_DrawID ) );
	vColor.xyz *= batchingColor.xyz;
#endif`,Wf=`#define PI 3.141592653589793
#define PI2 6.283185307179586
#define PI_HALF 1.5707963267948966
#define RECIPROCAL_PI 0.3183098861837907
#define RECIPROCAL_PI2 0.15915494309189535
#define EPSILON 1e-6
#ifndef saturate
#define saturate( a ) clamp( a, 0.0, 1.0 )
#endif
#define whiteComplement( a ) ( 1.0 - saturate( a ) )
float pow2( const in float x ) { return x*x; }
vec3 pow2( const in vec3 x ) { return x*x; }
float pow3( const in float x ) { return x*x*x; }
float pow4( const in float x ) { float x2 = x*x; return x2*x2; }
float max3( const in vec3 v ) { return max( max( v.x, v.y ), v.z ); }
float average( const in vec3 v ) { return dot( v, vec3( 0.3333333 ) ); }
highp float rand( const in vec2 uv ) {
	const highp float a = 12.9898, b = 78.233, c = 43758.5453;
	highp float dt = dot( uv.xy, vec2( a,b ) ), sn = mod( dt, PI );
	return fract( sin( sn ) * c );
}
#ifdef HIGH_PRECISION
	float precisionSafeLength( vec3 v ) { return length( v ); }
#else
	float precisionSafeLength( vec3 v ) {
		float maxComponent = max3( abs( v ) );
		return length( v / maxComponent ) * maxComponent;
	}
#endif
struct IncidentLight {
	vec3 color;
	vec3 direction;
	bool visible;
};
struct ReflectedLight {
	vec3 directDiffuse;
	vec3 directSpecular;
	vec3 indirectDiffuse;
	vec3 indirectSpecular;
};
#ifdef USE_ALPHAHASH
	varying vec3 vPosition;
#endif
vec3 transformDirection( in vec3 dir, in mat4 matrix ) {
	return normalize( ( matrix * vec4( dir, 0.0 ) ).xyz );
}
vec3 inverseTransformDirection( in vec3 dir, in mat4 matrix ) {
	return normalize( ( vec4( dir, 0.0 ) * matrix ).xyz );
}
mat3 transposeMat3( const in mat3 m ) {
	mat3 tmp;
	tmp[ 0 ] = vec3( m[ 0 ].x, m[ 1 ].x, m[ 2 ].x );
	tmp[ 1 ] = vec3( m[ 0 ].y, m[ 1 ].y, m[ 2 ].y );
	tmp[ 2 ] = vec3( m[ 0 ].z, m[ 1 ].z, m[ 2 ].z );
	return tmp;
}
bool isPerspectiveMatrix( mat4 m ) {
	return m[ 2 ][ 3 ] == - 1.0;
}
vec2 equirectUv( in vec3 dir ) {
	float u = atan( dir.z, dir.x ) * RECIPROCAL_PI2 + 0.5;
	float v = asin( clamp( dir.y, - 1.0, 1.0 ) ) * RECIPROCAL_PI + 0.5;
	return vec2( u, v );
}
vec3 BRDF_Lambert( const in vec3 diffuseColor ) {
	return RECIPROCAL_PI * diffuseColor;
}
vec3 F_Schlick( const in vec3 f0, const in float f90, const in float dotVH ) {
	float fresnel = exp2( ( - 5.55473 * dotVH - 6.98316 ) * dotVH );
	return f0 * ( 1.0 - fresnel ) + ( f90 * fresnel );
}
float F_Schlick( const in float f0, const in float f90, const in float dotVH ) {
	float fresnel = exp2( ( - 5.55473 * dotVH - 6.98316 ) * dotVH );
	return f0 * ( 1.0 - fresnel ) + ( f90 * fresnel );
} // validated`,Xf=`#ifdef ENVMAP_TYPE_CUBE_UV
	#define cubeUV_minMipLevel 4.0
	#define cubeUV_minTileSize 16.0
	float getFace( vec3 direction ) {
		vec3 absDirection = abs( direction );
		float face = - 1.0;
		if ( absDirection.x > absDirection.z ) {
			if ( absDirection.x > absDirection.y )
				face = direction.x > 0.0 ? 0.0 : 3.0;
			else
				face = direction.y > 0.0 ? 1.0 : 4.0;
		} else {
			if ( absDirection.z > absDirection.y )
				face = direction.z > 0.0 ? 2.0 : 5.0;
			else
				face = direction.y > 0.0 ? 1.0 : 4.0;
		}
		return face;
	}
	vec2 getUV( vec3 direction, float face ) {
		vec2 uv;
		if ( face == 0.0 ) {
			uv = vec2( direction.z, direction.y ) / abs( direction.x );
		} else if ( face == 1.0 ) {
			uv = vec2( - direction.x, - direction.z ) / abs( direction.y );
		} else if ( face == 2.0 ) {
			uv = vec2( - direction.x, direction.y ) / abs( direction.z );
		} else if ( face == 3.0 ) {
			uv = vec2( - direction.z, direction.y ) / abs( direction.x );
		} else if ( face == 4.0 ) {
			uv = vec2( - direction.x, direction.z ) / abs( direction.y );
		} else {
			uv = vec2( direction.x, direction.y ) / abs( direction.z );
		}
		return 0.5 * ( uv + 1.0 );
	}
	vec3 bilinearCubeUV( sampler2D envMap, vec3 direction, float mipInt ) {
		float face = getFace( direction );
		float filterInt = max( cubeUV_minMipLevel - mipInt, 0.0 );
		mipInt = max( mipInt, cubeUV_minMipLevel );
		float faceSize = exp2( mipInt );
		highp vec2 uv = getUV( direction, face ) * ( faceSize - 2.0 ) + 1.0;
		if ( face > 2.0 ) {
			uv.y += faceSize;
			face -= 3.0;
		}
		uv.x += face * faceSize;
		uv.x += filterInt * 3.0 * cubeUV_minTileSize;
		uv.y += 4.0 * ( exp2( CUBEUV_MAX_MIP ) - faceSize );
		uv.x *= CUBEUV_TEXEL_WIDTH;
		uv.y *= CUBEUV_TEXEL_HEIGHT;
		#ifdef texture2DGradEXT
			return texture2DGradEXT( envMap, uv, vec2( 0.0 ), vec2( 0.0 ) ).rgb;
		#else
			return texture2D( envMap, uv ).rgb;
		#endif
	}
	#define cubeUV_r0 1.0
	#define cubeUV_m0 - 2.0
	#define cubeUV_r1 0.8
	#define cubeUV_m1 - 1.0
	#define cubeUV_r4 0.4
	#define cubeUV_m4 2.0
	#define cubeUV_r5 0.305
	#define cubeUV_m5 3.0
	#define cubeUV_r6 0.21
	#define cubeUV_m6 4.0
	float roughnessToMip( float roughness ) {
		float mip = 0.0;
		if ( roughness >= cubeUV_r1 ) {
			mip = ( cubeUV_r0 - roughness ) * ( cubeUV_m1 - cubeUV_m0 ) / ( cubeUV_r0 - cubeUV_r1 ) + cubeUV_m0;
		} else if ( roughness >= cubeUV_r4 ) {
			mip = ( cubeUV_r1 - roughness ) * ( cubeUV_m4 - cubeUV_m1 ) / ( cubeUV_r1 - cubeUV_r4 ) + cubeUV_m1;
		} else if ( roughness >= cubeUV_r5 ) {
			mip = ( cubeUV_r4 - roughness ) * ( cubeUV_m5 - cubeUV_m4 ) / ( cubeUV_r4 - cubeUV_r5 ) + cubeUV_m4;
		} else if ( roughness >= cubeUV_r6 ) {
			mip = ( cubeUV_r5 - roughness ) * ( cubeUV_m6 - cubeUV_m5 ) / ( cubeUV_r5 - cubeUV_r6 ) + cubeUV_m5;
		} else {
			mip = - 2.0 * log2( 1.16 * roughness );		}
		return mip;
	}
	vec4 textureCubeUV( sampler2D envMap, vec3 sampleDir, float roughness ) {
		float mip = clamp( roughnessToMip( roughness ), cubeUV_m0, CUBEUV_MAX_MIP );
		float mipF = fract( mip );
		float mipInt = floor( mip );
		vec3 color0 = bilinearCubeUV( envMap, sampleDir, mipInt );
		if ( mipF == 0.0 ) {
			return vec4( color0, 1.0 );
		} else {
			vec3 color1 = bilinearCubeUV( envMap, sampleDir, mipInt + 1.0 );
			return vec4( mix( color0, color1, mipF ), 1.0 );
		}
	}
#endif`,qf=`vec3 transformedNormal = objectNormal;
#ifdef USE_TANGENT
	vec3 transformedTangent = objectTangent;
#endif
#ifdef USE_BATCHING
	mat3 bm = mat3( batchingMatrix );
	transformedNormal /= vec3( dot( bm[ 0 ], bm[ 0 ] ), dot( bm[ 1 ], bm[ 1 ] ), dot( bm[ 2 ], bm[ 2 ] ) );
	transformedNormal = bm * transformedNormal;
	#ifdef USE_TANGENT
		transformedTangent = bm * transformedTangent;
	#endif
#endif
#ifdef USE_INSTANCING
	mat3 im = mat3( instanceMatrix );
	transformedNormal /= vec3( dot( im[ 0 ], im[ 0 ] ), dot( im[ 1 ], im[ 1 ] ), dot( im[ 2 ], im[ 2 ] ) );
	transformedNormal = im * transformedNormal;
	#ifdef USE_TANGENT
		transformedTangent = im * transformedTangent;
	#endif
#endif
transformedNormal = normalMatrix * transformedNormal;
#ifdef FLIP_SIDED
	transformedNormal = - transformedNormal;
#endif
#ifdef USE_TANGENT
	transformedTangent = ( modelViewMatrix * vec4( transformedTangent, 0.0 ) ).xyz;
	#ifdef FLIP_SIDED
		transformedTangent = - transformedTangent;
	#endif
#endif`,Yf=`#ifdef USE_DISPLACEMENTMAP
	uniform sampler2D displacementMap;
	uniform float displacementScale;
	uniform float displacementBias;
#endif`,Zf=`#ifdef USE_DISPLACEMENTMAP
	transformed += normalize( objectNormal ) * ( texture2D( displacementMap, vDisplacementMapUv ).x * displacementScale + displacementBias );
#endif`,Kf=`#ifdef USE_EMISSIVEMAP
	vec4 emissiveColor = texture2D( emissiveMap, vEmissiveMapUv );
	#ifdef DECODE_VIDEO_TEXTURE_EMISSIVE
		emissiveColor = sRGBTransferEOTF( emissiveColor );
	#endif
	totalEmissiveRadiance *= emissiveColor.rgb;
#endif`,Jf=`#ifdef USE_EMISSIVEMAP
	uniform sampler2D emissiveMap;
#endif`,jf="gl_FragColor = linearToOutputTexel( gl_FragColor );",$f=`vec4 LinearTransferOETF( in vec4 value ) {
	return value;
}
vec4 sRGBTransferEOTF( in vec4 value ) {
	return vec4( mix( pow( value.rgb * 0.9478672986 + vec3( 0.0521327014 ), vec3( 2.4 ) ), value.rgb * 0.0773993808, vec3( lessThanEqual( value.rgb, vec3( 0.04045 ) ) ) ), value.a );
}
vec4 sRGBTransferOETF( in vec4 value ) {
	return vec4( mix( pow( value.rgb, vec3( 0.41666 ) ) * 1.055 - vec3( 0.055 ), value.rgb * 12.92, vec3( lessThanEqual( value.rgb, vec3( 0.0031308 ) ) ) ), value.a );
}`,Qf=`#ifdef USE_ENVMAP
	#ifdef ENV_WORLDPOS
		vec3 cameraToFrag;
		if ( isOrthographic ) {
			cameraToFrag = normalize( vec3( - viewMatrix[ 0 ][ 2 ], - viewMatrix[ 1 ][ 2 ], - viewMatrix[ 2 ][ 2 ] ) );
		} else {
			cameraToFrag = normalize( vWorldPosition - cameraPosition );
		}
		vec3 worldNormal = inverseTransformDirection( normal, viewMatrix );
		#ifdef ENVMAP_MODE_REFLECTION
			vec3 reflectVec = reflect( cameraToFrag, worldNormal );
		#else
			vec3 reflectVec = refract( cameraToFrag, worldNormal, refractionRatio );
		#endif
	#else
		vec3 reflectVec = vReflect;
	#endif
	#ifdef ENVMAP_TYPE_CUBE
		vec4 envColor = textureCube( envMap, envMapRotation * vec3( flipEnvMap * reflectVec.x, reflectVec.yz ) );
	#else
		vec4 envColor = vec4( 0.0 );
	#endif
	#ifdef ENVMAP_BLENDING_MULTIPLY
		outgoingLight = mix( outgoingLight, outgoingLight * envColor.xyz, specularStrength * reflectivity );
	#elif defined( ENVMAP_BLENDING_MIX )
		outgoingLight = mix( outgoingLight, envColor.xyz, specularStrength * reflectivity );
	#elif defined( ENVMAP_BLENDING_ADD )
		outgoingLight += envColor.xyz * specularStrength * reflectivity;
	#endif
#endif`,ep=`#ifdef USE_ENVMAP
	uniform float envMapIntensity;
	uniform float flipEnvMap;
	uniform mat3 envMapRotation;
	#ifdef ENVMAP_TYPE_CUBE
		uniform samplerCube envMap;
	#else
		uniform sampler2D envMap;
	#endif
	
#endif`,tp=`#ifdef USE_ENVMAP
	uniform float reflectivity;
	#if defined( USE_BUMPMAP ) || defined( USE_NORMALMAP ) || defined( PHONG ) || defined( LAMBERT )
		#define ENV_WORLDPOS
	#endif
	#ifdef ENV_WORLDPOS
		varying vec3 vWorldPosition;
		uniform float refractionRatio;
	#else
		varying vec3 vReflect;
	#endif
#endif`,np=`#ifdef USE_ENVMAP
	#if defined( USE_BUMPMAP ) || defined( USE_NORMALMAP ) || defined( PHONG ) || defined( LAMBERT )
		#define ENV_WORLDPOS
	#endif
	#ifdef ENV_WORLDPOS
		
		varying vec3 vWorldPosition;
	#else
		varying vec3 vReflect;
		uniform float refractionRatio;
	#endif
#endif`,ip=`#ifdef USE_ENVMAP
	#ifdef ENV_WORLDPOS
		vWorldPosition = worldPosition.xyz;
	#else
		vec3 cameraToVertex;
		if ( isOrthographic ) {
			cameraToVertex = normalize( vec3( - viewMatrix[ 0 ][ 2 ], - viewMatrix[ 1 ][ 2 ], - viewMatrix[ 2 ][ 2 ] ) );
		} else {
			cameraToVertex = normalize( worldPosition.xyz - cameraPosition );
		}
		vec3 worldNormal = inverseTransformDirection( transformedNormal, viewMatrix );
		#ifdef ENVMAP_MODE_REFLECTION
			vReflect = reflect( cameraToVertex, worldNormal );
		#else
			vReflect = refract( cameraToVertex, worldNormal, refractionRatio );
		#endif
	#endif
#endif`,sp=`#ifdef USE_FOG
	vFogDepth = - mvPosition.z;
#endif`,rp=`#ifdef USE_FOG
	varying float vFogDepth;
#endif`,op=`#ifdef USE_FOG
	#ifdef FOG_EXP2
		float fogFactor = 1.0 - exp( - fogDensity * fogDensity * vFogDepth * vFogDepth );
	#else
		float fogFactor = smoothstep( fogNear, fogFar, vFogDepth );
	#endif
	gl_FragColor.rgb = mix( gl_FragColor.rgb, fogColor, fogFactor );
#endif`,ap=`#ifdef USE_FOG
	uniform vec3 fogColor;
	varying float vFogDepth;
	#ifdef FOG_EXP2
		uniform float fogDensity;
	#else
		uniform float fogNear;
		uniform float fogFar;
	#endif
#endif`,lp=`#ifdef USE_GRADIENTMAP
	uniform sampler2D gradientMap;
#endif
vec3 getGradientIrradiance( vec3 normal, vec3 lightDirection ) {
	float dotNL = dot( normal, lightDirection );
	vec2 coord = vec2( dotNL * 0.5 + 0.5, 0.0 );
	#ifdef USE_GRADIENTMAP
		return vec3( texture2D( gradientMap, coord ).r );
	#else
		vec2 fw = fwidth( coord ) * 0.5;
		return mix( vec3( 0.7 ), vec3( 1.0 ), smoothstep( 0.7 - fw.x, 0.7 + fw.x, coord.x ) );
	#endif
}`,cp=`#ifdef USE_LIGHTMAP
	uniform sampler2D lightMap;
	uniform float lightMapIntensity;
#endif`,hp=`LambertMaterial material;
material.diffuseColor = diffuseColor.rgb;
material.specularStrength = specularStrength;`,up=`varying vec3 vViewPosition;
struct LambertMaterial {
	vec3 diffuseColor;
	float specularStrength;
};
void RE_Direct_Lambert( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in LambertMaterial material, inout ReflectedLight reflectedLight ) {
	float dotNL = saturate( dot( geometryNormal, directLight.direction ) );
	vec3 irradiance = dotNL * directLight.color;
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
void RE_IndirectDiffuse_Lambert( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in LambertMaterial material, inout ReflectedLight reflectedLight ) {
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
#define RE_Direct				RE_Direct_Lambert
#define RE_IndirectDiffuse		RE_IndirectDiffuse_Lambert`,dp=`uniform bool receiveShadow;
uniform vec3 ambientLightColor;
#if defined( USE_LIGHT_PROBES )
	uniform vec3 lightProbe[ 9 ];
#endif
vec3 shGetIrradianceAt( in vec3 normal, in vec3 shCoefficients[ 9 ] ) {
	float x = normal.x, y = normal.y, z = normal.z;
	vec3 result = shCoefficients[ 0 ] * 0.886227;
	result += shCoefficients[ 1 ] * 2.0 * 0.511664 * y;
	result += shCoefficients[ 2 ] * 2.0 * 0.511664 * z;
	result += shCoefficients[ 3 ] * 2.0 * 0.511664 * x;
	result += shCoefficients[ 4 ] * 2.0 * 0.429043 * x * y;
	result += shCoefficients[ 5 ] * 2.0 * 0.429043 * y * z;
	result += shCoefficients[ 6 ] * ( 0.743125 * z * z - 0.247708 );
	result += shCoefficients[ 7 ] * 2.0 * 0.429043 * x * z;
	result += shCoefficients[ 8 ] * 0.429043 * ( x * x - y * y );
	return result;
}
vec3 getLightProbeIrradiance( const in vec3 lightProbe[ 9 ], const in vec3 normal ) {
	vec3 worldNormal = inverseTransformDirection( normal, viewMatrix );
	vec3 irradiance = shGetIrradianceAt( worldNormal, lightProbe );
	return irradiance;
}
vec3 getAmbientLightIrradiance( const in vec3 ambientLightColor ) {
	vec3 irradiance = ambientLightColor;
	return irradiance;
}
float getDistanceAttenuation( const in float lightDistance, const in float cutoffDistance, const in float decayExponent ) {
	float distanceFalloff = 1.0 / max( pow( lightDistance, decayExponent ), 0.01 );
	if ( cutoffDistance > 0.0 ) {
		distanceFalloff *= pow2( saturate( 1.0 - pow4( lightDistance / cutoffDistance ) ) );
	}
	return distanceFalloff;
}
float getSpotAttenuation( const in float coneCosine, const in float penumbraCosine, const in float angleCosine ) {
	return smoothstep( coneCosine, penumbraCosine, angleCosine );
}
#if NUM_DIR_LIGHTS > 0
	struct DirectionalLight {
		vec3 direction;
		vec3 color;
	};
	uniform DirectionalLight directionalLights[ NUM_DIR_LIGHTS ];
	void getDirectionalLightInfo( const in DirectionalLight directionalLight, out IncidentLight light ) {
		light.color = directionalLight.color;
		light.direction = directionalLight.direction;
		light.visible = true;
	}
#endif
#if NUM_POINT_LIGHTS > 0
	struct PointLight {
		vec3 position;
		vec3 color;
		float distance;
		float decay;
	};
	uniform PointLight pointLights[ NUM_POINT_LIGHTS ];
	void getPointLightInfo( const in PointLight pointLight, const in vec3 geometryPosition, out IncidentLight light ) {
		vec3 lVector = pointLight.position - geometryPosition;
		light.direction = normalize( lVector );
		float lightDistance = length( lVector );
		light.color = pointLight.color;
		light.color *= getDistanceAttenuation( lightDistance, pointLight.distance, pointLight.decay );
		light.visible = ( light.color != vec3( 0.0 ) );
	}
#endif
#if NUM_SPOT_LIGHTS > 0
	struct SpotLight {
		vec3 position;
		vec3 direction;
		vec3 color;
		float distance;
		float decay;
		float coneCos;
		float penumbraCos;
	};
	uniform SpotLight spotLights[ NUM_SPOT_LIGHTS ];
	void getSpotLightInfo( const in SpotLight spotLight, const in vec3 geometryPosition, out IncidentLight light ) {
		vec3 lVector = spotLight.position - geometryPosition;
		light.direction = normalize( lVector );
		float angleCos = dot( light.direction, spotLight.direction );
		float spotAttenuation = getSpotAttenuation( spotLight.coneCos, spotLight.penumbraCos, angleCos );
		if ( spotAttenuation > 0.0 ) {
			float lightDistance = length( lVector );
			light.color = spotLight.color * spotAttenuation;
			light.color *= getDistanceAttenuation( lightDistance, spotLight.distance, spotLight.decay );
			light.visible = ( light.color != vec3( 0.0 ) );
		} else {
			light.color = vec3( 0.0 );
			light.visible = false;
		}
	}
#endif
#if NUM_RECT_AREA_LIGHTS > 0
	struct RectAreaLight {
		vec3 color;
		vec3 position;
		vec3 halfWidth;
		vec3 halfHeight;
	};
	uniform sampler2D ltc_1;	uniform sampler2D ltc_2;
	uniform RectAreaLight rectAreaLights[ NUM_RECT_AREA_LIGHTS ];
#endif
#if NUM_HEMI_LIGHTS > 0
	struct HemisphereLight {
		vec3 direction;
		vec3 skyColor;
		vec3 groundColor;
	};
	uniform HemisphereLight hemisphereLights[ NUM_HEMI_LIGHTS ];
	vec3 getHemisphereLightIrradiance( const in HemisphereLight hemiLight, const in vec3 normal ) {
		float dotNL = dot( normal, hemiLight.direction );
		float hemiDiffuseWeight = 0.5 * dotNL + 0.5;
		vec3 irradiance = mix( hemiLight.groundColor, hemiLight.skyColor, hemiDiffuseWeight );
		return irradiance;
	}
#endif`,fp=`#ifdef USE_ENVMAP
	vec3 getIBLIrradiance( const in vec3 normal ) {
		#ifdef ENVMAP_TYPE_CUBE_UV
			vec3 worldNormal = inverseTransformDirection( normal, viewMatrix );
			vec4 envMapColor = textureCubeUV( envMap, envMapRotation * worldNormal, 1.0 );
			return PI * envMapColor.rgb * envMapIntensity;
		#else
			return vec3( 0.0 );
		#endif
	}
	vec3 getIBLRadiance( const in vec3 viewDir, const in vec3 normal, const in float roughness ) {
		#ifdef ENVMAP_TYPE_CUBE_UV
			vec3 reflectVec = reflect( - viewDir, normal );
			reflectVec = normalize( mix( reflectVec, normal, roughness * roughness) );
			reflectVec = inverseTransformDirection( reflectVec, viewMatrix );
			vec4 envMapColor = textureCubeUV( envMap, envMapRotation * reflectVec, roughness );
			return envMapColor.rgb * envMapIntensity;
		#else
			return vec3( 0.0 );
		#endif
	}
	#ifdef USE_ANISOTROPY
		vec3 getIBLAnisotropyRadiance( const in vec3 viewDir, const in vec3 normal, const in float roughness, const in vec3 bitangent, const in float anisotropy ) {
			#ifdef ENVMAP_TYPE_CUBE_UV
				vec3 bentNormal = cross( bitangent, viewDir );
				bentNormal = normalize( cross( bentNormal, bitangent ) );
				bentNormal = normalize( mix( bentNormal, normal, pow2( pow2( 1.0 - anisotropy * ( 1.0 - roughness ) ) ) ) );
				return getIBLRadiance( viewDir, bentNormal, roughness );
			#else
				return vec3( 0.0 );
			#endif
		}
	#endif
#endif`,pp=`ToonMaterial material;
material.diffuseColor = diffuseColor.rgb;`,mp=`varying vec3 vViewPosition;
struct ToonMaterial {
	vec3 diffuseColor;
};
void RE_Direct_Toon( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in ToonMaterial material, inout ReflectedLight reflectedLight ) {
	vec3 irradiance = getGradientIrradiance( geometryNormal, directLight.direction ) * directLight.color;
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
void RE_IndirectDiffuse_Toon( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in ToonMaterial material, inout ReflectedLight reflectedLight ) {
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
#define RE_Direct				RE_Direct_Toon
#define RE_IndirectDiffuse		RE_IndirectDiffuse_Toon`,gp=`BlinnPhongMaterial material;
material.diffuseColor = diffuseColor.rgb;
material.specularColor = specular;
material.specularShininess = shininess;
material.specularStrength = specularStrength;`,_p=`varying vec3 vViewPosition;
struct BlinnPhongMaterial {
	vec3 diffuseColor;
	vec3 specularColor;
	float specularShininess;
	float specularStrength;
};
void RE_Direct_BlinnPhong( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in BlinnPhongMaterial material, inout ReflectedLight reflectedLight ) {
	float dotNL = saturate( dot( geometryNormal, directLight.direction ) );
	vec3 irradiance = dotNL * directLight.color;
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
	reflectedLight.directSpecular += irradiance * BRDF_BlinnPhong( directLight.direction, geometryViewDir, geometryNormal, material.specularColor, material.specularShininess ) * material.specularStrength;
}
void RE_IndirectDiffuse_BlinnPhong( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in BlinnPhongMaterial material, inout ReflectedLight reflectedLight ) {
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
#define RE_Direct				RE_Direct_BlinnPhong
#define RE_IndirectDiffuse		RE_IndirectDiffuse_BlinnPhong`,xp=`PhysicalMaterial material;
material.diffuseColor = diffuseColor.rgb * ( 1.0 - metalnessFactor );
vec3 dxy = max( abs( dFdx( nonPerturbedNormal ) ), abs( dFdy( nonPerturbedNormal ) ) );
float geometryRoughness = max( max( dxy.x, dxy.y ), dxy.z );
material.roughness = max( roughnessFactor, 0.0525 );material.roughness += geometryRoughness;
material.roughness = min( material.roughness, 1.0 );
#ifdef IOR
	material.ior = ior;
	#ifdef USE_SPECULAR
		float specularIntensityFactor = specularIntensity;
		vec3 specularColorFactor = specularColor;
		#ifdef USE_SPECULAR_COLORMAP
			specularColorFactor *= texture2D( specularColorMap, vSpecularColorMapUv ).rgb;
		#endif
		#ifdef USE_SPECULAR_INTENSITYMAP
			specularIntensityFactor *= texture2D( specularIntensityMap, vSpecularIntensityMapUv ).a;
		#endif
		material.specularF90 = mix( specularIntensityFactor, 1.0, metalnessFactor );
	#else
		float specularIntensityFactor = 1.0;
		vec3 specularColorFactor = vec3( 1.0 );
		material.specularF90 = 1.0;
	#endif
	material.specularColor = mix( min( pow2( ( material.ior - 1.0 ) / ( material.ior + 1.0 ) ) * specularColorFactor, vec3( 1.0 ) ) * specularIntensityFactor, diffuseColor.rgb, metalnessFactor );
#else
	material.specularColor = mix( vec3( 0.04 ), diffuseColor.rgb, metalnessFactor );
	material.specularF90 = 1.0;
#endif
#ifdef USE_CLEARCOAT
	material.clearcoat = clearcoat;
	material.clearcoatRoughness = clearcoatRoughness;
	material.clearcoatF0 = vec3( 0.04 );
	material.clearcoatF90 = 1.0;
	#ifdef USE_CLEARCOATMAP
		material.clearcoat *= texture2D( clearcoatMap, vClearcoatMapUv ).x;
	#endif
	#ifdef USE_CLEARCOAT_ROUGHNESSMAP
		material.clearcoatRoughness *= texture2D( clearcoatRoughnessMap, vClearcoatRoughnessMapUv ).y;
	#endif
	material.clearcoat = saturate( material.clearcoat );	material.clearcoatRoughness = max( material.clearcoatRoughness, 0.0525 );
	material.clearcoatRoughness += geometryRoughness;
	material.clearcoatRoughness = min( material.clearcoatRoughness, 1.0 );
#endif
#ifdef USE_DISPERSION
	material.dispersion = dispersion;
#endif
#ifdef USE_IRIDESCENCE
	material.iridescence = iridescence;
	material.iridescenceIOR = iridescenceIOR;
	#ifdef USE_IRIDESCENCEMAP
		material.iridescence *= texture2D( iridescenceMap, vIridescenceMapUv ).r;
	#endif
	#ifdef USE_IRIDESCENCE_THICKNESSMAP
		material.iridescenceThickness = (iridescenceThicknessMaximum - iridescenceThicknessMinimum) * texture2D( iridescenceThicknessMap, vIridescenceThicknessMapUv ).g + iridescenceThicknessMinimum;
	#else
		material.iridescenceThickness = iridescenceThicknessMaximum;
	#endif
#endif
#ifdef USE_SHEEN
	material.sheenColor = sheenColor;
	#ifdef USE_SHEEN_COLORMAP
		material.sheenColor *= texture2D( sheenColorMap, vSheenColorMapUv ).rgb;
	#endif
	material.sheenRoughness = clamp( sheenRoughness, 0.07, 1.0 );
	#ifdef USE_SHEEN_ROUGHNESSMAP
		material.sheenRoughness *= texture2D( sheenRoughnessMap, vSheenRoughnessMapUv ).a;
	#endif
#endif
#ifdef USE_ANISOTROPY
	#ifdef USE_ANISOTROPYMAP
		mat2 anisotropyMat = mat2( anisotropyVector.x, anisotropyVector.y, - anisotropyVector.y, anisotropyVector.x );
		vec3 anisotropyPolar = texture2D( anisotropyMap, vAnisotropyMapUv ).rgb;
		vec2 anisotropyV = anisotropyMat * normalize( 2.0 * anisotropyPolar.rg - vec2( 1.0 ) ) * anisotropyPolar.b;
	#else
		vec2 anisotropyV = anisotropyVector;
	#endif
	material.anisotropy = length( anisotropyV );
	if( material.anisotropy == 0.0 ) {
		anisotropyV = vec2( 1.0, 0.0 );
	} else {
		anisotropyV /= material.anisotropy;
		material.anisotropy = saturate( material.anisotropy );
	}
	material.alphaT = mix( pow2( material.roughness ), 1.0, pow2( material.anisotropy ) );
	material.anisotropyT = tbn[ 0 ] * anisotropyV.x + tbn[ 1 ] * anisotropyV.y;
	material.anisotropyB = tbn[ 1 ] * anisotropyV.x - tbn[ 0 ] * anisotropyV.y;
#endif`,yp=`struct PhysicalMaterial {
	vec3 diffuseColor;
	float roughness;
	vec3 specularColor;
	float specularF90;
	float dispersion;
	#ifdef USE_CLEARCOAT
		float clearcoat;
		float clearcoatRoughness;
		vec3 clearcoatF0;
		float clearcoatF90;
	#endif
	#ifdef USE_IRIDESCENCE
		float iridescence;
		float iridescenceIOR;
		float iridescenceThickness;
		vec3 iridescenceFresnel;
		vec3 iridescenceF0;
	#endif
	#ifdef USE_SHEEN
		vec3 sheenColor;
		float sheenRoughness;
	#endif
	#ifdef IOR
		float ior;
	#endif
	#ifdef USE_TRANSMISSION
		float transmission;
		float transmissionAlpha;
		float thickness;
		float attenuationDistance;
		vec3 attenuationColor;
	#endif
	#ifdef USE_ANISOTROPY
		float anisotropy;
		float alphaT;
		vec3 anisotropyT;
		vec3 anisotropyB;
	#endif
};
vec3 clearcoatSpecularDirect = vec3( 0.0 );
vec3 clearcoatSpecularIndirect = vec3( 0.0 );
vec3 sheenSpecularDirect = vec3( 0.0 );
vec3 sheenSpecularIndirect = vec3(0.0 );
vec3 Schlick_to_F0( const in vec3 f, const in float f90, const in float dotVH ) {
    float x = clamp( 1.0 - dotVH, 0.0, 1.0 );
    float x2 = x * x;
    float x5 = clamp( x * x2 * x2, 0.0, 0.9999 );
    return ( f - vec3( f90 ) * x5 ) / ( 1.0 - x5 );
}
float V_GGX_SmithCorrelated( const in float alpha, const in float dotNL, const in float dotNV ) {
	float a2 = pow2( alpha );
	float gv = dotNL * sqrt( a2 + ( 1.0 - a2 ) * pow2( dotNV ) );
	float gl = dotNV * sqrt( a2 + ( 1.0 - a2 ) * pow2( dotNL ) );
	return 0.5 / max( gv + gl, EPSILON );
}
float D_GGX( const in float alpha, const in float dotNH ) {
	float a2 = pow2( alpha );
	float denom = pow2( dotNH ) * ( a2 - 1.0 ) + 1.0;
	return RECIPROCAL_PI * a2 / pow2( denom );
}
#ifdef USE_ANISOTROPY
	float V_GGX_SmithCorrelated_Anisotropic( const in float alphaT, const in float alphaB, const in float dotTV, const in float dotBV, const in float dotTL, const in float dotBL, const in float dotNV, const in float dotNL ) {
		float gv = dotNL * length( vec3( alphaT * dotTV, alphaB * dotBV, dotNV ) );
		float gl = dotNV * length( vec3( alphaT * dotTL, alphaB * dotBL, dotNL ) );
		float v = 0.5 / ( gv + gl );
		return saturate(v);
	}
	float D_GGX_Anisotropic( const in float alphaT, const in float alphaB, const in float dotNH, const in float dotTH, const in float dotBH ) {
		float a2 = alphaT * alphaB;
		highp vec3 v = vec3( alphaB * dotTH, alphaT * dotBH, a2 * dotNH );
		highp float v2 = dot( v, v );
		float w2 = a2 / v2;
		return RECIPROCAL_PI * a2 * pow2 ( w2 );
	}
#endif
#ifdef USE_CLEARCOAT
	vec3 BRDF_GGX_Clearcoat( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, const in PhysicalMaterial material) {
		vec3 f0 = material.clearcoatF0;
		float f90 = material.clearcoatF90;
		float roughness = material.clearcoatRoughness;
		float alpha = pow2( roughness );
		vec3 halfDir = normalize( lightDir + viewDir );
		float dotNL = saturate( dot( normal, lightDir ) );
		float dotNV = saturate( dot( normal, viewDir ) );
		float dotNH = saturate( dot( normal, halfDir ) );
		float dotVH = saturate( dot( viewDir, halfDir ) );
		vec3 F = F_Schlick( f0, f90, dotVH );
		float V = V_GGX_SmithCorrelated( alpha, dotNL, dotNV );
		float D = D_GGX( alpha, dotNH );
		return F * ( V * D );
	}
#endif
vec3 BRDF_GGX( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, const in PhysicalMaterial material ) {
	vec3 f0 = material.specularColor;
	float f90 = material.specularF90;
	float roughness = material.roughness;
	float alpha = pow2( roughness );
	vec3 halfDir = normalize( lightDir + viewDir );
	float dotNL = saturate( dot( normal, lightDir ) );
	float dotNV = saturate( dot( normal, viewDir ) );
	float dotNH = saturate( dot( normal, halfDir ) );
	float dotVH = saturate( dot( viewDir, halfDir ) );
	vec3 F = F_Schlick( f0, f90, dotVH );
	#ifdef USE_IRIDESCENCE
		F = mix( F, material.iridescenceFresnel, material.iridescence );
	#endif
	#ifdef USE_ANISOTROPY
		float dotTL = dot( material.anisotropyT, lightDir );
		float dotTV = dot( material.anisotropyT, viewDir );
		float dotTH = dot( material.anisotropyT, halfDir );
		float dotBL = dot( material.anisotropyB, lightDir );
		float dotBV = dot( material.anisotropyB, viewDir );
		float dotBH = dot( material.anisotropyB, halfDir );
		float V = V_GGX_SmithCorrelated_Anisotropic( material.alphaT, alpha, dotTV, dotBV, dotTL, dotBL, dotNV, dotNL );
		float D = D_GGX_Anisotropic( material.alphaT, alpha, dotNH, dotTH, dotBH );
	#else
		float V = V_GGX_SmithCorrelated( alpha, dotNL, dotNV );
		float D = D_GGX( alpha, dotNH );
	#endif
	return F * ( V * D );
}
vec2 LTC_Uv( const in vec3 N, const in vec3 V, const in float roughness ) {
	const float LUT_SIZE = 64.0;
	const float LUT_SCALE = ( LUT_SIZE - 1.0 ) / LUT_SIZE;
	const float LUT_BIAS = 0.5 / LUT_SIZE;
	float dotNV = saturate( dot( N, V ) );
	vec2 uv = vec2( roughness, sqrt( 1.0 - dotNV ) );
	uv = uv * LUT_SCALE + LUT_BIAS;
	return uv;
}
float LTC_ClippedSphereFormFactor( const in vec3 f ) {
	float l = length( f );
	return max( ( l * l + f.z ) / ( l + 1.0 ), 0.0 );
}
vec3 LTC_EdgeVectorFormFactor( const in vec3 v1, const in vec3 v2 ) {
	float x = dot( v1, v2 );
	float y = abs( x );
	float a = 0.8543985 + ( 0.4965155 + 0.0145206 * y ) * y;
	float b = 3.4175940 + ( 4.1616724 + y ) * y;
	float v = a / b;
	float theta_sintheta = ( x > 0.0 ) ? v : 0.5 * inversesqrt( max( 1.0 - x * x, 1e-7 ) ) - v;
	return cross( v1, v2 ) * theta_sintheta;
}
vec3 LTC_Evaluate( const in vec3 N, const in vec3 V, const in vec3 P, const in mat3 mInv, const in vec3 rectCoords[ 4 ] ) {
	vec3 v1 = rectCoords[ 1 ] - rectCoords[ 0 ];
	vec3 v2 = rectCoords[ 3 ] - rectCoords[ 0 ];
	vec3 lightNormal = cross( v1, v2 );
	if( dot( lightNormal, P - rectCoords[ 0 ] ) < 0.0 ) return vec3( 0.0 );
	vec3 T1, T2;
	T1 = normalize( V - N * dot( V, N ) );
	T2 = - cross( N, T1 );
	mat3 mat = mInv * transposeMat3( mat3( T1, T2, N ) );
	vec3 coords[ 4 ];
	coords[ 0 ] = mat * ( rectCoords[ 0 ] - P );
	coords[ 1 ] = mat * ( rectCoords[ 1 ] - P );
	coords[ 2 ] = mat * ( rectCoords[ 2 ] - P );
	coords[ 3 ] = mat * ( rectCoords[ 3 ] - P );
	coords[ 0 ] = normalize( coords[ 0 ] );
	coords[ 1 ] = normalize( coords[ 1 ] );
	coords[ 2 ] = normalize( coords[ 2 ] );
	coords[ 3 ] = normalize( coords[ 3 ] );
	vec3 vectorFormFactor = vec3( 0.0 );
	vectorFormFactor += LTC_EdgeVectorFormFactor( coords[ 0 ], coords[ 1 ] );
	vectorFormFactor += LTC_EdgeVectorFormFactor( coords[ 1 ], coords[ 2 ] );
	vectorFormFactor += LTC_EdgeVectorFormFactor( coords[ 2 ], coords[ 3 ] );
	vectorFormFactor += LTC_EdgeVectorFormFactor( coords[ 3 ], coords[ 0 ] );
	float result = LTC_ClippedSphereFormFactor( vectorFormFactor );
	return vec3( result );
}
#if defined( USE_SHEEN )
float D_Charlie( float roughness, float dotNH ) {
	float alpha = pow2( roughness );
	float invAlpha = 1.0 / alpha;
	float cos2h = dotNH * dotNH;
	float sin2h = max( 1.0 - cos2h, 0.0078125 );
	return ( 2.0 + invAlpha ) * pow( sin2h, invAlpha * 0.5 ) / ( 2.0 * PI );
}
float V_Neubelt( float dotNV, float dotNL ) {
	return saturate( 1.0 / ( 4.0 * ( dotNL + dotNV - dotNL * dotNV ) ) );
}
vec3 BRDF_Sheen( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, vec3 sheenColor, const in float sheenRoughness ) {
	vec3 halfDir = normalize( lightDir + viewDir );
	float dotNL = saturate( dot( normal, lightDir ) );
	float dotNV = saturate( dot( normal, viewDir ) );
	float dotNH = saturate( dot( normal, halfDir ) );
	float D = D_Charlie( sheenRoughness, dotNH );
	float V = V_Neubelt( dotNV, dotNL );
	return sheenColor * ( D * V );
}
#endif
float IBLSheenBRDF( const in vec3 normal, const in vec3 viewDir, const in float roughness ) {
	float dotNV = saturate( dot( normal, viewDir ) );
	float r2 = roughness * roughness;
	float a = roughness < 0.25 ? -339.2 * r2 + 161.4 * roughness - 25.9 : -8.48 * r2 + 14.3 * roughness - 9.95;
	float b = roughness < 0.25 ? 44.0 * r2 - 23.7 * roughness + 3.26 : 1.97 * r2 - 3.27 * roughness + 0.72;
	float DG = exp( a * dotNV + b ) + ( roughness < 0.25 ? 0.0 : 0.1 * ( roughness - 0.25 ) );
	return saturate( DG * RECIPROCAL_PI );
}
vec2 DFGApprox( const in vec3 normal, const in vec3 viewDir, const in float roughness ) {
	float dotNV = saturate( dot( normal, viewDir ) );
	const vec4 c0 = vec4( - 1, - 0.0275, - 0.572, 0.022 );
	const vec4 c1 = vec4( 1, 0.0425, 1.04, - 0.04 );
	vec4 r = roughness * c0 + c1;
	float a004 = min( r.x * r.x, exp2( - 9.28 * dotNV ) ) * r.x + r.y;
	vec2 fab = vec2( - 1.04, 1.04 ) * a004 + r.zw;
	return fab;
}
vec3 EnvironmentBRDF( const in vec3 normal, const in vec3 viewDir, const in vec3 specularColor, const in float specularF90, const in float roughness ) {
	vec2 fab = DFGApprox( normal, viewDir, roughness );
	return specularColor * fab.x + specularF90 * fab.y;
}
#ifdef USE_IRIDESCENCE
void computeMultiscatteringIridescence( const in vec3 normal, const in vec3 viewDir, const in vec3 specularColor, const in float specularF90, const in float iridescence, const in vec3 iridescenceF0, const in float roughness, inout vec3 singleScatter, inout vec3 multiScatter ) {
#else
void computeMultiscattering( const in vec3 normal, const in vec3 viewDir, const in vec3 specularColor, const in float specularF90, const in float roughness, inout vec3 singleScatter, inout vec3 multiScatter ) {
#endif
	vec2 fab = DFGApprox( normal, viewDir, roughness );
	#ifdef USE_IRIDESCENCE
		vec3 Fr = mix( specularColor, iridescenceF0, iridescence );
	#else
		vec3 Fr = specularColor;
	#endif
	vec3 FssEss = Fr * fab.x + specularF90 * fab.y;
	float Ess = fab.x + fab.y;
	float Ems = 1.0 - Ess;
	vec3 Favg = Fr + ( 1.0 - Fr ) * 0.047619;	vec3 Fms = FssEss * Favg / ( 1.0 - Ems * Favg );
	singleScatter += FssEss;
	multiScatter += Fms * Ems;
}
#if NUM_RECT_AREA_LIGHTS > 0
	void RE_Direct_RectArea_Physical( const in RectAreaLight rectAreaLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {
		vec3 normal = geometryNormal;
		vec3 viewDir = geometryViewDir;
		vec3 position = geometryPosition;
		vec3 lightPos = rectAreaLight.position;
		vec3 halfWidth = rectAreaLight.halfWidth;
		vec3 halfHeight = rectAreaLight.halfHeight;
		vec3 lightColor = rectAreaLight.color;
		float roughness = material.roughness;
		vec3 rectCoords[ 4 ];
		rectCoords[ 0 ] = lightPos + halfWidth - halfHeight;		rectCoords[ 1 ] = lightPos - halfWidth - halfHeight;
		rectCoords[ 2 ] = lightPos - halfWidth + halfHeight;
		rectCoords[ 3 ] = lightPos + halfWidth + halfHeight;
		vec2 uv = LTC_Uv( normal, viewDir, roughness );
		vec4 t1 = texture2D( ltc_1, uv );
		vec4 t2 = texture2D( ltc_2, uv );
		mat3 mInv = mat3(
			vec3( t1.x, 0, t1.y ),
			vec3(    0, 1,    0 ),
			vec3( t1.z, 0, t1.w )
		);
		vec3 fresnel = ( material.specularColor * t2.x + ( vec3( 1.0 ) - material.specularColor ) * t2.y );
		reflectedLight.directSpecular += lightColor * fresnel * LTC_Evaluate( normal, viewDir, position, mInv, rectCoords );
		reflectedLight.directDiffuse += lightColor * material.diffuseColor * LTC_Evaluate( normal, viewDir, position, mat3( 1.0 ), rectCoords );
	}
#endif
void RE_Direct_Physical( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {
	float dotNL = saturate( dot( geometryNormal, directLight.direction ) );
	vec3 irradiance = dotNL * directLight.color;
	#ifdef USE_CLEARCOAT
		float dotNLcc = saturate( dot( geometryClearcoatNormal, directLight.direction ) );
		vec3 ccIrradiance = dotNLcc * directLight.color;
		clearcoatSpecularDirect += ccIrradiance * BRDF_GGX_Clearcoat( directLight.direction, geometryViewDir, geometryClearcoatNormal, material );
	#endif
	#ifdef USE_SHEEN
		sheenSpecularDirect += irradiance * BRDF_Sheen( directLight.direction, geometryViewDir, geometryNormal, material.sheenColor, material.sheenRoughness );
	#endif
	reflectedLight.directSpecular += irradiance * BRDF_GGX( directLight.direction, geometryViewDir, geometryNormal, material );
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
void RE_IndirectDiffuse_Physical( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
void RE_IndirectSpecular_Physical( const in vec3 radiance, const in vec3 irradiance, const in vec3 clearcoatRadiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight) {
	#ifdef USE_CLEARCOAT
		clearcoatSpecularIndirect += clearcoatRadiance * EnvironmentBRDF( geometryClearcoatNormal, geometryViewDir, material.clearcoatF0, material.clearcoatF90, material.clearcoatRoughness );
	#endif
	#ifdef USE_SHEEN
		sheenSpecularIndirect += irradiance * material.sheenColor * IBLSheenBRDF( geometryNormal, geometryViewDir, material.sheenRoughness );
	#endif
	vec3 singleScattering = vec3( 0.0 );
	vec3 multiScattering = vec3( 0.0 );
	vec3 cosineWeightedIrradiance = irradiance * RECIPROCAL_PI;
	#ifdef USE_IRIDESCENCE
		computeMultiscatteringIridescence( geometryNormal, geometryViewDir, material.specularColor, material.specularF90, material.iridescence, material.iridescenceFresnel, material.roughness, singleScattering, multiScattering );
	#else
		computeMultiscattering( geometryNormal, geometryViewDir, material.specularColor, material.specularF90, material.roughness, singleScattering, multiScattering );
	#endif
	vec3 totalScattering = singleScattering + multiScattering;
	vec3 diffuse = material.diffuseColor * ( 1.0 - max( max( totalScattering.r, totalScattering.g ), totalScattering.b ) );
	reflectedLight.indirectSpecular += radiance * singleScattering;
	reflectedLight.indirectSpecular += multiScattering * cosineWeightedIrradiance;
	reflectedLight.indirectDiffuse += diffuse * cosineWeightedIrradiance;
}
#define RE_Direct				RE_Direct_Physical
#define RE_Direct_RectArea		RE_Direct_RectArea_Physical
#define RE_IndirectDiffuse		RE_IndirectDiffuse_Physical
#define RE_IndirectSpecular		RE_IndirectSpecular_Physical
float computeSpecularOcclusion( const in float dotNV, const in float ambientOcclusion, const in float roughness ) {
	return saturate( pow( dotNV + ambientOcclusion, exp2( - 16.0 * roughness - 1.0 ) ) - 1.0 + ambientOcclusion );
}`,vp=`
vec3 geometryPosition = - vViewPosition;
vec3 geometryNormal = normal;
vec3 geometryViewDir = ( isOrthographic ) ? vec3( 0, 0, 1 ) : normalize( vViewPosition );
vec3 geometryClearcoatNormal = vec3( 0.0 );
#ifdef USE_CLEARCOAT
	geometryClearcoatNormal = clearcoatNormal;
#endif
#ifdef USE_IRIDESCENCE
	float dotNVi = saturate( dot( normal, geometryViewDir ) );
	if ( material.iridescenceThickness == 0.0 ) {
		material.iridescence = 0.0;
	} else {
		material.iridescence = saturate( material.iridescence );
	}
	if ( material.iridescence > 0.0 ) {
		material.iridescenceFresnel = evalIridescence( 1.0, material.iridescenceIOR, dotNVi, material.iridescenceThickness, material.specularColor );
		material.iridescenceF0 = Schlick_to_F0( material.iridescenceFresnel, 1.0, dotNVi );
	}
#endif
IncidentLight directLight;
#if ( NUM_POINT_LIGHTS > 0 ) && defined( RE_Direct )
	PointLight pointLight;
	#if defined( USE_SHADOWMAP ) && NUM_POINT_LIGHT_SHADOWS > 0
	PointLightShadow pointLightShadow;
	#endif
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_POINT_LIGHTS; i ++ ) {
		pointLight = pointLights[ i ];
		getPointLightInfo( pointLight, geometryPosition, directLight );
		#if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_POINT_LIGHT_SHADOWS )
		pointLightShadow = pointLightShadows[ i ];
		directLight.color *= ( directLight.visible && receiveShadow ) ? getPointShadow( pointShadowMap[ i ], pointLightShadow.shadowMapSize, pointLightShadow.shadowIntensity, pointLightShadow.shadowBias, pointLightShadow.shadowRadius, vPointShadowCoord[ i ], pointLightShadow.shadowCameraNear, pointLightShadow.shadowCameraFar ) : 1.0;
		#endif
		RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if ( NUM_SPOT_LIGHTS > 0 ) && defined( RE_Direct )
	SpotLight spotLight;
	vec4 spotColor;
	vec3 spotLightCoord;
	bool inSpotLightMap;
	#if defined( USE_SHADOWMAP ) && NUM_SPOT_LIGHT_SHADOWS > 0
	SpotLightShadow spotLightShadow;
	#endif
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_SPOT_LIGHTS; i ++ ) {
		spotLight = spotLights[ i ];
		getSpotLightInfo( spotLight, geometryPosition, directLight );
		#if ( UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS_WITH_MAPS )
		#define SPOT_LIGHT_MAP_INDEX UNROLLED_LOOP_INDEX
		#elif ( UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS )
		#define SPOT_LIGHT_MAP_INDEX NUM_SPOT_LIGHT_MAPS
		#else
		#define SPOT_LIGHT_MAP_INDEX ( UNROLLED_LOOP_INDEX - NUM_SPOT_LIGHT_SHADOWS + NUM_SPOT_LIGHT_SHADOWS_WITH_MAPS )
		#endif
		#if ( SPOT_LIGHT_MAP_INDEX < NUM_SPOT_LIGHT_MAPS )
			spotLightCoord = vSpotLightCoord[ i ].xyz / vSpotLightCoord[ i ].w;
			inSpotLightMap = all( lessThan( abs( spotLightCoord * 2. - 1. ), vec3( 1.0 ) ) );
			spotColor = texture2D( spotLightMap[ SPOT_LIGHT_MAP_INDEX ], spotLightCoord.xy );
			directLight.color = inSpotLightMap ? directLight.color * spotColor.rgb : directLight.color;
		#endif
		#undef SPOT_LIGHT_MAP_INDEX
		#if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS )
		spotLightShadow = spotLightShadows[ i ];
		directLight.color *= ( directLight.visible && receiveShadow ) ? getShadow( spotShadowMap[ i ], spotLightShadow.shadowMapSize, spotLightShadow.shadowIntensity, spotLightShadow.shadowBias, spotLightShadow.shadowRadius, vSpotLightCoord[ i ] ) : 1.0;
		#endif
		RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if ( NUM_DIR_LIGHTS > 0 ) && defined( RE_Direct )
	DirectionalLight directionalLight;
	#if defined( USE_SHADOWMAP ) && NUM_DIR_LIGHT_SHADOWS > 0
	DirectionalLightShadow directionalLightShadow;
	#endif
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_DIR_LIGHTS; i ++ ) {
		directionalLight = directionalLights[ i ];
		getDirectionalLightInfo( directionalLight, directLight );
		#if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_DIR_LIGHT_SHADOWS )
		directionalLightShadow = directionalLightShadows[ i ];
		directLight.color *= ( directLight.visible && receiveShadow ) ? getShadow( directionalShadowMap[ i ], directionalLightShadow.shadowMapSize, directionalLightShadow.shadowIntensity, directionalLightShadow.shadowBias, directionalLightShadow.shadowRadius, vDirectionalShadowCoord[ i ] ) : 1.0;
		#endif
		RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if ( NUM_RECT_AREA_LIGHTS > 0 ) && defined( RE_Direct_RectArea )
	RectAreaLight rectAreaLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_RECT_AREA_LIGHTS; i ++ ) {
		rectAreaLight = rectAreaLights[ i ];
		RE_Direct_RectArea( rectAreaLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if defined( RE_IndirectDiffuse )
	vec3 iblIrradiance = vec3( 0.0 );
	vec3 irradiance = getAmbientLightIrradiance( ambientLightColor );
	#if defined( USE_LIGHT_PROBES )
		irradiance += getLightProbeIrradiance( lightProbe, geometryNormal );
	#endif
	#if ( NUM_HEMI_LIGHTS > 0 )
		#pragma unroll_loop_start
		for ( int i = 0; i < NUM_HEMI_LIGHTS; i ++ ) {
			irradiance += getHemisphereLightIrradiance( hemisphereLights[ i ], geometryNormal );
		}
		#pragma unroll_loop_end
	#endif
#endif
#if defined( RE_IndirectSpecular )
	vec3 radiance = vec3( 0.0 );
	vec3 clearcoatRadiance = vec3( 0.0 );
#endif`,Mp=`#if defined( RE_IndirectDiffuse )
	#ifdef USE_LIGHTMAP
		vec4 lightMapTexel = texture2D( lightMap, vLightMapUv );
		vec3 lightMapIrradiance = lightMapTexel.rgb * lightMapIntensity;
		irradiance += lightMapIrradiance;
	#endif
	#if defined( USE_ENVMAP ) && defined( STANDARD ) && defined( ENVMAP_TYPE_CUBE_UV )
		iblIrradiance += getIBLIrradiance( geometryNormal );
	#endif
#endif
#if defined( USE_ENVMAP ) && defined( RE_IndirectSpecular )
	#ifdef USE_ANISOTROPY
		radiance += getIBLAnisotropyRadiance( geometryViewDir, geometryNormal, material.roughness, material.anisotropyB, material.anisotropy );
	#else
		radiance += getIBLRadiance( geometryViewDir, geometryNormal, material.roughness );
	#endif
	#ifdef USE_CLEARCOAT
		clearcoatRadiance += getIBLRadiance( geometryViewDir, geometryClearcoatNormal, material.clearcoatRoughness );
	#endif
#endif`,Sp=`#if defined( RE_IndirectDiffuse )
	RE_IndirectDiffuse( irradiance, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
#endif
#if defined( RE_IndirectSpecular )
	RE_IndirectSpecular( radiance, iblIrradiance, clearcoatRadiance, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
#endif`,bp=`#if defined( USE_LOGDEPTHBUF )
	gl_FragDepth = vIsPerspective == 0.0 ? gl_FragCoord.z : log2( vFragDepth ) * logDepthBufFC * 0.5;
#endif`,wp=`#if defined( USE_LOGDEPTHBUF )
	uniform float logDepthBufFC;
	varying float vFragDepth;
	varying float vIsPerspective;
#endif`,Ep=`#ifdef USE_LOGDEPTHBUF
	varying float vFragDepth;
	varying float vIsPerspective;
#endif`,Ap=`#ifdef USE_LOGDEPTHBUF
	vFragDepth = 1.0 + gl_Position.w;
	vIsPerspective = float( isPerspectiveMatrix( projectionMatrix ) );
#endif`,Tp=`#ifdef USE_MAP
	vec4 sampledDiffuseColor = texture2D( map, vMapUv );
	#ifdef DECODE_VIDEO_TEXTURE
		sampledDiffuseColor = sRGBTransferEOTF( sampledDiffuseColor );
	#endif
	diffuseColor *= sampledDiffuseColor;
#endif`,Rp=`#ifdef USE_MAP
	uniform sampler2D map;
#endif`,Cp=`#if defined( USE_MAP ) || defined( USE_ALPHAMAP )
	#if defined( USE_POINTS_UV )
		vec2 uv = vUv;
	#else
		vec2 uv = ( uvTransform * vec3( gl_PointCoord.x, 1.0 - gl_PointCoord.y, 1 ) ).xy;
	#endif
#endif
#ifdef USE_MAP
	diffuseColor *= texture2D( map, uv );
#endif
#ifdef USE_ALPHAMAP
	diffuseColor.a *= texture2D( alphaMap, uv ).g;
#endif`,Ip=`#if defined( USE_POINTS_UV )
	varying vec2 vUv;
#else
	#if defined( USE_MAP ) || defined( USE_ALPHAMAP )
		uniform mat3 uvTransform;
	#endif
#endif
#ifdef USE_MAP
	uniform sampler2D map;
#endif
#ifdef USE_ALPHAMAP
	uniform sampler2D alphaMap;
#endif`,Pp=`float metalnessFactor = metalness;
#ifdef USE_METALNESSMAP
	vec4 texelMetalness = texture2D( metalnessMap, vMetalnessMapUv );
	metalnessFactor *= texelMetalness.b;
#endif`,Lp=`#ifdef USE_METALNESSMAP
	uniform sampler2D metalnessMap;
#endif`,Dp=`#ifdef USE_INSTANCING_MORPH
	float morphTargetInfluences[ MORPHTARGETS_COUNT ];
	float morphTargetBaseInfluence = texelFetch( morphTexture, ivec2( 0, gl_InstanceID ), 0 ).r;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		morphTargetInfluences[i] =  texelFetch( morphTexture, ivec2( i + 1, gl_InstanceID ), 0 ).r;
	}
#endif`,Up=`#if defined( USE_MORPHCOLORS )
	vColor *= morphTargetBaseInfluence;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		#if defined( USE_COLOR_ALPHA )
			if ( morphTargetInfluences[ i ] != 0.0 ) vColor += getMorph( gl_VertexID, i, 2 ) * morphTargetInfluences[ i ];
		#elif defined( USE_COLOR )
			if ( morphTargetInfluences[ i ] != 0.0 ) vColor += getMorph( gl_VertexID, i, 2 ).rgb * morphTargetInfluences[ i ];
		#endif
	}
#endif`,Np=`#ifdef USE_MORPHNORMALS
	objectNormal *= morphTargetBaseInfluence;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		if ( morphTargetInfluences[ i ] != 0.0 ) objectNormal += getMorph( gl_VertexID, i, 1 ).xyz * morphTargetInfluences[ i ];
	}
#endif`,Op=`#ifdef USE_MORPHTARGETS
	#ifndef USE_INSTANCING_MORPH
		uniform float morphTargetBaseInfluence;
		uniform float morphTargetInfluences[ MORPHTARGETS_COUNT ];
	#endif
	uniform sampler2DArray morphTargetsTexture;
	uniform ivec2 morphTargetsTextureSize;
	vec4 getMorph( const in int vertexIndex, const in int morphTargetIndex, const in int offset ) {
		int texelIndex = vertexIndex * MORPHTARGETS_TEXTURE_STRIDE + offset;
		int y = texelIndex / morphTargetsTextureSize.x;
		int x = texelIndex - y * morphTargetsTextureSize.x;
		ivec3 morphUV = ivec3( x, y, morphTargetIndex );
		return texelFetch( morphTargetsTexture, morphUV, 0 );
	}
#endif`,Fp=`#ifdef USE_MORPHTARGETS
	transformed *= morphTargetBaseInfluence;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		if ( morphTargetInfluences[ i ] != 0.0 ) transformed += getMorph( gl_VertexID, i, 0 ).xyz * morphTargetInfluences[ i ];
	}
#endif`,Bp=`float faceDirection = gl_FrontFacing ? 1.0 : - 1.0;
#ifdef FLAT_SHADED
	vec3 fdx = dFdx( vViewPosition );
	vec3 fdy = dFdy( vViewPosition );
	vec3 normal = normalize( cross( fdx, fdy ) );
#else
	vec3 normal = normalize( vNormal );
	#ifdef DOUBLE_SIDED
		normal *= faceDirection;
	#endif
#endif
#if defined( USE_NORMALMAP_TANGENTSPACE ) || defined( USE_CLEARCOAT_NORMALMAP ) || defined( USE_ANISOTROPY )
	#ifdef USE_TANGENT
		mat3 tbn = mat3( normalize( vTangent ), normalize( vBitangent ), normal );
	#else
		mat3 tbn = getTangentFrame( - vViewPosition, normal,
		#if defined( USE_NORMALMAP )
			vNormalMapUv
		#elif defined( USE_CLEARCOAT_NORMALMAP )
			vClearcoatNormalMapUv
		#else
			vUv
		#endif
		);
	#endif
	#if defined( DOUBLE_SIDED ) && ! defined( FLAT_SHADED )
		tbn[0] *= faceDirection;
		tbn[1] *= faceDirection;
	#endif
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	#ifdef USE_TANGENT
		mat3 tbn2 = mat3( normalize( vTangent ), normalize( vBitangent ), normal );
	#else
		mat3 tbn2 = getTangentFrame( - vViewPosition, normal, vClearcoatNormalMapUv );
	#endif
	#if defined( DOUBLE_SIDED ) && ! defined( FLAT_SHADED )
		tbn2[0] *= faceDirection;
		tbn2[1] *= faceDirection;
	#endif
#endif
vec3 nonPerturbedNormal = normal;`,zp=`#ifdef USE_NORMALMAP_OBJECTSPACE
	normal = texture2D( normalMap, vNormalMapUv ).xyz * 2.0 - 1.0;
	#ifdef FLIP_SIDED
		normal = - normal;
	#endif
	#ifdef DOUBLE_SIDED
		normal = normal * faceDirection;
	#endif
	normal = normalize( normalMatrix * normal );
#elif defined( USE_NORMALMAP_TANGENTSPACE )
	vec3 mapN = texture2D( normalMap, vNormalMapUv ).xyz * 2.0 - 1.0;
	mapN.xy *= normalScale;
	normal = normalize( tbn * mapN );
#elif defined( USE_BUMPMAP )
	normal = perturbNormalArb( - vViewPosition, normal, dHdxy_fwd(), faceDirection );
#endif`,kp=`#ifndef FLAT_SHADED
	varying vec3 vNormal;
	#ifdef USE_TANGENT
		varying vec3 vTangent;
		varying vec3 vBitangent;
	#endif
#endif`,Hp=`#ifndef FLAT_SHADED
	varying vec3 vNormal;
	#ifdef USE_TANGENT
		varying vec3 vTangent;
		varying vec3 vBitangent;
	#endif
#endif`,Vp=`#ifndef FLAT_SHADED
	vNormal = normalize( transformedNormal );
	#ifdef USE_TANGENT
		vTangent = normalize( transformedTangent );
		vBitangent = normalize( cross( vNormal, vTangent ) * tangent.w );
	#endif
#endif`,Gp=`#ifdef USE_NORMALMAP
	uniform sampler2D normalMap;
	uniform vec2 normalScale;
#endif
#ifdef USE_NORMALMAP_OBJECTSPACE
	uniform mat3 normalMatrix;
#endif
#if ! defined ( USE_TANGENT ) && ( defined ( USE_NORMALMAP_TANGENTSPACE ) || defined ( USE_CLEARCOAT_NORMALMAP ) || defined( USE_ANISOTROPY ) )
	mat3 getTangentFrame( vec3 eye_pos, vec3 surf_norm, vec2 uv ) {
		vec3 q0 = dFdx( eye_pos.xyz );
		vec3 q1 = dFdy( eye_pos.xyz );
		vec2 st0 = dFdx( uv.st );
		vec2 st1 = dFdy( uv.st );
		vec3 N = surf_norm;
		vec3 q1perp = cross( q1, N );
		vec3 q0perp = cross( N, q0 );
		vec3 T = q1perp * st0.x + q0perp * st1.x;
		vec3 B = q1perp * st0.y + q0perp * st1.y;
		float det = max( dot( T, T ), dot( B, B ) );
		float scale = ( det == 0.0 ) ? 0.0 : inversesqrt( det );
		return mat3( T * scale, B * scale, N );
	}
#endif`,Wp=`#ifdef USE_CLEARCOAT
	vec3 clearcoatNormal = nonPerturbedNormal;
#endif`,Xp=`#ifdef USE_CLEARCOAT_NORMALMAP
	vec3 clearcoatMapN = texture2D( clearcoatNormalMap, vClearcoatNormalMapUv ).xyz * 2.0 - 1.0;
	clearcoatMapN.xy *= clearcoatNormalScale;
	clearcoatNormal = normalize( tbn2 * clearcoatMapN );
#endif`,qp=`#ifdef USE_CLEARCOATMAP
	uniform sampler2D clearcoatMap;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	uniform sampler2D clearcoatNormalMap;
	uniform vec2 clearcoatNormalScale;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	uniform sampler2D clearcoatRoughnessMap;
#endif`,Yp=`#ifdef USE_IRIDESCENCEMAP
	uniform sampler2D iridescenceMap;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	uniform sampler2D iridescenceThicknessMap;
#endif`,Zp=`#ifdef OPAQUE
diffuseColor.a = 1.0;
#endif
#ifdef USE_TRANSMISSION
diffuseColor.a *= material.transmissionAlpha;
#endif
gl_FragColor = vec4( outgoingLight, diffuseColor.a );`,Kp=`vec3 packNormalToRGB( const in vec3 normal ) {
	return normalize( normal ) * 0.5 + 0.5;
}
vec3 unpackRGBToNormal( const in vec3 rgb ) {
	return 2.0 * rgb.xyz - 1.0;
}
const float PackUpscale = 256. / 255.;const float UnpackDownscale = 255. / 256.;const float ShiftRight8 = 1. / 256.;
const float Inv255 = 1. / 255.;
const vec4 PackFactors = vec4( 1.0, 256.0, 256.0 * 256.0, 256.0 * 256.0 * 256.0 );
const vec2 UnpackFactors2 = vec2( UnpackDownscale, 1.0 / PackFactors.g );
const vec3 UnpackFactors3 = vec3( UnpackDownscale / PackFactors.rg, 1.0 / PackFactors.b );
const vec4 UnpackFactors4 = vec4( UnpackDownscale / PackFactors.rgb, 1.0 / PackFactors.a );
vec4 packDepthToRGBA( const in float v ) {
	if( v <= 0.0 )
		return vec4( 0., 0., 0., 0. );
	if( v >= 1.0 )
		return vec4( 1., 1., 1., 1. );
	float vuf;
	float af = modf( v * PackFactors.a, vuf );
	float bf = modf( vuf * ShiftRight8, vuf );
	float gf = modf( vuf * ShiftRight8, vuf );
	return vec4( vuf * Inv255, gf * PackUpscale, bf * PackUpscale, af );
}
vec3 packDepthToRGB( const in float v ) {
	if( v <= 0.0 )
		return vec3( 0., 0., 0. );
	if( v >= 1.0 )
		return vec3( 1., 1., 1. );
	float vuf;
	float bf = modf( v * PackFactors.b, vuf );
	float gf = modf( vuf * ShiftRight8, vuf );
	return vec3( vuf * Inv255, gf * PackUpscale, bf );
}
vec2 packDepthToRG( const in float v ) {
	if( v <= 0.0 )
		return vec2( 0., 0. );
	if( v >= 1.0 )
		return vec2( 1., 1. );
	float vuf;
	float gf = modf( v * 256., vuf );
	return vec2( vuf * Inv255, gf );
}
float unpackRGBAToDepth( const in vec4 v ) {
	return dot( v, UnpackFactors4 );
}
float unpackRGBToDepth( const in vec3 v ) {
	return dot( v, UnpackFactors3 );
}
float unpackRGToDepth( const in vec2 v ) {
	return v.r * UnpackFactors2.r + v.g * UnpackFactors2.g;
}
vec4 pack2HalfToRGBA( const in vec2 v ) {
	vec4 r = vec4( v.x, fract( v.x * 255.0 ), v.y, fract( v.y * 255.0 ) );
	return vec4( r.x - r.y / 255.0, r.y, r.z - r.w / 255.0, r.w );
}
vec2 unpackRGBATo2Half( const in vec4 v ) {
	return vec2( v.x + ( v.y / 255.0 ), v.z + ( v.w / 255.0 ) );
}
float viewZToOrthographicDepth( const in float viewZ, const in float near, const in float far ) {
	return ( viewZ + near ) / ( near - far );
}
float orthographicDepthToViewZ( const in float depth, const in float near, const in float far ) {
	return depth * ( near - far ) - near;
}
float viewZToPerspectiveDepth( const in float viewZ, const in float near, const in float far ) {
	return ( ( near + viewZ ) * far ) / ( ( far - near ) * viewZ );
}
float perspectiveDepthToViewZ( const in float depth, const in float near, const in float far ) {
	return ( near * far ) / ( ( far - near ) * depth - far );
}`,Jp=`#ifdef PREMULTIPLIED_ALPHA
	gl_FragColor.rgb *= gl_FragColor.a;
#endif`,jp=`vec4 mvPosition = vec4( transformed, 1.0 );
#ifdef USE_BATCHING
	mvPosition = batchingMatrix * mvPosition;
#endif
#ifdef USE_INSTANCING
	mvPosition = instanceMatrix * mvPosition;
#endif
mvPosition = modelViewMatrix * mvPosition;
gl_Position = projectionMatrix * mvPosition;`,$p=`#ifdef DITHERING
	gl_FragColor.rgb = dithering( gl_FragColor.rgb );
#endif`,Qp=`#ifdef DITHERING
	vec3 dithering( vec3 color ) {
		float grid_position = rand( gl_FragCoord.xy );
		vec3 dither_shift_RGB = vec3( 0.25 / 255.0, -0.25 / 255.0, 0.25 / 255.0 );
		dither_shift_RGB = mix( 2.0 * dither_shift_RGB, -2.0 * dither_shift_RGB, grid_position );
		return color + dither_shift_RGB;
	}
#endif`,em=`float roughnessFactor = roughness;
#ifdef USE_ROUGHNESSMAP
	vec4 texelRoughness = texture2D( roughnessMap, vRoughnessMapUv );
	roughnessFactor *= texelRoughness.g;
#endif`,tm=`#ifdef USE_ROUGHNESSMAP
	uniform sampler2D roughnessMap;
#endif`,nm=`#if NUM_SPOT_LIGHT_COORDS > 0
	varying vec4 vSpotLightCoord[ NUM_SPOT_LIGHT_COORDS ];
#endif
#if NUM_SPOT_LIGHT_MAPS > 0
	uniform sampler2D spotLightMap[ NUM_SPOT_LIGHT_MAPS ];
#endif
#ifdef USE_SHADOWMAP
	#if NUM_DIR_LIGHT_SHADOWS > 0
		uniform sampler2D directionalShadowMap[ NUM_DIR_LIGHT_SHADOWS ];
		varying vec4 vDirectionalShadowCoord[ NUM_DIR_LIGHT_SHADOWS ];
		struct DirectionalLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform DirectionalLightShadow directionalLightShadows[ NUM_DIR_LIGHT_SHADOWS ];
	#endif
	#if NUM_SPOT_LIGHT_SHADOWS > 0
		uniform sampler2D spotShadowMap[ NUM_SPOT_LIGHT_SHADOWS ];
		struct SpotLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform SpotLightShadow spotLightShadows[ NUM_SPOT_LIGHT_SHADOWS ];
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0
		uniform sampler2D pointShadowMap[ NUM_POINT_LIGHT_SHADOWS ];
		varying vec4 vPointShadowCoord[ NUM_POINT_LIGHT_SHADOWS ];
		struct PointLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
			float shadowCameraNear;
			float shadowCameraFar;
		};
		uniform PointLightShadow pointLightShadows[ NUM_POINT_LIGHT_SHADOWS ];
	#endif
	float texture2DCompare( sampler2D depths, vec2 uv, float compare ) {
		return step( compare, unpackRGBAToDepth( texture2D( depths, uv ) ) );
	}
	vec2 texture2DDistribution( sampler2D shadow, vec2 uv ) {
		return unpackRGBATo2Half( texture2D( shadow, uv ) );
	}
	float VSMShadow (sampler2D shadow, vec2 uv, float compare ){
		float occlusion = 1.0;
		vec2 distribution = texture2DDistribution( shadow, uv );
		float hard_shadow = step( compare , distribution.x );
		if (hard_shadow != 1.0 ) {
			float distance = compare - distribution.x ;
			float variance = max( 0.00000, distribution.y * distribution.y );
			float softness_probability = variance / (variance + distance * distance );			softness_probability = clamp( ( softness_probability - 0.3 ) / ( 0.95 - 0.3 ), 0.0, 1.0 );			occlusion = clamp( max( hard_shadow, softness_probability ), 0.0, 1.0 );
		}
		return occlusion;
	}
	float getShadow( sampler2D shadowMap, vec2 shadowMapSize, float shadowIntensity, float shadowBias, float shadowRadius, vec4 shadowCoord ) {
		float shadow = 1.0;
		shadowCoord.xyz /= shadowCoord.w;
		shadowCoord.z += shadowBias;
		bool inFrustum = shadowCoord.x >= 0.0 && shadowCoord.x <= 1.0 && shadowCoord.y >= 0.0 && shadowCoord.y <= 1.0;
		bool frustumTest = inFrustum && shadowCoord.z <= 1.0;
		if ( frustumTest ) {
		#if defined( SHADOWMAP_TYPE_PCF )
			vec2 texelSize = vec2( 1.0 ) / shadowMapSize;
			float dx0 = - texelSize.x * shadowRadius;
			float dy0 = - texelSize.y * shadowRadius;
			float dx1 = + texelSize.x * shadowRadius;
			float dy1 = + texelSize.y * shadowRadius;
			float dx2 = dx0 / 2.0;
			float dy2 = dy0 / 2.0;
			float dx3 = dx1 / 2.0;
			float dy3 = dy1 / 2.0;
			shadow = (
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx0, dy0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( 0.0, dy0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx1, dy0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx2, dy2 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( 0.0, dy2 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx3, dy2 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx0, 0.0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx2, 0.0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy, shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx3, 0.0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx1, 0.0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx2, dy3 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( 0.0, dy3 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx3, dy3 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx0, dy1 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( 0.0, dy1 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx1, dy1 ), shadowCoord.z )
			) * ( 1.0 / 17.0 );
		#elif defined( SHADOWMAP_TYPE_PCF_SOFT )
			vec2 texelSize = vec2( 1.0 ) / shadowMapSize;
			float dx = texelSize.x;
			float dy = texelSize.y;
			vec2 uv = shadowCoord.xy;
			vec2 f = fract( uv * shadowMapSize + 0.5 );
			uv -= f * texelSize;
			shadow = (
				texture2DCompare( shadowMap, uv, shadowCoord.z ) +
				texture2DCompare( shadowMap, uv + vec2( dx, 0.0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, uv + vec2( 0.0, dy ), shadowCoord.z ) +
				texture2DCompare( shadowMap, uv + texelSize, shadowCoord.z ) +
				mix( texture2DCompare( shadowMap, uv + vec2( -dx, 0.0 ), shadowCoord.z ),
					 texture2DCompare( shadowMap, uv + vec2( 2.0 * dx, 0.0 ), shadowCoord.z ),
					 f.x ) +
				mix( texture2DCompare( shadowMap, uv + vec2( -dx, dy ), shadowCoord.z ),
					 texture2DCompare( shadowMap, uv + vec2( 2.0 * dx, dy ), shadowCoord.z ),
					 f.x ) +
				mix( texture2DCompare( shadowMap, uv + vec2( 0.0, -dy ), shadowCoord.z ),
					 texture2DCompare( shadowMap, uv + vec2( 0.0, 2.0 * dy ), shadowCoord.z ),
					 f.y ) +
				mix( texture2DCompare( shadowMap, uv + vec2( dx, -dy ), shadowCoord.z ),
					 texture2DCompare( shadowMap, uv + vec2( dx, 2.0 * dy ), shadowCoord.z ),
					 f.y ) +
				mix( mix( texture2DCompare( shadowMap, uv + vec2( -dx, -dy ), shadowCoord.z ),
						  texture2DCompare( shadowMap, uv + vec2( 2.0 * dx, -dy ), shadowCoord.z ),
						  f.x ),
					 mix( texture2DCompare( shadowMap, uv + vec2( -dx, 2.0 * dy ), shadowCoord.z ),
						  texture2DCompare( shadowMap, uv + vec2( 2.0 * dx, 2.0 * dy ), shadowCoord.z ),
						  f.x ),
					 f.y )
			) * ( 1.0 / 9.0 );
		#elif defined( SHADOWMAP_TYPE_VSM )
			shadow = VSMShadow( shadowMap, shadowCoord.xy, shadowCoord.z );
		#else
			shadow = texture2DCompare( shadowMap, shadowCoord.xy, shadowCoord.z );
		#endif
		}
		return mix( 1.0, shadow, shadowIntensity );
	}
	vec2 cubeToUV( vec3 v, float texelSizeY ) {
		vec3 absV = abs( v );
		float scaleToCube = 1.0 / max( absV.x, max( absV.y, absV.z ) );
		absV *= scaleToCube;
		v *= scaleToCube * ( 1.0 - 2.0 * texelSizeY );
		vec2 planar = v.xy;
		float almostATexel = 1.5 * texelSizeY;
		float almostOne = 1.0 - almostATexel;
		if ( absV.z >= almostOne ) {
			if ( v.z > 0.0 )
				planar.x = 4.0 - v.x;
		} else if ( absV.x >= almostOne ) {
			float signX = sign( v.x );
			planar.x = v.z * signX + 2.0 * signX;
		} else if ( absV.y >= almostOne ) {
			float signY = sign( v.y );
			planar.x = v.x + 2.0 * signY + 2.0;
			planar.y = v.z * signY - 2.0;
		}
		return vec2( 0.125, 0.25 ) * planar + vec2( 0.375, 0.75 );
	}
	float getPointShadow( sampler2D shadowMap, vec2 shadowMapSize, float shadowIntensity, float shadowBias, float shadowRadius, vec4 shadowCoord, float shadowCameraNear, float shadowCameraFar ) {
		float shadow = 1.0;
		vec3 lightToPosition = shadowCoord.xyz;
		
		float lightToPositionLength = length( lightToPosition );
		if ( lightToPositionLength - shadowCameraFar <= 0.0 && lightToPositionLength - shadowCameraNear >= 0.0 ) {
			float dp = ( lightToPositionLength - shadowCameraNear ) / ( shadowCameraFar - shadowCameraNear );			dp += shadowBias;
			vec3 bd3D = normalize( lightToPosition );
			vec2 texelSize = vec2( 1.0 ) / ( shadowMapSize * vec2( 4.0, 2.0 ) );
			#if defined( SHADOWMAP_TYPE_PCF ) || defined( SHADOWMAP_TYPE_PCF_SOFT ) || defined( SHADOWMAP_TYPE_VSM )
				vec2 offset = vec2( - 1, 1 ) * shadowRadius * texelSize.y;
				shadow = (
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.xyy, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.yyy, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.xyx, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.yyx, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.xxy, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.yxy, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.xxx, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.yxx, texelSize.y ), dp )
				) * ( 1.0 / 9.0 );
			#else
				shadow = texture2DCompare( shadowMap, cubeToUV( bd3D, texelSize.y ), dp );
			#endif
		}
		return mix( 1.0, shadow, shadowIntensity );
	}
#endif`,im=`#if NUM_SPOT_LIGHT_COORDS > 0
	uniform mat4 spotLightMatrix[ NUM_SPOT_LIGHT_COORDS ];
	varying vec4 vSpotLightCoord[ NUM_SPOT_LIGHT_COORDS ];
#endif
#ifdef USE_SHADOWMAP
	#if NUM_DIR_LIGHT_SHADOWS > 0
		uniform mat4 directionalShadowMatrix[ NUM_DIR_LIGHT_SHADOWS ];
		varying vec4 vDirectionalShadowCoord[ NUM_DIR_LIGHT_SHADOWS ];
		struct DirectionalLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform DirectionalLightShadow directionalLightShadows[ NUM_DIR_LIGHT_SHADOWS ];
	#endif
	#if NUM_SPOT_LIGHT_SHADOWS > 0
		struct SpotLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform SpotLightShadow spotLightShadows[ NUM_SPOT_LIGHT_SHADOWS ];
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0
		uniform mat4 pointShadowMatrix[ NUM_POINT_LIGHT_SHADOWS ];
		varying vec4 vPointShadowCoord[ NUM_POINT_LIGHT_SHADOWS ];
		struct PointLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
			float shadowCameraNear;
			float shadowCameraFar;
		};
		uniform PointLightShadow pointLightShadows[ NUM_POINT_LIGHT_SHADOWS ];
	#endif
#endif`,sm=`#if ( defined( USE_SHADOWMAP ) && ( NUM_DIR_LIGHT_SHADOWS > 0 || NUM_POINT_LIGHT_SHADOWS > 0 ) ) || ( NUM_SPOT_LIGHT_COORDS > 0 )
	vec3 shadowWorldNormal = inverseTransformDirection( transformedNormal, viewMatrix );
	vec4 shadowWorldPosition;
#endif
#if defined( USE_SHADOWMAP )
	#if NUM_DIR_LIGHT_SHADOWS > 0
		#pragma unroll_loop_start
		for ( int i = 0; i < NUM_DIR_LIGHT_SHADOWS; i ++ ) {
			shadowWorldPosition = worldPosition + vec4( shadowWorldNormal * directionalLightShadows[ i ].shadowNormalBias, 0 );
			vDirectionalShadowCoord[ i ] = directionalShadowMatrix[ i ] * shadowWorldPosition;
		}
		#pragma unroll_loop_end
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0
		#pragma unroll_loop_start
		for ( int i = 0; i < NUM_POINT_LIGHT_SHADOWS; i ++ ) {
			shadowWorldPosition = worldPosition + vec4( shadowWorldNormal * pointLightShadows[ i ].shadowNormalBias, 0 );
			vPointShadowCoord[ i ] = pointShadowMatrix[ i ] * shadowWorldPosition;
		}
		#pragma unroll_loop_end
	#endif
#endif
#if NUM_SPOT_LIGHT_COORDS > 0
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_SPOT_LIGHT_COORDS; i ++ ) {
		shadowWorldPosition = worldPosition;
		#if ( defined( USE_SHADOWMAP ) && UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS )
			shadowWorldPosition.xyz += shadowWorldNormal * spotLightShadows[ i ].shadowNormalBias;
		#endif
		vSpotLightCoord[ i ] = spotLightMatrix[ i ] * shadowWorldPosition;
	}
	#pragma unroll_loop_end
#endif`,rm=`float getShadowMask() {
	float shadow = 1.0;
	#ifdef USE_SHADOWMAP
	#if NUM_DIR_LIGHT_SHADOWS > 0
	DirectionalLightShadow directionalLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_DIR_LIGHT_SHADOWS; i ++ ) {
		directionalLight = directionalLightShadows[ i ];
		shadow *= receiveShadow ? getShadow( directionalShadowMap[ i ], directionalLight.shadowMapSize, directionalLight.shadowIntensity, directionalLight.shadowBias, directionalLight.shadowRadius, vDirectionalShadowCoord[ i ] ) : 1.0;
	}
	#pragma unroll_loop_end
	#endif
	#if NUM_SPOT_LIGHT_SHADOWS > 0
	SpotLightShadow spotLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_SPOT_LIGHT_SHADOWS; i ++ ) {
		spotLight = spotLightShadows[ i ];
		shadow *= receiveShadow ? getShadow( spotShadowMap[ i ], spotLight.shadowMapSize, spotLight.shadowIntensity, spotLight.shadowBias, spotLight.shadowRadius, vSpotLightCoord[ i ] ) : 1.0;
	}
	#pragma unroll_loop_end
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0
	PointLightShadow pointLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_POINT_LIGHT_SHADOWS; i ++ ) {
		pointLight = pointLightShadows[ i ];
		shadow *= receiveShadow ? getPointShadow( pointShadowMap[ i ], pointLight.shadowMapSize, pointLight.shadowIntensity, pointLight.shadowBias, pointLight.shadowRadius, vPointShadowCoord[ i ], pointLight.shadowCameraNear, pointLight.shadowCameraFar ) : 1.0;
	}
	#pragma unroll_loop_end
	#endif
	#endif
	return shadow;
}`,om=`#ifdef USE_SKINNING
	mat4 boneMatX = getBoneMatrix( skinIndex.x );
	mat4 boneMatY = getBoneMatrix( skinIndex.y );
	mat4 boneMatZ = getBoneMatrix( skinIndex.z );
	mat4 boneMatW = getBoneMatrix( skinIndex.w );
#endif`,am=`#ifdef USE_SKINNING
	uniform mat4 bindMatrix;
	uniform mat4 bindMatrixInverse;
	uniform highp sampler2D boneTexture;
	mat4 getBoneMatrix( const in float i ) {
		int size = textureSize( boneTexture, 0 ).x;
		int j = int( i ) * 4;
		int x = j % size;
		int y = j / size;
		vec4 v1 = texelFetch( boneTexture, ivec2( x, y ), 0 );
		vec4 v2 = texelFetch( boneTexture, ivec2( x + 1, y ), 0 );
		vec4 v3 = texelFetch( boneTexture, ivec2( x + 2, y ), 0 );
		vec4 v4 = texelFetch( boneTexture, ivec2( x + 3, y ), 0 );
		return mat4( v1, v2, v3, v4 );
	}
#endif`,lm=`#ifdef USE_SKINNING
	vec4 skinVertex = bindMatrix * vec4( transformed, 1.0 );
	vec4 skinned = vec4( 0.0 );
	skinned += boneMatX * skinVertex * skinWeight.x;
	skinned += boneMatY * skinVertex * skinWeight.y;
	skinned += boneMatZ * skinVertex * skinWeight.z;
	skinned += boneMatW * skinVertex * skinWeight.w;
	transformed = ( bindMatrixInverse * skinned ).xyz;
#endif`,cm=`#ifdef USE_SKINNING
	mat4 skinMatrix = mat4( 0.0 );
	skinMatrix += skinWeight.x * boneMatX;
	skinMatrix += skinWeight.y * boneMatY;
	skinMatrix += skinWeight.z * boneMatZ;
	skinMatrix += skinWeight.w * boneMatW;
	skinMatrix = bindMatrixInverse * skinMatrix * bindMatrix;
	objectNormal = vec4( skinMatrix * vec4( objectNormal, 0.0 ) ).xyz;
	#ifdef USE_TANGENT
		objectTangent = vec4( skinMatrix * vec4( objectTangent, 0.0 ) ).xyz;
	#endif
#endif`,hm=`float specularStrength;
#ifdef USE_SPECULARMAP
	vec4 texelSpecular = texture2D( specularMap, vSpecularMapUv );
	specularStrength = texelSpecular.r;
#else
	specularStrength = 1.0;
#endif`,um=`#ifdef USE_SPECULARMAP
	uniform sampler2D specularMap;
#endif`,dm=`#if defined( TONE_MAPPING )
	gl_FragColor.rgb = toneMapping( gl_FragColor.rgb );
#endif`,fm=`#ifndef saturate
#define saturate( a ) clamp( a, 0.0, 1.0 )
#endif
uniform float toneMappingExposure;
vec3 LinearToneMapping( vec3 color ) {
	return saturate( toneMappingExposure * color );
}
vec3 ReinhardToneMapping( vec3 color ) {
	color *= toneMappingExposure;
	return saturate( color / ( vec3( 1.0 ) + color ) );
}
vec3 CineonToneMapping( vec3 color ) {
	color *= toneMappingExposure;
	color = max( vec3( 0.0 ), color - 0.004 );
	return pow( ( color * ( 6.2 * color + 0.5 ) ) / ( color * ( 6.2 * color + 1.7 ) + 0.06 ), vec3( 2.2 ) );
}
vec3 RRTAndODTFit( vec3 v ) {
	vec3 a = v * ( v + 0.0245786 ) - 0.000090537;
	vec3 b = v * ( 0.983729 * v + 0.4329510 ) + 0.238081;
	return a / b;
}
vec3 ACESFilmicToneMapping( vec3 color ) {
	const mat3 ACESInputMat = mat3(
		vec3( 0.59719, 0.07600, 0.02840 ),		vec3( 0.35458, 0.90834, 0.13383 ),
		vec3( 0.04823, 0.01566, 0.83777 )
	);
	const mat3 ACESOutputMat = mat3(
		vec3(  1.60475, -0.10208, -0.00327 ),		vec3( -0.53108,  1.10813, -0.07276 ),
		vec3( -0.07367, -0.00605,  1.07602 )
	);
	color *= toneMappingExposure / 0.6;
	color = ACESInputMat * color;
	color = RRTAndODTFit( color );
	color = ACESOutputMat * color;
	return saturate( color );
}
const mat3 LINEAR_REC2020_TO_LINEAR_SRGB = mat3(
	vec3( 1.6605, - 0.1246, - 0.0182 ),
	vec3( - 0.5876, 1.1329, - 0.1006 ),
	vec3( - 0.0728, - 0.0083, 1.1187 )
);
const mat3 LINEAR_SRGB_TO_LINEAR_REC2020 = mat3(
	vec3( 0.6274, 0.0691, 0.0164 ),
	vec3( 0.3293, 0.9195, 0.0880 ),
	vec3( 0.0433, 0.0113, 0.8956 )
);
vec3 agxDefaultContrastApprox( vec3 x ) {
	vec3 x2 = x * x;
	vec3 x4 = x2 * x2;
	return + 15.5 * x4 * x2
		- 40.14 * x4 * x
		+ 31.96 * x4
		- 6.868 * x2 * x
		+ 0.4298 * x2
		+ 0.1191 * x
		- 0.00232;
}
vec3 AgXToneMapping( vec3 color ) {
	const mat3 AgXInsetMatrix = mat3(
		vec3( 0.856627153315983, 0.137318972929847, 0.11189821299995 ),
		vec3( 0.0951212405381588, 0.761241990602591, 0.0767994186031903 ),
		vec3( 0.0482516061458583, 0.101439036467562, 0.811302368396859 )
	);
	const mat3 AgXOutsetMatrix = mat3(
		vec3( 1.1271005818144368, - 0.1413297634984383, - 0.14132976349843826 ),
		vec3( - 0.11060664309660323, 1.157823702216272, - 0.11060664309660294 ),
		vec3( - 0.016493938717834573, - 0.016493938717834257, 1.2519364065950405 )
	);
	const float AgxMinEv = - 12.47393;	const float AgxMaxEv = 4.026069;
	color *= toneMappingExposure;
	color = LINEAR_SRGB_TO_LINEAR_REC2020 * color;
	color = AgXInsetMatrix * color;
	color = max( color, 1e-10 );	color = log2( color );
	color = ( color - AgxMinEv ) / ( AgxMaxEv - AgxMinEv );
	color = clamp( color, 0.0, 1.0 );
	color = agxDefaultContrastApprox( color );
	color = AgXOutsetMatrix * color;
	color = pow( max( vec3( 0.0 ), color ), vec3( 2.2 ) );
	color = LINEAR_REC2020_TO_LINEAR_SRGB * color;
	color = clamp( color, 0.0, 1.0 );
	return color;
}
vec3 NeutralToneMapping( vec3 color ) {
	const float StartCompression = 0.8 - 0.04;
	const float Desaturation = 0.15;
	color *= toneMappingExposure;
	float x = min( color.r, min( color.g, color.b ) );
	float offset = x < 0.08 ? x - 6.25 * x * x : 0.04;
	color -= offset;
	float peak = max( color.r, max( color.g, color.b ) );
	if ( peak < StartCompression ) return color;
	float d = 1. - StartCompression;
	float newPeak = 1. - d * d / ( peak + d - StartCompression );
	color *= newPeak / peak;
	float g = 1. - 1. / ( Desaturation * ( peak - newPeak ) + 1. );
	return mix( color, vec3( newPeak ), g );
}
vec3 CustomToneMapping( vec3 color ) { return color; }`,pm=`#ifdef USE_TRANSMISSION
	material.transmission = transmission;
	material.transmissionAlpha = 1.0;
	material.thickness = thickness;
	material.attenuationDistance = attenuationDistance;
	material.attenuationColor = attenuationColor;
	#ifdef USE_TRANSMISSIONMAP
		material.transmission *= texture2D( transmissionMap, vTransmissionMapUv ).r;
	#endif
	#ifdef USE_THICKNESSMAP
		material.thickness *= texture2D( thicknessMap, vThicknessMapUv ).g;
	#endif
	vec3 pos = vWorldPosition;
	vec3 v = normalize( cameraPosition - pos );
	vec3 n = inverseTransformDirection( normal, viewMatrix );
	vec4 transmitted = getIBLVolumeRefraction(
		n, v, material.roughness, material.diffuseColor, material.specularColor, material.specularF90,
		pos, modelMatrix, viewMatrix, projectionMatrix, material.dispersion, material.ior, material.thickness,
		material.attenuationColor, material.attenuationDistance );
	material.transmissionAlpha = mix( material.transmissionAlpha, transmitted.a, material.transmission );
	totalDiffuse = mix( totalDiffuse, transmitted.rgb, material.transmission );
#endif`,mm=`#ifdef USE_TRANSMISSION
	uniform float transmission;
	uniform float thickness;
	uniform float attenuationDistance;
	uniform vec3 attenuationColor;
	#ifdef USE_TRANSMISSIONMAP
		uniform sampler2D transmissionMap;
	#endif
	#ifdef USE_THICKNESSMAP
		uniform sampler2D thicknessMap;
	#endif
	uniform vec2 transmissionSamplerSize;
	uniform sampler2D transmissionSamplerMap;
	uniform mat4 modelMatrix;
	uniform mat4 projectionMatrix;
	varying vec3 vWorldPosition;
	float w0( float a ) {
		return ( 1.0 / 6.0 ) * ( a * ( a * ( - a + 3.0 ) - 3.0 ) + 1.0 );
	}
	float w1( float a ) {
		return ( 1.0 / 6.0 ) * ( a *  a * ( 3.0 * a - 6.0 ) + 4.0 );
	}
	float w2( float a ){
		return ( 1.0 / 6.0 ) * ( a * ( a * ( - 3.0 * a + 3.0 ) + 3.0 ) + 1.0 );
	}
	float w3( float a ) {
		return ( 1.0 / 6.0 ) * ( a * a * a );
	}
	float g0( float a ) {
		return w0( a ) + w1( a );
	}
	float g1( float a ) {
		return w2( a ) + w3( a );
	}
	float h0( float a ) {
		return - 1.0 + w1( a ) / ( w0( a ) + w1( a ) );
	}
	float h1( float a ) {
		return 1.0 + w3( a ) / ( w2( a ) + w3( a ) );
	}
	vec4 bicubic( sampler2D tex, vec2 uv, vec4 texelSize, float lod ) {
		uv = uv * texelSize.zw + 0.5;
		vec2 iuv = floor( uv );
		vec2 fuv = fract( uv );
		float g0x = g0( fuv.x );
		float g1x = g1( fuv.x );
		float h0x = h0( fuv.x );
		float h1x = h1( fuv.x );
		float h0y = h0( fuv.y );
		float h1y = h1( fuv.y );
		vec2 p0 = ( vec2( iuv.x + h0x, iuv.y + h0y ) - 0.5 ) * texelSize.xy;
		vec2 p1 = ( vec2( iuv.x + h1x, iuv.y + h0y ) - 0.5 ) * texelSize.xy;
		vec2 p2 = ( vec2( iuv.x + h0x, iuv.y + h1y ) - 0.5 ) * texelSize.xy;
		vec2 p3 = ( vec2( iuv.x + h1x, iuv.y + h1y ) - 0.5 ) * texelSize.xy;
		return g0( fuv.y ) * ( g0x * textureLod( tex, p0, lod ) + g1x * textureLod( tex, p1, lod ) ) +
			g1( fuv.y ) * ( g0x * textureLod( tex, p2, lod ) + g1x * textureLod( tex, p3, lod ) );
	}
	vec4 textureBicubic( sampler2D sampler, vec2 uv, float lod ) {
		vec2 fLodSize = vec2( textureSize( sampler, int( lod ) ) );
		vec2 cLodSize = vec2( textureSize( sampler, int( lod + 1.0 ) ) );
		vec2 fLodSizeInv = 1.0 / fLodSize;
		vec2 cLodSizeInv = 1.0 / cLodSize;
		vec4 fSample = bicubic( sampler, uv, vec4( fLodSizeInv, fLodSize ), floor( lod ) );
		vec4 cSample = bicubic( sampler, uv, vec4( cLodSizeInv, cLodSize ), ceil( lod ) );
		return mix( fSample, cSample, fract( lod ) );
	}
	vec3 getVolumeTransmissionRay( const in vec3 n, const in vec3 v, const in float thickness, const in float ior, const in mat4 modelMatrix ) {
		vec3 refractionVector = refract( - v, normalize( n ), 1.0 / ior );
		vec3 modelScale;
		modelScale.x = length( vec3( modelMatrix[ 0 ].xyz ) );
		modelScale.y = length( vec3( modelMatrix[ 1 ].xyz ) );
		modelScale.z = length( vec3( modelMatrix[ 2 ].xyz ) );
		return normalize( refractionVector ) * thickness * modelScale;
	}
	float applyIorToRoughness( const in float roughness, const in float ior ) {
		return roughness * clamp( ior * 2.0 - 2.0, 0.0, 1.0 );
	}
	vec4 getTransmissionSample( const in vec2 fragCoord, const in float roughness, const in float ior ) {
		float lod = log2( transmissionSamplerSize.x ) * applyIorToRoughness( roughness, ior );
		return textureBicubic( transmissionSamplerMap, fragCoord.xy, lod );
	}
	vec3 volumeAttenuation( const in float transmissionDistance, const in vec3 attenuationColor, const in float attenuationDistance ) {
		if ( isinf( attenuationDistance ) ) {
			return vec3( 1.0 );
		} else {
			vec3 attenuationCoefficient = -log( attenuationColor ) / attenuationDistance;
			vec3 transmittance = exp( - attenuationCoefficient * transmissionDistance );			return transmittance;
		}
	}
	vec4 getIBLVolumeRefraction( const in vec3 n, const in vec3 v, const in float roughness, const in vec3 diffuseColor,
		const in vec3 specularColor, const in float specularF90, const in vec3 position, const in mat4 modelMatrix,
		const in mat4 viewMatrix, const in mat4 projMatrix, const in float dispersion, const in float ior, const in float thickness,
		const in vec3 attenuationColor, const in float attenuationDistance ) {
		vec4 transmittedLight;
		vec3 transmittance;
		#ifdef USE_DISPERSION
			float halfSpread = ( ior - 1.0 ) * 0.025 * dispersion;
			vec3 iors = vec3( ior - halfSpread, ior, ior + halfSpread );
			for ( int i = 0; i < 3; i ++ ) {
				vec3 transmissionRay = getVolumeTransmissionRay( n, v, thickness, iors[ i ], modelMatrix );
				vec3 refractedRayExit = position + transmissionRay;
		
				vec4 ndcPos = projMatrix * viewMatrix * vec4( refractedRayExit, 1.0 );
				vec2 refractionCoords = ndcPos.xy / ndcPos.w;
				refractionCoords += 1.0;
				refractionCoords /= 2.0;
		
				vec4 transmissionSample = getTransmissionSample( refractionCoords, roughness, iors[ i ] );
				transmittedLight[ i ] = transmissionSample[ i ];
				transmittedLight.a += transmissionSample.a;
				transmittance[ i ] = diffuseColor[ i ] * volumeAttenuation( length( transmissionRay ), attenuationColor, attenuationDistance )[ i ];
			}
			transmittedLight.a /= 3.0;
		
		#else
		
			vec3 transmissionRay = getVolumeTransmissionRay( n, v, thickness, ior, modelMatrix );
			vec3 refractedRayExit = position + transmissionRay;
			vec4 ndcPos = projMatrix * viewMatrix * vec4( refractedRayExit, 1.0 );
			vec2 refractionCoords = ndcPos.xy / ndcPos.w;
			refractionCoords += 1.0;
			refractionCoords /= 2.0;
			transmittedLight = getTransmissionSample( refractionCoords, roughness, ior );
			transmittance = diffuseColor * volumeAttenuation( length( transmissionRay ), attenuationColor, attenuationDistance );
		
		#endif
		vec3 attenuatedColor = transmittance * transmittedLight.rgb;
		vec3 F = EnvironmentBRDF( n, v, specularColor, specularF90, roughness );
		float transmittanceFactor = ( transmittance.r + transmittance.g + transmittance.b ) / 3.0;
		return vec4( ( 1.0 - F ) * attenuatedColor, 1.0 - ( 1.0 - transmittedLight.a ) * transmittanceFactor );
	}
#endif`,gm=`#if defined( USE_UV ) || defined( USE_ANISOTROPY )
	varying vec2 vUv;
#endif
#ifdef USE_MAP
	varying vec2 vMapUv;
#endif
#ifdef USE_ALPHAMAP
	varying vec2 vAlphaMapUv;
#endif
#ifdef USE_LIGHTMAP
	varying vec2 vLightMapUv;
#endif
#ifdef USE_AOMAP
	varying vec2 vAoMapUv;
#endif
#ifdef USE_BUMPMAP
	varying vec2 vBumpMapUv;
#endif
#ifdef USE_NORMALMAP
	varying vec2 vNormalMapUv;
#endif
#ifdef USE_EMISSIVEMAP
	varying vec2 vEmissiveMapUv;
#endif
#ifdef USE_METALNESSMAP
	varying vec2 vMetalnessMapUv;
#endif
#ifdef USE_ROUGHNESSMAP
	varying vec2 vRoughnessMapUv;
#endif
#ifdef USE_ANISOTROPYMAP
	varying vec2 vAnisotropyMapUv;
#endif
#ifdef USE_CLEARCOATMAP
	varying vec2 vClearcoatMapUv;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	varying vec2 vClearcoatNormalMapUv;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	varying vec2 vClearcoatRoughnessMapUv;
#endif
#ifdef USE_IRIDESCENCEMAP
	varying vec2 vIridescenceMapUv;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	varying vec2 vIridescenceThicknessMapUv;
#endif
#ifdef USE_SHEEN_COLORMAP
	varying vec2 vSheenColorMapUv;
#endif
#ifdef USE_SHEEN_ROUGHNESSMAP
	varying vec2 vSheenRoughnessMapUv;
#endif
#ifdef USE_SPECULARMAP
	varying vec2 vSpecularMapUv;
#endif
#ifdef USE_SPECULAR_COLORMAP
	varying vec2 vSpecularColorMapUv;
#endif
#ifdef USE_SPECULAR_INTENSITYMAP
	varying vec2 vSpecularIntensityMapUv;
#endif
#ifdef USE_TRANSMISSIONMAP
	uniform mat3 transmissionMapTransform;
	varying vec2 vTransmissionMapUv;
#endif
#ifdef USE_THICKNESSMAP
	uniform mat3 thicknessMapTransform;
	varying vec2 vThicknessMapUv;
#endif`,_m=`#if defined( USE_UV ) || defined( USE_ANISOTROPY )
	varying vec2 vUv;
#endif
#ifdef USE_MAP
	uniform mat3 mapTransform;
	varying vec2 vMapUv;
#endif
#ifdef USE_ALPHAMAP
	uniform mat3 alphaMapTransform;
	varying vec2 vAlphaMapUv;
#endif
#ifdef USE_LIGHTMAP
	uniform mat3 lightMapTransform;
	varying vec2 vLightMapUv;
#endif
#ifdef USE_AOMAP
	uniform mat3 aoMapTransform;
	varying vec2 vAoMapUv;
#endif
#ifdef USE_BUMPMAP
	uniform mat3 bumpMapTransform;
	varying vec2 vBumpMapUv;
#endif
#ifdef USE_NORMALMAP
	uniform mat3 normalMapTransform;
	varying vec2 vNormalMapUv;
#endif
#ifdef USE_DISPLACEMENTMAP
	uniform mat3 displacementMapTransform;
	varying vec2 vDisplacementMapUv;
#endif
#ifdef USE_EMISSIVEMAP
	uniform mat3 emissiveMapTransform;
	varying vec2 vEmissiveMapUv;
#endif
#ifdef USE_METALNESSMAP
	uniform mat3 metalnessMapTransform;
	varying vec2 vMetalnessMapUv;
#endif
#ifdef USE_ROUGHNESSMAP
	uniform mat3 roughnessMapTransform;
	varying vec2 vRoughnessMapUv;
#endif
#ifdef USE_ANISOTROPYMAP
	uniform mat3 anisotropyMapTransform;
	varying vec2 vAnisotropyMapUv;
#endif
#ifdef USE_CLEARCOATMAP
	uniform mat3 clearcoatMapTransform;
	varying vec2 vClearcoatMapUv;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	uniform mat3 clearcoatNormalMapTransform;
	varying vec2 vClearcoatNormalMapUv;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	uniform mat3 clearcoatRoughnessMapTransform;
	varying vec2 vClearcoatRoughnessMapUv;
#endif
#ifdef USE_SHEEN_COLORMAP
	uniform mat3 sheenColorMapTransform;
	varying vec2 vSheenColorMapUv;
#endif
#ifdef USE_SHEEN_ROUGHNESSMAP
	uniform mat3 sheenRoughnessMapTransform;
	varying vec2 vSheenRoughnessMapUv;
#endif
#ifdef USE_IRIDESCENCEMAP
	uniform mat3 iridescenceMapTransform;
	varying vec2 vIridescenceMapUv;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	uniform mat3 iridescenceThicknessMapTransform;
	varying vec2 vIridescenceThicknessMapUv;
#endif
#ifdef USE_SPECULARMAP
	uniform mat3 specularMapTransform;
	varying vec2 vSpecularMapUv;
#endif
#ifdef USE_SPECULAR_COLORMAP
	uniform mat3 specularColorMapTransform;
	varying vec2 vSpecularColorMapUv;
#endif
#ifdef USE_SPECULAR_INTENSITYMAP
	uniform mat3 specularIntensityMapTransform;
	varying vec2 vSpecularIntensityMapUv;
#endif
#ifdef USE_TRANSMISSIONMAP
	uniform mat3 transmissionMapTransform;
	varying vec2 vTransmissionMapUv;
#endif
#ifdef USE_THICKNESSMAP
	uniform mat3 thicknessMapTransform;
	varying vec2 vThicknessMapUv;
#endif`,xm=`#if defined( USE_UV ) || defined( USE_ANISOTROPY )
	vUv = vec3( uv, 1 ).xy;
#endif
#ifdef USE_MAP
	vMapUv = ( mapTransform * vec3( MAP_UV, 1 ) ).xy;
#endif
#ifdef USE_ALPHAMAP
	vAlphaMapUv = ( alphaMapTransform * vec3( ALPHAMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_LIGHTMAP
	vLightMapUv = ( lightMapTransform * vec3( LIGHTMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_AOMAP
	vAoMapUv = ( aoMapTransform * vec3( AOMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_BUMPMAP
	vBumpMapUv = ( bumpMapTransform * vec3( BUMPMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_NORMALMAP
	vNormalMapUv = ( normalMapTransform * vec3( NORMALMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_DISPLACEMENTMAP
	vDisplacementMapUv = ( displacementMapTransform * vec3( DISPLACEMENTMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_EMISSIVEMAP
	vEmissiveMapUv = ( emissiveMapTransform * vec3( EMISSIVEMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_METALNESSMAP
	vMetalnessMapUv = ( metalnessMapTransform * vec3( METALNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_ROUGHNESSMAP
	vRoughnessMapUv = ( roughnessMapTransform * vec3( ROUGHNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_ANISOTROPYMAP
	vAnisotropyMapUv = ( anisotropyMapTransform * vec3( ANISOTROPYMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_CLEARCOATMAP
	vClearcoatMapUv = ( clearcoatMapTransform * vec3( CLEARCOATMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	vClearcoatNormalMapUv = ( clearcoatNormalMapTransform * vec3( CLEARCOAT_NORMALMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	vClearcoatRoughnessMapUv = ( clearcoatRoughnessMapTransform * vec3( CLEARCOAT_ROUGHNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_IRIDESCENCEMAP
	vIridescenceMapUv = ( iridescenceMapTransform * vec3( IRIDESCENCEMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	vIridescenceThicknessMapUv = ( iridescenceThicknessMapTransform * vec3( IRIDESCENCE_THICKNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SHEEN_COLORMAP
	vSheenColorMapUv = ( sheenColorMapTransform * vec3( SHEEN_COLORMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SHEEN_ROUGHNESSMAP
	vSheenRoughnessMapUv = ( sheenRoughnessMapTransform * vec3( SHEEN_ROUGHNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SPECULARMAP
	vSpecularMapUv = ( specularMapTransform * vec3( SPECULARMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SPECULAR_COLORMAP
	vSpecularColorMapUv = ( specularColorMapTransform * vec3( SPECULAR_COLORMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SPECULAR_INTENSITYMAP
	vSpecularIntensityMapUv = ( specularIntensityMapTransform * vec3( SPECULAR_INTENSITYMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_TRANSMISSIONMAP
	vTransmissionMapUv = ( transmissionMapTransform * vec3( TRANSMISSIONMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_THICKNESSMAP
	vThicknessMapUv = ( thicknessMapTransform * vec3( THICKNESSMAP_UV, 1 ) ).xy;
#endif`,ym=`#if defined( USE_ENVMAP ) || defined( DISTANCE ) || defined ( USE_SHADOWMAP ) || defined ( USE_TRANSMISSION ) || NUM_SPOT_LIGHT_COORDS > 0
	vec4 worldPosition = vec4( transformed, 1.0 );
	#ifdef USE_BATCHING
		worldPosition = batchingMatrix * worldPosition;
	#endif
	#ifdef USE_INSTANCING
		worldPosition = instanceMatrix * worldPosition;
	#endif
	worldPosition = modelMatrix * worldPosition;
#endif`,vm=`varying vec2 vUv;
uniform mat3 uvTransform;
void main() {
	vUv = ( uvTransform * vec3( uv, 1 ) ).xy;
	gl_Position = vec4( position.xy, 1.0, 1.0 );
}`,Mm=`uniform sampler2D t2D;
uniform float backgroundIntensity;
varying vec2 vUv;
void main() {
	vec4 texColor = texture2D( t2D, vUv );
	#ifdef DECODE_VIDEO_TEXTURE
		texColor = vec4( mix( pow( texColor.rgb * 0.9478672986 + vec3( 0.0521327014 ), vec3( 2.4 ) ), texColor.rgb * 0.0773993808, vec3( lessThanEqual( texColor.rgb, vec3( 0.04045 ) ) ) ), texColor.w );
	#endif
	texColor.rgb *= backgroundIntensity;
	gl_FragColor = texColor;
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,Sm=`varying vec3 vWorldDirection;
#include <common>
void main() {
	vWorldDirection = transformDirection( position, modelMatrix );
	#include <begin_vertex>
	#include <project_vertex>
	gl_Position.z = gl_Position.w;
}`,bm=`#ifdef ENVMAP_TYPE_CUBE
	uniform samplerCube envMap;
#elif defined( ENVMAP_TYPE_CUBE_UV )
	uniform sampler2D envMap;
#endif
uniform float flipEnvMap;
uniform float backgroundBlurriness;
uniform float backgroundIntensity;
uniform mat3 backgroundRotation;
varying vec3 vWorldDirection;
#include <cube_uv_reflection_fragment>
void main() {
	#ifdef ENVMAP_TYPE_CUBE
		vec4 texColor = textureCube( envMap, backgroundRotation * vec3( flipEnvMap * vWorldDirection.x, vWorldDirection.yz ) );
	#elif defined( ENVMAP_TYPE_CUBE_UV )
		vec4 texColor = textureCubeUV( envMap, backgroundRotation * vWorldDirection, backgroundBlurriness );
	#else
		vec4 texColor = vec4( 0.0, 0.0, 0.0, 1.0 );
	#endif
	texColor.rgb *= backgroundIntensity;
	gl_FragColor = texColor;
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,wm=`varying vec3 vWorldDirection;
#include <common>
void main() {
	vWorldDirection = transformDirection( position, modelMatrix );
	#include <begin_vertex>
	#include <project_vertex>
	gl_Position.z = gl_Position.w;
}`,Em=`uniform samplerCube tCube;
uniform float tFlip;
uniform float opacity;
varying vec3 vWorldDirection;
void main() {
	vec4 texColor = textureCube( tCube, vec3( tFlip * vWorldDirection.x, vWorldDirection.yz ) );
	gl_FragColor = texColor;
	gl_FragColor.a *= opacity;
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,Am=`#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
varying vec2 vHighPrecisionZW;
void main() {
	#include <uv_vertex>
	#include <batching_vertex>
	#include <skinbase_vertex>
	#include <morphinstance_vertex>
	#ifdef USE_DISPLACEMENTMAP
		#include <beginnormal_vertex>
		#include <morphnormal_vertex>
		#include <skinnormal_vertex>
	#endif
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vHighPrecisionZW = gl_Position.zw;
}`,Tm=`#if DEPTH_PACKING == 3200
	uniform float opacity;
#endif
#include <common>
#include <packing>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
varying vec2 vHighPrecisionZW;
void main() {
	vec4 diffuseColor = vec4( 1.0 );
	#include <clipping_planes_fragment>
	#if DEPTH_PACKING == 3200
		diffuseColor.a = opacity;
	#endif
	#include <map_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <logdepthbuf_fragment>
	float fragCoordZ = 0.5 * vHighPrecisionZW[0] / vHighPrecisionZW[1] + 0.5;
	#if DEPTH_PACKING == 3200
		gl_FragColor = vec4( vec3( 1.0 - fragCoordZ ), opacity );
	#elif DEPTH_PACKING == 3201
		gl_FragColor = packDepthToRGBA( fragCoordZ );
	#elif DEPTH_PACKING == 3202
		gl_FragColor = vec4( packDepthToRGB( fragCoordZ ), 1.0 );
	#elif DEPTH_PACKING == 3203
		gl_FragColor = vec4( packDepthToRG( fragCoordZ ), 0.0, 1.0 );
	#endif
}`,Rm=`#define DISTANCE
varying vec3 vWorldPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <batching_vertex>
	#include <skinbase_vertex>
	#include <morphinstance_vertex>
	#ifdef USE_DISPLACEMENTMAP
		#include <beginnormal_vertex>
		#include <morphnormal_vertex>
		#include <skinnormal_vertex>
	#endif
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <worldpos_vertex>
	#include <clipping_planes_vertex>
	vWorldPosition = worldPosition.xyz;
}`,Cm=`#define DISTANCE
uniform vec3 referencePosition;
uniform float nearDistance;
uniform float farDistance;
varying vec3 vWorldPosition;
#include <common>
#include <packing>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <clipping_planes_pars_fragment>
void main () {
	vec4 diffuseColor = vec4( 1.0 );
	#include <clipping_planes_fragment>
	#include <map_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	float dist = length( vWorldPosition - referencePosition );
	dist = ( dist - nearDistance ) / ( farDistance - nearDistance );
	dist = saturate( dist );
	gl_FragColor = packDepthToRGBA( dist );
}`,Im=`varying vec3 vWorldDirection;
#include <common>
void main() {
	vWorldDirection = transformDirection( position, modelMatrix );
	#include <begin_vertex>
	#include <project_vertex>
}`,Pm=`uniform sampler2D tEquirect;
varying vec3 vWorldDirection;
#include <common>
void main() {
	vec3 direction = normalize( vWorldDirection );
	vec2 sampleUV = equirectUv( direction );
	gl_FragColor = texture2D( tEquirect, sampleUV );
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,Lm=`uniform float scale;
attribute float lineDistance;
varying float vLineDistance;
#include <common>
#include <uv_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	vLineDistance = scale * lineDistance;
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <fog_vertex>
}`,Dm=`uniform vec3 diffuse;
uniform float opacity;
uniform float dashSize;
uniform float totalSize;
varying float vLineDistance;
#include <common>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <fog_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	if ( mod( vLineDistance, totalSize ) > dashSize ) {
		discard;
	}
	vec3 outgoingLight = vec3( 0.0 );
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	outgoingLight = diffuseColor.rgb;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
}`,Um=`#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <envmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#if defined ( USE_ENVMAP ) || defined ( USE_SKINNING )
		#include <beginnormal_vertex>
		#include <morphnormal_vertex>
		#include <skinbase_vertex>
		#include <skinnormal_vertex>
		#include <defaultnormal_vertex>
	#endif
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <worldpos_vertex>
	#include <envmap_vertex>
	#include <fog_vertex>
}`,Nm=`uniform vec3 diffuse;
uniform float opacity;
#ifndef FLAT_SHADED
	varying vec3 vNormal;
#endif
#include <common>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <envmap_common_pars_fragment>
#include <envmap_pars_fragment>
#include <fog_pars_fragment>
#include <specularmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <specularmap_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	#ifdef USE_LIGHTMAP
		vec4 lightMapTexel = texture2D( lightMap, vLightMapUv );
		reflectedLight.indirectDiffuse += lightMapTexel.rgb * lightMapIntensity * RECIPROCAL_PI;
	#else
		reflectedLight.indirectDiffuse += vec3( 1.0 );
	#endif
	#include <aomap_fragment>
	reflectedLight.indirectDiffuse *= diffuseColor.rgb;
	vec3 outgoingLight = reflectedLight.indirectDiffuse;
	#include <envmap_fragment>
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,Om=`#define LAMBERT
varying vec3 vViewPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <envmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vViewPosition = - mvPosition.xyz;
	#include <worldpos_vertex>
	#include <envmap_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
}`,Fm=`#define LAMBERT
uniform vec3 diffuse;
uniform vec3 emissive;
uniform float opacity;
#include <common>
#include <packing>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>
#include <envmap_common_pars_fragment>
#include <envmap_pars_fragment>
#include <fog_pars_fragment>
#include <bsdfs>
#include <lights_pars_begin>
#include <normal_pars_fragment>
#include <lights_lambert_pars_fragment>
#include <shadowmap_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <specularmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	vec3 totalEmissiveRadiance = emissive;
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <specularmap_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	#include <emissivemap_fragment>
	#include <lights_lambert_fragment>
	#include <lights_fragment_begin>
	#include <lights_fragment_maps>
	#include <lights_fragment_end>
	#include <aomap_fragment>
	vec3 outgoingLight = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse + totalEmissiveRadiance;
	#include <envmap_fragment>
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,Bm=`#define MATCAP
varying vec3 vViewPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <color_pars_vertex>
#include <displacementmap_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <fog_vertex>
	vViewPosition = - mvPosition.xyz;
}`,zm=`#define MATCAP
uniform vec3 diffuse;
uniform float opacity;
uniform sampler2D matcap;
varying vec3 vViewPosition;
#include <common>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <fog_pars_fragment>
#include <normal_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	vec3 viewDir = normalize( vViewPosition );
	vec3 x = normalize( vec3( viewDir.z, 0.0, - viewDir.x ) );
	vec3 y = cross( viewDir, x );
	vec2 uv = vec2( dot( x, normal ), dot( y, normal ) ) * 0.495 + 0.5;
	#ifdef USE_MATCAP
		vec4 matcapColor = texture2D( matcap, uv );
	#else
		vec4 matcapColor = vec4( vec3( mix( 0.2, 0.8, uv.y ) ), 1.0 );
	#endif
	vec3 outgoingLight = diffuseColor.rgb * matcapColor.rgb;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,km=`#define NORMAL
#if defined( FLAT_SHADED ) || defined( USE_BUMPMAP ) || defined( USE_NORMALMAP_TANGENTSPACE )
	varying vec3 vViewPosition;
#endif
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphinstance_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
#if defined( FLAT_SHADED ) || defined( USE_BUMPMAP ) || defined( USE_NORMALMAP_TANGENTSPACE )
	vViewPosition = - mvPosition.xyz;
#endif
}`,Hm=`#define NORMAL
uniform float opacity;
#if defined( FLAT_SHADED ) || defined( USE_BUMPMAP ) || defined( USE_NORMALMAP_TANGENTSPACE )
	varying vec3 vViewPosition;
#endif
#include <packing>
#include <uv_pars_fragment>
#include <normal_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( 0.0, 0.0, 0.0, opacity );
	#include <clipping_planes_fragment>
	#include <logdepthbuf_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	gl_FragColor = vec4( packNormalToRGB( normal ), diffuseColor.a );
	#ifdef OPAQUE
		gl_FragColor.a = 1.0;
	#endif
}`,Vm=`#define PHONG
varying vec3 vViewPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <envmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphinstance_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vViewPosition = - mvPosition.xyz;
	#include <worldpos_vertex>
	#include <envmap_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
}`,Gm=`#define PHONG
uniform vec3 diffuse;
uniform vec3 emissive;
uniform vec3 specular;
uniform float shininess;
uniform float opacity;
#include <common>
#include <packing>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>
#include <envmap_common_pars_fragment>
#include <envmap_pars_fragment>
#include <fog_pars_fragment>
#include <bsdfs>
#include <lights_pars_begin>
#include <normal_pars_fragment>
#include <lights_phong_pars_fragment>
#include <shadowmap_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <specularmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	vec3 totalEmissiveRadiance = emissive;
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <specularmap_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	#include <emissivemap_fragment>
	#include <lights_phong_fragment>
	#include <lights_fragment_begin>
	#include <lights_fragment_maps>
	#include <lights_fragment_end>
	#include <aomap_fragment>
	vec3 outgoingLight = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse + reflectedLight.directSpecular + reflectedLight.indirectSpecular + totalEmissiveRadiance;
	#include <envmap_fragment>
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,Wm=`#define STANDARD
varying vec3 vViewPosition;
#ifdef USE_TRANSMISSION
	varying vec3 vWorldPosition;
#endif
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vViewPosition = - mvPosition.xyz;
	#include <worldpos_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
#ifdef USE_TRANSMISSION
	vWorldPosition = worldPosition.xyz;
#endif
}`,Xm=`#define STANDARD
#ifdef PHYSICAL
	#define IOR
	#define USE_SPECULAR
#endif
uniform vec3 diffuse;
uniform vec3 emissive;
uniform float roughness;
uniform float metalness;
uniform float opacity;
#ifdef IOR
	uniform float ior;
#endif
#ifdef USE_SPECULAR
	uniform float specularIntensity;
	uniform vec3 specularColor;
	#ifdef USE_SPECULAR_COLORMAP
		uniform sampler2D specularColorMap;
	#endif
	#ifdef USE_SPECULAR_INTENSITYMAP
		uniform sampler2D specularIntensityMap;
	#endif
#endif
#ifdef USE_CLEARCOAT
	uniform float clearcoat;
	uniform float clearcoatRoughness;
#endif
#ifdef USE_DISPERSION
	uniform float dispersion;
#endif
#ifdef USE_IRIDESCENCE
	uniform float iridescence;
	uniform float iridescenceIOR;
	uniform float iridescenceThicknessMinimum;
	uniform float iridescenceThicknessMaximum;
#endif
#ifdef USE_SHEEN
	uniform vec3 sheenColor;
	uniform float sheenRoughness;
	#ifdef USE_SHEEN_COLORMAP
		uniform sampler2D sheenColorMap;
	#endif
	#ifdef USE_SHEEN_ROUGHNESSMAP
		uniform sampler2D sheenRoughnessMap;
	#endif
#endif
#ifdef USE_ANISOTROPY
	uniform vec2 anisotropyVector;
	#ifdef USE_ANISOTROPYMAP
		uniform sampler2D anisotropyMap;
	#endif
#endif
varying vec3 vViewPosition;
#include <common>
#include <packing>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>
#include <iridescence_fragment>
#include <cube_uv_reflection_fragment>
#include <envmap_common_pars_fragment>
#include <envmap_physical_pars_fragment>
#include <fog_pars_fragment>
#include <lights_pars_begin>
#include <normal_pars_fragment>
#include <lights_physical_pars_fragment>
#include <transmission_pars_fragment>
#include <shadowmap_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <clearcoat_pars_fragment>
#include <iridescence_pars_fragment>
#include <roughnessmap_pars_fragment>
#include <metalnessmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	vec3 totalEmissiveRadiance = emissive;
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <roughnessmap_fragment>
	#include <metalnessmap_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	#include <clearcoat_normal_fragment_begin>
	#include <clearcoat_normal_fragment_maps>
	#include <emissivemap_fragment>
	#include <lights_physical_fragment>
	#include <lights_fragment_begin>
	#include <lights_fragment_maps>
	#include <lights_fragment_end>
	#include <aomap_fragment>
	vec3 totalDiffuse = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse;
	vec3 totalSpecular = reflectedLight.directSpecular + reflectedLight.indirectSpecular;
	#include <transmission_fragment>
	vec3 outgoingLight = totalDiffuse + totalSpecular + totalEmissiveRadiance;
	#ifdef USE_SHEEN
		float sheenEnergyComp = 1.0 - 0.157 * max3( material.sheenColor );
		outgoingLight = outgoingLight * sheenEnergyComp + sheenSpecularDirect + sheenSpecularIndirect;
	#endif
	#ifdef USE_CLEARCOAT
		float dotNVcc = saturate( dot( geometryClearcoatNormal, geometryViewDir ) );
		vec3 Fcc = F_Schlick( material.clearcoatF0, material.clearcoatF90, dotNVcc );
		outgoingLight = outgoingLight * ( 1.0 - material.clearcoat * Fcc ) + ( clearcoatSpecularDirect + clearcoatSpecularIndirect ) * material.clearcoat;
	#endif
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,qm=`#define TOON
varying vec3 vViewPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vViewPosition = - mvPosition.xyz;
	#include <worldpos_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
}`,Ym=`#define TOON
uniform vec3 diffuse;
uniform vec3 emissive;
uniform float opacity;
#include <common>
#include <packing>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>
#include <gradientmap_pars_fragment>
#include <fog_pars_fragment>
#include <bsdfs>
#include <lights_pars_begin>
#include <normal_pars_fragment>
#include <lights_toon_pars_fragment>
#include <shadowmap_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	vec3 totalEmissiveRadiance = emissive;
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	#include <emissivemap_fragment>
	#include <lights_toon_fragment>
	#include <lights_fragment_begin>
	#include <lights_fragment_maps>
	#include <lights_fragment_end>
	#include <aomap_fragment>
	vec3 outgoingLight = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse + totalEmissiveRadiance;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,Zm=`uniform float size;
uniform float scale;
#include <common>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
#ifdef USE_POINTS_UV
	varying vec2 vUv;
	uniform mat3 uvTransform;
#endif
void main() {
	#ifdef USE_POINTS_UV
		vUv = ( uvTransform * vec3( uv, 1 ) ).xy;
	#endif
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <project_vertex>
	gl_PointSize = size;
	#ifdef USE_SIZEATTENUATION
		bool isPerspective = isPerspectiveMatrix( projectionMatrix );
		if ( isPerspective ) gl_PointSize *= ( scale / - mvPosition.z );
	#endif
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <worldpos_vertex>
	#include <fog_vertex>
}`,Km=`uniform vec3 diffuse;
uniform float opacity;
#include <common>
#include <color_pars_fragment>
#include <map_particle_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <fog_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	vec3 outgoingLight = vec3( 0.0 );
	#include <logdepthbuf_fragment>
	#include <map_particle_fragment>
	#include <color_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	outgoingLight = diffuseColor.rgb;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
}`,Jm=`#include <common>
#include <batching_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <shadowmap_pars_vertex>
void main() {
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphinstance_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <worldpos_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
}`,jm=`uniform vec3 color;
uniform float opacity;
#include <common>
#include <packing>
#include <fog_pars_fragment>
#include <bsdfs>
#include <lights_pars_begin>
#include <logdepthbuf_pars_fragment>
#include <shadowmap_pars_fragment>
#include <shadowmask_pars_fragment>
void main() {
	#include <logdepthbuf_fragment>
	gl_FragColor = vec4( color, opacity * ( 1.0 - getShadowMask() ) );
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
}`,$m=`uniform float rotation;
uniform vec2 center;
#include <common>
#include <uv_pars_vertex>
#include <fog_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	vec4 mvPosition = modelViewMatrix[ 3 ];
	vec2 scale = vec2( length( modelMatrix[ 0 ].xyz ), length( modelMatrix[ 1 ].xyz ) );
	#ifndef USE_SIZEATTENUATION
		bool isPerspective = isPerspectiveMatrix( projectionMatrix );
		if ( isPerspective ) scale *= - mvPosition.z;
	#endif
	vec2 alignedPosition = ( position.xy - ( center - vec2( 0.5 ) ) ) * scale;
	vec2 rotatedPosition;
	rotatedPosition.x = cos( rotation ) * alignedPosition.x - sin( rotation ) * alignedPosition.y;
	rotatedPosition.y = sin( rotation ) * alignedPosition.x + cos( rotation ) * alignedPosition.y;
	mvPosition.xy += rotatedPosition;
	gl_Position = projectionMatrix * mvPosition;
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <fog_vertex>
}`,Qm=`uniform vec3 diffuse;
uniform float opacity;
#include <common>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <fog_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	vec3 outgoingLight = vec3( 0.0 );
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	outgoingLight = diffuseColor.rgb;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
}`,Fe={alphahash_fragment:Mf,alphahash_pars_fragment:Sf,alphamap_fragment:bf,alphamap_pars_fragment:wf,alphatest_fragment:Ef,alphatest_pars_fragment:Af,aomap_fragment:Tf,aomap_pars_fragment:Rf,batching_pars_vertex:Cf,batching_vertex:If,begin_vertex:Pf,beginnormal_vertex:Lf,bsdfs:Df,iridescence_fragment:Uf,bumpmap_pars_fragment:Nf,clipping_planes_fragment:Of,clipping_planes_pars_fragment:Ff,clipping_planes_pars_vertex:Bf,clipping_planes_vertex:zf,color_fragment:kf,color_pars_fragment:Hf,color_pars_vertex:Vf,color_vertex:Gf,common:Wf,cube_uv_reflection_fragment:Xf,defaultnormal_vertex:qf,displacementmap_pars_vertex:Yf,displacementmap_vertex:Zf,emissivemap_fragment:Kf,emissivemap_pars_fragment:Jf,colorspace_fragment:jf,colorspace_pars_fragment:$f,envmap_fragment:Qf,envmap_common_pars_fragment:ep,envmap_pars_fragment:tp,envmap_pars_vertex:np,envmap_physical_pars_fragment:fp,envmap_vertex:ip,fog_vertex:sp,fog_pars_vertex:rp,fog_fragment:op,fog_pars_fragment:ap,gradientmap_pars_fragment:lp,lightmap_pars_fragment:cp,lights_lambert_fragment:hp,lights_lambert_pars_fragment:up,lights_pars_begin:dp,lights_toon_fragment:pp,lights_toon_pars_fragment:mp,lights_phong_fragment:gp,lights_phong_pars_fragment:_p,lights_physical_fragment:xp,lights_physical_pars_fragment:yp,lights_fragment_begin:vp,lights_fragment_maps:Mp,lights_fragment_end:Sp,logdepthbuf_fragment:bp,logdepthbuf_pars_fragment:wp,logdepthbuf_pars_vertex:Ep,logdepthbuf_vertex:Ap,map_fragment:Tp,map_pars_fragment:Rp,map_particle_fragment:Cp,map_particle_pars_fragment:Ip,metalnessmap_fragment:Pp,metalnessmap_pars_fragment:Lp,morphinstance_vertex:Dp,morphcolor_vertex:Up,morphnormal_vertex:Np,morphtarget_pars_vertex:Op,morphtarget_vertex:Fp,normal_fragment_begin:Bp,normal_fragment_maps:zp,normal_pars_fragment:kp,normal_pars_vertex:Hp,normal_vertex:Vp,normalmap_pars_fragment:Gp,clearcoat_normal_fragment_begin:Wp,clearcoat_normal_fragment_maps:Xp,clearcoat_pars_fragment:qp,iridescence_pars_fragment:Yp,opaque_fragment:Zp,packing:Kp,premultiplied_alpha_fragment:Jp,project_vertex:jp,dithering_fragment:$p,dithering_pars_fragment:Qp,roughnessmap_fragment:em,roughnessmap_pars_fragment:tm,shadowmap_pars_fragment:nm,shadowmap_pars_vertex:im,shadowmap_vertex:sm,shadowmask_pars_fragment:rm,skinbase_vertex:om,skinning_pars_vertex:am,skinning_vertex:lm,skinnormal_vertex:cm,specularmap_fragment:hm,specularmap_pars_fragment:um,tonemapping_fragment:dm,tonemapping_pars_fragment:fm,transmission_fragment:pm,transmission_pars_fragment:mm,uv_pars_fragment:gm,uv_pars_vertex:_m,uv_vertex:xm,worldpos_vertex:ym,background_vert:vm,background_frag:Mm,backgroundCube_vert:Sm,backgroundCube_frag:bm,cube_vert:wm,cube_frag:Em,depth_vert:Am,depth_frag:Tm,distanceRGBA_vert:Rm,distanceRGBA_frag:Cm,equirect_vert:Im,equirect_frag:Pm,linedashed_vert:Lm,linedashed_frag:Dm,meshbasic_vert:Um,meshbasic_frag:Nm,meshlambert_vert:Om,meshlambert_frag:Fm,meshmatcap_vert:Bm,meshmatcap_frag:zm,meshnormal_vert:km,meshnormal_frag:Hm,meshphong_vert:Vm,meshphong_frag:Gm,meshphysical_vert:Wm,meshphysical_frag:Xm,meshtoon_vert:qm,meshtoon_frag:Ym,points_vert:Zm,points_frag:Km,shadow_vert:Jm,shadow_frag:jm,sprite_vert:$m,sprite_frag:Qm},re={common:{diffuse:{value:new Ae(16777215)},opacity:{value:1},map:{value:null},mapTransform:{value:new Ne},alphaMap:{value:null},alphaMapTransform:{value:new Ne},alphaTest:{value:0}},specularmap:{specularMap:{value:null},specularMapTransform:{value:new Ne}},envmap:{envMap:{value:null},envMapRotation:{value:new Ne},flipEnvMap:{value:-1},reflectivity:{value:1},ior:{value:1.5},refractionRatio:{value:.98}},aomap:{aoMap:{value:null},aoMapIntensity:{value:1},aoMapTransform:{value:new Ne}},lightmap:{lightMap:{value:null},lightMapIntensity:{value:1},lightMapTransform:{value:new Ne}},bumpmap:{bumpMap:{value:null},bumpMapTransform:{value:new Ne},bumpScale:{value:1}},normalmap:{normalMap:{value:null},normalMapTransform:{value:new Ne},normalScale:{value:new we(1,1)}},displacementmap:{displacementMap:{value:null},displacementMapTransform:{value:new Ne},displacementScale:{value:1},displacementBias:{value:0}},emissivemap:{emissiveMap:{value:null},emissiveMapTransform:{value:new Ne}},metalnessmap:{metalnessMap:{value:null},metalnessMapTransform:{value:new Ne}},roughnessmap:{roughnessMap:{value:null},roughnessMapTransform:{value:new Ne}},gradientmap:{gradientMap:{value:null}},fog:{fogDensity:{value:25e-5},fogNear:{value:1},fogFar:{value:2e3},fogColor:{value:new Ae(16777215)}},lights:{ambientLightColor:{value:[]},lightProbe:{value:[]},directionalLights:{value:[],properties:{direction:{},color:{}}},directionalLightShadows:{value:[],properties:{shadowIntensity:1,shadowBias:{},shadowNormalBias:{},shadowRadius:{},shadowMapSize:{}}},directionalShadowMap:{value:[]},directionalShadowMatrix:{value:[]},spotLights:{value:[],properties:{color:{},position:{},direction:{},distance:{},coneCos:{},penumbraCos:{},decay:{}}},spotLightShadows:{value:[],properties:{shadowIntensity:1,shadowBias:{},shadowNormalBias:{},shadowRadius:{},shadowMapSize:{}}},spotLightMap:{value:[]},spotShadowMap:{value:[]},spotLightMatrix:{value:[]},pointLights:{value:[],properties:{color:{},position:{},decay:{},distance:{}}},pointLightShadows:{value:[],properties:{shadowIntensity:1,shadowBias:{},shadowNormalBias:{},shadowRadius:{},shadowMapSize:{},shadowCameraNear:{},shadowCameraFar:{}}},pointShadowMap:{value:[]},pointShadowMatrix:{value:[]},hemisphereLights:{value:[],properties:{direction:{},skyColor:{},groundColor:{}}},rectAreaLights:{value:[],properties:{color:{},position:{},width:{},height:{}}},ltc_1:{value:null},ltc_2:{value:null}},points:{diffuse:{value:new Ae(16777215)},opacity:{value:1},size:{value:1},scale:{value:1},map:{value:null},alphaMap:{value:null},alphaMapTransform:{value:new Ne},alphaTest:{value:0},uvTransform:{value:new Ne}},sprite:{diffuse:{value:new Ae(16777215)},opacity:{value:1},center:{value:new we(.5,.5)},rotation:{value:0},map:{value:null},mapTransform:{value:new Ne},alphaMap:{value:null},alphaMapTransform:{value:new Ne},alphaTest:{value:0}}},bn={basic:{uniforms:zt([re.common,re.specularmap,re.envmap,re.aomap,re.lightmap,re.fog]),vertexShader:Fe.meshbasic_vert,fragmentShader:Fe.meshbasic_frag},lambert:{uniforms:zt([re.common,re.specularmap,re.envmap,re.aomap,re.lightmap,re.emissivemap,re.bumpmap,re.normalmap,re.displacementmap,re.fog,re.lights,{emissive:{value:new Ae(0)}}]),vertexShader:Fe.meshlambert_vert,fragmentShader:Fe.meshlambert_frag},phong:{uniforms:zt([re.common,re.specularmap,re.envmap,re.aomap,re.lightmap,re.emissivemap,re.bumpmap,re.normalmap,re.displacementmap,re.fog,re.lights,{emissive:{value:new Ae(0)},specular:{value:new Ae(1118481)},shininess:{value:30}}]),vertexShader:Fe.meshphong_vert,fragmentShader:Fe.meshphong_frag},standard:{uniforms:zt([re.common,re.envmap,re.aomap,re.lightmap,re.emissivemap,re.bumpmap,re.normalmap,re.displacementmap,re.roughnessmap,re.metalnessmap,re.fog,re.lights,{emissive:{value:new Ae(0)},roughness:{value:1},metalness:{value:0},envMapIntensity:{value:1}}]),vertexShader:Fe.meshphysical_vert,fragmentShader:Fe.meshphysical_frag},toon:{uniforms:zt([re.common,re.aomap,re.lightmap,re.emissivemap,re.bumpmap,re.normalmap,re.displacementmap,re.gradientmap,re.fog,re.lights,{emissive:{value:new Ae(0)}}]),vertexShader:Fe.meshtoon_vert,fragmentShader:Fe.meshtoon_frag},matcap:{uniforms:zt([re.common,re.bumpmap,re.normalmap,re.displacementmap,re.fog,{matcap:{value:null}}]),vertexShader:Fe.meshmatcap_vert,fragmentShader:Fe.meshmatcap_frag},points:{uniforms:zt([re.points,re.fog]),vertexShader:Fe.points_vert,fragmentShader:Fe.points_frag},dashed:{uniforms:zt([re.common,re.fog,{scale:{value:1},dashSize:{value:1},totalSize:{value:2}}]),vertexShader:Fe.linedashed_vert,fragmentShader:Fe.linedashed_frag},depth:{uniforms:zt([re.common,re.displacementmap]),vertexShader:Fe.depth_vert,fragmentShader:Fe.depth_frag},normal:{uniforms:zt([re.common,re.bumpmap,re.normalmap,re.displacementmap,{opacity:{value:1}}]),vertexShader:Fe.meshnormal_vert,fragmentShader:Fe.meshnormal_frag},sprite:{uniforms:zt([re.sprite,re.fog]),vertexShader:Fe.sprite_vert,fragmentShader:Fe.sprite_frag},background:{uniforms:{uvTransform:{value:new Ne},t2D:{value:null},backgroundIntensity:{value:1}},vertexShader:Fe.background_vert,fragmentShader:Fe.background_frag},backgroundCube:{uniforms:{envMap:{value:null},flipEnvMap:{value:-1},backgroundBlurriness:{value:0},backgroundIntensity:{value:1},backgroundRotation:{value:new Ne}},vertexShader:Fe.backgroundCube_vert,fragmentShader:Fe.backgroundCube_frag},cube:{uniforms:{tCube:{value:null},tFlip:{value:-1},opacity:{value:1}},vertexShader:Fe.cube_vert,fragmentShader:Fe.cube_frag},equirect:{uniforms:{tEquirect:{value:null}},vertexShader:Fe.equirect_vert,fragmentShader:Fe.equirect_frag},distanceRGBA:{uniforms:zt([re.common,re.displacementmap,{referencePosition:{value:new C},nearDistance:{value:1},farDistance:{value:1e3}}]),vertexShader:Fe.distanceRGBA_vert,fragmentShader:Fe.distanceRGBA_frag},shadow:{uniforms:zt([re.lights,re.fog,{color:{value:new Ae(0)},opacity:{value:1}}]),vertexShader:Fe.shadow_vert,fragmentShader:Fe.shadow_frag}};bn.physical={uniforms:zt([bn.standard.uniforms,{clearcoat:{value:0},clearcoatMap:{value:null},clearcoatMapTransform:{value:new Ne},clearcoatNormalMap:{value:null},clearcoatNormalMapTransform:{value:new Ne},clearcoatNormalScale:{value:new we(1,1)},clearcoatRoughness:{value:0},clearcoatRoughnessMap:{value:null},clearcoatRoughnessMapTransform:{value:new Ne},dispersion:{value:0},iridescence:{value:0},iridescenceMap:{value:null},iridescenceMapTransform:{value:new Ne},iridescenceIOR:{value:1.3},iridescenceThicknessMinimum:{value:100},iridescenceThicknessMaximum:{value:400},iridescenceThicknessMap:{value:null},iridescenceThicknessMapTransform:{value:new Ne},sheen:{value:0},sheenColor:{value:new Ae(0)},sheenColorMap:{value:null},sheenColorMapTransform:{value:new Ne},sheenRoughness:{value:1},sheenRoughnessMap:{value:null},sheenRoughnessMapTransform:{value:new Ne},transmission:{value:0},transmissionMap:{value:null},transmissionMapTransform:{value:new Ne},transmissionSamplerSize:{value:new we},transmissionSamplerMap:{value:null},thickness:{value:0},thicknessMap:{value:null},thicknessMapTransform:{value:new Ne},attenuationDistance:{value:0},attenuationColor:{value:new Ae(0)},specularColor:{value:new Ae(1,1,1)},specularColorMap:{value:null},specularColorMapTransform:{value:new Ne},specularIntensity:{value:1},specularIntensityMap:{value:null},specularIntensityMapTransform:{value:new Ne},anisotropyVector:{value:new we},anisotropyMap:{value:null},anisotropyMapTransform:{value:new Ne}}]),vertexShader:Fe.meshphysical_vert,fragmentShader:Fe.meshphysical_frag};var Tr={r:0,b:0,g:0},Ai=new An,e0=new Le;function t0(i,e,t,n,s,r,o){let a=new Ae(0),l=r===!0?0:1,c,h,u=null,d=0,f=null;function g(w){let b=w.isScene===!0?w.background:null;return b&&b.isTexture&&(b=(w.backgroundBlurriness>0?t:e).get(b)),b}function _(w){let b=!1,x=g(w);x===null?p(a,l):x&&x.isColor&&(p(x,1),b=!0);let P=i.xr.getEnvironmentBlendMode();P==="additive"?n.buffers.color.setClear(0,0,0,1,o):P==="alpha-blend"&&n.buffers.color.setClear(0,0,0,0,o),(i.autoClear||b)&&(n.buffers.depth.setTest(!0),n.buffers.depth.setMask(!0),n.buffers.color.setMask(!0),i.clear(i.autoClearColor,i.autoClearDepth,i.autoClearStencil))}function m(w,b){let x=g(b);x&&(x.isCubeTexture||x.mapping===bo)?(h===void 0&&(h=new tt(new qn(1,1,1),new ln({name:"BackgroundCubeMaterial",uniforms:gs(bn.backgroundCube.uniforms),vertexShader:bn.backgroundCube.vertexShader,fragmentShader:bn.backgroundCube.fragmentShader,side:Ut,depthTest:!1,depthWrite:!1,fog:!1})),h.geometry.deleteAttribute("normal"),h.geometry.deleteAttribute("uv"),h.onBeforeRender=function(P,T,A){this.matrixWorld.copyPosition(A.matrixWorld)},Object.defineProperty(h.material,"envMap",{get:function(){return this.uniforms.envMap.value}}),s.update(h)),Ai.copy(b.backgroundRotation),Ai.x*=-1,Ai.y*=-1,Ai.z*=-1,x.isCubeTexture&&x.isRenderTargetTexture===!1&&(Ai.y*=-1,Ai.z*=-1),h.material.uniforms.envMap.value=x,h.material.uniforms.flipEnvMap.value=x.isCubeTexture&&x.isRenderTargetTexture===!1?-1:1,h.material.uniforms.backgroundBlurriness.value=b.backgroundBlurriness,h.material.uniforms.backgroundIntensity.value=b.backgroundIntensity,h.material.uniforms.backgroundRotation.value.setFromMatrix4(e0.makeRotationFromEuler(Ai)),h.material.toneMapped=ke.getTransfer(x.colorSpace)!==Qe,(u!==x||d!==x.version||f!==i.toneMapping)&&(h.material.needsUpdate=!0,u=x,d=x.version,f=i.toneMapping),h.layers.enableAll(),w.unshift(h,h.geometry,h.material,0,0,null)):x&&x.isTexture&&(c===void 0&&(c=new tt(new Yn(2,2),new ln({name:"BackgroundMaterial",uniforms:gs(bn.background.uniforms),vertexShader:bn.background.vertexShader,fragmentShader:bn.background.fragmentShader,side:En,depthTest:!1,depthWrite:!1,fog:!1})),c.geometry.deleteAttribute("normal"),Object.defineProperty(c.material,"map",{get:function(){return this.uniforms.t2D.value}}),s.update(c)),c.material.uniforms.t2D.value=x,c.material.uniforms.backgroundIntensity.value=b.backgroundIntensity,c.material.toneMapped=ke.getTransfer(x.colorSpace)!==Qe,x.matrixAutoUpdate===!0&&x.updateMatrix(),c.material.uniforms.uvTransform.value.copy(x.matrix),(u!==x||d!==x.version||f!==i.toneMapping)&&(c.material.needsUpdate=!0,u=x,d=x.version,f=i.toneMapping),c.layers.enableAll(),w.unshift(c,c.geometry,c.material,0,0,null))}function p(w,b){w.getRGB(Tr,vu(i)),n.buffers.color.setClear(Tr.r,Tr.g,Tr.b,b,o)}return{getClearColor:function(){return a},setClearColor:function(w,b=1){a.set(w),l=b,p(a,l)},getClearAlpha:function(){return l},setClearAlpha:function(w){l=w,p(a,l)},render:_,addToRenderList:m}}function n0(i,e){let t=i.getParameter(i.MAX_VERTEX_ATTRIBS),n={},s=d(null),r=s,o=!1;function a(v,I,G,O,X){let Y=!1,V=u(O,G,I);r!==V&&(r=V,c(r.object)),Y=f(v,O,G,X),Y&&g(v,O,G,X),X!==null&&e.update(X,i.ELEMENT_ARRAY_BUFFER),(Y||o)&&(o=!1,x(v,I,G,O),X!==null&&i.bindBuffer(i.ELEMENT_ARRAY_BUFFER,e.get(X).buffer))}function l(){return i.createVertexArray()}function c(v){return i.bindVertexArray(v)}function h(v){return i.deleteVertexArray(v)}function u(v,I,G){let O=G.wireframe===!0,X=n[v.id];X===void 0&&(X={},n[v.id]=X);let Y=X[I.id];Y===void 0&&(Y={},X[I.id]=Y);let V=Y[O];return V===void 0&&(V=d(l()),Y[O]=V),V}function d(v){let I=[],G=[],O=[];for(let X=0;X<t;X++)I[X]=0,G[X]=0,O[X]=0;return{geometry:null,program:null,wireframe:!1,newAttributes:I,enabledAttributes:G,attributeDivisors:O,object:v,attributes:{},index:null}}function f(v,I,G,O){let X=r.attributes,Y=I.attributes,V=0,Q=G.getAttributes();for(let B in Q)if(Q[B].location>=0){let j=X[B],ie=Y[B];if(ie===void 0&&(B==="instanceMatrix"&&v.instanceMatrix&&(ie=v.instanceMatrix),B==="instanceColor"&&v.instanceColor&&(ie=v.instanceColor)),j===void 0||j.attribute!==ie||ie&&j.data!==ie.data)return!0;V++}return r.attributesNum!==V||r.index!==O}function g(v,I,G,O){let X={},Y=I.attributes,V=0,Q=G.getAttributes();for(let B in Q)if(Q[B].location>=0){let j=Y[B];j===void 0&&(B==="instanceMatrix"&&v.instanceMatrix&&(j=v.instanceMatrix),B==="instanceColor"&&v.instanceColor&&(j=v.instanceColor));let ie={};ie.attribute=j,j&&j.data&&(ie.data=j.data),X[B]=ie,V++}r.attributes=X,r.attributesNum=V,r.index=O}function _(){let v=r.newAttributes;for(let I=0,G=v.length;I<G;I++)v[I]=0}function m(v){p(v,0)}function p(v,I){let G=r.newAttributes,O=r.enabledAttributes,X=r.attributeDivisors;G[v]=1,O[v]===0&&(i.enableVertexAttribArray(v),O[v]=1),X[v]!==I&&(i.vertexAttribDivisor(v,I),X[v]=I)}function w(){let v=r.newAttributes,I=r.enabledAttributes;for(let G=0,O=I.length;G<O;G++)I[G]!==v[G]&&(i.disableVertexAttribArray(G),I[G]=0)}function b(v,I,G,O,X,Y,V){V===!0?i.vertexAttribIPointer(v,I,G,X,Y):i.vertexAttribPointer(v,I,G,O,X,Y)}function x(v,I,G,O){_();let X=O.attributes,Y=G.getAttributes(),V=I.defaultAttributeValues;for(let Q in Y){let B=Y[Q];if(B.location>=0){let H=X[Q];if(H===void 0&&(Q==="instanceMatrix"&&v.instanceMatrix&&(H=v.instanceMatrix),Q==="instanceColor"&&v.instanceColor&&(H=v.instanceColor)),H!==void 0){let j=H.normalized,ie=H.itemSize,Te=e.get(H);if(Te===void 0)continue;let Re=Te.buffer,q=Te.type,ee=Te.bytesPerElement,me=q===i.INT||q===i.UNSIGNED_INT||H.gpuType===Cl;if(H.isInterleavedBufferAttribute){let se=H.data,Me=se.stride,Pe=H.offset;if(se.isInstancedInterleavedBuffer){for(let Be=0;Be<B.locationSize;Be++)p(B.location+Be,se.meshPerAttribute);v.isInstancedMesh!==!0&&O._maxInstanceCount===void 0&&(O._maxInstanceCount=se.meshPerAttribute*se.count)}else for(let Be=0;Be<B.locationSize;Be++)m(B.location+Be);i.bindBuffer(i.ARRAY_BUFFER,Re);for(let Be=0;Be<B.locationSize;Be++)b(B.location+Be,ie/B.locationSize,q,j,Me*ee,(Pe+ie/B.locationSize*Be)*ee,me)}else{if(H.isInstancedBufferAttribute){for(let se=0;se<B.locationSize;se++)p(B.location+se,H.meshPerAttribute);v.isInstancedMesh!==!0&&O._maxInstanceCount===void 0&&(O._maxInstanceCount=H.meshPerAttribute*H.count)}else for(let se=0;se<B.locationSize;se++)m(B.location+se);i.bindBuffer(i.ARRAY_BUFFER,Re);for(let se=0;se<B.locationSize;se++)b(B.location+se,ie/B.locationSize,q,j,ie*ee,ie/B.locationSize*se*ee,me)}}else if(V!==void 0){let j=V[Q];if(j!==void 0)switch(j.length){case 2:i.vertexAttrib2fv(B.location,j);break;case 3:i.vertexAttrib3fv(B.location,j);break;case 4:i.vertexAttrib4fv(B.location,j);break;default:i.vertexAttrib1fv(B.location,j)}}}}w()}function P(){R();for(let v in n){let I=n[v];for(let G in I){let O=I[G];for(let X in O)h(O[X].object),delete O[X];delete I[G]}delete n[v]}}function T(v){if(n[v.id]===void 0)return;let I=n[v.id];for(let G in I){let O=I[G];for(let X in O)h(O[X].object),delete O[X];delete I[G]}delete n[v.id]}function A(v){for(let I in n){let G=n[I];if(G[v.id]===void 0)continue;let O=G[v.id];for(let X in O)h(O[X].object),delete O[X];delete G[v.id]}}function R(){M(),o=!0,r!==s&&(r=s,c(r.object))}function M(){s.geometry=null,s.program=null,s.wireframe=!1}return{setup:a,reset:R,resetDefaultState:M,dispose:P,releaseStatesOfGeometry:T,releaseStatesOfProgram:A,initAttributes:_,enableAttribute:m,disableUnusedAttributes:w}}function i0(i,e,t){let n;function s(c){n=c}function r(c,h){i.drawArrays(n,c,h),t.update(h,n,1)}function o(c,h,u){u!==0&&(i.drawArraysInstanced(n,c,h,u),t.update(h,n,u))}function a(c,h,u){if(u===0)return;e.get("WEBGL_multi_draw").multiDrawArraysWEBGL(n,c,0,h,0,u);let f=0;for(let g=0;g<u;g++)f+=h[g];t.update(f,n,1)}function l(c,h,u,d){if(u===0)return;let f=e.get("WEBGL_multi_draw");if(f===null)for(let g=0;g<c.length;g++)o(c[g],h[g],d[g]);else{f.multiDrawArraysInstancedWEBGL(n,c,0,h,0,d,0,u);let g=0;for(let _=0;_<u;_++)g+=h[_]*d[_];t.update(g,n,1)}}this.setMode=s,this.render=r,this.renderInstances=o,this.renderMultiDraw=a,this.renderMultiDrawInstances=l}function s0(i,e,t,n){let s;function r(){if(s!==void 0)return s;if(e.has("EXT_texture_filter_anisotropic")===!0){let A=e.get("EXT_texture_filter_anisotropic");s=i.getParameter(A.MAX_TEXTURE_MAX_ANISOTROPY_EXT)}else s=0;return s}function o(A){return!(A!==on&&n.convert(A)!==i.getParameter(i.IMPLEMENTATION_COLOR_READ_FORMAT))}function a(A){let R=A===tr&&(e.has("EXT_color_buffer_half_float")||e.has("EXT_color_buffer_float"));return!(A!==Vn&&n.convert(A)!==i.getParameter(i.IMPLEMENTATION_COLOR_READ_TYPE)&&A!==xn&&!R)}function l(A){if(A==="highp"){if(i.getShaderPrecisionFormat(i.VERTEX_SHADER,i.HIGH_FLOAT).precision>0&&i.getShaderPrecisionFormat(i.FRAGMENT_SHADER,i.HIGH_FLOAT).precision>0)return"highp";A="mediump"}return A==="mediump"&&i.getShaderPrecisionFormat(i.VERTEX_SHADER,i.MEDIUM_FLOAT).precision>0&&i.getShaderPrecisionFormat(i.FRAGMENT_SHADER,i.MEDIUM_FLOAT).precision>0?"mediump":"lowp"}let c=t.precision!==void 0?t.precision:"highp",h=l(c);h!==c&&(console.warn("THREE.WebGLRenderer:",c,"not supported, using",h,"instead."),c=h);let u=t.logarithmicDepthBuffer===!0,d=t.reverseDepthBuffer===!0&&e.has("EXT_clip_control"),f=i.getParameter(i.MAX_TEXTURE_IMAGE_UNITS),g=i.getParameter(i.MAX_VERTEX_TEXTURE_IMAGE_UNITS),_=i.getParameter(i.MAX_TEXTURE_SIZE),m=i.getParameter(i.MAX_CUBE_MAP_TEXTURE_SIZE),p=i.getParameter(i.MAX_VERTEX_ATTRIBS),w=i.getParameter(i.MAX_VERTEX_UNIFORM_VECTORS),b=i.getParameter(i.MAX_VARYING_VECTORS),x=i.getParameter(i.MAX_FRAGMENT_UNIFORM_VECTORS),P=g>0,T=i.getParameter(i.MAX_SAMPLES);return{isWebGL2:!0,getMaxAnisotropy:r,getMaxPrecision:l,textureFormatReadable:o,textureTypeReadable:a,precision:c,logarithmicDepthBuffer:u,reverseDepthBuffer:d,maxTextures:f,maxVertexTextures:g,maxTextureSize:_,maxCubemapSize:m,maxAttributes:p,maxVertexUniforms:w,maxVaryings:b,maxFragmentUniforms:x,vertexTextures:P,maxSamples:T}}function r0(i){let e=this,t=null,n=0,s=!1,r=!1,o=new Kt,a=new Ne,l={value:null,needsUpdate:!1};this.uniform=l,this.numPlanes=0,this.numIntersection=0,this.init=function(u,d){let f=u.length!==0||d||n!==0||s;return s=d,n=u.length,f},this.beginShadows=function(){r=!0,h(null)},this.endShadows=function(){r=!1},this.setGlobalState=function(u,d){t=h(u,d,0)},this.setState=function(u,d,f){let g=u.clippingPlanes,_=u.clipIntersection,m=u.clipShadows,p=i.get(u);if(!s||g===null||g.length===0||r&&!m)r?h(null):c();else{let w=r?0:n,b=w*4,x=p.clippingState||null;l.value=x,x=h(g,d,b,f);for(let P=0;P!==b;++P)x[P]=t[P];p.clippingState=x,this.numIntersection=_?this.numPlanes:0,this.numPlanes+=w}};function c(){l.value!==t&&(l.value=t,l.needsUpdate=n>0),e.numPlanes=n,e.numIntersection=0}function h(u,d,f,g){let _=u!==null?u.length:0,m=null;if(_!==0){if(m=l.value,g!==!0||m===null){let p=f+_*4,w=d.matrixWorldInverse;a.getNormalMatrix(w),(m===null||m.length<p)&&(m=new Float32Array(p));for(let b=0,x=f;b!==_;++b,x+=4)o.copy(u[b]).applyMatrix4(w,a),o.normal.toArray(m,x),m[x+3]=o.constant}l.value=m,l.needsUpdate=!0}return e.numPlanes=_,e.numIntersection=0,m}}function o0(i){let e=new WeakMap;function t(o,a){return a===Ma?o.mapping=cs:a===Sa&&(o.mapping=hs),o}function n(o){if(o&&o.isTexture){let a=o.mapping;if(a===Ma||a===Sa)if(e.has(o)){let l=e.get(o).texture;return t(l,o.mapping)}else{let l=o.image;if(l&&l.height>0){let c=new el(l.height);return c.fromEquirectangularTexture(i,o),e.set(o,c),o.addEventListener("dispose",s),t(c.texture,o.mapping)}else return null}}return o}function s(o){let a=o.target;a.removeEventListener("dispose",s);let l=e.get(a);l!==void 0&&(e.delete(a),l.dispose())}function r(){e=new WeakMap}return{get:n,dispose:r}}var _s=class extends jr{constructor(e=-1,t=1,n=1,s=-1,r=.1,o=2e3){super(),this.isOrthographicCamera=!0,this.type="OrthographicCamera",this.zoom=1,this.view=null,this.left=e,this.right=t,this.top=n,this.bottom=s,this.near=r,this.far=o,this.updateProjectionMatrix()}copy(e,t){return super.copy(e,t),this.left=e.left,this.right=e.right,this.top=e.top,this.bottom=e.bottom,this.near=e.near,this.far=e.far,this.zoom=e.zoom,this.view=e.view===null?null:Object.assign({},e.view),this}setViewOffset(e,t,n,s,r,o){this.view===null&&(this.view={enabled:!0,fullWidth:1,fullHeight:1,offsetX:0,offsetY:0,width:1,height:1}),this.view.enabled=!0,this.view.fullWidth=e,this.view.fullHeight=t,this.view.offsetX=n,this.view.offsetY=s,this.view.width=r,this.view.height=o,this.updateProjectionMatrix()}clearViewOffset(){this.view!==null&&(this.view.enabled=!1),this.updateProjectionMatrix()}updateProjectionMatrix(){let e=(this.right-this.left)/(2*this.zoom),t=(this.top-this.bottom)/(2*this.zoom),n=(this.right+this.left)/2,s=(this.top+this.bottom)/2,r=n-e,o=n+e,a=s+t,l=s-t;if(this.view!==null&&this.view.enabled){let c=(this.right-this.left)/this.view.fullWidth/this.zoom,h=(this.top-this.bottom)/this.view.fullHeight/this.zoom;r+=c*this.view.offsetX,o=r+c*this.view.width,a-=h*this.view.offsetY,l=a-h*this.view.height}this.projectionMatrix.makeOrthographic(r,o,a,l,this.near,this.far,this.coordinateSystem),this.projectionMatrixInverse.copy(this.projectionMatrix).invert()}toJSON(e){let t=super.toJSON(e);return t.object.zoom=this.zoom,t.object.left=this.left,t.object.right=this.right,t.object.top=this.top,t.object.bottom=this.bottom,t.object.near=this.near,t.object.far=this.far,this.view!==null&&(t.object.view=Object.assign({},this.view)),t}},ns=4,fh=[.125,.215,.35,.446,.526,.582],Ii=20,ea=new _s,ph=new Ae,ta=null,na=0,ia=0,sa=!1,Ri=(1+Math.sqrt(5))/2,Qi=1/Ri,mh=[new C(-Ri,Qi,0),new C(Ri,Qi,0),new C(-Qi,0,Ri),new C(Qi,0,Ri),new C(0,Ri,-Qi),new C(0,Ri,Qi),new C(-1,1,-1),new C(1,1,-1),new C(-1,1,1),new C(1,1,1)],xs=class{constructor(e){this._renderer=e,this._pingPongRenderTarget=null,this._lodMax=0,this._cubeSize=0,this._lodPlanes=[],this._sizeLods=[],this._sigmas=[],this._blurMaterial=null,this._cubemapMaterial=null,this._equirectMaterial=null,this._compileMaterial(this._blurMaterial)}fromScene(e,t=0,n=.1,s=100){ta=this._renderer.getRenderTarget(),na=this._renderer.getActiveCubeFace(),ia=this._renderer.getActiveMipmapLevel(),sa=this._renderer.xr.enabled,this._renderer.xr.enabled=!1,this._setSize(256);let r=this._allocateTargets();return r.depthBuffer=!0,this._sceneToCubeUV(e,n,s,r),t>0&&this._blur(r,0,0,t),this._applyPMREM(r),this._cleanup(r),r}fromEquirectangular(e,t=null){return this._fromTexture(e,t)}fromCubemap(e,t=null){return this._fromTexture(e,t)}compileCubemapShader(){this._cubemapMaterial===null&&(this._cubemapMaterial=xh(),this._compileMaterial(this._cubemapMaterial))}compileEquirectangularShader(){this._equirectMaterial===null&&(this._equirectMaterial=_h(),this._compileMaterial(this._equirectMaterial))}dispose(){this._dispose(),this._cubemapMaterial!==null&&this._cubemapMaterial.dispose(),this._equirectMaterial!==null&&this._equirectMaterial.dispose()}_setSize(e){this._lodMax=Math.floor(Math.log2(e)),this._cubeSize=Math.pow(2,this._lodMax)}_dispose(){this._blurMaterial!==null&&this._blurMaterial.dispose(),this._pingPongRenderTarget!==null&&this._pingPongRenderTarget.dispose();for(let e=0;e<this._lodPlanes.length;e++)this._lodPlanes[e].dispose()}_cleanup(e){this._renderer.setRenderTarget(ta,na,ia),this._renderer.xr.enabled=sa,e.scissorTest=!1,Rr(e,0,0,e.width,e.height)}_fromTexture(e,t){e.mapping===cs||e.mapping===hs?this._setSize(e.image.length===0?16:e.image[0].width||e.image[0].image.width):this._setSize(e.image.width/4),ta=this._renderer.getRenderTarget(),na=this._renderer.getActiveCubeFace(),ia=this._renderer.getActiveMipmapLevel(),sa=this._renderer.xr.enabled,this._renderer.xr.enabled=!1;let n=t||this._allocateTargets();return this._textureToCubeUV(e,n),this._applyPMREM(n),this._cleanup(n),n}_allocateTargets(){let e=3*Math.max(this._cubeSize,112),t=4*this._cubeSize,n={magFilter:Vt,minFilter:Vt,generateMipmaps:!1,type:tr,format:on,colorSpace:Ft,depthBuffer:!1},s=gh(e,t,n);if(this._pingPongRenderTarget===null||this._pingPongRenderTarget.width!==e||this._pingPongRenderTarget.height!==t){this._pingPongRenderTarget!==null&&this._dispose(),this._pingPongRenderTarget=gh(e,t,n);let{_lodMax:r}=this;({sizeLods:this._sizeLods,lodPlanes:this._lodPlanes,sigmas:this._sigmas}=a0(r)),this._blurMaterial=l0(r,e,t)}return s}_compileMaterial(e){let t=new tt(this._lodPlanes[0],e);this._renderer.compile(t,ea)}_sceneToCubeUV(e,t,n,s){let a=new xt(90,1,t,n),l=[1,-1,1,1,1,1],c=[1,1,1,-1,-1,-1],h=this._renderer,u=h.autoClear,d=h.toneMapping;h.getClearColor(ph),h.toneMapping=di,h.autoClear=!1;let f=new an({name:"PMREM.Background",side:Ut,depthWrite:!1,depthTest:!1}),g=new tt(new qn,f),_=!1,m=e.background;m?m.isColor&&(f.color.copy(m),e.background=null,_=!0):(f.color.copy(ph),_=!0);for(let p=0;p<6;p++){let w=p%3;w===0?(a.up.set(0,l[p],0),a.lookAt(c[p],0,0)):w===1?(a.up.set(0,0,l[p]),a.lookAt(0,c[p],0)):(a.up.set(0,l[p],0),a.lookAt(0,0,c[p]));let b=this._cubeSize;Rr(s,w*b,p>2?b:0,b,b),h.setRenderTarget(s),_&&h.render(g,a),h.render(e,a)}g.geometry.dispose(),g.material.dispose(),h.toneMapping=d,h.autoClear=u,e.background=m}_textureToCubeUV(e,t){let n=this._renderer,s=e.mapping===cs||e.mapping===hs;s?(this._cubemapMaterial===null&&(this._cubemapMaterial=xh()),this._cubemapMaterial.uniforms.flipEnvMap.value=e.isRenderTargetTexture===!1?-1:1):this._equirectMaterial===null&&(this._equirectMaterial=_h());let r=s?this._cubemapMaterial:this._equirectMaterial,o=new tt(this._lodPlanes[0],r),a=r.uniforms;a.envMap.value=e;let l=this._cubeSize;Rr(t,0,0,3*l,2*l),n.setRenderTarget(t),n.render(o,ea)}_applyPMREM(e){let t=this._renderer,n=t.autoClear;t.autoClear=!1;let s=this._lodPlanes.length;for(let r=1;r<s;r++){let o=Math.sqrt(this._sigmas[r]*this._sigmas[r]-this._sigmas[r-1]*this._sigmas[r-1]),a=mh[(s-r-1)%mh.length];this._blur(e,r-1,r,o,a)}t.autoClear=n}_blur(e,t,n,s,r){let o=this._pingPongRenderTarget;this._halfBlur(e,o,t,n,s,"latitudinal",r),this._halfBlur(o,e,n,n,s,"longitudinal",r)}_halfBlur(e,t,n,s,r,o,a){let l=this._renderer,c=this._blurMaterial;o!=="latitudinal"&&o!=="longitudinal"&&console.error("blur direction must be either latitudinal or longitudinal!");let h=3,u=new tt(this._lodPlanes[s],c),d=c.uniforms,f=this._sizeLods[n]-1,g=isFinite(r)?Math.PI/(2*f):2*Math.PI/(2*Ii-1),_=r/g,m=isFinite(r)?1+Math.floor(h*_):Ii;m>Ii&&console.warn(`sigmaRadians, ${r}, is too large and will clip, as it requested ${m} samples when the maximum is set to ${Ii}`);let p=[],w=0;for(let A=0;A<Ii;++A){let R=A/_,M=Math.exp(-R*R/2);p.push(M),A===0?w+=M:A<m&&(w+=2*M)}for(let A=0;A<p.length;A++)p[A]=p[A]/w;d.envMap.value=e.texture,d.samples.value=m,d.weights.value=p,d.latitudinal.value=o==="latitudinal",a&&(d.poleAxis.value=a);let{_lodMax:b}=this;d.dTheta.value=g,d.mipInt.value=b-n;let x=this._sizeLods[s],P=3*x*(s>b-ns?s-b+ns:0),T=4*(this._cubeSize-x);Rr(t,P,T,3*x,2*x),l.setRenderTarget(t),l.render(u,ea)}};function a0(i){let e=[],t=[],n=[],s=i,r=i-ns+1+fh.length;for(let o=0;o<r;o++){let a=Math.pow(2,s);t.push(a);let l=1/a;o>i-ns?l=fh[o-i+ns-1]:o===0&&(l=0),n.push(l);let c=1/(a-2),h=-c,u=1+c,d=[h,h,u,h,u,u,h,h,u,u,h,u],f=6,g=6,_=3,m=2,p=1,w=new Float32Array(_*g*f),b=new Float32Array(m*g*f),x=new Float32Array(p*g*f);for(let T=0;T<f;T++){let A=T%3*2/3-1,R=T>2?0:-1,M=[A,R,0,A+2/3,R,0,A+2/3,R+1,0,A,R,0,A+2/3,R+1,0,A,R+1,0];w.set(M,_*g*T),b.set(d,m*g*T);let v=[T,T,T,T,T,T];x.set(v,p*g*T)}let P=new yt;P.setAttribute("position",new pt(w,_)),P.setAttribute("uv",new pt(b,m)),P.setAttribute("faceIndex",new pt(x,p)),e.push(P),s>ns&&s--}return{lodPlanes:e,sizeLods:t,sigmas:n}}function gh(i,e,t){let n=new Wn(i,e,t);return n.texture.mapping=bo,n.texture.name="PMREM.cubeUv",n.scissorTest=!0,n}function Rr(i,e,t,n,s){i.viewport.set(e,t,n,s),i.scissor.set(e,t,n,s)}function l0(i,e,t){let n=new Float32Array(Ii),s=new C(0,1,0);return new ln({name:"SphericalGaussianBlur",defines:{n:Ii,CUBEUV_TEXEL_WIDTH:1/e,CUBEUV_TEXEL_HEIGHT:1/t,CUBEUV_MAX_MIP:`${i}.0`},uniforms:{envMap:{value:null},samples:{value:1},weights:{value:n},latitudinal:{value:!1},dTheta:{value:0},mipInt:{value:0},poleAxis:{value:s}},vertexShader:Bl(),fragmentShader:`

			precision mediump float;
			precision mediump int;

			varying vec3 vOutputDirection;

			uniform sampler2D envMap;
			uniform int samples;
			uniform float weights[ n ];
			uniform bool latitudinal;
			uniform float dTheta;
			uniform float mipInt;
			uniform vec3 poleAxis;

			#define ENVMAP_TYPE_CUBE_UV
			#include <cube_uv_reflection_fragment>

			vec3 getSample( float theta, vec3 axis ) {

				float cosTheta = cos( theta );
				// Rodrigues' axis-angle rotation
				vec3 sampleDirection = vOutputDirection * cosTheta
					+ cross( axis, vOutputDirection ) * sin( theta )
					+ axis * dot( axis, vOutputDirection ) * ( 1.0 - cosTheta );

				return bilinearCubeUV( envMap, sampleDirection, mipInt );

			}

			void main() {

				vec3 axis = latitudinal ? poleAxis : cross( poleAxis, vOutputDirection );

				if ( all( equal( axis, vec3( 0.0 ) ) ) ) {

					axis = vec3( vOutputDirection.z, 0.0, - vOutputDirection.x );

				}

				axis = normalize( axis );

				gl_FragColor = vec4( 0.0, 0.0, 0.0, 1.0 );
				gl_FragColor.rgb += weights[ 0 ] * getSample( 0.0, axis );

				for ( int i = 1; i < n; i++ ) {

					if ( i >= samples ) {

						break;

					}

					float theta = dTheta * float( i );
					gl_FragColor.rgb += weights[ i ] * getSample( -1.0 * theta, axis );
					gl_FragColor.rgb += weights[ i ] * getSample( theta, axis );

				}

			}
		`,blending:ui,depthTest:!1,depthWrite:!1})}function _h(){return new ln({name:"EquirectangularToCubeUV",uniforms:{envMap:{value:null}},vertexShader:Bl(),fragmentShader:`

			precision mediump float;
			precision mediump int;

			varying vec3 vOutputDirection;

			uniform sampler2D envMap;

			#include <common>

			void main() {

				vec3 outputDirection = normalize( vOutputDirection );
				vec2 uv = equirectUv( outputDirection );

				gl_FragColor = vec4( texture2D ( envMap, uv ).rgb, 1.0 );

			}
		`,blending:ui,depthTest:!1,depthWrite:!1})}function xh(){return new ln({name:"CubemapToCubeUV",uniforms:{envMap:{value:null},flipEnvMap:{value:-1}},vertexShader:Bl(),fragmentShader:`

			precision mediump float;
			precision mediump int;

			uniform float flipEnvMap;

			varying vec3 vOutputDirection;

			uniform samplerCube envMap;

			void main() {

				gl_FragColor = textureCube( envMap, vec3( flipEnvMap * vOutputDirection.x, vOutputDirection.yz ) );

			}
		`,blending:ui,depthTest:!1,depthWrite:!1})}function Bl(){return`

		precision mediump float;
		precision mediump int;

		attribute float faceIndex;

		varying vec3 vOutputDirection;

		// RH coordinate system; PMREM face-indexing convention
		vec3 getDirection( vec2 uv, float face ) {

			uv = 2.0 * uv - 1.0;

			vec3 direction = vec3( uv, 1.0 );

			if ( face == 0.0 ) {

				direction = direction.zyx; // ( 1, v, u ) pos x

			} else if ( face == 1.0 ) {

				direction = direction.xzy;
				direction.xz *= -1.0; // ( -u, 1, -v ) pos y

			} else if ( face == 2.0 ) {

				direction.x *= -1.0; // ( -u, v, 1 ) pos z

			} else if ( face == 3.0 ) {

				direction = direction.zyx;
				direction.xz *= -1.0; // ( -1, v, -u ) neg x

			} else if ( face == 4.0 ) {

				direction = direction.xzy;
				direction.xy *= -1.0; // ( -u, -1, v ) neg y

			} else if ( face == 5.0 ) {

				direction.z *= -1.0; // ( u, v, -1 ) neg z

			}

			return direction;

		}

		void main() {

			vOutputDirection = getDirection( uv, faceIndex );
			gl_Position = vec4( position, 1.0 );

		}
	`}function c0(i){let e=new WeakMap,t=null;function n(a){if(a&&a.isTexture){let l=a.mapping,c=l===Ma||l===Sa,h=l===cs||l===hs;if(c||h){let u=e.get(a),d=u!==void 0?u.texture.pmremVersion:0;if(a.isRenderTargetTexture&&a.pmremVersion!==d)return t===null&&(t=new xs(i)),u=c?t.fromEquirectangular(a,u):t.fromCubemap(a,u),u.texture.pmremVersion=a.pmremVersion,e.set(a,u),u.texture;if(u!==void 0)return u.texture;{let f=a.image;return c&&f&&f.height>0||h&&f&&s(f)?(t===null&&(t=new xs(i)),u=c?t.fromEquirectangular(a):t.fromCubemap(a),u.texture.pmremVersion=a.pmremVersion,e.set(a,u),a.addEventListener("dispose",r),u.texture):null}}}return a}function s(a){let l=0,c=6;for(let h=0;h<c;h++)a[h]!==void 0&&l++;return l===c}function r(a){let l=a.target;l.removeEventListener("dispose",r);let c=e.get(l);c!==void 0&&(e.delete(l),c.dispose())}function o(){e=new WeakMap,t!==null&&(t.dispose(),t=null)}return{get:n,dispose:o}}function h0(i){let e={};function t(n){if(e[n]!==void 0)return e[n];let s;switch(n){case"WEBGL_depth_texture":s=i.getExtension("WEBGL_depth_texture")||i.getExtension("MOZ_WEBGL_depth_texture")||i.getExtension("WEBKIT_WEBGL_depth_texture");break;case"EXT_texture_filter_anisotropic":s=i.getExtension("EXT_texture_filter_anisotropic")||i.getExtension("MOZ_EXT_texture_filter_anisotropic")||i.getExtension("WEBKIT_EXT_texture_filter_anisotropic");break;case"WEBGL_compressed_texture_s3tc":s=i.getExtension("WEBGL_compressed_texture_s3tc")||i.getExtension("MOZ_WEBGL_compressed_texture_s3tc")||i.getExtension("WEBKIT_WEBGL_compressed_texture_s3tc");break;case"WEBGL_compressed_texture_pvrtc":s=i.getExtension("WEBGL_compressed_texture_pvrtc")||i.getExtension("WEBKIT_WEBGL_compressed_texture_pvrtc");break;default:s=i.getExtension(n)}return e[n]=s,s}return{has:function(n){return t(n)!==null},init:function(){t("EXT_color_buffer_float"),t("WEBGL_clip_cull_distance"),t("OES_texture_float_linear"),t("EXT_color_buffer_half_float"),t("WEBGL_multisampled_render_to_texture"),t("WEBGL_render_shared_exponent")},get:function(n){let s=t(n);return s===null&&Fs("THREE.WebGLRenderer: "+n+" extension not supported."),s}}}function u0(i,e,t,n){let s={},r=new WeakMap;function o(u){let d=u.target;d.index!==null&&e.remove(d.index);for(let g in d.attributes)e.remove(d.attributes[g]);for(let g in d.morphAttributes){let _=d.morphAttributes[g];for(let m=0,p=_.length;m<p;m++)e.remove(_[m])}d.removeEventListener("dispose",o),delete s[d.id];let f=r.get(d);f&&(e.remove(f),r.delete(d)),n.releaseStatesOfGeometry(d),d.isInstancedBufferGeometry===!0&&delete d._maxInstanceCount,t.memory.geometries--}function a(u,d){return s[d.id]===!0||(d.addEventListener("dispose",o),s[d.id]=!0,t.memory.geometries++),d}function l(u){let d=u.attributes;for(let g in d)e.update(d[g],i.ARRAY_BUFFER);let f=u.morphAttributes;for(let g in f){let _=f[g];for(let m=0,p=_.length;m<p;m++)e.update(_[m],i.ARRAY_BUFFER)}}function c(u){let d=[],f=u.index,g=u.attributes.position,_=0;if(f!==null){let w=f.array;_=f.version;for(let b=0,x=w.length;b<x;b+=3){let P=w[b+0],T=w[b+1],A=w[b+2];d.push(P,T,T,A,A,P)}}else if(g!==void 0){let w=g.array;_=g.version;for(let b=0,x=w.length/3-1;b<x;b+=3){let P=b+0,T=b+1,A=b+2;d.push(P,T,T,A,A,P)}}else return;let m=new(xu(d)?Jr:Kr)(d,1);m.version=_;let p=r.get(u);p&&e.remove(p),r.set(u,m)}function h(u){let d=r.get(u);if(d){let f=u.index;f!==null&&d.version<f.version&&c(u)}else c(u);return r.get(u)}return{get:a,update:l,getWireframeAttribute:h}}function d0(i,e,t){let n;function s(d){n=d}let r,o;function a(d){r=d.type,o=d.bytesPerElement}function l(d,f){i.drawElements(n,f,r,d*o),t.update(f,n,1)}function c(d,f,g){g!==0&&(i.drawElementsInstanced(n,f,r,d*o,g),t.update(f,n,g))}function h(d,f,g){if(g===0)return;e.get("WEBGL_multi_draw").multiDrawElementsWEBGL(n,f,0,r,d,0,g);let m=0;for(let p=0;p<g;p++)m+=f[p];t.update(m,n,1)}function u(d,f,g,_){if(g===0)return;let m=e.get("WEBGL_multi_draw");if(m===null)for(let p=0;p<d.length;p++)c(d[p]/o,f[p],_[p]);else{m.multiDrawElementsInstancedWEBGL(n,f,0,r,d,0,_,0,g);let p=0;for(let w=0;w<g;w++)p+=f[w]*_[w];t.update(p,n,1)}}this.setMode=s,this.setIndex=a,this.render=l,this.renderInstances=c,this.renderMultiDraw=h,this.renderMultiDrawInstances=u}function f0(i){let e={geometries:0,textures:0},t={frame:0,calls:0,triangles:0,points:0,lines:0};function n(r,o,a){switch(t.calls++,o){case i.TRIANGLES:t.triangles+=a*(r/3);break;case i.LINES:t.lines+=a*(r/2);break;case i.LINE_STRIP:t.lines+=a*(r-1);break;case i.LINE_LOOP:t.lines+=a*r;break;case i.POINTS:t.points+=a*r;break;default:console.error("THREE.WebGLInfo: Unknown draw mode:",o);break}}function s(){t.calls=0,t.triangles=0,t.points=0,t.lines=0}return{memory:e,render:t,programs:null,autoReset:!0,reset:s,update:n}}function p0(i,e,t){let n=new WeakMap,s=new Ye;function r(o,a,l){let c=o.morphTargetInfluences,h=a.morphAttributes.position||a.morphAttributes.normal||a.morphAttributes.color,u=h!==void 0?h.length:0,d=n.get(a);if(d===void 0||d.count!==u){let M=function(){A.dispose(),n.delete(a),a.removeEventListener("dispose",M)};d!==void 0&&d.texture.dispose();let f=a.morphAttributes.position!==void 0,g=a.morphAttributes.normal!==void 0,_=a.morphAttributes.color!==void 0,m=a.morphAttributes.position||[],p=a.morphAttributes.normal||[],w=a.morphAttributes.color||[],b=0;f===!0&&(b=1),g===!0&&(b=2),_===!0&&(b=3);let x=a.attributes.position.count*b,P=1;x>e.maxTextureSize&&(P=Math.ceil(x/e.maxTextureSize),x=e.maxTextureSize);let T=new Float32Array(x*P*4*u),A=new Zr(T,x,P,u);A.type=xn,A.needsUpdate=!0;let R=b*4;for(let v=0;v<u;v++){let I=m[v],G=p[v],O=w[v],X=x*P*4*v;for(let Y=0;Y<I.count;Y++){let V=Y*R;f===!0&&(s.fromBufferAttribute(I,Y),T[X+V+0]=s.x,T[X+V+1]=s.y,T[X+V+2]=s.z,T[X+V+3]=0),g===!0&&(s.fromBufferAttribute(G,Y),T[X+V+4]=s.x,T[X+V+5]=s.y,T[X+V+6]=s.z,T[X+V+7]=0),_===!0&&(s.fromBufferAttribute(O,Y),T[X+V+8]=s.x,T[X+V+9]=s.y,T[X+V+10]=s.z,T[X+V+11]=O.itemSize===4?s.w:1)}}d={count:u,texture:A,size:new we(x,P)},n.set(a,d),a.addEventListener("dispose",M)}if(o.isInstancedMesh===!0&&o.morphTexture!==null)l.getUniforms().setValue(i,"morphTexture",o.morphTexture,t);else{let f=0;for(let _=0;_<c.length;_++)f+=c[_];let g=a.morphTargetsRelative?1:1-f;l.getUniforms().setValue(i,"morphTargetBaseInfluence",g),l.getUniforms().setValue(i,"morphTargetInfluences",c)}l.getUniforms().setValue(i,"morphTargetsTexture",d.texture,t),l.getUniforms().setValue(i,"morphTargetsTextureSize",d.size)}return{update:r}}function m0(i,e,t,n){let s=new WeakMap;function r(l){let c=n.render.frame,h=l.geometry,u=e.get(l,h);if(s.get(u)!==c&&(e.update(u),s.set(u,c)),l.isInstancedMesh&&(l.hasEventListener("dispose",a)===!1&&l.addEventListener("dispose",a),s.get(l)!==c&&(t.update(l.instanceMatrix,i.ARRAY_BUFFER),l.instanceColor!==null&&t.update(l.instanceColor,i.ARRAY_BUFFER),s.set(l,c))),l.isSkinnedMesh){let d=l.skeleton;s.get(d)!==c&&(d.update(),s.set(d,c))}return u}function o(){s=new WeakMap}function a(l){let c=l.target;c.removeEventListener("dispose",a),t.remove(c.instanceMatrix),c.instanceColor!==null&&t.remove(c.instanceColor)}return{update:r,dispose:o}}var Qr=class extends Et{constructor(e,t,n,s,r,o,a,l,c,h=ss){if(h!==ss&&h!==ds)throw new Error("DepthTexture format must be either THREE.DepthFormat or THREE.DepthStencilFormat");n===void 0&&h===ss&&(n=Pi),n===void 0&&h===ds&&(n=us),super(null,s,r,o,a,l,h,n,c),this.isDepthTexture=!0,this.image={width:e,height:t},this.magFilter=a!==void 0?a:Nt,this.minFilter=l!==void 0?l:Nt,this.flipY=!1,this.generateMipmaps=!1,this.compareFunction=null}copy(e){return super.copy(e),this.compareFunction=e.compareFunction,this}toJSON(e){let t=super.toJSON(e);return this.compareFunction!==null&&(t.compareFunction=this.compareFunction),t}},Su=new Et,yh=new Qr(1,1),bu=new Zr,wu=new $a,Eu=new $r,vh=[],Mh=[],Sh=new Float32Array(16),bh=new Float32Array(9),wh=new Float32Array(4);function bs(i,e,t){let n=i[0];if(n<=0||n>0)return i;let s=e*t,r=vh[s];if(r===void 0&&(r=new Float32Array(s),vh[s]=r),e!==0){n.toArray(r,0);for(let o=1,a=0;o!==e;++o)a+=t,i[o].toArray(r,a)}return r}function vt(i,e){if(i.length!==e.length)return!1;for(let t=0,n=i.length;t<n;t++)if(i[t]!==e[t])return!1;return!0}function Mt(i,e){for(let t=0,n=e.length;t<n;t++)i[t]=e[t]}function Ao(i,e){let t=Mh[e];t===void 0&&(t=new Int32Array(e),Mh[e]=t);for(let n=0;n!==e;++n)t[n]=i.allocateTextureUnit();return t}function g0(i,e){let t=this.cache;t[0]!==e&&(i.uniform1f(this.addr,e),t[0]=e)}function _0(i,e){let t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y)&&(i.uniform2f(this.addr,e.x,e.y),t[0]=e.x,t[1]=e.y);else{if(vt(t,e))return;i.uniform2fv(this.addr,e),Mt(t,e)}}function x0(i,e){let t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y||t[2]!==e.z)&&(i.uniform3f(this.addr,e.x,e.y,e.z),t[0]=e.x,t[1]=e.y,t[2]=e.z);else if(e.r!==void 0)(t[0]!==e.r||t[1]!==e.g||t[2]!==e.b)&&(i.uniform3f(this.addr,e.r,e.g,e.b),t[0]=e.r,t[1]=e.g,t[2]=e.b);else{if(vt(t,e))return;i.uniform3fv(this.addr,e),Mt(t,e)}}function y0(i,e){let t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y||t[2]!==e.z||t[3]!==e.w)&&(i.uniform4f(this.addr,e.x,e.y,e.z,e.w),t[0]=e.x,t[1]=e.y,t[2]=e.z,t[3]=e.w);else{if(vt(t,e))return;i.uniform4fv(this.addr,e),Mt(t,e)}}function v0(i,e){let t=this.cache,n=e.elements;if(n===void 0){if(vt(t,e))return;i.uniformMatrix2fv(this.addr,!1,e),Mt(t,e)}else{if(vt(t,n))return;wh.set(n),i.uniformMatrix2fv(this.addr,!1,wh),Mt(t,n)}}function M0(i,e){let t=this.cache,n=e.elements;if(n===void 0){if(vt(t,e))return;i.uniformMatrix3fv(this.addr,!1,e),Mt(t,e)}else{if(vt(t,n))return;bh.set(n),i.uniformMatrix3fv(this.addr,!1,bh),Mt(t,n)}}function S0(i,e){let t=this.cache,n=e.elements;if(n===void 0){if(vt(t,e))return;i.uniformMatrix4fv(this.addr,!1,e),Mt(t,e)}else{if(vt(t,n))return;Sh.set(n),i.uniformMatrix4fv(this.addr,!1,Sh),Mt(t,n)}}function b0(i,e){let t=this.cache;t[0]!==e&&(i.uniform1i(this.addr,e),t[0]=e)}function w0(i,e){let t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y)&&(i.uniform2i(this.addr,e.x,e.y),t[0]=e.x,t[1]=e.y);else{if(vt(t,e))return;i.uniform2iv(this.addr,e),Mt(t,e)}}function E0(i,e){let t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y||t[2]!==e.z)&&(i.uniform3i(this.addr,e.x,e.y,e.z),t[0]=e.x,t[1]=e.y,t[2]=e.z);else{if(vt(t,e))return;i.uniform3iv(this.addr,e),Mt(t,e)}}function A0(i,e){let t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y||t[2]!==e.z||t[3]!==e.w)&&(i.uniform4i(this.addr,e.x,e.y,e.z,e.w),t[0]=e.x,t[1]=e.y,t[2]=e.z,t[3]=e.w);else{if(vt(t,e))return;i.uniform4iv(this.addr,e),Mt(t,e)}}function T0(i,e){let t=this.cache;t[0]!==e&&(i.uniform1ui(this.addr,e),t[0]=e)}function R0(i,e){let t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y)&&(i.uniform2ui(this.addr,e.x,e.y),t[0]=e.x,t[1]=e.y);else{if(vt(t,e))return;i.uniform2uiv(this.addr,e),Mt(t,e)}}function C0(i,e){let t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y||t[2]!==e.z)&&(i.uniform3ui(this.addr,e.x,e.y,e.z),t[0]=e.x,t[1]=e.y,t[2]=e.z);else{if(vt(t,e))return;i.uniform3uiv(this.addr,e),Mt(t,e)}}function I0(i,e){let t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y||t[2]!==e.z||t[3]!==e.w)&&(i.uniform4ui(this.addr,e.x,e.y,e.z,e.w),t[0]=e.x,t[1]=e.y,t[2]=e.z,t[3]=e.w);else{if(vt(t,e))return;i.uniform4uiv(this.addr,e),Mt(t,e)}}function P0(i,e,t){let n=this.cache,s=t.allocateTextureUnit();n[0]!==s&&(i.uniform1i(this.addr,s),n[0]=s);let r;this.type===i.SAMPLER_2D_SHADOW?(yh.compareFunction=_u,r=yh):r=Su,t.setTexture2D(e||r,s)}function L0(i,e,t){let n=this.cache,s=t.allocateTextureUnit();n[0]!==s&&(i.uniform1i(this.addr,s),n[0]=s),t.setTexture3D(e||wu,s)}function D0(i,e,t){let n=this.cache,s=t.allocateTextureUnit();n[0]!==s&&(i.uniform1i(this.addr,s),n[0]=s),t.setTextureCube(e||Eu,s)}function U0(i,e,t){let n=this.cache,s=t.allocateTextureUnit();n[0]!==s&&(i.uniform1i(this.addr,s),n[0]=s),t.setTexture2DArray(e||bu,s)}function N0(i){switch(i){case 5126:return g0;case 35664:return _0;case 35665:return x0;case 35666:return y0;case 35674:return v0;case 35675:return M0;case 35676:return S0;case 5124:case 35670:return b0;case 35667:case 35671:return w0;case 35668:case 35672:return E0;case 35669:case 35673:return A0;case 5125:return T0;case 36294:return R0;case 36295:return C0;case 36296:return I0;case 35678:case 36198:case 36298:case 36306:case 35682:return P0;case 35679:case 36299:case 36307:return L0;case 35680:case 36300:case 36308:case 36293:return D0;case 36289:case 36303:case 36311:case 36292:return U0}}function O0(i,e){i.uniform1fv(this.addr,e)}function F0(i,e){let t=bs(e,this.size,2);i.uniform2fv(this.addr,t)}function B0(i,e){let t=bs(e,this.size,3);i.uniform3fv(this.addr,t)}function z0(i,e){let t=bs(e,this.size,4);i.uniform4fv(this.addr,t)}function k0(i,e){let t=bs(e,this.size,4);i.uniformMatrix2fv(this.addr,!1,t)}function H0(i,e){let t=bs(e,this.size,9);i.uniformMatrix3fv(this.addr,!1,t)}function V0(i,e){let t=bs(e,this.size,16);i.uniformMatrix4fv(this.addr,!1,t)}function G0(i,e){i.uniform1iv(this.addr,e)}function W0(i,e){i.uniform2iv(this.addr,e)}function X0(i,e){i.uniform3iv(this.addr,e)}function q0(i,e){i.uniform4iv(this.addr,e)}function Y0(i,e){i.uniform1uiv(this.addr,e)}function Z0(i,e){i.uniform2uiv(this.addr,e)}function K0(i,e){i.uniform3uiv(this.addr,e)}function J0(i,e){i.uniform4uiv(this.addr,e)}function j0(i,e,t){let n=this.cache,s=e.length,r=Ao(t,s);vt(n,r)||(i.uniform1iv(this.addr,r),Mt(n,r));for(let o=0;o!==s;++o)t.setTexture2D(e[o]||Su,r[o])}function $0(i,e,t){let n=this.cache,s=e.length,r=Ao(t,s);vt(n,r)||(i.uniform1iv(this.addr,r),Mt(n,r));for(let o=0;o!==s;++o)t.setTexture3D(e[o]||wu,r[o])}function Q0(i,e,t){let n=this.cache,s=e.length,r=Ao(t,s);vt(n,r)||(i.uniform1iv(this.addr,r),Mt(n,r));for(let o=0;o!==s;++o)t.setTextureCube(e[o]||Eu,r[o])}function eg(i,e,t){let n=this.cache,s=e.length,r=Ao(t,s);vt(n,r)||(i.uniform1iv(this.addr,r),Mt(n,r));for(let o=0;o!==s;++o)t.setTexture2DArray(e[o]||bu,r[o])}function tg(i){switch(i){case 5126:return O0;case 35664:return F0;case 35665:return B0;case 35666:return z0;case 35674:return k0;case 35675:return H0;case 35676:return V0;case 5124:case 35670:return G0;case 35667:case 35671:return W0;case 35668:case 35672:return X0;case 35669:case 35673:return q0;case 5125:return Y0;case 36294:return Z0;case 36295:return K0;case 36296:return J0;case 35678:case 36198:case 36298:case 36306:case 35682:return j0;case 35679:case 36299:case 36307:return $0;case 35680:case 36300:case 36308:case 36293:return Q0;case 36289:case 36303:case 36311:case 36292:return eg}}var tl=class{constructor(e,t,n){this.id=e,this.addr=n,this.cache=[],this.type=t.type,this.setValue=N0(t.type)}},nl=class{constructor(e,t,n){this.id=e,this.addr=n,this.cache=[],this.type=t.type,this.size=t.size,this.setValue=tg(t.type)}},il=class{constructor(e){this.id=e,this.seq=[],this.map={}}setValue(e,t,n){let s=this.seq;for(let r=0,o=s.length;r!==o;++r){let a=s[r];a.setValue(e,t[a.id],n)}}},ra=/(\w+)(\])?(\[|\.)?/g;function Eh(i,e){i.seq.push(e),i.map[e.id]=e}function ng(i,e,t){let n=i.name,s=n.length;for(ra.lastIndex=0;;){let r=ra.exec(n),o=ra.lastIndex,a=r[1],l=r[2]==="]",c=r[3];if(l&&(a=a|0),c===void 0||c==="["&&o+2===s){Eh(t,c===void 0?new tl(a,i,e):new nl(a,i,e));break}else{let u=t.map[a];u===void 0&&(u=new il(a),Eh(t,u)),t=u}}}var as=class{constructor(e,t){this.seq=[],this.map={};let n=e.getProgramParameter(t,e.ACTIVE_UNIFORMS);for(let s=0;s<n;++s){let r=e.getActiveUniform(t,s),o=e.getUniformLocation(t,r.name);ng(r,o,this)}}setValue(e,t,n,s){let r=this.map[t];r!==void 0&&r.setValue(e,n,s)}setOptional(e,t,n){let s=t[n];s!==void 0&&this.setValue(e,n,s)}static upload(e,t,n,s){for(let r=0,o=t.length;r!==o;++r){let a=t[r],l=n[a.id];l.needsUpdate!==!1&&a.setValue(e,l.value,s)}}static seqWithValue(e,t){let n=[];for(let s=0,r=e.length;s!==r;++s){let o=e[s];o.id in t&&n.push(o)}return n}};function Ah(i,e,t){let n=i.createShader(e);return i.shaderSource(n,t),i.compileShader(n),n}var ig=37297,sg=0;function rg(i,e){let t=i.split(`
`),n=[],s=Math.max(e-6,0),r=Math.min(e+6,t.length);for(let o=s;o<r;o++){let a=o+1;n.push(`${a===e?">":" "} ${a}: ${t[o]}`)}return n.join(`
`)}var Th=new Ne;function og(i){ke._getMatrix(Th,ke.workingColorSpace,i);let e=`mat3( ${Th.elements.map(t=>t.toFixed(4))} )`;switch(ke.getTransfer(i)){case Eo:return[e,"LinearTransferOETF"];case Qe:return[e,"sRGBTransferOETF"];default:return console.warn("THREE.WebGLProgram: Unsupported color space: ",i),[e,"LinearTransferOETF"]}}function Rh(i,e,t){let n=i.getShaderParameter(e,i.COMPILE_STATUS),s=i.getShaderInfoLog(e).trim();if(n&&s==="")return"";let r=/ERROR: 0:(\d+)/.exec(s);if(r){let o=parseInt(r[1]);return t.toUpperCase()+`

`+s+`

`+rg(i.getShaderSource(e),o)}else return s}function ag(i,e){let t=og(e);return[`vec4 ${i}( vec4 value ) {`,`	return ${t[1]}( vec4( value.rgb * ${t[0]}, value.a ) );`,"}"].join(`
`)}function lg(i,e){let t;switch(e){case xd:t="Linear";break;case yd:t="Reinhard";break;case vd:t="Cineon";break;case Tl:t="ACESFilmic";break;case Sd:t="AgX";break;case bd:t="Neutral";break;case Md:t="Custom";break;default:console.warn("THREE.WebGLProgram: Unsupported toneMapping:",e),t="Linear"}return"vec3 "+i+"( vec3 color ) { return "+t+"ToneMapping( color ); }"}var Cr=new C;function cg(){ke.getLuminanceCoefficients(Cr);let i=Cr.x.toFixed(4),e=Cr.y.toFixed(4),t=Cr.z.toFixed(4);return["float luminance( const in vec3 rgb ) {",`	const vec3 weights = vec3( ${i}, ${e}, ${t} );`,"	return dot( weights, rgb );","}"].join(`
`)}function hg(i){return[i.extensionClipCullDistance?"#extension GL_ANGLE_clip_cull_distance : require":"",i.extensionMultiDraw?"#extension GL_ANGLE_multi_draw : require":""].filter(Bs).join(`
`)}function ug(i){let e=[];for(let t in i){let n=i[t];n!==!1&&e.push("#define "+t+" "+n)}return e.join(`
`)}function dg(i,e){let t={},n=i.getProgramParameter(e,i.ACTIVE_ATTRIBUTES);for(let s=0;s<n;s++){let r=i.getActiveAttrib(e,s),o=r.name,a=1;r.type===i.FLOAT_MAT2&&(a=2),r.type===i.FLOAT_MAT3&&(a=3),r.type===i.FLOAT_MAT4&&(a=4),t[o]={type:r.type,location:i.getAttribLocation(e,o),locationSize:a}}return t}function Bs(i){return i!==""}function Ch(i,e){let t=e.numSpotLightShadows+e.numSpotLightMaps-e.numSpotLightShadowsWithMaps;return i.replace(/NUM_DIR_LIGHTS/g,e.numDirLights).replace(/NUM_SPOT_LIGHTS/g,e.numSpotLights).replace(/NUM_SPOT_LIGHT_MAPS/g,e.numSpotLightMaps).replace(/NUM_SPOT_LIGHT_COORDS/g,t).replace(/NUM_RECT_AREA_LIGHTS/g,e.numRectAreaLights).replace(/NUM_POINT_LIGHTS/g,e.numPointLights).replace(/NUM_HEMI_LIGHTS/g,e.numHemiLights).replace(/NUM_DIR_LIGHT_SHADOWS/g,e.numDirLightShadows).replace(/NUM_SPOT_LIGHT_SHADOWS_WITH_MAPS/g,e.numSpotLightShadowsWithMaps).replace(/NUM_SPOT_LIGHT_SHADOWS/g,e.numSpotLightShadows).replace(/NUM_POINT_LIGHT_SHADOWS/g,e.numPointLightShadows)}function Ih(i,e){return i.replace(/NUM_CLIPPING_PLANES/g,e.numClippingPlanes).replace(/UNION_CLIPPING_PLANES/g,e.numClippingPlanes-e.numClipIntersection)}var fg=/^[ \t]*#include +<([\w\d./]+)>/gm;function sl(i){return i.replace(fg,mg)}var pg=new Map;function mg(i,e){let t=Fe[e];if(t===void 0){let n=pg.get(e);if(n!==void 0)t=Fe[n],console.warn('THREE.WebGLRenderer: Shader chunk "%s" has been deprecated. Use "%s" instead.',e,n);else throw new Error("Can not resolve #include <"+e+">")}return sl(t)}var gg=/#pragma unroll_loop_start\s+for\s*\(\s*int\s+i\s*=\s*(\d+)\s*;\s*i\s*<\s*(\d+)\s*;\s*i\s*\+\+\s*\)\s*{([\s\S]+?)}\s+#pragma unroll_loop_end/g;function Ph(i){return i.replace(gg,_g)}function _g(i,e,t,n){let s="";for(let r=parseInt(e);r<parseInt(t);r++)s+=n.replace(/\[\s*i\s*\]/g,"[ "+r+" ]").replace(/UNROLLED_LOOP_INDEX/g,r);return s}function Lh(i){let e=`precision ${i.precision} float;
	precision ${i.precision} int;
	precision ${i.precision} sampler2D;
	precision ${i.precision} samplerCube;
	precision ${i.precision} sampler3D;
	precision ${i.precision} sampler2DArray;
	precision ${i.precision} sampler2DShadow;
	precision ${i.precision} samplerCubeShadow;
	precision ${i.precision} sampler2DArrayShadow;
	precision ${i.precision} isampler2D;
	precision ${i.precision} isampler3D;
	precision ${i.precision} isamplerCube;
	precision ${i.precision} isampler2DArray;
	precision ${i.precision} usampler2D;
	precision ${i.precision} usampler3D;
	precision ${i.precision} usamplerCube;
	precision ${i.precision} usampler2DArray;
	`;return i.precision==="highp"?e+=`
#define HIGH_PRECISION`:i.precision==="mediump"?e+=`
#define MEDIUM_PRECISION`:i.precision==="lowp"&&(e+=`
#define LOW_PRECISION`),e}function xg(i){let e="SHADOWMAP_TYPE_BASIC";return i.shadowMapType===iu?e="SHADOWMAP_TYPE_PCF":i.shadowMapType===Al?e="SHADOWMAP_TYPE_PCF_SOFT":i.shadowMapType===Fn&&(e="SHADOWMAP_TYPE_VSM"),e}function yg(i){let e="ENVMAP_TYPE_CUBE";if(i.envMap)switch(i.envMapMode){case cs:case hs:e="ENVMAP_TYPE_CUBE";break;case bo:e="ENVMAP_TYPE_CUBE_UV";break}return e}function vg(i){let e="ENVMAP_MODE_REFLECTION";if(i.envMap)switch(i.envMapMode){case hs:e="ENVMAP_MODE_REFRACTION";break}return e}function Mg(i){let e="ENVMAP_BLENDING_NONE";if(i.envMap)switch(i.combine){case su:e="ENVMAP_BLENDING_MULTIPLY";break;case gd:e="ENVMAP_BLENDING_MIX";break;case _d:e="ENVMAP_BLENDING_ADD";break}return e}function Sg(i){let e=i.envMapCubeUVHeight;if(e===null)return null;let t=Math.log2(e)-2,n=1/e;return{texelWidth:1/(3*Math.max(Math.pow(2,t),7*16)),texelHeight:n,maxMip:t}}function bg(i,e,t,n){let s=i.getContext(),r=t.defines,o=t.vertexShader,a=t.fragmentShader,l=xg(t),c=yg(t),h=vg(t),u=Mg(t),d=Sg(t),f=hg(t),g=ug(r),_=s.createProgram(),m,p,w=t.glslVersion?"#version "+t.glslVersion+`
`:"";t.isRawShaderMaterial?(m=["#define SHADER_TYPE "+t.shaderType,"#define SHADER_NAME "+t.shaderName,g].filter(Bs).join(`
`),m.length>0&&(m+=`
`),p=["#define SHADER_TYPE "+t.shaderType,"#define SHADER_NAME "+t.shaderName,g].filter(Bs).join(`
`),p.length>0&&(p+=`
`)):(m=[Lh(t),"#define SHADER_TYPE "+t.shaderType,"#define SHADER_NAME "+t.shaderName,g,t.extensionClipCullDistance?"#define USE_CLIP_DISTANCE":"",t.batching?"#define USE_BATCHING":"",t.batchingColor?"#define USE_BATCHING_COLOR":"",t.instancing?"#define USE_INSTANCING":"",t.instancingColor?"#define USE_INSTANCING_COLOR":"",t.instancingMorph?"#define USE_INSTANCING_MORPH":"",t.useFog&&t.fog?"#define USE_FOG":"",t.useFog&&t.fogExp2?"#define FOG_EXP2":"",t.map?"#define USE_MAP":"",t.envMap?"#define USE_ENVMAP":"",t.envMap?"#define "+h:"",t.lightMap?"#define USE_LIGHTMAP":"",t.aoMap?"#define USE_AOMAP":"",t.bumpMap?"#define USE_BUMPMAP":"",t.normalMap?"#define USE_NORMALMAP":"",t.normalMapObjectSpace?"#define USE_NORMALMAP_OBJECTSPACE":"",t.normalMapTangentSpace?"#define USE_NORMALMAP_TANGENTSPACE":"",t.displacementMap?"#define USE_DISPLACEMENTMAP":"",t.emissiveMap?"#define USE_EMISSIVEMAP":"",t.anisotropy?"#define USE_ANISOTROPY":"",t.anisotropyMap?"#define USE_ANISOTROPYMAP":"",t.clearcoatMap?"#define USE_CLEARCOATMAP":"",t.clearcoatRoughnessMap?"#define USE_CLEARCOAT_ROUGHNESSMAP":"",t.clearcoatNormalMap?"#define USE_CLEARCOAT_NORMALMAP":"",t.iridescenceMap?"#define USE_IRIDESCENCEMAP":"",t.iridescenceThicknessMap?"#define USE_IRIDESCENCE_THICKNESSMAP":"",t.specularMap?"#define USE_SPECULARMAP":"",t.specularColorMap?"#define USE_SPECULAR_COLORMAP":"",t.specularIntensityMap?"#define USE_SPECULAR_INTENSITYMAP":"",t.roughnessMap?"#define USE_ROUGHNESSMAP":"",t.metalnessMap?"#define USE_METALNESSMAP":"",t.alphaMap?"#define USE_ALPHAMAP":"",t.alphaHash?"#define USE_ALPHAHASH":"",t.transmission?"#define USE_TRANSMISSION":"",t.transmissionMap?"#define USE_TRANSMISSIONMAP":"",t.thicknessMap?"#define USE_THICKNESSMAP":"",t.sheenColorMap?"#define USE_SHEEN_COLORMAP":"",t.sheenRoughnessMap?"#define USE_SHEEN_ROUGHNESSMAP":"",t.mapUv?"#define MAP_UV "+t.mapUv:"",t.alphaMapUv?"#define ALPHAMAP_UV "+t.alphaMapUv:"",t.lightMapUv?"#define LIGHTMAP_UV "+t.lightMapUv:"",t.aoMapUv?"#define AOMAP_UV "+t.aoMapUv:"",t.emissiveMapUv?"#define EMISSIVEMAP_UV "+t.emissiveMapUv:"",t.bumpMapUv?"#define BUMPMAP_UV "+t.bumpMapUv:"",t.normalMapUv?"#define NORMALMAP_UV "+t.normalMapUv:"",t.displacementMapUv?"#define DISPLACEMENTMAP_UV "+t.displacementMapUv:"",t.metalnessMapUv?"#define METALNESSMAP_UV "+t.metalnessMapUv:"",t.roughnessMapUv?"#define ROUGHNESSMAP_UV "+t.roughnessMapUv:"",t.anisotropyMapUv?"#define ANISOTROPYMAP_UV "+t.anisotropyMapUv:"",t.clearcoatMapUv?"#define CLEARCOATMAP_UV "+t.clearcoatMapUv:"",t.clearcoatNormalMapUv?"#define CLEARCOAT_NORMALMAP_UV "+t.clearcoatNormalMapUv:"",t.clearcoatRoughnessMapUv?"#define CLEARCOAT_ROUGHNESSMAP_UV "+t.clearcoatRoughnessMapUv:"",t.iridescenceMapUv?"#define IRIDESCENCEMAP_UV "+t.iridescenceMapUv:"",t.iridescenceThicknessMapUv?"#define IRIDESCENCE_THICKNESSMAP_UV "+t.iridescenceThicknessMapUv:"",t.sheenColorMapUv?"#define SHEEN_COLORMAP_UV "+t.sheenColorMapUv:"",t.sheenRoughnessMapUv?"#define SHEEN_ROUGHNESSMAP_UV "+t.sheenRoughnessMapUv:"",t.specularMapUv?"#define SPECULARMAP_UV "+t.specularMapUv:"",t.specularColorMapUv?"#define SPECULAR_COLORMAP_UV "+t.specularColorMapUv:"",t.specularIntensityMapUv?"#define SPECULAR_INTENSITYMAP_UV "+t.specularIntensityMapUv:"",t.transmissionMapUv?"#define TRANSMISSIONMAP_UV "+t.transmissionMapUv:"",t.thicknessMapUv?"#define THICKNESSMAP_UV "+t.thicknessMapUv:"",t.vertexTangents&&t.flatShading===!1?"#define USE_TANGENT":"",t.vertexColors?"#define USE_COLOR":"",t.vertexAlphas?"#define USE_COLOR_ALPHA":"",t.vertexUv1s?"#define USE_UV1":"",t.vertexUv2s?"#define USE_UV2":"",t.vertexUv3s?"#define USE_UV3":"",t.pointsUvs?"#define USE_POINTS_UV":"",t.flatShading?"#define FLAT_SHADED":"",t.skinning?"#define USE_SKINNING":"",t.morphTargets?"#define USE_MORPHTARGETS":"",t.morphNormals&&t.flatShading===!1?"#define USE_MORPHNORMALS":"",t.morphColors?"#define USE_MORPHCOLORS":"",t.morphTargetsCount>0?"#define MORPHTARGETS_TEXTURE_STRIDE "+t.morphTextureStride:"",t.morphTargetsCount>0?"#define MORPHTARGETS_COUNT "+t.morphTargetsCount:"",t.doubleSided?"#define DOUBLE_SIDED":"",t.flipSided?"#define FLIP_SIDED":"",t.shadowMapEnabled?"#define USE_SHADOWMAP":"",t.shadowMapEnabled?"#define "+l:"",t.sizeAttenuation?"#define USE_SIZEATTENUATION":"",t.numLightProbes>0?"#define USE_LIGHT_PROBES":"",t.logarithmicDepthBuffer?"#define USE_LOGDEPTHBUF":"",t.reverseDepthBuffer?"#define USE_REVERSEDEPTHBUF":"","uniform mat4 modelMatrix;","uniform mat4 modelViewMatrix;","uniform mat4 projectionMatrix;","uniform mat4 viewMatrix;","uniform mat3 normalMatrix;","uniform vec3 cameraPosition;","uniform bool isOrthographic;","#ifdef USE_INSTANCING","	attribute mat4 instanceMatrix;","#endif","#ifdef USE_INSTANCING_COLOR","	attribute vec3 instanceColor;","#endif","#ifdef USE_INSTANCING_MORPH","	uniform sampler2D morphTexture;","#endif","attribute vec3 position;","attribute vec3 normal;","attribute vec2 uv;","#ifdef USE_UV1","	attribute vec2 uv1;","#endif","#ifdef USE_UV2","	attribute vec2 uv2;","#endif","#ifdef USE_UV3","	attribute vec2 uv3;","#endif","#ifdef USE_TANGENT","	attribute vec4 tangent;","#endif","#if defined( USE_COLOR_ALPHA )","	attribute vec4 color;","#elif defined( USE_COLOR )","	attribute vec3 color;","#endif","#ifdef USE_SKINNING","	attribute vec4 skinIndex;","	attribute vec4 skinWeight;","#endif",`
`].filter(Bs).join(`
`),p=[Lh(t),"#define SHADER_TYPE "+t.shaderType,"#define SHADER_NAME "+t.shaderName,g,t.useFog&&t.fog?"#define USE_FOG":"",t.useFog&&t.fogExp2?"#define FOG_EXP2":"",t.alphaToCoverage?"#define ALPHA_TO_COVERAGE":"",t.map?"#define USE_MAP":"",t.matcap?"#define USE_MATCAP":"",t.envMap?"#define USE_ENVMAP":"",t.envMap?"#define "+c:"",t.envMap?"#define "+h:"",t.envMap?"#define "+u:"",d?"#define CUBEUV_TEXEL_WIDTH "+d.texelWidth:"",d?"#define CUBEUV_TEXEL_HEIGHT "+d.texelHeight:"",d?"#define CUBEUV_MAX_MIP "+d.maxMip+".0":"",t.lightMap?"#define USE_LIGHTMAP":"",t.aoMap?"#define USE_AOMAP":"",t.bumpMap?"#define USE_BUMPMAP":"",t.normalMap?"#define USE_NORMALMAP":"",t.normalMapObjectSpace?"#define USE_NORMALMAP_OBJECTSPACE":"",t.normalMapTangentSpace?"#define USE_NORMALMAP_TANGENTSPACE":"",t.emissiveMap?"#define USE_EMISSIVEMAP":"",t.anisotropy?"#define USE_ANISOTROPY":"",t.anisotropyMap?"#define USE_ANISOTROPYMAP":"",t.clearcoat?"#define USE_CLEARCOAT":"",t.clearcoatMap?"#define USE_CLEARCOATMAP":"",t.clearcoatRoughnessMap?"#define USE_CLEARCOAT_ROUGHNESSMAP":"",t.clearcoatNormalMap?"#define USE_CLEARCOAT_NORMALMAP":"",t.dispersion?"#define USE_DISPERSION":"",t.iridescence?"#define USE_IRIDESCENCE":"",t.iridescenceMap?"#define USE_IRIDESCENCEMAP":"",t.iridescenceThicknessMap?"#define USE_IRIDESCENCE_THICKNESSMAP":"",t.specularMap?"#define USE_SPECULARMAP":"",t.specularColorMap?"#define USE_SPECULAR_COLORMAP":"",t.specularIntensityMap?"#define USE_SPECULAR_INTENSITYMAP":"",t.roughnessMap?"#define USE_ROUGHNESSMAP":"",t.metalnessMap?"#define USE_METALNESSMAP":"",t.alphaMap?"#define USE_ALPHAMAP":"",t.alphaTest?"#define USE_ALPHATEST":"",t.alphaHash?"#define USE_ALPHAHASH":"",t.sheen?"#define USE_SHEEN":"",t.sheenColorMap?"#define USE_SHEEN_COLORMAP":"",t.sheenRoughnessMap?"#define USE_SHEEN_ROUGHNESSMAP":"",t.transmission?"#define USE_TRANSMISSION":"",t.transmissionMap?"#define USE_TRANSMISSIONMAP":"",t.thicknessMap?"#define USE_THICKNESSMAP":"",t.vertexTangents&&t.flatShading===!1?"#define USE_TANGENT":"",t.vertexColors||t.instancingColor||t.batchingColor?"#define USE_COLOR":"",t.vertexAlphas?"#define USE_COLOR_ALPHA":"",t.vertexUv1s?"#define USE_UV1":"",t.vertexUv2s?"#define USE_UV2":"",t.vertexUv3s?"#define USE_UV3":"",t.pointsUvs?"#define USE_POINTS_UV":"",t.gradientMap?"#define USE_GRADIENTMAP":"",t.flatShading?"#define FLAT_SHADED":"",t.doubleSided?"#define DOUBLE_SIDED":"",t.flipSided?"#define FLIP_SIDED":"",t.shadowMapEnabled?"#define USE_SHADOWMAP":"",t.shadowMapEnabled?"#define "+l:"",t.premultipliedAlpha?"#define PREMULTIPLIED_ALPHA":"",t.numLightProbes>0?"#define USE_LIGHT_PROBES":"",t.decodeVideoTexture?"#define DECODE_VIDEO_TEXTURE":"",t.decodeVideoTextureEmissive?"#define DECODE_VIDEO_TEXTURE_EMISSIVE":"",t.logarithmicDepthBuffer?"#define USE_LOGDEPTHBUF":"",t.reverseDepthBuffer?"#define USE_REVERSEDEPTHBUF":"","uniform mat4 viewMatrix;","uniform vec3 cameraPosition;","uniform bool isOrthographic;",t.toneMapping!==di?"#define TONE_MAPPING":"",t.toneMapping!==di?Fe.tonemapping_pars_fragment:"",t.toneMapping!==di?lg("toneMapping",t.toneMapping):"",t.dithering?"#define DITHERING":"",t.opaque?"#define OPAQUE":"",Fe.colorspace_pars_fragment,ag("linearToOutputTexel",t.outputColorSpace),cg(),t.useDepthPacking?"#define DEPTH_PACKING "+t.depthPacking:"",`
`].filter(Bs).join(`
`)),o=sl(o),o=Ch(o,t),o=Ih(o,t),a=sl(a),a=Ch(a,t),a=Ih(a,t),o=Ph(o),a=Ph(a),t.isRawShaderMaterial!==!0&&(w=`#version 300 es
`,m=[f,"#define attribute in","#define varying out","#define texture2D texture"].join(`
`)+`
`+m,p=["#define varying in",t.glslVersion===Xc?"":"layout(location = 0) out highp vec4 pc_fragColor;",t.glslVersion===Xc?"":"#define gl_FragColor pc_fragColor","#define gl_FragDepthEXT gl_FragDepth","#define texture2D texture","#define textureCube texture","#define texture2DProj textureProj","#define texture2DLodEXT textureLod","#define texture2DProjLodEXT textureProjLod","#define textureCubeLodEXT textureLod","#define texture2DGradEXT textureGrad","#define texture2DProjGradEXT textureProjGrad","#define textureCubeGradEXT textureGrad"].join(`
`)+`
`+p);let b=w+m+o,x=w+p+a,P=Ah(s,s.VERTEX_SHADER,b),T=Ah(s,s.FRAGMENT_SHADER,x);s.attachShader(_,P),s.attachShader(_,T),t.index0AttributeName!==void 0?s.bindAttribLocation(_,0,t.index0AttributeName):t.morphTargets===!0&&s.bindAttribLocation(_,0,"position"),s.linkProgram(_);function A(I){if(i.debug.checkShaderErrors){let G=s.getProgramInfoLog(_).trim(),O=s.getShaderInfoLog(P).trim(),X=s.getShaderInfoLog(T).trim(),Y=!0,V=!0;if(s.getProgramParameter(_,s.LINK_STATUS)===!1)if(Y=!1,typeof i.debug.onShaderError=="function")i.debug.onShaderError(s,_,P,T);else{let Q=Rh(s,P,"vertex"),B=Rh(s,T,"fragment");console.error("THREE.WebGLProgram: Shader Error "+s.getError()+" - VALIDATE_STATUS "+s.getProgramParameter(_,s.VALIDATE_STATUS)+`

Material Name: `+I.name+`
Material Type: `+I.type+`

Program Info Log: `+G+`
`+Q+`
`+B)}else G!==""?console.warn("THREE.WebGLProgram: Program Info Log:",G):(O===""||X==="")&&(V=!1);V&&(I.diagnostics={runnable:Y,programLog:G,vertexShader:{log:O,prefix:m},fragmentShader:{log:X,prefix:p}})}s.deleteShader(P),s.deleteShader(T),R=new as(s,_),M=dg(s,_)}let R;this.getUniforms=function(){return R===void 0&&A(this),R};let M;this.getAttributes=function(){return M===void 0&&A(this),M};let v=t.rendererExtensionParallelShaderCompile===!1;return this.isReady=function(){return v===!1&&(v=s.getProgramParameter(_,ig)),v},this.destroy=function(){n.releaseStatesOfProgram(this),s.deleteProgram(_),this.program=void 0},this.type=t.shaderType,this.name=t.shaderName,this.id=sg++,this.cacheKey=e,this.usedTimes=1,this.program=_,this.vertexShader=P,this.fragmentShader=T,this}var wg=0,rl=class{constructor(){this.shaderCache=new Map,this.materialCache=new Map}update(e){let t=e.vertexShader,n=e.fragmentShader,s=this._getShaderStage(t),r=this._getShaderStage(n),o=this._getShaderCacheForMaterial(e);return o.has(s)===!1&&(o.add(s),s.usedTimes++),o.has(r)===!1&&(o.add(r),r.usedTimes++),this}remove(e){let t=this.materialCache.get(e);for(let n of t)n.usedTimes--,n.usedTimes===0&&this.shaderCache.delete(n.code);return this.materialCache.delete(e),this}getVertexShaderID(e){return this._getShaderStage(e.vertexShader).id}getFragmentShaderID(e){return this._getShaderStage(e.fragmentShader).id}dispose(){this.shaderCache.clear(),this.materialCache.clear()}_getShaderCacheForMaterial(e){let t=this.materialCache,n=t.get(e);return n===void 0&&(n=new Set,t.set(e,n)),n}_getShaderStage(e){let t=this.shaderCache,n=t.get(e);return n===void 0&&(n=new ol(e),t.set(e,n)),n}},ol=class{constructor(e){this.id=wg++,this.code=e,this.usedTimes=0}};function Eg(i,e,t,n,s,r,o){let a=new Xs,l=new rl,c=new Set,h=[],u=s.logarithmicDepthBuffer,d=s.vertexTextures,f=s.precision,g={MeshDepthMaterial:"depth",MeshDistanceMaterial:"distanceRGBA",MeshNormalMaterial:"normal",MeshBasicMaterial:"basic",MeshLambertMaterial:"lambert",MeshPhongMaterial:"phong",MeshToonMaterial:"toon",MeshStandardMaterial:"physical",MeshPhysicalMaterial:"physical",MeshMatcapMaterial:"matcap",LineBasicMaterial:"basic",LineDashedMaterial:"dashed",PointsMaterial:"points",ShadowMaterial:"shadow",SpriteMaterial:"sprite"};function _(M){return c.add(M),M===0?"uv":`uv${M}`}function m(M,v,I,G,O){let X=G.fog,Y=O.geometry,V=M.isMeshStandardMaterial?G.environment:null,Q=(M.isMeshStandardMaterial?t:e).get(M.envMap||V),B=Q&&Q.mapping===bo?Q.image.height:null,H=g[M.type];M.precision!==null&&(f=s.getMaxPrecision(M.precision),f!==M.precision&&console.warn("THREE.WebGLProgram.getParameters:",M.precision,"not supported, using",f,"instead."));let j=Y.morphAttributes.position||Y.morphAttributes.normal||Y.morphAttributes.color,ie=j!==void 0?j.length:0,Te=0;Y.morphAttributes.position!==void 0&&(Te=1),Y.morphAttributes.normal!==void 0&&(Te=2),Y.morphAttributes.color!==void 0&&(Te=3);let Re,q,ee,me;if(H){let je=bn[H];Re=je.vertexShader,q=je.fragmentShader}else Re=M.vertexShader,q=M.fragmentShader,l.update(M),ee=l.getVertexShaderID(M),me=l.getFragmentShaderID(M);let se=i.getRenderTarget(),Me=i.state.buffers.depth.getReversed(),Pe=O.isInstancedMesh===!0,Be=O.isBatchedMesh===!0,ct=!!M.map,We=!!M.matcap,ft=!!Q,N=!!M.aoMap,nn=!!M.lightMap,He=!!M.bumpMap,Ve=!!M.normalMap,be=!!M.displacementMap,ot=!!M.emissiveMap,Se=!!M.metalnessMap,E=!!M.roughnessMap,y=M.anisotropy>0,F=M.clearcoat>0,K=M.dispersion>0,$=M.iridescence>0,Z=M.sheen>0,ye=M.transmission>0,le=y&&!!M.anisotropyMap,de=F&&!!M.clearcoatMap,Xe=F&&!!M.clearcoatNormalMap,te=F&&!!M.clearcoatRoughnessMap,fe=$&&!!M.iridescenceMap,Ee=$&&!!M.iridescenceThicknessMap,Ce=Z&&!!M.sheenColorMap,pe=Z&&!!M.sheenRoughnessMap,Ge=!!M.specularMap,Oe=!!M.specularColorMap,it=!!M.specularIntensityMap,L=ye&&!!M.transmissionMap,ae=ye&&!!M.thicknessMap,W=!!M.gradientMap,J=!!M.alphaMap,ue=M.alphaTest>0,ce=!!M.alphaHash,De=!!M.extensions,ut=di;M.toneMapped&&(se===null||se.isXRRenderTarget===!0)&&(ut=i.toneMapping);let It={shaderID:H,shaderType:M.type,shaderName:M.name,vertexShader:Re,fragmentShader:q,defines:M.defines,customVertexShaderID:ee,customFragmentShaderID:me,isRawShaderMaterial:M.isRawShaderMaterial===!0,glslVersion:M.glslVersion,precision:f,batching:Be,batchingColor:Be&&O._colorsTexture!==null,instancing:Pe,instancingColor:Pe&&O.instanceColor!==null,instancingMorph:Pe&&O.morphTexture!==null,supportsVertexTextures:d,outputColorSpace:se===null?i.outputColorSpace:se.isXRRenderTarget===!0?se.texture.colorSpace:Ft,alphaToCoverage:!!M.alphaToCoverage,map:ct,matcap:We,envMap:ft,envMapMode:ft&&Q.mapping,envMapCubeUVHeight:B,aoMap:N,lightMap:nn,bumpMap:He,normalMap:Ve,displacementMap:d&&be,emissiveMap:ot,normalMapObjectSpace:Ve&&M.normalMapType===Rd,normalMapTangentSpace:Ve&&M.normalMapType===gu,metalnessMap:Se,roughnessMap:E,anisotropy:y,anisotropyMap:le,clearcoat:F,clearcoatMap:de,clearcoatNormalMap:Xe,clearcoatRoughnessMap:te,dispersion:K,iridescence:$,iridescenceMap:fe,iridescenceThicknessMap:Ee,sheen:Z,sheenColorMap:Ce,sheenRoughnessMap:pe,specularMap:Ge,specularColorMap:Oe,specularIntensityMap:it,transmission:ye,transmissionMap:L,thicknessMap:ae,gradientMap:W,opaque:M.transparent===!1&&M.blending===is&&M.alphaToCoverage===!1,alphaMap:J,alphaTest:ue,alphaHash:ce,combine:M.combine,mapUv:ct&&_(M.map.channel),aoMapUv:N&&_(M.aoMap.channel),lightMapUv:nn&&_(M.lightMap.channel),bumpMapUv:He&&_(M.bumpMap.channel),normalMapUv:Ve&&_(M.normalMap.channel),displacementMapUv:be&&_(M.displacementMap.channel),emissiveMapUv:ot&&_(M.emissiveMap.channel),metalnessMapUv:Se&&_(M.metalnessMap.channel),roughnessMapUv:E&&_(M.roughnessMap.channel),anisotropyMapUv:le&&_(M.anisotropyMap.channel),clearcoatMapUv:de&&_(M.clearcoatMap.channel),clearcoatNormalMapUv:Xe&&_(M.clearcoatNormalMap.channel),clearcoatRoughnessMapUv:te&&_(M.clearcoatRoughnessMap.channel),iridescenceMapUv:fe&&_(M.iridescenceMap.channel),iridescenceThicknessMapUv:Ee&&_(M.iridescenceThicknessMap.channel),sheenColorMapUv:Ce&&_(M.sheenColorMap.channel),sheenRoughnessMapUv:pe&&_(M.sheenRoughnessMap.channel),specularMapUv:Ge&&_(M.specularMap.channel),specularColorMapUv:Oe&&_(M.specularColorMap.channel),specularIntensityMapUv:it&&_(M.specularIntensityMap.channel),transmissionMapUv:L&&_(M.transmissionMap.channel),thicknessMapUv:ae&&_(M.thicknessMap.channel),alphaMapUv:J&&_(M.alphaMap.channel),vertexTangents:!!Y.attributes.tangent&&(Ve||y),vertexColors:M.vertexColors,vertexAlphas:M.vertexColors===!0&&!!Y.attributes.color&&Y.attributes.color.itemSize===4,pointsUvs:O.isPoints===!0&&!!Y.attributes.uv&&(ct||J),fog:!!X,useFog:M.fog===!0,fogExp2:!!X&&X.isFogExp2,flatShading:M.flatShading===!0,sizeAttenuation:M.sizeAttenuation===!0,logarithmicDepthBuffer:u,reverseDepthBuffer:Me,skinning:O.isSkinnedMesh===!0,morphTargets:Y.morphAttributes.position!==void 0,morphNormals:Y.morphAttributes.normal!==void 0,morphColors:Y.morphAttributes.color!==void 0,morphTargetsCount:ie,morphTextureStride:Te,numDirLights:v.directional.length,numPointLights:v.point.length,numSpotLights:v.spot.length,numSpotLightMaps:v.spotLightMap.length,numRectAreaLights:v.rectArea.length,numHemiLights:v.hemi.length,numDirLightShadows:v.directionalShadowMap.length,numPointLightShadows:v.pointShadowMap.length,numSpotLightShadows:v.spotShadowMap.length,numSpotLightShadowsWithMaps:v.numSpotLightShadowsWithMaps,numLightProbes:v.numLightProbes,numClippingPlanes:o.numPlanes,numClipIntersection:o.numIntersection,dithering:M.dithering,shadowMapEnabled:i.shadowMap.enabled&&I.length>0,shadowMapType:i.shadowMap.type,toneMapping:ut,decodeVideoTexture:ct&&M.map.isVideoTexture===!0&&ke.getTransfer(M.map.colorSpace)===Qe,decodeVideoTextureEmissive:ot&&M.emissiveMap.isVideoTexture===!0&&ke.getTransfer(M.emissiveMap.colorSpace)===Qe,premultipliedAlpha:M.premultipliedAlpha,doubleSided:M.side===Jt,flipSided:M.side===Ut,useDepthPacking:M.depthPacking>=0,depthPacking:M.depthPacking||0,index0AttributeName:M.index0AttributeName,extensionClipCullDistance:De&&M.extensions.clipCullDistance===!0&&n.has("WEBGL_clip_cull_distance"),extensionMultiDraw:(De&&M.extensions.multiDraw===!0||Be)&&n.has("WEBGL_multi_draw"),rendererExtensionParallelShaderCompile:n.has("KHR_parallel_shader_compile"),customProgramCacheKey:M.customProgramCacheKey()};return It.vertexUv1s=c.has(1),It.vertexUv2s=c.has(2),It.vertexUv3s=c.has(3),c.clear(),It}function p(M){let v=[];if(M.shaderID?v.push(M.shaderID):(v.push(M.customVertexShaderID),v.push(M.customFragmentShaderID)),M.defines!==void 0)for(let I in M.defines)v.push(I),v.push(M.defines[I]);return M.isRawShaderMaterial===!1&&(w(v,M),b(v,M),v.push(i.outputColorSpace)),v.push(M.customProgramCacheKey),v.join()}function w(M,v){M.push(v.precision),M.push(v.outputColorSpace),M.push(v.envMapMode),M.push(v.envMapCubeUVHeight),M.push(v.mapUv),M.push(v.alphaMapUv),M.push(v.lightMapUv),M.push(v.aoMapUv),M.push(v.bumpMapUv),M.push(v.normalMapUv),M.push(v.displacementMapUv),M.push(v.emissiveMapUv),M.push(v.metalnessMapUv),M.push(v.roughnessMapUv),M.push(v.anisotropyMapUv),M.push(v.clearcoatMapUv),M.push(v.clearcoatNormalMapUv),M.push(v.clearcoatRoughnessMapUv),M.push(v.iridescenceMapUv),M.push(v.iridescenceThicknessMapUv),M.push(v.sheenColorMapUv),M.push(v.sheenRoughnessMapUv),M.push(v.specularMapUv),M.push(v.specularColorMapUv),M.push(v.specularIntensityMapUv),M.push(v.transmissionMapUv),M.push(v.thicknessMapUv),M.push(v.combine),M.push(v.fogExp2),M.push(v.sizeAttenuation),M.push(v.morphTargetsCount),M.push(v.morphAttributeCount),M.push(v.numDirLights),M.push(v.numPointLights),M.push(v.numSpotLights),M.push(v.numSpotLightMaps),M.push(v.numHemiLights),M.push(v.numRectAreaLights),M.push(v.numDirLightShadows),M.push(v.numPointLightShadows),M.push(v.numSpotLightShadows),M.push(v.numSpotLightShadowsWithMaps),M.push(v.numLightProbes),M.push(v.shadowMapType),M.push(v.toneMapping),M.push(v.numClippingPlanes),M.push(v.numClipIntersection),M.push(v.depthPacking)}function b(M,v){a.disableAll(),v.supportsVertexTextures&&a.enable(0),v.instancing&&a.enable(1),v.instancingColor&&a.enable(2),v.instancingMorph&&a.enable(3),v.matcap&&a.enable(4),v.envMap&&a.enable(5),v.normalMapObjectSpace&&a.enable(6),v.normalMapTangentSpace&&a.enable(7),v.clearcoat&&a.enable(8),v.iridescence&&a.enable(9),v.alphaTest&&a.enable(10),v.vertexColors&&a.enable(11),v.vertexAlphas&&a.enable(12),v.vertexUv1s&&a.enable(13),v.vertexUv2s&&a.enable(14),v.vertexUv3s&&a.enable(15),v.vertexTangents&&a.enable(16),v.anisotropy&&a.enable(17),v.alphaHash&&a.enable(18),v.batching&&a.enable(19),v.dispersion&&a.enable(20),v.batchingColor&&a.enable(21),M.push(a.mask),a.disableAll(),v.fog&&a.enable(0),v.useFog&&a.enable(1),v.flatShading&&a.enable(2),v.logarithmicDepthBuffer&&a.enable(3),v.reverseDepthBuffer&&a.enable(4),v.skinning&&a.enable(5),v.morphTargets&&a.enable(6),v.morphNormals&&a.enable(7),v.morphColors&&a.enable(8),v.premultipliedAlpha&&a.enable(9),v.shadowMapEnabled&&a.enable(10),v.doubleSided&&a.enable(11),v.flipSided&&a.enable(12),v.useDepthPacking&&a.enable(13),v.dithering&&a.enable(14),v.transmission&&a.enable(15),v.sheen&&a.enable(16),v.opaque&&a.enable(17),v.pointsUvs&&a.enable(18),v.decodeVideoTexture&&a.enable(19),v.decodeVideoTextureEmissive&&a.enable(20),v.alphaToCoverage&&a.enable(21),M.push(a.mask)}function x(M){let v=g[M.type],I;if(v){let G=bn[v];I=Fl.clone(G.uniforms)}else I=M.uniforms;return I}function P(M,v){let I;for(let G=0,O=h.length;G<O;G++){let X=h[G];if(X.cacheKey===v){I=X,++I.usedTimes;break}}return I===void 0&&(I=new bg(i,v,M,r),h.push(I)),I}function T(M){if(--M.usedTimes===0){let v=h.indexOf(M);h[v]=h[h.length-1],h.pop(),M.destroy()}}function A(M){l.remove(M)}function R(){l.dispose()}return{getParameters:m,getProgramCacheKey:p,getUniforms:x,acquireProgram:P,releaseProgram:T,releaseShaderCache:A,programs:h,dispose:R}}function Ag(){let i=new WeakMap;function e(o){return i.has(o)}function t(o){let a=i.get(o);return a===void 0&&(a={},i.set(o,a)),a}function n(o){i.delete(o)}function s(o,a,l){i.get(o)[a]=l}function r(){i=new WeakMap}return{has:e,get:t,remove:n,update:s,dispose:r}}function Tg(i,e){return i.groupOrder!==e.groupOrder?i.groupOrder-e.groupOrder:i.renderOrder!==e.renderOrder?i.renderOrder-e.renderOrder:i.material.id!==e.material.id?i.material.id-e.material.id:i.z!==e.z?i.z-e.z:i.id-e.id}function Dh(i,e){return i.groupOrder!==e.groupOrder?i.groupOrder-e.groupOrder:i.renderOrder!==e.renderOrder?i.renderOrder-e.renderOrder:i.z!==e.z?e.z-i.z:i.id-e.id}function Uh(){let i=[],e=0,t=[],n=[],s=[];function r(){e=0,t.length=0,n.length=0,s.length=0}function o(u,d,f,g,_,m){let p=i[e];return p===void 0?(p={id:u.id,object:u,geometry:d,material:f,groupOrder:g,renderOrder:u.renderOrder,z:_,group:m},i[e]=p):(p.id=u.id,p.object=u,p.geometry=d,p.material=f,p.groupOrder=g,p.renderOrder=u.renderOrder,p.z=_,p.group=m),e++,p}function a(u,d,f,g,_,m){let p=o(u,d,f,g,_,m);f.transmission>0?n.push(p):f.transparent===!0?s.push(p):t.push(p)}function l(u,d,f,g,_,m){let p=o(u,d,f,g,_,m);f.transmission>0?n.unshift(p):f.transparent===!0?s.unshift(p):t.unshift(p)}function c(u,d){t.length>1&&t.sort(u||Tg),n.length>1&&n.sort(d||Dh),s.length>1&&s.sort(d||Dh)}function h(){for(let u=e,d=i.length;u<d;u++){let f=i[u];if(f.id===null)break;f.id=null,f.object=null,f.geometry=null,f.material=null,f.group=null}}return{opaque:t,transmissive:n,transparent:s,init:r,push:a,unshift:l,finish:h,sort:c}}function Rg(){let i=new WeakMap;function e(n,s){let r=i.get(n),o;return r===void 0?(o=new Uh,i.set(n,[o])):s>=r.length?(o=new Uh,r.push(o)):o=r[s],o}function t(){i=new WeakMap}return{get:e,dispose:t}}function Cg(){let i={};return{get:function(e){if(i[e.id]!==void 0)return i[e.id];let t;switch(e.type){case"DirectionalLight":t={direction:new C,color:new Ae};break;case"SpotLight":t={position:new C,direction:new C,color:new Ae,distance:0,coneCos:0,penumbraCos:0,decay:0};break;case"PointLight":t={position:new C,color:new Ae,distance:0,decay:0};break;case"HemisphereLight":t={direction:new C,skyColor:new Ae,groundColor:new Ae};break;case"RectAreaLight":t={color:new Ae,position:new C,halfWidth:new C,halfHeight:new C};break}return i[e.id]=t,t}}}function Ig(){let i={};return{get:function(e){if(i[e.id]!==void 0)return i[e.id];let t;switch(e.type){case"DirectionalLight":t={shadowIntensity:1,shadowBias:0,shadowNormalBias:0,shadowRadius:1,shadowMapSize:new we};break;case"SpotLight":t={shadowIntensity:1,shadowBias:0,shadowNormalBias:0,shadowRadius:1,shadowMapSize:new we};break;case"PointLight":t={shadowIntensity:1,shadowBias:0,shadowNormalBias:0,shadowRadius:1,shadowMapSize:new we,shadowCameraNear:1,shadowCameraFar:1e3};break}return i[e.id]=t,t}}}var Pg=0;function Lg(i,e){return(e.castShadow?2:0)-(i.castShadow?2:0)+(e.map?1:0)-(i.map?1:0)}function Dg(i){let e=new Cg,t=Ig(),n={version:0,hash:{directionalLength:-1,pointLength:-1,spotLength:-1,rectAreaLength:-1,hemiLength:-1,numDirectionalShadows:-1,numPointShadows:-1,numSpotShadows:-1,numSpotMaps:-1,numLightProbes:-1},ambient:[0,0,0],probe:[],directional:[],directionalShadow:[],directionalShadowMap:[],directionalShadowMatrix:[],spot:[],spotLightMap:[],spotShadow:[],spotShadowMap:[],spotLightMatrix:[],rectArea:[],rectAreaLTC1:null,rectAreaLTC2:null,point:[],pointShadow:[],pointShadowMap:[],pointShadowMatrix:[],hemi:[],numSpotLightShadowsWithMaps:0,numLightProbes:0};for(let c=0;c<9;c++)n.probe.push(new C);let s=new C,r=new Le,o=new Le;function a(c){let h=0,u=0,d=0;for(let M=0;M<9;M++)n.probe[M].set(0,0,0);let f=0,g=0,_=0,m=0,p=0,w=0,b=0,x=0,P=0,T=0,A=0;c.sort(Lg);for(let M=0,v=c.length;M<v;M++){let I=c[M],G=I.color,O=I.intensity,X=I.distance,Y=I.shadow&&I.shadow.map?I.shadow.map.texture:null;if(I.isAmbientLight)h+=G.r*O,u+=G.g*O,d+=G.b*O;else if(I.isLightProbe){for(let V=0;V<9;V++)n.probe[V].addScaledVector(I.sh.coefficients[V],O);A++}else if(I.isDirectionalLight){let V=e.get(I);if(V.color.copy(I.color).multiplyScalar(I.intensity),I.castShadow){let Q=I.shadow,B=t.get(I);B.shadowIntensity=Q.intensity,B.shadowBias=Q.bias,B.shadowNormalBias=Q.normalBias,B.shadowRadius=Q.radius,B.shadowMapSize=Q.mapSize,n.directionalShadow[f]=B,n.directionalShadowMap[f]=Y,n.directionalShadowMatrix[f]=I.shadow.matrix,w++}n.directional[f]=V,f++}else if(I.isSpotLight){let V=e.get(I);V.position.setFromMatrixPosition(I.matrixWorld),V.color.copy(G).multiplyScalar(O),V.distance=X,V.coneCos=Math.cos(I.angle),V.penumbraCos=Math.cos(I.angle*(1-I.penumbra)),V.decay=I.decay,n.spot[_]=V;let Q=I.shadow;if(I.map&&(n.spotLightMap[P]=I.map,P++,Q.updateMatrices(I),I.castShadow&&T++),n.spotLightMatrix[_]=Q.matrix,I.castShadow){let B=t.get(I);B.shadowIntensity=Q.intensity,B.shadowBias=Q.bias,B.shadowNormalBias=Q.normalBias,B.shadowRadius=Q.radius,B.shadowMapSize=Q.mapSize,n.spotShadow[_]=B,n.spotShadowMap[_]=Y,x++}_++}else if(I.isRectAreaLight){let V=e.get(I);V.color.copy(G).multiplyScalar(O),V.halfWidth.set(I.width*.5,0,0),V.halfHeight.set(0,I.height*.5,0),n.rectArea[m]=V,m++}else if(I.isPointLight){let V=e.get(I);if(V.color.copy(I.color).multiplyScalar(I.intensity),V.distance=I.distance,V.decay=I.decay,I.castShadow){let Q=I.shadow,B=t.get(I);B.shadowIntensity=Q.intensity,B.shadowBias=Q.bias,B.shadowNormalBias=Q.normalBias,B.shadowRadius=Q.radius,B.shadowMapSize=Q.mapSize,B.shadowCameraNear=Q.camera.near,B.shadowCameraFar=Q.camera.far,n.pointShadow[g]=B,n.pointShadowMap[g]=Y,n.pointShadowMatrix[g]=I.shadow.matrix,b++}n.point[g]=V,g++}else if(I.isHemisphereLight){let V=e.get(I);V.skyColor.copy(I.color).multiplyScalar(O),V.groundColor.copy(I.groundColor).multiplyScalar(O),n.hemi[p]=V,p++}}m>0&&(i.has("OES_texture_float_linear")===!0?(n.rectAreaLTC1=re.LTC_FLOAT_1,n.rectAreaLTC2=re.LTC_FLOAT_2):(n.rectAreaLTC1=re.LTC_HALF_1,n.rectAreaLTC2=re.LTC_HALF_2)),n.ambient[0]=h,n.ambient[1]=u,n.ambient[2]=d;let R=n.hash;(R.directionalLength!==f||R.pointLength!==g||R.spotLength!==_||R.rectAreaLength!==m||R.hemiLength!==p||R.numDirectionalShadows!==w||R.numPointShadows!==b||R.numSpotShadows!==x||R.numSpotMaps!==P||R.numLightProbes!==A)&&(n.directional.length=f,n.spot.length=_,n.rectArea.length=m,n.point.length=g,n.hemi.length=p,n.directionalShadow.length=w,n.directionalShadowMap.length=w,n.pointShadow.length=b,n.pointShadowMap.length=b,n.spotShadow.length=x,n.spotShadowMap.length=x,n.directionalShadowMatrix.length=w,n.pointShadowMatrix.length=b,n.spotLightMatrix.length=x+P-T,n.spotLightMap.length=P,n.numSpotLightShadowsWithMaps=T,n.numLightProbes=A,R.directionalLength=f,R.pointLength=g,R.spotLength=_,R.rectAreaLength=m,R.hemiLength=p,R.numDirectionalShadows=w,R.numPointShadows=b,R.numSpotShadows=x,R.numSpotMaps=P,R.numLightProbes=A,n.version=Pg++)}function l(c,h){let u=0,d=0,f=0,g=0,_=0,m=h.matrixWorldInverse;for(let p=0,w=c.length;p<w;p++){let b=c[p];if(b.isDirectionalLight){let x=n.directional[u];x.direction.setFromMatrixPosition(b.matrixWorld),s.setFromMatrixPosition(b.target.matrixWorld),x.direction.sub(s),x.direction.transformDirection(m),u++}else if(b.isSpotLight){let x=n.spot[f];x.position.setFromMatrixPosition(b.matrixWorld),x.position.applyMatrix4(m),x.direction.setFromMatrixPosition(b.matrixWorld),s.setFromMatrixPosition(b.target.matrixWorld),x.direction.sub(s),x.direction.transformDirection(m),f++}else if(b.isRectAreaLight){let x=n.rectArea[g];x.position.setFromMatrixPosition(b.matrixWorld),x.position.applyMatrix4(m),o.identity(),r.copy(b.matrixWorld),r.premultiply(m),o.extractRotation(r),x.halfWidth.set(b.width*.5,0,0),x.halfHeight.set(0,b.height*.5,0),x.halfWidth.applyMatrix4(o),x.halfHeight.applyMatrix4(o),g++}else if(b.isPointLight){let x=n.point[d];x.position.setFromMatrixPosition(b.matrixWorld),x.position.applyMatrix4(m),d++}else if(b.isHemisphereLight){let x=n.hemi[_];x.direction.setFromMatrixPosition(b.matrixWorld),x.direction.transformDirection(m),_++}}}return{setup:a,setupView:l,state:n}}function Nh(i){let e=new Dg(i),t=[],n=[];function s(h){c.camera=h,t.length=0,n.length=0}function r(h){t.push(h)}function o(h){n.push(h)}function a(){e.setup(t)}function l(h){e.setupView(t,h)}let c={lightsArray:t,shadowsArray:n,camera:null,lights:e,transmissionRenderTarget:{}};return{init:s,state:c,setupLights:a,setupLightsView:l,pushLight:r,pushShadow:o}}function Ug(i){let e=new WeakMap;function t(s,r=0){let o=e.get(s),a;return o===void 0?(a=new Nh(i),e.set(s,[a])):r>=o.length?(a=new Nh(i),o.push(a)):a=o[r],a}function n(){e=new WeakMap}return{get:t,dispose:n}}var al=class extends $t{static get type(){return"MeshDepthMaterial"}constructor(e){super(),this.isMeshDepthMaterial=!0,this.depthPacking=Ad,this.map=null,this.alphaMap=null,this.displacementMap=null,this.displacementScale=1,this.displacementBias=0,this.wireframe=!1,this.wireframeLinewidth=1,this.setValues(e)}copy(e){return super.copy(e),this.depthPacking=e.depthPacking,this.map=e.map,this.alphaMap=e.alphaMap,this.displacementMap=e.displacementMap,this.displacementScale=e.displacementScale,this.displacementBias=e.displacementBias,this.wireframe=e.wireframe,this.wireframeLinewidth=e.wireframeLinewidth,this}},ll=class extends $t{static get type(){return"MeshDistanceMaterial"}constructor(e){super(),this.isMeshDistanceMaterial=!0,this.map=null,this.alphaMap=null,this.displacementMap=null,this.displacementScale=1,this.displacementBias=0,this.setValues(e)}copy(e){return super.copy(e),this.map=e.map,this.alphaMap=e.alphaMap,this.displacementMap=e.displacementMap,this.displacementScale=e.displacementScale,this.displacementBias=e.displacementBias,this}},Ng=`void main() {
	gl_Position = vec4( position, 1.0 );
}`,Og=`uniform sampler2D shadow_pass;
uniform vec2 resolution;
uniform float radius;
#include <packing>
void main() {
	const float samples = float( VSM_SAMPLES );
	float mean = 0.0;
	float squared_mean = 0.0;
	float uvStride = samples <= 1.0 ? 0.0 : 2.0 / ( samples - 1.0 );
	float uvStart = samples <= 1.0 ? 0.0 : - 1.0;
	for ( float i = 0.0; i < samples; i ++ ) {
		float uvOffset = uvStart + i * uvStride;
		#ifdef HORIZONTAL_PASS
			vec2 distribution = unpackRGBATo2Half( texture2D( shadow_pass, ( gl_FragCoord.xy + vec2( uvOffset, 0.0 ) * radius ) / resolution ) );
			mean += distribution.x;
			squared_mean += distribution.y * distribution.y + distribution.x * distribution.x;
		#else
			float depth = unpackRGBAToDepth( texture2D( shadow_pass, ( gl_FragCoord.xy + vec2( 0.0, uvOffset ) * radius ) / resolution ) );
			mean += depth;
			squared_mean += depth * depth;
		#endif
	}
	mean = mean / samples;
	squared_mean = squared_mean / samples;
	float std_dev = sqrt( squared_mean - mean * mean );
	gl_FragColor = pack2HalfToRGBA( vec2( mean, std_dev ) );
}`;function Fg(i,e,t){let n=new qs,s=new we,r=new we,o=new Ye,a=new al({depthPacking:Td}),l=new ll,c={},h=t.maxTextureSize,u={[En]:Ut,[Ut]:En,[Jt]:Jt},d=new ln({defines:{VSM_SAMPLES:8},uniforms:{shadow_pass:{value:null},resolution:{value:new we},radius:{value:4}},vertexShader:Ng,fragmentShader:Og}),f=d.clone();f.defines.HORIZONTAL_PASS=1;let g=new yt;g.setAttribute("position",new pt(new Float32Array([-1,-1,.5,3,-1,.5,-1,3,.5]),3));let _=new tt(g,d),m=this;this.enabled=!1,this.autoUpdate=!0,this.needsUpdate=!1,this.type=iu;let p=this.type;this.render=function(T,A,R){if(m.enabled===!1||m.autoUpdate===!1&&m.needsUpdate===!1||T.length===0)return;let M=i.getRenderTarget(),v=i.getActiveCubeFace(),I=i.getActiveMipmapLevel(),G=i.state;G.setBlending(ui),G.buffers.color.setClear(1,1,1,1),G.buffers.depth.setTest(!0),G.setScissorTest(!1);let O=p!==Fn&&this.type===Fn,X=p===Fn&&this.type!==Fn;for(let Y=0,V=T.length;Y<V;Y++){let Q=T[Y],B=Q.shadow;if(B===void 0){console.warn("THREE.WebGLShadowMap:",Q,"has no shadow.");continue}if(B.autoUpdate===!1&&B.needsUpdate===!1)continue;s.copy(B.mapSize);let H=B.getFrameExtents();if(s.multiply(H),r.copy(B.mapSize),(s.x>h||s.y>h)&&(s.x>h&&(r.x=Math.floor(h/H.x),s.x=r.x*H.x,B.mapSize.x=r.x),s.y>h&&(r.y=Math.floor(h/H.y),s.y=r.y*H.y,B.mapSize.y=r.y)),B.map===null||O===!0||X===!0){let ie=this.type!==Fn?{minFilter:Nt,magFilter:Nt}:{};B.map!==null&&B.map.dispose(),B.map=new Wn(s.x,s.y,ie),B.map.texture.name=Q.name+".shadowMap",B.camera.updateProjectionMatrix()}i.setRenderTarget(B.map),i.clear();let j=B.getViewportCount();for(let ie=0;ie<j;ie++){let Te=B.getViewport(ie);o.set(r.x*Te.x,r.y*Te.y,r.x*Te.z,r.y*Te.w),G.viewport(o),B.updateMatrices(Q,ie),n=B.getFrustum(),x(A,R,B.camera,Q,this.type)}B.isPointLightShadow!==!0&&this.type===Fn&&w(B,R),B.needsUpdate=!1}p=this.type,m.needsUpdate=!1,i.setRenderTarget(M,v,I)};function w(T,A){let R=e.update(_);d.defines.VSM_SAMPLES!==T.blurSamples&&(d.defines.VSM_SAMPLES=T.blurSamples,f.defines.VSM_SAMPLES=T.blurSamples,d.needsUpdate=!0,f.needsUpdate=!0),T.mapPass===null&&(T.mapPass=new Wn(s.x,s.y)),d.uniforms.shadow_pass.value=T.map.texture,d.uniforms.resolution.value=T.mapSize,d.uniforms.radius.value=T.radius,i.setRenderTarget(T.mapPass),i.clear(),i.renderBufferDirect(A,null,R,d,_,null),f.uniforms.shadow_pass.value=T.mapPass.texture,f.uniforms.resolution.value=T.mapSize,f.uniforms.radius.value=T.radius,i.setRenderTarget(T.map),i.clear(),i.renderBufferDirect(A,null,R,f,_,null)}function b(T,A,R,M){let v=null,I=R.isPointLight===!0?T.customDistanceMaterial:T.customDepthMaterial;if(I!==void 0)v=I;else if(v=R.isPointLight===!0?l:a,i.localClippingEnabled&&A.clipShadows===!0&&Array.isArray(A.clippingPlanes)&&A.clippingPlanes.length!==0||A.displacementMap&&A.displacementScale!==0||A.alphaMap&&A.alphaTest>0||A.map&&A.alphaTest>0){let G=v.uuid,O=A.uuid,X=c[G];X===void 0&&(X={},c[G]=X);let Y=X[O];Y===void 0&&(Y=v.clone(),X[O]=Y,A.addEventListener("dispose",P)),v=Y}if(v.visible=A.visible,v.wireframe=A.wireframe,M===Fn?v.side=A.shadowSide!==null?A.shadowSide:A.side:v.side=A.shadowSide!==null?A.shadowSide:u[A.side],v.alphaMap=A.alphaMap,v.alphaTest=A.alphaTest,v.map=A.map,v.clipShadows=A.clipShadows,v.clippingPlanes=A.clippingPlanes,v.clipIntersection=A.clipIntersection,v.displacementMap=A.displacementMap,v.displacementScale=A.displacementScale,v.displacementBias=A.displacementBias,v.wireframeLinewidth=A.wireframeLinewidth,v.linewidth=A.linewidth,R.isPointLight===!0&&v.isMeshDistanceMaterial===!0){let G=i.properties.get(v);G.light=R}return v}function x(T,A,R,M,v){if(T.visible===!1)return;if(T.layers.test(A.layers)&&(T.isMesh||T.isLine||T.isPoints)&&(T.castShadow||T.receiveShadow&&v===Fn)&&(!T.frustumCulled||n.intersectsObject(T))){T.modelViewMatrix.multiplyMatrices(R.matrixWorldInverse,T.matrixWorld);let O=e.update(T),X=T.material;if(Array.isArray(X)){let Y=O.groups;for(let V=0,Q=Y.length;V<Q;V++){let B=Y[V],H=X[B.materialIndex];if(H&&H.visible){let j=b(T,H,M,v);T.onBeforeShadow(i,T,A,R,O,j,B),i.renderBufferDirect(R,null,O,j,T,B),T.onAfterShadow(i,T,A,R,O,j,B)}}}else if(X.visible){let Y=b(T,X,M,v);T.onBeforeShadow(i,T,A,R,O,Y,null),i.renderBufferDirect(R,null,O,Y,T,null),T.onAfterShadow(i,T,A,R,O,Y,null)}}let G=T.children;for(let O=0,X=G.length;O<X;O++)x(G[O],A,R,M,v)}function P(T){T.target.removeEventListener("dispose",P);for(let R in c){let M=c[R],v=T.target.uuid;v in M&&(M[v].dispose(),delete M[v])}}}var Bg={[pa]:ma,[ga]:ya,[_a]:va,[ls]:xa,[ma]:pa,[ya]:ga,[va]:_a,[xa]:ls};function zg(i,e){function t(){let L=!1,ae=new Ye,W=null,J=new Ye(0,0,0,0);return{setMask:function(ue){W!==ue&&!L&&(i.colorMask(ue,ue,ue,ue),W=ue)},setLocked:function(ue){L=ue},setClear:function(ue,ce,De,ut,It){It===!0&&(ue*=ut,ce*=ut,De*=ut),ae.set(ue,ce,De,ut),J.equals(ae)===!1&&(i.clearColor(ue,ce,De,ut),J.copy(ae))},reset:function(){L=!1,W=null,J.set(-1,0,0,0)}}}function n(){let L=!1,ae=!1,W=null,J=null,ue=null;return{setReversed:function(ce){if(ae!==ce){let De=e.get("EXT_clip_control");ae?De.clipControlEXT(De.LOWER_LEFT_EXT,De.ZERO_TO_ONE_EXT):De.clipControlEXT(De.LOWER_LEFT_EXT,De.NEGATIVE_ONE_TO_ONE_EXT);let ut=ue;ue=null,this.setClear(ut)}ae=ce},getReversed:function(){return ae},setTest:function(ce){ce?se(i.DEPTH_TEST):Me(i.DEPTH_TEST)},setMask:function(ce){W!==ce&&!L&&(i.depthMask(ce),W=ce)},setFunc:function(ce){if(ae&&(ce=Bg[ce]),J!==ce){switch(ce){case pa:i.depthFunc(i.NEVER);break;case ma:i.depthFunc(i.ALWAYS);break;case ga:i.depthFunc(i.LESS);break;case ls:i.depthFunc(i.LEQUAL);break;case _a:i.depthFunc(i.EQUAL);break;case xa:i.depthFunc(i.GEQUAL);break;case ya:i.depthFunc(i.GREATER);break;case va:i.depthFunc(i.NOTEQUAL);break;default:i.depthFunc(i.LEQUAL)}J=ce}},setLocked:function(ce){L=ce},setClear:function(ce){ue!==ce&&(ae&&(ce=1-ce),i.clearDepth(ce),ue=ce)},reset:function(){L=!1,W=null,J=null,ue=null,ae=!1}}}function s(){let L=!1,ae=null,W=null,J=null,ue=null,ce=null,De=null,ut=null,It=null;return{setTest:function(je){L||(je?se(i.STENCIL_TEST):Me(i.STENCIL_TEST))},setMask:function(je){ae!==je&&!L&&(i.stencilMask(je),ae=je)},setFunc:function(je,dn,Cn){(W!==je||J!==dn||ue!==Cn)&&(i.stencilFunc(je,dn,Cn),W=je,J=dn,ue=Cn)},setOp:function(je,dn,Cn){(ce!==je||De!==dn||ut!==Cn)&&(i.stencilOp(je,dn,Cn),ce=je,De=dn,ut=Cn)},setLocked:function(je){L=je},setClear:function(je){It!==je&&(i.clearStencil(je),It=je)},reset:function(){L=!1,ae=null,W=null,J=null,ue=null,ce=null,De=null,ut=null,It=null}}}let r=new t,o=new n,a=new s,l=new WeakMap,c=new WeakMap,h={},u={},d=new WeakMap,f=[],g=null,_=!1,m=null,p=null,w=null,b=null,x=null,P=null,T=null,A=new Ae(0,0,0),R=0,M=!1,v=null,I=null,G=null,O=null,X=null,Y=i.getParameter(i.MAX_COMBINED_TEXTURE_IMAGE_UNITS),V=!1,Q=0,B=i.getParameter(i.VERSION);B.indexOf("WebGL")!==-1?(Q=parseFloat(/^WebGL (\d)/.exec(B)[1]),V=Q>=1):B.indexOf("OpenGL ES")!==-1&&(Q=parseFloat(/^OpenGL ES (\d)/.exec(B)[1]),V=Q>=2);let H=null,j={},ie=i.getParameter(i.SCISSOR_BOX),Te=i.getParameter(i.VIEWPORT),Re=new Ye().fromArray(ie),q=new Ye().fromArray(Te);function ee(L,ae,W,J){let ue=new Uint8Array(4),ce=i.createTexture();i.bindTexture(L,ce),i.texParameteri(L,i.TEXTURE_MIN_FILTER,i.NEAREST),i.texParameteri(L,i.TEXTURE_MAG_FILTER,i.NEAREST);for(let De=0;De<W;De++)L===i.TEXTURE_3D||L===i.TEXTURE_2D_ARRAY?i.texImage3D(ae,0,i.RGBA,1,1,J,0,i.RGBA,i.UNSIGNED_BYTE,ue):i.texImage2D(ae+De,0,i.RGBA,1,1,0,i.RGBA,i.UNSIGNED_BYTE,ue);return ce}let me={};me[i.TEXTURE_2D]=ee(i.TEXTURE_2D,i.TEXTURE_2D,1),me[i.TEXTURE_CUBE_MAP]=ee(i.TEXTURE_CUBE_MAP,i.TEXTURE_CUBE_MAP_POSITIVE_X,6),me[i.TEXTURE_2D_ARRAY]=ee(i.TEXTURE_2D_ARRAY,i.TEXTURE_2D_ARRAY,1,1),me[i.TEXTURE_3D]=ee(i.TEXTURE_3D,i.TEXTURE_3D,1,1),r.setClear(0,0,0,1),o.setClear(1),a.setClear(0),se(i.DEPTH_TEST),o.setFunc(ls),He(!1),Ve(Oc),se(i.CULL_FACE),N(ui);function se(L){h[L]!==!0&&(i.enable(L),h[L]=!0)}function Me(L){h[L]!==!1&&(i.disable(L),h[L]=!1)}function Pe(L,ae){return u[L]!==ae?(i.bindFramebuffer(L,ae),u[L]=ae,L===i.DRAW_FRAMEBUFFER&&(u[i.FRAMEBUFFER]=ae),L===i.FRAMEBUFFER&&(u[i.DRAW_FRAMEBUFFER]=ae),!0):!1}function Be(L,ae){let W=f,J=!1;if(L){W=d.get(ae),W===void 0&&(W=[],d.set(ae,W));let ue=L.textures;if(W.length!==ue.length||W[0]!==i.COLOR_ATTACHMENT0){for(let ce=0,De=ue.length;ce<De;ce++)W[ce]=i.COLOR_ATTACHMENT0+ce;W.length=ue.length,J=!0}}else W[0]!==i.BACK&&(W[0]=i.BACK,J=!0);J&&i.drawBuffers(W)}function ct(L){return g!==L?(i.useProgram(L),g=L,!0):!1}let We={[Ci]:i.FUNC_ADD,[Qu]:i.FUNC_SUBTRACT,[ed]:i.FUNC_REVERSE_SUBTRACT};We[td]=i.MIN,We[nd]=i.MAX;let ft={[id]:i.ZERO,[sd]:i.ONE,[rd]:i.SRC_COLOR,[da]:i.SRC_ALPHA,[ud]:i.SRC_ALPHA_SATURATE,[cd]:i.DST_COLOR,[ad]:i.DST_ALPHA,[od]:i.ONE_MINUS_SRC_COLOR,[fa]:i.ONE_MINUS_SRC_ALPHA,[hd]:i.ONE_MINUS_DST_COLOR,[ld]:i.ONE_MINUS_DST_ALPHA,[dd]:i.CONSTANT_COLOR,[fd]:i.ONE_MINUS_CONSTANT_COLOR,[pd]:i.CONSTANT_ALPHA,[md]:i.ONE_MINUS_CONSTANT_ALPHA};function N(L,ae,W,J,ue,ce,De,ut,It,je){if(L===ui){_===!0&&(Me(i.BLEND),_=!1);return}if(_===!1&&(se(i.BLEND),_=!0),L!==$u){if(L!==m||je!==M){if((p!==Ci||x!==Ci)&&(i.blendEquation(i.FUNC_ADD),p=Ci,x=Ci),je)switch(L){case is:i.blendFuncSeparate(i.ONE,i.ONE_MINUS_SRC_ALPHA,i.ONE,i.ONE_MINUS_SRC_ALPHA);break;case Fc:i.blendFunc(i.ONE,i.ONE);break;case Bc:i.blendFuncSeparate(i.ZERO,i.ONE_MINUS_SRC_COLOR,i.ZERO,i.ONE);break;case zc:i.blendFuncSeparate(i.ZERO,i.SRC_COLOR,i.ZERO,i.SRC_ALPHA);break;default:console.error("THREE.WebGLState: Invalid blending: ",L);break}else switch(L){case is:i.blendFuncSeparate(i.SRC_ALPHA,i.ONE_MINUS_SRC_ALPHA,i.ONE,i.ONE_MINUS_SRC_ALPHA);break;case Fc:i.blendFunc(i.SRC_ALPHA,i.ONE);break;case Bc:i.blendFuncSeparate(i.ZERO,i.ONE_MINUS_SRC_COLOR,i.ZERO,i.ONE);break;case zc:i.blendFunc(i.ZERO,i.SRC_COLOR);break;default:console.error("THREE.WebGLState: Invalid blending: ",L);break}w=null,b=null,P=null,T=null,A.set(0,0,0),R=0,m=L,M=je}return}ue=ue||ae,ce=ce||W,De=De||J,(ae!==p||ue!==x)&&(i.blendEquationSeparate(We[ae],We[ue]),p=ae,x=ue),(W!==w||J!==b||ce!==P||De!==T)&&(i.blendFuncSeparate(ft[W],ft[J],ft[ce],ft[De]),w=W,b=J,P=ce,T=De),(ut.equals(A)===!1||It!==R)&&(i.blendColor(ut.r,ut.g,ut.b,It),A.copy(ut),R=It),m=L,M=!1}function nn(L,ae){L.side===Jt?Me(i.CULL_FACE):se(i.CULL_FACE);let W=L.side===Ut;ae&&(W=!W),He(W),L.blending===is&&L.transparent===!1?N(ui):N(L.blending,L.blendEquation,L.blendSrc,L.blendDst,L.blendEquationAlpha,L.blendSrcAlpha,L.blendDstAlpha,L.blendColor,L.blendAlpha,L.premultipliedAlpha),o.setFunc(L.depthFunc),o.setTest(L.depthTest),o.setMask(L.depthWrite),r.setMask(L.colorWrite);let J=L.stencilWrite;a.setTest(J),J&&(a.setMask(L.stencilWriteMask),a.setFunc(L.stencilFunc,L.stencilRef,L.stencilFuncMask),a.setOp(L.stencilFail,L.stencilZFail,L.stencilZPass)),ot(L.polygonOffset,L.polygonOffsetFactor,L.polygonOffsetUnits),L.alphaToCoverage===!0?se(i.SAMPLE_ALPHA_TO_COVERAGE):Me(i.SAMPLE_ALPHA_TO_COVERAGE)}function He(L){v!==L&&(L?i.frontFace(i.CW):i.frontFace(i.CCW),v=L)}function Ve(L){L!==Ju?(se(i.CULL_FACE),L!==I&&(L===Oc?i.cullFace(i.BACK):L===ju?i.cullFace(i.FRONT):i.cullFace(i.FRONT_AND_BACK))):Me(i.CULL_FACE),I=L}function be(L){L!==G&&(V&&i.lineWidth(L),G=L)}function ot(L,ae,W){L?(se(i.POLYGON_OFFSET_FILL),(O!==ae||X!==W)&&(i.polygonOffset(ae,W),O=ae,X=W)):Me(i.POLYGON_OFFSET_FILL)}function Se(L){L?se(i.SCISSOR_TEST):Me(i.SCISSOR_TEST)}function E(L){L===void 0&&(L=i.TEXTURE0+Y-1),H!==L&&(i.activeTexture(L),H=L)}function y(L,ae,W){W===void 0&&(H===null?W=i.TEXTURE0+Y-1:W=H);let J=j[W];J===void 0&&(J={type:void 0,texture:void 0},j[W]=J),(J.type!==L||J.texture!==ae)&&(H!==W&&(i.activeTexture(W),H=W),i.bindTexture(L,ae||me[L]),J.type=L,J.texture=ae)}function F(){let L=j[H];L!==void 0&&L.type!==void 0&&(i.bindTexture(L.type,null),L.type=void 0,L.texture=void 0)}function K(){try{i.compressedTexImage2D.apply(i,arguments)}catch(L){console.error("THREE.WebGLState:",L)}}function $(){try{i.compressedTexImage3D.apply(i,arguments)}catch(L){console.error("THREE.WebGLState:",L)}}function Z(){try{i.texSubImage2D.apply(i,arguments)}catch(L){console.error("THREE.WebGLState:",L)}}function ye(){try{i.texSubImage3D.apply(i,arguments)}catch(L){console.error("THREE.WebGLState:",L)}}function le(){try{i.compressedTexSubImage2D.apply(i,arguments)}catch(L){console.error("THREE.WebGLState:",L)}}function de(){try{i.compressedTexSubImage3D.apply(i,arguments)}catch(L){console.error("THREE.WebGLState:",L)}}function Xe(){try{i.texStorage2D.apply(i,arguments)}catch(L){console.error("THREE.WebGLState:",L)}}function te(){try{i.texStorage3D.apply(i,arguments)}catch(L){console.error("THREE.WebGLState:",L)}}function fe(){try{i.texImage2D.apply(i,arguments)}catch(L){console.error("THREE.WebGLState:",L)}}function Ee(){try{i.texImage3D.apply(i,arguments)}catch(L){console.error("THREE.WebGLState:",L)}}function Ce(L){Re.equals(L)===!1&&(i.scissor(L.x,L.y,L.z,L.w),Re.copy(L))}function pe(L){q.equals(L)===!1&&(i.viewport(L.x,L.y,L.z,L.w),q.copy(L))}function Ge(L,ae){let W=c.get(ae);W===void 0&&(W=new WeakMap,c.set(ae,W));let J=W.get(L);J===void 0&&(J=i.getUniformBlockIndex(ae,L.name),W.set(L,J))}function Oe(L,ae){let J=c.get(ae).get(L);l.get(ae)!==J&&(i.uniformBlockBinding(ae,J,L.__bindingPointIndex),l.set(ae,J))}function it(){i.disable(i.BLEND),i.disable(i.CULL_FACE),i.disable(i.DEPTH_TEST),i.disable(i.POLYGON_OFFSET_FILL),i.disable(i.SCISSOR_TEST),i.disable(i.STENCIL_TEST),i.disable(i.SAMPLE_ALPHA_TO_COVERAGE),i.blendEquation(i.FUNC_ADD),i.blendFunc(i.ONE,i.ZERO),i.blendFuncSeparate(i.ONE,i.ZERO,i.ONE,i.ZERO),i.blendColor(0,0,0,0),i.colorMask(!0,!0,!0,!0),i.clearColor(0,0,0,0),i.depthMask(!0),i.depthFunc(i.LESS),o.setReversed(!1),i.clearDepth(1),i.stencilMask(4294967295),i.stencilFunc(i.ALWAYS,0,4294967295),i.stencilOp(i.KEEP,i.KEEP,i.KEEP),i.clearStencil(0),i.cullFace(i.BACK),i.frontFace(i.CCW),i.polygonOffset(0,0),i.activeTexture(i.TEXTURE0),i.bindFramebuffer(i.FRAMEBUFFER,null),i.bindFramebuffer(i.DRAW_FRAMEBUFFER,null),i.bindFramebuffer(i.READ_FRAMEBUFFER,null),i.useProgram(null),i.lineWidth(1),i.scissor(0,0,i.canvas.width,i.canvas.height),i.viewport(0,0,i.canvas.width,i.canvas.height),h={},H=null,j={},u={},d=new WeakMap,f=[],g=null,_=!1,m=null,p=null,w=null,b=null,x=null,P=null,T=null,A=new Ae(0,0,0),R=0,M=!1,v=null,I=null,G=null,O=null,X=null,Re.set(0,0,i.canvas.width,i.canvas.height),q.set(0,0,i.canvas.width,i.canvas.height),r.reset(),o.reset(),a.reset()}return{buffers:{color:r,depth:o,stencil:a},enable:se,disable:Me,bindFramebuffer:Pe,drawBuffers:Be,useProgram:ct,setBlending:N,setMaterial:nn,setFlipSided:He,setCullFace:Ve,setLineWidth:be,setPolygonOffset:ot,setScissorTest:Se,activeTexture:E,bindTexture:y,unbindTexture:F,compressedTexImage2D:K,compressedTexImage3D:$,texImage2D:fe,texImage3D:Ee,updateUBOMapping:Ge,uniformBlockBinding:Oe,texStorage2D:Xe,texStorage3D:te,texSubImage2D:Z,texSubImage3D:ye,compressedTexSubImage2D:le,compressedTexSubImage3D:de,scissor:Ce,viewport:pe,reset:it}}function Oh(i,e,t,n){let s=kg(n);switch(t){case cu:return i*e;case uu:return i*e;case du:return i*e*2;case Ll:return i*e/s.components*s.byteLength;case Dl:return i*e/s.components*s.byteLength;case fu:return i*e*2/s.components*s.byteLength;case Ul:return i*e*2/s.components*s.byteLength;case hu:return i*e*3/s.components*s.byteLength;case on:return i*e*4/s.components*s.byteLength;case Nl:return i*e*4/s.components*s.byteLength;case Hr:case Vr:return Math.floor((i+3)/4)*Math.floor((e+3)/4)*8;case Gr:case Wr:return Math.floor((i+3)/4)*Math.floor((e+3)/4)*16;case wa:case Aa:return Math.max(i,16)*Math.max(e,8)/4;case ba:case Ea:return Math.max(i,8)*Math.max(e,8)/2;case Ta:case Ra:return Math.floor((i+3)/4)*Math.floor((e+3)/4)*8;case Ca:return Math.floor((i+3)/4)*Math.floor((e+3)/4)*16;case Ia:return Math.floor((i+3)/4)*Math.floor((e+3)/4)*16;case Pa:return Math.floor((i+4)/5)*Math.floor((e+3)/4)*16;case La:return Math.floor((i+4)/5)*Math.floor((e+4)/5)*16;case Da:return Math.floor((i+5)/6)*Math.floor((e+4)/5)*16;case Ua:return Math.floor((i+5)/6)*Math.floor((e+5)/6)*16;case Na:return Math.floor((i+7)/8)*Math.floor((e+4)/5)*16;case Oa:return Math.floor((i+7)/8)*Math.floor((e+5)/6)*16;case Fa:return Math.floor((i+7)/8)*Math.floor((e+7)/8)*16;case Ba:return Math.floor((i+9)/10)*Math.floor((e+4)/5)*16;case za:return Math.floor((i+9)/10)*Math.floor((e+5)/6)*16;case ka:return Math.floor((i+9)/10)*Math.floor((e+7)/8)*16;case Ha:return Math.floor((i+9)/10)*Math.floor((e+9)/10)*16;case Va:return Math.floor((i+11)/12)*Math.floor((e+9)/10)*16;case Ga:return Math.floor((i+11)/12)*Math.floor((e+11)/12)*16;case Xr:case Wa:case Xa:return Math.ceil(i/4)*Math.ceil(e/4)*16;case pu:case qa:return Math.ceil(i/4)*Math.ceil(e/4)*8;case Ya:case Za:return Math.ceil(i/4)*Math.ceil(e/4)*16}throw new Error(`Unable to determine texture byte length for ${t} format.`)}function kg(i){switch(i){case Vn:case ou:return{byteLength:1,components:1};case Gs:case au:case tr:return{byteLength:2,components:1};case Il:case Pl:return{byteLength:2,components:4};case Pi:case Cl:case xn:return{byteLength:4,components:1};case lu:return{byteLength:4,components:3}}throw new Error(`Unknown texture type ${i}.`)}function Hg(i,e,t,n,s,r,o){let a=e.has("WEBGL_multisampled_render_to_texture")?e.get("WEBGL_multisampled_render_to_texture"):null,l=typeof navigator>"u"?!1:/OculusBrowser/g.test(navigator.userAgent),c=new we,h=new WeakMap,u,d=new WeakMap,f=!1;try{f=typeof OffscreenCanvas<"u"&&new OffscreenCanvas(1,1).getContext("2d")!==null}catch{}function g(E,y){return f?new OffscreenCanvas(E,y):Ws("canvas")}function _(E,y,F){let K=1,$=Se(E);if(($.width>F||$.height>F)&&(K=F/Math.max($.width,$.height)),K<1)if(typeof HTMLImageElement<"u"&&E instanceof HTMLImageElement||typeof HTMLCanvasElement<"u"&&E instanceof HTMLCanvasElement||typeof ImageBitmap<"u"&&E instanceof ImageBitmap||typeof VideoFrame<"u"&&E instanceof VideoFrame){let Z=Math.floor(K*$.width),ye=Math.floor(K*$.height);u===void 0&&(u=g(Z,ye));let le=y?g(Z,ye):u;return le.width=Z,le.height=ye,le.getContext("2d").drawImage(E,0,0,Z,ye),console.warn("THREE.WebGLRenderer: Texture has been resized from ("+$.width+"x"+$.height+") to ("+Z+"x"+ye+")."),le}else return"data"in E&&console.warn("THREE.WebGLRenderer: Image in DataTexture is too big ("+$.width+"x"+$.height+")."),E;return E}function m(E){return E.generateMipmaps}function p(E){i.generateMipmap(E)}function w(E){return E.isWebGLCubeRenderTarget?i.TEXTURE_CUBE_MAP:E.isWebGL3DRenderTarget?i.TEXTURE_3D:E.isWebGLArrayRenderTarget||E.isCompressedArrayTexture?i.TEXTURE_2D_ARRAY:i.TEXTURE_2D}function b(E,y,F,K,$=!1){if(E!==null){if(i[E]!==void 0)return i[E];console.warn("THREE.WebGLRenderer: Attempt to use non-existing WebGL internal format '"+E+"'")}let Z=y;if(y===i.RED&&(F===i.FLOAT&&(Z=i.R32F),F===i.HALF_FLOAT&&(Z=i.R16F),F===i.UNSIGNED_BYTE&&(Z=i.R8)),y===i.RED_INTEGER&&(F===i.UNSIGNED_BYTE&&(Z=i.R8UI),F===i.UNSIGNED_SHORT&&(Z=i.R16UI),F===i.UNSIGNED_INT&&(Z=i.R32UI),F===i.BYTE&&(Z=i.R8I),F===i.SHORT&&(Z=i.R16I),F===i.INT&&(Z=i.R32I)),y===i.RG&&(F===i.FLOAT&&(Z=i.RG32F),F===i.HALF_FLOAT&&(Z=i.RG16F),F===i.UNSIGNED_BYTE&&(Z=i.RG8)),y===i.RG_INTEGER&&(F===i.UNSIGNED_BYTE&&(Z=i.RG8UI),F===i.UNSIGNED_SHORT&&(Z=i.RG16UI),F===i.UNSIGNED_INT&&(Z=i.RG32UI),F===i.BYTE&&(Z=i.RG8I),F===i.SHORT&&(Z=i.RG16I),F===i.INT&&(Z=i.RG32I)),y===i.RGB_INTEGER&&(F===i.UNSIGNED_BYTE&&(Z=i.RGB8UI),F===i.UNSIGNED_SHORT&&(Z=i.RGB16UI),F===i.UNSIGNED_INT&&(Z=i.RGB32UI),F===i.BYTE&&(Z=i.RGB8I),F===i.SHORT&&(Z=i.RGB16I),F===i.INT&&(Z=i.RGB32I)),y===i.RGBA_INTEGER&&(F===i.UNSIGNED_BYTE&&(Z=i.RGBA8UI),F===i.UNSIGNED_SHORT&&(Z=i.RGBA16UI),F===i.UNSIGNED_INT&&(Z=i.RGBA32UI),F===i.BYTE&&(Z=i.RGBA8I),F===i.SHORT&&(Z=i.RGBA16I),F===i.INT&&(Z=i.RGBA32I)),y===i.RGB&&F===i.UNSIGNED_INT_5_9_9_9_REV&&(Z=i.RGB9_E5),y===i.RGBA){let ye=$?Eo:ke.getTransfer(K);F===i.FLOAT&&(Z=i.RGBA32F),F===i.HALF_FLOAT&&(Z=i.RGBA16F),F===i.UNSIGNED_BYTE&&(Z=ye===Qe?i.SRGB8_ALPHA8:i.RGBA8),F===i.UNSIGNED_SHORT_4_4_4_4&&(Z=i.RGBA4),F===i.UNSIGNED_SHORT_5_5_5_1&&(Z=i.RGB5_A1)}return(Z===i.R16F||Z===i.R32F||Z===i.RG16F||Z===i.RG32F||Z===i.RGBA16F||Z===i.RGBA32F)&&e.get("EXT_color_buffer_float"),Z}function x(E,y){let F;return E?y===null||y===Pi||y===us?F=i.DEPTH24_STENCIL8:y===xn?F=i.DEPTH32F_STENCIL8:y===Gs&&(F=i.DEPTH24_STENCIL8,console.warn("DepthTexture: 16 bit depth attachment is not supported with stencil. Using 24-bit attachment.")):y===null||y===Pi||y===us?F=i.DEPTH_COMPONENT24:y===xn?F=i.DEPTH_COMPONENT32F:y===Gs&&(F=i.DEPTH_COMPONENT16),F}function P(E,y){return m(E)===!0||E.isFramebufferTexture&&E.minFilter!==Nt&&E.minFilter!==Vt?Math.log2(Math.max(y.width,y.height))+1:E.mipmaps!==void 0&&E.mipmaps.length>0?E.mipmaps.length:E.isCompressedTexture&&Array.isArray(E.image)?y.mipmaps.length:1}function T(E){let y=E.target;y.removeEventListener("dispose",T),R(y),y.isVideoTexture&&h.delete(y)}function A(E){let y=E.target;y.removeEventListener("dispose",A),v(y)}function R(E){let y=n.get(E);if(y.__webglInit===void 0)return;let F=E.source,K=d.get(F);if(K){let $=K[y.__cacheKey];$.usedTimes--,$.usedTimes===0&&M(E),Object.keys(K).length===0&&d.delete(F)}n.remove(E)}function M(E){let y=n.get(E);i.deleteTexture(y.__webglTexture);let F=E.source,K=d.get(F);delete K[y.__cacheKey],o.memory.textures--}function v(E){let y=n.get(E);if(E.depthTexture&&(E.depthTexture.dispose(),n.remove(E.depthTexture)),E.isWebGLCubeRenderTarget)for(let K=0;K<6;K++){if(Array.isArray(y.__webglFramebuffer[K]))for(let $=0;$<y.__webglFramebuffer[K].length;$++)i.deleteFramebuffer(y.__webglFramebuffer[K][$]);else i.deleteFramebuffer(y.__webglFramebuffer[K]);y.__webglDepthbuffer&&i.deleteRenderbuffer(y.__webglDepthbuffer[K])}else{if(Array.isArray(y.__webglFramebuffer))for(let K=0;K<y.__webglFramebuffer.length;K++)i.deleteFramebuffer(y.__webglFramebuffer[K]);else i.deleteFramebuffer(y.__webglFramebuffer);if(y.__webglDepthbuffer&&i.deleteRenderbuffer(y.__webglDepthbuffer),y.__webglMultisampledFramebuffer&&i.deleteFramebuffer(y.__webglMultisampledFramebuffer),y.__webglColorRenderbuffer)for(let K=0;K<y.__webglColorRenderbuffer.length;K++)y.__webglColorRenderbuffer[K]&&i.deleteRenderbuffer(y.__webglColorRenderbuffer[K]);y.__webglDepthRenderbuffer&&i.deleteRenderbuffer(y.__webglDepthRenderbuffer)}let F=E.textures;for(let K=0,$=F.length;K<$;K++){let Z=n.get(F[K]);Z.__webglTexture&&(i.deleteTexture(Z.__webglTexture),o.memory.textures--),n.remove(F[K])}n.remove(E)}let I=0;function G(){I=0}function O(){let E=I;return E>=s.maxTextures&&console.warn("THREE.WebGLTextures: Trying to use "+E+" texture units while this GPU supports only "+s.maxTextures),I+=1,E}function X(E){let y=[];return y.push(E.wrapS),y.push(E.wrapT),y.push(E.wrapR||0),y.push(E.magFilter),y.push(E.minFilter),y.push(E.anisotropy),y.push(E.internalFormat),y.push(E.format),y.push(E.type),y.push(E.generateMipmaps),y.push(E.premultiplyAlpha),y.push(E.flipY),y.push(E.unpackAlignment),y.push(E.colorSpace),y.join()}function Y(E,y){let F=n.get(E);if(E.isVideoTexture&&be(E),E.isRenderTargetTexture===!1&&E.version>0&&F.__version!==E.version){let K=E.image;if(K===null)console.warn("THREE.WebGLRenderer: Texture marked for update but no image data found.");else if(K.complete===!1)console.warn("THREE.WebGLRenderer: Texture marked for update but image is incomplete");else{q(F,E,y);return}}t.bindTexture(i.TEXTURE_2D,F.__webglTexture,i.TEXTURE0+y)}function V(E,y){let F=n.get(E);if(E.version>0&&F.__version!==E.version){q(F,E,y);return}t.bindTexture(i.TEXTURE_2D_ARRAY,F.__webglTexture,i.TEXTURE0+y)}function Q(E,y){let F=n.get(E);if(E.version>0&&F.__version!==E.version){q(F,E,y);return}t.bindTexture(i.TEXTURE_3D,F.__webglTexture,i.TEXTURE0+y)}function B(E,y){let F=n.get(E);if(E.version>0&&F.__version!==E.version){ee(F,E,y);return}t.bindTexture(i.TEXTURE_CUBE_MAP,F.__webglTexture,i.TEXTURE0+y)}let H={[Hn]:i.REPEAT,[Bn]:i.CLAMP_TO_EDGE,[Vs]:i.MIRRORED_REPEAT},j={[Nt]:i.NEAREST,[Rl]:i.NEAREST_MIPMAP_NEAREST,[ts]:i.NEAREST_MIPMAP_LINEAR,[Vt]:i.LINEAR,[zs]:i.LINEAR_MIPMAP_NEAREST,[wn]:i.LINEAR_MIPMAP_LINEAR},ie={[Cd]:i.NEVER,[Nd]:i.ALWAYS,[Id]:i.LESS,[_u]:i.LEQUAL,[Pd]:i.EQUAL,[Ud]:i.GEQUAL,[Ld]:i.GREATER,[Dd]:i.NOTEQUAL};function Te(E,y){if(y.type===xn&&e.has("OES_texture_float_linear")===!1&&(y.magFilter===Vt||y.magFilter===zs||y.magFilter===ts||y.magFilter===wn||y.minFilter===Vt||y.minFilter===zs||y.minFilter===ts||y.minFilter===wn)&&console.warn("THREE.WebGLRenderer: Unable to use linear filtering with floating point textures. OES_texture_float_linear not supported on this device."),i.texParameteri(E,i.TEXTURE_WRAP_S,H[y.wrapS]),i.texParameteri(E,i.TEXTURE_WRAP_T,H[y.wrapT]),(E===i.TEXTURE_3D||E===i.TEXTURE_2D_ARRAY)&&i.texParameteri(E,i.TEXTURE_WRAP_R,H[y.wrapR]),i.texParameteri(E,i.TEXTURE_MAG_FILTER,j[y.magFilter]),i.texParameteri(E,i.TEXTURE_MIN_FILTER,j[y.minFilter]),y.compareFunction&&(i.texParameteri(E,i.TEXTURE_COMPARE_MODE,i.COMPARE_REF_TO_TEXTURE),i.texParameteri(E,i.TEXTURE_COMPARE_FUNC,ie[y.compareFunction])),e.has("EXT_texture_filter_anisotropic")===!0){if(y.magFilter===Nt||y.minFilter!==ts&&y.minFilter!==wn||y.type===xn&&e.has("OES_texture_float_linear")===!1)return;if(y.anisotropy>1||n.get(y).__currentAnisotropy){let F=e.get("EXT_texture_filter_anisotropic");i.texParameterf(E,F.TEXTURE_MAX_ANISOTROPY_EXT,Math.min(y.anisotropy,s.getMaxAnisotropy())),n.get(y).__currentAnisotropy=y.anisotropy}}}function Re(E,y){let F=!1;E.__webglInit===void 0&&(E.__webglInit=!0,y.addEventListener("dispose",T));let K=y.source,$=d.get(K);$===void 0&&($={},d.set(K,$));let Z=X(y);if(Z!==E.__cacheKey){$[Z]===void 0&&($[Z]={texture:i.createTexture(),usedTimes:0},o.memory.textures++,F=!0),$[Z].usedTimes++;let ye=$[E.__cacheKey];ye!==void 0&&($[E.__cacheKey].usedTimes--,ye.usedTimes===0&&M(y)),E.__cacheKey=Z,E.__webglTexture=$[Z].texture}return F}function q(E,y,F){let K=i.TEXTURE_2D;(y.isDataArrayTexture||y.isCompressedArrayTexture)&&(K=i.TEXTURE_2D_ARRAY),y.isData3DTexture&&(K=i.TEXTURE_3D);let $=Re(E,y),Z=y.source;t.bindTexture(K,E.__webglTexture,i.TEXTURE0+F);let ye=n.get(Z);if(Z.version!==ye.__version||$===!0){t.activeTexture(i.TEXTURE0+F);let le=ke.getPrimaries(ke.workingColorSpace),de=y.colorSpace===li?null:ke.getPrimaries(y.colorSpace),Xe=y.colorSpace===li||le===de?i.NONE:i.BROWSER_DEFAULT_WEBGL;i.pixelStorei(i.UNPACK_FLIP_Y_WEBGL,y.flipY),i.pixelStorei(i.UNPACK_PREMULTIPLY_ALPHA_WEBGL,y.premultiplyAlpha),i.pixelStorei(i.UNPACK_ALIGNMENT,y.unpackAlignment),i.pixelStorei(i.UNPACK_COLORSPACE_CONVERSION_WEBGL,Xe);let te=_(y.image,!1,s.maxTextureSize);te=ot(y,te);let fe=r.convert(y.format,y.colorSpace),Ee=r.convert(y.type),Ce=b(y.internalFormat,fe,Ee,y.colorSpace,y.isVideoTexture);Te(K,y);let pe,Ge=y.mipmaps,Oe=y.isVideoTexture!==!0,it=ye.__version===void 0||$===!0,L=Z.dataReady,ae=P(y,te);if(y.isDepthTexture)Ce=x(y.format===ds,y.type),it&&(Oe?t.texStorage2D(i.TEXTURE_2D,1,Ce,te.width,te.height):t.texImage2D(i.TEXTURE_2D,0,Ce,te.width,te.height,0,fe,Ee,null));else if(y.isDataTexture)if(Ge.length>0){Oe&&it&&t.texStorage2D(i.TEXTURE_2D,ae,Ce,Ge[0].width,Ge[0].height);for(let W=0,J=Ge.length;W<J;W++)pe=Ge[W],Oe?L&&t.texSubImage2D(i.TEXTURE_2D,W,0,0,pe.width,pe.height,fe,Ee,pe.data):t.texImage2D(i.TEXTURE_2D,W,Ce,pe.width,pe.height,0,fe,Ee,pe.data);y.generateMipmaps=!1}else Oe?(it&&t.texStorage2D(i.TEXTURE_2D,ae,Ce,te.width,te.height),L&&t.texSubImage2D(i.TEXTURE_2D,0,0,0,te.width,te.height,fe,Ee,te.data)):t.texImage2D(i.TEXTURE_2D,0,Ce,te.width,te.height,0,fe,Ee,te.data);else if(y.isCompressedTexture)if(y.isCompressedArrayTexture){Oe&&it&&t.texStorage3D(i.TEXTURE_2D_ARRAY,ae,Ce,Ge[0].width,Ge[0].height,te.depth);for(let W=0,J=Ge.length;W<J;W++)if(pe=Ge[W],y.format!==on)if(fe!==null)if(Oe){if(L)if(y.layerUpdates.size>0){let ue=Oh(pe.width,pe.height,y.format,y.type);for(let ce of y.layerUpdates){let De=pe.data.subarray(ce*ue/pe.data.BYTES_PER_ELEMENT,(ce+1)*ue/pe.data.BYTES_PER_ELEMENT);t.compressedTexSubImage3D(i.TEXTURE_2D_ARRAY,W,0,0,ce,pe.width,pe.height,1,fe,De)}y.clearLayerUpdates()}else t.compressedTexSubImage3D(i.TEXTURE_2D_ARRAY,W,0,0,0,pe.width,pe.height,te.depth,fe,pe.data)}else t.compressedTexImage3D(i.TEXTURE_2D_ARRAY,W,Ce,pe.width,pe.height,te.depth,0,pe.data,0,0);else console.warn("THREE.WebGLRenderer: Attempt to load unsupported compressed texture format in .uploadTexture()");else Oe?L&&t.texSubImage3D(i.TEXTURE_2D_ARRAY,W,0,0,0,pe.width,pe.height,te.depth,fe,Ee,pe.data):t.texImage3D(i.TEXTURE_2D_ARRAY,W,Ce,pe.width,pe.height,te.depth,0,fe,Ee,pe.data)}else{Oe&&it&&t.texStorage2D(i.TEXTURE_2D,ae,Ce,Ge[0].width,Ge[0].height);for(let W=0,J=Ge.length;W<J;W++)pe=Ge[W],y.format!==on?fe!==null?Oe?L&&t.compressedTexSubImage2D(i.TEXTURE_2D,W,0,0,pe.width,pe.height,fe,pe.data):t.compressedTexImage2D(i.TEXTURE_2D,W,Ce,pe.width,pe.height,0,pe.data):console.warn("THREE.WebGLRenderer: Attempt to load unsupported compressed texture format in .uploadTexture()"):Oe?L&&t.texSubImage2D(i.TEXTURE_2D,W,0,0,pe.width,pe.height,fe,Ee,pe.data):t.texImage2D(i.TEXTURE_2D,W,Ce,pe.width,pe.height,0,fe,Ee,pe.data)}else if(y.isDataArrayTexture)if(Oe){if(it&&t.texStorage3D(i.TEXTURE_2D_ARRAY,ae,Ce,te.width,te.height,te.depth),L)if(y.layerUpdates.size>0){let W=Oh(te.width,te.height,y.format,y.type);for(let J of y.layerUpdates){let ue=te.data.subarray(J*W/te.data.BYTES_PER_ELEMENT,(J+1)*W/te.data.BYTES_PER_ELEMENT);t.texSubImage3D(i.TEXTURE_2D_ARRAY,0,0,0,J,te.width,te.height,1,fe,Ee,ue)}y.clearLayerUpdates()}else t.texSubImage3D(i.TEXTURE_2D_ARRAY,0,0,0,0,te.width,te.height,te.depth,fe,Ee,te.data)}else t.texImage3D(i.TEXTURE_2D_ARRAY,0,Ce,te.width,te.height,te.depth,0,fe,Ee,te.data);else if(y.isData3DTexture)Oe?(it&&t.texStorage3D(i.TEXTURE_3D,ae,Ce,te.width,te.height,te.depth),L&&t.texSubImage3D(i.TEXTURE_3D,0,0,0,0,te.width,te.height,te.depth,fe,Ee,te.data)):t.texImage3D(i.TEXTURE_3D,0,Ce,te.width,te.height,te.depth,0,fe,Ee,te.data);else if(y.isFramebufferTexture){if(it)if(Oe)t.texStorage2D(i.TEXTURE_2D,ae,Ce,te.width,te.height);else{let W=te.width,J=te.height;for(let ue=0;ue<ae;ue++)t.texImage2D(i.TEXTURE_2D,ue,Ce,W,J,0,fe,Ee,null),W>>=1,J>>=1}}else if(Ge.length>0){if(Oe&&it){let W=Se(Ge[0]);t.texStorage2D(i.TEXTURE_2D,ae,Ce,W.width,W.height)}for(let W=0,J=Ge.length;W<J;W++)pe=Ge[W],Oe?L&&t.texSubImage2D(i.TEXTURE_2D,W,0,0,fe,Ee,pe):t.texImage2D(i.TEXTURE_2D,W,Ce,fe,Ee,pe);y.generateMipmaps=!1}else if(Oe){if(it){let W=Se(te);t.texStorage2D(i.TEXTURE_2D,ae,Ce,W.width,W.height)}L&&t.texSubImage2D(i.TEXTURE_2D,0,0,0,fe,Ee,te)}else t.texImage2D(i.TEXTURE_2D,0,Ce,fe,Ee,te);m(y)&&p(K),ye.__version=Z.version,y.onUpdate&&y.onUpdate(y)}E.__version=y.version}function ee(E,y,F){if(y.image.length!==6)return;let K=Re(E,y),$=y.source;t.bindTexture(i.TEXTURE_CUBE_MAP,E.__webglTexture,i.TEXTURE0+F);let Z=n.get($);if($.version!==Z.__version||K===!0){t.activeTexture(i.TEXTURE0+F);let ye=ke.getPrimaries(ke.workingColorSpace),le=y.colorSpace===li?null:ke.getPrimaries(y.colorSpace),de=y.colorSpace===li||ye===le?i.NONE:i.BROWSER_DEFAULT_WEBGL;i.pixelStorei(i.UNPACK_FLIP_Y_WEBGL,y.flipY),i.pixelStorei(i.UNPACK_PREMULTIPLY_ALPHA_WEBGL,y.premultiplyAlpha),i.pixelStorei(i.UNPACK_ALIGNMENT,y.unpackAlignment),i.pixelStorei(i.UNPACK_COLORSPACE_CONVERSION_WEBGL,de);let Xe=y.isCompressedTexture||y.image[0].isCompressedTexture,te=y.image[0]&&y.image[0].isDataTexture,fe=[];for(let J=0;J<6;J++)!Xe&&!te?fe[J]=_(y.image[J],!0,s.maxCubemapSize):fe[J]=te?y.image[J].image:y.image[J],fe[J]=ot(y,fe[J]);let Ee=fe[0],Ce=r.convert(y.format,y.colorSpace),pe=r.convert(y.type),Ge=b(y.internalFormat,Ce,pe,y.colorSpace),Oe=y.isVideoTexture!==!0,it=Z.__version===void 0||K===!0,L=$.dataReady,ae=P(y,Ee);Te(i.TEXTURE_CUBE_MAP,y);let W;if(Xe){Oe&&it&&t.texStorage2D(i.TEXTURE_CUBE_MAP,ae,Ge,Ee.width,Ee.height);for(let J=0;J<6;J++){W=fe[J].mipmaps;for(let ue=0;ue<W.length;ue++){let ce=W[ue];y.format!==on?Ce!==null?Oe?L&&t.compressedTexSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+J,ue,0,0,ce.width,ce.height,Ce,ce.data):t.compressedTexImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+J,ue,Ge,ce.width,ce.height,0,ce.data):console.warn("THREE.WebGLRenderer: Attempt to load unsupported compressed texture format in .setTextureCube()"):Oe?L&&t.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+J,ue,0,0,ce.width,ce.height,Ce,pe,ce.data):t.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+J,ue,Ge,ce.width,ce.height,0,Ce,pe,ce.data)}}}else{if(W=y.mipmaps,Oe&&it){W.length>0&&ae++;let J=Se(fe[0]);t.texStorage2D(i.TEXTURE_CUBE_MAP,ae,Ge,J.width,J.height)}for(let J=0;J<6;J++)if(te){Oe?L&&t.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+J,0,0,0,fe[J].width,fe[J].height,Ce,pe,fe[J].data):t.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+J,0,Ge,fe[J].width,fe[J].height,0,Ce,pe,fe[J].data);for(let ue=0;ue<W.length;ue++){let De=W[ue].image[J].image;Oe?L&&t.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+J,ue+1,0,0,De.width,De.height,Ce,pe,De.data):t.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+J,ue+1,Ge,De.width,De.height,0,Ce,pe,De.data)}}else{Oe?L&&t.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+J,0,0,0,Ce,pe,fe[J]):t.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+J,0,Ge,Ce,pe,fe[J]);for(let ue=0;ue<W.length;ue++){let ce=W[ue];Oe?L&&t.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+J,ue+1,0,0,Ce,pe,ce.image[J]):t.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+J,ue+1,Ge,Ce,pe,ce.image[J])}}}m(y)&&p(i.TEXTURE_CUBE_MAP),Z.__version=$.version,y.onUpdate&&y.onUpdate(y)}E.__version=y.version}function me(E,y,F,K,$,Z){let ye=r.convert(F.format,F.colorSpace),le=r.convert(F.type),de=b(F.internalFormat,ye,le,F.colorSpace),Xe=n.get(y),te=n.get(F);if(te.__renderTarget=y,!Xe.__hasExternalTextures){let fe=Math.max(1,y.width>>Z),Ee=Math.max(1,y.height>>Z);$===i.TEXTURE_3D||$===i.TEXTURE_2D_ARRAY?t.texImage3D($,Z,de,fe,Ee,y.depth,0,ye,le,null):t.texImage2D($,Z,de,fe,Ee,0,ye,le,null)}t.bindFramebuffer(i.FRAMEBUFFER,E),Ve(y)?a.framebufferTexture2DMultisampleEXT(i.FRAMEBUFFER,K,$,te.__webglTexture,0,He(y)):($===i.TEXTURE_2D||$>=i.TEXTURE_CUBE_MAP_POSITIVE_X&&$<=i.TEXTURE_CUBE_MAP_NEGATIVE_Z)&&i.framebufferTexture2D(i.FRAMEBUFFER,K,$,te.__webglTexture,Z),t.bindFramebuffer(i.FRAMEBUFFER,null)}function se(E,y,F){if(i.bindRenderbuffer(i.RENDERBUFFER,E),y.depthBuffer){let K=y.depthTexture,$=K&&K.isDepthTexture?K.type:null,Z=x(y.stencilBuffer,$),ye=y.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT,le=He(y);Ve(y)?a.renderbufferStorageMultisampleEXT(i.RENDERBUFFER,le,Z,y.width,y.height):F?i.renderbufferStorageMultisample(i.RENDERBUFFER,le,Z,y.width,y.height):i.renderbufferStorage(i.RENDERBUFFER,Z,y.width,y.height),i.framebufferRenderbuffer(i.FRAMEBUFFER,ye,i.RENDERBUFFER,E)}else{let K=y.textures;for(let $=0;$<K.length;$++){let Z=K[$],ye=r.convert(Z.format,Z.colorSpace),le=r.convert(Z.type),de=b(Z.internalFormat,ye,le,Z.colorSpace),Xe=He(y);F&&Ve(y)===!1?i.renderbufferStorageMultisample(i.RENDERBUFFER,Xe,de,y.width,y.height):Ve(y)?a.renderbufferStorageMultisampleEXT(i.RENDERBUFFER,Xe,de,y.width,y.height):i.renderbufferStorage(i.RENDERBUFFER,de,y.width,y.height)}}i.bindRenderbuffer(i.RENDERBUFFER,null)}function Me(E,y){if(y&&y.isWebGLCubeRenderTarget)throw new Error("Depth Texture with cube render targets is not supported");if(t.bindFramebuffer(i.FRAMEBUFFER,E),!(y.depthTexture&&y.depthTexture.isDepthTexture))throw new Error("renderTarget.depthTexture must be an instance of THREE.DepthTexture");let K=n.get(y.depthTexture);K.__renderTarget=y,(!K.__webglTexture||y.depthTexture.image.width!==y.width||y.depthTexture.image.height!==y.height)&&(y.depthTexture.image.width=y.width,y.depthTexture.image.height=y.height,y.depthTexture.needsUpdate=!0),Y(y.depthTexture,0);let $=K.__webglTexture,Z=He(y);if(y.depthTexture.format===ss)Ve(y)?a.framebufferTexture2DMultisampleEXT(i.FRAMEBUFFER,i.DEPTH_ATTACHMENT,i.TEXTURE_2D,$,0,Z):i.framebufferTexture2D(i.FRAMEBUFFER,i.DEPTH_ATTACHMENT,i.TEXTURE_2D,$,0);else if(y.depthTexture.format===ds)Ve(y)?a.framebufferTexture2DMultisampleEXT(i.FRAMEBUFFER,i.DEPTH_STENCIL_ATTACHMENT,i.TEXTURE_2D,$,0,Z):i.framebufferTexture2D(i.FRAMEBUFFER,i.DEPTH_STENCIL_ATTACHMENT,i.TEXTURE_2D,$,0);else throw new Error("Unknown depthTexture format")}function Pe(E){let y=n.get(E),F=E.isWebGLCubeRenderTarget===!0;if(y.__boundDepthTexture!==E.depthTexture){let K=E.depthTexture;if(y.__depthDisposeCallback&&y.__depthDisposeCallback(),K){let $=()=>{delete y.__boundDepthTexture,delete y.__depthDisposeCallback,K.removeEventListener("dispose",$)};K.addEventListener("dispose",$),y.__depthDisposeCallback=$}y.__boundDepthTexture=K}if(E.depthTexture&&!y.__autoAllocateDepthBuffer){if(F)throw new Error("target.depthTexture not supported in Cube render targets");Me(y.__webglFramebuffer,E)}else if(F){y.__webglDepthbuffer=[];for(let K=0;K<6;K++)if(t.bindFramebuffer(i.FRAMEBUFFER,y.__webglFramebuffer[K]),y.__webglDepthbuffer[K]===void 0)y.__webglDepthbuffer[K]=i.createRenderbuffer(),se(y.__webglDepthbuffer[K],E,!1);else{let $=E.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT,Z=y.__webglDepthbuffer[K];i.bindRenderbuffer(i.RENDERBUFFER,Z),i.framebufferRenderbuffer(i.FRAMEBUFFER,$,i.RENDERBUFFER,Z)}}else if(t.bindFramebuffer(i.FRAMEBUFFER,y.__webglFramebuffer),y.__webglDepthbuffer===void 0)y.__webglDepthbuffer=i.createRenderbuffer(),se(y.__webglDepthbuffer,E,!1);else{let K=E.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT,$=y.__webglDepthbuffer;i.bindRenderbuffer(i.RENDERBUFFER,$),i.framebufferRenderbuffer(i.FRAMEBUFFER,K,i.RENDERBUFFER,$)}t.bindFramebuffer(i.FRAMEBUFFER,null)}function Be(E,y,F){let K=n.get(E);y!==void 0&&me(K.__webglFramebuffer,E,E.texture,i.COLOR_ATTACHMENT0,i.TEXTURE_2D,0),F!==void 0&&Pe(E)}function ct(E){let y=E.texture,F=n.get(E),K=n.get(y);E.addEventListener("dispose",A);let $=E.textures,Z=E.isWebGLCubeRenderTarget===!0,ye=$.length>1;if(ye||(K.__webglTexture===void 0&&(K.__webglTexture=i.createTexture()),K.__version=y.version,o.memory.textures++),Z){F.__webglFramebuffer=[];for(let le=0;le<6;le++)if(y.mipmaps&&y.mipmaps.length>0){F.__webglFramebuffer[le]=[];for(let de=0;de<y.mipmaps.length;de++)F.__webglFramebuffer[le][de]=i.createFramebuffer()}else F.__webglFramebuffer[le]=i.createFramebuffer()}else{if(y.mipmaps&&y.mipmaps.length>0){F.__webglFramebuffer=[];for(let le=0;le<y.mipmaps.length;le++)F.__webglFramebuffer[le]=i.createFramebuffer()}else F.__webglFramebuffer=i.createFramebuffer();if(ye)for(let le=0,de=$.length;le<de;le++){let Xe=n.get($[le]);Xe.__webglTexture===void 0&&(Xe.__webglTexture=i.createTexture(),o.memory.textures++)}if(E.samples>0&&Ve(E)===!1){F.__webglMultisampledFramebuffer=i.createFramebuffer(),F.__webglColorRenderbuffer=[],t.bindFramebuffer(i.FRAMEBUFFER,F.__webglMultisampledFramebuffer);for(let le=0;le<$.length;le++){let de=$[le];F.__webglColorRenderbuffer[le]=i.createRenderbuffer(),i.bindRenderbuffer(i.RENDERBUFFER,F.__webglColorRenderbuffer[le]);let Xe=r.convert(de.format,de.colorSpace),te=r.convert(de.type),fe=b(de.internalFormat,Xe,te,de.colorSpace,E.isXRRenderTarget===!0),Ee=He(E);i.renderbufferStorageMultisample(i.RENDERBUFFER,Ee,fe,E.width,E.height),i.framebufferRenderbuffer(i.FRAMEBUFFER,i.COLOR_ATTACHMENT0+le,i.RENDERBUFFER,F.__webglColorRenderbuffer[le])}i.bindRenderbuffer(i.RENDERBUFFER,null),E.depthBuffer&&(F.__webglDepthRenderbuffer=i.createRenderbuffer(),se(F.__webglDepthRenderbuffer,E,!0)),t.bindFramebuffer(i.FRAMEBUFFER,null)}}if(Z){t.bindTexture(i.TEXTURE_CUBE_MAP,K.__webglTexture),Te(i.TEXTURE_CUBE_MAP,y);for(let le=0;le<6;le++)if(y.mipmaps&&y.mipmaps.length>0)for(let de=0;de<y.mipmaps.length;de++)me(F.__webglFramebuffer[le][de],E,y,i.COLOR_ATTACHMENT0,i.TEXTURE_CUBE_MAP_POSITIVE_X+le,de);else me(F.__webglFramebuffer[le],E,y,i.COLOR_ATTACHMENT0,i.TEXTURE_CUBE_MAP_POSITIVE_X+le,0);m(y)&&p(i.TEXTURE_CUBE_MAP),t.unbindTexture()}else if(ye){for(let le=0,de=$.length;le<de;le++){let Xe=$[le],te=n.get(Xe);t.bindTexture(i.TEXTURE_2D,te.__webglTexture),Te(i.TEXTURE_2D,Xe),me(F.__webglFramebuffer,E,Xe,i.COLOR_ATTACHMENT0+le,i.TEXTURE_2D,0),m(Xe)&&p(i.TEXTURE_2D)}t.unbindTexture()}else{let le=i.TEXTURE_2D;if((E.isWebGL3DRenderTarget||E.isWebGLArrayRenderTarget)&&(le=E.isWebGL3DRenderTarget?i.TEXTURE_3D:i.TEXTURE_2D_ARRAY),t.bindTexture(le,K.__webglTexture),Te(le,y),y.mipmaps&&y.mipmaps.length>0)for(let de=0;de<y.mipmaps.length;de++)me(F.__webglFramebuffer[de],E,y,i.COLOR_ATTACHMENT0,le,de);else me(F.__webglFramebuffer,E,y,i.COLOR_ATTACHMENT0,le,0);m(y)&&p(le),t.unbindTexture()}E.depthBuffer&&Pe(E)}function We(E){let y=E.textures;for(let F=0,K=y.length;F<K;F++){let $=y[F];if(m($)){let Z=w(E),ye=n.get($).__webglTexture;t.bindTexture(Z,ye),p(Z),t.unbindTexture()}}}let ft=[],N=[];function nn(E){if(E.samples>0){if(Ve(E)===!1){let y=E.textures,F=E.width,K=E.height,$=i.COLOR_BUFFER_BIT,Z=E.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT,ye=n.get(E),le=y.length>1;if(le)for(let de=0;de<y.length;de++)t.bindFramebuffer(i.FRAMEBUFFER,ye.__webglMultisampledFramebuffer),i.framebufferRenderbuffer(i.FRAMEBUFFER,i.COLOR_ATTACHMENT0+de,i.RENDERBUFFER,null),t.bindFramebuffer(i.FRAMEBUFFER,ye.__webglFramebuffer),i.framebufferTexture2D(i.DRAW_FRAMEBUFFER,i.COLOR_ATTACHMENT0+de,i.TEXTURE_2D,null,0);t.bindFramebuffer(i.READ_FRAMEBUFFER,ye.__webglMultisampledFramebuffer),t.bindFramebuffer(i.DRAW_FRAMEBUFFER,ye.__webglFramebuffer);for(let de=0;de<y.length;de++){if(E.resolveDepthBuffer&&(E.depthBuffer&&($|=i.DEPTH_BUFFER_BIT),E.stencilBuffer&&E.resolveStencilBuffer&&($|=i.STENCIL_BUFFER_BIT)),le){i.framebufferRenderbuffer(i.READ_FRAMEBUFFER,i.COLOR_ATTACHMENT0,i.RENDERBUFFER,ye.__webglColorRenderbuffer[de]);let Xe=n.get(y[de]).__webglTexture;i.framebufferTexture2D(i.DRAW_FRAMEBUFFER,i.COLOR_ATTACHMENT0,i.TEXTURE_2D,Xe,0)}i.blitFramebuffer(0,0,F,K,0,0,F,K,$,i.NEAREST),l===!0&&(ft.length=0,N.length=0,ft.push(i.COLOR_ATTACHMENT0+de),E.depthBuffer&&E.resolveDepthBuffer===!1&&(ft.push(Z),N.push(Z),i.invalidateFramebuffer(i.DRAW_FRAMEBUFFER,N)),i.invalidateFramebuffer(i.READ_FRAMEBUFFER,ft))}if(t.bindFramebuffer(i.READ_FRAMEBUFFER,null),t.bindFramebuffer(i.DRAW_FRAMEBUFFER,null),le)for(let de=0;de<y.length;de++){t.bindFramebuffer(i.FRAMEBUFFER,ye.__webglMultisampledFramebuffer),i.framebufferRenderbuffer(i.FRAMEBUFFER,i.COLOR_ATTACHMENT0+de,i.RENDERBUFFER,ye.__webglColorRenderbuffer[de]);let Xe=n.get(y[de]).__webglTexture;t.bindFramebuffer(i.FRAMEBUFFER,ye.__webglFramebuffer),i.framebufferTexture2D(i.DRAW_FRAMEBUFFER,i.COLOR_ATTACHMENT0+de,i.TEXTURE_2D,Xe,0)}t.bindFramebuffer(i.DRAW_FRAMEBUFFER,ye.__webglMultisampledFramebuffer)}else if(E.depthBuffer&&E.resolveDepthBuffer===!1&&l){let y=E.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT;i.invalidateFramebuffer(i.DRAW_FRAMEBUFFER,[y])}}}function He(E){return Math.min(s.maxSamples,E.samples)}function Ve(E){let y=n.get(E);return E.samples>0&&e.has("WEBGL_multisampled_render_to_texture")===!0&&y.__useRenderToTexture!==!1}function be(E){let y=o.render.frame;h.get(E)!==y&&(h.set(E,y),E.update())}function ot(E,y){let F=E.colorSpace,K=E.format,$=E.type;return E.isCompressedTexture===!0||E.isVideoTexture===!0||F!==Ft&&F!==li&&(ke.getTransfer(F)===Qe?(K!==on||$!==Vn)&&console.warn("THREE.WebGLTextures: sRGB encoded textures have to use RGBAFormat and UnsignedByteType."):console.error("THREE.WebGLTextures: Unsupported texture color space:",F)),y}function Se(E){return typeof HTMLImageElement<"u"&&E instanceof HTMLImageElement?(c.width=E.naturalWidth||E.width,c.height=E.naturalHeight||E.height):typeof VideoFrame<"u"&&E instanceof VideoFrame?(c.width=E.displayWidth,c.height=E.displayHeight):(c.width=E.width,c.height=E.height),c}this.allocateTextureUnit=O,this.resetTextureUnits=G,this.setTexture2D=Y,this.setTexture2DArray=V,this.setTexture3D=Q,this.setTextureCube=B,this.rebindTextures=Be,this.setupRenderTarget=ct,this.updateRenderTargetMipmap=We,this.updateMultisampleRenderTarget=nn,this.setupDepthRenderbuffer=Pe,this.setupFrameBufferTexture=me,this.useMultisampledRTT=Ve}function Vg(i,e){function t(n,s=li){let r,o=ke.getTransfer(s);if(n===Vn)return i.UNSIGNED_BYTE;if(n===Il)return i.UNSIGNED_SHORT_4_4_4_4;if(n===Pl)return i.UNSIGNED_SHORT_5_5_5_1;if(n===lu)return i.UNSIGNED_INT_5_9_9_9_REV;if(n===ou)return i.BYTE;if(n===au)return i.SHORT;if(n===Gs)return i.UNSIGNED_SHORT;if(n===Cl)return i.INT;if(n===Pi)return i.UNSIGNED_INT;if(n===xn)return i.FLOAT;if(n===tr)return i.HALF_FLOAT;if(n===cu)return i.ALPHA;if(n===hu)return i.RGB;if(n===on)return i.RGBA;if(n===uu)return i.LUMINANCE;if(n===du)return i.LUMINANCE_ALPHA;if(n===ss)return i.DEPTH_COMPONENT;if(n===ds)return i.DEPTH_STENCIL;if(n===Ll)return i.RED;if(n===Dl)return i.RED_INTEGER;if(n===fu)return i.RG;if(n===Ul)return i.RG_INTEGER;if(n===Nl)return i.RGBA_INTEGER;if(n===Hr||n===Vr||n===Gr||n===Wr)if(o===Qe)if(r=e.get("WEBGL_compressed_texture_s3tc_srgb"),r!==null){if(n===Hr)return r.COMPRESSED_SRGB_S3TC_DXT1_EXT;if(n===Vr)return r.COMPRESSED_SRGB_ALPHA_S3TC_DXT1_EXT;if(n===Gr)return r.COMPRESSED_SRGB_ALPHA_S3TC_DXT3_EXT;if(n===Wr)return r.COMPRESSED_SRGB_ALPHA_S3TC_DXT5_EXT}else return null;else if(r=e.get("WEBGL_compressed_texture_s3tc"),r!==null){if(n===Hr)return r.COMPRESSED_RGB_S3TC_DXT1_EXT;if(n===Vr)return r.COMPRESSED_RGBA_S3TC_DXT1_EXT;if(n===Gr)return r.COMPRESSED_RGBA_S3TC_DXT3_EXT;if(n===Wr)return r.COMPRESSED_RGBA_S3TC_DXT5_EXT}else return null;if(n===ba||n===wa||n===Ea||n===Aa)if(r=e.get("WEBGL_compressed_texture_pvrtc"),r!==null){if(n===ba)return r.COMPRESSED_RGB_PVRTC_4BPPV1_IMG;if(n===wa)return r.COMPRESSED_RGB_PVRTC_2BPPV1_IMG;if(n===Ea)return r.COMPRESSED_RGBA_PVRTC_4BPPV1_IMG;if(n===Aa)return r.COMPRESSED_RGBA_PVRTC_2BPPV1_IMG}else return null;if(n===Ta||n===Ra||n===Ca)if(r=e.get("WEBGL_compressed_texture_etc"),r!==null){if(n===Ta||n===Ra)return o===Qe?r.COMPRESSED_SRGB8_ETC2:r.COMPRESSED_RGB8_ETC2;if(n===Ca)return o===Qe?r.COMPRESSED_SRGB8_ALPHA8_ETC2_EAC:r.COMPRESSED_RGBA8_ETC2_EAC}else return null;if(n===Ia||n===Pa||n===La||n===Da||n===Ua||n===Na||n===Oa||n===Fa||n===Ba||n===za||n===ka||n===Ha||n===Va||n===Ga)if(r=e.get("WEBGL_compressed_texture_astc"),r!==null){if(n===Ia)return o===Qe?r.COMPRESSED_SRGB8_ALPHA8_ASTC_4x4_KHR:r.COMPRESSED_RGBA_ASTC_4x4_KHR;if(n===Pa)return o===Qe?r.COMPRESSED_SRGB8_ALPHA8_ASTC_5x4_KHR:r.COMPRESSED_RGBA_ASTC_5x4_KHR;if(n===La)return o===Qe?r.COMPRESSED_SRGB8_ALPHA8_ASTC_5x5_KHR:r.COMPRESSED_RGBA_ASTC_5x5_KHR;if(n===Da)return o===Qe?r.COMPRESSED_SRGB8_ALPHA8_ASTC_6x5_KHR:r.COMPRESSED_RGBA_ASTC_6x5_KHR;if(n===Ua)return o===Qe?r.COMPRESSED_SRGB8_ALPHA8_ASTC_6x6_KHR:r.COMPRESSED_RGBA_ASTC_6x6_KHR;if(n===Na)return o===Qe?r.COMPRESSED_SRGB8_ALPHA8_ASTC_8x5_KHR:r.COMPRESSED_RGBA_ASTC_8x5_KHR;if(n===Oa)return o===Qe?r.COMPRESSED_SRGB8_ALPHA8_ASTC_8x6_KHR:r.COMPRESSED_RGBA_ASTC_8x6_KHR;if(n===Fa)return o===Qe?r.COMPRESSED_SRGB8_ALPHA8_ASTC_8x8_KHR:r.COMPRESSED_RGBA_ASTC_8x8_KHR;if(n===Ba)return o===Qe?r.COMPRESSED_SRGB8_ALPHA8_ASTC_10x5_KHR:r.COMPRESSED_RGBA_ASTC_10x5_KHR;if(n===za)return o===Qe?r.COMPRESSED_SRGB8_ALPHA8_ASTC_10x6_KHR:r.COMPRESSED_RGBA_ASTC_10x6_KHR;if(n===ka)return o===Qe?r.COMPRESSED_SRGB8_ALPHA8_ASTC_10x8_KHR:r.COMPRESSED_RGBA_ASTC_10x8_KHR;if(n===Ha)return o===Qe?r.COMPRESSED_SRGB8_ALPHA8_ASTC_10x10_KHR:r.COMPRESSED_RGBA_ASTC_10x10_KHR;if(n===Va)return o===Qe?r.COMPRESSED_SRGB8_ALPHA8_ASTC_12x10_KHR:r.COMPRESSED_RGBA_ASTC_12x10_KHR;if(n===Ga)return o===Qe?r.COMPRESSED_SRGB8_ALPHA8_ASTC_12x12_KHR:r.COMPRESSED_RGBA_ASTC_12x12_KHR}else return null;if(n===Xr||n===Wa||n===Xa)if(r=e.get("EXT_texture_compression_bptc"),r!==null){if(n===Xr)return o===Qe?r.COMPRESSED_SRGB_ALPHA_BPTC_UNORM_EXT:r.COMPRESSED_RGBA_BPTC_UNORM_EXT;if(n===Wa)return r.COMPRESSED_RGB_BPTC_SIGNED_FLOAT_EXT;if(n===Xa)return r.COMPRESSED_RGB_BPTC_UNSIGNED_FLOAT_EXT}else return null;if(n===pu||n===qa||n===Ya||n===Za)if(r=e.get("EXT_texture_compression_rgtc"),r!==null){if(n===Xr)return r.COMPRESSED_RED_RGTC1_EXT;if(n===qa)return r.COMPRESSED_SIGNED_RED_RGTC1_EXT;if(n===Ya)return r.COMPRESSED_RED_GREEN_RGTC2_EXT;if(n===Za)return r.COMPRESSED_SIGNED_RED_GREEN_RGTC2_EXT}else return null;return n===us?i.UNSIGNED_INT_24_8:i[n]!==void 0?i[n]:null}return{convert:t}}var cl=class extends xt{constructor(e=[]){super(),this.isArrayCamera=!0,this.cameras=e}},Dt=class extends ht{constructor(){super(),this.isGroup=!0,this.type="Group"}},Gg={type:"move"},Hs=class{constructor(){this._targetRay=null,this._grip=null,this._hand=null}getHandSpace(){return this._hand===null&&(this._hand=new Dt,this._hand.matrixAutoUpdate=!1,this._hand.visible=!1,this._hand.joints={},this._hand.inputState={pinching:!1}),this._hand}getTargetRaySpace(){return this._targetRay===null&&(this._targetRay=new Dt,this._targetRay.matrixAutoUpdate=!1,this._targetRay.visible=!1,this._targetRay.hasLinearVelocity=!1,this._targetRay.linearVelocity=new C,this._targetRay.hasAngularVelocity=!1,this._targetRay.angularVelocity=new C),this._targetRay}getGripSpace(){return this._grip===null&&(this._grip=new Dt,this._grip.matrixAutoUpdate=!1,this._grip.visible=!1,this._grip.hasLinearVelocity=!1,this._grip.linearVelocity=new C,this._grip.hasAngularVelocity=!1,this._grip.angularVelocity=new C),this._grip}dispatchEvent(e){return this._targetRay!==null&&this._targetRay.dispatchEvent(e),this._grip!==null&&this._grip.dispatchEvent(e),this._hand!==null&&this._hand.dispatchEvent(e),this}connect(e){if(e&&e.hand){let t=this._hand;if(t)for(let n of e.hand.values())this._getHandJoint(t,n)}return this.dispatchEvent({type:"connected",data:e}),this}disconnect(e){return this.dispatchEvent({type:"disconnected",data:e}),this._targetRay!==null&&(this._targetRay.visible=!1),this._grip!==null&&(this._grip.visible=!1),this._hand!==null&&(this._hand.visible=!1),this}update(e,t,n){let s=null,r=null,o=null,a=this._targetRay,l=this._grip,c=this._hand;if(e&&t.session.visibilityState!=="visible-blurred"){if(c&&e.hand){o=!0;for(let _ of e.hand.values()){let m=t.getJointPose(_,n),p=this._getHandJoint(c,_);m!==null&&(p.matrix.fromArray(m.transform.matrix),p.matrix.decompose(p.position,p.rotation,p.scale),p.matrixWorldNeedsUpdate=!0,p.jointRadius=m.radius),p.visible=m!==null}let h=c.joints["index-finger-tip"],u=c.joints["thumb-tip"],d=h.position.distanceTo(u.position),f=.02,g=.005;c.inputState.pinching&&d>f+g?(c.inputState.pinching=!1,this.dispatchEvent({type:"pinchend",handedness:e.handedness,target:this})):!c.inputState.pinching&&d<=f-g&&(c.inputState.pinching=!0,this.dispatchEvent({type:"pinchstart",handedness:e.handedness,target:this}))}else l!==null&&e.gripSpace&&(r=t.getPose(e.gripSpace,n),r!==null&&(l.matrix.fromArray(r.transform.matrix),l.matrix.decompose(l.position,l.rotation,l.scale),l.matrixWorldNeedsUpdate=!0,r.linearVelocity?(l.hasLinearVelocity=!0,l.linearVelocity.copy(r.linearVelocity)):l.hasLinearVelocity=!1,r.angularVelocity?(l.hasAngularVelocity=!0,l.angularVelocity.copy(r.angularVelocity)):l.hasAngularVelocity=!1));a!==null&&(s=t.getPose(e.targetRaySpace,n),s===null&&r!==null&&(s=r),s!==null&&(a.matrix.fromArray(s.transform.matrix),a.matrix.decompose(a.position,a.rotation,a.scale),a.matrixWorldNeedsUpdate=!0,s.linearVelocity?(a.hasLinearVelocity=!0,a.linearVelocity.copy(s.linearVelocity)):a.hasLinearVelocity=!1,s.angularVelocity?(a.hasAngularVelocity=!0,a.angularVelocity.copy(s.angularVelocity)):a.hasAngularVelocity=!1,this.dispatchEvent(Gg)))}return a!==null&&(a.visible=s!==null),l!==null&&(l.visible=r!==null),c!==null&&(c.visible=o!==null),this}_getHandJoint(e,t){if(e.joints[t.jointName]===void 0){let n=new Dt;n.matrixAutoUpdate=!1,n.visible=!1,e.joints[t.jointName]=n,e.add(n)}return e.joints[t.jointName]}},Wg=`
void main() {

	gl_Position = vec4( position, 1.0 );

}`,Xg=`
uniform sampler2DArray depthColor;
uniform float depthWidth;
uniform float depthHeight;

void main() {

	vec2 coord = vec2( gl_FragCoord.x / depthWidth, gl_FragCoord.y / depthHeight );

	if ( coord.x >= 1.0 ) {

		gl_FragDepth = texture( depthColor, vec3( coord.x - 1.0, coord.y, 1 ) ).r;

	} else {

		gl_FragDepth = texture( depthColor, vec3( coord.x, coord.y, 0 ) ).r;

	}

}`,hl=class{constructor(){this.texture=null,this.mesh=null,this.depthNear=0,this.depthFar=0}init(e,t,n){if(this.texture===null){let s=new Et,r=e.properties.get(s);r.__webglTexture=t.texture,(t.depthNear!=n.depthNear||t.depthFar!=n.depthFar)&&(this.depthNear=t.depthNear,this.depthFar=t.depthFar),this.texture=s}}getMesh(e){if(this.texture!==null&&this.mesh===null){let t=e.cameras[0].viewport,n=new ln({vertexShader:Wg,fragmentShader:Xg,uniforms:{depthColor:{value:this.texture},depthWidth:{value:t.z},depthHeight:{value:t.w}}});this.mesh=new tt(new Yn(20,20),n)}return this.mesh}reset(){this.texture=null,this.mesh=null}getDepthTexture(){return this.texture}},ul=class extends Gn{constructor(e,t){super();let n=this,s=null,r=1,o=null,a="local-floor",l=1,c=null,h=null,u=null,d=null,f=null,g=null,_=new hl,m=t.getContextAttributes(),p=null,w=null,b=[],x=[],P=new we,T=null,A=new xt;A.viewport=new Ye;let R=new xt;R.viewport=new Ye;let M=[A,R],v=new cl,I=null,G=null;this.cameraAutoUpdate=!0,this.enabled=!1,this.isPresenting=!1,this.getController=function(q){let ee=b[q];return ee===void 0&&(ee=new Hs,b[q]=ee),ee.getTargetRaySpace()},this.getControllerGrip=function(q){let ee=b[q];return ee===void 0&&(ee=new Hs,b[q]=ee),ee.getGripSpace()},this.getHand=function(q){let ee=b[q];return ee===void 0&&(ee=new Hs,b[q]=ee),ee.getHandSpace()};function O(q){let ee=x.indexOf(q.inputSource);if(ee===-1)return;let me=b[ee];me!==void 0&&(me.update(q.inputSource,q.frame,c||o),me.dispatchEvent({type:q.type,data:q.inputSource}))}function X(){s.removeEventListener("select",O),s.removeEventListener("selectstart",O),s.removeEventListener("selectend",O),s.removeEventListener("squeeze",O),s.removeEventListener("squeezestart",O),s.removeEventListener("squeezeend",O),s.removeEventListener("end",X),s.removeEventListener("inputsourceschange",Y);for(let q=0;q<b.length;q++){let ee=x[q];ee!==null&&(x[q]=null,b[q].disconnect(ee))}I=null,G=null,_.reset(),e.setRenderTarget(p),f=null,d=null,u=null,s=null,w=null,Re.stop(),n.isPresenting=!1,e.setPixelRatio(T),e.setSize(P.width,P.height,!1),n.dispatchEvent({type:"sessionend"})}this.setFramebufferScaleFactor=function(q){r=q,n.isPresenting===!0&&console.warn("THREE.WebXRManager: Cannot change framebuffer scale while presenting.")},this.setReferenceSpaceType=function(q){a=q,n.isPresenting===!0&&console.warn("THREE.WebXRManager: Cannot change reference space type while presenting.")},this.getReferenceSpace=function(){return c||o},this.setReferenceSpace=function(q){c=q},this.getBaseLayer=function(){return d!==null?d:f},this.getBinding=function(){return u},this.getFrame=function(){return g},this.getSession=function(){return s},this.setSession=async function(q){if(s=q,s!==null){if(p=e.getRenderTarget(),s.addEventListener("select",O),s.addEventListener("selectstart",O),s.addEventListener("selectend",O),s.addEventListener("squeeze",O),s.addEventListener("squeezestart",O),s.addEventListener("squeezeend",O),s.addEventListener("end",X),s.addEventListener("inputsourceschange",Y),m.xrCompatible!==!0&&await t.makeXRCompatible(),T=e.getPixelRatio(),e.getSize(P),s.renderState.layers===void 0){let ee={antialias:m.antialias,alpha:!0,depth:m.depth,stencil:m.stencil,framebufferScaleFactor:r};f=new XRWebGLLayer(s,t,ee),s.updateRenderState({baseLayer:f}),e.setPixelRatio(1),e.setSize(f.framebufferWidth,f.framebufferHeight,!1),w=new Wn(f.framebufferWidth,f.framebufferHeight,{format:on,type:Vn,colorSpace:e.outputColorSpace,stencilBuffer:m.stencil})}else{let ee=null,me=null,se=null;m.depth&&(se=m.stencil?t.DEPTH24_STENCIL8:t.DEPTH_COMPONENT24,ee=m.stencil?ds:ss,me=m.stencil?us:Pi);let Me={colorFormat:t.RGBA8,depthFormat:se,scaleFactor:r};u=new XRWebGLBinding(s,t),d=u.createProjectionLayer(Me),s.updateRenderState({layers:[d]}),e.setPixelRatio(1),e.setSize(d.textureWidth,d.textureHeight,!1),w=new Wn(d.textureWidth,d.textureHeight,{format:on,type:Vn,depthTexture:new Qr(d.textureWidth,d.textureHeight,me,void 0,void 0,void 0,void 0,void 0,void 0,ee),stencilBuffer:m.stencil,colorSpace:e.outputColorSpace,samples:m.antialias?4:0,resolveDepthBuffer:d.ignoreDepthValues===!1})}w.isXRRenderTarget=!0,this.setFoveation(l),c=null,o=await s.requestReferenceSpace(a),Re.setContext(s),Re.start(),n.isPresenting=!0,n.dispatchEvent({type:"sessionstart"})}},this.getEnvironmentBlendMode=function(){if(s!==null)return s.environmentBlendMode},this.getDepthTexture=function(){return _.getDepthTexture()};function Y(q){for(let ee=0;ee<q.removed.length;ee++){let me=q.removed[ee],se=x.indexOf(me);se>=0&&(x[se]=null,b[se].disconnect(me))}for(let ee=0;ee<q.added.length;ee++){let me=q.added[ee],se=x.indexOf(me);if(se===-1){for(let Pe=0;Pe<b.length;Pe++)if(Pe>=x.length){x.push(me),se=Pe;break}else if(x[Pe]===null){x[Pe]=me,se=Pe;break}if(se===-1)break}let Me=b[se];Me&&Me.connect(me)}}let V=new C,Q=new C;function B(q,ee,me){V.setFromMatrixPosition(ee.matrixWorld),Q.setFromMatrixPosition(me.matrixWorld);let se=V.distanceTo(Q),Me=ee.projectionMatrix.elements,Pe=me.projectionMatrix.elements,Be=Me[14]/(Me[10]-1),ct=Me[14]/(Me[10]+1),We=(Me[9]+1)/Me[5],ft=(Me[9]-1)/Me[5],N=(Me[8]-1)/Me[0],nn=(Pe[8]+1)/Pe[0],He=Be*N,Ve=Be*nn,be=se/(-N+nn),ot=be*-N;if(ee.matrixWorld.decompose(q.position,q.quaternion,q.scale),q.translateX(ot),q.translateZ(be),q.matrixWorld.compose(q.position,q.quaternion,q.scale),q.matrixWorldInverse.copy(q.matrixWorld).invert(),Me[10]===-1)q.projectionMatrix.copy(ee.projectionMatrix),q.projectionMatrixInverse.copy(ee.projectionMatrixInverse);else{let Se=Be+be,E=ct+be,y=He-ot,F=Ve+(se-ot),K=We*ct/E*Se,$=ft*ct/E*Se;q.projectionMatrix.makePerspective(y,F,K,$,Se,E),q.projectionMatrixInverse.copy(q.projectionMatrix).invert()}}function H(q,ee){ee===null?q.matrixWorld.copy(q.matrix):q.matrixWorld.multiplyMatrices(ee.matrixWorld,q.matrix),q.matrixWorldInverse.copy(q.matrixWorld).invert()}this.updateCamera=function(q){if(s===null)return;let ee=q.near,me=q.far;_.texture!==null&&(_.depthNear>0&&(ee=_.depthNear),_.depthFar>0&&(me=_.depthFar)),v.near=R.near=A.near=ee,v.far=R.far=A.far=me,(I!==v.near||G!==v.far)&&(s.updateRenderState({depthNear:v.near,depthFar:v.far}),I=v.near,G=v.far),A.layers.mask=q.layers.mask|2,R.layers.mask=q.layers.mask|4,v.layers.mask=A.layers.mask|R.layers.mask;let se=q.parent,Me=v.cameras;H(v,se);for(let Pe=0;Pe<Me.length;Pe++)H(Me[Pe],se);Me.length===2?B(v,A,R):v.projectionMatrix.copy(A.projectionMatrix),j(q,v,se)};function j(q,ee,me){me===null?q.matrix.copy(ee.matrixWorld):(q.matrix.copy(me.matrixWorld),q.matrix.invert(),q.matrix.multiply(ee.matrixWorld)),q.matrix.decompose(q.position,q.quaternion,q.scale),q.updateMatrixWorld(!0),q.projectionMatrix.copy(ee.projectionMatrix),q.projectionMatrixInverse.copy(ee.projectionMatrixInverse),q.isPerspectiveCamera&&(q.fov=ms*2*Math.atan(1/q.projectionMatrix.elements[5]),q.zoom=1)}this.getCamera=function(){return v},this.getFoveation=function(){if(!(d===null&&f===null))return l},this.setFoveation=function(q){l=q,d!==null&&(d.fixedFoveation=q),f!==null&&f.fixedFoveation!==void 0&&(f.fixedFoveation=q)},this.hasDepthSensing=function(){return _.texture!==null},this.getDepthSensingMesh=function(){return _.getMesh(v)};let ie=null;function Te(q,ee){if(h=ee.getViewerPose(c||o),g=ee,h!==null){let me=h.views;f!==null&&(e.setRenderTargetFramebuffer(w,f.framebuffer),e.setRenderTarget(w));let se=!1;me.length!==v.cameras.length&&(v.cameras.length=0,se=!0);for(let Pe=0;Pe<me.length;Pe++){let Be=me[Pe],ct=null;if(f!==null)ct=f.getViewport(Be);else{let ft=u.getViewSubImage(d,Be);ct=ft.viewport,Pe===0&&(e.setRenderTargetTextures(w,ft.colorTexture,d.ignoreDepthValues?void 0:ft.depthStencilTexture),e.setRenderTarget(w))}let We=M[Pe];We===void 0&&(We=new xt,We.layers.enable(Pe),We.viewport=new Ye,M[Pe]=We),We.matrix.fromArray(Be.transform.matrix),We.matrix.decompose(We.position,We.quaternion,We.scale),We.projectionMatrix.fromArray(Be.projectionMatrix),We.projectionMatrixInverse.copy(We.projectionMatrix).invert(),We.viewport.set(ct.x,ct.y,ct.width,ct.height),Pe===0&&(v.matrix.copy(We.matrix),v.matrix.decompose(v.position,v.quaternion,v.scale)),se===!0&&v.cameras.push(We)}let Me=s.enabledFeatures;if(Me&&Me.includes("depth-sensing")){let Pe=u.getDepthInformation(me[0]);Pe&&Pe.isValid&&Pe.texture&&_.init(e,Pe,s.renderState)}}for(let me=0;me<b.length;me++){let se=x[me],Me=b[me];se!==null&&Me!==void 0&&Me.update(se,ee,c||o)}ie&&ie(q,ee),ee.detectedPlanes&&n.dispatchEvent({type:"planesdetected",data:ee}),g=null}let Re=new Mu;Re.setAnimationLoop(Te),this.setAnimationLoop=function(q){ie=q},this.dispose=function(){}}},Ti=new An,qg=new Le;function Yg(i,e){function t(m,p){m.matrixAutoUpdate===!0&&m.updateMatrix(),p.value.copy(m.matrix)}function n(m,p){p.color.getRGB(m.fogColor.value,vu(i)),p.isFog?(m.fogNear.value=p.near,m.fogFar.value=p.far):p.isFogExp2&&(m.fogDensity.value=p.density)}function s(m,p,w,b,x){p.isMeshBasicMaterial||p.isMeshLambertMaterial?r(m,p):p.isMeshToonMaterial?(r(m,p),u(m,p)):p.isMeshPhongMaterial?(r(m,p),h(m,p)):p.isMeshStandardMaterial?(r(m,p),d(m,p),p.isMeshPhysicalMaterial&&f(m,p,x)):p.isMeshMatcapMaterial?(r(m,p),g(m,p)):p.isMeshDepthMaterial?r(m,p):p.isMeshDistanceMaterial?(r(m,p),_(m,p)):p.isMeshNormalMaterial?r(m,p):p.isLineBasicMaterial?(o(m,p),p.isLineDashedMaterial&&a(m,p)):p.isPointsMaterial?l(m,p,w,b):p.isSpriteMaterial?c(m,p):p.isShadowMaterial?(m.color.value.copy(p.color),m.opacity.value=p.opacity):p.isShaderMaterial&&(p.uniformsNeedUpdate=!1)}function r(m,p){m.opacity.value=p.opacity,p.color&&m.diffuse.value.copy(p.color),p.emissive&&m.emissive.value.copy(p.emissive).multiplyScalar(p.emissiveIntensity),p.map&&(m.map.value=p.map,t(p.map,m.mapTransform)),p.alphaMap&&(m.alphaMap.value=p.alphaMap,t(p.alphaMap,m.alphaMapTransform)),p.bumpMap&&(m.bumpMap.value=p.bumpMap,t(p.bumpMap,m.bumpMapTransform),m.bumpScale.value=p.bumpScale,p.side===Ut&&(m.bumpScale.value*=-1)),p.normalMap&&(m.normalMap.value=p.normalMap,t(p.normalMap,m.normalMapTransform),m.normalScale.value.copy(p.normalScale),p.side===Ut&&m.normalScale.value.negate()),p.displacementMap&&(m.displacementMap.value=p.displacementMap,t(p.displacementMap,m.displacementMapTransform),m.displacementScale.value=p.displacementScale,m.displacementBias.value=p.displacementBias),p.emissiveMap&&(m.emissiveMap.value=p.emissiveMap,t(p.emissiveMap,m.emissiveMapTransform)),p.specularMap&&(m.specularMap.value=p.specularMap,t(p.specularMap,m.specularMapTransform)),p.alphaTest>0&&(m.alphaTest.value=p.alphaTest);let w=e.get(p),b=w.envMap,x=w.envMapRotation;b&&(m.envMap.value=b,Ti.copy(x),Ti.x*=-1,Ti.y*=-1,Ti.z*=-1,b.isCubeTexture&&b.isRenderTargetTexture===!1&&(Ti.y*=-1,Ti.z*=-1),m.envMapRotation.value.setFromMatrix4(qg.makeRotationFromEuler(Ti)),m.flipEnvMap.value=b.isCubeTexture&&b.isRenderTargetTexture===!1?-1:1,m.reflectivity.value=p.reflectivity,m.ior.value=p.ior,m.refractionRatio.value=p.refractionRatio),p.lightMap&&(m.lightMap.value=p.lightMap,m.lightMapIntensity.value=p.lightMapIntensity,t(p.lightMap,m.lightMapTransform)),p.aoMap&&(m.aoMap.value=p.aoMap,m.aoMapIntensity.value=p.aoMapIntensity,t(p.aoMap,m.aoMapTransform))}function o(m,p){m.diffuse.value.copy(p.color),m.opacity.value=p.opacity,p.map&&(m.map.value=p.map,t(p.map,m.mapTransform))}function a(m,p){m.dashSize.value=p.dashSize,m.totalSize.value=p.dashSize+p.gapSize,m.scale.value=p.scale}function l(m,p,w,b){m.diffuse.value.copy(p.color),m.opacity.value=p.opacity,m.size.value=p.size*w,m.scale.value=b*.5,p.map&&(m.map.value=p.map,t(p.map,m.uvTransform)),p.alphaMap&&(m.alphaMap.value=p.alphaMap,t(p.alphaMap,m.alphaMapTransform)),p.alphaTest>0&&(m.alphaTest.value=p.alphaTest)}function c(m,p){m.diffuse.value.copy(p.color),m.opacity.value=p.opacity,m.rotation.value=p.rotation,p.map&&(m.map.value=p.map,t(p.map,m.mapTransform)),p.alphaMap&&(m.alphaMap.value=p.alphaMap,t(p.alphaMap,m.alphaMapTransform)),p.alphaTest>0&&(m.alphaTest.value=p.alphaTest)}function h(m,p){m.specular.value.copy(p.specular),m.shininess.value=Math.max(p.shininess,1e-4)}function u(m,p){p.gradientMap&&(m.gradientMap.value=p.gradientMap)}function d(m,p){m.metalness.value=p.metalness,p.metalnessMap&&(m.metalnessMap.value=p.metalnessMap,t(p.metalnessMap,m.metalnessMapTransform)),m.roughness.value=p.roughness,p.roughnessMap&&(m.roughnessMap.value=p.roughnessMap,t(p.roughnessMap,m.roughnessMapTransform)),p.envMap&&(m.envMapIntensity.value=p.envMapIntensity)}function f(m,p,w){m.ior.value=p.ior,p.sheen>0&&(m.sheenColor.value.copy(p.sheenColor).multiplyScalar(p.sheen),m.sheenRoughness.value=p.sheenRoughness,p.sheenColorMap&&(m.sheenColorMap.value=p.sheenColorMap,t(p.sheenColorMap,m.sheenColorMapTransform)),p.sheenRoughnessMap&&(m.sheenRoughnessMap.value=p.sheenRoughnessMap,t(p.sheenRoughnessMap,m.sheenRoughnessMapTransform))),p.clearcoat>0&&(m.clearcoat.value=p.clearcoat,m.clearcoatRoughness.value=p.clearcoatRoughness,p.clearcoatMap&&(m.clearcoatMap.value=p.clearcoatMap,t(p.clearcoatMap,m.clearcoatMapTransform)),p.clearcoatRoughnessMap&&(m.clearcoatRoughnessMap.value=p.clearcoatRoughnessMap,t(p.clearcoatRoughnessMap,m.clearcoatRoughnessMapTransform)),p.clearcoatNormalMap&&(m.clearcoatNormalMap.value=p.clearcoatNormalMap,t(p.clearcoatNormalMap,m.clearcoatNormalMapTransform),m.clearcoatNormalScale.value.copy(p.clearcoatNormalScale),p.side===Ut&&m.clearcoatNormalScale.value.negate())),p.dispersion>0&&(m.dispersion.value=p.dispersion),p.iridescence>0&&(m.iridescence.value=p.iridescence,m.iridescenceIOR.value=p.iridescenceIOR,m.iridescenceThicknessMinimum.value=p.iridescenceThicknessRange[0],m.iridescenceThicknessMaximum.value=p.iridescenceThicknessRange[1],p.iridescenceMap&&(m.iridescenceMap.value=p.iridescenceMap,t(p.iridescenceMap,m.iridescenceMapTransform)),p.iridescenceThicknessMap&&(m.iridescenceThicknessMap.value=p.iridescenceThicknessMap,t(p.iridescenceThicknessMap,m.iridescenceThicknessMapTransform))),p.transmission>0&&(m.transmission.value=p.transmission,m.transmissionSamplerMap.value=w.texture,m.transmissionSamplerSize.value.set(w.width,w.height),p.transmissionMap&&(m.transmissionMap.value=p.transmissionMap,t(p.transmissionMap,m.transmissionMapTransform)),m.thickness.value=p.thickness,p.thicknessMap&&(m.thicknessMap.value=p.thicknessMap,t(p.thicknessMap,m.thicknessMapTransform)),m.attenuationDistance.value=p.attenuationDistance,m.attenuationColor.value.copy(p.attenuationColor)),p.anisotropy>0&&(m.anisotropyVector.value.set(p.anisotropy*Math.cos(p.anisotropyRotation),p.anisotropy*Math.sin(p.anisotropyRotation)),p.anisotropyMap&&(m.anisotropyMap.value=p.anisotropyMap,t(p.anisotropyMap,m.anisotropyMapTransform))),m.specularIntensity.value=p.specularIntensity,m.specularColor.value.copy(p.specularColor),p.specularColorMap&&(m.specularColorMap.value=p.specularColorMap,t(p.specularColorMap,m.specularColorMapTransform)),p.specularIntensityMap&&(m.specularIntensityMap.value=p.specularIntensityMap,t(p.specularIntensityMap,m.specularIntensityMapTransform))}function g(m,p){p.matcap&&(m.matcap.value=p.matcap)}function _(m,p){let w=e.get(p).light;m.referencePosition.value.setFromMatrixPosition(w.matrixWorld),m.nearDistance.value=w.shadow.camera.near,m.farDistance.value=w.shadow.camera.far}return{refreshFogUniforms:n,refreshMaterialUniforms:s}}function Zg(i,e,t,n){let s={},r={},o=[],a=i.getParameter(i.MAX_UNIFORM_BUFFER_BINDINGS);function l(w,b){let x=b.program;n.uniformBlockBinding(w,x)}function c(w,b){let x=s[w.id];x===void 0&&(g(w),x=h(w),s[w.id]=x,w.addEventListener("dispose",m));let P=b.program;n.updateUBOMapping(w,P);let T=e.render.frame;r[w.id]!==T&&(d(w),r[w.id]=T)}function h(w){let b=u();w.__bindingPointIndex=b;let x=i.createBuffer(),P=w.__size,T=w.usage;return i.bindBuffer(i.UNIFORM_BUFFER,x),i.bufferData(i.UNIFORM_BUFFER,P,T),i.bindBuffer(i.UNIFORM_BUFFER,null),i.bindBufferBase(i.UNIFORM_BUFFER,b,x),x}function u(){for(let w=0;w<a;w++)if(o.indexOf(w)===-1)return o.push(w),w;return console.error("THREE.WebGLRenderer: Maximum number of simultaneously usable uniforms groups reached."),0}function d(w){let b=s[w.id],x=w.uniforms,P=w.__cache;i.bindBuffer(i.UNIFORM_BUFFER,b);for(let T=0,A=x.length;T<A;T++){let R=Array.isArray(x[T])?x[T]:[x[T]];for(let M=0,v=R.length;M<v;M++){let I=R[M];if(f(I,T,M,P)===!0){let G=I.__offset,O=Array.isArray(I.value)?I.value:[I.value],X=0;for(let Y=0;Y<O.length;Y++){let V=O[Y],Q=_(V);typeof V=="number"||typeof V=="boolean"?(I.__data[0]=V,i.bufferSubData(i.UNIFORM_BUFFER,G+X,I.__data)):V.isMatrix3?(I.__data[0]=V.elements[0],I.__data[1]=V.elements[1],I.__data[2]=V.elements[2],I.__data[3]=0,I.__data[4]=V.elements[3],I.__data[5]=V.elements[4],I.__data[6]=V.elements[5],I.__data[7]=0,I.__data[8]=V.elements[6],I.__data[9]=V.elements[7],I.__data[10]=V.elements[8],I.__data[11]=0):(V.toArray(I.__data,X),X+=Q.storage/Float32Array.BYTES_PER_ELEMENT)}i.bufferSubData(i.UNIFORM_BUFFER,G,I.__data)}}}i.bindBuffer(i.UNIFORM_BUFFER,null)}function f(w,b,x,P){let T=w.value,A=b+"_"+x;if(P[A]===void 0)return typeof T=="number"||typeof T=="boolean"?P[A]=T:P[A]=T.clone(),!0;{let R=P[A];if(typeof T=="number"||typeof T=="boolean"){if(R!==T)return P[A]=T,!0}else if(R.equals(T)===!1)return R.copy(T),!0}return!1}function g(w){let b=w.uniforms,x=0,P=16;for(let A=0,R=b.length;A<R;A++){let M=Array.isArray(b[A])?b[A]:[b[A]];for(let v=0,I=M.length;v<I;v++){let G=M[v],O=Array.isArray(G.value)?G.value:[G.value];for(let X=0,Y=O.length;X<Y;X++){let V=O[X],Q=_(V),B=x%P,H=B%Q.boundary,j=B+H;x+=H,j!==0&&P-j<Q.storage&&(x+=P-j),G.__data=new Float32Array(Q.storage/Float32Array.BYTES_PER_ELEMENT),G.__offset=x,x+=Q.storage}}}let T=x%P;return T>0&&(x+=P-T),w.__size=x,w.__cache={},this}function _(w){let b={boundary:0,storage:0};return typeof w=="number"||typeof w=="boolean"?(b.boundary=4,b.storage=4):w.isVector2?(b.boundary=8,b.storage=8):w.isVector3||w.isColor?(b.boundary=16,b.storage=12):w.isVector4?(b.boundary=16,b.storage=16):w.isMatrix3?(b.boundary=48,b.storage=48):w.isMatrix4?(b.boundary=64,b.storage=64):w.isTexture?console.warn("THREE.WebGLRenderer: Texture samplers can not be part of an uniforms group."):console.warn("THREE.WebGLRenderer: Unsupported uniform value type.",w),b}function m(w){let b=w.target;b.removeEventListener("dispose",m);let x=o.indexOf(b.__bindingPointIndex);o.splice(x,1),i.deleteBuffer(s[b.id]),delete s[b.id],delete r[b.id]}function p(){for(let w in s)i.deleteBuffer(s[w]);o=[],s={},r={}}return{bind:l,update:c,dispose:p}}var eo=class{constructor(e={}){let{canvas:t=$d(),context:n=null,depth:s=!0,stencil:r=!1,alpha:o=!1,antialias:a=!1,premultipliedAlpha:l=!0,preserveDrawingBuffer:c=!1,powerPreference:h="default",failIfMajorPerformanceCaveat:u=!1,reverseDepthBuffer:d=!1}=e;this.isWebGLRenderer=!0;let f;if(n!==null){if(typeof WebGLRenderingContext<"u"&&n instanceof WebGLRenderingContext)throw new Error("THREE.WebGLRenderer: WebGL 1 is not supported since r163.");f=n.getContextAttributes().alpha}else f=o;let g=new Uint32Array(4),_=new Int32Array(4),m=null,p=null,w=[],b=[];this.domElement=t,this.debug={checkShaderErrors:!0,onShaderError:null},this.autoClear=!0,this.autoClearColor=!0,this.autoClearDepth=!0,this.autoClearStencil=!0,this.sortObjects=!0,this.clippingPlanes=[],this.localClippingEnabled=!1,this._outputColorSpace=gt,this.toneMapping=di,this.toneMappingExposure=1;let x=this,P=!1,T=0,A=0,R=null,M=-1,v=null,I=new Ye,G=new Ye,O=null,X=new Ae(0),Y=0,V=t.width,Q=t.height,B=1,H=null,j=null,ie=new Ye(0,0,V,Q),Te=new Ye(0,0,V,Q),Re=!1,q=new qs,ee=!1,me=!1,se=new Le,Me=new Le,Pe=new C,Be=new Ye,ct={background:null,fog:null,environment:null,overrideMaterial:null,isScene:!0},We=!1;function ft(){return R===null?B:1}let N=n;function nn(S,D){return t.getContext(S,D)}try{let S={alpha:!0,depth:s,stencil:r,antialias:a,premultipliedAlpha:l,preserveDrawingBuffer:c,powerPreference:h,failIfMajorPerformanceCaveat:u};if("setAttribute"in t&&t.setAttribute("data-engine",`three.js r${El}`),t.addEventListener("webglcontextlost",J,!1),t.addEventListener("webglcontextrestored",ue,!1),t.addEventListener("webglcontextcreationerror",ce,!1),N===null){let D="webgl2";if(N=nn(D,S),N===null)throw nn(D)?new Error("Error creating WebGL context with your selected attributes."):new Error("Error creating WebGL context.")}}catch(S){throw console.error("THREE.WebGLRenderer: "+S.message),S}let He,Ve,be,ot,Se,E,y,F,K,$,Z,ye,le,de,Xe,te,fe,Ee,Ce,pe,Ge,Oe,it,L;function ae(){He=new h0(N),He.init(),Oe=new Vg(N,He),Ve=new s0(N,He,e,Oe),be=new zg(N,He),Ve.reverseDepthBuffer&&d&&be.buffers.depth.setReversed(!0),ot=new f0(N),Se=new Ag,E=new Hg(N,He,be,Se,Ve,Oe,ot),y=new o0(x),F=new c0(x),K=new vf(N),it=new n0(N,K),$=new u0(N,K,ot,it),Z=new m0(N,$,K,ot),Ce=new p0(N,Ve,E),te=new r0(Se),ye=new Eg(x,y,F,He,Ve,it,te),le=new Yg(x,Se),de=new Rg,Xe=new Ug(He),Ee=new t0(x,y,F,be,Z,f,l),fe=new Fg(x,Z,Ve),L=new Zg(N,ot,Ve,be),pe=new i0(N,He,ot),Ge=new d0(N,He,ot),ot.programs=ye.programs,x.capabilities=Ve,x.extensions=He,x.properties=Se,x.renderLists=de,x.shadowMap=fe,x.state=be,x.info=ot}ae();let W=new ul(x,N);this.xr=W,this.getContext=function(){return N},this.getContextAttributes=function(){return N.getContextAttributes()},this.forceContextLoss=function(){let S=He.get("WEBGL_lose_context");S&&S.loseContext()},this.forceContextRestore=function(){let S=He.get("WEBGL_lose_context");S&&S.restoreContext()},this.getPixelRatio=function(){return B},this.setPixelRatio=function(S){S!==void 0&&(B=S,this.setSize(V,Q,!1))},this.getSize=function(S){return S.set(V,Q)},this.setSize=function(S,D,z=!0){if(W.isPresenting){console.warn("THREE.WebGLRenderer: Can't change size while VR device is presenting.");return}V=S,Q=D,t.width=Math.floor(S*B),t.height=Math.floor(D*B),z===!0&&(t.style.width=S+"px",t.style.height=D+"px"),this.setViewport(0,0,S,D)},this.getDrawingBufferSize=function(S){return S.set(V*B,Q*B).floor()},this.setDrawingBufferSize=function(S,D,z){V=S,Q=D,B=z,t.width=Math.floor(S*z),t.height=Math.floor(D*z),this.setViewport(0,0,S,D)},this.getCurrentViewport=function(S){return S.copy(I)},this.getViewport=function(S){return S.copy(ie)},this.setViewport=function(S,D,z,k){S.isVector4?ie.set(S.x,S.y,S.z,S.w):ie.set(S,D,z,k),be.viewport(I.copy(ie).multiplyScalar(B).round())},this.getScissor=function(S){return S.copy(Te)},this.setScissor=function(S,D,z,k){S.isVector4?Te.set(S.x,S.y,S.z,S.w):Te.set(S,D,z,k),be.scissor(G.copy(Te).multiplyScalar(B).round())},this.getScissorTest=function(){return Re},this.setScissorTest=function(S){be.setScissorTest(Re=S)},this.setOpaqueSort=function(S){H=S},this.setTransparentSort=function(S){j=S},this.getClearColor=function(S){return S.copy(Ee.getClearColor())},this.setClearColor=function(){Ee.setClearColor.apply(Ee,arguments)},this.getClearAlpha=function(){return Ee.getClearAlpha()},this.setClearAlpha=function(){Ee.setClearAlpha.apply(Ee,arguments)},this.clear=function(S=!0,D=!0,z=!0){let k=0;if(S){let U=!1;if(R!==null){let ne=R.texture.format;U=ne===Nl||ne===Ul||ne===Dl}if(U){let ne=R.texture.type,he=ne===Vn||ne===Pi||ne===Gs||ne===us||ne===Il||ne===Pl,ge=Ee.getClearColor(),_e=Ee.getClearAlpha(),Ie=ge.r,Ue=ge.g,xe=ge.b;he?(g[0]=Ie,g[1]=Ue,g[2]=xe,g[3]=_e,N.clearBufferuiv(N.COLOR,0,g)):(_[0]=Ie,_[1]=Ue,_[2]=xe,_[3]=_e,N.clearBufferiv(N.COLOR,0,_))}else k|=N.COLOR_BUFFER_BIT}D&&(k|=N.DEPTH_BUFFER_BIT),z&&(k|=N.STENCIL_BUFFER_BIT,this.state.buffers.stencil.setMask(4294967295)),N.clear(k)},this.clearColor=function(){this.clear(!0,!1,!1)},this.clearDepth=function(){this.clear(!1,!0,!1)},this.clearStencil=function(){this.clear(!1,!1,!0)},this.dispose=function(){t.removeEventListener("webglcontextlost",J,!1),t.removeEventListener("webglcontextrestored",ue,!1),t.removeEventListener("webglcontextcreationerror",ce,!1),de.dispose(),Xe.dispose(),Se.dispose(),y.dispose(),F.dispose(),Z.dispose(),it.dispose(),L.dispose(),ye.dispose(),W.dispose(),W.removeEventListener("sessionstart",Rc),W.removeEventListener("sessionend",Cc),Mi.stop()};function J(S){S.preventDefault(),console.log("THREE.WebGLRenderer: Context Lost."),P=!0}function ue(){console.log("THREE.WebGLRenderer: Context Restored."),P=!1;let S=ot.autoReset,D=fe.enabled,z=fe.autoUpdate,k=fe.needsUpdate,U=fe.type;ae(),ot.autoReset=S,fe.enabled=D,fe.autoUpdate=z,fe.needsUpdate=k,fe.type=U}function ce(S){console.error("THREE.WebGLRenderer: A WebGL context could not be created. Reason: ",S.statusMessage)}function De(S){let D=S.target;D.removeEventListener("dispose",De),ut(D)}function ut(S){It(S),Se.remove(S)}function It(S){let D=Se.get(S).programs;D!==void 0&&(D.forEach(function(z){ye.releaseProgram(z)}),S.isShaderMaterial&&ye.releaseShaderCache(S))}this.renderBufferDirect=function(S,D,z,k,U,ne){D===null&&(D=ct);let he=U.isMesh&&U.matrixWorld.determinant()<0,ge=Yu(S,D,z,k,U);be.setMaterial(k,he);let _e=z.index,Ie=1;if(k.wireframe===!0){if(_e=$.getWireframeAttribute(z),_e===void 0)return;Ie=2}let Ue=z.drawRange,xe=z.attributes.position,qe=Ue.start*Ie,st=(Ue.start+Ue.count)*Ie;ne!==null&&(qe=Math.max(qe,ne.start*Ie),st=Math.min(st,(ne.start+ne.count)*Ie)),_e!==null?(qe=Math.max(qe,0),st=Math.min(st,_e.count)):xe!=null&&(qe=Math.max(qe,0),st=Math.min(st,xe.count));let at=st-qe;if(at<0||at===1/0)return;it.setup(U,k,ge,z,_e);let Ht,Ke=pe;if(_e!==null&&(Ht=K.get(_e),Ke=Ge,Ke.setIndex(Ht)),U.isMesh)k.wireframe===!0?(be.setLineWidth(k.wireframeLinewidth*ft()),Ke.setMode(N.LINES)):Ke.setMode(N.TRIANGLES);else if(U.isLine){let ve=k.linewidth;ve===void 0&&(ve=1),be.setLineWidth(ve*ft()),U.isLineSegments?Ke.setMode(N.LINES):U.isLineLoop?Ke.setMode(N.LINE_LOOP):Ke.setMode(N.LINE_STRIP)}else U.isPoints?Ke.setMode(N.POINTS):U.isSprite&&Ke.setMode(N.TRIANGLES);if(U.isBatchedMesh)if(U._multiDrawInstances!==null)Ke.renderMultiDrawInstances(U._multiDrawStarts,U._multiDrawCounts,U._multiDrawCount,U._multiDrawInstances);else if(He.get("WEBGL_multi_draw"))Ke.renderMultiDraw(U._multiDrawStarts,U._multiDrawCounts,U._multiDrawCount);else{let ve=U._multiDrawStarts,In=U._multiDrawCounts,Je=U._multiDrawCount,fn=_e?K.get(_e).bytesPerElement:1,zi=Se.get(k).currentProgram.getUniforms();for(let qt=0;qt<Je;qt++)zi.setValue(N,"_gl_DrawID",qt),Ke.render(ve[qt]/fn,In[qt])}else if(U.isInstancedMesh)Ke.renderInstances(qe,at,U.count);else if(z.isInstancedBufferGeometry){let ve=z._maxInstanceCount!==void 0?z._maxInstanceCount:1/0,In=Math.min(z.instanceCount,ve);Ke.renderInstances(qe,at,In)}else Ke.render(qe,at)};function je(S,D,z){S.transparent===!0&&S.side===Jt&&S.forceSinglePass===!1?(S.side=Ut,S.needsUpdate=!0,cr(S,D,z),S.side=En,S.needsUpdate=!0,cr(S,D,z),S.side=Jt):cr(S,D,z)}this.compile=function(S,D,z=null){z===null&&(z=S),p=Xe.get(z),p.init(D),b.push(p),z.traverseVisible(function(U){U.isLight&&U.layers.test(D.layers)&&(p.pushLight(U),U.castShadow&&p.pushShadow(U))}),S!==z&&S.traverseVisible(function(U){U.isLight&&U.layers.test(D.layers)&&(p.pushLight(U),U.castShadow&&p.pushShadow(U))}),p.setupLights();let k=new Set;return S.traverse(function(U){if(!(U.isMesh||U.isPoints||U.isLine||U.isSprite))return;let ne=U.material;if(ne)if(Array.isArray(ne))for(let he=0;he<ne.length;he++){let ge=ne[he];je(ge,z,U),k.add(ge)}else je(ne,z,U),k.add(ne)}),b.pop(),p=null,k},this.compileAsync=function(S,D,z=null){let k=this.compile(S,D,z);return new Promise(U=>{function ne(){if(k.forEach(function(he){Se.get(he).currentProgram.isReady()&&k.delete(he)}),k.size===0){U(S);return}setTimeout(ne,10)}He.get("KHR_parallel_shader_compile")!==null?ne():setTimeout(ne,10)})};let dn=null;function Cn(S){dn&&dn(S)}function Rc(){Mi.stop()}function Cc(){Mi.start()}let Mi=new Mu;Mi.setAnimationLoop(Cn),typeof self<"u"&&Mi.setContext(self),this.setAnimationLoop=function(S){dn=S,W.setAnimationLoop(S),S===null?Mi.stop():Mi.start()},W.addEventListener("sessionstart",Rc),W.addEventListener("sessionend",Cc),this.render=function(S,D){if(D!==void 0&&D.isCamera!==!0){console.error("THREE.WebGLRenderer.render: camera is not an instance of THREE.Camera.");return}if(P===!0)return;if(S.matrixWorldAutoUpdate===!0&&S.updateMatrixWorld(),D.parent===null&&D.matrixWorldAutoUpdate===!0&&D.updateMatrixWorld(),W.enabled===!0&&W.isPresenting===!0&&(W.cameraAutoUpdate===!0&&W.updateCamera(D),D=W.getCamera()),S.isScene===!0&&S.onBeforeRender(x,S,D,R),p=Xe.get(S,b.length),p.init(D),b.push(p),Me.multiplyMatrices(D.projectionMatrix,D.matrixWorldInverse),q.setFromProjectionMatrix(Me),me=this.localClippingEnabled,ee=te.init(this.clippingPlanes,me),m=de.get(S,w.length),m.init(),w.push(m),W.enabled===!0&&W.isPresenting===!0){let ne=x.xr.getDepthSensingMesh();ne!==null&&Lo(ne,D,-1/0,x.sortObjects)}Lo(S,D,0,x.sortObjects),m.finish(),x.sortObjects===!0&&m.sort(H,j),We=W.enabled===!1||W.isPresenting===!1||W.hasDepthSensing()===!1,We&&Ee.addToRenderList(m,S),this.info.render.frame++,ee===!0&&te.beginShadows();let z=p.state.shadowsArray;fe.render(z,S,D),ee===!0&&te.endShadows(),this.info.autoReset===!0&&this.info.reset();let k=m.opaque,U=m.transmissive;if(p.setupLights(),D.isArrayCamera){let ne=D.cameras;if(U.length>0)for(let he=0,ge=ne.length;he<ge;he++){let _e=ne[he];Pc(k,U,S,_e)}We&&Ee.render(S);for(let he=0,ge=ne.length;he<ge;he++){let _e=ne[he];Ic(m,S,_e,_e.viewport)}}else U.length>0&&Pc(k,U,S,D),We&&Ee.render(S),Ic(m,S,D);R!==null&&(E.updateMultisampleRenderTarget(R),E.updateRenderTargetMipmap(R)),S.isScene===!0&&S.onAfterRender(x,S,D),it.resetDefaultState(),M=-1,v=null,b.pop(),b.length>0?(p=b[b.length-1],ee===!0&&te.setGlobalState(x.clippingPlanes,p.state.camera)):p=null,w.pop(),w.length>0?m=w[w.length-1]:m=null};function Lo(S,D,z,k){if(S.visible===!1)return;if(S.layers.test(D.layers)){if(S.isGroup)z=S.renderOrder;else if(S.isLOD)S.autoUpdate===!0&&S.update(D);else if(S.isLight)p.pushLight(S),S.castShadow&&p.pushShadow(S);else if(S.isSprite){if(!S.frustumCulled||q.intersectsSprite(S)){k&&Be.setFromMatrixPosition(S.matrixWorld).applyMatrix4(Me);let he=Z.update(S),ge=S.material;ge.visible&&m.push(S,he,ge,z,Be.z,null)}}else if((S.isMesh||S.isLine||S.isPoints)&&(!S.frustumCulled||q.intersectsObject(S))){let he=Z.update(S),ge=S.material;if(k&&(S.boundingSphere!==void 0?(S.boundingSphere===null&&S.computeBoundingSphere(),Be.copy(S.boundingSphere.center)):(he.boundingSphere===null&&he.computeBoundingSphere(),Be.copy(he.boundingSphere.center)),Be.applyMatrix4(S.matrixWorld).applyMatrix4(Me)),Array.isArray(ge)){let _e=he.groups;for(let Ie=0,Ue=_e.length;Ie<Ue;Ie++){let xe=_e[Ie],qe=ge[xe.materialIndex];qe&&qe.visible&&m.push(S,he,qe,z,Be.z,xe)}}else ge.visible&&m.push(S,he,ge,z,Be.z,null)}}let ne=S.children;for(let he=0,ge=ne.length;he<ge;he++)Lo(ne[he],D,z,k)}function Ic(S,D,z,k){let U=S.opaque,ne=S.transmissive,he=S.transparent;p.setupLightsView(z),ee===!0&&te.setGlobalState(x.clippingPlanes,z),k&&be.viewport(I.copy(k)),U.length>0&&lr(U,D,z),ne.length>0&&lr(ne,D,z),he.length>0&&lr(he,D,z),be.buffers.depth.setTest(!0),be.buffers.depth.setMask(!0),be.buffers.color.setMask(!0),be.setPolygonOffset(!1)}function Pc(S,D,z,k){if((z.isScene===!0?z.overrideMaterial:null)!==null)return;p.state.transmissionRenderTarget[k.id]===void 0&&(p.state.transmissionRenderTarget[k.id]=new Wn(1,1,{generateMipmaps:!0,type:He.has("EXT_color_buffer_half_float")||He.has("EXT_color_buffer_float")?tr:Vn,minFilter:wn,samples:4,stencilBuffer:r,resolveDepthBuffer:!1,resolveStencilBuffer:!1,colorSpace:ke.workingColorSpace}));let ne=p.state.transmissionRenderTarget[k.id],he=k.viewport||I;ne.setSize(he.z,he.w);let ge=x.getRenderTarget();x.setRenderTarget(ne),x.getClearColor(X),Y=x.getClearAlpha(),Y<1&&x.setClearColor(16777215,.5),x.clear(),We&&Ee.render(z);let _e=x.toneMapping;x.toneMapping=di;let Ie=k.viewport;if(k.viewport!==void 0&&(k.viewport=void 0),p.setupLightsView(k),ee===!0&&te.setGlobalState(x.clippingPlanes,k),lr(S,z,k),E.updateMultisampleRenderTarget(ne),E.updateRenderTargetMipmap(ne),He.has("WEBGL_multisampled_render_to_texture")===!1){let Ue=!1;for(let xe=0,qe=D.length;xe<qe;xe++){let st=D[xe],at=st.object,Ht=st.geometry,Ke=st.material,ve=st.group;if(Ke.side===Jt&&at.layers.test(k.layers)){let In=Ke.side;Ke.side=Ut,Ke.needsUpdate=!0,Lc(at,z,k,Ht,Ke,ve),Ke.side=In,Ke.needsUpdate=!0,Ue=!0}}Ue===!0&&(E.updateMultisampleRenderTarget(ne),E.updateRenderTargetMipmap(ne))}x.setRenderTarget(ge),x.setClearColor(X,Y),Ie!==void 0&&(k.viewport=Ie),x.toneMapping=_e}function lr(S,D,z){let k=D.isScene===!0?D.overrideMaterial:null;for(let U=0,ne=S.length;U<ne;U++){let he=S[U],ge=he.object,_e=he.geometry,Ie=k===null?he.material:k,Ue=he.group;ge.layers.test(z.layers)&&Lc(ge,D,z,_e,Ie,Ue)}}function Lc(S,D,z,k,U,ne){S.onBeforeRender(x,D,z,k,U,ne),S.modelViewMatrix.multiplyMatrices(z.matrixWorldInverse,S.matrixWorld),S.normalMatrix.getNormalMatrix(S.modelViewMatrix),U.onBeforeRender(x,D,z,k,S,ne),U.transparent===!0&&U.side===Jt&&U.forceSinglePass===!1?(U.side=Ut,U.needsUpdate=!0,x.renderBufferDirect(z,D,k,U,S,ne),U.side=En,U.needsUpdate=!0,x.renderBufferDirect(z,D,k,U,S,ne),U.side=Jt):x.renderBufferDirect(z,D,k,U,S,ne),S.onAfterRender(x,D,z,k,U,ne)}function cr(S,D,z){D.isScene!==!0&&(D=ct);let k=Se.get(S),U=p.state.lights,ne=p.state.shadowsArray,he=U.state.version,ge=ye.getParameters(S,U.state,ne,D,z),_e=ye.getProgramCacheKey(ge),Ie=k.programs;k.environment=S.isMeshStandardMaterial?D.environment:null,k.fog=D.fog,k.envMap=(S.isMeshStandardMaterial?F:y).get(S.envMap||k.environment),k.envMapRotation=k.environment!==null&&S.envMap===null?D.environmentRotation:S.envMapRotation,Ie===void 0&&(S.addEventListener("dispose",De),Ie=new Map,k.programs=Ie);let Ue=Ie.get(_e);if(Ue!==void 0){if(k.currentProgram===Ue&&k.lightsStateVersion===he)return Uc(S,ge),Ue}else ge.uniforms=ye.getUniforms(S),S.onBeforeCompile(ge,x),Ue=ye.acquireProgram(ge,_e),Ie.set(_e,Ue),k.uniforms=ge.uniforms;let xe=k.uniforms;return(!S.isShaderMaterial&&!S.isRawShaderMaterial||S.clipping===!0)&&(xe.clippingPlanes=te.uniform),Uc(S,ge),k.needsLights=Ku(S),k.lightsStateVersion=he,k.needsLights&&(xe.ambientLightColor.value=U.state.ambient,xe.lightProbe.value=U.state.probe,xe.directionalLights.value=U.state.directional,xe.directionalLightShadows.value=U.state.directionalShadow,xe.spotLights.value=U.state.spot,xe.spotLightShadows.value=U.state.spotShadow,xe.rectAreaLights.value=U.state.rectArea,xe.ltc_1.value=U.state.rectAreaLTC1,xe.ltc_2.value=U.state.rectAreaLTC2,xe.pointLights.value=U.state.point,xe.pointLightShadows.value=U.state.pointShadow,xe.hemisphereLights.value=U.state.hemi,xe.directionalShadowMap.value=U.state.directionalShadowMap,xe.directionalShadowMatrix.value=U.state.directionalShadowMatrix,xe.spotShadowMap.value=U.state.spotShadowMap,xe.spotLightMatrix.value=U.state.spotLightMatrix,xe.spotLightMap.value=U.state.spotLightMap,xe.pointShadowMap.value=U.state.pointShadowMap,xe.pointShadowMatrix.value=U.state.pointShadowMatrix),k.currentProgram=Ue,k.uniformsList=null,Ue}function Dc(S){if(S.uniformsList===null){let D=S.currentProgram.getUniforms();S.uniformsList=as.seqWithValue(D.seq,S.uniforms)}return S.uniformsList}function Uc(S,D){let z=Se.get(S);z.outputColorSpace=D.outputColorSpace,z.batching=D.batching,z.batchingColor=D.batchingColor,z.instancing=D.instancing,z.instancingColor=D.instancingColor,z.instancingMorph=D.instancingMorph,z.skinning=D.skinning,z.morphTargets=D.morphTargets,z.morphNormals=D.morphNormals,z.morphColors=D.morphColors,z.morphTargetsCount=D.morphTargetsCount,z.numClippingPlanes=D.numClippingPlanes,z.numIntersection=D.numClipIntersection,z.vertexAlphas=D.vertexAlphas,z.vertexTangents=D.vertexTangents,z.toneMapping=D.toneMapping}function Yu(S,D,z,k,U){D.isScene!==!0&&(D=ct),E.resetTextureUnits();let ne=D.fog,he=k.isMeshStandardMaterial?D.environment:null,ge=R===null?x.outputColorSpace:R.isXRRenderTarget===!0?R.texture.colorSpace:Ft,_e=(k.isMeshStandardMaterial?F:y).get(k.envMap||he),Ie=k.vertexColors===!0&&!!z.attributes.color&&z.attributes.color.itemSize===4,Ue=!!z.attributes.tangent&&(!!k.normalMap||k.anisotropy>0),xe=!!z.morphAttributes.position,qe=!!z.morphAttributes.normal,st=!!z.morphAttributes.color,at=di;k.toneMapped&&(R===null||R.isXRRenderTarget===!0)&&(at=x.toneMapping);let Ht=z.morphAttributes.position||z.morphAttributes.normal||z.morphAttributes.color,Ke=Ht!==void 0?Ht.length:0,ve=Se.get(k),In=p.state.lights;if(ee===!0&&(me===!0||S!==v)){let sn=S===v&&k.id===M;te.setState(k,S,sn)}let Je=!1;k.version===ve.__version?(ve.needsLights&&ve.lightsStateVersion!==In.state.version||ve.outputColorSpace!==ge||U.isBatchedMesh&&ve.batching===!1||!U.isBatchedMesh&&ve.batching===!0||U.isBatchedMesh&&ve.batchingColor===!0&&U.colorTexture===null||U.isBatchedMesh&&ve.batchingColor===!1&&U.colorTexture!==null||U.isInstancedMesh&&ve.instancing===!1||!U.isInstancedMesh&&ve.instancing===!0||U.isSkinnedMesh&&ve.skinning===!1||!U.isSkinnedMesh&&ve.skinning===!0||U.isInstancedMesh&&ve.instancingColor===!0&&U.instanceColor===null||U.isInstancedMesh&&ve.instancingColor===!1&&U.instanceColor!==null||U.isInstancedMesh&&ve.instancingMorph===!0&&U.morphTexture===null||U.isInstancedMesh&&ve.instancingMorph===!1&&U.morphTexture!==null||ve.envMap!==_e||k.fog===!0&&ve.fog!==ne||ve.numClippingPlanes!==void 0&&(ve.numClippingPlanes!==te.numPlanes||ve.numIntersection!==te.numIntersection)||ve.vertexAlphas!==Ie||ve.vertexTangents!==Ue||ve.morphTargets!==xe||ve.morphNormals!==qe||ve.morphColors!==st||ve.toneMapping!==at||ve.morphTargetsCount!==Ke)&&(Je=!0):(Je=!0,ve.__version=k.version);let fn=ve.currentProgram;Je===!0&&(fn=cr(k,D,U));let zi=!1,qt=!1,Ts=!1,lt=fn.getUniforms(),Sn=ve.uniforms;if(be.useProgram(fn.program)&&(zi=!0,qt=!0,Ts=!0),k.id!==M&&(M=k.id,qt=!0),zi||v!==S){be.buffers.depth.getReversed()?(se.copy(S.projectionMatrix),ef(se),tf(se),lt.setValue(N,"projectionMatrix",se)):lt.setValue(N,"projectionMatrix",S.projectionMatrix),lt.setValue(N,"viewMatrix",S.matrixWorldInverse);let ei=lt.map.cameraPosition;ei!==void 0&&ei.setValue(N,Pe.setFromMatrixPosition(S.matrixWorld)),Ve.logarithmicDepthBuffer&&lt.setValue(N,"logDepthBufFC",2/(Math.log(S.far+1)/Math.LN2)),(k.isMeshPhongMaterial||k.isMeshToonMaterial||k.isMeshLambertMaterial||k.isMeshBasicMaterial||k.isMeshStandardMaterial||k.isShaderMaterial)&&lt.setValue(N,"isOrthographic",S.isOrthographicCamera===!0),v!==S&&(v=S,qt=!0,Ts=!0)}if(U.isSkinnedMesh){lt.setOptional(N,U,"bindMatrix"),lt.setOptional(N,U,"bindMatrixInverse");let sn=U.skeleton;sn&&(sn.boneTexture===null&&sn.computeBoneTexture(),lt.setValue(N,"boneTexture",sn.boneTexture,E))}U.isBatchedMesh&&(lt.setOptional(N,U,"batchingTexture"),lt.setValue(N,"batchingTexture",U._matricesTexture,E),lt.setOptional(N,U,"batchingIdTexture"),lt.setValue(N,"batchingIdTexture",U._indirectTexture,E),lt.setOptional(N,U,"batchingColorTexture"),U._colorsTexture!==null&&lt.setValue(N,"batchingColorTexture",U._colorsTexture,E));let Rs=z.morphAttributes;if((Rs.position!==void 0||Rs.normal!==void 0||Rs.color!==void 0)&&Ce.update(U,z,fn),(qt||ve.receiveShadow!==U.receiveShadow)&&(ve.receiveShadow=U.receiveShadow,lt.setValue(N,"receiveShadow",U.receiveShadow)),k.isMeshGouraudMaterial&&k.envMap!==null&&(Sn.envMap.value=_e,Sn.flipEnvMap.value=_e.isCubeTexture&&_e.isRenderTargetTexture===!1?-1:1),k.isMeshStandardMaterial&&k.envMap===null&&D.environment!==null&&(Sn.envMapIntensity.value=D.environmentIntensity),qt&&(lt.setValue(N,"toneMappingExposure",x.toneMappingExposure),ve.needsLights&&Zu(Sn,Ts),ne&&k.fog===!0&&le.refreshFogUniforms(Sn,ne),le.refreshMaterialUniforms(Sn,k,B,Q,p.state.transmissionRenderTarget[S.id]),as.upload(N,Dc(ve),Sn,E)),k.isShaderMaterial&&k.uniformsNeedUpdate===!0&&(as.upload(N,Dc(ve),Sn,E),k.uniformsNeedUpdate=!1),k.isSpriteMaterial&&lt.setValue(N,"center",U.center),lt.setValue(N,"modelViewMatrix",U.modelViewMatrix),lt.setValue(N,"normalMatrix",U.normalMatrix),lt.setValue(N,"modelMatrix",U.matrixWorld),k.isShaderMaterial||k.isRawShaderMaterial){let sn=k.uniformsGroups;for(let ei=0,ti=sn.length;ei<ti;ei++){let Nc=sn[ei];L.update(Nc,fn),L.bind(Nc,fn)}}return fn}function Zu(S,D){S.ambientLightColor.needsUpdate=D,S.lightProbe.needsUpdate=D,S.directionalLights.needsUpdate=D,S.directionalLightShadows.needsUpdate=D,S.pointLights.needsUpdate=D,S.pointLightShadows.needsUpdate=D,S.spotLights.needsUpdate=D,S.spotLightShadows.needsUpdate=D,S.rectAreaLights.needsUpdate=D,S.hemisphereLights.needsUpdate=D}function Ku(S){return S.isMeshLambertMaterial||S.isMeshToonMaterial||S.isMeshPhongMaterial||S.isMeshStandardMaterial||S.isShadowMaterial||S.isShaderMaterial&&S.lights===!0}this.getActiveCubeFace=function(){return T},this.getActiveMipmapLevel=function(){return A},this.getRenderTarget=function(){return R},this.setRenderTargetTextures=function(S,D,z){Se.get(S.texture).__webglTexture=D,Se.get(S.depthTexture).__webglTexture=z;let k=Se.get(S);k.__hasExternalTextures=!0,k.__autoAllocateDepthBuffer=z===void 0,k.__autoAllocateDepthBuffer||He.has("WEBGL_multisampled_render_to_texture")===!0&&(console.warn("THREE.WebGLRenderer: Render-to-texture extension was disabled because an external texture was provided"),k.__useRenderToTexture=!1)},this.setRenderTargetFramebuffer=function(S,D){let z=Se.get(S);z.__webglFramebuffer=D,z.__useDefaultFramebuffer=D===void 0},this.setRenderTarget=function(S,D=0,z=0){R=S,T=D,A=z;let k=!0,U=null,ne=!1,he=!1;if(S){let _e=Se.get(S);if(_e.__useDefaultFramebuffer!==void 0)be.bindFramebuffer(N.FRAMEBUFFER,null),k=!1;else if(_e.__webglFramebuffer===void 0)E.setupRenderTarget(S);else if(_e.__hasExternalTextures)E.rebindTextures(S,Se.get(S.texture).__webglTexture,Se.get(S.depthTexture).__webglTexture);else if(S.depthBuffer){let xe=S.depthTexture;if(_e.__boundDepthTexture!==xe){if(xe!==null&&Se.has(xe)&&(S.width!==xe.image.width||S.height!==xe.image.height))throw new Error("WebGLRenderTarget: Attached DepthTexture is initialized to the incorrect size.");E.setupDepthRenderbuffer(S)}}let Ie=S.texture;(Ie.isData3DTexture||Ie.isDataArrayTexture||Ie.isCompressedArrayTexture)&&(he=!0);let Ue=Se.get(S).__webglFramebuffer;S.isWebGLCubeRenderTarget?(Array.isArray(Ue[D])?U=Ue[D][z]:U=Ue[D],ne=!0):S.samples>0&&E.useMultisampledRTT(S)===!1?U=Se.get(S).__webglMultisampledFramebuffer:Array.isArray(Ue)?U=Ue[z]:U=Ue,I.copy(S.viewport),G.copy(S.scissor),O=S.scissorTest}else I.copy(ie).multiplyScalar(B).floor(),G.copy(Te).multiplyScalar(B).floor(),O=Re;if(be.bindFramebuffer(N.FRAMEBUFFER,U)&&k&&be.drawBuffers(S,U),be.viewport(I),be.scissor(G),be.setScissorTest(O),ne){let _e=Se.get(S.texture);N.framebufferTexture2D(N.FRAMEBUFFER,N.COLOR_ATTACHMENT0,N.TEXTURE_CUBE_MAP_POSITIVE_X+D,_e.__webglTexture,z)}else if(he){let _e=Se.get(S.texture),Ie=D||0;N.framebufferTextureLayer(N.FRAMEBUFFER,N.COLOR_ATTACHMENT0,_e.__webglTexture,z||0,Ie)}M=-1},this.readRenderTargetPixels=function(S,D,z,k,U,ne,he){if(!(S&&S.isWebGLRenderTarget)){console.error("THREE.WebGLRenderer.readRenderTargetPixels: renderTarget is not THREE.WebGLRenderTarget.");return}let ge=Se.get(S).__webglFramebuffer;if(S.isWebGLCubeRenderTarget&&he!==void 0&&(ge=ge[he]),ge){be.bindFramebuffer(N.FRAMEBUFFER,ge);try{let _e=S.texture,Ie=_e.format,Ue=_e.type;if(!Ve.textureFormatReadable(Ie)){console.error("THREE.WebGLRenderer.readRenderTargetPixels: renderTarget is not in RGBA or implementation defined format.");return}if(!Ve.textureTypeReadable(Ue)){console.error("THREE.WebGLRenderer.readRenderTargetPixels: renderTarget is not in UnsignedByteType or implementation defined type.");return}D>=0&&D<=S.width-k&&z>=0&&z<=S.height-U&&N.readPixels(D,z,k,U,Oe.convert(Ie),Oe.convert(Ue),ne)}finally{let _e=R!==null?Se.get(R).__webglFramebuffer:null;be.bindFramebuffer(N.FRAMEBUFFER,_e)}}},this.readRenderTargetPixelsAsync=async function(S,D,z,k,U,ne,he){if(!(S&&S.isWebGLRenderTarget))throw new Error("THREE.WebGLRenderer.readRenderTargetPixels: renderTarget is not THREE.WebGLRenderTarget.");let ge=Se.get(S).__webglFramebuffer;if(S.isWebGLCubeRenderTarget&&he!==void 0&&(ge=ge[he]),ge){let _e=S.texture,Ie=_e.format,Ue=_e.type;if(!Ve.textureFormatReadable(Ie))throw new Error("THREE.WebGLRenderer.readRenderTargetPixelsAsync: renderTarget is not in RGBA or implementation defined format.");if(!Ve.textureTypeReadable(Ue))throw new Error("THREE.WebGLRenderer.readRenderTargetPixelsAsync: renderTarget is not in UnsignedByteType or implementation defined type.");if(D>=0&&D<=S.width-k&&z>=0&&z<=S.height-U){be.bindFramebuffer(N.FRAMEBUFFER,ge);let xe=N.createBuffer();N.bindBuffer(N.PIXEL_PACK_BUFFER,xe),N.bufferData(N.PIXEL_PACK_BUFFER,ne.byteLength,N.STREAM_READ),N.readPixels(D,z,k,U,Oe.convert(Ie),Oe.convert(Ue),0);let qe=R!==null?Se.get(R).__webglFramebuffer:null;be.bindFramebuffer(N.FRAMEBUFFER,qe);let st=N.fenceSync(N.SYNC_GPU_COMMANDS_COMPLETE,0);return N.flush(),await Qd(N,st,4),N.bindBuffer(N.PIXEL_PACK_BUFFER,xe),N.getBufferSubData(N.PIXEL_PACK_BUFFER,0,ne),N.deleteBuffer(xe),N.deleteSync(st),ne}else throw new Error("THREE.WebGLRenderer.readRenderTargetPixelsAsync: requested read bounds are out of range.")}},this.copyFramebufferToTexture=function(S,D=null,z=0){S.isTexture!==!0&&(Fs("WebGLRenderer: copyFramebufferToTexture function signature has changed."),D=arguments[0]||null,S=arguments[1]);let k=Math.pow(2,-z),U=Math.floor(S.image.width*k),ne=Math.floor(S.image.height*k),he=D!==null?D.x:0,ge=D!==null?D.y:0;E.setTexture2D(S,0),N.copyTexSubImage2D(N.TEXTURE_2D,z,0,0,he,ge,U,ne),be.unbindTexture()},this.copyTextureToTexture=function(S,D,z=null,k=null,U=0){S.isTexture!==!0&&(Fs("WebGLRenderer: copyTextureToTexture function signature has changed."),k=arguments[0]||null,S=arguments[1],D=arguments[2],U=arguments[3]||0,z=null);let ne,he,ge,_e,Ie,Ue,xe,qe,st,at=S.isCompressedTexture?S.mipmaps[U]:S.image;z!==null?(ne=z.max.x-z.min.x,he=z.max.y-z.min.y,ge=z.isBox3?z.max.z-z.min.z:1,_e=z.min.x,Ie=z.min.y,Ue=z.isBox3?z.min.z:0):(ne=at.width,he=at.height,ge=at.depth||1,_e=0,Ie=0,Ue=0),k!==null?(xe=k.x,qe=k.y,st=k.z):(xe=0,qe=0,st=0);let Ht=Oe.convert(D.format),Ke=Oe.convert(D.type),ve;D.isData3DTexture?(E.setTexture3D(D,0),ve=N.TEXTURE_3D):D.isDataArrayTexture||D.isCompressedArrayTexture?(E.setTexture2DArray(D,0),ve=N.TEXTURE_2D_ARRAY):(E.setTexture2D(D,0),ve=N.TEXTURE_2D),N.pixelStorei(N.UNPACK_FLIP_Y_WEBGL,D.flipY),N.pixelStorei(N.UNPACK_PREMULTIPLY_ALPHA_WEBGL,D.premultiplyAlpha),N.pixelStorei(N.UNPACK_ALIGNMENT,D.unpackAlignment);let In=N.getParameter(N.UNPACK_ROW_LENGTH),Je=N.getParameter(N.UNPACK_IMAGE_HEIGHT),fn=N.getParameter(N.UNPACK_SKIP_PIXELS),zi=N.getParameter(N.UNPACK_SKIP_ROWS),qt=N.getParameter(N.UNPACK_SKIP_IMAGES);N.pixelStorei(N.UNPACK_ROW_LENGTH,at.width),N.pixelStorei(N.UNPACK_IMAGE_HEIGHT,at.height),N.pixelStorei(N.UNPACK_SKIP_PIXELS,_e),N.pixelStorei(N.UNPACK_SKIP_ROWS,Ie),N.pixelStorei(N.UNPACK_SKIP_IMAGES,Ue);let Ts=S.isDataArrayTexture||S.isData3DTexture,lt=D.isDataArrayTexture||D.isData3DTexture;if(S.isRenderTargetTexture||S.isDepthTexture){let Sn=Se.get(S),Rs=Se.get(D),sn=Se.get(Sn.__renderTarget),ei=Se.get(Rs.__renderTarget);be.bindFramebuffer(N.READ_FRAMEBUFFER,sn.__webglFramebuffer),be.bindFramebuffer(N.DRAW_FRAMEBUFFER,ei.__webglFramebuffer);for(let ti=0;ti<ge;ti++)Ts&&N.framebufferTextureLayer(N.READ_FRAMEBUFFER,N.COLOR_ATTACHMENT0,Se.get(S).__webglTexture,U,Ue+ti),S.isDepthTexture?(lt&&N.framebufferTextureLayer(N.DRAW_FRAMEBUFFER,N.COLOR_ATTACHMENT0,Se.get(D).__webglTexture,U,st+ti),N.blitFramebuffer(_e,Ie,ne,he,xe,qe,ne,he,N.DEPTH_BUFFER_BIT,N.NEAREST)):lt?N.copyTexSubImage3D(ve,U,xe,qe,st+ti,_e,Ie,ne,he):N.copyTexSubImage2D(ve,U,xe,qe,st+ti,_e,Ie,ne,he);be.bindFramebuffer(N.READ_FRAMEBUFFER,null),be.bindFramebuffer(N.DRAW_FRAMEBUFFER,null)}else lt?S.isDataTexture||S.isData3DTexture?N.texSubImage3D(ve,U,xe,qe,st,ne,he,ge,Ht,Ke,at.data):D.isCompressedArrayTexture?N.compressedTexSubImage3D(ve,U,xe,qe,st,ne,he,ge,Ht,at.data):N.texSubImage3D(ve,U,xe,qe,st,ne,he,ge,Ht,Ke,at):S.isDataTexture?N.texSubImage2D(N.TEXTURE_2D,U,xe,qe,ne,he,Ht,Ke,at.data):S.isCompressedTexture?N.compressedTexSubImage2D(N.TEXTURE_2D,U,xe,qe,at.width,at.height,Ht,at.data):N.texSubImage2D(N.TEXTURE_2D,U,xe,qe,ne,he,Ht,Ke,at);N.pixelStorei(N.UNPACK_ROW_LENGTH,In),N.pixelStorei(N.UNPACK_IMAGE_HEIGHT,Je),N.pixelStorei(N.UNPACK_SKIP_PIXELS,fn),N.pixelStorei(N.UNPACK_SKIP_ROWS,zi),N.pixelStorei(N.UNPACK_SKIP_IMAGES,qt),U===0&&D.generateMipmaps&&N.generateMipmap(ve),be.unbindTexture()},this.copyTextureToTexture3D=function(S,D,z=null,k=null,U=0){return S.isTexture!==!0&&(Fs("WebGLRenderer: copyTextureToTexture3D function signature has changed."),z=arguments[0]||null,k=arguments[1]||null,S=arguments[2],D=arguments[3],U=arguments[4]||0),Fs('WebGLRenderer: copyTextureToTexture3D function has been deprecated. Use "copyTextureToTexture" instead.'),this.copyTextureToTexture(S,D,z,k,U)},this.initRenderTarget=function(S){Se.get(S).__webglFramebuffer===void 0&&E.setupRenderTarget(S)},this.initTexture=function(S){S.isCubeTexture?E.setTextureCube(S,0):S.isData3DTexture?E.setTexture3D(S,0):S.isDataArrayTexture||S.isCompressedArrayTexture?E.setTexture2DArray(S,0):E.setTexture2D(S,0),be.unbindTexture()},this.resetState=function(){T=0,A=0,R=null,be.reset(),it.reset()},typeof __THREE_DEVTOOLS__<"u"&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent("observe",{detail:this}))}get coordinateSystem(){return zn}get outputColorSpace(){return this._outputColorSpace}set outputColorSpace(e){this._outputColorSpace=e;let t=this.getContext();t.drawingBufferColorspace=ke._getDrawingBufferColorSpace(e),t.unpackColorSpace=ke._getUnpackColorSpace()}};var to=class i{constructor(e,t=1,n=1e3){this.isFog=!0,this.name="",this.color=new Ae(e),this.near=t,this.far=n}clone(){return new i(this.color,this.near,this.far)}toJSON(){return{type:"Fog",name:this.name,color:this.color.getHex(),near:this.near,far:this.far}}},Ys=class extends ht{constructor(){super(),this.isScene=!0,this.type="Scene",this.background=null,this.environment=null,this.fog=null,this.backgroundBlurriness=0,this.backgroundIntensity=1,this.backgroundRotation=new An,this.environmentIntensity=1,this.environmentRotation=new An,this.overrideMaterial=null,typeof __THREE_DEVTOOLS__<"u"&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent("observe",{detail:this}))}copy(e,t){return super.copy(e,t),e.background!==null&&(this.background=e.background.clone()),e.environment!==null&&(this.environment=e.environment.clone()),e.fog!==null&&(this.fog=e.fog.clone()),this.backgroundBlurriness=e.backgroundBlurriness,this.backgroundIntensity=e.backgroundIntensity,this.backgroundRotation.copy(e.backgroundRotation),this.environmentIntensity=e.environmentIntensity,this.environmentRotation.copy(e.environmentRotation),e.overrideMaterial!==null&&(this.overrideMaterial=e.overrideMaterial.clone()),this.matrixAutoUpdate=e.matrixAutoUpdate,this}toJSON(e){let t=super.toJSON(e);return this.fog!==null&&(t.object.fog=this.fog.toJSON()),this.backgroundBlurriness>0&&(t.object.backgroundBlurriness=this.backgroundBlurriness),this.backgroundIntensity!==1&&(t.object.backgroundIntensity=this.backgroundIntensity),t.object.backgroundRotation=this.backgroundRotation.toArray(),this.environmentIntensity!==1&&(t.object.environmentIntensity=this.environmentIntensity),t.object.environmentRotation=this.environmentRotation.toArray(),t}},Zs=class{constructor(e,t){this.isInterleavedBuffer=!0,this.array=e,this.stride=t,this.count=e!==void 0?e.length/t:0,this.usage=Ka,this.updateRanges=[],this.version=0,this.uuid=yn()}onUploadCallback(){}set needsUpdate(e){e===!0&&this.version++}setUsage(e){return this.usage=e,this}addUpdateRange(e,t){this.updateRanges.push({start:e,count:t})}clearUpdateRanges(){this.updateRanges.length=0}copy(e){return this.array=new e.array.constructor(e.array),this.count=e.count,this.stride=e.stride,this.usage=e.usage,this}copyAt(e,t,n){e*=this.stride,n*=t.stride;for(let s=0,r=this.stride;s<r;s++)this.array[e+s]=t.array[n+s];return this}set(e,t=0){return this.array.set(e,t),this}clone(e){e.arrayBuffers===void 0&&(e.arrayBuffers={}),this.array.buffer._uuid===void 0&&(this.array.buffer._uuid=yn()),e.arrayBuffers[this.array.buffer._uuid]===void 0&&(e.arrayBuffers[this.array.buffer._uuid]=this.array.slice(0).buffer);let t=new this.array.constructor(e.arrayBuffers[this.array.buffer._uuid]),n=new this.constructor(t,this.stride);return n.setUsage(this.usage),n}onUpload(e){return this.onUploadCallback=e,this}toJSON(e){return e.arrayBuffers===void 0&&(e.arrayBuffers={}),this.array.buffer._uuid===void 0&&(this.array.buffer._uuid=yn()),e.arrayBuffers[this.array.buffer._uuid]===void 0&&(e.arrayBuffers[this.array.buffer._uuid]=Array.from(new Uint32Array(this.array.buffer))),{uuid:this.uuid,buffer:this.array.buffer._uuid,type:this.array.constructor.name,stride:this.stride}}},Bt=new C,Ks=class i{constructor(e,t,n,s=!1){this.isInterleavedBufferAttribute=!0,this.name="",this.data=e,this.itemSize=t,this.offset=n,this.normalized=s}get count(){return this.data.count}get array(){return this.data.array}set needsUpdate(e){this.data.needsUpdate=e}applyMatrix4(e){for(let t=0,n=this.data.count;t<n;t++)Bt.fromBufferAttribute(this,t),Bt.applyMatrix4(e),this.setXYZ(t,Bt.x,Bt.y,Bt.z);return this}applyNormalMatrix(e){for(let t=0,n=this.count;t<n;t++)Bt.fromBufferAttribute(this,t),Bt.applyNormalMatrix(e),this.setXYZ(t,Bt.x,Bt.y,Bt.z);return this}transformDirection(e){for(let t=0,n=this.count;t<n;t++)Bt.fromBufferAttribute(this,t),Bt.transformDirection(e),this.setXYZ(t,Bt.x,Bt.y,Bt.z);return this}getComponent(e,t){let n=this.array[e*this.data.stride+this.offset+t];return this.normalized&&(n=_n(n,this.array)),n}setComponent(e,t,n){return this.normalized&&(n=$e(n,this.array)),this.data.array[e*this.data.stride+this.offset+t]=n,this}setX(e,t){return this.normalized&&(t=$e(t,this.array)),this.data.array[e*this.data.stride+this.offset]=t,this}setY(e,t){return this.normalized&&(t=$e(t,this.array)),this.data.array[e*this.data.stride+this.offset+1]=t,this}setZ(e,t){return this.normalized&&(t=$e(t,this.array)),this.data.array[e*this.data.stride+this.offset+2]=t,this}setW(e,t){return this.normalized&&(t=$e(t,this.array)),this.data.array[e*this.data.stride+this.offset+3]=t,this}getX(e){let t=this.data.array[e*this.data.stride+this.offset];return this.normalized&&(t=_n(t,this.array)),t}getY(e){let t=this.data.array[e*this.data.stride+this.offset+1];return this.normalized&&(t=_n(t,this.array)),t}getZ(e){let t=this.data.array[e*this.data.stride+this.offset+2];return this.normalized&&(t=_n(t,this.array)),t}getW(e){let t=this.data.array[e*this.data.stride+this.offset+3];return this.normalized&&(t=_n(t,this.array)),t}setXY(e,t,n){return e=e*this.data.stride+this.offset,this.normalized&&(t=$e(t,this.array),n=$e(n,this.array)),this.data.array[e+0]=t,this.data.array[e+1]=n,this}setXYZ(e,t,n,s){return e=e*this.data.stride+this.offset,this.normalized&&(t=$e(t,this.array),n=$e(n,this.array),s=$e(s,this.array)),this.data.array[e+0]=t,this.data.array[e+1]=n,this.data.array[e+2]=s,this}setXYZW(e,t,n,s,r){return e=e*this.data.stride+this.offset,this.normalized&&(t=$e(t,this.array),n=$e(n,this.array),s=$e(s,this.array),r=$e(r,this.array)),this.data.array[e+0]=t,this.data.array[e+1]=n,this.data.array[e+2]=s,this.data.array[e+3]=r,this}clone(e){if(e===void 0){console.log("THREE.InterleavedBufferAttribute.clone(): Cloning an interleaved buffer attribute will de-interleave buffer data.");let t=[];for(let n=0;n<this.count;n++){let s=n*this.data.stride+this.offset;for(let r=0;r<this.itemSize;r++)t.push(this.data.array[s+r])}return new pt(new this.array.constructor(t),this.itemSize,this.normalized)}else return e.interleavedBuffers===void 0&&(e.interleavedBuffers={}),e.interleavedBuffers[this.data.uuid]===void 0&&(e.interleavedBuffers[this.data.uuid]=this.data.clone(e)),new i(e.interleavedBuffers[this.data.uuid],this.itemSize,this.offset,this.normalized)}toJSON(e){if(e===void 0){console.log("THREE.InterleavedBufferAttribute.toJSON(): Serializing an interleaved buffer attribute will de-interleave buffer data.");let t=[];for(let n=0;n<this.count;n++){let s=n*this.data.stride+this.offset;for(let r=0;r<this.itemSize;r++)t.push(this.data.array[s+r])}return{itemSize:this.itemSize,type:this.array.constructor.name,array:t,normalized:this.normalized}}else return e.interleavedBuffers===void 0&&(e.interleavedBuffers={}),e.interleavedBuffers[this.data.uuid]===void 0&&(e.interleavedBuffers[this.data.uuid]=this.data.toJSON(e)),{isInterleavedBufferAttribute:!0,itemSize:this.itemSize,data:this.data.uuid,offset:this.offset,normalized:this.normalized}}};var Fh=new C,Bh=new Ye,zh=new Ye,Kg=new C,kh=new Le,Ir=new C,oa=new jt,Hh=new Le,aa=new Xn,no=class extends tt{constructor(e,t){super(e,t),this.isSkinnedMesh=!0,this.type="SkinnedMesh",this.bindMode=kc,this.bindMatrix=new Le,this.bindMatrixInverse=new Le,this.boundingBox=null,this.boundingSphere=null}computeBoundingBox(){let e=this.geometry;this.boundingBox===null&&(this.boundingBox=new Ot),this.boundingBox.makeEmpty();let t=e.getAttribute("position");for(let n=0;n<t.count;n++)this.getVertexPosition(n,Ir),this.boundingBox.expandByPoint(Ir)}computeBoundingSphere(){let e=this.geometry;this.boundingSphere===null&&(this.boundingSphere=new jt),this.boundingSphere.makeEmpty();let t=e.getAttribute("position");for(let n=0;n<t.count;n++)this.getVertexPosition(n,Ir),this.boundingSphere.expandByPoint(Ir)}copy(e,t){return super.copy(e,t),this.bindMode=e.bindMode,this.bindMatrix.copy(e.bindMatrix),this.bindMatrixInverse.copy(e.bindMatrixInverse),this.skeleton=e.skeleton,e.boundingBox!==null&&(this.boundingBox=e.boundingBox.clone()),e.boundingSphere!==null&&(this.boundingSphere=e.boundingSphere.clone()),this}raycast(e,t){let n=this.material,s=this.matrixWorld;n!==void 0&&(this.boundingSphere===null&&this.computeBoundingSphere(),oa.copy(this.boundingSphere),oa.applyMatrix4(s),e.ray.intersectsSphere(oa)!==!1&&(Hh.copy(s).invert(),aa.copy(e.ray).applyMatrix4(Hh),!(this.boundingBox!==null&&aa.intersectsBox(this.boundingBox)===!1)&&this._computeIntersections(e,t,aa)))}getVertexPosition(e,t){return super.getVertexPosition(e,t),this.applyBoneTransform(e,t),t}bind(e,t){this.skeleton=e,t===void 0&&(this.updateMatrixWorld(!0),this.skeleton.calculateInverses(),t=this.matrixWorld),this.bindMatrix.copy(t),this.bindMatrixInverse.copy(t).invert()}pose(){this.skeleton.pose()}normalizeSkinWeights(){let e=new Ye,t=this.geometry.attributes.skinWeight;for(let n=0,s=t.count;n<s;n++){e.fromBufferAttribute(t,n);let r=1/e.manhattanLength();r!==1/0?e.multiplyScalar(r):e.set(1,0,0,0),t.setXYZW(n,e.x,e.y,e.z,e.w)}}updateMatrixWorld(e){super.updateMatrixWorld(e),this.bindMode===kc?this.bindMatrixInverse.copy(this.matrixWorld).invert():this.bindMode===wd?this.bindMatrixInverse.copy(this.bindMatrix).invert():console.warn("THREE.SkinnedMesh: Unrecognized bindMode: "+this.bindMode)}applyBoneTransform(e,t){let n=this.skeleton,s=this.geometry;Bh.fromBufferAttribute(s.attributes.skinIndex,e),zh.fromBufferAttribute(s.attributes.skinWeight,e),Fh.copy(t).applyMatrix4(this.bindMatrix),t.set(0,0,0);for(let r=0;r<4;r++){let o=zh.getComponent(r);if(o!==0){let a=Bh.getComponent(r);kh.multiplyMatrices(n.bones[a].matrixWorld,n.boneInverses[a]),t.addScaledVector(Kg.copy(Fh).applyMatrix4(kh),o)}}return t.applyMatrix4(this.bindMatrixInverse)}},Js=class extends ht{constructor(){super(),this.isBone=!0,this.type="Bone"}},io=class extends Et{constructor(e=null,t=1,n=1,s,r,o,a,l,c=Nt,h=Nt,u,d){super(null,o,a,l,c,h,s,r,u,d),this.isDataTexture=!0,this.image={data:e,width:t,height:n},this.generateMipmaps=!1,this.flipY=!1,this.unpackAlignment=1}},Vh=new Le,Jg=new Le,so=class i{constructor(e=[],t=[]){this.uuid=yn(),this.bones=e.slice(0),this.boneInverses=t,this.boneMatrices=null,this.boneTexture=null,this.init()}init(){let e=this.bones,t=this.boneInverses;if(this.boneMatrices=new Float32Array(e.length*16),t.length===0)this.calculateInverses();else if(e.length!==t.length){console.warn("THREE.Skeleton: Number of inverse bone matrices does not match amount of bones."),this.boneInverses=[];for(let n=0,s=this.bones.length;n<s;n++)this.boneInverses.push(new Le)}}calculateInverses(){this.boneInverses.length=0;for(let e=0,t=this.bones.length;e<t;e++){let n=new Le;this.bones[e]&&n.copy(this.bones[e].matrixWorld).invert(),this.boneInverses.push(n)}}pose(){for(let e=0,t=this.bones.length;e<t;e++){let n=this.bones[e];n&&n.matrixWorld.copy(this.boneInverses[e]).invert()}for(let e=0,t=this.bones.length;e<t;e++){let n=this.bones[e];n&&(n.parent&&n.parent.isBone?(n.matrix.copy(n.parent.matrixWorld).invert(),n.matrix.multiply(n.matrixWorld)):n.matrix.copy(n.matrixWorld),n.matrix.decompose(n.position,n.quaternion,n.scale))}}update(){let e=this.bones,t=this.boneInverses,n=this.boneMatrices,s=this.boneTexture;for(let r=0,o=e.length;r<o;r++){let a=e[r]?e[r].matrixWorld:Jg;Vh.multiplyMatrices(a,t[r]),Vh.toArray(n,r*16)}s!==null&&(s.needsUpdate=!0)}clone(){return new i(this.bones,this.boneInverses)}computeBoneTexture(){let e=Math.sqrt(this.bones.length*4);e=Math.ceil(e/4)*4,e=Math.max(e,4);let t=new Float32Array(e*e*4);t.set(this.boneMatrices);let n=new io(t,e,e,on,xn);return n.needsUpdate=!0,this.boneMatrices=t,this.boneTexture=n,this}getBoneByName(e){for(let t=0,n=this.bones.length;t<n;t++){let s=this.bones[t];if(s.name===e)return s}}dispose(){this.boneTexture!==null&&(this.boneTexture.dispose(),this.boneTexture=null)}fromJSON(e,t){this.uuid=e.uuid;for(let n=0,s=e.bones.length;n<s;n++){let r=e.bones[n],o=t[r];o===void 0&&(console.warn("THREE.Skeleton: No bone found with UUID:",r),o=new Js),this.bones.push(o),this.boneInverses.push(new Le().fromArray(e.boneInverses[n]))}return this.init(),this}toJSON(){let e={metadata:{version:4.6,type:"Skeleton",generator:"Skeleton.toJSON"},bones:[],boneInverses:[]};e.uuid=this.uuid;let t=this.bones,n=this.boneInverses;for(let s=0,r=t.length;s<r;s++){let o=t[s];e.bones.push(o.uuid);let a=n[s];e.boneInverses.push(a.toArray())}return e}},Li=class extends pt{constructor(e,t,n,s=1){super(e,t,n),this.isInstancedBufferAttribute=!0,this.meshPerAttribute=s}copy(e){return super.copy(e),this.meshPerAttribute=e.meshPerAttribute,this}toJSON(){let e=super.toJSON();return e.meshPerAttribute=this.meshPerAttribute,e.isInstancedBufferAttribute=!0,e}},es=new Le,Gh=new Le,Pr=[],Wh=new Ot,jg=new Le,Ds=new tt,Us=new jt,ro=class extends tt{constructor(e,t,n){super(e,t),this.isInstancedMesh=!0,this.instanceMatrix=new Li(new Float32Array(n*16),16),this.instanceColor=null,this.morphTexture=null,this.count=n,this.boundingBox=null,this.boundingSphere=null;for(let s=0;s<n;s++)this.setMatrixAt(s,jg)}computeBoundingBox(){let e=this.geometry,t=this.count;this.boundingBox===null&&(this.boundingBox=new Ot),e.boundingBox===null&&e.computeBoundingBox(),this.boundingBox.makeEmpty();for(let n=0;n<t;n++)this.getMatrixAt(n,es),Wh.copy(e.boundingBox).applyMatrix4(es),this.boundingBox.union(Wh)}computeBoundingSphere(){let e=this.geometry,t=this.count;this.boundingSphere===null&&(this.boundingSphere=new jt),e.boundingSphere===null&&e.computeBoundingSphere(),this.boundingSphere.makeEmpty();for(let n=0;n<t;n++)this.getMatrixAt(n,es),Us.copy(e.boundingSphere).applyMatrix4(es),this.boundingSphere.union(Us)}copy(e,t){return super.copy(e,t),this.instanceMatrix.copy(e.instanceMatrix),e.morphTexture!==null&&(this.morphTexture=e.morphTexture.clone()),e.instanceColor!==null&&(this.instanceColor=e.instanceColor.clone()),this.count=e.count,e.boundingBox!==null&&(this.boundingBox=e.boundingBox.clone()),e.boundingSphere!==null&&(this.boundingSphere=e.boundingSphere.clone()),this}getColorAt(e,t){t.fromArray(this.instanceColor.array,e*3)}getMatrixAt(e,t){t.fromArray(this.instanceMatrix.array,e*16)}getMorphAt(e,t){let n=t.morphTargetInfluences,s=this.morphTexture.source.data.data,r=n.length+1,o=e*r+1;for(let a=0;a<n.length;a++)n[a]=s[o+a]}raycast(e,t){let n=this.matrixWorld,s=this.count;if(Ds.geometry=this.geometry,Ds.material=this.material,Ds.material!==void 0&&(this.boundingSphere===null&&this.computeBoundingSphere(),Us.copy(this.boundingSphere),Us.applyMatrix4(n),e.ray.intersectsSphere(Us)!==!1))for(let r=0;r<s;r++){this.getMatrixAt(r,es),Gh.multiplyMatrices(n,es),Ds.matrixWorld=Gh,Ds.raycast(e,Pr);for(let o=0,a=Pr.length;o<a;o++){let l=Pr[o];l.instanceId=r,l.object=this,t.push(l)}Pr.length=0}}setColorAt(e,t){this.instanceColor===null&&(this.instanceColor=new Li(new Float32Array(this.instanceMatrix.count*3).fill(1),3)),t.toArray(this.instanceColor.array,e*3)}setMatrixAt(e,t){t.toArray(this.instanceMatrix.array,e*16)}setMorphAt(e,t){let n=t.morphTargetInfluences,s=n.length+1;this.morphTexture===null&&(this.morphTexture=new io(new Float32Array(s*this.count),s,this.count,Ll,xn));let r=this.morphTexture.source.data.data,o=0;for(let c=0;c<n.length;c++)o+=n[c];let a=this.geometry.morphTargetsRelative?1:1-o,l=s*e;r[l]=a,r.set(n,l+1)}updateMorphTargets(){}dispose(){return this.dispatchEvent({type:"dispose"}),this.morphTexture!==null&&(this.morphTexture.dispose(),this.morphTexture=null),this}};var fi=class extends $t{static get type(){return"LineBasicMaterial"}constructor(e){super(),this.isLineBasicMaterial=!0,this.color=new Ae(16777215),this.map=null,this.linewidth=1,this.linecap="round",this.linejoin="round",this.fog=!0,this.setValues(e)}copy(e){return super.copy(e),this.color.copy(e.color),this.map=e.map,this.linewidth=e.linewidth,this.linecap=e.linecap,this.linejoin=e.linejoin,this.fog=e.fog,this}},oo=new C,ao=new C,Xh=new Le,Ns=new Xn,Lr=new jt,la=new C,qh=new C,ys=class extends ht{constructor(e=new yt,t=new fi){super(),this.isLine=!0,this.type="Line",this.geometry=e,this.material=t,this.updateMorphTargets()}copy(e,t){return super.copy(e,t),this.material=Array.isArray(e.material)?e.material.slice():e.material,this.geometry=e.geometry,this}computeLineDistances(){let e=this.geometry;if(e.index===null){let t=e.attributes.position,n=[0];for(let s=1,r=t.count;s<r;s++)oo.fromBufferAttribute(t,s-1),ao.fromBufferAttribute(t,s),n[s]=n[s-1],n[s]+=oo.distanceTo(ao);e.setAttribute("lineDistance",new dt(n,1))}else console.warn("THREE.Line.computeLineDistances(): Computation only possible with non-indexed BufferGeometry.");return this}raycast(e,t){let n=this.geometry,s=this.matrixWorld,r=e.params.Line.threshold,o=n.drawRange;if(n.boundingSphere===null&&n.computeBoundingSphere(),Lr.copy(n.boundingSphere),Lr.applyMatrix4(s),Lr.radius+=r,e.ray.intersectsSphere(Lr)===!1)return;Xh.copy(s).invert(),Ns.copy(e.ray).applyMatrix4(Xh);let a=r/((this.scale.x+this.scale.y+this.scale.z)/3),l=a*a,c=this.isLineSegments?2:1,h=n.index,d=n.attributes.position;if(h!==null){let f=Math.max(0,o.start),g=Math.min(h.count,o.start+o.count);for(let _=f,m=g-1;_<m;_+=c){let p=h.getX(_),w=h.getX(_+1),b=Dr(this,e,Ns,l,p,w);b&&t.push(b)}if(this.isLineLoop){let _=h.getX(g-1),m=h.getX(f),p=Dr(this,e,Ns,l,_,m);p&&t.push(p)}}else{let f=Math.max(0,o.start),g=Math.min(d.count,o.start+o.count);for(let _=f,m=g-1;_<m;_+=c){let p=Dr(this,e,Ns,l,_,_+1);p&&t.push(p)}if(this.isLineLoop){let _=Dr(this,e,Ns,l,g-1,f);_&&t.push(_)}}}updateMorphTargets(){let t=this.geometry.morphAttributes,n=Object.keys(t);if(n.length>0){let s=t[n[0]];if(s!==void 0){this.morphTargetInfluences=[],this.morphTargetDictionary={};for(let r=0,o=s.length;r<o;r++){let a=s[r].name||String(r);this.morphTargetInfluences.push(0),this.morphTargetDictionary[a]=r}}}}};function Dr(i,e,t,n,s,r){let o=i.geometry.attributes.position;if(oo.fromBufferAttribute(o,s),ao.fromBufferAttribute(o,r),t.distanceSqToSegment(oo,ao,la,qh)>n)return;la.applyMatrix4(i.matrixWorld);let l=e.ray.origin.distanceTo(la);if(!(l<e.near||l>e.far))return{distance:l,point:qh.clone().applyMatrix4(i.matrixWorld),index:s,face:null,faceIndex:null,barycoord:null,object:i}}var Yh=new C,Zh=new C,Di=class extends ys{constructor(e,t){super(e,t),this.isLineSegments=!0,this.type="LineSegments"}computeLineDistances(){let e=this.geometry;if(e.index===null){let t=e.attributes.position,n=[];for(let s=0,r=t.count;s<r;s+=2)Yh.fromBufferAttribute(t,s),Zh.fromBufferAttribute(t,s+1),n[s]=s===0?0:n[s-1],n[s+1]=n[s]+Yh.distanceTo(Zh);e.setAttribute("lineDistance",new dt(n,1))}else console.warn("THREE.LineSegments.computeLineDistances(): Computation only possible with non-indexed BufferGeometry.");return this}},lo=class extends ys{constructor(e,t){super(e,t),this.isLineLoop=!0,this.type="LineLoop"}},js=class extends $t{static get type(){return"PointsMaterial"}constructor(e){super(),this.isPointsMaterial=!0,this.color=new Ae(16777215),this.map=null,this.alphaMap=null,this.size=1,this.sizeAttenuation=!0,this.fog=!0,this.setValues(e)}copy(e){return super.copy(e),this.color.copy(e.color),this.map=e.map,this.alphaMap=e.alphaMap,this.size=e.size,this.sizeAttenuation=e.sizeAttenuation,this.fog=e.fog,this}},Kh=new Le,dl=new Xn,Ur=new jt,Nr=new C,co=class extends ht{constructor(e=new yt,t=new js){super(),this.isPoints=!0,this.type="Points",this.geometry=e,this.material=t,this.updateMorphTargets()}copy(e,t){return super.copy(e,t),this.material=Array.isArray(e.material)?e.material.slice():e.material,this.geometry=e.geometry,this}raycast(e,t){let n=this.geometry,s=this.matrixWorld,r=e.params.Points.threshold,o=n.drawRange;if(n.boundingSphere===null&&n.computeBoundingSphere(),Ur.copy(n.boundingSphere),Ur.applyMatrix4(s),Ur.radius+=r,e.ray.intersectsSphere(Ur)===!1)return;Kh.copy(s).invert(),dl.copy(e.ray).applyMatrix4(Kh);let a=r/((this.scale.x+this.scale.y+this.scale.z)/3),l=a*a,c=n.index,u=n.attributes.position;if(c!==null){let d=Math.max(0,o.start),f=Math.min(c.count,o.start+o.count);for(let g=d,_=f;g<_;g++){let m=c.getX(g);Nr.fromBufferAttribute(u,m),Jh(Nr,m,l,s,e,t,this)}}else{let d=Math.max(0,o.start),f=Math.min(u.count,o.start+o.count);for(let g=d,_=f;g<_;g++)Nr.fromBufferAttribute(u,g),Jh(Nr,g,l,s,e,t,this)}}updateMorphTargets(){let t=this.geometry.morphAttributes,n=Object.keys(t);if(n.length>0){let s=t[n[0]];if(s!==void 0){this.morphTargetInfluences=[],this.morphTargetDictionary={};for(let r=0,o=s.length;r<o;r++){let a=s[r].name||String(r);this.morphTargetInfluences.push(0),this.morphTargetDictionary[a]=r}}}}};function Jh(i,e,t,n,s,r,o){let a=dl.distanceSqToPoint(i);if(a<t){let l=new C;dl.closestPointToPoint(i,l),l.applyMatrix4(n);let c=s.ray.origin.distanceTo(l);if(c<s.near||c>s.far)return;r.push({distance:c,distanceToRay:Math.sqrt(a),point:l,index:e,face:null,faceIndex:null,barycoord:null,object:o})}}var ho=class extends Et{constructor(e,t,n,s,r,o,a,l,c){super(e,t,n,s,r,o,a,l,c),this.isCanvasTexture=!0,this.needsUpdate=!0}};var Or=new C,Fr=new C,ca=new C,Br=new ci,uo=class extends yt{constructor(e=null,t=1){if(super(),this.type="EdgesGeometry",this.parameters={geometry:e,thresholdAngle:t},e!==null){let s=Math.pow(10,4),r=Math.cos(rs*t),o=e.getIndex(),a=e.getAttribute("position"),l=o?o.count:a.count,c=[0,0,0],h=["a","b","c"],u=new Array(3),d={},f=[];for(let g=0;g<l;g+=3){o?(c[0]=o.getX(g),c[1]=o.getX(g+1),c[2]=o.getX(g+2)):(c[0]=g,c[1]=g+1,c[2]=g+2);let{a:_,b:m,c:p}=Br;if(_.fromBufferAttribute(a,c[0]),m.fromBufferAttribute(a,c[1]),p.fromBufferAttribute(a,c[2]),Br.getNormal(ca),u[0]=`${Math.round(_.x*s)},${Math.round(_.y*s)},${Math.round(_.z*s)}`,u[1]=`${Math.round(m.x*s)},${Math.round(m.y*s)},${Math.round(m.z*s)}`,u[2]=`${Math.round(p.x*s)},${Math.round(p.y*s)},${Math.round(p.z*s)}`,!(u[0]===u[1]||u[1]===u[2]||u[2]===u[0]))for(let w=0;w<3;w++){let b=(w+1)%3,x=u[w],P=u[b],T=Br[h[w]],A=Br[h[b]],R=`${x}_${P}`,M=`${P}_${x}`;M in d&&d[M]?(ca.dot(d[M].normal)<=r&&(f.push(T.x,T.y,T.z),f.push(A.x,A.y,A.z)),d[M]=null):R in d||(d[R]={index0:c[w],index1:c[b],normal:ca.clone()})}}for(let g in d)if(d[g]){let{index0:_,index1:m}=d[g];Or.fromBufferAttribute(a,_),Fr.fromBufferAttribute(a,m),f.push(Or.x,Or.y,Or.z),f.push(Fr.x,Fr.y,Fr.z)}this.setAttribute("position",new dt(f,3))}}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}};var fo=class i extends yt{constructor(e=1,t=.4,n=12,s=48,r=Math.PI*2){super(),this.type="TorusGeometry",this.parameters={radius:e,tube:t,radialSegments:n,tubularSegments:s,arc:r},n=Math.floor(n),s=Math.floor(s);let o=[],a=[],l=[],c=[],h=new C,u=new C,d=new C;for(let f=0;f<=n;f++)for(let g=0;g<=s;g++){let _=g/s*r,m=f/n*Math.PI*2;u.x=(e+t*Math.cos(m))*Math.cos(_),u.y=(e+t*Math.cos(m))*Math.sin(_),u.z=t*Math.sin(m),a.push(u.x,u.y,u.z),h.x=e*Math.cos(_),h.y=e*Math.sin(_),d.subVectors(u,h).normalize(),l.push(d.x,d.y,d.z),c.push(g/s),c.push(f/n)}for(let f=1;f<=n;f++)for(let g=1;g<=s;g++){let _=(s+1)*f+g-1,m=(s+1)*(f-1)+g-1,p=(s+1)*(f-1)+g,w=(s+1)*f+g;o.push(_,m,w),o.push(m,p,w)}this.setIndex(o),this.setAttribute("position",new dt(a,3)),this.setAttribute("normal",new dt(l,3)),this.setAttribute("uv",new dt(c,2))}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}static fromJSON(e){return new i(e.radius,e.tube,e.radialSegments,e.tubularSegments,e.arc)}};var kt=class extends $t{static get type(){return"MeshStandardMaterial"}constructor(e){super(),this.isMeshStandardMaterial=!0,this.defines={STANDARD:""},this.color=new Ae(16777215),this.roughness=1,this.metalness=0,this.map=null,this.lightMap=null,this.lightMapIntensity=1,this.aoMap=null,this.aoMapIntensity=1,this.emissive=new Ae(0),this.emissiveIntensity=1,this.emissiveMap=null,this.bumpMap=null,this.bumpScale=1,this.normalMap=null,this.normalMapType=gu,this.normalScale=new we(1,1),this.displacementMap=null,this.displacementScale=1,this.displacementBias=0,this.roughnessMap=null,this.metalnessMap=null,this.alphaMap=null,this.envMap=null,this.envMapRotation=new An,this.envMapIntensity=1,this.wireframe=!1,this.wireframeLinewidth=1,this.wireframeLinecap="round",this.wireframeLinejoin="round",this.flatShading=!1,this.fog=!0,this.setValues(e)}copy(e){return super.copy(e),this.defines={STANDARD:""},this.color.copy(e.color),this.roughness=e.roughness,this.metalness=e.metalness,this.map=e.map,this.lightMap=e.lightMap,this.lightMapIntensity=e.lightMapIntensity,this.aoMap=e.aoMap,this.aoMapIntensity=e.aoMapIntensity,this.emissive.copy(e.emissive),this.emissiveMap=e.emissiveMap,this.emissiveIntensity=e.emissiveIntensity,this.bumpMap=e.bumpMap,this.bumpScale=e.bumpScale,this.normalMap=e.normalMap,this.normalMapType=e.normalMapType,this.normalScale.copy(e.normalScale),this.displacementMap=e.displacementMap,this.displacementScale=e.displacementScale,this.displacementBias=e.displacementBias,this.roughnessMap=e.roughnessMap,this.metalnessMap=e.metalnessMap,this.alphaMap=e.alphaMap,this.envMap=e.envMap,this.envMapRotation.copy(e.envMapRotation),this.envMapIntensity=e.envMapIntensity,this.wireframe=e.wireframe,this.wireframeLinewidth=e.wireframeLinewidth,this.wireframeLinecap=e.wireframeLinecap,this.wireframeLinejoin=e.wireframeLinejoin,this.flatShading=e.flatShading,this.fog=e.fog,this}},Qt=class extends kt{static get type(){return"MeshPhysicalMaterial"}constructor(e){super(),this.isMeshPhysicalMaterial=!0,this.defines={STANDARD:"",PHYSICAL:""},this.anisotropyRotation=0,this.anisotropyMap=null,this.clearcoatMap=null,this.clearcoatRoughness=0,this.clearcoatRoughnessMap=null,this.clearcoatNormalScale=new we(1,1),this.clearcoatNormalMap=null,this.ior=1.5,Object.defineProperty(this,"reflectivity",{get:function(){return Ct(2.5*(this.ior-1)/(this.ior+1),0,1)},set:function(t){this.ior=(1+.4*t)/(1-.4*t)}}),this.iridescenceMap=null,this.iridescenceIOR=1.3,this.iridescenceThicknessRange=[100,400],this.iridescenceThicknessMap=null,this.sheenColor=new Ae(0),this.sheenColorMap=null,this.sheenRoughness=1,this.sheenRoughnessMap=null,this.transmissionMap=null,this.thickness=0,this.thicknessMap=null,this.attenuationDistance=1/0,this.attenuationColor=new Ae(1,1,1),this.specularIntensity=1,this.specularIntensityMap=null,this.specularColor=new Ae(1,1,1),this.specularColorMap=null,this._anisotropy=0,this._clearcoat=0,this._dispersion=0,this._iridescence=0,this._sheen=0,this._transmission=0,this.setValues(e)}get anisotropy(){return this._anisotropy}set anisotropy(e){this._anisotropy>0!=e>0&&this.version++,this._anisotropy=e}get clearcoat(){return this._clearcoat}set clearcoat(e){this._clearcoat>0!=e>0&&this.version++,this._clearcoat=e}get iridescence(){return this._iridescence}set iridescence(e){this._iridescence>0!=e>0&&this.version++,this._iridescence=e}get dispersion(){return this._dispersion}set dispersion(e){this._dispersion>0!=e>0&&this.version++,this._dispersion=e}get sheen(){return this._sheen}set sheen(e){this._sheen>0!=e>0&&this.version++,this._sheen=e}get transmission(){return this._transmission}set transmission(e){this._transmission>0!=e>0&&this.version++,this._transmission=e}copy(e){return super.copy(e),this.defines={STANDARD:"",PHYSICAL:""},this.anisotropy=e.anisotropy,this.anisotropyRotation=e.anisotropyRotation,this.anisotropyMap=e.anisotropyMap,this.clearcoat=e.clearcoat,this.clearcoatMap=e.clearcoatMap,this.clearcoatRoughness=e.clearcoatRoughness,this.clearcoatRoughnessMap=e.clearcoatRoughnessMap,this.clearcoatNormalMap=e.clearcoatNormalMap,this.clearcoatNormalScale.copy(e.clearcoatNormalScale),this.dispersion=e.dispersion,this.ior=e.ior,this.iridescence=e.iridescence,this.iridescenceMap=e.iridescenceMap,this.iridescenceIOR=e.iridescenceIOR,this.iridescenceThicknessRange=[...e.iridescenceThicknessRange],this.iridescenceThicknessMap=e.iridescenceThicknessMap,this.sheen=e.sheen,this.sheenColor.copy(e.sheenColor),this.sheenColorMap=e.sheenColorMap,this.sheenRoughness=e.sheenRoughness,this.sheenRoughnessMap=e.sheenRoughnessMap,this.transmission=e.transmission,this.transmissionMap=e.transmissionMap,this.thickness=e.thickness,this.thicknessMap=e.thicknessMap,this.attenuationDistance=e.attenuationDistance,this.attenuationColor.copy(e.attenuationColor),this.specularIntensity=e.specularIntensity,this.specularIntensityMap=e.specularIntensityMap,this.specularColor.copy(e.specularColor),this.specularColorMap=e.specularColorMap,this}};function zr(i,e,t){return!i||!t&&i.constructor===e?i:typeof e.BYTES_PER_ELEMENT=="number"?new e(i):Array.prototype.slice.call(i)}function $g(i){return ArrayBuffer.isView(i)&&!(i instanceof DataView)}function Qg(i){function e(s,r){return i[s]-i[r]}let t=i.length,n=new Array(t);for(let s=0;s!==t;++s)n[s]=s;return n.sort(e),n}function jh(i,e,t){let n=i.length,s=new i.constructor(n);for(let r=0,o=0;o!==n;++r){let a=t[r]*e;for(let l=0;l!==e;++l)s[o++]=i[a+l]}return s}function Au(i,e,t,n){let s=1,r=i[0];for(;r!==void 0&&r[n]===void 0;)r=i[s++];if(r===void 0)return;let o=r[n];if(o!==void 0)if(Array.isArray(o))do o=r[n],o!==void 0&&(e.push(r.time),t.push.apply(t,o)),r=i[s++];while(r!==void 0);else if(o.toArray!==void 0)do o=r[n],o!==void 0&&(e.push(r.time),o.toArray(t,t.length)),r=i[s++];while(r!==void 0);else do o=r[n],o!==void 0&&(e.push(r.time),t.push(o)),r=i[s++];while(r!==void 0)}var pi=class{constructor(e,t,n,s){this.parameterPositions=e,this._cachedIndex=0,this.resultBuffer=s!==void 0?s:new t.constructor(n),this.sampleValues=t,this.valueSize=n,this.settings=null,this.DefaultSettings_={}}evaluate(e){let t=this.parameterPositions,n=this._cachedIndex,s=t[n],r=t[n-1];n:{e:{let o;t:{i:if(!(e<s)){for(let a=n+2;;){if(s===void 0){if(e<r)break i;return n=t.length,this._cachedIndex=n,this.copySampleValue_(n-1)}if(n===a)break;if(r=s,s=t[++n],e<s)break e}o=t.length;break t}if(!(e>=r)){let a=t[1];e<a&&(n=2,r=a);for(let l=n-2;;){if(r===void 0)return this._cachedIndex=0,this.copySampleValue_(0);if(n===l)break;if(s=r,r=t[--n-1],e>=r)break e}o=n,n=0;break t}break n}for(;n<o;){let a=n+o>>>1;e<t[a]?o=a:n=a+1}if(s=t[n],r=t[n-1],r===void 0)return this._cachedIndex=0,this.copySampleValue_(0);if(s===void 0)return n=t.length,this._cachedIndex=n,this.copySampleValue_(n-1)}this._cachedIndex=n,this.intervalChanged_(n,r,s)}return this.interpolate_(n,r,e,s)}getSettings_(){return this.settings||this.DefaultSettings_}copySampleValue_(e){let t=this.resultBuffer,n=this.sampleValues,s=this.valueSize,r=e*s;for(let o=0;o!==s;++o)t[o]=n[r+o];return t}interpolate_(){throw new Error("call to abstract method")}intervalChanged_(){}},fl=class extends pi{constructor(e,t,n,s){super(e,t,n,s),this._weightPrev=-0,this._offsetPrev=-0,this._weightNext=-0,this._offsetNext=-0,this.DefaultSettings_={endingStart:Hc,endingEnd:Hc}}intervalChanged_(e,t,n){let s=this.parameterPositions,r=e-2,o=e+1,a=s[r],l=s[o];if(a===void 0)switch(this.getSettings_().endingStart){case Vc:r=e,a=2*t-n;break;case Gc:r=s.length-2,a=t+s[r]-s[r+1];break;default:r=e,a=n}if(l===void 0)switch(this.getSettings_().endingEnd){case Vc:o=e,l=2*n-t;break;case Gc:o=1,l=n+s[1]-s[0];break;default:o=e-1,l=t}let c=(n-t)*.5,h=this.valueSize;this._weightPrev=c/(t-a),this._weightNext=c/(l-n),this._offsetPrev=r*h,this._offsetNext=o*h}interpolate_(e,t,n,s){let r=this.resultBuffer,o=this.sampleValues,a=this.valueSize,l=e*a,c=l-a,h=this._offsetPrev,u=this._offsetNext,d=this._weightPrev,f=this._weightNext,g=(n-t)/(s-t),_=g*g,m=_*g,p=-d*m+2*d*_-d*g,w=(1+d)*m+(-1.5-2*d)*_+(-.5+d)*g+1,b=(-1-f)*m+(1.5+f)*_+.5*g,x=f*m-f*_;for(let P=0;P!==a;++P)r[P]=p*o[h+P]+w*o[c+P]+b*o[l+P]+x*o[u+P];return r}},pl=class extends pi{constructor(e,t,n,s){super(e,t,n,s)}interpolate_(e,t,n,s){let r=this.resultBuffer,o=this.sampleValues,a=this.valueSize,l=e*a,c=l-a,h=(n-t)/(s-t),u=1-h;for(let d=0;d!==a;++d)r[d]=o[c+d]*u+o[l+d]*h;return r}},ml=class extends pi{constructor(e,t,n,s){super(e,t,n,s)}interpolate_(e){return this.copySampleValue_(e-1)}},cn=class{constructor(e,t,n,s){if(e===void 0)throw new Error("THREE.KeyframeTrack: track name is undefined");if(t===void 0||t.length===0)throw new Error("THREE.KeyframeTrack: no keyframes in track named "+e);this.name=e,this.times=zr(t,this.TimeBufferType),this.values=zr(n,this.ValueBufferType),this.setInterpolation(s||this.DefaultInterpolation)}static toJSON(e){let t=e.constructor,n;if(t.toJSON!==this.toJSON)n=t.toJSON(e);else{n={name:e.name,times:zr(e.times,Array),values:zr(e.values,Array)};let s=e.getInterpolation();s!==e.DefaultInterpolation&&(n.interpolation=s)}return n.type=e.ValueTypeName,n}InterpolantFactoryMethodDiscrete(e){return new ml(this.times,this.values,this.getValueSize(),e)}InterpolantFactoryMethodLinear(e){return new pl(this.times,this.values,this.getValueSize(),e)}InterpolantFactoryMethodSmooth(e){return new fl(this.times,this.values,this.getValueSize(),e)}setInterpolation(e){let t;switch(e){case fs:t=this.InterpolantFactoryMethodDiscrete;break;case ps:t=this.InterpolantFactoryMethodLinear;break;case Do:t=this.InterpolantFactoryMethodSmooth;break}if(t===void 0){let n="unsupported interpolation for "+this.ValueTypeName+" keyframe track named "+this.name;if(this.createInterpolant===void 0)if(e!==this.DefaultInterpolation)this.setInterpolation(this.DefaultInterpolation);else throw new Error(n);return console.warn("THREE.KeyframeTrack:",n),this}return this.createInterpolant=t,this}getInterpolation(){switch(this.createInterpolant){case this.InterpolantFactoryMethodDiscrete:return fs;case this.InterpolantFactoryMethodLinear:return ps;case this.InterpolantFactoryMethodSmooth:return Do}}getValueSize(){return this.values.length/this.times.length}shift(e){if(e!==0){let t=this.times;for(let n=0,s=t.length;n!==s;++n)t[n]+=e}return this}scale(e){if(e!==1){let t=this.times;for(let n=0,s=t.length;n!==s;++n)t[n]*=e}return this}trim(e,t){let n=this.times,s=n.length,r=0,o=s-1;for(;r!==s&&n[r]<e;)++r;for(;o!==-1&&n[o]>t;)--o;if(++o,r!==0||o!==s){r>=o&&(o=Math.max(o,1),r=o-1);let a=this.getValueSize();this.times=n.slice(r,o),this.values=this.values.slice(r*a,o*a)}return this}validate(){let e=!0,t=this.getValueSize();t-Math.floor(t)!==0&&(console.error("THREE.KeyframeTrack: Invalid value size in track.",this),e=!1);let n=this.times,s=this.values,r=n.length;r===0&&(console.error("THREE.KeyframeTrack: Track is empty.",this),e=!1);let o=null;for(let a=0;a!==r;a++){let l=n[a];if(typeof l=="number"&&isNaN(l)){console.error("THREE.KeyframeTrack: Time is not a valid number.",this,a,l),e=!1;break}if(o!==null&&o>l){console.error("THREE.KeyframeTrack: Out of order keys.",this,a,l,o),e=!1;break}o=l}if(s!==void 0&&$g(s))for(let a=0,l=s.length;a!==l;++a){let c=s[a];if(isNaN(c)){console.error("THREE.KeyframeTrack: Value is not a valid number.",this,a,c),e=!1;break}}return e}optimize(){let e=this.times.slice(),t=this.values.slice(),n=this.getValueSize(),s=this.getInterpolation()===Do,r=e.length-1,o=1;for(let a=1;a<r;++a){let l=!1,c=e[a],h=e[a+1];if(c!==h&&(a!==1||c!==e[0]))if(s)l=!0;else{let u=a*n,d=u-n,f=u+n;for(let g=0;g!==n;++g){let _=t[u+g];if(_!==t[d+g]||_!==t[f+g]){l=!0;break}}}if(l){if(a!==o){e[o]=e[a];let u=a*n,d=o*n;for(let f=0;f!==n;++f)t[d+f]=t[u+f]}++o}}if(r>0){e[o]=e[r];for(let a=r*n,l=o*n,c=0;c!==n;++c)t[l+c]=t[a+c];++o}return o!==e.length?(this.times=e.slice(0,o),this.values=t.slice(0,o*n)):(this.times=e,this.values=t),this}clone(){let e=this.times.slice(),t=this.values.slice(),n=this.constructor,s=new n(this.name,e,t);return s.createInterpolant=this.createInterpolant,s}};cn.prototype.TimeBufferType=Float32Array;cn.prototype.ValueBufferType=Float32Array;cn.prototype.DefaultInterpolation=ps;var mi=class extends cn{constructor(e,t,n){super(e,t,n)}};mi.prototype.ValueTypeName="bool";mi.prototype.ValueBufferType=Array;mi.prototype.DefaultInterpolation=fs;mi.prototype.InterpolantFactoryMethodLinear=void 0;mi.prototype.InterpolantFactoryMethodSmooth=void 0;var po=class extends cn{};po.prototype.ValueTypeName="color";var Zn=class extends cn{};Zn.prototype.ValueTypeName="number";var gl=class extends pi{constructor(e,t,n,s){super(e,t,n,s)}interpolate_(e,t,n,s){let r=this.resultBuffer,o=this.sampleValues,a=this.valueSize,l=(n-t)/(s-t),c=e*a;for(let h=c+a;c!==h;c+=4)Gt.slerpFlat(r,0,o,c-a,o,c,l);return r}},Kn=class extends cn{InterpolantFactoryMethodLinear(e){return new gl(this.times,this.values,this.getValueSize(),e)}};Kn.prototype.ValueTypeName="quaternion";Kn.prototype.InterpolantFactoryMethodSmooth=void 0;var gi=class extends cn{constructor(e,t,n){super(e,t,n)}};gi.prototype.ValueTypeName="string";gi.prototype.ValueBufferType=Array;gi.prototype.DefaultInterpolation=fs;gi.prototype.InterpolantFactoryMethodLinear=void 0;gi.prototype.InterpolantFactoryMethodSmooth=void 0;var Jn=class extends cn{};Jn.prototype.ValueTypeName="vector";var mo=class{constructor(e="",t=-1,n=[],s=Ed){this.name=e,this.tracks=n,this.duration=t,this.blendMode=s,this.uuid=yn(),this.duration<0&&this.resetDuration()}static parse(e){let t=[],n=e.tracks,s=1/(e.fps||1);for(let o=0,a=n.length;o!==a;++o)t.push(t_(n[o]).scale(s));let r=new this(e.name,e.duration,t,e.blendMode);return r.uuid=e.uuid,r}static toJSON(e){let t=[],n=e.tracks,s={name:e.name,duration:e.duration,tracks:t,uuid:e.uuid,blendMode:e.blendMode};for(let r=0,o=n.length;r!==o;++r)t.push(cn.toJSON(n[r]));return s}static CreateFromMorphTargetSequence(e,t,n,s){let r=t.length,o=[];for(let a=0;a<r;a++){let l=[],c=[];l.push((a+r-1)%r,a,(a+1)%r),c.push(0,1,0);let h=Qg(l);l=jh(l,1,h),c=jh(c,1,h),!s&&l[0]===0&&(l.push(r),c.push(c[0])),o.push(new Zn(".morphTargetInfluences["+t[a].name+"]",l,c).scale(1/n))}return new this(e,-1,o)}static findByName(e,t){let n=e;if(!Array.isArray(e)){let s=e;n=s.geometry&&s.geometry.animations||s.animations}for(let s=0;s<n.length;s++)if(n[s].name===t)return n[s];return null}static CreateClipsFromMorphTargetSequences(e,t,n){let s={},r=/^([\w-]*?)([\d]+)$/;for(let a=0,l=e.length;a<l;a++){let c=e[a],h=c.name.match(r);if(h&&h.length>1){let u=h[1],d=s[u];d||(s[u]=d=[]),d.push(c)}}let o=[];for(let a in s)o.push(this.CreateFromMorphTargetSequence(a,s[a],t,n));return o}static parseAnimation(e,t){if(!e)return console.error("THREE.AnimationClip: No animation in JSONLoader data."),null;let n=function(u,d,f,g,_){if(f.length!==0){let m=[],p=[];Au(f,m,p,g),m.length!==0&&_.push(new u(d,m,p))}},s=[],r=e.name||"default",o=e.fps||30,a=e.blendMode,l=e.length||-1,c=e.hierarchy||[];for(let u=0;u<c.length;u++){let d=c[u].keys;if(!(!d||d.length===0))if(d[0].morphTargets){let f={},g;for(g=0;g<d.length;g++)if(d[g].morphTargets)for(let _=0;_<d[g].morphTargets.length;_++)f[d[g].morphTargets[_]]=-1;for(let _ in f){let m=[],p=[];for(let w=0;w!==d[g].morphTargets.length;++w){let b=d[g];m.push(b.time),p.push(b.morphTarget===_?1:0)}s.push(new Zn(".morphTargetInfluence["+_+"]",m,p))}l=f.length*o}else{let f=".bones["+t[u].name+"]";n(Jn,f+".position",d,"pos",s),n(Kn,f+".quaternion",d,"rot",s),n(Jn,f+".scale",d,"scl",s)}}return s.length===0?null:new this(r,l,s,a)}resetDuration(){let e=this.tracks,t=0;for(let n=0,s=e.length;n!==s;++n){let r=this.tracks[n];t=Math.max(t,r.times[r.times.length-1])}return this.duration=t,this}trim(){for(let e=0;e<this.tracks.length;e++)this.tracks[e].trim(0,this.duration);return this}validate(){let e=!0;for(let t=0;t<this.tracks.length;t++)e=e&&this.tracks[t].validate();return e}optimize(){for(let e=0;e<this.tracks.length;e++)this.tracks[e].optimize();return this}clone(){let e=[];for(let t=0;t<this.tracks.length;t++)e.push(this.tracks[t].clone());return new this.constructor(this.name,this.duration,e,this.blendMode)}toJSON(){return this.constructor.toJSON(this)}};function e_(i){switch(i.toLowerCase()){case"scalar":case"double":case"float":case"number":case"integer":return Zn;case"vector":case"vector2":case"vector3":case"vector4":return Jn;case"color":return po;case"quaternion":return Kn;case"bool":case"boolean":return mi;case"string":return gi}throw new Error("THREE.KeyframeTrack: Unsupported typeName: "+i)}function t_(i){if(i.type===void 0)throw new Error("THREE.KeyframeTrack: track type undefined, can not parse");let e=e_(i.type);if(i.times===void 0){let t=[],n=[];Au(i.keys,t,n,"value"),i.times=t,i.values=n}return e.parse!==void 0?e.parse(i):new e(i.name,i.times,i.values,i.interpolation)}var hi={enabled:!1,files:{},add:function(i,e){this.enabled!==!1&&(this.files[i]=e)},get:function(i){if(this.enabled!==!1)return this.files[i]},remove:function(i){delete this.files[i]},clear:function(){this.files={}}},_l=class{constructor(e,t,n){let s=this,r=!1,o=0,a=0,l,c=[];this.onStart=void 0,this.onLoad=e,this.onProgress=t,this.onError=n,this.itemStart=function(h){a++,r===!1&&s.onStart!==void 0&&s.onStart(h,o,a),r=!0},this.itemEnd=function(h){o++,s.onProgress!==void 0&&s.onProgress(h,o,a),o===a&&(r=!1,s.onLoad!==void 0&&s.onLoad())},this.itemError=function(h){s.onError!==void 0&&s.onError(h)},this.resolveURL=function(h){return l?l(h):h},this.setURLModifier=function(h){return l=h,this},this.addHandler=function(h,u){return c.push(h,u),this},this.removeHandler=function(h){let u=c.indexOf(h);return u!==-1&&c.splice(u,2),this},this.getHandler=function(h){for(let u=0,d=c.length;u<d;u+=2){let f=c[u],g=c[u+1];if(f.global&&(f.lastIndex=0),f.test(h))return g}return null}}},n_=new _l,jn=class{constructor(e){this.manager=e!==void 0?e:n_,this.crossOrigin="anonymous",this.withCredentials=!1,this.path="",this.resourcePath="",this.requestHeader={}}load(){}loadAsync(e,t){let n=this;return new Promise(function(s,r){n.load(e,s,t,r)})}parse(){}setCrossOrigin(e){return this.crossOrigin=e,this}setWithCredentials(e){return this.withCredentials=e,this}setPath(e){return this.path=e,this}setResourcePath(e){return this.resourcePath=e,this}setRequestHeader(e){return this.requestHeader=e,this}};jn.DEFAULT_MATERIAL_NAME="__DEFAULT";var On={},xl=class extends Error{constructor(e,t){super(e),this.response=t}},$s=class extends jn{constructor(e){super(e)}load(e,t,n,s){e===void 0&&(e=""),this.path!==void 0&&(e=this.path+e),e=this.manager.resolveURL(e);let r=hi.get(e);if(r!==void 0)return this.manager.itemStart(e),setTimeout(()=>{t&&t(r),this.manager.itemEnd(e)},0),r;if(On[e]!==void 0){On[e].push({onLoad:t,onProgress:n,onError:s});return}On[e]=[],On[e].push({onLoad:t,onProgress:n,onError:s});let o=new Request(e,{headers:new Headers(this.requestHeader),credentials:this.withCredentials?"include":"same-origin"}),a=this.mimeType,l=this.responseType;fetch(o).then(c=>{if(c.status===200||c.status===0){if(c.status===0&&console.warn("THREE.FileLoader: HTTP Status 0 received."),typeof ReadableStream>"u"||c.body===void 0||c.body.getReader===void 0)return c;let h=On[e],u=c.body.getReader(),d=c.headers.get("X-File-Size")||c.headers.get("Content-Length"),f=d?parseInt(d):0,g=f!==0,_=0,m=new ReadableStream({start(p){w();function w(){u.read().then(({done:b,value:x})=>{if(b)p.close();else{_+=x.byteLength;let P=new ProgressEvent("progress",{lengthComputable:g,loaded:_,total:f});for(let T=0,A=h.length;T<A;T++){let R=h[T];R.onProgress&&R.onProgress(P)}p.enqueue(x),w()}},b=>{p.error(b)})}}});return new Response(m)}else throw new xl(`fetch for "${c.url}" responded with ${c.status}: ${c.statusText}`,c)}).then(c=>{switch(l){case"arraybuffer":return c.arrayBuffer();case"blob":return c.blob();case"document":return c.text().then(h=>new DOMParser().parseFromString(h,a));case"json":return c.json();default:if(a===void 0)return c.text();{let u=/charset="?([^;"\s]*)"?/i.exec(a),d=u&&u[1]?u[1].toLowerCase():void 0,f=new TextDecoder(d);return c.arrayBuffer().then(g=>f.decode(g))}}}).then(c=>{hi.add(e,c);let h=On[e];delete On[e];for(let u=0,d=h.length;u<d;u++){let f=h[u];f.onLoad&&f.onLoad(c)}}).catch(c=>{let h=On[e];if(h===void 0)throw this.manager.itemError(e),c;delete On[e];for(let u=0,d=h.length;u<d;u++){let f=h[u];f.onError&&f.onError(c)}this.manager.itemError(e)}).finally(()=>{this.manager.itemEnd(e)}),this.manager.itemStart(e)}setResponseType(e){return this.responseType=e,this}setMimeType(e){return this.mimeType=e,this}};var yl=class extends jn{constructor(e){super(e)}load(e,t,n,s){this.path!==void 0&&(e=this.path+e),e=this.manager.resolveURL(e);let r=this,o=hi.get(e);if(o!==void 0)return r.manager.itemStart(e),setTimeout(function(){t&&t(o),r.manager.itemEnd(e)},0),o;let a=Ws("img");function l(){h(),hi.add(e,this),t&&t(this),r.manager.itemEnd(e)}function c(u){h(),s&&s(u),r.manager.itemError(e),r.manager.itemEnd(e)}function h(){a.removeEventListener("load",l,!1),a.removeEventListener("error",c,!1)}return a.addEventListener("load",l,!1),a.addEventListener("error",c,!1),e.slice(0,5)!=="data:"&&this.crossOrigin!==void 0&&(a.crossOrigin=this.crossOrigin),r.manager.itemStart(e),a.src=e,a}};var go=class extends jn{constructor(e){super(e)}load(e,t,n,s){let r=new Et,o=new yl(this.manager);return o.setCrossOrigin(this.crossOrigin),o.setPath(this.path),o.load(e,function(a){r.image=a,r.needsUpdate=!0,t!==void 0&&t(r)},n,s),r}},vs=class extends ht{constructor(e,t=1){super(),this.isLight=!0,this.type="Light",this.color=new Ae(e),this.intensity=t}dispose(){}copy(e,t){return super.copy(e,t),this.color.copy(e.color),this.intensity=e.intensity,this}toJSON(e){let t=super.toJSON(e);return t.object.color=this.color.getHex(),t.object.intensity=this.intensity,this.groundColor!==void 0&&(t.object.groundColor=this.groundColor.getHex()),this.distance!==void 0&&(t.object.distance=this.distance),this.angle!==void 0&&(t.object.angle=this.angle),this.decay!==void 0&&(t.object.decay=this.decay),this.penumbra!==void 0&&(t.object.penumbra=this.penumbra),this.shadow!==void 0&&(t.object.shadow=this.shadow.toJSON()),this.target!==void 0&&(t.object.target=this.target.uuid),t}},_o=class extends vs{constructor(e,t,n){super(e,n),this.isHemisphereLight=!0,this.type="HemisphereLight",this.position.copy(ht.DEFAULT_UP),this.updateMatrix(),this.groundColor=new Ae(t)}copy(e,t){return super.copy(e,t),this.groundColor.copy(e.groundColor),this}},ha=new Le,$h=new C,Qh=new C,Qs=class{constructor(e){this.camera=e,this.intensity=1,this.bias=0,this.normalBias=0,this.radius=1,this.blurSamples=8,this.mapSize=new we(512,512),this.map=null,this.mapPass=null,this.matrix=new Le,this.autoUpdate=!0,this.needsUpdate=!1,this._frustum=new qs,this._frameExtents=new we(1,1),this._viewportCount=1,this._viewports=[new Ye(0,0,1,1)]}getViewportCount(){return this._viewportCount}getFrustum(){return this._frustum}updateMatrices(e){let t=this.camera,n=this.matrix;$h.setFromMatrixPosition(e.matrixWorld),t.position.copy($h),Qh.setFromMatrixPosition(e.target.matrixWorld),t.lookAt(Qh),t.updateMatrixWorld(),ha.multiplyMatrices(t.projectionMatrix,t.matrixWorldInverse),this._frustum.setFromProjectionMatrix(ha),n.set(.5,0,0,.5,0,.5,0,.5,0,0,.5,.5,0,0,0,1),n.multiply(ha)}getViewport(e){return this._viewports[e]}getFrameExtents(){return this._frameExtents}dispose(){this.map&&this.map.dispose(),this.mapPass&&this.mapPass.dispose()}copy(e){return this.camera=e.camera.clone(),this.intensity=e.intensity,this.bias=e.bias,this.radius=e.radius,this.mapSize.copy(e.mapSize),this}clone(){return new this.constructor().copy(this)}toJSON(){let e={};return this.intensity!==1&&(e.intensity=this.intensity),this.bias!==0&&(e.bias=this.bias),this.normalBias!==0&&(e.normalBias=this.normalBias),this.radius!==1&&(e.radius=this.radius),(this.mapSize.x!==512||this.mapSize.y!==512)&&(e.mapSize=this.mapSize.toArray()),e.camera=this.camera.toJSON(!1).object,delete e.camera.matrix,e}},vl=class extends Qs{constructor(){super(new xt(50,1,.5,500)),this.isSpotLightShadow=!0,this.focus=1}updateMatrices(e){let t=this.camera,n=ms*2*e.angle*this.focus,s=this.mapSize.width/this.mapSize.height,r=e.distance||t.far;(n!==t.fov||s!==t.aspect||r!==t.far)&&(t.fov=n,t.aspect=s,t.far=r,t.updateProjectionMatrix()),super.updateMatrices(e)}copy(e){return super.copy(e),this.focus=e.focus,this}},xo=class extends vs{constructor(e,t,n=0,s=Math.PI/3,r=0,o=2){super(e,t),this.isSpotLight=!0,this.type="SpotLight",this.position.copy(ht.DEFAULT_UP),this.updateMatrix(),this.target=new ht,this.distance=n,this.angle=s,this.penumbra=r,this.decay=o,this.map=null,this.shadow=new vl}get power(){return this.intensity*Math.PI}set power(e){this.intensity=e/Math.PI}dispose(){this.shadow.dispose()}copy(e,t){return super.copy(e,t),this.distance=e.distance,this.angle=e.angle,this.penumbra=e.penumbra,this.decay=e.decay,this.target=e.target.clone(),this.shadow=e.shadow.clone(),this}},eu=new Le,Os=new C,ua=new C,Ml=class extends Qs{constructor(){super(new xt(90,1,.5,500)),this.isPointLightShadow=!0,this._frameExtents=new we(4,2),this._viewportCount=6,this._viewports=[new Ye(2,1,1,1),new Ye(0,1,1,1),new Ye(3,1,1,1),new Ye(1,1,1,1),new Ye(3,0,1,1),new Ye(1,0,1,1)],this._cubeDirections=[new C(1,0,0),new C(-1,0,0),new C(0,0,1),new C(0,0,-1),new C(0,1,0),new C(0,-1,0)],this._cubeUps=[new C(0,1,0),new C(0,1,0),new C(0,1,0),new C(0,1,0),new C(0,0,1),new C(0,0,-1)]}updateMatrices(e,t=0){let n=this.camera,s=this.matrix,r=e.distance||n.far;r!==n.far&&(n.far=r,n.updateProjectionMatrix()),Os.setFromMatrixPosition(e.matrixWorld),n.position.copy(Os),ua.copy(n.position),ua.add(this._cubeDirections[t]),n.up.copy(this._cubeUps[t]),n.lookAt(ua),n.updateMatrixWorld(),s.makeTranslation(-Os.x,-Os.y,-Os.z),eu.multiplyMatrices(n.projectionMatrix,n.matrixWorldInverse),this._frustum.setFromProjectionMatrix(eu)}},Ms=class extends vs{constructor(e,t,n=0,s=2){super(e,t),this.isPointLight=!0,this.type="PointLight",this.distance=n,this.decay=s,this.shadow=new Ml}get power(){return this.intensity*4*Math.PI}set power(e){this.intensity=e/(4*Math.PI)}dispose(){this.shadow.dispose()}copy(e,t){return super.copy(e,t),this.distance=e.distance,this.decay=e.decay,this.shadow=e.shadow.clone(),this}},Sl=class extends Qs{constructor(){super(new _s(-5,5,5,-5,.5,500)),this.isDirectionalLightShadow=!0}},Ss=class extends vs{constructor(e,t){super(e,t),this.isDirectionalLight=!0,this.type="DirectionalLight",this.position.copy(ht.DEFAULT_UP),this.updateMatrix(),this.target=new ht,this.shadow=new Sl}dispose(){this.shadow.dispose()}copy(e){return super.copy(e),this.target=e.target.clone(),this.shadow=e.shadow.clone(),this}};var _i=class{static decodeText(e){if(console.warn("THREE.LoaderUtils: decodeText() has been deprecated with r165 and will be removed with r175. Use TextDecoder instead."),typeof TextDecoder<"u")return new TextDecoder().decode(e);let t="";for(let n=0,s=e.length;n<s;n++)t+=String.fromCharCode(e[n]);try{return decodeURIComponent(escape(t))}catch{return t}}static extractUrlBase(e){let t=e.lastIndexOf("/");return t===-1?"./":e.slice(0,t+1)}static resolveURL(e,t){return typeof e!="string"||e===""?"":(/^https?:\/\//i.test(t)&&/^\//.test(e)&&(t=t.replace(/(^https?:\/\/[^\/]+).*/i,"$1")),/^(https?:)?\/\//i.test(e)||/^data:.*,.*$/i.test(e)||/^blob:.*$/i.test(e)?e:t+e)}};var yo=class extends jn{constructor(e){super(e),this.isImageBitmapLoader=!0,typeof createImageBitmap>"u"&&console.warn("THREE.ImageBitmapLoader: createImageBitmap() not supported."),typeof fetch>"u"&&console.warn("THREE.ImageBitmapLoader: fetch() not supported."),this.options={premultiplyAlpha:"none"}}setOptions(e){return this.options=e,this}load(e,t,n,s){e===void 0&&(e=""),this.path!==void 0&&(e=this.path+e),e=this.manager.resolveURL(e);let r=this,o=hi.get(e);if(o!==void 0){if(r.manager.itemStart(e),o.then){o.then(c=>{t&&t(c),r.manager.itemEnd(e)}).catch(c=>{s&&s(c)});return}return setTimeout(function(){t&&t(o),r.manager.itemEnd(e)},0),o}let a={};a.credentials=this.crossOrigin==="anonymous"?"same-origin":"include",a.headers=this.requestHeader;let l=fetch(e,a).then(function(c){return c.blob()}).then(function(c){return createImageBitmap(c,Object.assign(r.options,{colorSpaceConversion:"none"}))}).then(function(c){return hi.add(e,c),t&&t(c),r.manager.itemEnd(e),c}).catch(function(c){s&&s(c),hi.remove(e),r.manager.itemError(e),r.manager.itemEnd(e)});hi.add(e,l),r.manager.itemStart(e)}};var zl="\\[\\]\\.:\\/",i_=new RegExp("["+zl+"]","g"),kl="[^"+zl+"]",s_="[^"+zl.replace("\\.","")+"]",r_=/((?:WC+[\/:])*)/.source.replace("WC",kl),o_=/(WCOD+)?/.source.replace("WCOD",s_),a_=/(?:\.(WC+)(?:\[(.+)\])?)?/.source.replace("WC",kl),l_=/\.(WC+)(?:\[(.+)\])?/.source.replace("WC",kl),c_=new RegExp("^"+r_+o_+a_+l_+"$"),h_=["material","materials","bones","map"],bl=class{constructor(e,t,n){let s=n||rt.parseTrackName(t);this._targetGroup=e,this._bindings=e.subscribe_(t,s)}getValue(e,t){this.bind();let n=this._targetGroup.nCachedObjects_,s=this._bindings[n];s!==void 0&&s.getValue(e,t)}setValue(e,t){let n=this._bindings;for(let s=this._targetGroup.nCachedObjects_,r=n.length;s!==r;++s)n[s].setValue(e,t)}bind(){let e=this._bindings;for(let t=this._targetGroup.nCachedObjects_,n=e.length;t!==n;++t)e[t].bind()}unbind(){let e=this._bindings;for(let t=this._targetGroup.nCachedObjects_,n=e.length;t!==n;++t)e[t].unbind()}},rt=class i{constructor(e,t,n){this.path=t,this.parsedPath=n||i.parseTrackName(t),this.node=i.findNode(e,this.parsedPath.nodeName),this.rootNode=e,this.getValue=this._getValue_unbound,this.setValue=this._setValue_unbound}static create(e,t,n){return e&&e.isAnimationObjectGroup?new i.Composite(e,t,n):new i(e,t,n)}static sanitizeNodeName(e){return e.replace(/\s/g,"_").replace(i_,"")}static parseTrackName(e){let t=c_.exec(e);if(t===null)throw new Error("PropertyBinding: Cannot parse trackName: "+e);let n={nodeName:t[2],objectName:t[3],objectIndex:t[4],propertyName:t[5],propertyIndex:t[6]},s=n.nodeName&&n.nodeName.lastIndexOf(".");if(s!==void 0&&s!==-1){let r=n.nodeName.substring(s+1);h_.indexOf(r)!==-1&&(n.nodeName=n.nodeName.substring(0,s),n.objectName=r)}if(n.propertyName===null||n.propertyName.length===0)throw new Error("PropertyBinding: can not parse propertyName from trackName: "+e);return n}static findNode(e,t){if(t===void 0||t===""||t==="."||t===-1||t===e.name||t===e.uuid)return e;if(e.skeleton){let n=e.skeleton.getBoneByName(t);if(n!==void 0)return n}if(e.children){let n=function(r){for(let o=0;o<r.length;o++){let a=r[o];if(a.name===t||a.uuid===t)return a;let l=n(a.children);if(l)return l}return null},s=n(e.children);if(s)return s}return null}_getValue_unavailable(){}_setValue_unavailable(){}_getValue_direct(e,t){e[t]=this.targetObject[this.propertyName]}_getValue_array(e,t){let n=this.resolvedProperty;for(let s=0,r=n.length;s!==r;++s)e[t++]=n[s]}_getValue_arrayElement(e,t){e[t]=this.resolvedProperty[this.propertyIndex]}_getValue_toArray(e,t){this.resolvedProperty.toArray(e,t)}_setValue_direct(e,t){this.targetObject[this.propertyName]=e[t]}_setValue_direct_setNeedsUpdate(e,t){this.targetObject[this.propertyName]=e[t],this.targetObject.needsUpdate=!0}_setValue_direct_setMatrixWorldNeedsUpdate(e,t){this.targetObject[this.propertyName]=e[t],this.targetObject.matrixWorldNeedsUpdate=!0}_setValue_array(e,t){let n=this.resolvedProperty;for(let s=0,r=n.length;s!==r;++s)n[s]=e[t++]}_setValue_array_setNeedsUpdate(e,t){let n=this.resolvedProperty;for(let s=0,r=n.length;s!==r;++s)n[s]=e[t++];this.targetObject.needsUpdate=!0}_setValue_array_setMatrixWorldNeedsUpdate(e,t){let n=this.resolvedProperty;for(let s=0,r=n.length;s!==r;++s)n[s]=e[t++];this.targetObject.matrixWorldNeedsUpdate=!0}_setValue_arrayElement(e,t){this.resolvedProperty[this.propertyIndex]=e[t]}_setValue_arrayElement_setNeedsUpdate(e,t){this.resolvedProperty[this.propertyIndex]=e[t],this.targetObject.needsUpdate=!0}_setValue_arrayElement_setMatrixWorldNeedsUpdate(e,t){this.resolvedProperty[this.propertyIndex]=e[t],this.targetObject.matrixWorldNeedsUpdate=!0}_setValue_fromArray(e,t){this.resolvedProperty.fromArray(e,t)}_setValue_fromArray_setNeedsUpdate(e,t){this.resolvedProperty.fromArray(e,t),this.targetObject.needsUpdate=!0}_setValue_fromArray_setMatrixWorldNeedsUpdate(e,t){this.resolvedProperty.fromArray(e,t),this.targetObject.matrixWorldNeedsUpdate=!0}_getValue_unbound(e,t){this.bind(),this.getValue(e,t)}_setValue_unbound(e,t){this.bind(),this.setValue(e,t)}bind(){let e=this.node,t=this.parsedPath,n=t.objectName,s=t.propertyName,r=t.propertyIndex;if(e||(e=i.findNode(this.rootNode,t.nodeName),this.node=e),this.getValue=this._getValue_unavailable,this.setValue=this._setValue_unavailable,!e){console.warn("THREE.PropertyBinding: No target node found for track: "+this.path+".");return}if(n){let c=t.objectIndex;switch(n){case"materials":if(!e.material){console.error("THREE.PropertyBinding: Can not bind to material as node does not have a material.",this);return}if(!e.material.materials){console.error("THREE.PropertyBinding: Can not bind to material.materials as node.material does not have a materials array.",this);return}e=e.material.materials;break;case"bones":if(!e.skeleton){console.error("THREE.PropertyBinding: Can not bind to bones as node does not have a skeleton.",this);return}e=e.skeleton.bones;for(let h=0;h<e.length;h++)if(e[h].name===c){c=h;break}break;case"map":if("map"in e){e=e.map;break}if(!e.material){console.error("THREE.PropertyBinding: Can not bind to material as node does not have a material.",this);return}if(!e.material.map){console.error("THREE.PropertyBinding: Can not bind to material.map as node.material does not have a map.",this);return}e=e.material.map;break;default:if(e[n]===void 0){console.error("THREE.PropertyBinding: Can not bind to objectName of node undefined.",this);return}e=e[n]}if(c!==void 0){if(e[c]===void 0){console.error("THREE.PropertyBinding: Trying to bind to objectIndex of objectName, but is undefined.",this,e);return}e=e[c]}}let o=e[s];if(o===void 0){let c=t.nodeName;console.error("THREE.PropertyBinding: Trying to update property for track: "+c+"."+s+" but it wasn't found.",e);return}let a=this.Versioning.None;this.targetObject=e,e.needsUpdate!==void 0?a=this.Versioning.NeedsUpdate:e.matrixWorldNeedsUpdate!==void 0&&(a=this.Versioning.MatrixWorldNeedsUpdate);let l=this.BindingType.Direct;if(r!==void 0){if(s==="morphTargetInfluences"){if(!e.geometry){console.error("THREE.PropertyBinding: Can not bind to morphTargetInfluences because node does not have a geometry.",this);return}if(!e.geometry.morphAttributes){console.error("THREE.PropertyBinding: Can not bind to morphTargetInfluences because node does not have a geometry.morphAttributes.",this);return}e.morphTargetDictionary[r]!==void 0&&(r=e.morphTargetDictionary[r])}l=this.BindingType.ArrayElement,this.resolvedProperty=o,this.propertyIndex=r}else o.fromArray!==void 0&&o.toArray!==void 0?(l=this.BindingType.HasFromToArray,this.resolvedProperty=o):Array.isArray(o)?(l=this.BindingType.EntireArray,this.resolvedProperty=o):this.propertyName=s;this.getValue=this.GetterByBindingType[l],this.setValue=this.SetterByBindingTypeAndVersioning[l][a]}unbind(){this.node=null,this.getValue=this._getValue_unbound,this.setValue=this._setValue_unbound}};rt.Composite=bl;rt.prototype.BindingType={Direct:0,EntireArray:1,ArrayElement:2,HasFromToArray:3};rt.prototype.Versioning={None:0,NeedsUpdate:1,MatrixWorldNeedsUpdate:2};rt.prototype.GetterByBindingType=[rt.prototype._getValue_direct,rt.prototype._getValue_array,rt.prototype._getValue_arrayElement,rt.prototype._getValue_toArray];rt.prototype.SetterByBindingTypeAndVersioning=[[rt.prototype._setValue_direct,rt.prototype._setValue_direct_setNeedsUpdate,rt.prototype._setValue_direct_setMatrixWorldNeedsUpdate],[rt.prototype._setValue_array,rt.prototype._setValue_array_setNeedsUpdate,rt.prototype._setValue_array_setMatrixWorldNeedsUpdate],[rt.prototype._setValue_arrayElement,rt.prototype._setValue_arrayElement_setNeedsUpdate,rt.prototype._setValue_arrayElement_setMatrixWorldNeedsUpdate],[rt.prototype._setValue_fromArray,rt.prototype._setValue_fromArray_setNeedsUpdate,rt.prototype._setValue_fromArray_setMatrixWorldNeedsUpdate]];var H_=new Float32Array(1);var tu=new Le,vo=class{constructor(e,t,n=0,s=1/0){this.ray=new Xn(e,t),this.near=n,this.far=s,this.camera=null,this.layers=new Xs,this.params={Mesh:{},Line:{threshold:1},LOD:{},Points:{threshold:1},Sprite:{}}}set(e,t){this.ray.set(e,t)}setFromCamera(e,t){t.isPerspectiveCamera?(this.ray.origin.setFromMatrixPosition(t.matrixWorld),this.ray.direction.set(e.x,e.y,.5).unproject(t).sub(this.ray.origin).normalize(),this.camera=t):t.isOrthographicCamera?(this.ray.origin.set(e.x,e.y,(t.near+t.far)/(t.near-t.far)).unproject(t),this.ray.direction.set(0,0,-1).transformDirection(t.matrixWorld),this.camera=t):console.error("THREE.Raycaster: Unsupported camera type: "+t.type)}setFromXRController(e){return tu.identity().extractRotation(e.matrixWorld),this.ray.origin.setFromMatrixPosition(e.matrixWorld),this.ray.direction.set(0,0,-1).applyMatrix4(tu),this}intersectObject(e,t=!0,n=[]){return wl(e,this,n,t),n.sort(nu),n}intersectObjects(e,t=!0,n=[]){for(let s=0,r=e.length;s<r;s++)wl(e[s],this,n,t);return n.sort(nu),n}};function nu(i,e){return i.distance-e.distance}function wl(i,e,t,n){let s=!0;if(i.layers.test(e.layers)&&i.raycast(e,t)===!1&&(s=!1),s===!0&&n===!0){let r=i.children;for(let o=0,a=r.length;o<a;o++)wl(r[o],e,t,!0)}}var er=class{constructor(e=1,t=0,n=0){return this.radius=e,this.phi=t,this.theta=n,this}set(e,t,n){return this.radius=e,this.phi=t,this.theta=n,this}copy(e){return this.radius=e.radius,this.phi=e.phi,this.theta=e.theta,this}makeSafe(){return this.phi=Math.max(1e-6,Math.min(Math.PI-1e-6,this.phi)),this}setFromVector3(e){return this.setFromCartesianCoords(e.x,e.y,e.z)}setFromCartesianCoords(e,t,n){return this.radius=Math.sqrt(e*e+t*t+n*n),this.radius===0?(this.theta=0,this.phi=0):(this.theta=Math.atan2(e,n),this.phi=Math.acos(Ct(t/this.radius,-1,1))),this}clone(){return new this.constructor().copy(this)}};var kr=new Ot,Mo=class extends Di{constructor(e,t=16776960){let n=new Uint16Array([0,1,1,2,2,3,3,0,4,5,5,6,6,7,7,4,0,4,1,5,2,6,3,7]),s=new Float32Array(8*3),r=new yt;r.setIndex(new pt(n,1)),r.setAttribute("position",new pt(s,3)),super(r,new fi({color:t,toneMapped:!1})),this.object=e,this.type="BoxHelper",this.matrixAutoUpdate=!1,this.update()}update(e){if(e!==void 0&&console.warn("THREE.BoxHelper: .update() has no longer arguments."),this.object!==void 0&&kr.setFromObject(this.object),kr.isEmpty())return;let t=kr.min,n=kr.max,s=this.geometry.attributes.position,r=s.array;r[0]=n.x,r[1]=n.y,r[2]=n.z,r[3]=t.x,r[4]=n.y,r[5]=n.z,r[6]=t.x,r[7]=t.y,r[8]=n.z,r[9]=n.x,r[10]=t.y,r[11]=n.z,r[12]=n.x,r[13]=n.y,r[14]=t.z,r[15]=t.x,r[16]=n.y,r[17]=t.z,r[18]=t.x,r[19]=t.y,r[20]=t.z,r[21]=n.x,r[22]=t.y,r[23]=t.z,s.needsUpdate=!0,this.geometry.computeBoundingSphere()}setFromObject(e){return this.object=e,this.update(),this}copy(e,t){return super.copy(e,t),this.object=e.object,this}dispose(){this.geometry.dispose(),this.material.dispose()}};var So=class extends Gn{constructor(e,t=null){super(),this.object=e,this.domElement=t,this.enabled=!0,this.state=-1,this.keys={},this.mouseButtons={LEFT:null,MIDDLE:null,RIGHT:null},this.touches={ONE:null,TWO:null}}connect(){}disconnect(){}dispose(){}update(){}};typeof __THREE_DEVTOOLS__<"u"&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent("register",{detail:{revision:El}}));typeof window<"u"&&(window.__THREE__?console.warn("WARNING: Multiple instances of Three.js being imported."):window.__THREE__=El);var Tu=i=>Math.max(0,Math.min(1,i)),u_=i=>{let e=Tu(i);return e*e*(3-2*e)},ws=(i,e,t)=>u_((i-e)/(t-e)),Vl=[{at:0,title:"\u0418\u0437 \u0437\u0430\u043C\u044B\u0441\u043B\u0430 \u2014 \u0432 \u0434\u043E\u043C",caption:"\u041D\u0430\u0447\u0438\u043D\u0430\u0435\u043C \u0441 \u043F\u0440\u0435\u0434\u043B\u043E\u0436\u0435\u043D\u043D\u043E\u0439 \u043F\u043B\u0430\u043D\u0438\u0440\u043E\u0432\u043A\u0438. \u041A\u043E\u043C\u043D\u0430\u0442\u044B \u0438 \u0440\u0430\u0437\u043C\u0435\u0440\u044B \u0435\u0449\u0451 \u043F\u0440\u0435\u0434\u0441\u0442\u043E\u0438\u0442 \u0441\u043E\u0433\u043B\u0430\u0441\u043E\u0432\u0430\u0442\u044C."},{at:.14,title:"\u041E\u0441\u043D\u043E\u0432\u0430\u043D\u0438\u0435 \u0434\u043E\u043C\u0430",caption:"\u0412 \u044D\u0441\u043A\u0438\u0437\u0435 \u043F\u043E\u043A\u0430\u0437\u0430\u043D\u043E \u0443\u0441\u043B\u043E\u0432\u043D\u043E\u0435 \u043E\u0441\u043D\u043E\u0432\u0430\u043D\u0438\u0435. \u0415\u0433\u043E \u0442\u0438\u043F \u0432\u044B\u0431\u0438\u0440\u0430\u044E\u0442 \u043F\u043E\u0441\u043B\u0435 \u0438\u0437\u0443\u0447\u0435\u043D\u0438\u044F \u0443\u0447\u0430\u0441\u0442\u043A\u0430 \u0438 \u0440\u0430\u0441\u0447\u0451\u0442\u0430."},{at:.28,title:"\u0421\u0442\u0435\u043D\u044B \u0438 \u043A\u043E\u043C\u043D\u0430\u0442\u044B",caption:"\u041B\u0438\u043D\u0438\u0438 \u043F\u043B\u0430\u043D\u0430 \u0441\u0442\u0430\u043D\u043E\u0432\u044F\u0442\u0441\u044F \u043E\u0431\u044A\u0451\u043C\u043E\u043C. \u0412\u0438\u0434\u043D\u044B \u043D\u0430\u0441\u0442\u043E\u044F\u0449\u0438\u0435 \u043F\u0440\u043E\u0451\u043C\u044B \u0438 \u0440\u0430\u0441\u043F\u043E\u043B\u043E\u0436\u0435\u043D\u0438\u0435 \u043F\u043E\u043C\u0435\u0449\u0435\u043D\u0438\u0439 \u044D\u0442\u043E\u0439 \u043C\u043E\u0434\u0435\u043B\u0438."},{at:.5,title:"\u041F\u0435\u0440\u0435\u043A\u0440\u044B\u0442\u0438\u0435 \u0438 \u0441\u0442\u0440\u043E\u043F\u0438\u043B\u0430",caption:"\u041F\u043E\u044F\u0432\u043B\u044F\u044E\u0442\u0441\u044F \u043F\u0435\u0440\u0435\u043A\u0440\u044B\u0442\u0438\u0435 \u0438 \u043D\u0435\u0441\u0443\u0449\u0438\u0435 \u044D\u043B\u0435\u043C\u0435\u043D\u0442\u044B \u043A\u0440\u043E\u0432\u043B\u0438. \u0421\u0435\u0447\u0435\u043D\u0438\u044F \u0438 \u0441\u043E\u0435\u0434\u0438\u043D\u0435\u043D\u0438\u044F \u0437\u0434\u0435\u0441\u044C \u043D\u0435 \u0440\u0430\u0441\u0441\u0447\u0438\u0442\u0430\u043D\u044B."},{at:.66,title:"\u0414\u043E\u043C \u043F\u043E\u043B\u0443\u0447\u0430\u0435\u0442 \u043A\u0440\u043E\u0432\u043B\u044E",caption:"\u041F\u043E\u043A\u0430\u0437\u0430\u043D \u043F\u0440\u0435\u0434\u043B\u0430\u0433\u0430\u0435\u043C\u044B\u0439 \u0432\u0430\u0440\u0438\u0430\u043D\u0442 \u2014 \u0444\u0430\u043B\u044C\u0446\u0435\u0432\u0430\u044F \u0441\u0442\u0430\u043B\u044C\u043D\u0430\u044F \u043A\u0440\u043E\u0432\u043B\u044F. \u0421\u043F\u0435\u0446\u0438\u0444\u0438\u043A\u0430\u0446\u0438\u044E \u043F\u043E\u043A\u0440\u044B\u0442\u0438\u044F \u0435\u0449\u0451 \u043D\u0443\u0436\u043D\u043E \u0432\u044B\u0431\u0440\u0430\u0442\u044C."},{at:.82,title:"\u0424\u0430\u0441\u0430\u0434, \u0441\u0432\u0435\u0442 \u0438 \u0438\u043D\u0442\u0435\u0440\u044C\u0435\u0440",caption:"\u0414\u043E\u0431\u0430\u0432\u043B\u044F\u0435\u043C \u043E\u0441\u0442\u0435\u043A\u043B\u0435\u043D\u0438\u0435, \u0434\u0435\u0440\u0435\u0432\u044F\u043D\u043D\u044B\u0435 \u0434\u0435\u0442\u0430\u043B\u0438, \u0442\u0435\u0440\u0440\u0430\u0441\u0443 \u0438 \u043F\u0440\u0435\u0434\u043B\u043E\u0436\u0435\u043D\u043D\u043E\u0435 \u043E\u0444\u043E\u0440\u043C\u043B\u0435\u043D\u0438\u0435 \u043F\u043E\u043C\u0435\u0449\u0435\u043D\u0438\u0439."},{at:.98,title:"\u0422\u0435\u043F\u0435\u0440\u044C \u0434\u043E\u043C \u043C\u043E\u0436\u043D\u043E \u0438\u0437\u0443\u0447\u0430\u0442\u044C",caption:"\u0420\u0430\u0437\u0431\u0435\u0440\u0438\u0442\u0435 \u0441\u043B\u043E\u0438, \u0441\u043D\u0438\u043C\u0438\u0442\u0435 \u043A\u0440\u043E\u0432\u043B\u044E \u0438\u043B\u0438 \u0437\u0430\u0439\u0434\u0438\u0442\u0435 \u0432\u043D\u0443\u0442\u0440\u044C. \u042D\u0442\u043E \u043E\u0434\u0438\u043D \u0438 \u0442\u043E\u0442 \u0436\u0435 \u0434\u043E\u043C."}];function Ru({house:i,scene:e,renderer:t,camera:n,controls:s,onUpdate:r,onComplete:o}){let a=new Dt;a.name="construction drawing",e.add(a),a.visible=!1,i.updateMatrixWorld(!0);let l=[];for(let H of["03_walls","09_wall_core"])i.getObjectByName(H).traverse(j=>{if(!j.isMesh)return;let ie=new uo(j.geometry,35),Te=ie.getAttribute("position");for(let Re=0;Re<Te.count;Re++){let q=new C().fromBufferAttribute(Te,Re).applyMatrix4(j.matrixWorld);l.push(q.x,q.y,q.z)}ie.dispose()});let c=new Float32Array(l),h=new yt;h.setAttribute("position",new dt(c.slice(),3));let u=new fi({color:3562860,transparent:!0,opacity:.9,depthWrite:!1}),d=new Di(h,u);d.frustumCulled=!1,a.add(d);let f=new tt(new Yn(16,12),new an({color:16250604,transparent:!0,depthWrite:!1}));f.rotation.x=-Math.PI/2,f.position.y=-.339,a.add(f);let g=new Ot().setFromObject(i.getObjectByName("01_foundation")),_=g.getSize(new C),m=g.getCenter(new C),p=new tt(new Yn(_.x,_.z),new kt({color:10066318,roughness:.95}));p.rotation.x=-Math.PI/2,p.position.set(m.x,0,m.z),p.visible=!1,p.receiveShadow=!0,a.add(p);let w={foundation:[.14,.28],walls:[.28,.5],ceiling:[.5,.58],rafters:[.55,.66],underlay:[.66,.71],battens:[.7,.75],roof:[.74,.82],finish:[.82,.98]};function b(H){let j=H;for(;j.parent&&j.parent!==i;)j=j.parent;let ie=j.name;return ie==="01_foundation"?"foundation":ie==="02_structure"||ie==="04_ceiling"?"ceiling":ie==="14_rafters"?"rafters":ie==="15_roof_underlay"?"underlay":ie==="16_roof_battens"?"battens":ie==="05_roof"?"roof":["09_wall_core","10_insulation","11_vent_gap","13_inner_finish"].includes(ie)?"walls":ie==="03_walls"?(Array.isArray(H.material)?H.material:[H.material]).some(Re=>/glass|anthracite|light oak/.test(Re.name))?"finish":"walls":"finish"}let x=!1,P=!1,T=0,A=[],R=new Map,M={},v={},I=!1,G=!0,O=!0;function X(){A=[],R=new Map,M={},v={},O=!1,i.traverse(H=>{if(!H.isMesh)return;let j=b(H),ie=new Ot().setFromObject(H);v[j]?(v[j][0]=Math.min(v[j][0],ie.min.y),v[j][1]=Math.max(v[j][1],ie.max.y)):v[j]=[ie.min.y,ie.max.y],A.push({object:H,phase:j,original:H.material,visible:H.visible})});for(let H of Object.keys(w))M[H]=new Kt(new C(0,-1,0),-1);for(let H of A){let j=Array.isArray(H.original),Te=(j?H.original:[H.original]).map(Re=>{let q=H.phase+":"+Re.uuid;if(!R.has(q)){let ee=Re.clone();ee.onBeforeCompile=Re.onBeforeCompile,ee.customProgramCacheKey=()=>Re.customProgramCacheKey(),ee.clippingPlanes=[M[H.phase]],ee.clipShadows=!0,R.set(q,ee)}return R.get(q)});H.object.material=j?Te:Te[0]}}function Y(){return{active:x,playing:P,progress:T,clipping:t.localClippingEnabled,restored:O,materialsRestored:A.every(H=>H.object.material===H.original),visibleByPhase:Object.fromEntries(Object.keys(w).map(H=>[H,A.filter(j=>j.phase===H&&j.object.visible).length])),clippingHeight:Object.fromEntries(Object.entries(M).map(([H,j])=>[H,j.constant])),wireVertices:c.length/3}}function V(){let H=0;for(let j=0;j<Vl.length;j++)T>=Vl[j].at&&(H=j);r({active:x,playing:P,progress:T,index:H,...Vl[H]},Y())}function Q(H){if(!x)return;T=Tu(H);for(let[Re,[q,ee]]of Object.entries(w)){let me=ws(T,q,ee),se=v[Re];se&&(M[Re].constant=en.lerp(se[0]-.025,se[1]+.025,me));for(let Me of A)Me.phase===Re&&(Me.object.visible=Me.visible&&me>0)}let j=ws(T,.2,.47),ie=h.getAttribute("position");for(let Re=0;Re<ie.count;Re++)ie.setY(Re,en.lerp(-.335,c[Re*3+1]+.006,j));ie.needsUpdate=!0,u.opacity=.92*(1-ws(T,.43,.62)),f.material.opacity=1-ws(T,.14,.28),f.visible=T<.28,p.visible=T>.14&&T<.28,p.visible&&(p.position.y=Math.min(g.max.y,M.foundation.constant)+.001),h.setDrawRange(0,Math.min(ie.count,2*Math.floor(ie.count*Math.max(.03,ws(T,0,.14))/2))),a.visible=T<.62;let Te=ws(T,.14,.94);n.position.lerpVectors(new C(14,24,17),new C(18,9,22),Te),s.target.lerpVectors(new C(0,.1,1),new C(0,1.4,3),Te),n.lookAt(s.target),t.shadowMap.needsUpdate=!0,V()}function B(){if(x){x=!1,P=!1;for(let H of A)H.object.material=H.original,H.object.visible=H.visible;for(let H of R.values())H.dispose();R.clear(),t.localClippingEnabled=I,s.enabled=G,a.visible=!1,t.shadowMap.needsUpdate=!0,O=!0,V()}}return{get active(){return x},get playing(){return P},audit:Y,start({autoplay:H=!0}={}){B(),I=t.localClippingEnabled,G=s.enabled,X(),x=!0,P=H,t.localClippingEnabled=!0,s.enabled=!1,Q(0)},seek(H){P=!1,Q(H)},pause(){x&&(P=!1,V())},toggle(){x&&(T>=1&&Q(0),P=!P,V())},update(H,j){if(!(!x||!P)){if(j){P=!1,V();return}Q(T+H/10),T>=1&&(B(),o())}},cancel:B,dispose(){B(),e.remove(a),h.dispose(),u.dispose(),f.geometry.dispose(),f.material.dispose(),p.geometry.dispose(),p.material.dispose()}}}var Cu={version:1,source:"unbatched-polished.blend",units:"metres",radius:.22,eyeHeight:1.65,floorHeight:.055,modelSha256:"953c85f57a73e064b22c3876998191194a17dde6ca49e16504927161d8a49fbb",bounds:[-6.85,6.85,-4.85,4.85],colliders:[{name:"kitchen tap",group:"07_interior",polygon:[[1.284,-1.175],[1.2871,-1.1844],[1.2951,-1.1902],[1.3049,-1.1902],[1.3129,-1.1844],[1.316,-1.175],[1.316,-.89],[1.3129,-.8819],[1.3049,-.877],[1.2951,-.877],[1.2871,-.8819],[1.284,-.89]],height:[1,1.3914]},{name:"bath spout",group:"07_interior",polygon:[[.545,-2.4445],[.5479,-2.4534],[.5554,-2.4588],[.5646,-2.4588],[.5721,-2.4534],[.575,-2.4445],[.575,-2.27],[.545,-2.27]],height:[.95,1.1827]},{name:"south facade",group:"03_walls",polygon:[[-7,4.885],[-6.9956,4.8744],[-6.985,4.87],[-6.015,4.87],[-6.0044,4.8744],[-6,4.885],[-6,5.115],[-6.0044,5.1256],[-6.015,5.13],[-6.985,5.13],[-6.9956,5.1256],[-7,5.115]],height:[0,3]},{name:"south facade.001",group:"03_walls",polygon:[[-6,4.885],[-5.9956,4.8744],[-5.985,4.87],[-2.715,4.87],[-2.7044,4.8744],[-2.7,4.885],[-2.7,5.115],[-2.7044,5.1256],[-2.715,5.13],[-5.985,5.13],[-5.9956,5.1256],[-6,5.115]],height:[0,.75]},{name:"south facade.003",group:"03_walls",polygon:[[-2.7,4.885],[-2.6956,4.8744],[-2.685,4.87],[-1.665,4.87],[-1.6544,4.8744],[-1.65,4.885],[-1.65,5.115],[-1.6544,5.1256],[-1.665,5.13],[-2.685,5.13],[-2.6956,5.1256],[-2.7,5.115]],height:[0,3]},{name:"south facade.005",group:"03_walls",polygon:[[-.25,4.885],[-.2456,4.8744],[-.235,4.87],[.385,4.87],[.3956,4.8744],[.4,4.885],[.4,5.115],[.3956,5.1256],[.385,5.13],[-.235,5.13],[-.2456,5.1256],[-.25,5.115]],height:[0,3]},{name:"south facade.008",group:"03_walls",polygon:[[6.5,4.885],[6.5044,4.8744],[6.515,4.87],[6.985,4.87],[6.9956,4.8744],[7,4.885],[7,5.115],[6.9956,5.1256],[6.985,5.13],[6.515,5.13],[6.5044,5.1256],[6.5,5.115]],height:[0,3]},{name:"south facade glass",group:"03_walls",polygon:[[-6,4.984],[-2.7,4.984],[-2.7,5.016],[-6,5.016]],height:[.75,2.4]},{name:"south facade frame",group:"03_walls",polygon:[[-6.0325,4.942],[-6.0304,4.9371],[-6.0255,4.935],[-5.9745,4.935],[-5.9696,4.9371],[-5.9675,4.942],[-5.9675,5.058],[-5.9696,5.0629],[-5.9745,5.065],[-6.0255,5.065],[-6.0304,5.0629],[-6.0325,5.058]],height:[.7,2.45]},{name:"south facade frame.001",group:"03_walls",polygon:[[-2.7325,4.942],[-2.7304,4.9371],[-2.7255,4.935],[-2.6745,4.935],[-2.6696,4.9371],[-2.6675,4.942],[-2.6675,5.058],[-2.6696,5.0629],[-2.6745,5.065],[-2.7255,5.065],[-2.7304,5.0629],[-2.7325,5.058]],height:[.7,2.45]},{name:"south facade frame.002",group:"03_walls",polygon:[[-6.06,4.942],[-6.0579,4.9371],[-6.053,4.935],[-2.647,4.935],[-2.6421,4.9371],[-2.64,4.942],[-2.64,5.058],[-2.6421,5.0629],[-2.647,5.065],[-6.053,5.065],[-6.0579,5.0629],[-6.06,5.058]],height:[.7175,.7825]},{name:"south facade mullion",group:"03_walls",polygon:[[-4.9225,4.959],[-4.9213,4.9562],[-4.9185,4.955],[-4.8815,4.955],[-4.8787,4.9562],[-4.8775,4.959],[-4.8775,5.041],[-4.8787,5.0438],[-4.8815,5.045],[-4.9185,5.045],[-4.9213,5.0438],[-4.9225,5.041]],height:[.75,2.4]},{name:"south facade mullion.001",group:"03_walls",polygon:[[-3.8225,4.959],[-3.8213,4.9562],[-3.8185,4.955],[-3.7815,4.955],[-3.7787,4.9562],[-3.7775,4.959],[-3.7775,5.041],[-3.7787,5.0438],[-3.7815,5.045],[-3.8185,5.045],[-3.8213,5.0438],[-3.8225,5.041]],height:[.75,2.4]},{name:"south facade glass.001",group:"03_walls",polygon:[[-1.65,4.984],[-.25,4.984],[-.25,5.016],[-1.65,5.016]],height:[0,2.5]},{name:"south facade frame.004",group:"03_walls",polygon:[[-1.6825,4.942],[-1.6804,4.9371],[-1.6755,4.935],[-1.6245,4.935],[-1.6196,4.9371],[-1.6175,4.942],[-1.6175,5.058],[-1.6196,5.0629],[-1.6245,5.065],[-1.6755,5.065],[-1.6804,5.0629],[-1.6825,5.058]],height:[-.05,2.55]},{name:"south facade frame.005",group:"03_walls",polygon:[[-.2825,4.942],[-.2804,4.9371],[-.2755,4.935],[-.2245,4.935],[-.2196,4.9371],[-.2175,4.942],[-.2175,5.058],[-.2196,5.0629],[-.2245,5.065],[-.2755,5.065],[-.2804,5.0629],[-.2825,5.058]],height:[-.05,2.55]},{name:"south facade mullion.002",group:"03_walls",polygon:[[-.9725,4.959],[-.9713,4.9562],[-.9685,4.955],[-.9315,4.955],[-.9287,4.9562],[-.9275,4.959],[-.9275,5.041],[-.9287,5.0438],[-.9315,5.045],[-.9685,5.045],[-.9713,5.0438],[-.9725,5.041]],height:[0,2.5]},{name:"south facade glass.002",group:"03_walls",polygon:[[.4,4.984],[6.5,4.984],[6.5,5.016],[.4,5.016]],height:[.05,2.55]},{name:"south facade frame.008",group:"03_walls",polygon:[[.3675,4.942],[.3696,4.9371],[.3745,4.935],[.4255,4.935],[.4304,4.9371],[.4325,4.942],[.4325,5.058],[.4304,5.0629],[.4255,5.065],[.3745,5.065],[.3696,5.0629],[.3675,5.058]],height:[0,2.6]},{name:"south facade frame.009",group:"03_walls",polygon:[[6.4675,4.942],[6.4696,4.9371],[6.4745,4.935],[6.5255,4.935],[6.5304,4.9371],[6.5325,4.942],[6.5325,5.058],[6.5304,5.0629],[6.5255,5.065],[6.4745,5.065],[6.4696,5.0629],[6.4675,5.058]],height:[0,2.6]},{name:"south facade mullion.003",group:"03_walls",polygon:[[1.5975,4.959],[1.5987,4.9562],[1.6015,4.955],[1.6385,4.955],[1.6413,4.9562],[1.6425,4.959],[1.6425,5.041],[1.6413,5.0438],[1.6385,5.045],[1.6015,5.045],[1.5987,5.0438],[1.5975,5.041]],height:[.05,2.55]},{name:"south facade mullion.004",group:"03_walls",polygon:[[2.8175,4.959],[2.8187,4.9562],[2.8215,4.955],[2.8585,4.955],[2.8613,4.9562],[2.8625,4.959],[2.8625,5.041],[2.8613,5.0438],[2.8585,5.045],[2.8215,5.045],[2.8187,5.0438],[2.8175,5.041]],height:[.05,2.55]},{name:"south facade mullion.005",group:"03_walls",polygon:[[4.0375,4.959],[4.0387,4.9562],[4.0415,4.955],[4.0785,4.955],[4.0813,4.9562],[4.0825,4.959],[4.0825,5.041],[4.0813,5.0438],[4.0785,5.045],[4.0415,5.045],[4.0387,5.0438],[4.0375,5.041]],height:[.05,2.55]},{name:"south facade mullion.006",group:"03_walls",polygon:[[5.2575,4.959],[5.2587,4.9562],[5.2615,4.955],[5.2985,4.955],[5.3013,4.9562],[5.3025,4.959],[5.3025,5.041],[5.3013,5.0438],[5.2985,5.045],[5.2615,5.045],[5.2587,5.0438],[5.2575,5.041]],height:[.05,2.55]},{name:"north facade",group:"03_walls",polygon:[[-7,-5.115],[-6.9956,-5.1256],[-6.985,-5.13],[-6.015,-5.13],[-6.0044,-5.1256],[-6,-5.115],[-6,-4.885],[-6.0044,-4.8744],[-6.015,-4.87],[-6.985,-4.87],[-6.9956,-4.8744],[-7,-4.885]],height:[0,3]},{name:"north facade.001",group:"03_walls",polygon:[[-6,-5.115],[-5.9956,-5.1256],[-5.985,-5.13],[-2.715,-5.13],[-2.7044,-5.1256],[-2.7,-5.115],[-2.7,-4.885],[-2.7044,-4.8744],[-2.715,-4.87],[-5.985,-4.87],[-5.9956,-4.8744],[-6,-4.885]],height:[0,.8]},{name:"north facade.003",group:"03_walls",polygon:[[-2.7,-5.115],[-2.6956,-5.1256],[-2.685,-5.13],[.435,-5.13],[.4456,-5.1256],[.45,-5.115],[.45,-4.885],[.4456,-4.8744],[.435,-4.87],[-2.685,-4.87],[-2.6956,-4.8744],[-2.7,-4.885]],height:[0,3]},{name:"north facade.004",group:"03_walls",polygon:[[.45,-5.115],[.4544,-5.1256],[.465,-5.13],[2.185,-5.13],[2.1956,-5.1256],[2.2,-5.115],[2.2,-4.885],[2.1956,-4.8744],[2.185,-4.87],[.465,-4.87],[.4544,-4.8744],[.45,-4.885]],height:[0,1.5]},{name:"north facade.006",group:"03_walls",polygon:[[2.2,-5.115],[2.2044,-5.1256],[2.215,-5.13],[4.885,-5.13],[4.8956,-5.1256],[4.9,-5.115],[4.9,-4.885],[4.8956,-4.8744],[4.885,-4.87],[2.215,-4.87],[2.2044,-4.8744],[2.2,-4.885]],height:[0,3]},{name:"north facade.007",group:"03_walls",polygon:[[4.9,-5.115],[4.9044,-5.1256],[4.915,-5.13],[6.485,-5.13],[6.4956,-5.1256],[6.5,-5.115],[6.5,-4.885],[6.4956,-4.8744],[6.485,-4.87],[4.915,-4.87],[4.9044,-4.8744],[4.9,-4.885]],height:[0,.8]},{name:"north facade.009",group:"03_walls",polygon:[[6.5,-5.115],[6.5044,-5.1256],[6.515,-5.13],[6.985,-5.13],[6.9956,-5.1256],[7,-5.115],[7,-4.885],[6.9956,-4.8744],[6.985,-4.87],[6.515,-4.87],[6.5044,-4.8744],[6.5,-4.885]],height:[0,3]},{name:"north facade glass",group:"03_walls",polygon:[[-6,-5.016],[-2.7,-5.016],[-2.7,-4.984],[-6,-4.984]],height:[.8,2.35]},{name:"north facade frame",group:"03_walls",polygon:[[-6.0325,-5.058],[-6.0304,-5.0629],[-6.0255,-5.065],[-5.9745,-5.065],[-5.9696,-5.0629],[-5.9675,-5.058],[-5.9675,-4.942],[-5.9696,-4.9371],[-5.9745,-4.935],[-6.0255,-4.935],[-6.0304,-4.9371],[-6.0325,-4.942]],height:[.75,2.4]},{name:"north facade frame.001",group:"03_walls",polygon:[[-2.7325,-5.058],[-2.7304,-5.0629],[-2.7255,-5.065],[-2.6745,-5.065],[-2.6696,-5.0629],[-2.6675,-5.058],[-2.6675,-4.942],[-2.6696,-4.9371],[-2.6745,-4.935],[-2.7255,-4.935],[-2.7304,-4.9371],[-2.7325,-4.942]],height:[.75,2.4]},{name:"north facade frame.002",group:"03_walls",polygon:[[-6.06,-5.058],[-6.0579,-5.0629],[-6.053,-5.065],[-2.647,-5.065],[-2.6421,-5.0629],[-2.64,-5.058],[-2.64,-4.942],[-2.6421,-4.9371],[-2.647,-4.935],[-6.053,-4.935],[-6.0579,-4.9371],[-6.06,-4.942]],height:[.7675,.8325]},{name:"north facade mullion",group:"03_walls",polygon:[[-4.9225,-5.041],[-4.9213,-5.0438],[-4.9185,-5.045],[-4.8815,-5.045],[-4.8787,-5.0438],[-4.8775,-5.041],[-4.8775,-4.959],[-4.8787,-4.9562],[-4.8815,-4.955],[-4.9185,-4.955],[-4.9213,-4.9562],[-4.9225,-4.959]],height:[.8,2.35]},{name:"north facade mullion.001",group:"03_walls",polygon:[[-3.8225,-5.041],[-3.8213,-5.0438],[-3.8185,-5.045],[-3.7815,-5.045],[-3.7787,-5.0438],[-3.7775,-5.041],[-3.7775,-4.959],[-3.7787,-4.9562],[-3.7815,-4.955],[-3.8185,-4.955],[-3.8213,-4.9562],[-3.8225,-4.959]],height:[.8,2.35]},{name:"north facade glass.001",group:"03_walls",polygon:[[.45,-5.016],[2.2,-5.016],[2.2,-4.984],[.45,-4.984]],height:[1.5,2.3]},{name:"north facade frame.004",group:"03_walls",polygon:[[.4175,-5.058],[.4196,-5.0629],[.4245,-5.065],[.4755,-5.065],[.4804,-5.0629],[.4825,-5.058],[.4825,-4.942],[.4804,-4.9371],[.4755,-4.935],[.4245,-4.935],[.4196,-4.9371],[.4175,-4.942]],height:[1.45,2.35]},{name:"north facade frame.005",group:"03_walls",polygon:[[2.1675,-5.058],[2.1696,-5.0629],[2.1745,-5.065],[2.2255,-5.065],[2.2304,-5.0629],[2.2325,-5.058],[2.2325,-4.942],[2.2304,-4.9371],[2.2255,-4.935],[2.1745,-4.935],[2.1696,-4.9371],[2.1675,-4.942]],height:[1.45,2.35]},{name:"north facade frame.006",group:"03_walls",polygon:[[.39,-5.058],[.3921,-5.0629],[.397,-5.065],[2.253,-5.065],[2.2579,-5.0629],[2.26,-5.058],[2.26,-4.942],[2.2579,-4.9371],[2.253,-4.935],[.397,-4.935],[.3921,-4.9371],[.39,-4.942]],height:[1.4675,1.5325]},{name:"north facade mullion.002",group:"03_walls",polygon:[[1.3025,-5.041],[1.3037,-5.0438],[1.3065,-5.045],[1.3435,-5.045],[1.3463,-5.0438],[1.3475,-5.041],[1.3475,-4.959],[1.3463,-4.9562],[1.3435,-4.955],[1.3065,-4.955],[1.3037,-4.9562],[1.3025,-4.959]],height:[1.5,2.3]},{name:"north facade glass.002",group:"03_walls",polygon:[[4.9,-5.016],[6.5,-5.016],[6.5,-4.984],[4.9,-4.984]],height:[.8,2.35]},{name:"north facade frame.008",group:"03_walls",polygon:[[4.8675,-5.058],[4.8696,-5.0629],[4.8745,-5.065],[4.9255,-5.065],[4.9304,-5.0629],[4.9325,-5.058],[4.9325,-4.942],[4.9304,-4.9371],[4.9255,-4.935],[4.8745,-4.935],[4.8696,-4.9371],[4.8675,-4.942]],height:[.75,2.4]},{name:"north facade frame.009",group:"03_walls",polygon:[[6.4675,-5.058],[6.4696,-5.0629],[6.4745,-5.065],[6.5255,-5.065],[6.5304,-5.0629],[6.5325,-5.058],[6.5325,-4.942],[6.5304,-4.9371],[6.5255,-4.935],[6.4745,-4.935],[6.4696,-4.9371],[6.4675,-4.942]],height:[.75,2.4]},{name:"north facade frame.010",group:"03_walls",polygon:[[4.84,-5.058],[4.8421,-5.0629],[4.847,-5.065],[6.553,-5.065],[6.5579,-5.0629],[6.56,-5.058],[6.56,-4.942],[6.5579,-4.9371],[6.553,-4.935],[4.847,-4.935],[4.8421,-4.9371],[4.84,-4.942]],height:[.7675,.8325]},{name:"north facade mullion.003",group:"03_walls",polygon:[[5.6775,-5.041],[5.6787,-5.0438],[5.6815,-5.045],[5.7185,-5.045],[5.7213,-5.0438],[5.7225,-5.041],[5.7225,-4.959],[5.7213,-4.9562],[5.7185,-4.955],[5.6815,-4.955],[5.6787,-4.9562],[5.6775,-4.959]],height:[.8,2.35]},{name:"west facade",group:"03_walls",polygon:[[-7.13,4.015],[-7.1256,4.0044],[-7.115,4],[-6.885,4],[-6.8744,4.0044],[-6.87,4.015],[-6.87,4.885],[-6.8744,4.8956],[-6.885,4.9],[-7.115,4.9],[-7.1256,4.8956],[-7.13,4.885]],height:[0,3]},{name:"west facade.001",group:"03_walls",polygon:[[-7.13,2.015],[-7.1256,2.0044],[-7.115,2],[-6.885,2],[-6.8744,2.0044],[-6.87,2.015],[-6.87,3.985],[-6.8744,3.9956],[-6.885,4],[-7.115,4],[-7.1256,3.9956],[-7.13,3.985]],height:[0,.8]},{name:"west facade.003",group:"03_walls",polygon:[[-7.13,.915],[-7.1256,.9044],[-7.115,.9],[-6.885,.9],[-6.8744,.9044],[-6.87,.915],[-6.87,1.985],[-6.8744,1.9956],[-6.885,2],[-7.115,2],[-7.1256,1.9956],[-7.13,1.985]],height:[0,3]},{name:"west facade.004",group:"03_walls",polygon:[[-7.13,-.885],[-7.1256,-.8956],[-7.115,-.9],[-6.885,-.9],[-6.8744,-.8956],[-6.87,-.885],[-6.87,.885],[-6.8744,.8956],[-6.885,.9],[-7.115,.9],[-7.1256,.8956],[-7.13,.885]],height:[0,.8]},{name:"west facade.006",group:"03_walls",polygon:[[-7.13,-1.985],[-7.1256,-1.9956],[-7.115,-2],[-6.885,-2],[-6.8744,-1.9956],[-6.87,-1.985],[-6.87,-.915],[-6.8744,-.9044],[-6.885,-.9],[-7.115,-.9],[-7.1256,-.9044],[-7.13,-.915]],height:[0,3]},{name:"west facade.007",group:"03_walls",polygon:[[-7.13,-3.985],[-7.1256,-3.9956],[-7.115,-4],[-6.885,-4],[-6.8744,-3.9956],[-6.87,-3.985],[-6.87,-2.015],[-6.8744,-2.0044],[-6.885,-2],[-7.115,-2],[-7.1256,-2.0044],[-7.13,-2.015]],height:[0,.8]},{name:"west facade.009",group:"03_walls",polygon:[[-7.13,-4.885],[-7.1256,-4.8956],[-7.115,-4.9],[-6.885,-4.9],[-6.8744,-4.8956],[-6.87,-4.885],[-6.87,-4.015],[-6.8744,-4.0044],[-6.885,-4],[-7.115,-4],[-7.1256,-4.0044],[-7.13,-4.015]],height:[0,3]},{name:"west facade glass",group:"03_walls",polygon:[[-7.016,2],[-6.984,2],[-6.984,4],[-7.016,4]],height:[.8,2.35]},{name:"west facade frame",group:"03_walls",polygon:[[-7.065,3.9745],[-7.0629,3.9696],[-7.058,3.9675],[-6.942,3.9675],[-6.9371,3.9696],[-6.935,3.9745],[-6.935,4.0255],[-6.9371,4.0304],[-6.942,4.0325],[-7.058,4.0325],[-7.0629,4.0304],[-7.065,4.0255]],height:[.75,2.4]},{name:"west facade frame.001",group:"03_walls",polygon:[[-7.065,1.9745],[-7.0629,1.9696],[-7.058,1.9675],[-6.942,1.9675],[-6.9371,1.9696],[-6.935,1.9745],[-6.935,2.0255],[-6.9371,2.0304],[-6.942,2.0325],[-7.058,2.0325],[-7.0629,2.0304],[-7.065,2.0255]],height:[.75,2.4]},{name:"west facade frame.002",group:"03_walls",polygon:[[-7.065,1.947],[-7.0629,1.9421],[-7.058,1.94],[-6.942,1.94],[-6.9371,1.9421],[-6.935,1.947],[-6.935,4.053],[-6.9371,4.0579],[-6.942,4.06],[-7.058,4.06],[-7.0629,4.0579],[-7.065,4.053]],height:[.7675,.8325]},{name:"west facade mullion",group:"03_walls",polygon:[[-7.045,2.9815],[-7.0438,2.9787],[-7.041,2.9775],[-6.959,2.9775],[-6.9562,2.9787],[-6.955,2.9815],[-6.955,3.0185],[-6.9562,3.0213],[-6.959,3.0225],[-7.041,3.0225],[-7.0438,3.0213],[-7.045,3.0185]],height:[.8,2.35]},{name:"west facade glass.001",group:"03_walls",polygon:[[-7.016,-.9],[-6.984,-.9],[-6.984,.9],[-7.016,.9]],height:[.8,2.35]},{name:"west facade frame.004",group:"03_walls",polygon:[[-7.065,.8745],[-7.0629,.8696],[-7.058,.8675],[-6.942,.8675],[-6.9371,.8696],[-6.935,.8745],[-6.935,.9255],[-6.9371,.9304],[-6.942,.9325],[-7.058,.9325],[-7.0629,.9304],[-7.065,.9255]],height:[.75,2.4]},{name:"west facade frame.005",group:"03_walls",polygon:[[-7.065,-.9255],[-7.0629,-.9304],[-7.058,-.9325],[-6.942,-.9325],[-6.9371,-.9304],[-6.935,-.9255],[-6.935,-.8745],[-6.9371,-.8696],[-6.942,-.8675],[-7.058,-.8675],[-7.0629,-.8696],[-7.065,-.8745]],height:[.75,2.4]},{name:"west facade frame.006",group:"03_walls",polygon:[[-7.065,-.953],[-7.0629,-.9579],[-7.058,-.96],[-6.942,-.96],[-6.9371,-.9579],[-6.935,-.953],[-6.935,.953],[-6.9371,.9579],[-6.942,.96],[-7.058,.96],[-7.0629,.9579],[-7.065,.953]],height:[.7675,.8325]},{name:"west facade mullion.001",group:"03_walls",polygon:[[-7.045,-.0185],[-7.0438,-.0213],[-7.041,-.0225],[-6.959,-.0225],[-6.9562,-.0213],[-6.955,-.0185],[-6.955,.0185],[-6.9562,.0213],[-6.959,.0225],[-7.041,.0225],[-7.0438,.0213],[-7.045,.0185]],height:[.8,2.35]},{name:"west facade glass.002",group:"03_walls",polygon:[[-7.016,-4],[-6.984,-4],[-6.984,-2],[-7.016,-2]],height:[.8,2.35]},{name:"west facade frame.008",group:"03_walls",polygon:[[-7.065,-2.0255],[-7.0629,-2.0304],[-7.058,-2.0325],[-6.942,-2.0325],[-6.9371,-2.0304],[-6.935,-2.0255],[-6.935,-1.9745],[-6.9371,-1.9696],[-6.942,-1.9675],[-7.058,-1.9675],[-7.0629,-1.9696],[-7.065,-1.9745]],height:[.75,2.4]},{name:"west facade frame.009",group:"03_walls",polygon:[[-7.065,-4.0255],[-7.0629,-4.0304],[-7.058,-4.0325],[-6.942,-4.0325],[-6.9371,-4.0304],[-6.935,-4.0255],[-6.935,-3.9745],[-6.9371,-3.9696],[-6.942,-3.9675],[-7.058,-3.9675],[-7.0629,-3.9696],[-7.065,-3.9745]],height:[.75,2.4]},{name:"west facade frame.010",group:"03_walls",polygon:[[-7.065,-4.053],[-7.0629,-4.0579],[-7.058,-4.06],[-6.942,-4.06],[-6.9371,-4.0579],[-6.935,-4.053],[-6.935,-1.947],[-6.9371,-1.9421],[-6.942,-1.94],[-7.058,-1.94],[-7.0629,-1.9421],[-7.065,-1.947]],height:[.7675,.8325]},{name:"west facade mullion.002",group:"03_walls",polygon:[[-7.045,-3.0185],[-7.0438,-3.0213],[-7.041,-3.0225],[-6.959,-3.0225],[-6.9562,-3.0213],[-6.955,-3.0185],[-6.955,-2.9815],[-6.9562,-2.9787],[-6.959,-2.9775],[-7.041,-2.9775],[-7.0438,-2.9787],[-7.045,-2.9815]],height:[.8,2.35]},{name:"east facade",group:"03_walls",polygon:[[6.87,4.115],[6.8744,4.1044],[6.885,4.1],[7.115,4.1],[7.1256,4.1044],[7.13,4.115],[7.13,4.885],[7.1256,4.8956],[7.115,4.9],[6.885,4.9],[6.8744,4.8956],[6.87,4.885]],height:[0,3]},{name:"east facade.004",group:"03_walls",polygon:[[6.87,-3.985],[6.8744,-3.9956],[6.885,-4],[7.115,-4],[7.1256,-3.9956],[7.13,-3.985],[7.13,-2.115],[7.1256,-2.1044],[7.115,-2.1],[6.885,-2.1],[6.8744,-2.1044],[6.87,-2.115]],height:[0,.8]},{name:"east facade.006",group:"03_walls",polygon:[[6.87,-4.885],[6.8744,-4.8956],[6.885,-4.9],[7.115,-4.9],[7.1256,-4.8956],[7.13,-4.885],[7.13,-4.015],[7.1256,-4.0044],[7.115,-4],[6.885,-4],[6.8744,-4.0044],[6.87,-4.015]],height:[0,3]},{name:"east facade glass",group:"03_walls",polygon:[[6.984,-.6],[7.016,-.6],[7.016,4.1],[6.984,4.1]],height:[.05,2.55]},{name:"east facade frame",group:"03_walls",polygon:[[6.935,4.0745],[6.9371,4.0696],[6.942,4.0675],[7.058,4.0675],[7.0629,4.0696],[7.065,4.0745],[7.065,4.1255],[7.0629,4.1304],[7.058,4.1325],[6.942,4.1325],[6.9371,4.1304],[6.935,4.1255]],height:[0,2.6]},{name:"east facade frame.001",group:"03_walls",polygon:[[6.935,-.6255],[6.9371,-.6304],[6.942,-.6325],[7.058,-.6325],[7.0629,-.6304],[7.065,-.6255],[7.065,-.5745],[7.0629,-.5696],[7.058,-.5675],[6.942,-.5675],[6.9371,-.5696],[6.935,-.5745]],height:[0,2.6]},{name:"east facade mullion",group:"03_walls",polygon:[[6.955,2.9065],[6.9562,2.9037],[6.959,2.9025],[7.041,2.9025],[7.0438,2.9037],[7.045,2.9065],[7.045,2.9435],[7.0438,2.9463],[7.041,2.9475],[6.959,2.9475],[6.9562,2.9463],[6.955,2.9435]],height:[.05,2.55]},{name:"east facade mullion.001",group:"03_walls",polygon:[[6.955,1.7315],[6.9562,1.7287],[6.959,1.7275],[7.041,1.7275],[7.0438,1.7287],[7.045,1.7315],[7.045,1.7685],[7.0438,1.7713],[7.041,1.7725],[6.959,1.7725],[6.9562,1.7713],[6.955,1.7685]],height:[.05,2.55]},{name:"east facade mullion.002",group:"03_walls",polygon:[[6.955,.5565],[6.9562,.5537],[6.959,.5525],[7.041,.5525],[7.0438,.5537],[7.045,.5565],[7.045,.5935],[7.0438,.5963],[7.041,.5975],[6.959,.5975],[6.9562,.5963],[6.955,.5935]],height:[.05,2.55]},{name:"east facade glass.001",group:"03_walls",polygon:[[6.984,-4],[7.016,-4],[7.016,-2.1],[6.984,-2.1]],height:[.8,2.35]},{name:"east facade frame.004",group:"03_walls",polygon:[[6.935,-2.1255],[6.9371,-2.1304],[6.942,-2.1325],[7.058,-2.1325],[7.0629,-2.1304],[7.065,-2.1255],[7.065,-2.0745],[7.0629,-2.0696],[7.058,-2.0675],[6.942,-2.0675],[6.9371,-2.0696],[6.935,-2.0745]],height:[.75,2.4]},{name:"east facade frame.005",group:"03_walls",polygon:[[6.935,-4.0255],[6.9371,-4.0304],[6.942,-4.0325],[7.058,-4.0325],[7.0629,-4.0304],[7.065,-4.0255],[7.065,-3.9745],[7.0629,-3.9696],[7.058,-3.9675],[6.942,-3.9675],[6.9371,-3.9696],[6.935,-3.9745]],height:[.75,2.4]},{name:"east facade frame.006",group:"03_walls",polygon:[[6.935,-4.053],[6.9371,-4.0579],[6.942,-4.06],[7.058,-4.06],[7.0629,-4.0579],[7.065,-4.053],[7.065,-2.047],[7.0629,-2.0421],[7.058,-2.04],[6.942,-2.04],[6.9371,-2.0421],[6.935,-2.047]],height:[.7675,.8325]},{name:"east facade mullion.003",group:"03_walls",polygon:[[6.955,-3.0685],[6.9562,-3.0713],[6.959,-3.0725],[7.041,-3.0725],[7.0438,-3.0713],[7.045,-3.0685],[7.045,-3.0315],[7.0438,-3.0287],[7.041,-3.0275],[6.959,-3.0275],[6.9562,-3.0287],[6.955,-3.0315]],height:[.8,2.35]},{name:"interior partition",group:"03_walls",polygon:[[-1.865,3.515],[-1.8606,3.5044],[-1.85,3.5],[-1.75,3.5],[-1.7394,3.5044],[-1.735,3.515],[-1.735,4.835],[-1.7394,4.8456],[-1.75,4.85],[-1.85,4.85],[-1.8606,4.8456],[-1.865,4.835]],height:[0,2.8]},{name:"interior partition.001",group:"03_walls",polygon:[[-1.865,1.565],[-1.8606,1.5544],[-1.85,1.55],[-1.75,1.55],[-1.7394,1.5544],[-1.735,1.565],[-1.735,2.485],[-1.7394,2.4956],[-1.75,2.5],[-1.85,2.5],[-1.8606,2.4956],[-1.865,2.485]],height:[0,2.8]},{name:"door leaf",group:"03_walls",polygon:[[-2.4441,3.6808],[-2.4383,3.6709],[-1.889,3.2533],[-1.8779,3.2504],[-1.8679,3.2562],[-1.8589,3.2681],[-1.8559,3.2792],[-1.8617,3.2891],[-2.411,3.7067],[-2.4221,3.7096],[-2.4321,3.7038],[-2.4411,3.6919]],height:[0,2.2]},{name:"interior partition.002",group:"03_walls",polygon:[[-1.865,.515],[-1.8606,.5044],[-1.85,.5],[-1.75,.5],[-1.7394,.5044],[-1.735,.515],[-1.735,1.535],[-1.7394,1.5456],[-1.75,1.55],[-1.85,1.55],[-1.8606,1.5456],[-1.865,1.535]],height:[0,2.8]},{name:"interior partition.003",group:"03_walls",polygon:[[-1.865,-1.535],[-1.8606,-1.5456],[-1.85,-1.55],[-1.75,-1.55],[-1.7394,-1.5456],[-1.735,-1.535],[-1.735,-.515],[-1.7394,-.5044],[-1.75,-.5],[-1.85,-.5],[-1.8606,-.5044],[-1.865,-.515]],height:[0,2.8]},{name:"door leaf.001",group:"03_walls",polygon:[[-2.4441,.6808],[-2.4383,.6709],[-1.889,.2533],[-1.8779,.2504],[-1.8679,.2562],[-1.8589,.2681],[-1.8559,.2792],[-1.8617,.2891],[-2.411,.7067],[-2.4221,.7096],[-2.4321,.7038],[-2.4411,.6919]],height:[0,2.2]},{name:"interior partition.004",group:"03_walls",polygon:[[-1.865,-2.485],[-1.8606,-2.4956],[-1.85,-2.5],[-1.75,-2.5],[-1.7394,-2.4956],[-1.735,-2.485],[-1.735,-1.565],[-1.7394,-1.5544],[-1.75,-1.55],[-1.85,-1.55],[-1.8606,-1.5544],[-1.865,-1.565]],height:[0,2.8]},{name:"interior partition.005",group:"03_walls",polygon:[[-1.865,-4.835],[-1.8606,-4.8456],[-1.85,-4.85],[-1.75,-4.85],[-1.7394,-4.8456],[-1.735,-4.835],[-1.735,-3.515],[-1.7394,-3.5044],[-1.75,-3.5],[-1.85,-3.5],[-1.8606,-3.5044],[-1.865,-3.515]],height:[0,2.8]},{name:"door leaf.002",group:"03_walls",polygon:[[-2.4441,-2.3192],[-2.4383,-2.3291],[-1.889,-2.7467],[-1.8779,-2.7496],[-1.8679,-2.7438],[-1.8589,-2.7319],[-1.8559,-2.7208],[-1.8617,-2.7109],[-2.411,-2.2933],[-2.4221,-2.2904],[-2.4321,-2.2962],[-2.4411,-2.3081]],height:[0,2.2]},{name:"bedroom divider",group:"03_walls",polygon:[[-6.9,1.5],[-6.8956,1.4894],[-6.885,1.485],[-1.915,1.485],[-1.9044,1.4894],[-1.9,1.5],[-1.9,1.6],[-1.9044,1.6106],[-1.915,1.615],[-6.885,1.615],[-6.8956,1.6106],[-6.9,1.6]],height:[0,2.8]},{name:"bedroom divider.001",group:"03_walls",polygon:[[-6.9,-1.6],[-6.8956,-1.6106],[-6.885,-1.615],[-1.915,-1.615],[-1.9044,-1.6106],[-1.9,-1.6],[-1.9,-1.5],[-1.9044,-1.4894],[-1.915,-1.485],[-6.885,-1.485],[-6.8956,-1.4894],[-6.9,-1.5]],height:[0,2.8]},{name:"service room divider",group:"03_walls",polygon:[[2.535,-4.935],[2.5394,-4.9456],[2.55,-4.95],[2.65,-4.95],[2.6606,-4.9456],[2.665,-4.935],[2.665,-1.265],[2.6606,-1.2544],[2.65,-1.25],[2.55,-1.25],[2.5394,-1.2544],[2.535,-1.265]],height:[0,2.8]},{name:"service room divider.001",group:"03_walls",polygon:[[4.535,-4.935],[4.5394,-4.9456],[4.55,-4.95],[4.65,-4.95],[4.6606,-4.9456],[4.665,-4.935],[4.665,-1.265],[4.6606,-1.2544],[4.65,-1.25],[4.55,-1.25],[4.5394,-1.2544],[4.535,-1.265]],height:[0,2.8]},{name:"service partition",group:"03_walls",polygon:[[0,-1.35],[.0044,-1.3606],[.015,-1.365],[.855,-1.365],[.8656,-1.3606],[.87,-1.35],[.87,-1.25],[.8656,-1.2394],[.855,-1.235],[.015,-1.235],[.0044,-1.2394],[0,-1.25]],height:[0,2.8]},{name:"service partition.001",group:"03_walls",polygon:[[1.73,-1.35],[1.7344,-1.3606],[1.745,-1.365],[2.585,-1.365],[2.5956,-1.3606],[2.6,-1.35],[2.6,-1.25],[2.5956,-1.2394],[2.585,-1.235],[1.745,-1.235],[1.7344,-1.2394],[1.73,-1.25]],height:[0,2.8]},{name:"service partition.002",group:"03_walls",polygon:[[2.6,-1.35],[2.6044,-1.3606],[2.615,-1.365],[3.155,-1.365],[3.1656,-1.3606],[3.17,-1.35],[3.17,-1.25],[3.1656,-1.2394],[3.155,-1.235],[2.615,-1.235],[2.6044,-1.2394],[2.6,-1.25]],height:[0,2.8]},{name:"service partition.003",group:"03_walls",polygon:[[4.03,-1.35],[4.0344,-1.3606],[4.045,-1.365],[4.585,-1.365],[4.5956,-1.3606],[4.6,-1.35],[4.6,-1.25],[4.5956,-1.2394],[4.585,-1.235],[4.045,-1.235],[4.0344,-1.2394],[4.03,-1.25]],height:[0,2.8]},{name:"service partition.004",group:"03_walls",polygon:[[4.6,-1.35],[4.6044,-1.3606],[4.615,-1.365],[5.28,-1.365],[5.2906,-1.3606],[5.295,-1.35],[5.295,-1.25],[5.2906,-1.2394],[5.28,-1.235],[4.615,-1.235],[4.6044,-1.2394],[4.6,-1.25]],height:[0,2.8]},{name:"service partition.005",group:"03_walls",polygon:[[6.155,-1.35],[6.1594,-1.3606],[6.17,-1.365],[6.835,-1.365],[6.8456,-1.3606],[6.85,-1.35],[6.85,-1.25],[6.8456,-1.2394],[6.835,-1.235],[6.17,-1.235],[6.1594,-1.2394],[6.155,-1.25]],height:[0,2.8]},{name:"bed base",group:"07_interior",polygon:[[-6.3,2.17],[-6.2868,2.1382],[-6.255,2.125],[-4.745,2.125],[-4.7132,2.1382],[-4.7,2.17],[-4.7,4.13],[-4.7132,4.1618],[-4.745,4.175],[-6.255,4.175],[-6.2868,4.1618],[-6.3,4.13]],height:[.07,.39]},{name:"mattress",group:"07_interior",polygon:[[-6.3,2.24],[-6.2736,2.1764],[-6.21,2.15],[-4.79,2.15],[-4.7264,2.1764],[-4.7,2.24],[-4.7,4.06],[-4.7264,4.1236],[-4.79,4.15],[-6.21,4.15],[-6.2736,4.1236],[-6.3,4.06]],height:[.365,.595]},{name:"duvet",group:"07_interior",polygon:[[-6.315,2.69],[-6.2945,2.6405],[-6.245,2.62],[-4.755,2.62],[-4.7055,2.6405],[-4.685,2.69],[-4.685,4.05],[-4.7055,4.0995],[-4.755,4.12],[-6.245,4.12],[-6.2945,4.0995],[-6.315,4.05]],height:[.55,.69]},{name:"headboard",group:"07_interior",polygon:[[-6.375,2.095],[-6.3677,2.0773],[-6.35,2.07],[-4.65,2.07],[-4.6323,2.0773],[-4.625,2.095],[-4.625,2.145],[-4.6323,2.1627],[-4.65,2.17],[-6.35,2.17],[-6.3677,2.1627],[-6.375,2.145]],height:[.2,1.2]},{name:"pillow",group:"07_interior",polygon:[[-6.244,2.35],[-6.2264,2.3076],[-6.184,2.29],[-5.616,2.29],[-5.5736,2.3076],[-5.556,2.35],[-5.556,2.65],[-5.5736,2.6924],[-5.616,2.71],[-6.184,2.71],[-6.2264,2.6924],[-6.244,2.65]],height:[.595,.745]},{name:"pillow.001",group:"07_interior",polygon:[[-5.444,2.35],[-5.4264,2.3076],[-5.384,2.29],[-4.816,2.29],[-4.7736,2.3076],[-4.756,2.35],[-4.756,2.65],[-4.7736,2.6924],[-4.816,2.71],[-5.384,2.71],[-5.4264,2.6924],[-5.444,2.65]],height:[.595,.745]},{name:"bedside",group:"07_interior",polygon:[[-4.525,2.255],[-4.5162,2.2338],[-4.495,2.225],[-4.105,2.225],[-4.0838,2.2338],[-4.075,2.255],[-4.075,2.645],[-4.0838,2.6662],[-4.105,2.675],[-4.495,2.675],[-4.5162,2.6662],[-4.525,2.645]],height:[0,.5]},{name:"bed base.001",group:"07_interior",polygon:[[-6,-.98],[-5.9868,-1.0118],[-5.955,-1.025],[-5.045,-1.025],[-5.0132,-1.0118],[-5,-.98],[-5,.98],[-5.0132,1.0118],[-5.045,1.025],[-5.955,1.025],[-5.9868,1.0118],[-6,.98]],height:[.07,.39]},{name:"mattress.001",group:"07_interior",polygon:[[-6,-.91],[-5.9736,-.9736],[-5.91,-1],[-5.09,-1],[-5.0264,-.9736],[-5,-.91],[-5,.91],[-5.0264,.9736],[-5.09,1],[-5.91,1],[-5.9736,.9736],[-6,.91]],height:[.365,.595]},{name:"duvet.001",group:"07_interior",polygon:[[-6.015,-.46],[-5.9945,-.5095],[-5.945,-.53],[-5.055,-.53],[-5.0055,-.5095],[-4.985,-.46],[-4.985,.9],[-5.0055,.9495],[-5.055,.97],[-5.945,.97],[-5.9945,.9495],[-6.015,.9]],height:[.55,.69]},{name:"headboard.001",group:"07_interior",polygon:[[-6.075,-1.055],[-6.0677,-1.0727],[-6.05,-1.08],[-4.95,-1.08],[-4.9323,-1.0727],[-4.925,-1.055],[-4.925,-1.005],[-4.9323,-.9873],[-4.95,-.98],[-6.05,-.98],[-6.0677,-.9873],[-6.075,-1.005]],height:[.2,1.2]},{name:"pillow.002",group:"07_interior",polygon:[[-5.965,-.8],[-5.9474,-.8424],[-5.905,-.86],[-5.595,-.86],[-5.5526,-.8424],[-5.535,-.8],[-5.535,-.5],[-5.5526,-.4576],[-5.595,-.44],[-5.905,-.44],[-5.9474,-.4576],[-5.965,-.5]],height:[.595,.745]},{name:"pillow.003",group:"07_interior",polygon:[[-5.465,-.8],[-5.4474,-.8424],[-5.405,-.86],[-5.095,-.86],[-5.0526,-.8424],[-5.035,-.8],[-5.035,-.5],[-5.0526,-.4576],[-5.095,-.44],[-5.405,-.44],[-5.4474,-.4576],[-5.465,-.5]],height:[.595,.745]},{name:"bedside.001",group:"07_interior",polygon:[[-4.525,-.895],[-4.5162,-.9162],[-4.495,-.925],[-4.105,-.925],[-4.0838,-.9162],[-4.075,-.895],[-4.075,-.505],[-4.0838,-.4838],[-4.105,-.475],[-4.495,-.475],[-4.5162,-.4838],[-4.525,-.505]],height:[0,.5]},{name:"bed base.002",group:"07_interior",polygon:[[-6.3,-4.08],[-6.2868,-4.1118],[-6.255,-4.125],[-4.745,-4.125],[-4.7132,-4.1118],[-4.7,-4.08],[-4.7,-2.12],[-4.7132,-2.0882],[-4.745,-2.075],[-6.255,-2.075],[-6.2868,-2.0882],[-6.3,-2.12]],height:[.07,.39]},{name:"mattress.002",group:"07_interior",polygon:[[-6.3,-4.01],[-6.2736,-4.0736],[-6.21,-4.1],[-4.79,-4.1],[-4.7264,-4.0736],[-4.7,-4.01],[-4.7,-2.19],[-4.7264,-2.1264],[-4.79,-2.1],[-6.21,-2.1],[-6.2736,-2.1264],[-6.3,-2.19]],height:[.365,.595]},{name:"duvet.002",group:"07_interior",polygon:[[-6.315,-3.56],[-6.2945,-3.6095],[-6.245,-3.63],[-4.755,-3.63],[-4.7055,-3.6095],[-4.685,-3.56],[-4.685,-2.2],[-4.7055,-2.1505],[-4.755,-2.13],[-6.245,-2.13],[-6.2945,-2.1505],[-6.315,-2.2]],height:[.55,.69]},{name:"headboard.002",group:"07_interior",polygon:[[-6.375,-4.155],[-6.3677,-4.1727],[-6.35,-4.18],[-4.65,-4.18],[-4.6323,-4.1727],[-4.625,-4.155],[-4.625,-4.105],[-4.6323,-4.0873],[-4.65,-4.08],[-6.35,-4.08],[-6.3677,-4.0873],[-6.375,-4.105]],height:[.2,1.2]},{name:"pillow.004",group:"07_interior",polygon:[[-6.244,-3.9],[-6.2264,-3.9424],[-6.184,-3.96],[-5.616,-3.96],[-5.5736,-3.9424],[-5.556,-3.9],[-5.556,-3.6],[-5.5736,-3.5576],[-5.616,-3.54],[-6.184,-3.54],[-6.2264,-3.5576],[-6.244,-3.6]],height:[.595,.745]},{name:"pillow.005",group:"07_interior",polygon:[[-5.444,-3.9],[-5.4264,-3.9424],[-5.384,-3.96],[-4.816,-3.96],[-4.7736,-3.9424],[-4.756,-3.9],[-4.756,-3.6],[-4.7736,-3.5576],[-4.816,-3.54],[-5.384,-3.54],[-5.4264,-3.5576],[-5.444,-3.6]],height:[.595,.745]},{name:"bedside.002",group:"07_interior",polygon:[[-4.525,-3.995],[-4.5162,-4.0162],[-4.495,-4.025],[-4.105,-4.025],[-4.0838,-4.0162],[-4.075,-3.995],[-4.075,-3.605],[-4.0838,-3.5838],[-4.105,-3.575],[-4.495,-3.575],[-4.5162,-3.5838],[-4.525,-3.605]],height:[0,.5]},{name:"wardrobe",group:"07_interior",polygon:[[-3.6,1.695],[-3.5941,1.6809],[-3.58,1.675],[-2.42,1.675],[-2.4059,1.6809],[-2.4,1.695],[-2.4,2.105],[-2.4059,2.1191],[-2.42,2.125],[-3.58,2.125],[-3.5941,2.1191],[-3.6,2.105]],height:[0,1.96]},{name:"wardrobe.001",group:"07_interior",polygon:[[-3.6,-1.405],[-3.5941,-1.4191],[-3.58,-1.425],[-2.42,-1.425],[-2.4059,-1.4191],[-2.4,-1.405],[-2.4,-.995],[-2.4059,-.9809],[-2.42,-.975],[-3.58,-.975],[-3.5941,-.9809],[-3.6,-.995]],height:[0,1.96]},{name:"wardrobe.002",group:"07_interior",polygon:[[-3.6,-4.755],[-3.5941,-4.7691],[-3.58,-4.775],[-2.42,-4.775],[-2.4059,-4.7691],[-2.4,-4.755],[-2.4,-4.345],[-2.4059,-4.3309],[-2.42,-4.325],[-3.58,-4.325],[-3.5941,-4.3309],[-3.6,-4.345]],height:[0,1.96]},{name:"sofa base",group:"07_interior",polygon:[[3.45,3.105],[3.4851,3.0201],[3.57,2.985],[6.03,2.985],[6.1149,3.0201],[6.15,3.105],[6.15,3.895],[6.1149,3.9799],[6.03,4.015],[3.57,4.015],[3.4851,3.9799],[3.45,3.895]],height:[.125,.575]},{name:"sofa back",group:"07_interior",polygon:[[3.45,3.02],[3.4764,2.9564],[3.54,2.93],[6.06,2.93],[6.1236,2.9564],[6.15,3.02],[6.15,3.06],[6.1236,3.1236],[6.06,3.15],[3.54,3.15],[3.4764,3.1236],[3.45,3.06]],height:[.325,1.175]},{name:"sofa arm",group:"07_interior",polygon:[[3.445,3.065],[3.4684,3.0084],[3.525,2.985],[3.575,2.985],[3.6316,3.0084],[3.655,3.065],[3.655,3.935],[3.6316,3.9916],[3.575,4.015],[3.525,4.015],[3.4684,3.9916],[3.445,3.935]],height:[.325,.955]},{name:"sofa arm.001",group:"07_interior",polygon:[[5.945,3.065],[5.9684,3.0084],[6.025,2.985],[6.075,2.985],[6.1316,3.0084],[6.155,3.065],[6.155,3.935],[6.1316,3.9916],[6.075,4.015],[6.025,4.015],[5.9684,3.9916],[5.945,3.935]],height:[.325,.955]},{name:"sofa cushion",group:"07_interior",polygon:[[3.625,3.215],[3.6484,3.1584],[3.705,3.135],[4.295,3.135],[4.3516,3.1584],[4.375,3.215],[4.375,3.885],[4.3516,3.9416],[4.295,3.965],[3.705,3.965],[3.6484,3.9416],[3.625,3.885]],height:[.53,.69]},{name:"sofa cushion.001",group:"07_interior",polygon:[[4.425,3.215],[4.4484,3.1584],[4.505,3.135],[5.095,3.135],[5.1516,3.1584],[5.175,3.215],[5.175,3.885],[5.1516,3.9416],[5.095,3.965],[4.505,3.965],[4.4484,3.9416],[4.425,3.885]],height:[.53,.69]},{name:"sofa cushion.002",group:"07_interior",polygon:[[5.225,3.215],[5.2484,3.1584],[5.305,3.135],[5.895,3.135],[5.9516,3.1584],[5.975,3.215],[5.975,3.885],[5.9516,3.9416],[5.895,3.965],[5.305,3.965],[5.2484,3.9416],[5.225,3.885]],height:[.53,.69]},{name:"coffee table",group:"07_interior",polygon:[[4.14,2.35],[4.1674,2.177],[4.247,2.0208],[4.3708,1.897],[4.527,1.8174],[4.7,1.79],[4.873,1.8174],[5.0292,1.897],[5.153,2.0208],[5.2326,2.177],[5.26,2.35],[5.2326,2.523],[5.153,2.6792],[5.0292,2.803],[4.873,2.8826],[4.7,2.91],[4.527,2.8826],[4.3708,2.803],[4.247,2.6792],[4.1674,2.523]],height:[.365,.435]},{name:"table foot",group:"07_interior",polygon:[[4.57,2.35],[4.5764,2.3098],[4.5948,2.2736],[4.6236,2.2448],[4.6598,2.2264],[4.7,2.22],[4.7402,2.2264],[4.7764,2.2448],[4.8052,2.2736],[4.8236,2.3098],[4.83,2.35],[4.8236,2.3902],[4.8052,2.4264],[4.7764,2.4552],[4.7402,2.4736],[4.7,2.48],[4.6598,2.4736],[4.6236,2.4552],[4.5948,2.4264],[4.5764,2.3902]],height:[0,.4]},{name:"kitchen cabinet",group:"07_interior",polygon:[[.31,-1.175],[.3144,-1.1856],[.325,-1.19],[.875,-1.19],[.8856,-1.1856],[.89,-1.175],[.89,-.585],[.8856,-.5744],[.875,-.57],[.325,-.57],[.3144,-.5744],[.31,-.585]],height:[.03,.93]},{name:"countertop",group:"07_interior",polygon:[[.3,-1.2],[.3029,-1.2071],[.31,-1.21],[.89,-1.21],[.8971,-1.2071],[.9,-1.2],[.9,-.56],[.8971,-.5529],[.89,-.55],[.31,-.55],[.3029,-.5529],[.3,-.56]],height:[.935,.985]},{name:"kitchen cabinet.001",group:"07_interior",polygon:[[.91,-1.175],[.9144,-1.1856],[.925,-1.19],[1.475,-1.19],[1.4856,-1.1856],[1.49,-1.175],[1.49,-.585],[1.4856,-.5744],[1.475,-.57],[.925,-.57],[.9144,-.5744],[.91,-.585]],height:[.03,.93]},{name:"countertop.001",group:"07_interior",polygon:[[.9,-1.2],[.9029,-1.2071],[.91,-1.21],[1.49,-1.21],[1.4971,-1.2071],[1.5,-1.2],[1.5,-.56],[1.4971,-.5529],[1.49,-.55],[.91,-.55],[.9029,-.5529],[.9,-.56]],height:[.935,.985]},{name:"kitchen cabinet.002",group:"07_interior",polygon:[[1.51,-1.175],[1.5144,-1.1856],[1.525,-1.19],[2.075,-1.19],[2.0856,-1.1856],[2.09,-1.175],[2.09,-.585],[2.0856,-.5744],[2.075,-.57],[1.525,-.57],[1.5144,-.5744],[1.51,-.585]],height:[.03,.93]},{name:"countertop.002",group:"07_interior",polygon:[[1.5,-1.2],[1.5029,-1.2071],[1.51,-1.21],[2.09,-1.21],[2.0971,-1.2071],[2.1,-1.2],[2.1,-.56],[2.0971,-.5529],[2.09,-.55],[1.51,-.55],[1.5029,-.5529],[1.5,-.56]],height:[.935,.985]},{name:"kitchen cabinet.003",group:"07_interior",polygon:[[2.11,-1.175],[2.1144,-1.1856],[2.125,-1.19],[2.675,-1.19],[2.6856,-1.1856],[2.69,-1.175],[2.69,-.585],[2.6856,-.5744],[2.675,-.57],[2.125,-.57],[2.1144,-.5744],[2.11,-.585]],height:[.03,.93]},{name:"countertop.003",group:"07_interior",polygon:[[2.1,-1.2],[2.1029,-1.2071],[2.11,-1.21],[2.69,-1.21],[2.6971,-1.2071],[2.7,-1.2],[2.7,-.56],[2.6971,-.5529],[2.69,-.55],[2.11,-.55],[2.1029,-.5529],[2.1,-.56]],height:[.935,.985]},{name:"kitchen cabinet.004",group:"07_interior",polygon:[[2.71,-1.175],[2.7144,-1.1856],[2.725,-1.19],[3.275,-1.19],[3.2856,-1.1856],[3.29,-1.175],[3.29,-.585],[3.2856,-.5744],[3.275,-.57],[2.725,-.57],[2.7144,-.5744],[2.71,-.585]],height:[.03,.93]},{name:"countertop.004",group:"07_interior",polygon:[[2.7,-1.2],[2.7029,-1.2071],[2.71,-1.21],[3.29,-1.21],[3.2971,-1.2071],[3.3,-1.2],[3.3,-.56],[3.2971,-.5529],[3.29,-.55],[2.71,-.55],[2.7029,-.5529],[2.7,-.56]],height:[.935,.985]},{name:"fridge",group:"07_interior",polygon:[[.15,-1.05],[.1573,-1.0677],[.175,-1.075],[.825,-1.075],[.8427,-1.0677],[.85,-1.05],[.85,-.35],[.8427,-.3323],[.825,-.325],[.175,-.325],[.1573,-.3323],[.15,-.35]],height:[0,2.2]},{name:"kitchen island",group:"07_interior",polygon:[[.95,.32],[.9559,.3059],[.97,.3],[3.23,.3],[3.2441,.3059],[3.25,.32],[3.25,1.18],[3.2441,1.1941],[3.23,1.2],[.97,1.2],[.9559,1.1941],[.95,1.18]],height:[0,1]},{name:"island top",group:"07_interior",polygon:[[.9,.26],[.9029,.2529],[.91,.25],[3.29,.25],[3.2971,.2529],[3.3,.26],[3.3,1.24],[3.2971,1.2471],[3.29,1.25],[.91,1.25],[.9029,1.2471],[.9,1.24]],height:[1,1.06]},{name:"hob",group:"07_interior",polygon:[[2.26,-1.085],[2.2629,-1.0921],[2.27,-1.095],[2.73,-1.095],[2.7371,-1.0921],[2.74,-1.085],[2.74,-.655],[2.7371,-.6479],[2.73,-.645],[2.27,-.645],[2.2629,-.6479],[2.26,-.655]],height:[.9875,1.0125]},{name:"dining top",group:"07_interior",polygon:[[4.95,.75],[4.9867,.5182],[5.0932,.3092],[5.2592,.1432],[5.4682,.0367],[5.7,-0],[5.9318,.0367],[6.1408,.1432],[6.3068,.3092],[6.4133,.5182],[6.45,.75],[6.4133,.9818],[6.3068,1.1908],[6.1408,1.3568],[5.9318,1.4633],[5.7,1.5],[5.4682,1.4633],[5.2592,1.3568],[5.0932,1.1908],[4.9867,.9818]],height:[.745,.815]},{name:"dining pedestal",group:"07_interior",polygon:[[5.5,.75],[5.5098,.6882],[5.5382,.6324],[5.5824,.5882],[5.6382,.5598],[5.7,.55],[5.7618,.5598],[5.8176,.5882],[5.8618,.6324],[5.8902,.6882],[5.9,.75],[5.8902,.8118],[5.8618,.8676],[5.8176,.9118],[5.7618,.9402],[5.7,.95],[5.6382,.9402],[5.5824,.9118],[5.5382,.8676],[5.5098,.8118]],height:[.025,.775]},{name:"chair seat",group:"07_interior",polygon:[[6.52,.56],[6.5317,.5317],[6.56,.52],[6.94,.52],[6.9683,.5317],[6.98,.56],[6.98,.94],[6.9683,.9683],[6.94,.98],[6.56,.98],[6.5317,.9683],[6.52,.94]],height:[.385,.475]},{name:"chair leg",group:"07_interior",polygon:[[6.57,.894],[6.5712,.8912],[6.574,.89],[6.606,.89],[6.6088,.8912],[6.61,.894],[6.61,.926],[6.6088,.9288],[6.606,.93],[6.574,.93],[6.5712,.9288],[6.57,.926]],height:[.01,.43]},{name:"chair leg.001",group:"07_interior",polygon:[[6.57,.574],[6.5712,.5712],[6.574,.57],[6.606,.57],[6.6088,.5712],[6.61,.574],[6.61,.606],[6.6088,.6088],[6.606,.61],[6.574,.61],[6.5712,.6088],[6.57,.606]],height:[.01,.43]},{name:"chair leg.002",group:"07_interior",polygon:[[6.89,.894],[6.8912,.8912],[6.894,.89],[6.926,.89],[6.9288,.8912],[6.93,.894],[6.93,.926],[6.9288,.9288],[6.926,.93],[6.894,.93],[6.8912,.9288],[6.89,.926]],height:[.01,.43]},{name:"chair leg.003",group:"07_interior",polygon:[[6.89,.574],[6.8912,.5712],[6.894,.57],[6.926,.57],[6.9288,.5712],[6.93,.574],[6.93,.606],[6.9288,.6088],[6.926,.61],[6.894,.61],[6.8912,.6088],[6.89,.606]],height:[.01,.43]},{name:"chair seat.001",group:"07_interior",polygon:[[5.47,-.49],[5.4817,-.5183],[5.51,-.53],[5.89,-.53],[5.9183,-.5183],[5.93,-.49],[5.93,-.11],[5.9183,-.0817],[5.89,-.07],[5.51,-.07],[5.4817,-.0817],[5.47,-.11]],height:[.385,.475]},{name:"chair leg.004",group:"07_interior",polygon:[[5.52,-.156],[5.5212,-.1588],[5.524,-.16],[5.556,-.16],[5.5588,-.1588],[5.56,-.156],[5.56,-.124],[5.5588,-.1212],[5.556,-.12],[5.524,-.12],[5.5212,-.1212],[5.52,-.124]],height:[.01,.43]},{name:"chair leg.005",group:"07_interior",polygon:[[5.52,-.476],[5.5212,-.4788],[5.524,-.48],[5.556,-.48],[5.5588,-.4788],[5.56,-.476],[5.56,-.444],[5.5588,-.4412],[5.556,-.44],[5.524,-.44],[5.5212,-.4412],[5.52,-.444]],height:[.01,.43]},{name:"chair leg.006",group:"07_interior",polygon:[[5.84,-.156],[5.8412,-.1588],[5.844,-.16],[5.876,-.16],[5.8788,-.1588],[5.88,-.156],[5.88,-.124],[5.8788,-.1212],[5.876,-.12],[5.844,-.12],[5.8412,-.1212],[5.84,-.124]],height:[.01,.43]},{name:"chair leg.007",group:"07_interior",polygon:[[5.84,-.476],[5.8412,-.4788],[5.844,-.48],[5.876,-.48],[5.8788,-.4788],[5.88,-.476],[5.88,-.444],[5.8788,-.4412],[5.876,-.44],[5.844,-.44],[5.8412,-.4412],[5.84,-.444]],height:[.01,.43]},{name:"chair seat.002",group:"07_interior",polygon:[[4.42,.56],[4.4317,.5317],[4.46,.52],[4.84,.52],[4.8683,.5317],[4.88,.56],[4.88,.94],[4.8683,.9683],[4.84,.98],[4.46,.98],[4.4317,.9683],[4.42,.94]],height:[.385,.475]},{name:"chair leg.008",group:"07_interior",polygon:[[4.47,.894],[4.4712,.8912],[4.474,.89],[4.506,.89],[4.5088,.8912],[4.51,.894],[4.51,.926],[4.5088,.9288],[4.506,.93],[4.474,.93],[4.4712,.9288],[4.47,.926]],height:[.01,.43]},{name:"chair leg.009",group:"07_interior",polygon:[[4.47,.574],[4.4712,.5712],[4.474,.57],[4.506,.57],[4.5088,.5712],[4.51,.574],[4.51,.606],[4.5088,.6088],[4.506,.61],[4.474,.61],[4.4712,.6088],[4.47,.606]],height:[.01,.43]},{name:"chair leg.010",group:"07_interior",polygon:[[4.79,.894],[4.7912,.8912],[4.794,.89],[4.826,.89],[4.8288,.8912],[4.83,.894],[4.83,.926],[4.8288,.9288],[4.826,.93],[4.794,.93],[4.7912,.9288],[4.79,.926]],height:[.01,.43]},{name:"chair leg.011",group:"07_interior",polygon:[[4.79,.574],[4.7912,.5712],[4.794,.57],[4.826,.57],[4.8288,.5712],[4.83,.574],[4.83,.606],[4.8288,.6088],[4.826,.61],[4.794,.61],[4.7912,.6088],[4.79,.606]],height:[.01,.43]},{name:"chair seat.003",group:"07_interior",polygon:[[5.47,1.61],[5.4817,1.5817],[5.51,1.57],[5.89,1.57],[5.9183,1.5817],[5.93,1.61],[5.93,1.99],[5.9183,2.0183],[5.89,2.03],[5.51,2.03],[5.4817,2.0183],[5.47,1.99]],height:[.385,.475]},{name:"chair leg.012",group:"07_interior",polygon:[[5.52,1.944],[5.5212,1.9412],[5.524,1.94],[5.556,1.94],[5.5588,1.9412],[5.56,1.944],[5.56,1.976],[5.5588,1.9788],[5.556,1.98],[5.524,1.98],[5.5212,1.9788],[5.52,1.976]],height:[.01,.43]},{name:"chair leg.013",group:"07_interior",polygon:[[5.52,1.624],[5.5212,1.6212],[5.524,1.62],[5.556,1.62],[5.5588,1.6212],[5.56,1.624],[5.56,1.656],[5.5588,1.6588],[5.556,1.66],[5.524,1.66],[5.5212,1.6588],[5.52,1.656]],height:[.01,.43]},{name:"chair leg.014",group:"07_interior",polygon:[[5.84,1.944],[5.8412,1.9412],[5.844,1.94],[5.876,1.94],[5.8788,1.9412],[5.88,1.944],[5.88,1.976],[5.8788,1.9788],[5.876,1.98],[5.844,1.98],[5.8412,1.9788],[5.84,1.976]],height:[.01,.43]},{name:"chair leg.015",group:"07_interior",polygon:[[5.84,1.624],[5.8412,1.6212],[5.844,1.62],[5.876,1.62],[5.8788,1.6212],[5.88,1.624],[5.88,1.656],[5.8788,1.6588],[5.876,1.66],[5.844,1.66],[5.8412,1.6588],[5.84,1.656]],height:[.01,.43]},{name:"bathtub",group:"07_interior",polygon:[[.375,-4.315],[.4219,-4.4281],[.535,-4.475],[1.965,-4.475],[2.0781,-4.4281],[2.125,-4.315],[2.125,-3.885],[2.0781,-3.7719],[1.965,-3.725],[.535,-3.725],[.4219,-3.7719],[.375,-3.885]],height:[.025,.675]},{name:"bath interior",group:"07_interior",polygon:[[.5,-4.355],[.5059,-4.3691],[.52,-4.375],[1.98,-4.375],[1.9941,-4.3691],[2,-4.355],[2,-3.845],[1.9941,-3.8309],[1.98,-3.825],[.52,-3.825],[.5059,-3.8309],[.5,-3.845]],height:[.66,.7]},{name:"vanity",group:"07_interior",polygon:[[.25,-2.62],[.2588,-2.6412],[.28,-2.65],[.82,-2.65],[.8412,-2.6412],[.85,-2.62],[.85,-1.78],[.8412,-1.7588],[.82,-1.75],[.28,-1.75],[.2588,-1.7588],[.25,-1.78]],height:[.03,.93]},{name:"basin",group:"07_interior",polygon:[[.3,-2.2],[.3122,-2.2773],[.3477,-2.3469],[.4031,-2.4023],[.4727,-2.4378],[.55,-2.45],[.6273,-2.4378],[.6969,-2.4023],[.7523,-2.3469],[.7878,-2.2773],[.8,-2.2],[.7878,-2.1227],[.7523,-2.0531],[.6969,-1.9977],[.6273,-1.9622],[.55,-1.95],[.4727,-1.9622],[.4031,-1.9977],[.3477,-2.0531],[.3122,-2.1227]],height:[.92,1.04]},{name:"washer",group:"07_interior",polygon:[[2.96,-4.5],[2.9673,-4.5177],[2.985,-4.525],[3.615,-4.525],[3.6327,-4.5177],[3.64,-4.5],[3.64,-3.9],[3.6327,-3.8823],[3.615,-3.875],[2.985,-3.875],[2.9673,-3.8823],[2.96,-3.9]],height:[0,1]},{name:"washer door",group:"07_interior",polygon:[[3.08,-3.8695],[3.0824,-3.8752],[3.0881,-3.8775],[3.5119,-3.8775],[3.5176,-3.8752],[3.52,-3.8695],[3.52,-3.8505],[3.5176,-3.8448],[3.5119,-3.8425],[3.0881,-3.8425],[3.0824,-3.8448],[3.08,-3.8505]],height:[.3,.74]},{name:"office desk",group:"07_interior",polygon:[[5,-4.585],[5.0044,-4.5956],[5.015,-4.6],[6.585,-4.6],[6.5956,-4.5956],[6.6,-4.585],[6.6,-4.015],[6.5956,-4.0044],[6.585,-4],[5.015,-4],[5.0044,-4.0044],[5,-4.015]],height:[.73,.81]},{name:"laptop",group:"07_interior",polygon:[[5.6,-4.4275],[5.6037,-4.4363],[5.6125,-4.44],[5.9875,-4.44],[5.9963,-4.4363],[6,-4.4275],[6,-4.1725],[5.9963,-4.1637],[5.9875,-4.16],[5.6125,-4.16],[5.6037,-4.1637],[5.6,-4.1725]],height:[.8275,.8525]},{name:"13_inner_finish.001",group:"13_inner_finish",polygon:[[6.87,-2.094],[6.8708,-2.097],[6.873,-2.0992],[6.876,-2.1],[6.894,-2.1],[6.897,-2.0992],[6.8992,-2.097],[6.9,-2.094],[6.9,-.606],[6.8992,-.603],[6.897,-.6008],[6.894,-.6],[6.876,-.6],[6.873,-.6008],[6.8708,-.603],[6.87,-.606]],height:[0,3]},{name:"09_wall_core.001",group:"09_wall_core",polygon:[[6.9,-2.094],[6.9008,-2.097],[6.903,-2.0992],[6.906,-2.1],[7.054,-2.1],[7.057,-2.0992],[7.0592,-2.097],[7.06,-2.094],[7.06,-.606],[7.0592,-.603],[7.057,-.6008],[7.054,-.6],[6.906,-.6],[6.903,-.6008],[6.9008,-.603],[6.9,-.606]],height:[0,3]},{name:"10_insulation.001",group:"10_insulation",polygon:[[7.06,-2.094],[7.0608,-2.097],[7.063,-2.0992],[7.066,-2.1],[7.114,-2.1],[7.117,-2.0992],[7.1192,-2.097],[7.12,-2.094],[7.12,-.606],[7.1192,-.603],[7.117,-.6008],[7.114,-.6],[7.066,-.6],[7.063,-.6008],[7.0608,-.603],[7.06,-.606]],height:[0,3]},{name:"11_vent_gap.001",group:"11_vent_gap",polygon:[[7.124,-2.094],[7.1248,-2.097],[7.127,-2.0992],[7.13,-2.1],[7.133,-2.0992],[7.1352,-2.097],[7.136,-2.094],[7.136,-.606],[7.1352,-.603],[7.133,-.6008],[7.13,-.6],[7.127,-.6008],[7.1248,-.603],[7.124,-.606]],height:[0,3]},{name:"facade wood slat",group:"12_cladding",polygon:[[7.1375,-.717],[7.1386,-.721],[7.1415,-.7239],[7.1455,-.725],[7.1645,-.725],[7.1685,-.7239],[7.1714,-.721],[7.1725,-.717],[7.1725,-.613],[7.1714,-.609],[7.1685,-.6061],[7.1645,-.605],[7.1455,-.605],[7.1415,-.6061],[7.1386,-.609],[7.1375,-.613]],height:[0,3]},{name:"facade wood slat.001",group:"12_cladding",polygon:[[7.1375,-.853],[7.1386,-.857],[7.1415,-.8599],[7.1455,-.861],[7.1645,-.861],[7.1685,-.8599],[7.1714,-.857],[7.1725,-.853],[7.1725,-.749],[7.1714,-.745],[7.1685,-.7421],[7.1645,-.741],[7.1455,-.741],[7.1415,-.7421],[7.1386,-.745],[7.1375,-.749]],height:[0,3]},{name:"facade wood slat.002",group:"12_cladding",polygon:[[7.1375,-.989],[7.1386,-.993],[7.1415,-.9959],[7.1455,-.997],[7.1645,-.997],[7.1685,-.9959],[7.1714,-.993],[7.1725,-.989],[7.1725,-.885],[7.1714,-.881],[7.1685,-.8781],[7.1645,-.877],[7.1455,-.877],[7.1415,-.8781],[7.1386,-.881],[7.1375,-.885]],height:[0,3]},{name:"facade wood slat.003",group:"12_cladding",polygon:[[7.1375,-1.125],[7.1386,-1.129],[7.1415,-1.1319],[7.1455,-1.133],[7.1645,-1.133],[7.1685,-1.1319],[7.1714,-1.129],[7.1725,-1.125],[7.1725,-1.021],[7.1714,-1.017],[7.1685,-1.0141],[7.1645,-1.013],[7.1455,-1.013],[7.1415,-1.0141],[7.1386,-1.017],[7.1375,-1.021]],height:[0,3]},{name:"facade wood slat.004",group:"12_cladding",polygon:[[7.1375,-1.261],[7.1386,-1.265],[7.1415,-1.2679],[7.1455,-1.269],[7.1645,-1.269],[7.1685,-1.2679],[7.1714,-1.265],[7.1725,-1.261],[7.1725,-1.157],[7.1714,-1.153],[7.1685,-1.1501],[7.1645,-1.149],[7.1455,-1.149],[7.1415,-1.1501],[7.1386,-1.153],[7.1375,-1.157]],height:[0,3]},{name:"facade wood slat.005",group:"12_cladding",polygon:[[7.1375,-1.397],[7.1386,-1.401],[7.1415,-1.4039],[7.1455,-1.405],[7.1645,-1.405],[7.1685,-1.4039],[7.1714,-1.401],[7.1725,-1.397],[7.1725,-1.293],[7.1714,-1.289],[7.1685,-1.2861],[7.1645,-1.285],[7.1455,-1.285],[7.1415,-1.2861],[7.1386,-1.289],[7.1375,-1.293]],height:[0,3]},{name:"facade wood slat.006",group:"12_cladding",polygon:[[7.1375,-1.533],[7.1386,-1.537],[7.1415,-1.5399],[7.1455,-1.541],[7.1645,-1.541],[7.1685,-1.5399],[7.1714,-1.537],[7.1725,-1.533],[7.1725,-1.429],[7.1714,-1.425],[7.1685,-1.4221],[7.1645,-1.421],[7.1455,-1.421],[7.1415,-1.4221],[7.1386,-1.425],[7.1375,-1.429]],height:[0,3]},{name:"facade wood slat.007",group:"12_cladding",polygon:[[7.1375,-1.669],[7.1386,-1.673],[7.1415,-1.6759],[7.1455,-1.677],[7.1645,-1.677],[7.1685,-1.6759],[7.1714,-1.673],[7.1725,-1.669],[7.1725,-1.565],[7.1714,-1.561],[7.1685,-1.5581],[7.1645,-1.557],[7.1455,-1.557],[7.1415,-1.5581],[7.1386,-1.561],[7.1375,-1.565]],height:[0,3]},{name:"facade wood slat.008",group:"12_cladding",polygon:[[7.1375,-1.805],[7.1386,-1.809],[7.1415,-1.8119],[7.1455,-1.813],[7.1645,-1.813],[7.1685,-1.8119],[7.1714,-1.809],[7.1725,-1.805],[7.1725,-1.701],[7.1714,-1.697],[7.1685,-1.6941],[7.1645,-1.693],[7.1455,-1.693],[7.1415,-1.6941],[7.1386,-1.697],[7.1375,-1.701]],height:[0,3]},{name:"facade wood slat.009",group:"12_cladding",polygon:[[7.1375,-1.941],[7.1386,-1.945],[7.1415,-1.9479],[7.1455,-1.949],[7.1645,-1.949],[7.1685,-1.9479],[7.1714,-1.945],[7.1725,-1.941],[7.1725,-1.837],[7.1714,-1.833],[7.1685,-1.8301],[7.1645,-1.829],[7.1455,-1.829],[7.1415,-1.8301],[7.1386,-1.833],[7.1375,-1.837]],height:[0,3]},{name:"facade wood slat.010",group:"12_cladding",polygon:[[7.1375,-2.077],[7.1386,-2.081],[7.1415,-2.0839],[7.1455,-2.085],[7.1645,-2.085],[7.1685,-2.0839],[7.1714,-2.081],[7.1725,-2.077],[7.1725,-1.973],[7.1714,-1.969],[7.1685,-1.9661],[7.1645,-1.965],[7.1455,-1.965],[7.1415,-1.9661],[7.1386,-1.969],[7.1375,-1.973]],height:[0,3]},{name:"core horizontal joint",group:"09_wall_core",polygon:[[7.063,-2.09],[7.065,-2.09],[7.065,-.61],[7.063,-.61]],height:[.596,.604]},{name:"core horizontal joint.001",group:"09_wall_core",polygon:[[7.063,-2.09],[7.065,-2.09],[7.065,-.61],[7.063,-.61]],height:[1.196,1.204]},{name:"bedside book",group:"07_interior",polygon:[[-4.41,2.304],[-4.4095,2.302],[-4.408,2.3005],[-4.406,2.3],[-4.194,2.3],[-4.192,2.3005],[-4.1905,2.302],[-4.19,2.304],[-4.19,2.596],[-4.1905,2.598],[-4.192,2.5995],[-4.194,2.6],[-4.406,2.6],[-4.408,2.5995],[-4.4095,2.598],[-4.41,2.596]],height:[.5075,.5525]},{name:"bedside lamp foot",group:"07_interior",polygon:[[-4.4,2.45],[-4.3966,2.4241],[-4.3866,2.4],[-4.3707,2.3793],[-4.35,2.3634],[-4.3259,2.3534],[-4.3,2.35],[-4.2741,2.3534],[-4.25,2.3634],[-4.2293,2.3793],[-4.2134,2.4],[-4.2034,2.4241],[-4.2,2.45],[-4.2034,2.4759],[-4.2134,2.5],[-4.2293,2.5207],[-4.25,2.5366],[-4.2741,2.5466],[-4.3,2.55],[-4.3259,2.5466],[-4.35,2.5366],[-4.3707,2.5207],[-4.3866,2.5],[-4.3966,2.4759]],height:[.5575,.5825]},{name:"bedside lamp stem",group:"07_interior",polygon:[[-4.312,2.45],[-4.3116,2.4469],[-4.3104,2.444],[-4.3085,2.4415],[-4.306,2.4396],[-4.3031,2.4384],[-4.3,2.438],[-4.2969,2.4384],[-4.294,2.4396],[-4.2915,2.4415],[-4.2896,2.444],[-4.2884,2.4469],[-4.288,2.45],[-4.2884,2.4531],[-4.2896,2.456],[-4.2915,2.4585],[-4.294,2.4604],[-4.2969,2.4616],[-4.3,2.462],[-4.3031,2.4616],[-4.306,2.4604],[-4.3085,2.4585],[-4.3104,2.456],[-4.3116,2.4531]],height:[.57,.89]},{name:"bedside shade",group:"07_interior",polygon:[[-4.45,2.45],[-4.4449,2.4112],[-4.4299,2.375],[-4.4061,2.3439],[-4.375,2.3201],[-4.3388,2.3051],[-4.3,2.3],[-4.2612,2.3051],[-4.225,2.3201],[-4.1939,2.3439],[-4.1701,2.375],[-4.1551,2.4112],[-4.15,2.45],[-4.1551,2.4888],[-4.1701,2.525],[-4.1939,2.5561],[-4.225,2.5799],[-4.2612,2.5949],[-4.3,2.6],[-4.3388,2.5949],[-4.375,2.5799],[-4.4061,2.5561],[-4.4299,2.525],[-4.4449,2.4888]],height:[.815,1.005]},{name:"bedside book.001",group:"07_interior",polygon:[[-4.41,-.846],[-4.4095,-.848],[-4.408,-.8495],[-4.406,-.85],[-4.194,-.85],[-4.192,-.8495],[-4.1905,-.848],[-4.19,-.846],[-4.19,-.554],[-4.1905,-.552],[-4.192,-.5505],[-4.194,-.55],[-4.406,-.55],[-4.408,-.5505],[-4.4095,-.552],[-4.41,-.554]],height:[.5075,.5525]},{name:"bedside lamp foot.001",group:"07_interior",polygon:[[-4.4,-.7],[-4.3966,-.7259],[-4.3866,-.75],[-4.3707,-.7707],[-4.35,-.7866],[-4.3259,-.7966],[-4.3,-.8],[-4.2741,-.7966],[-4.25,-.7866],[-4.2293,-.7707],[-4.2134,-.75],[-4.2034,-.7259],[-4.2,-.7],[-4.2034,-.6741],[-4.2134,-.65],[-4.2293,-.6293],[-4.25,-.6134],[-4.2741,-.6034],[-4.3,-.6],[-4.3259,-.6034],[-4.35,-.6134],[-4.3707,-.6293],[-4.3866,-.65],[-4.3966,-.6741]],height:[.5575,.5825]},{name:"bedside lamp stem.001",group:"07_interior",polygon:[[-4.312,-.7],[-4.3116,-.7031],[-4.3104,-.706],[-4.3085,-.7085],[-4.306,-.7104],[-4.3031,-.7116],[-4.3,-.712],[-4.2969,-.7116],[-4.294,-.7104],[-4.2915,-.7085],[-4.2896,-.706],[-4.2884,-.7031],[-4.288,-.7],[-4.2884,-.6969],[-4.2896,-.694],[-4.2915,-.6915],[-4.294,-.6896],[-4.2969,-.6884],[-4.3,-.688],[-4.3031,-.6884],[-4.306,-.6896],[-4.3085,-.6915],[-4.3104,-.694],[-4.3116,-.6969]],height:[.57,.89]},{name:"bedside shade.001",group:"07_interior",polygon:[[-4.45,-.7],[-4.4449,-.7388],[-4.4299,-.775],[-4.4061,-.8061],[-4.375,-.8299],[-4.3388,-.8449],[-4.3,-.85],[-4.2612,-.8449],[-4.225,-.8299],[-4.1939,-.8061],[-4.1701,-.775],[-4.1551,-.7388],[-4.15,-.7],[-4.1551,-.6612],[-4.1701,-.625],[-4.1939,-.5939],[-4.225,-.5701],[-4.2612,-.5551],[-4.3,-.55],[-4.3388,-.5551],[-4.375,-.5701],[-4.4061,-.5939],[-4.4299,-.625],[-4.4449,-.6612]],height:[.815,1.005]},{name:"bedside book.002",group:"07_interior",polygon:[[-4.41,-3.946],[-4.4095,-3.948],[-4.408,-3.9495],[-4.406,-3.95],[-4.194,-3.95],[-4.192,-3.9495],[-4.1905,-3.948],[-4.19,-3.946],[-4.19,-3.654],[-4.1905,-3.652],[-4.192,-3.6505],[-4.194,-3.65],[-4.406,-3.65],[-4.408,-3.6505],[-4.4095,-3.652],[-4.41,-3.654]],height:[.5075,.5525]},{name:"bedside lamp foot.002",group:"07_interior",polygon:[[-4.4,-3.8],[-4.3966,-3.8259],[-4.3866,-3.85],[-4.3707,-3.8707],[-4.35,-3.8866],[-4.3259,-3.8966],[-4.3,-3.9],[-4.2741,-3.8966],[-4.25,-3.8866],[-4.2293,-3.8707],[-4.2134,-3.85],[-4.2034,-3.8259],[-4.2,-3.8],[-4.2034,-3.7741],[-4.2134,-3.75],[-4.2293,-3.7293],[-4.25,-3.7134],[-4.2741,-3.7034],[-4.3,-3.7],[-4.3259,-3.7034],[-4.35,-3.7134],[-4.3707,-3.7293],[-4.3866,-3.75],[-4.3966,-3.7741]],height:[.5575,.5825]},{name:"bedside lamp stem.002",group:"07_interior",polygon:[[-4.312,-3.8],[-4.3116,-3.8031],[-4.3104,-3.806],[-4.3085,-3.8085],[-4.306,-3.8104],[-4.3031,-3.8116],[-4.3,-3.812],[-4.2969,-3.8116],[-4.294,-3.8104],[-4.2915,-3.8085],[-4.2896,-3.806],[-4.2884,-3.8031],[-4.288,-3.8],[-4.2884,-3.7969],[-4.2896,-3.794],[-4.2915,-3.7915],[-4.294,-3.7896],[-4.2969,-3.7884],[-4.3,-3.788],[-4.3031,-3.7884],[-4.306,-3.7896],[-4.3085,-3.7915],[-4.3104,-3.794],[-4.3116,-3.7969]],height:[.57,.89]},{name:"bedside shade.002",group:"07_interior",polygon:[[-4.45,-3.8],[-4.4449,-3.8388],[-4.4299,-3.875],[-4.4061,-3.9061],[-4.375,-3.9299],[-4.3388,-3.9449],[-4.3,-3.95],[-4.2612,-3.9449],[-4.225,-3.9299],[-4.1939,-3.9061],[-4.1701,-3.875],[-4.1551,-3.8388],[-4.15,-3.8],[-4.1551,-3.7612],[-4.1701,-3.725],[-4.1939,-3.6939],[-4.225,-3.6701],[-4.2612,-3.6551],[-4.3,-3.65],[-4.3388,-3.6551],[-4.375,-3.6701],[-4.4061,-3.6939],[-4.4299,-3.725],[-4.4449,-3.7612]],height:[.815,1.005]},{name:"sofa scatter cushion",group:"07_interior",polygon:[[3.69,3.2],[3.7052,3.1567],[3.7492,3.1177],[3.8178,3.0867],[3.9042,3.0669],[4,3.06],[4.0958,3.0669],[4.1822,3.0867],[4.2508,3.1177],[4.2948,3.1567],[4.31,3.2],[4.2948,3.2433],[4.2508,3.2823],[4.1822,3.3133],[4.0958,3.3331],[4,3.34],[3.9042,3.3331],[3.8178,3.3133],[3.7492,3.2823],[3.7052,3.2433]],height:[.62,1.26]},{name:"sofa scatter cushion.001",group:"07_interior",polygon:[[5.29,3.2],[5.3052,3.1567],[5.3492,3.1177],[5.4178,3.0867],[5.5042,3.0669],[5.6,3.06],[5.6958,3.0669],[5.7822,3.0867],[5.8508,3.1177],[5.8948,3.1567],[5.91,3.2],[5.8948,3.2433],[5.8508,3.2823],[5.7822,3.3133],[5.6958,3.3331],[5.6,3.34],[5.5042,3.3331],[5.4178,3.3133],[5.3492,3.2823],[5.3052,3.2433]],height:[.62,1.26]},{name:"coffee table book",group:"07_interior",polygon:[[4.575,2.183],[4.5754,2.1815],[4.5765,2.1804],[4.578,2.18],[4.822,2.18],[4.8235,2.1804],[4.8246,2.1815],[4.825,2.183],[4.825,2.517],[4.8246,2.5185],[4.8235,2.5196],[4.822,2.52],[4.578,2.52],[4.5765,2.5196],[4.5754,2.5185],[4.575,2.517]],height:[.4525,.4875]},{name:"coffee cup",group:"07_interior",polygon:[[4.895,2.4],[4.8969,2.3858],[4.9024,2.3725],[4.9111,2.3611],[4.9225,2.3524],[4.9358,2.3469],[4.95,2.345],[4.9642,2.3469],[4.9775,2.3524],[4.9889,2.3611],[4.9976,2.3725],[5.0031,2.3858],[5.005,2.4],[5.0031,2.4142],[4.9976,2.4275],[4.9889,2.4389],[4.9775,2.4476],[4.9642,2.4531],[4.95,2.455],[4.9358,2.4531],[4.9225,2.4476],[4.9111,2.4389],[4.9024,2.4275],[4.8969,2.4142]],height:[.47,.55]},{name:"splashback",group:"07_interior",polygon:[[.9,-1.2375],[.9007,-1.24],[.9025,-1.2418],[.905,-1.2425],[3.295,-1.2425],[3.2975,-1.2418],[3.2993,-1.24],[3.3,-1.2375],[3.3,-1.2225],[3.2993,-1.22],[3.2975,-1.2182],[3.295,-1.2175],[.905,-1.2175],[.9025,-1.2182],[.9007,-1.22],[.9,-1.2225]],height:[.995,1.445]},{name:"sink rim",group:"07_interior",polygon:[[1.075,-1.06],[1.0763,-1.065],[1.08,-1.0687],[1.085,-1.07],[1.515,-1.07],[1.52,-1.0687],[1.5237,-1.065],[1.525,-1.06],[1.525,-.68],[1.5237,-.675],[1.52,-.6713],[1.515,-.67],[1.085,-.67],[1.08,-.6713],[1.0763,-.675],[1.075,-.68]],height:[.99,1.01]},{name:"sink basin",group:"07_interior",polygon:[[1.115,-1.02],[1.1163,-1.025],[1.12,-1.0287],[1.125,-1.03],[1.475,-1.03],[1.48,-1.0287],[1.4837,-1.025],[1.485,-1.02],[1.485,-.72],[1.4837,-.715],[1.48,-.7113],[1.475,-.71],[1.125,-.71],[1.12,-.7113],[1.1163,-.715],[1.115,-.72]],height:[.995,1.015]},{name:"stool seat",group:"07_interior",polygon:[[1.21,1.5],[1.2182,1.4379],[1.2422,1.38],[1.2803,1.3303],[1.33,1.2922],[1.3879,1.2682],[1.45,1.26],[1.5121,1.2682],[1.57,1.2922],[1.6197,1.3303],[1.6578,1.38],[1.6818,1.4379],[1.69,1.5],[1.6818,1.5621],[1.6578,1.62],[1.6197,1.6697],[1.57,1.7078],[1.5121,1.7318],[1.45,1.74],[1.3879,1.7318],[1.33,1.7078],[1.2803,1.6697],[1.2422,1.62],[1.2182,1.5621]],height:[.6725,.7275]},{name:"stool leg",group:"07_interior",polygon:[[1.2884,1.638],[1.2899,1.6353],[1.3473,1.5779],[1.35,1.5764],[1.3531,1.5764],[1.3558,1.578],[1.372,1.5942],[1.3736,1.5969],[1.3736,1.6],[1.3721,1.6027],[1.3559,1.6189],[1.3147,1.6601],[1.312,1.6616],[1.3089,1.6616],[1.3062,1.66],[1.29,1.6438],[1.2884,1.6411]],height:[.0589,.6811]},{name:"stool leg.001",group:"07_interior",polygon:[[1.2884,1.3589],[1.29,1.3562],[1.3062,1.34],[1.3089,1.3384],[1.312,1.3384],[1.3147,1.3399],[1.3559,1.3811],[1.3721,1.3973],[1.3736,1.4],[1.3736,1.4031],[1.372,1.4058],[1.3558,1.422],[1.3531,1.4236],[1.35,1.4236],[1.3473,1.4221],[1.2899,1.3647],[1.2884,1.362]],height:[.0589,.6811]},{name:"stool leg.002",group:"07_interior",polygon:[[1.5264,1.5969],[1.528,1.5942],[1.5442,1.578],[1.5469,1.5764],[1.55,1.5764],[1.5527,1.5779],[1.5939,1.6191],[1.6101,1.6353],[1.6116,1.638],[1.6116,1.6411],[1.61,1.6438],[1.5938,1.66],[1.5911,1.6616],[1.588,1.6616],[1.5853,1.6601],[1.5279,1.6027],[1.5264,1.6]],height:[.0589,.6811]},{name:"stool leg.003",group:"07_interior",polygon:[[1.5264,1.4],[1.5279,1.3973],[1.5853,1.3399],[1.588,1.3384],[1.5911,1.3384],[1.5938,1.34],[1.61,1.3562],[1.6116,1.3589],[1.6116,1.362],[1.6101,1.3647],[1.5939,1.3809],[1.5527,1.4221],[1.55,1.4236],[1.5469,1.4236],[1.5442,1.422],[1.528,1.4058],[1.5264,1.4031]],height:[.0589,.6811]},{name:"stool seat.001",group:"07_interior",polygon:[[2.11,1.5],[2.1182,1.4379],[2.1422,1.38],[2.1803,1.3303],[2.23,1.2922],[2.2879,1.2682],[2.35,1.26],[2.4121,1.2682],[2.47,1.2922],[2.5197,1.3303],[2.5578,1.38],[2.5818,1.4379],[2.59,1.5],[2.5818,1.5621],[2.5578,1.62],[2.5197,1.6697],[2.47,1.7078],[2.4121,1.7318],[2.35,1.74],[2.2879,1.7318],[2.23,1.7078],[2.1803,1.6697],[2.1422,1.62],[2.1182,1.5621]],height:[.6725,.7275]},{name:"stool leg.004",group:"07_interior",polygon:[[2.1884,1.638],[2.1899,1.6353],[2.2473,1.5779],[2.25,1.5764],[2.2531,1.5764],[2.2558,1.578],[2.272,1.5942],[2.2736,1.5969],[2.2736,1.6],[2.2721,1.6027],[2.2147,1.6601],[2.212,1.6616],[2.2089,1.6616],[2.2062,1.66],[2.19,1.6438],[2.1884,1.6411]],height:[.0589,.6811]},{name:"stool leg.005",group:"07_interior",polygon:[[2.1884,1.3589],[2.19,1.3562],[2.2062,1.34],[2.2089,1.3384],[2.212,1.3384],[2.2147,1.3399],[2.2721,1.3973],[2.2736,1.4],[2.2736,1.4031],[2.272,1.4058],[2.2558,1.422],[2.2531,1.4236],[2.25,1.4236],[2.2473,1.4221],[2.1899,1.3647],[2.1884,1.362]],height:[.0589,.6811]},{name:"stool leg.006",group:"07_interior",polygon:[[2.4264,1.5969],[2.428,1.5942],[2.4442,1.578],[2.4469,1.5764],[2.45,1.5764],[2.4527,1.5779],[2.5101,1.6353],[2.5116,1.638],[2.5116,1.6411],[2.51,1.6438],[2.4938,1.66],[2.4911,1.6616],[2.488,1.6616],[2.4853,1.6601],[2.4279,1.6027],[2.4264,1.6]],height:[.0589,.6811]},{name:"stool leg.007",group:"07_interior",polygon:[[2.4264,1.4],[2.4279,1.3973],[2.4853,1.3399],[2.488,1.3384],[2.4911,1.3384],[2.4938,1.34],[2.51,1.3562],[2.5116,1.3589],[2.5116,1.362],[2.5101,1.3647],[2.4527,1.4221],[2.45,1.4236],[2.4469,1.4236],[2.4442,1.422],[2.428,1.4058],[2.4264,1.4031]],height:[.0589,.6811]},{name:"toilet cistern",group:"07_interior",polygon:[[2.1,-3.62],[2.108,-3.65],[2.13,-3.672],[2.16,-3.68],[2.3,-3.68],[2.33,-3.672],[2.352,-3.65],[2.36,-3.62],[2.36,-3.28],[2.352,-3.25],[2.33,-3.228],[2.3,-3.22],[2.16,-3.22],[2.13,-3.228],[2.108,-3.25],[2.1,-3.28]],height:[.31,1.01]},{name:"toilet bowl",group:"07_interior",polygon:[[1.61,-3.45],[1.6266,-3.5242],[1.6749,-3.5911],[1.7502,-3.6442],[1.8449,-3.6783],[1.95,-3.69],[2.0551,-3.6783],[2.1498,-3.6442],[2.2251,-3.5911],[2.2734,-3.5242],[2.29,-3.45],[2.2734,-3.3758],[2.2251,-3.3089],[2.1498,-3.2558],[2.0551,-3.2217],[1.95,-3.21],[1.8449,-3.2217],[1.7502,-3.2558],[1.6749,-3.3089],[1.6266,-3.3758]],height:[.18,.6]},{name:"toilet plinth",group:"07_interior",polygon:[[1.825,-3.52],[1.8357,-3.5599],[1.8651,-3.5893],[1.905,-3.6],[2.095,-3.6],[2.1349,-3.5893],[2.1643,-3.5599],[2.175,-3.52],[2.175,-3.38],[2.1643,-3.3401],[2.1349,-3.3107],[2.095,-3.3],[1.905,-3.3],[1.8651,-3.3107],[1.8357,-3.3401],[1.825,-3.38]],height:[0,.4]},{name:"vanity mirror",group:"07_interior",polygon:[[.1825,-2.545],[.1845,-2.5525],[.19,-2.558],[.1975,-2.56],[.2025,-2.56],[.21,-2.558],[.2155,-2.5525],[.2175,-2.545],[.2175,-1.855],[.2155,-1.8475],[.21,-1.842],[.2025,-1.84],[.1975,-1.84],[.19,-1.842],[.1845,-1.8475],[.1825,-1.855]],height:[1.2,2.1]},{name:"folded towels",group:"07_interior",polygon:[[3.1,-4.35],[3.104,-4.365],[3.115,-4.376],[3.13,-4.38],[3.47,-4.38],[3.485,-4.376],[3.496,-4.365],[3.5,-4.35],[3.5,-4.05],[3.496,-4.035],[3.485,-4.024],[3.47,-4.02],[3.13,-4.02],[3.115,-4.024],[3.104,-4.035],[3.1,-4.05]],height:[1.005,1.095]},{name:"monitor",group:"07_interior",polygon:[[5.525,-4.4325],[5.527,-4.44],[5.5325,-4.4455],[5.54,-4.4475],[6.06,-4.4475],[6.0675,-4.4455],[6.073,-4.44],[6.075,-4.4325],[6.075,-4.4275],[6.073,-4.42],[6.0675,-4.4145],[6.06,-4.4125],[5.54,-4.4125],[5.5325,-4.4145],[5.527,-4.42],[5.525,-4.4275]],height:[1.04,1.36]},{name:"office chair seat",group:"07_interior",polygon:[[5.55,-3.755],[5.556,-3.7775],[5.5725,-3.794],[5.595,-3.8],[6.005,-3.8],[6.0275,-3.794],[6.044,-3.7775],[6.05,-3.755],[6.05,-3.345],[6.044,-3.3225],[6.0275,-3.306],[6.005,-3.3],[5.595,-3.3],[5.5725,-3.306],[5.556,-3.3225],[5.55,-3.345]],height:[.42,.52]},{name:"office chair back",group:"07_interior",polygon:[[5.55,-3.28],[5.5553,-3.3],[5.57,-3.3147],[5.59,-3.32],[6.01,-3.32],[6.03,-3.3147],[6.0447,-3.3],[6.05,-3.28],[6.0447,-3.26],[6.03,-3.2453],[6.01,-3.24],[5.59,-3.24],[5.57,-3.2453],[5.5553,-3.26]],height:[.55,1.05]},{name:"wardrobe pull",group:"07_interior",polygon:[[-3.289,2.136],[-3.271,2.136],[-3.271,2.154],[-3.289,2.154]],height:[.96,1.14]},{name:"wardrobe pull.001",group:"07_interior",polygon:[[-2.729,2.136],[-2.711,2.136],[-2.711,2.154],[-2.729,2.154]],height:[.96,1.14]},{name:"wardrobe pull.002",group:"07_interior",polygon:[[-3.289,-.964],[-3.271,-.964],[-3.271,-.946],[-3.289,-.946]],height:[.96,1.14]},{name:"wardrobe pull.003",group:"07_interior",polygon:[[-2.729,-.964],[-2.711,-.964],[-2.711,-.946],[-2.729,-.946]],height:[.96,1.14]},{name:"wardrobe pull.004",group:"07_interior",polygon:[[-3.289,-4.314],[-3.271,-4.314],[-3.271,-4.296],[-3.289,-4.296]],height:[.96,1.14]},{name:"wardrobe pull.005",group:"07_interior",polygon:[[-2.729,-4.314],[-2.711,-4.314],[-2.711,-4.296],[-2.729,-4.296]],height:[.96,1.14]}],rooms:[{id:"living",title:"\u041A\u0443\u0445\u043D\u044F-\u0433\u043E\u0441\u0442\u0438\u043D\u0430\u044F",point:[2.65,4.05],yaw:0,description:"\u041E\u0431\u0449\u0435\u0435 \u043F\u0440\u043E\u0441\u0442\u0440\u0430\u043D\u0441\u0442\u0432\u043E \u0441 \u0432\u044B\u0445\u043E\u0434\u043E\u043C \u043D\u0430 \u0442\u0435\u0440\u0440\u0430\u0441\u0443. \u041C\u0435\u0431\u0435\u043B\u044C \u0438 \u043F\u0440\u043E\u0445\u043E\u0434\u044B \u043F\u043E\u043A\u0430 \u043F\u0440\u0435\u0434\u043B\u043E\u0436\u0435\u043D\u044B \u0434\u043B\u044F \u043E\u0431\u0441\u0443\u0436\u0434\u0435\u043D\u0438\u044F."},{id:"hall",title:"\u041A\u043E\u0440\u0438\u0434\u043E\u0440",point:[-.75,.15],yaw:1.57,description:"\u0421\u043E\u0435\u0434\u0438\u043D\u044F\u0435\u0442 \u0442\u0440\u0438 \u0441\u043F\u0430\u043B\u044C\u043D\u0438 \u0438 \u043E\u0431\u0449\u0435\u0435 \u043F\u0440\u043E\u0441\u0442\u0440\u0430\u043D\u0441\u0442\u0432\u043E. \u041F\u0440\u043E\u0432\u0435\u0440\u044C\u0442\u0435 \u0443\u0434\u043E\u0431\u0441\u0442\u0432\u043E \u043C\u0430\u0440\u0448\u0440\u0443\u0442\u043E\u0432 \u0434\u043B\u044F \u0432\u0430\u0448\u0435\u0439 \u0441\u0435\u043C\u044C\u0438."},{id:"bedroom1",title:"\u0421\u043F\u0430\u043B\u044C\u043D\u044F 1",point:[-3.55,3.05],yaw:1.57,description:"\u041F\u0440\u0435\u0434\u043B\u043E\u0436\u0435\u043D\u0438\u0435 \u0441\u043F\u0430\u043B\u044C\u043D\u0438 \u0441 \u0434\u0432\u0443\u0441\u043F\u0430\u043B\u044C\u043D\u043E\u0439 \u043A\u0440\u043E\u0432\u0430\u0442\u044C\u044E \u0438 \u043C\u0435\u0441\u0442\u043E\u043C \u0445\u0440\u0430\u043D\u0435\u043D\u0438\u044F."},{id:"bedroom2",title:"\u0421\u043F\u0430\u043B\u044C\u043D\u044F 2",point:[-3.55,0],yaw:1.57,description:"\u041A\u043E\u043C\u043D\u0430\u0442\u0430 \u0441 \u043E\u0434\u043D\u043E\u0441\u043F\u0430\u043B\u044C\u043D\u043E\u0439 \u043A\u0440\u043E\u0432\u0430\u0442\u044C\u044E. \u041D\u0430\u0437\u043D\u0430\u0447\u0435\u043D\u0438\u0435 \u0438 \u043C\u0435\u0431\u0435\u043B\u044C \u043C\u043E\u0436\u043D\u043E \u043E\u0431\u0441\u0443\u0434\u0438\u0442\u044C \u043F\u043E\u0441\u043B\u0435 \u0432\u044B\u0431\u043E\u0440\u0430 \u043F\u043B\u0430\u043D\u0438\u0440\u043E\u0432\u043A\u0438."},{id:"bedroom3",title:"\u0421\u043F\u0430\u043B\u044C\u043D\u044F 3",point:[-3.55,-3.05],yaw:1.57,description:"\u0422\u0440\u0435\u0442\u044C\u044F \u0441\u043F\u0430\u043B\u044C\u043D\u044F \u0432 \u044D\u0442\u043E\u043C \u044D\u0441\u043A\u0438\u0437\u0435. \u0420\u0430\u0441\u043F\u0440\u0435\u0434\u0435\u043B\u0435\u043D\u0438\u0435 \u043A\u043E\u043C\u043D\u0430\u0442 \u043C\u0435\u0436\u0434\u0443 \u0447\u043B\u0435\u043D\u0430\u043C\u0438 \u0441\u0435\u043C\u044C\u0438 \u043D\u0435 \u0443\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043D\u043E."},{id:"bath",title:"\u0421\u0430\u043D\u0443\u0437\u0435\u043B",point:[1.5,-2.25],yaw:0,description:"\u041F\u043E\u043A\u0430\u0437\u0430\u043D\u043E \u043F\u0440\u0438\u043C\u0435\u0440\u043D\u043E\u0435 \u0440\u0430\u0441\u043F\u043E\u043B\u043E\u0436\u0435\u043D\u0438\u0435 \u0441\u0430\u043D\u0442\u0435\u0445\u043D\u0438\u043A\u0438. \u042D\u0440\u0433\u043E\u043D\u043E\u043C\u0438\u043A\u0430 \u0438 \u0438\u043D\u0436\u0435\u043D\u0435\u0440\u043D\u044B\u0435 \u043F\u043E\u0434\u043A\u043B\u044E\u0447\u0435\u043D\u0438\u044F \u0442\u0440\u0435\u0431\u0443\u044E\u0442 \u043F\u0440\u043E\u0432\u0435\u0440\u043A\u0438."},{id:"utility",title:"\u0425\u043E\u0437\u043F\u043E\u043C\u0435\u0449\u0435\u043D\u0438\u0435",point:[3.65,-2.4],yaw:0,description:"\u0417\u043E\u043D\u0430 \u0445\u043E\u0437\u044F\u0439\u0441\u0442\u0432\u0435\u043D\u043D\u043E\u0433\u043E \u043E\u0431\u043E\u0440\u0443\u0434\u043E\u0432\u0430\u043D\u0438\u044F. \u0421\u043E\u0441\u0442\u0430\u0432 \u043E\u0431\u043E\u0440\u0443\u0434\u043E\u0432\u0430\u043D\u0438\u044F \u0438 \u0442\u0440\u0435\u0431\u043E\u0432\u0430\u043D\u0438\u044F \u043A \u043F\u043E\u043C\u0435\u0449\u0435\u043D\u0438\u044E \u043F\u0440\u0435\u0434\u0441\u0442\u043E\u0438\u0442 \u0441\u043E\u0433\u043B\u0430\u0441\u043E\u0432\u0430\u0442\u044C."},{id:"office",title:"\u041A\u0430\u0431\u0438\u043D\u0435\u0442",point:[5.7,-2.25],yaw:0,description:"\u0420\u0430\u0431\u043E\u0447\u0435\u0435 \u043C\u0435\u0441\u0442\u043E \u0432 \u043E\u0442\u0434\u0435\u043B\u044C\u043D\u043E\u0439 \u043A\u043E\u043C\u043D\u0430\u0442\u0435. \u0412\u043E\u0437\u043C\u043E\u0436\u043D\u043E\u0441\u0442\u044C \u0434\u0440\u0443\u0433\u043E\u0433\u043E \u043D\u0430\u0437\u043D\u0430\u0447\u0435\u043D\u0438\u044F \u043E\u0431\u0441\u0443\u0434\u0438\u043C \u0441 \u043F\u0440\u043E\u0435\u043A\u0442\u0438\u0440\u043E\u0432\u0449\u0438\u043A\u043E\u043C."}]};function Iu(i){let e=i.radius,t=i.colliders.map(r=>({...r,minX:Math.min(...r.polygon.map(o=>o[0])),maxX:Math.max(...r.polygon.map(o=>o[0])),minZ:Math.min(...r.polygon.map(o=>o[1])),maxZ:Math.max(...r.polygon.map(o=>o[1]))}));function n(r,o){let[a,l,c,h]=i.bounds;if(r<a+e||r>l-e||o<c+e||o>h-e)return!0;for(let u of t){if(r<u.minX-e||r>u.maxX+e||o<u.minZ-e||o>u.maxZ+e)continue;let d=!1;for(let f=0,g=u.polygon.length-1;f<u.polygon.length;g=f++){let[_,m]=u.polygon[g],[p,w]=u.polygon[f];m>o!=w>o&&r<(p-_)*(o-m)/(w-m)+_&&(d=!d);let b=p-_,x=w-m,P=b*b+x*x,T=P?Math.max(0,Math.min(1,((r-_)*b+(o-m)*x)/P)):0;if((r-_-T*b)**2+(o-m-T*x)**2<e*e)return!0}if(d)return!0}return!1}function s(r,o,a){let l=Math.max(1,Math.ceil(Math.hypot(o,a)/.065)),[c,h]=r;for(let u=0;u<l;u++)n(c+o/l,h)||(c+=o/l),n(c,h+a/l)||(h+=a/l);return[c,h]}return{blocked:n,move:s,rooms:i.rooms,radius:e,eyeHeight:i.eyeHeight}}function Pu({camera:i,canvas:e,data:t,isActive:n,onChange:s}){let r=Iu(t),o=new AbortController,a={signal:o.signal},l=new Set,c=0,h=0,u=[...r.rooms[0].point],d=null,f="living",g=document.querySelector("#walk-room");g.replaceChildren();for(let x of r.rooms){let P=document.createElement("option");P.value=x.id,P.textContent=x.title,g.append(P)}function _(){i.position.set(u[0],r.eyeHeight+(t.floorHeight||0),u[1]),i.rotation.set(h,c,0,"YXZ");let[x,P]=u,T=x<-1.8?P>1.55?"bedroom1":P<-1.55?"bedroom3":"bedroom2":x<0?"hall":P<-1.3?x<2.6?"bath":x<4.6?"utility":"office":"living",A=r.rooms.find(M=>M.id===T);f=T,document.querySelector("#walk-title").textContent=A.title,document.querySelector("#walk-description").textContent=A.description,g.value=T,document.querySelector("#walk-marker").setAttribute("transform",`translate(${(x+7)*20} ${(P+5)*20}) rotate(${-c*180/Math.PI})`),s({x,z:P,yaw:c,pitch:h,room:T,eyeHeight:r.eyeHeight})}function m(x){let P=r.rooms.find(T=>T.id===x);if(P){if(r.blocked(...P.point))throw Error("Room viewpoint obstructed");u=[...P.point],c=P.yaw,h=0,l.clear(),_(),e.focus({preventScroll:!0})}}function p(x,P,T){let A=Math.hypot(x,P);if(!A)return;let R=(-Math.sin(c)*x+Math.cos(c)*P)*T/A,M=(-Math.cos(c)*x-Math.sin(c)*P)*T/A;u=r.move(u,R,M),_()}let w={KeyW:[1,0],ArrowUp:[1,0],KeyS:[-1,0],ArrowDown:[-1,0],KeyA:[0,-1],ArrowLeft:[0,-1],KeyD:[0,1],ArrowRight:[0,1]},b=()=>{l.clear(),d=null};window.addEventListener("keydown",x=>{!n()||/INPUT|TEXTAREA|SELECT/.test(x.target.tagName)||x.target.isContentEditable||w[x.code]&&(x.preventDefault(),l.add(x.code))},a),window.addEventListener("keyup",x=>l.delete(x.code),a),window.addEventListener("blur",b,a),document.addEventListener("visibilitychange",()=>{document.hidden&&b()},a),e.tabIndex=0,e.addEventListener("pointerdown",x=>{n()&&(d={id:x.pointerId,x:x.clientX,y:x.clientY},e.setPointerCapture(x.pointerId),e.focus({preventScroll:!0}))},a),e.addEventListener("pointermove",x=>{!n()||!d||d.id!==x.pointerId||(c-=(x.clientX-d.x)*.004,h=Math.max(-1.05,Math.min(1.05,h-(x.clientY-d.y)*.003)),d.x=x.clientX,d.y=x.clientY,_())},a);for(let x of["pointerup","pointercancel","lostpointercapture"])e.addEventListener(x,()=>{d=null},a);for(let x of document.querySelectorAll("[data-walk-key]")){let P=0;x.addEventListener("pointerdown",T=>{n()&&(T.preventDefault(),P=performance.now(),l.add(x.dataset.walkKey),x.setPointerCapture(T.pointerId))},a);for(let T of["pointerup","pointercancel","lostpointercapture"])x.addEventListener(T,()=>l.delete(x.dataset.walkKey),a);x.addEventListener("click",T=>{if(n()&&(T.detail===0||performance.now()-P<180)){let[A,R]=w[x.dataset.walkKey];p(A,R,.28)}},a)}return g.addEventListener("change",()=>{n()&&m(g.value)},a),{enter(){m(f)},leave:b,update(x){if(!n())return;let P=0,T=0;for(let A of l){let R=w[A];R&&(P+=R[0],T+=R[1])}(P||T)&&p(P,T,Math.min(.12,x)*1.45)},dispose(){b(),o.abort()}}}var Lu={warm:{title:"\u0422\u0451\u043F\u043B\u044B\u0439 \u0441\u043E\u0432\u0440\u0435\u043C\u0435\u043D\u043D\u044B\u0439",description:"\u0414\u0440\u0435\u0432\u0435\u0441\u043D\u044B\u0435 \u0444\u0430\u043A\u0442\u0443\u0440\u044B, \u0441\u043F\u043E\u043A\u043E\u0439\u043D\u044B\u0439 \u0437\u0435\u043B\u0451\u043D\u044B\u0439 \u0438 \u043C\u044F\u0433\u043A\u0438\u0435 \u043D\u0430\u0442\u0443\u0440\u0430\u043B\u044C\u043D\u044B\u0435 \u043E\u0442\u0442\u0435\u043D\u043A\u0438.",colors:{white:15196627,linen:13286822,fabric:9929585,sage:6714973,oak:11964001,"light oak":14271906},light:16770243},minimal:{title:"\u0421\u0432\u0435\u0442\u043B\u044B\u0439 \u043C\u0438\u043D\u0438\u043C\u0430\u043B\u0438\u0437\u043C",description:"\u0421\u0432\u0435\u0442\u043B\u044B\u0435 \u043F\u043E\u0432\u0435\u0440\u0445\u043D\u043E\u0441\u0442\u0438, \u0441\u0434\u0435\u0440\u0436\u0430\u043D\u043D\u044B\u0435 \u043A\u043E\u043D\u0442\u0440\u0430\u0441\u0442\u044B \u0438 \u0431\u043E\u043B\u0435\u0435 \u0441\u043F\u043E\u043A\u043E\u0439\u043D\u0430\u044F \u0444\u0430\u043A\u0442\u0443\u0440\u0430 \u0434\u0435\u0440\u0435\u0432\u0430.",colors:{white:15921384,linen:14211537,fabric:11844273,sage:13685962,oak:13683127,"light oak":15261644},light:16249573},classic:{title:"\u0421\u043E\u0432\u0440\u0435\u043C\u0435\u043D\u043D\u0430\u044F \u043A\u043B\u0430\u0441\u0441\u0438\u043A\u0430",description:"\u0422\u0451\u043F\u043B\u044B\u0435 \u0441\u0432\u0435\u0442\u043B\u044B\u0435 \u0441\u0442\u0435\u043D\u044B, \u0442\u0451\u043C\u043D\u043E\u0435 \u0434\u0435\u0440\u0435\u0432\u043E, \u0442\u043E\u043D\u043A\u0438\u0435 \u043C\u043E\u043B\u0434\u0438\u043D\u0433\u0438 \u0438 \u043B\u0430\u0442\u0443\u043D\u043D\u044B\u0435 \u0430\u043A\u0446\u0435\u043D\u0442\u044B.",colors:{white:15525076,linen:14206637,fabric:8225404,sage:11907488,oak:7757900,"light oak":12429965},light:16768949}};function Du(i,e){let t=[],n=new Map,s=new Dt;s.name="interior style details",i.add(s);for(let A of["07_interior","03_walls"])i.getObjectByName(A).traverse(R=>{if(!R.isMesh)return;let M=Array.isArray(R.material)?R.material:[R.material];A==="03_walls"&&!M.every(v=>["white","light oak"].includes(v.name))||t.push({object:R,original:R.material,materials:M,array:Array.isArray(R.material)})});let r=new Dt,o=new Dt;s.add(r,o);let a=new kt({color:15128765,roughness:.6}),l=new kt({color:11308368,metalness:.75,roughness:.32}),c=new kt({color:9072719,roughness:.65});function h(A,R,M,v,I,G,O,X){let Y=new tt(new qn(I,G,O),X);return Y.position.set(R,M,v),A.add(Y),Y}for(let[A,R]of[[.38,.46],[2.1,.5],[4.3,.3],[6.6,.32]]){for(let M of[.45,2.25])h(r,A,M,-1.222,R,.025,.022,a);for(let M of[-R/2,R/2])h(r,A+M,1.35,-1.222,.025,1.8,.022,a)}for(let[A,R]of[[5.7,.75],[2.1,.75],[4.7,3.1]]){let M=new tt(new fo(.235,.012,6,32),l);M.rotation.x=Math.PI/2,M.position.set(A,2.17,R),r.add(M)}for(let A=0;A<9;A++)h(o,4.15+A*.034,1.45,-1.216,.014,2.35,.018,c);let u=[],d=[],f=[];function g(A,R,M,v){let I=[];for(let G=0;G<A.length;G++){let O=A[G],X=A[(G+1)%A.length],Y=v*(O[R]-M)>=0,V=v*(X[R]-M)>=0;if(Y&&I.push(O),Y!==V){let Q=(M-O[R])/(X[R]-O[R]);I.push(O.map((B,H)=>B+(X[H]-B)*Q))}}return I}for(let A=-60;A<60;A++)for(let R=-60;R<60;R++){let M=((A+R)%8+8)%8;if(M!==0&&M!==4)continue;let v=M===0?.52:.13,I=M===0?.13:.52,G=Math.PI/4,O=Math.cos(G),X=Math.sin(G),Y=.0015,V=[[Y,Y],[v-Y,Y],[v-Y,I-Y],[Y,I-Y]].map(([B,H])=>{let j=A*.13+B,ie=R*.13+H;return[3+j*O-ie*X,1.8+j*X+ie*O,B/v,H/I]});for(let[B,H,j]of[[0,.03,1],[0,6.84,-1],[1,-1.21,1],[1,4.84,-1]])if(V=g(V,B,H,j),V.length<3)break;if(V.length<3)continue;let Q=.7+Math.abs(Math.sin(A*37+R*19))*.25;for(let B=1;B<V.length-1;B++)for(let H of[V[0],V[B],V[B+1]])u.push(H[0],.058,H[1]),d.push(H[2],H[3]),f.push(Q,Q*.96,Q*.88)}let _=new yt;_.setAttribute("position",new dt(u,3)),_.setAttribute("uv",new dt(d,2)),_.setAttribute("color",new dt(f,3)),_.computeVertexNormals();let m=i.getObjectByName("07_interior").children.find(A=>A.material?.name==="light oak")?.material,p=new kt({color:11903104,map:m?.map,vertexColors:!0,roughness:.6,side:Jt}),w=new tt(_,p);w.name="classic herringbone finish",w.receiveShadow=!0,r.add(w);let b=[];for(let[A,R]of[[2.1,.75],[5.7,.75],[-.8,0]]){let M=new Ms(16770243,11,10,2);M.position.set(A,2.65,R),e.add(M),b.push(M)}let x="warm";function P(A){if(!Lu[A])throw Error("Unknown interior style");x=A;let R=Lu[A];for(let M of t){let v=M.materials.map(I=>{let G=A+":"+I.uuid;if(!n.has(G)){let O=I.clone();O.name="interior "+A+" / "+I.name,R.colors[I.name]&&O.color.setHex(R.colors[I.name]),A==="minimal"&&["oak","light oak"].includes(I.name)&&(O.color.setHex(R.colors[I.name]),O.roughness=.7,O.onBeforeCompile=X=>{X.fragmentShader=X.fragmentShader.replace("#include <map_fragment>",`#include <map_fragment>
diffuseColor.rgb=mix(diffuseColor.rgb,vec3(0.65,0.62,0.56),0.45);`)},O.customProgramCacheKey=()=>"stroyka-light-wood-v1"),n.set(G,O)}return n.get(G)});M.object.material=M.array?v:v[0]}r.visible=A==="classic",o.visible=A==="warm";for(let M of b)M.color.setHex(R.light);return R}function T(){for(let A of n.values())A.dispose();n.clear()}return{apply:P,dispose:T,get current(){return x},get materialCount(){return n.size}}}var Uu={type:"change"},Wl={type:"start"},Ou={type:"end"},To=new Xn,Nu=new Kt,f_=Math.cos(70*en.DEG2RAD),St=new C,Wt=2*Math.PI,et={NONE:-1,ROTATE:0,DOLLY:1,PAN:2,TOUCH_ROTATE:3,TOUCH_PAN:4,TOUCH_DOLLY_PAN:5,TOUCH_DOLLY_ROTATE:6},Gl=1e-6,Ro=class extends So{constructor(e,t=null){super(e,t),this.state=et.NONE,this.enabled=!0,this.target=new C,this.cursor=new C,this.minDistance=0,this.maxDistance=1/0,this.minZoom=0,this.maxZoom=1/0,this.minTargetRadius=0,this.maxTargetRadius=1/0,this.minPolarAngle=0,this.maxPolarAngle=Math.PI,this.minAzimuthAngle=-1/0,this.maxAzimuthAngle=1/0,this.enableDamping=!1,this.dampingFactor=.05,this.enableZoom=!0,this.zoomSpeed=1,this.enableRotate=!0,this.rotateSpeed=1,this.enablePan=!0,this.panSpeed=1,this.screenSpacePanning=!0,this.keyPanSpeed=7,this.zoomToCursor=!1,this.autoRotate=!1,this.autoRotateSpeed=2,this.keys={LEFT:"ArrowLeft",UP:"ArrowUp",RIGHT:"ArrowRight",BOTTOM:"ArrowDown"},this.mouseButtons={LEFT:Ui.ROTATE,MIDDLE:Ui.DOLLY,RIGHT:Ui.PAN},this.touches={ONE:Ni.ROTATE,TWO:Ni.DOLLY_PAN},this.target0=this.target.clone(),this.position0=this.object.position.clone(),this.zoom0=this.object.zoom,this._domElementKeyEvents=null,this._lastPosition=new C,this._lastQuaternion=new Gt,this._lastTargetPosition=new C,this._quat=new Gt().setFromUnitVectors(e.up,new C(0,1,0)),this._quatInverse=this._quat.clone().invert(),this._spherical=new er,this._sphericalDelta=new er,this._scale=1,this._panOffset=new C,this._rotateStart=new we,this._rotateEnd=new we,this._rotateDelta=new we,this._panStart=new we,this._panEnd=new we,this._panDelta=new we,this._dollyStart=new we,this._dollyEnd=new we,this._dollyDelta=new we,this._dollyDirection=new C,this._mouse=new we,this._performCursorZoom=!1,this._pointers=[],this._pointerPositions={},this._controlActive=!1,this._onPointerMove=m_.bind(this),this._onPointerDown=p_.bind(this),this._onPointerUp=g_.bind(this),this._onContextMenu=b_.bind(this),this._onMouseWheel=y_.bind(this),this._onKeyDown=v_.bind(this),this._onTouchStart=M_.bind(this),this._onTouchMove=S_.bind(this),this._onMouseDown=__.bind(this),this._onMouseMove=x_.bind(this),this._interceptControlDown=w_.bind(this),this._interceptControlUp=E_.bind(this),this.domElement!==null&&this.connect(),this.update()}connect(){this.domElement.addEventListener("pointerdown",this._onPointerDown),this.domElement.addEventListener("pointercancel",this._onPointerUp),this.domElement.addEventListener("contextmenu",this._onContextMenu),this.domElement.addEventListener("wheel",this._onMouseWheel,{passive:!1}),this.domElement.getRootNode().addEventListener("keydown",this._interceptControlDown,{passive:!0,capture:!0}),this.domElement.style.touchAction="none"}disconnect(){this.domElement.removeEventListener("pointerdown",this._onPointerDown),this.domElement.removeEventListener("pointermove",this._onPointerMove),this.domElement.removeEventListener("pointerup",this._onPointerUp),this.domElement.removeEventListener("pointercancel",this._onPointerUp),this.domElement.removeEventListener("wheel",this._onMouseWheel),this.domElement.removeEventListener("contextmenu",this._onContextMenu),this.stopListenToKeyEvents(),this.domElement.getRootNode().removeEventListener("keydown",this._interceptControlDown,{capture:!0}),this.domElement.style.touchAction="auto"}dispose(){this.disconnect()}getPolarAngle(){return this._spherical.phi}getAzimuthalAngle(){return this._spherical.theta}getDistance(){return this.object.position.distanceTo(this.target)}listenToKeyEvents(e){e.addEventListener("keydown",this._onKeyDown),this._domElementKeyEvents=e}stopListenToKeyEvents(){this._domElementKeyEvents!==null&&(this._domElementKeyEvents.removeEventListener("keydown",this._onKeyDown),this._domElementKeyEvents=null)}saveState(){this.target0.copy(this.target),this.position0.copy(this.object.position),this.zoom0=this.object.zoom}reset(){this.target.copy(this.target0),this.object.position.copy(this.position0),this.object.zoom=this.zoom0,this.object.updateProjectionMatrix(),this.dispatchEvent(Uu),this.update(),this.state=et.NONE}update(e=null){let t=this.object.position;St.copy(t).sub(this.target),St.applyQuaternion(this._quat),this._spherical.setFromVector3(St),this.autoRotate&&this.state===et.NONE&&this._rotateLeft(this._getAutoRotationAngle(e)),this.enableDamping?(this._spherical.theta+=this._sphericalDelta.theta*this.dampingFactor,this._spherical.phi+=this._sphericalDelta.phi*this.dampingFactor):(this._spherical.theta+=this._sphericalDelta.theta,this._spherical.phi+=this._sphericalDelta.phi);let n=this.minAzimuthAngle,s=this.maxAzimuthAngle;isFinite(n)&&isFinite(s)&&(n<-Math.PI?n+=Wt:n>Math.PI&&(n-=Wt),s<-Math.PI?s+=Wt:s>Math.PI&&(s-=Wt),n<=s?this._spherical.theta=Math.max(n,Math.min(s,this._spherical.theta)):this._spherical.theta=this._spherical.theta>(n+s)/2?Math.max(n,this._spherical.theta):Math.min(s,this._spherical.theta)),this._spherical.phi=Math.max(this.minPolarAngle,Math.min(this.maxPolarAngle,this._spherical.phi)),this._spherical.makeSafe(),this.enableDamping===!0?this.target.addScaledVector(this._panOffset,this.dampingFactor):this.target.add(this._panOffset),this.target.sub(this.cursor),this.target.clampLength(this.minTargetRadius,this.maxTargetRadius),this.target.add(this.cursor);let r=!1;if(this.zoomToCursor&&this._performCursorZoom||this.object.isOrthographicCamera)this._spherical.radius=this._clampDistance(this._spherical.radius);else{let o=this._spherical.radius;this._spherical.radius=this._clampDistance(this._spherical.radius*this._scale),r=o!=this._spherical.radius}if(St.setFromSpherical(this._spherical),St.applyQuaternion(this._quatInverse),t.copy(this.target).add(St),this.object.lookAt(this.target),this.enableDamping===!0?(this._sphericalDelta.theta*=1-this.dampingFactor,this._sphericalDelta.phi*=1-this.dampingFactor,this._panOffset.multiplyScalar(1-this.dampingFactor)):(this._sphericalDelta.set(0,0,0),this._panOffset.set(0,0,0)),this.zoomToCursor&&this._performCursorZoom){let o=null;if(this.object.isPerspectiveCamera){let a=St.length();o=this._clampDistance(a*this._scale);let l=a-o;this.object.position.addScaledVector(this._dollyDirection,l),this.object.updateMatrixWorld(),r=!!l}else if(this.object.isOrthographicCamera){let a=new C(this._mouse.x,this._mouse.y,0);a.unproject(this.object);let l=this.object.zoom;this.object.zoom=Math.max(this.minZoom,Math.min(this.maxZoom,this.object.zoom/this._scale)),this.object.updateProjectionMatrix(),r=l!==this.object.zoom;let c=new C(this._mouse.x,this._mouse.y,0);c.unproject(this.object),this.object.position.sub(c).add(a),this.object.updateMatrixWorld(),o=St.length()}else console.warn("WARNING: OrbitControls.js encountered an unknown camera type - zoom to cursor disabled."),this.zoomToCursor=!1;o!==null&&(this.screenSpacePanning?this.target.set(0,0,-1).transformDirection(this.object.matrix).multiplyScalar(o).add(this.object.position):(To.origin.copy(this.object.position),To.direction.set(0,0,-1).transformDirection(this.object.matrix),Math.abs(this.object.up.dot(To.direction))<f_?this.object.lookAt(this.target):(Nu.setFromNormalAndCoplanarPoint(this.object.up,this.target),To.intersectPlane(Nu,this.target))))}else if(this.object.isOrthographicCamera){let o=this.object.zoom;this.object.zoom=Math.max(this.minZoom,Math.min(this.maxZoom,this.object.zoom/this._scale)),o!==this.object.zoom&&(this.object.updateProjectionMatrix(),r=!0)}return this._scale=1,this._performCursorZoom=!1,r||this._lastPosition.distanceToSquared(this.object.position)>Gl||8*(1-this._lastQuaternion.dot(this.object.quaternion))>Gl||this._lastTargetPosition.distanceToSquared(this.target)>Gl?(this.dispatchEvent(Uu),this._lastPosition.copy(this.object.position),this._lastQuaternion.copy(this.object.quaternion),this._lastTargetPosition.copy(this.target),!0):!1}_getAutoRotationAngle(e){return e!==null?Wt/60*this.autoRotateSpeed*e:Wt/60/60*this.autoRotateSpeed}_getZoomScale(e){let t=Math.abs(e*.01);return Math.pow(.95,this.zoomSpeed*t)}_rotateLeft(e){this._sphericalDelta.theta-=e}_rotateUp(e){this._sphericalDelta.phi-=e}_panLeft(e,t){St.setFromMatrixColumn(t,0),St.multiplyScalar(-e),this._panOffset.add(St)}_panUp(e,t){this.screenSpacePanning===!0?St.setFromMatrixColumn(t,1):(St.setFromMatrixColumn(t,0),St.crossVectors(this.object.up,St)),St.multiplyScalar(e),this._panOffset.add(St)}_pan(e,t){let n=this.domElement;if(this.object.isPerspectiveCamera){let s=this.object.position;St.copy(s).sub(this.target);let r=St.length();r*=Math.tan(this.object.fov/2*Math.PI/180),this._panLeft(2*e*r/n.clientHeight,this.object.matrix),this._panUp(2*t*r/n.clientHeight,this.object.matrix)}else this.object.isOrthographicCamera?(this._panLeft(e*(this.object.right-this.object.left)/this.object.zoom/n.clientWidth,this.object.matrix),this._panUp(t*(this.object.top-this.object.bottom)/this.object.zoom/n.clientHeight,this.object.matrix)):(console.warn("WARNING: OrbitControls.js encountered an unknown camera type - pan disabled."),this.enablePan=!1)}_dollyOut(e){this.object.isPerspectiveCamera||this.object.isOrthographicCamera?this._scale/=e:(console.warn("WARNING: OrbitControls.js encountered an unknown camera type - dolly/zoom disabled."),this.enableZoom=!1)}_dollyIn(e){this.object.isPerspectiveCamera||this.object.isOrthographicCamera?this._scale*=e:(console.warn("WARNING: OrbitControls.js encountered an unknown camera type - dolly/zoom disabled."),this.enableZoom=!1)}_updateZoomParameters(e,t){if(!this.zoomToCursor)return;this._performCursorZoom=!0;let n=this.domElement.getBoundingClientRect(),s=e-n.left,r=t-n.top,o=n.width,a=n.height;this._mouse.x=s/o*2-1,this._mouse.y=-(r/a)*2+1,this._dollyDirection.set(this._mouse.x,this._mouse.y,1).unproject(this.object).sub(this.object.position).normalize()}_clampDistance(e){return Math.max(this.minDistance,Math.min(this.maxDistance,e))}_handleMouseDownRotate(e){this._rotateStart.set(e.clientX,e.clientY)}_handleMouseDownDolly(e){this._updateZoomParameters(e.clientX,e.clientX),this._dollyStart.set(e.clientX,e.clientY)}_handleMouseDownPan(e){this._panStart.set(e.clientX,e.clientY)}_handleMouseMoveRotate(e){this._rotateEnd.set(e.clientX,e.clientY),this._rotateDelta.subVectors(this._rotateEnd,this._rotateStart).multiplyScalar(this.rotateSpeed);let t=this.domElement;this._rotateLeft(Wt*this._rotateDelta.x/t.clientHeight),this._rotateUp(Wt*this._rotateDelta.y/t.clientHeight),this._rotateStart.copy(this._rotateEnd),this.update()}_handleMouseMoveDolly(e){this._dollyEnd.set(e.clientX,e.clientY),this._dollyDelta.subVectors(this._dollyEnd,this._dollyStart),this._dollyDelta.y>0?this._dollyOut(this._getZoomScale(this._dollyDelta.y)):this._dollyDelta.y<0&&this._dollyIn(this._getZoomScale(this._dollyDelta.y)),this._dollyStart.copy(this._dollyEnd),this.update()}_handleMouseMovePan(e){this._panEnd.set(e.clientX,e.clientY),this._panDelta.subVectors(this._panEnd,this._panStart).multiplyScalar(this.panSpeed),this._pan(this._panDelta.x,this._panDelta.y),this._panStart.copy(this._panEnd),this.update()}_handleMouseWheel(e){this._updateZoomParameters(e.clientX,e.clientY),e.deltaY<0?this._dollyIn(this._getZoomScale(e.deltaY)):e.deltaY>0&&this._dollyOut(this._getZoomScale(e.deltaY)),this.update()}_handleKeyDown(e){let t=!1;switch(e.code){case this.keys.UP:e.ctrlKey||e.metaKey||e.shiftKey?this._rotateUp(Wt*this.rotateSpeed/this.domElement.clientHeight):this._pan(0,this.keyPanSpeed),t=!0;break;case this.keys.BOTTOM:e.ctrlKey||e.metaKey||e.shiftKey?this._rotateUp(-Wt*this.rotateSpeed/this.domElement.clientHeight):this._pan(0,-this.keyPanSpeed),t=!0;break;case this.keys.LEFT:e.ctrlKey||e.metaKey||e.shiftKey?this._rotateLeft(Wt*this.rotateSpeed/this.domElement.clientHeight):this._pan(this.keyPanSpeed,0),t=!0;break;case this.keys.RIGHT:e.ctrlKey||e.metaKey||e.shiftKey?this._rotateLeft(-Wt*this.rotateSpeed/this.domElement.clientHeight):this._pan(-this.keyPanSpeed,0),t=!0;break}t&&(e.preventDefault(),this.update())}_handleTouchStartRotate(e){if(this._pointers.length===1)this._rotateStart.set(e.pageX,e.pageY);else{let t=this._getSecondPointerPosition(e),n=.5*(e.pageX+t.x),s=.5*(e.pageY+t.y);this._rotateStart.set(n,s)}}_handleTouchStartPan(e){if(this._pointers.length===1)this._panStart.set(e.pageX,e.pageY);else{let t=this._getSecondPointerPosition(e),n=.5*(e.pageX+t.x),s=.5*(e.pageY+t.y);this._panStart.set(n,s)}}_handleTouchStartDolly(e){let t=this._getSecondPointerPosition(e),n=e.pageX-t.x,s=e.pageY-t.y,r=Math.sqrt(n*n+s*s);this._dollyStart.set(0,r)}_handleTouchStartDollyPan(e){this.enableZoom&&this._handleTouchStartDolly(e),this.enablePan&&this._handleTouchStartPan(e)}_handleTouchStartDollyRotate(e){this.enableZoom&&this._handleTouchStartDolly(e),this.enableRotate&&this._handleTouchStartRotate(e)}_handleTouchMoveRotate(e){if(this._pointers.length==1)this._rotateEnd.set(e.pageX,e.pageY);else{let n=this._getSecondPointerPosition(e),s=.5*(e.pageX+n.x),r=.5*(e.pageY+n.y);this._rotateEnd.set(s,r)}this._rotateDelta.subVectors(this._rotateEnd,this._rotateStart).multiplyScalar(this.rotateSpeed);let t=this.domElement;this._rotateLeft(Wt*this._rotateDelta.x/t.clientHeight),this._rotateUp(Wt*this._rotateDelta.y/t.clientHeight),this._rotateStart.copy(this._rotateEnd)}_handleTouchMovePan(e){if(this._pointers.length===1)this._panEnd.set(e.pageX,e.pageY);else{let t=this._getSecondPointerPosition(e),n=.5*(e.pageX+t.x),s=.5*(e.pageY+t.y);this._panEnd.set(n,s)}this._panDelta.subVectors(this._panEnd,this._panStart).multiplyScalar(this.panSpeed),this._pan(this._panDelta.x,this._panDelta.y),this._panStart.copy(this._panEnd)}_handleTouchMoveDolly(e){let t=this._getSecondPointerPosition(e),n=e.pageX-t.x,s=e.pageY-t.y,r=Math.sqrt(n*n+s*s);this._dollyEnd.set(0,r),this._dollyDelta.set(0,Math.pow(this._dollyEnd.y/this._dollyStart.y,this.zoomSpeed)),this._dollyOut(this._dollyDelta.y),this._dollyStart.copy(this._dollyEnd);let o=(e.pageX+t.x)*.5,a=(e.pageY+t.y)*.5;this._updateZoomParameters(o,a)}_handleTouchMoveDollyPan(e){this.enableZoom&&this._handleTouchMoveDolly(e),this.enablePan&&this._handleTouchMovePan(e)}_handleTouchMoveDollyRotate(e){this.enableZoom&&this._handleTouchMoveDolly(e),this.enableRotate&&this._handleTouchMoveRotate(e)}_addPointer(e){this._pointers.push(e.pointerId)}_removePointer(e){delete this._pointerPositions[e.pointerId];for(let t=0;t<this._pointers.length;t++)if(this._pointers[t]==e.pointerId){this._pointers.splice(t,1);return}}_isTrackingPointer(e){for(let t=0;t<this._pointers.length;t++)if(this._pointers[t]==e.pointerId)return!0;return!1}_trackPointer(e){let t=this._pointerPositions[e.pointerId];t===void 0&&(t=new we,this._pointerPositions[e.pointerId]=t),t.set(e.pageX,e.pageY)}_getSecondPointerPosition(e){let t=e.pointerId===this._pointers[0]?this._pointers[1]:this._pointers[0];return this._pointerPositions[t]}_customWheelEvent(e){let t=e.deltaMode,n={clientX:e.clientX,clientY:e.clientY,deltaY:e.deltaY};switch(t){case 1:n.deltaY*=16;break;case 2:n.deltaY*=100;break}return e.ctrlKey&&!this._controlActive&&(n.deltaY*=10),n}};function p_(i){this.enabled!==!1&&(this._pointers.length===0&&(this.domElement.setPointerCapture(i.pointerId),this.domElement.addEventListener("pointermove",this._onPointerMove),this.domElement.addEventListener("pointerup",this._onPointerUp)),!this._isTrackingPointer(i)&&(this._addPointer(i),i.pointerType==="touch"?this._onTouchStart(i):this._onMouseDown(i)))}function m_(i){this.enabled!==!1&&(i.pointerType==="touch"?this._onTouchMove(i):this._onMouseMove(i))}function g_(i){switch(this._removePointer(i),this._pointers.length){case 0:this.domElement.releasePointerCapture(i.pointerId),this.domElement.removeEventListener("pointermove",this._onPointerMove),this.domElement.removeEventListener("pointerup",this._onPointerUp),this.dispatchEvent(Ou),this.state=et.NONE;break;case 1:let e=this._pointers[0],t=this._pointerPositions[e];this._onTouchStart({pointerId:e,pageX:t.x,pageY:t.y});break}}function __(i){let e;switch(i.button){case 0:e=this.mouseButtons.LEFT;break;case 1:e=this.mouseButtons.MIDDLE;break;case 2:e=this.mouseButtons.RIGHT;break;default:e=-1}switch(e){case Ui.DOLLY:if(this.enableZoom===!1)return;this._handleMouseDownDolly(i),this.state=et.DOLLY;break;case Ui.ROTATE:if(i.ctrlKey||i.metaKey||i.shiftKey){if(this.enablePan===!1)return;this._handleMouseDownPan(i),this.state=et.PAN}else{if(this.enableRotate===!1)return;this._handleMouseDownRotate(i),this.state=et.ROTATE}break;case Ui.PAN:if(i.ctrlKey||i.metaKey||i.shiftKey){if(this.enableRotate===!1)return;this._handleMouseDownRotate(i),this.state=et.ROTATE}else{if(this.enablePan===!1)return;this._handleMouseDownPan(i),this.state=et.PAN}break;default:this.state=et.NONE}this.state!==et.NONE&&this.dispatchEvent(Wl)}function x_(i){switch(this.state){case et.ROTATE:if(this.enableRotate===!1)return;this._handleMouseMoveRotate(i);break;case et.DOLLY:if(this.enableZoom===!1)return;this._handleMouseMoveDolly(i);break;case et.PAN:if(this.enablePan===!1)return;this._handleMouseMovePan(i);break}}function y_(i){this.enabled===!1||this.enableZoom===!1||this.state!==et.NONE||(i.preventDefault(),this.dispatchEvent(Wl),this._handleMouseWheel(this._customWheelEvent(i)),this.dispatchEvent(Ou))}function v_(i){this.enabled===!1||this.enablePan===!1||this._handleKeyDown(i)}function M_(i){switch(this._trackPointer(i),this._pointers.length){case 1:switch(this.touches.ONE){case Ni.ROTATE:if(this.enableRotate===!1)return;this._handleTouchStartRotate(i),this.state=et.TOUCH_ROTATE;break;case Ni.PAN:if(this.enablePan===!1)return;this._handleTouchStartPan(i),this.state=et.TOUCH_PAN;break;default:this.state=et.NONE}break;case 2:switch(this.touches.TWO){case Ni.DOLLY_PAN:if(this.enableZoom===!1&&this.enablePan===!1)return;this._handleTouchStartDollyPan(i),this.state=et.TOUCH_DOLLY_PAN;break;case Ni.DOLLY_ROTATE:if(this.enableZoom===!1&&this.enableRotate===!1)return;this._handleTouchStartDollyRotate(i),this.state=et.TOUCH_DOLLY_ROTATE;break;default:this.state=et.NONE}break;default:this.state=et.NONE}this.state!==et.NONE&&this.dispatchEvent(Wl)}function S_(i){switch(this._trackPointer(i),this.state){case et.TOUCH_ROTATE:if(this.enableRotate===!1)return;this._handleTouchMoveRotate(i),this.update();break;case et.TOUCH_PAN:if(this.enablePan===!1)return;this._handleTouchMovePan(i),this.update();break;case et.TOUCH_DOLLY_PAN:if(this.enableZoom===!1&&this.enablePan===!1)return;this._handleTouchMoveDollyPan(i),this.update();break;case et.TOUCH_DOLLY_ROTATE:if(this.enableZoom===!1&&this.enableRotate===!1)return;this._handleTouchMoveDollyRotate(i),this.update();break;default:this.state=et.NONE}}function b_(i){this.enabled!==!1&&i.preventDefault()}function w_(i){i.key==="Control"&&(this._controlActive=!0,this.domElement.getRootNode().addEventListener("keyup",this._interceptControlUp,{passive:!0,capture:!0}))}function E_(i){i.key==="Control"&&(this._controlActive=!1,this.domElement.getRootNode().removeEventListener("keyup",this._interceptControlUp,{passive:!0,capture:!0}))}function Xl(i,e){if(e===mu)return console.warn("THREE.BufferGeometryUtils.toTrianglesDrawMode(): Geometry already defined as triangles."),i;if(e===nr||e===wo){let t=i.getIndex();if(t===null){let o=[],a=i.getAttribute("position");if(a!==void 0){for(let l=0;l<a.count;l++)o.push(l);i.setIndex(o),t=i.getIndex()}else return console.error("THREE.BufferGeometryUtils.toTrianglesDrawMode(): Undefined position attribute. Processing not possible."),i}let n=t.count-2,s=[];if(e===nr)for(let o=1;o<=n;o++)s.push(t.getX(0)),s.push(t.getX(o)),s.push(t.getX(o+1));else for(let o=0;o<n;o++)o%2===0?(s.push(t.getX(o)),s.push(t.getX(o+1)),s.push(t.getX(o+2))):(s.push(t.getX(o+2)),s.push(t.getX(o+1)),s.push(t.getX(o)));s.length/3!==n&&console.error("THREE.BufferGeometryUtils.toTrianglesDrawMode(): Unable to generate correct amount of triangles.");let r=i.clone();return r.setIndex(s),r.clearGroups(),r}else return console.error("THREE.BufferGeometryUtils.toTrianglesDrawMode(): Unknown draw mode:",e),i}var sr=class extends jn{constructor(e){super(e),this.dracoLoader=null,this.ktx2Loader=null,this.meshoptDecoder=null,this.pluginCallbacks=[],this.register(function(t){return new $l(t)}),this.register(function(t){return new Ql(t)}),this.register(function(t){return new lc(t)}),this.register(function(t){return new cc(t)}),this.register(function(t){return new hc(t)}),this.register(function(t){return new tc(t)}),this.register(function(t){return new nc(t)}),this.register(function(t){return new ic(t)}),this.register(function(t){return new sc(t)}),this.register(function(t){return new jl(t)}),this.register(function(t){return new rc(t)}),this.register(function(t){return new ec(t)}),this.register(function(t){return new ac(t)}),this.register(function(t){return new oc(t)}),this.register(function(t){return new Kl(t)}),this.register(function(t){return new uc(t)}),this.register(function(t){return new dc(t)})}load(e,t,n,s){let r=this,o;if(this.resourcePath!=="")o=this.resourcePath;else if(this.path!==""){let c=_i.extractUrlBase(e);o=_i.resolveURL(c,this.path)}else o=_i.extractUrlBase(e);this.manager.itemStart(e);let a=function(c){s?s(c):console.error(c),r.manager.itemError(e),r.manager.itemEnd(e)},l=new $s(this.manager);l.setPath(this.path),l.setResponseType("arraybuffer"),l.setRequestHeader(this.requestHeader),l.setWithCredentials(this.withCredentials),l.load(e,function(c){try{r.parse(c,o,function(h){t(h),r.manager.itemEnd(e)},a)}catch(h){a(h)}},n,a)}setDRACOLoader(e){return this.dracoLoader=e,this}setKTX2Loader(e){return this.ktx2Loader=e,this}setMeshoptDecoder(e){return this.meshoptDecoder=e,this}register(e){return this.pluginCallbacks.indexOf(e)===-1&&this.pluginCallbacks.push(e),this}unregister(e){return this.pluginCallbacks.indexOf(e)!==-1&&this.pluginCallbacks.splice(this.pluginCallbacks.indexOf(e),1),this}parse(e,t,n,s){let r,o={},a={},l=new TextDecoder;if(typeof e=="string")r=JSON.parse(e);else if(e instanceof ArrayBuffer)if(l.decode(new Uint8Array(e,0,4))===Hu){try{o[ze.KHR_BINARY_GLTF]=new fc(e)}catch(u){s&&s(u);return}r=JSON.parse(o[ze.KHR_BINARY_GLTF].content)}else r=JSON.parse(l.decode(e));else r=e;if(r.asset===void 0||r.asset.version[0]<2){s&&s(new Error("THREE.GLTFLoader: Unsupported asset. glTF versions >=2.0 are supported."));return}let c=new vc(r,{path:t||this.resourcePath||"",crossOrigin:this.crossOrigin,requestHeader:this.requestHeader,manager:this.manager,ktx2Loader:this.ktx2Loader,meshoptDecoder:this.meshoptDecoder});c.fileLoader.setRequestHeader(this.requestHeader);for(let h=0;h<this.pluginCallbacks.length;h++){let u=this.pluginCallbacks[h](c);u.name||console.error("THREE.GLTFLoader: Invalid plugin found: missing name"),a[u.name]=u,o[u.name]=!0}if(r.extensionsUsed)for(let h=0;h<r.extensionsUsed.length;++h){let u=r.extensionsUsed[h],d=r.extensionsRequired||[];switch(u){case ze.KHR_MATERIALS_UNLIT:o[u]=new Jl;break;case ze.KHR_DRACO_MESH_COMPRESSION:o[u]=new pc(r,this.dracoLoader);break;case ze.KHR_TEXTURE_TRANSFORM:o[u]=new mc;break;case ze.KHR_MESH_QUANTIZATION:o[u]=new gc;break;default:d.indexOf(u)>=0&&a[u]===void 0&&console.warn('THREE.GLTFLoader: Unknown extension "'+u+'".')}}c.setExtensions(o),c.setPlugins(a),c.parse(n,s)}parseAsync(e,t){let n=this;return new Promise(function(s,r){n.parse(e,t,s,r)})}};function A_(){let i={};return{get:function(e){return i[e]},add:function(e,t){i[e]=t},remove:function(e){delete i[e]},removeAll:function(){i={}}}}var ze={KHR_BINARY_GLTF:"KHR_binary_glTF",KHR_DRACO_MESH_COMPRESSION:"KHR_draco_mesh_compression",KHR_LIGHTS_PUNCTUAL:"KHR_lights_punctual",KHR_MATERIALS_CLEARCOAT:"KHR_materials_clearcoat",KHR_MATERIALS_DISPERSION:"KHR_materials_dispersion",KHR_MATERIALS_IOR:"KHR_materials_ior",KHR_MATERIALS_SHEEN:"KHR_materials_sheen",KHR_MATERIALS_SPECULAR:"KHR_materials_specular",KHR_MATERIALS_TRANSMISSION:"KHR_materials_transmission",KHR_MATERIALS_IRIDESCENCE:"KHR_materials_iridescence",KHR_MATERIALS_ANISOTROPY:"KHR_materials_anisotropy",KHR_MATERIALS_UNLIT:"KHR_materials_unlit",KHR_MATERIALS_VOLUME:"KHR_materials_volume",KHR_TEXTURE_BASISU:"KHR_texture_basisu",KHR_TEXTURE_TRANSFORM:"KHR_texture_transform",KHR_MESH_QUANTIZATION:"KHR_mesh_quantization",KHR_MATERIALS_EMISSIVE_STRENGTH:"KHR_materials_emissive_strength",EXT_MATERIALS_BUMP:"EXT_materials_bump",EXT_TEXTURE_WEBP:"EXT_texture_webp",EXT_TEXTURE_AVIF:"EXT_texture_avif",EXT_MESHOPT_COMPRESSION:"EXT_meshopt_compression",EXT_MESH_GPU_INSTANCING:"EXT_mesh_gpu_instancing"},Kl=class{constructor(e){this.parser=e,this.name=ze.KHR_LIGHTS_PUNCTUAL,this.cache={refs:{},uses:{}}}_markDefs(){let e=this.parser,t=this.parser.json.nodes||[];for(let n=0,s=t.length;n<s;n++){let r=t[n];r.extensions&&r.extensions[this.name]&&r.extensions[this.name].light!==void 0&&e._addNodeRef(this.cache,r.extensions[this.name].light)}}_loadLight(e){let t=this.parser,n="light:"+e,s=t.cache.get(n);if(s)return s;let r=t.json,l=((r.extensions&&r.extensions[this.name]||{}).lights||[])[e],c,h=new Ae(16777215);l.color!==void 0&&h.setRGB(l.color[0],l.color[1],l.color[2],Ft);let u=l.range!==void 0?l.range:0;switch(l.type){case"directional":c=new Ss(h),c.target.position.set(0,0,-1),c.add(c.target);break;case"point":c=new Ms(h),c.distance=u;break;case"spot":c=new xo(h),c.distance=u,l.spot=l.spot||{},l.spot.innerConeAngle=l.spot.innerConeAngle!==void 0?l.spot.innerConeAngle:0,l.spot.outerConeAngle=l.spot.outerConeAngle!==void 0?l.spot.outerConeAngle:Math.PI/4,c.angle=l.spot.outerConeAngle,c.penumbra=1-l.spot.innerConeAngle/l.spot.outerConeAngle,c.target.position.set(0,0,-1),c.add(c.target);break;default:throw new Error("THREE.GLTFLoader: Unexpected light type: "+l.type)}return c.position.set(0,0,0),c.decay=2,$n(c,l),l.intensity!==void 0&&(c.intensity=l.intensity),c.name=t.createUniqueName(l.name||"light_"+e),s=Promise.resolve(c),t.cache.add(n,s),s}getDependency(e,t){if(e==="light")return this._loadLight(t)}createNodeAttachment(e){let t=this,n=this.parser,r=n.json.nodes[e],a=(r.extensions&&r.extensions[this.name]||{}).light;return a===void 0?null:this._loadLight(a).then(function(l){return n._getNodeRef(t.cache,a,l)})}},Jl=class{constructor(){this.name=ze.KHR_MATERIALS_UNLIT}getMaterialType(){return an}extendParams(e,t,n){let s=[];e.color=new Ae(1,1,1),e.opacity=1;let r=t.pbrMetallicRoughness;if(r){if(Array.isArray(r.baseColorFactor)){let o=r.baseColorFactor;e.color.setRGB(o[0],o[1],o[2],Ft),e.opacity=o[3]}r.baseColorTexture!==void 0&&s.push(n.assignTexture(e,"map",r.baseColorTexture,gt))}return Promise.all(s)}},jl=class{constructor(e){this.parser=e,this.name=ze.KHR_MATERIALS_EMISSIVE_STRENGTH}extendMaterialParams(e,t){let s=this.parser.json.materials[e];if(!s.extensions||!s.extensions[this.name])return Promise.resolve();let r=s.extensions[this.name].emissiveStrength;return r!==void 0&&(t.emissiveIntensity=r),Promise.resolve()}},$l=class{constructor(e){this.parser=e,this.name=ze.KHR_MATERIALS_CLEARCOAT}getMaterialType(e){let n=this.parser.json.materials[e];return!n.extensions||!n.extensions[this.name]?null:Qt}extendMaterialParams(e,t){let n=this.parser,s=n.json.materials[e];if(!s.extensions||!s.extensions[this.name])return Promise.resolve();let r=[],o=s.extensions[this.name];if(o.clearcoatFactor!==void 0&&(t.clearcoat=o.clearcoatFactor),o.clearcoatTexture!==void 0&&r.push(n.assignTexture(t,"clearcoatMap",o.clearcoatTexture)),o.clearcoatRoughnessFactor!==void 0&&(t.clearcoatRoughness=o.clearcoatRoughnessFactor),o.clearcoatRoughnessTexture!==void 0&&r.push(n.assignTexture(t,"clearcoatRoughnessMap",o.clearcoatRoughnessTexture)),o.clearcoatNormalTexture!==void 0&&(r.push(n.assignTexture(t,"clearcoatNormalMap",o.clearcoatNormalTexture)),o.clearcoatNormalTexture.scale!==void 0)){let a=o.clearcoatNormalTexture.scale;t.clearcoatNormalScale=new we(a,a)}return Promise.all(r)}},Ql=class{constructor(e){this.parser=e,this.name=ze.KHR_MATERIALS_DISPERSION}getMaterialType(e){let n=this.parser.json.materials[e];return!n.extensions||!n.extensions[this.name]?null:Qt}extendMaterialParams(e,t){let s=this.parser.json.materials[e];if(!s.extensions||!s.extensions[this.name])return Promise.resolve();let r=s.extensions[this.name];return t.dispersion=r.dispersion!==void 0?r.dispersion:0,Promise.resolve()}},ec=class{constructor(e){this.parser=e,this.name=ze.KHR_MATERIALS_IRIDESCENCE}getMaterialType(e){let n=this.parser.json.materials[e];return!n.extensions||!n.extensions[this.name]?null:Qt}extendMaterialParams(e,t){let n=this.parser,s=n.json.materials[e];if(!s.extensions||!s.extensions[this.name])return Promise.resolve();let r=[],o=s.extensions[this.name];return o.iridescenceFactor!==void 0&&(t.iridescence=o.iridescenceFactor),o.iridescenceTexture!==void 0&&r.push(n.assignTexture(t,"iridescenceMap",o.iridescenceTexture)),o.iridescenceIor!==void 0&&(t.iridescenceIOR=o.iridescenceIor),t.iridescenceThicknessRange===void 0&&(t.iridescenceThicknessRange=[100,400]),o.iridescenceThicknessMinimum!==void 0&&(t.iridescenceThicknessRange[0]=o.iridescenceThicknessMinimum),o.iridescenceThicknessMaximum!==void 0&&(t.iridescenceThicknessRange[1]=o.iridescenceThicknessMaximum),o.iridescenceThicknessTexture!==void 0&&r.push(n.assignTexture(t,"iridescenceThicknessMap",o.iridescenceThicknessTexture)),Promise.all(r)}},tc=class{constructor(e){this.parser=e,this.name=ze.KHR_MATERIALS_SHEEN}getMaterialType(e){let n=this.parser.json.materials[e];return!n.extensions||!n.extensions[this.name]?null:Qt}extendMaterialParams(e,t){let n=this.parser,s=n.json.materials[e];if(!s.extensions||!s.extensions[this.name])return Promise.resolve();let r=[];t.sheenColor=new Ae(0,0,0),t.sheenRoughness=0,t.sheen=1;let o=s.extensions[this.name];if(o.sheenColorFactor!==void 0){let a=o.sheenColorFactor;t.sheenColor.setRGB(a[0],a[1],a[2],Ft)}return o.sheenRoughnessFactor!==void 0&&(t.sheenRoughness=o.sheenRoughnessFactor),o.sheenColorTexture!==void 0&&r.push(n.assignTexture(t,"sheenColorMap",o.sheenColorTexture,gt)),o.sheenRoughnessTexture!==void 0&&r.push(n.assignTexture(t,"sheenRoughnessMap",o.sheenRoughnessTexture)),Promise.all(r)}},nc=class{constructor(e){this.parser=e,this.name=ze.KHR_MATERIALS_TRANSMISSION}getMaterialType(e){let n=this.parser.json.materials[e];return!n.extensions||!n.extensions[this.name]?null:Qt}extendMaterialParams(e,t){let n=this.parser,s=n.json.materials[e];if(!s.extensions||!s.extensions[this.name])return Promise.resolve();let r=[],o=s.extensions[this.name];return o.transmissionFactor!==void 0&&(t.transmission=o.transmissionFactor),o.transmissionTexture!==void 0&&r.push(n.assignTexture(t,"transmissionMap",o.transmissionTexture)),Promise.all(r)}},ic=class{constructor(e){this.parser=e,this.name=ze.KHR_MATERIALS_VOLUME}getMaterialType(e){let n=this.parser.json.materials[e];return!n.extensions||!n.extensions[this.name]?null:Qt}extendMaterialParams(e,t){let n=this.parser,s=n.json.materials[e];if(!s.extensions||!s.extensions[this.name])return Promise.resolve();let r=[],o=s.extensions[this.name];t.thickness=o.thicknessFactor!==void 0?o.thicknessFactor:0,o.thicknessTexture!==void 0&&r.push(n.assignTexture(t,"thicknessMap",o.thicknessTexture)),t.attenuationDistance=o.attenuationDistance||1/0;let a=o.attenuationColor||[1,1,1];return t.attenuationColor=new Ae().setRGB(a[0],a[1],a[2],Ft),Promise.all(r)}},sc=class{constructor(e){this.parser=e,this.name=ze.KHR_MATERIALS_IOR}getMaterialType(e){let n=this.parser.json.materials[e];return!n.extensions||!n.extensions[this.name]?null:Qt}extendMaterialParams(e,t){let s=this.parser.json.materials[e];if(!s.extensions||!s.extensions[this.name])return Promise.resolve();let r=s.extensions[this.name];return t.ior=r.ior!==void 0?r.ior:1.5,Promise.resolve()}},rc=class{constructor(e){this.parser=e,this.name=ze.KHR_MATERIALS_SPECULAR}getMaterialType(e){let n=this.parser.json.materials[e];return!n.extensions||!n.extensions[this.name]?null:Qt}extendMaterialParams(e,t){let n=this.parser,s=n.json.materials[e];if(!s.extensions||!s.extensions[this.name])return Promise.resolve();let r=[],o=s.extensions[this.name];t.specularIntensity=o.specularFactor!==void 0?o.specularFactor:1,o.specularTexture!==void 0&&r.push(n.assignTexture(t,"specularIntensityMap",o.specularTexture));let a=o.specularColorFactor||[1,1,1];return t.specularColor=new Ae().setRGB(a[0],a[1],a[2],Ft),o.specularColorTexture!==void 0&&r.push(n.assignTexture(t,"specularColorMap",o.specularColorTexture,gt)),Promise.all(r)}},oc=class{constructor(e){this.parser=e,this.name=ze.EXT_MATERIALS_BUMP}getMaterialType(e){let n=this.parser.json.materials[e];return!n.extensions||!n.extensions[this.name]?null:Qt}extendMaterialParams(e,t){let n=this.parser,s=n.json.materials[e];if(!s.extensions||!s.extensions[this.name])return Promise.resolve();let r=[],o=s.extensions[this.name];return t.bumpScale=o.bumpFactor!==void 0?o.bumpFactor:1,o.bumpTexture!==void 0&&r.push(n.assignTexture(t,"bumpMap",o.bumpTexture)),Promise.all(r)}},ac=class{constructor(e){this.parser=e,this.name=ze.KHR_MATERIALS_ANISOTROPY}getMaterialType(e){let n=this.parser.json.materials[e];return!n.extensions||!n.extensions[this.name]?null:Qt}extendMaterialParams(e,t){let n=this.parser,s=n.json.materials[e];if(!s.extensions||!s.extensions[this.name])return Promise.resolve();let r=[],o=s.extensions[this.name];return o.anisotropyStrength!==void 0&&(t.anisotropy=o.anisotropyStrength),o.anisotropyRotation!==void 0&&(t.anisotropyRotation=o.anisotropyRotation),o.anisotropyTexture!==void 0&&r.push(n.assignTexture(t,"anisotropyMap",o.anisotropyTexture)),Promise.all(r)}},lc=class{constructor(e){this.parser=e,this.name=ze.KHR_TEXTURE_BASISU}loadTexture(e){let t=this.parser,n=t.json,s=n.textures[e];if(!s.extensions||!s.extensions[this.name])return null;let r=s.extensions[this.name],o=t.options.ktx2Loader;if(!o){if(n.extensionsRequired&&n.extensionsRequired.indexOf(this.name)>=0)throw new Error("THREE.GLTFLoader: setKTX2Loader must be called before loading KTX2 textures");return null}return t.loadTextureImage(e,r.source,o)}},cc=class{constructor(e){this.parser=e,this.name=ze.EXT_TEXTURE_WEBP,this.isSupported=null}loadTexture(e){let t=this.name,n=this.parser,s=n.json,r=s.textures[e];if(!r.extensions||!r.extensions[t])return null;let o=r.extensions[t],a=s.images[o.source],l=n.textureLoader;if(a.uri){let c=n.options.manager.getHandler(a.uri);c!==null&&(l=c)}return this.detectSupport().then(function(c){if(c)return n.loadTextureImage(e,o.source,l);if(s.extensionsRequired&&s.extensionsRequired.indexOf(t)>=0)throw new Error("THREE.GLTFLoader: WebP required by asset but unsupported.");return n.loadTexture(e)})}detectSupport(){return this.isSupported||(this.isSupported=new Promise(function(e){let t=new Image;t.src="data:image/webp;base64,UklGRiIAAABXRUJQVlA4IBYAAAAwAQCdASoBAAEADsD+JaQAA3AAAAAA",t.onload=t.onerror=function(){e(t.height===1)}})),this.isSupported}},hc=class{constructor(e){this.parser=e,this.name=ze.EXT_TEXTURE_AVIF,this.isSupported=null}loadTexture(e){let t=this.name,n=this.parser,s=n.json,r=s.textures[e];if(!r.extensions||!r.extensions[t])return null;let o=r.extensions[t],a=s.images[o.source],l=n.textureLoader;if(a.uri){let c=n.options.manager.getHandler(a.uri);c!==null&&(l=c)}return this.detectSupport().then(function(c){if(c)return n.loadTextureImage(e,o.source,l);if(s.extensionsRequired&&s.extensionsRequired.indexOf(t)>=0)throw new Error("THREE.GLTFLoader: AVIF required by asset but unsupported.");return n.loadTexture(e)})}detectSupport(){return this.isSupported||(this.isSupported=new Promise(function(e){let t=new Image;t.src="data:image/avif;base64,AAAAIGZ0eXBhdmlmAAAAAGF2aWZtaWYxbWlhZk1BMUIAAADybWV0YQAAAAAAAAAoaGRscgAAAAAAAAAAcGljdAAAAAAAAAAAAAAAAGxpYmF2aWYAAAAADnBpdG0AAAAAAAEAAAAeaWxvYwAAAABEAAABAAEAAAABAAABGgAAABcAAAAoaWluZgAAAAAAAQAAABppbmZlAgAAAAABAABhdjAxQ29sb3IAAAAAamlwcnAAAABLaXBjbwAAABRpc3BlAAAAAAAAAAEAAAABAAAAEHBpeGkAAAAAAwgICAAAAAxhdjFDgQAMAAAAABNjb2xybmNseAACAAIABoAAAAAXaXBtYQAAAAAAAAABAAEEAQKDBAAAAB9tZGF0EgAKCBgABogQEDQgMgkQAAAAB8dSLfI=",t.onload=t.onerror=function(){e(t.height===1)}})),this.isSupported}},uc=class{constructor(e){this.name=ze.EXT_MESHOPT_COMPRESSION,this.parser=e}loadBufferView(e){let t=this.parser.json,n=t.bufferViews[e];if(n.extensions&&n.extensions[this.name]){let s=n.extensions[this.name],r=this.parser.getDependency("buffer",s.buffer),o=this.parser.options.meshoptDecoder;if(!o||!o.supported){if(t.extensionsRequired&&t.extensionsRequired.indexOf(this.name)>=0)throw new Error("THREE.GLTFLoader: setMeshoptDecoder must be called before loading compressed files");return null}return r.then(function(a){let l=s.byteOffset||0,c=s.byteLength||0,h=s.count,u=s.byteStride,d=new Uint8Array(a,l,c);return o.decodeGltfBufferAsync?o.decodeGltfBufferAsync(h,u,d,s.mode,s.filter).then(function(f){return f.buffer}):o.ready.then(function(){let f=new ArrayBuffer(h*u);return o.decodeGltfBuffer(new Uint8Array(f),h,u,d,s.mode,s.filter),f})})}else return null}},dc=class{constructor(e){this.name=ze.EXT_MESH_GPU_INSTANCING,this.parser=e}createNodeMesh(e){let t=this.parser.json,n=t.nodes[e];if(!n.extensions||!n.extensions[this.name]||n.mesh===void 0)return null;let s=t.meshes[n.mesh];for(let c of s.primitives)if(c.mode!==hn.TRIANGLES&&c.mode!==hn.TRIANGLE_STRIP&&c.mode!==hn.TRIANGLE_FAN&&c.mode!==void 0)return null;let o=n.extensions[this.name].attributes,a=[],l={};for(let c in o)a.push(this.parser.getDependency("accessor",o[c]).then(h=>(l[c]=h,l[c])));return a.length<1?null:(a.push(this.parser.createNodeMesh(e)),Promise.all(a).then(c=>{let h=c.pop(),u=h.isGroup?h.children:[h],d=c[0].count,f=[];for(let g of u){let _=new Le,m=new C,p=new Gt,w=new C(1,1,1),b=new ro(g.geometry,g.material,d);for(let x=0;x<d;x++)l.TRANSLATION&&m.fromBufferAttribute(l.TRANSLATION,x),l.ROTATION&&p.fromBufferAttribute(l.ROTATION,x),l.SCALE&&w.fromBufferAttribute(l.SCALE,x),b.setMatrixAt(x,_.compose(m,p,w));for(let x in l)if(x==="_COLOR_0"){let P=l[x];b.instanceColor=new Li(P.array,P.itemSize,P.normalized)}else x!=="TRANSLATION"&&x!=="ROTATION"&&x!=="SCALE"&&g.geometry.setAttribute(x,l[x]);ht.prototype.copy.call(b,g),this.parser.assignFinalMaterial(b),f.push(b)}return h.isGroup?(h.clear(),h.add(...f),h):f[0]}))}},Hu="glTF",ir=12,Fu={JSON:1313821514,BIN:5130562},fc=class{constructor(e){this.name=ze.KHR_BINARY_GLTF,this.content=null,this.body=null;let t=new DataView(e,0,ir),n=new TextDecoder;if(this.header={magic:n.decode(new Uint8Array(e.slice(0,4))),version:t.getUint32(4,!0),length:t.getUint32(8,!0)},this.header.magic!==Hu)throw new Error("THREE.GLTFLoader: Unsupported glTF-Binary header.");if(this.header.version<2)throw new Error("THREE.GLTFLoader: Legacy binary file detected.");let s=this.header.length-ir,r=new DataView(e,ir),o=0;for(;o<s;){let a=r.getUint32(o,!0);o+=4;let l=r.getUint32(o,!0);if(o+=4,l===Fu.JSON){let c=new Uint8Array(e,ir+o,a);this.content=n.decode(c)}else if(l===Fu.BIN){let c=ir+o;this.body=e.slice(c,c+a)}o+=a}if(this.content===null)throw new Error("THREE.GLTFLoader: JSON content not found.")}},pc=class{constructor(e,t){if(!t)throw new Error("THREE.GLTFLoader: No DRACOLoader instance provided.");this.name=ze.KHR_DRACO_MESH_COMPRESSION,this.json=e,this.dracoLoader=t,this.dracoLoader.preload()}decodePrimitive(e,t){let n=this.json,s=this.dracoLoader,r=e.extensions[this.name].bufferView,o=e.extensions[this.name].attributes,a={},l={},c={};for(let h in o){let u=xc[h]||h.toLowerCase();a[u]=o[h]}for(let h in e.attributes){let u=xc[h]||h.toLowerCase();if(o[h]!==void 0){let d=n.accessors[e.attributes[h]],f=Es[d.componentType];c[u]=f.name,l[u]=d.normalized===!0}}return t.getDependency("bufferView",r).then(function(h){return new Promise(function(u,d){s.decodeDracoFile(h,function(f){for(let g in f.attributes){let _=f.attributes[g],m=l[g];m!==void 0&&(_.normalized=m)}u(f)},a,c,Ft,d)})})}},mc=class{constructor(){this.name=ze.KHR_TEXTURE_TRANSFORM}extendTexture(e,t){return(t.texCoord===void 0||t.texCoord===e.channel)&&t.offset===void 0&&t.rotation===void 0&&t.scale===void 0||(e=e.clone(),t.texCoord!==void 0&&(e.channel=t.texCoord),t.offset!==void 0&&e.offset.fromArray(t.offset),t.rotation!==void 0&&(e.rotation=t.rotation),t.scale!==void 0&&e.repeat.fromArray(t.scale),e.needsUpdate=!0),e}},gc=class{constructor(){this.name=ze.KHR_MESH_QUANTIZATION}},Co=class extends pi{constructor(e,t,n,s){super(e,t,n,s)}copySampleValue_(e){let t=this.resultBuffer,n=this.sampleValues,s=this.valueSize,r=e*s*3+s;for(let o=0;o!==s;o++)t[o]=n[r+o];return t}interpolate_(e,t,n,s){let r=this.resultBuffer,o=this.sampleValues,a=this.valueSize,l=a*2,c=a*3,h=s-t,u=(n-t)/h,d=u*u,f=d*u,g=e*c,_=g-c,m=-2*f+3*d,p=f-d,w=1-m,b=p-d+u;for(let x=0;x!==a;x++){let P=o[_+x+a],T=o[_+x+l]*h,A=o[g+x+a],R=o[g+x]*h;r[x]=w*P+b*T+m*A+p*R}return r}},T_=new Gt,_c=class extends Co{interpolate_(e,t,n,s){let r=super.interpolate_(e,t,n,s);return T_.fromArray(r).normalize().toArray(r),r}},hn={FLOAT:5126,FLOAT_MAT3:35675,FLOAT_MAT4:35676,FLOAT_VEC2:35664,FLOAT_VEC3:35665,FLOAT_VEC4:35666,LINEAR:9729,REPEAT:10497,SAMPLER_2D:35678,POINTS:0,LINES:1,LINE_LOOP:2,LINE_STRIP:3,TRIANGLES:4,TRIANGLE_STRIP:5,TRIANGLE_FAN:6,UNSIGNED_BYTE:5121,UNSIGNED_SHORT:5123},Es={5120:Int8Array,5121:Uint8Array,5122:Int16Array,5123:Uint16Array,5125:Uint32Array,5126:Float32Array},Bu={9728:Nt,9729:Vt,9984:Rl,9985:zs,9986:ts,9987:wn},zu={33071:Bn,33648:Vs,10497:Hn},ql={SCALAR:1,VEC2:2,VEC3:3,VEC4:4,MAT2:4,MAT3:9,MAT4:16},xc={POSITION:"position",NORMAL:"normal",TANGENT:"tangent",TEXCOORD_0:"uv",TEXCOORD_1:"uv1",TEXCOORD_2:"uv2",TEXCOORD_3:"uv3",COLOR_0:"color",WEIGHTS_0:"skinWeight",JOINTS_0:"skinIndex"},xi={scale:"scale",translation:"position",rotation:"quaternion",weights:"morphTargetInfluences"},R_={CUBICSPLINE:void 0,LINEAR:ps,STEP:fs},Yl={OPAQUE:"OPAQUE",MASK:"MASK",BLEND:"BLEND"};function C_(i){return i.DefaultMaterial===void 0&&(i.DefaultMaterial=new kt({color:16777215,emissive:0,metalness:1,roughness:1,transparent:!1,depthTest:!0,side:En})),i.DefaultMaterial}function Oi(i,e,t){for(let n in t.extensions)i[n]===void 0&&(e.userData.gltfExtensions=e.userData.gltfExtensions||{},e.userData.gltfExtensions[n]=t.extensions[n])}function $n(i,e){e.extras!==void 0&&(typeof e.extras=="object"?Object.assign(i.userData,e.extras):console.warn("THREE.GLTFLoader: Ignoring primitive type .extras, "+e.extras))}function I_(i,e,t){let n=!1,s=!1,r=!1;for(let c=0,h=e.length;c<h;c++){let u=e[c];if(u.POSITION!==void 0&&(n=!0),u.NORMAL!==void 0&&(s=!0),u.COLOR_0!==void 0&&(r=!0),n&&s&&r)break}if(!n&&!s&&!r)return Promise.resolve(i);let o=[],a=[],l=[];for(let c=0,h=e.length;c<h;c++){let u=e[c];if(n){let d=u.POSITION!==void 0?t.getDependency("accessor",u.POSITION):i.attributes.position;o.push(d)}if(s){let d=u.NORMAL!==void 0?t.getDependency("accessor",u.NORMAL):i.attributes.normal;a.push(d)}if(r){let d=u.COLOR_0!==void 0?t.getDependency("accessor",u.COLOR_0):i.attributes.color;l.push(d)}}return Promise.all([Promise.all(o),Promise.all(a),Promise.all(l)]).then(function(c){let h=c[0],u=c[1],d=c[2];return n&&(i.morphAttributes.position=h),s&&(i.morphAttributes.normal=u),r&&(i.morphAttributes.color=d),i.morphTargetsRelative=!0,i})}function P_(i,e){if(i.updateMorphTargets(),e.weights!==void 0)for(let t=0,n=e.weights.length;t<n;t++)i.morphTargetInfluences[t]=e.weights[t];if(e.extras&&Array.isArray(e.extras.targetNames)){let t=e.extras.targetNames;if(i.morphTargetInfluences.length===t.length){i.morphTargetDictionary={};for(let n=0,s=t.length;n<s;n++)i.morphTargetDictionary[t[n]]=n}else console.warn("THREE.GLTFLoader: Invalid extras.targetNames length. Ignoring names.")}}function L_(i){let e,t=i.extensions&&i.extensions[ze.KHR_DRACO_MESH_COMPRESSION];if(t?e="draco:"+t.bufferView+":"+t.indices+":"+Zl(t.attributes):e=i.indices+":"+Zl(i.attributes)+":"+i.mode,i.targets!==void 0)for(let n=0,s=i.targets.length;n<s;n++)e+=":"+Zl(i.targets[n]);return e}function Zl(i){let e="",t=Object.keys(i).sort();for(let n=0,s=t.length;n<s;n++)e+=t[n]+":"+i[t[n]]+";";return e}function yc(i){switch(i){case Int8Array:return 1/127;case Uint8Array:return 1/255;case Int16Array:return 1/32767;case Uint16Array:return 1/65535;default:throw new Error("THREE.GLTFLoader: Unsupported normalized accessor component type.")}}function D_(i){return i.search(/\.jpe?g($|\?)/i)>0||i.search(/^data\:image\/jpeg/)===0?"image/jpeg":i.search(/\.webp($|\?)/i)>0||i.search(/^data\:image\/webp/)===0?"image/webp":i.search(/\.ktx2($|\?)/i)>0||i.search(/^data\:image\/ktx2/)===0?"image/ktx2":"image/png"}var U_=new Le,vc=class{constructor(e={},t={}){this.json=e,this.extensions={},this.plugins={},this.options=t,this.cache=new A_,this.associations=new Map,this.primitiveCache={},this.nodeCache={},this.meshCache={refs:{},uses:{}},this.cameraCache={refs:{},uses:{}},this.lightCache={refs:{},uses:{}},this.sourceCache={},this.textureCache={},this.nodeNamesUsed={};let n=!1,s=-1,r=!1,o=-1;if(typeof navigator<"u"){let a=navigator.userAgent;n=/^((?!chrome|android).)*safari/i.test(a)===!0;let l=a.match(/Version\/(\d+)/);s=n&&l?parseInt(l[1],10):-1,r=a.indexOf("Firefox")>-1,o=r?a.match(/Firefox\/([0-9]+)\./)[1]:-1}typeof createImageBitmap>"u"||n&&s<17||r&&o<98?this.textureLoader=new go(this.options.manager):this.textureLoader=new yo(this.options.manager),this.textureLoader.setCrossOrigin(this.options.crossOrigin),this.textureLoader.setRequestHeader(this.options.requestHeader),this.fileLoader=new $s(this.options.manager),this.fileLoader.setResponseType("arraybuffer"),this.options.crossOrigin==="use-credentials"&&this.fileLoader.setWithCredentials(!0)}setExtensions(e){this.extensions=e}setPlugins(e){this.plugins=e}parse(e,t){let n=this,s=this.json,r=this.extensions;this.cache.removeAll(),this.nodeCache={},this._invokeAll(function(o){return o._markDefs&&o._markDefs()}),Promise.all(this._invokeAll(function(o){return o.beforeRoot&&o.beforeRoot()})).then(function(){return Promise.all([n.getDependencies("scene"),n.getDependencies("animation"),n.getDependencies("camera")])}).then(function(o){let a={scene:o[0][s.scene||0],scenes:o[0],animations:o[1],cameras:o[2],asset:s.asset,parser:n,userData:{}};return Oi(r,a,s),$n(a,s),Promise.all(n._invokeAll(function(l){return l.afterRoot&&l.afterRoot(a)})).then(function(){for(let l of a.scenes)l.updateMatrixWorld();e(a)})}).catch(t)}_markDefs(){let e=this.json.nodes||[],t=this.json.skins||[],n=this.json.meshes||[];for(let s=0,r=t.length;s<r;s++){let o=t[s].joints;for(let a=0,l=o.length;a<l;a++)e[o[a]].isBone=!0}for(let s=0,r=e.length;s<r;s++){let o=e[s];o.mesh!==void 0&&(this._addNodeRef(this.meshCache,o.mesh),o.skin!==void 0&&(n[o.mesh].isSkinnedMesh=!0)),o.camera!==void 0&&this._addNodeRef(this.cameraCache,o.camera)}}_addNodeRef(e,t){t!==void 0&&(e.refs[t]===void 0&&(e.refs[t]=e.uses[t]=0),e.refs[t]++)}_getNodeRef(e,t,n){if(e.refs[t]<=1)return n;let s=n.clone(),r=(o,a)=>{let l=this.associations.get(o);l!=null&&this.associations.set(a,l);for(let[c,h]of o.children.entries())r(h,a.children[c])};return r(n,s),s.name+="_instance_"+e.uses[t]++,s}_invokeOne(e){let t=Object.values(this.plugins);t.push(this);for(let n=0;n<t.length;n++){let s=e(t[n]);if(s)return s}return null}_invokeAll(e){let t=Object.values(this.plugins);t.unshift(this);let n=[];for(let s=0;s<t.length;s++){let r=e(t[s]);r&&n.push(r)}return n}getDependency(e,t){let n=e+":"+t,s=this.cache.get(n);if(!s){switch(e){case"scene":s=this.loadScene(t);break;case"node":s=this._invokeOne(function(r){return r.loadNode&&r.loadNode(t)});break;case"mesh":s=this._invokeOne(function(r){return r.loadMesh&&r.loadMesh(t)});break;case"accessor":s=this.loadAccessor(t);break;case"bufferView":s=this._invokeOne(function(r){return r.loadBufferView&&r.loadBufferView(t)});break;case"buffer":s=this.loadBuffer(t);break;case"material":s=this._invokeOne(function(r){return r.loadMaterial&&r.loadMaterial(t)});break;case"texture":s=this._invokeOne(function(r){return r.loadTexture&&r.loadTexture(t)});break;case"skin":s=this.loadSkin(t);break;case"animation":s=this._invokeOne(function(r){return r.loadAnimation&&r.loadAnimation(t)});break;case"camera":s=this.loadCamera(t);break;default:if(s=this._invokeOne(function(r){return r!=this&&r.getDependency&&r.getDependency(e,t)}),!s)throw new Error("Unknown type: "+e);break}this.cache.add(n,s)}return s}getDependencies(e){let t=this.cache.get(e);if(!t){let n=this,s=this.json[e+(e==="mesh"?"es":"s")]||[];t=Promise.all(s.map(function(r,o){return n.getDependency(e,o)})),this.cache.add(e,t)}return t}loadBuffer(e){let t=this.json.buffers[e],n=this.fileLoader;if(t.type&&t.type!=="arraybuffer")throw new Error("THREE.GLTFLoader: "+t.type+" buffer type is not supported.");if(t.uri===void 0&&e===0)return Promise.resolve(this.extensions[ze.KHR_BINARY_GLTF].body);let s=this.options;return new Promise(function(r,o){n.load(_i.resolveURL(t.uri,s.path),r,void 0,function(){o(new Error('THREE.GLTFLoader: Failed to load buffer "'+t.uri+'".'))})})}loadBufferView(e){let t=this.json.bufferViews[e];return this.getDependency("buffer",t.buffer).then(function(n){let s=t.byteLength||0,r=t.byteOffset||0;return n.slice(r,r+s)})}loadAccessor(e){let t=this,n=this.json,s=this.json.accessors[e];if(s.bufferView===void 0&&s.sparse===void 0){let o=ql[s.type],a=Es[s.componentType],l=s.normalized===!0,c=new a(s.count*o);return Promise.resolve(new pt(c,o,l))}let r=[];return s.bufferView!==void 0?r.push(this.getDependency("bufferView",s.bufferView)):r.push(null),s.sparse!==void 0&&(r.push(this.getDependency("bufferView",s.sparse.indices.bufferView)),r.push(this.getDependency("bufferView",s.sparse.values.bufferView))),Promise.all(r).then(function(o){let a=o[0],l=ql[s.type],c=Es[s.componentType],h=c.BYTES_PER_ELEMENT,u=h*l,d=s.byteOffset||0,f=s.bufferView!==void 0?n.bufferViews[s.bufferView].byteStride:void 0,g=s.normalized===!0,_,m;if(f&&f!==u){let p=Math.floor(d/f),w="InterleavedBuffer:"+s.bufferView+":"+s.componentType+":"+p+":"+s.count,b=t.cache.get(w);b||(_=new c(a,p*f,s.count*f/h),b=new Zs(_,f/h),t.cache.add(w,b)),m=new Ks(b,l,d%f/h,g)}else a===null?_=new c(s.count*l):_=new c(a,d,s.count*l),m=new pt(_,l,g);if(s.sparse!==void 0){let p=ql.SCALAR,w=Es[s.sparse.indices.componentType],b=s.sparse.indices.byteOffset||0,x=s.sparse.values.byteOffset||0,P=new w(o[1],b,s.sparse.count*p),T=new c(o[2],x,s.sparse.count*l);a!==null&&(m=new pt(m.array.slice(),m.itemSize,m.normalized)),m.normalized=!1;for(let A=0,R=P.length;A<R;A++){let M=P[A];if(m.setX(M,T[A*l]),l>=2&&m.setY(M,T[A*l+1]),l>=3&&m.setZ(M,T[A*l+2]),l>=4&&m.setW(M,T[A*l+3]),l>=5)throw new Error("THREE.GLTFLoader: Unsupported itemSize in sparse BufferAttribute.")}m.normalized=g}return m})}loadTexture(e){let t=this.json,n=this.options,r=t.textures[e].source,o=t.images[r],a=this.textureLoader;if(o.uri){let l=n.manager.getHandler(o.uri);l!==null&&(a=l)}return this.loadTextureImage(e,r,a)}loadTextureImage(e,t,n){let s=this,r=this.json,o=r.textures[e],a=r.images[t],l=(a.uri||a.bufferView)+":"+o.sampler;if(this.textureCache[l])return this.textureCache[l];let c=this.loadImageSource(t,n).then(function(h){h.flipY=!1,h.name=o.name||a.name||"",h.name===""&&typeof a.uri=="string"&&a.uri.startsWith("data:image/")===!1&&(h.name=a.uri);let d=(r.samplers||{})[o.sampler]||{};return h.magFilter=Bu[d.magFilter]||Vt,h.minFilter=Bu[d.minFilter]||wn,h.wrapS=zu[d.wrapS]||Hn,h.wrapT=zu[d.wrapT]||Hn,h.generateMipmaps=!h.isCompressedTexture&&h.minFilter!==Nt&&h.minFilter!==Vt,s.associations.set(h,{textures:e}),h}).catch(function(){return null});return this.textureCache[l]=c,c}loadImageSource(e,t){let n=this,s=this.json,r=this.options;if(this.sourceCache[e]!==void 0)return this.sourceCache[e].then(u=>u.clone());let o=s.images[e],a=self.URL||self.webkitURL,l=o.uri||"",c=!1;if(o.bufferView!==void 0)l=n.getDependency("bufferView",o.bufferView).then(function(u){c=!0;let d=new Blob([u],{type:o.mimeType});return l=a.createObjectURL(d),l});else if(o.uri===void 0)throw new Error("THREE.GLTFLoader: Image "+e+" is missing URI and bufferView");let h=Promise.resolve(l).then(function(u){return new Promise(function(d,f){let g=d;t.isImageBitmapLoader===!0&&(g=function(_){let m=new Et(_);m.needsUpdate=!0,d(m)}),t.load(_i.resolveURL(u,r.path),g,void 0,f)})}).then(function(u){return c===!0&&a.revokeObjectURL(l),$n(u,o),u.userData.mimeType=o.mimeType||D_(o.uri),u}).catch(function(u){throw console.error("THREE.GLTFLoader: Couldn't load texture",l),u});return this.sourceCache[e]=h,h}assignTexture(e,t,n,s){let r=this;return this.getDependency("texture",n.index).then(function(o){if(!o)return null;if(n.texCoord!==void 0&&n.texCoord>0&&(o=o.clone(),o.channel=n.texCoord),r.extensions[ze.KHR_TEXTURE_TRANSFORM]){let a=n.extensions!==void 0?n.extensions[ze.KHR_TEXTURE_TRANSFORM]:void 0;if(a){let l=r.associations.get(o);o=r.extensions[ze.KHR_TEXTURE_TRANSFORM].extendTexture(o,a),r.associations.set(o,l)}}return s!==void 0&&(o.colorSpace=s),e[t]=o,o})}assignFinalMaterial(e){let t=e.geometry,n=e.material,s=t.attributes.tangent===void 0,r=t.attributes.color!==void 0,o=t.attributes.normal===void 0;if(e.isPoints){let a="PointsMaterial:"+n.uuid,l=this.cache.get(a);l||(l=new js,$t.prototype.copy.call(l,n),l.color.copy(n.color),l.map=n.map,l.sizeAttenuation=!1,this.cache.add(a,l)),n=l}else if(e.isLine){let a="LineBasicMaterial:"+n.uuid,l=this.cache.get(a);l||(l=new fi,$t.prototype.copy.call(l,n),l.color.copy(n.color),l.map=n.map,this.cache.add(a,l)),n=l}if(s||r||o){let a="ClonedMaterial:"+n.uuid+":";s&&(a+="derivative-tangents:"),r&&(a+="vertex-colors:"),o&&(a+="flat-shading:");let l=this.cache.get(a);l||(l=n.clone(),r&&(l.vertexColors=!0),o&&(l.flatShading=!0),s&&(l.normalScale&&(l.normalScale.y*=-1),l.clearcoatNormalScale&&(l.clearcoatNormalScale.y*=-1)),this.cache.add(a,l),this.associations.set(l,this.associations.get(n))),n=l}e.material=n}getMaterialType(){return kt}loadMaterial(e){let t=this,n=this.json,s=this.extensions,r=n.materials[e],o,a={},l=r.extensions||{},c=[];if(l[ze.KHR_MATERIALS_UNLIT]){let u=s[ze.KHR_MATERIALS_UNLIT];o=u.getMaterialType(),c.push(u.extendParams(a,r,t))}else{let u=r.pbrMetallicRoughness||{};if(a.color=new Ae(1,1,1),a.opacity=1,Array.isArray(u.baseColorFactor)){let d=u.baseColorFactor;a.color.setRGB(d[0],d[1],d[2],Ft),a.opacity=d[3]}u.baseColorTexture!==void 0&&c.push(t.assignTexture(a,"map",u.baseColorTexture,gt)),a.metalness=u.metallicFactor!==void 0?u.metallicFactor:1,a.roughness=u.roughnessFactor!==void 0?u.roughnessFactor:1,u.metallicRoughnessTexture!==void 0&&(c.push(t.assignTexture(a,"metalnessMap",u.metallicRoughnessTexture)),c.push(t.assignTexture(a,"roughnessMap",u.metallicRoughnessTexture))),o=this._invokeOne(function(d){return d.getMaterialType&&d.getMaterialType(e)}),c.push(Promise.all(this._invokeAll(function(d){return d.extendMaterialParams&&d.extendMaterialParams(e,a)})))}r.doubleSided===!0&&(a.side=Jt);let h=r.alphaMode||Yl.OPAQUE;if(h===Yl.BLEND?(a.transparent=!0,a.depthWrite=!1):(a.transparent=!1,h===Yl.MASK&&(a.alphaTest=r.alphaCutoff!==void 0?r.alphaCutoff:.5)),r.normalTexture!==void 0&&o!==an&&(c.push(t.assignTexture(a,"normalMap",r.normalTexture)),a.normalScale=new we(1,1),r.normalTexture.scale!==void 0)){let u=r.normalTexture.scale;a.normalScale.set(u,u)}if(r.occlusionTexture!==void 0&&o!==an&&(c.push(t.assignTexture(a,"aoMap",r.occlusionTexture)),r.occlusionTexture.strength!==void 0&&(a.aoMapIntensity=r.occlusionTexture.strength)),r.emissiveFactor!==void 0&&o!==an){let u=r.emissiveFactor;a.emissive=new Ae().setRGB(u[0],u[1],u[2],Ft)}return r.emissiveTexture!==void 0&&o!==an&&c.push(t.assignTexture(a,"emissiveMap",r.emissiveTexture,gt)),Promise.all(c).then(function(){let u=new o(a);return r.name&&(u.name=r.name),$n(u,r),t.associations.set(u,{materials:e}),r.extensions&&Oi(s,u,r),u})}createUniqueName(e){let t=rt.sanitizeNodeName(e||"");return t in this.nodeNamesUsed?t+"_"+ ++this.nodeNamesUsed[t]:(this.nodeNamesUsed[t]=0,t)}loadGeometries(e){let t=this,n=this.extensions,s=this.primitiveCache;function r(a){return n[ze.KHR_DRACO_MESH_COMPRESSION].decodePrimitive(a,t).then(function(l){return ku(l,a,t)})}let o=[];for(let a=0,l=e.length;a<l;a++){let c=e[a],h=L_(c),u=s[h];if(u)o.push(u.promise);else{let d;c.extensions&&c.extensions[ze.KHR_DRACO_MESH_COMPRESSION]?d=r(c):d=ku(new yt,c,t),s[h]={primitive:c,promise:d},o.push(d)}}return Promise.all(o)}loadMesh(e){let t=this,n=this.json,s=this.extensions,r=n.meshes[e],o=r.primitives,a=[];for(let l=0,c=o.length;l<c;l++){let h=o[l].material===void 0?C_(this.cache):this.getDependency("material",o[l].material);a.push(h)}return a.push(t.loadGeometries(o)),Promise.all(a).then(function(l){let c=l.slice(0,l.length-1),h=l[l.length-1],u=[];for(let f=0,g=h.length;f<g;f++){let _=h[f],m=o[f],p,w=c[f];if(m.mode===hn.TRIANGLES||m.mode===hn.TRIANGLE_STRIP||m.mode===hn.TRIANGLE_FAN||m.mode===void 0)p=r.isSkinnedMesh===!0?new no(_,w):new tt(_,w),p.isSkinnedMesh===!0&&p.normalizeSkinWeights(),m.mode===hn.TRIANGLE_STRIP?p.geometry=Xl(p.geometry,wo):m.mode===hn.TRIANGLE_FAN&&(p.geometry=Xl(p.geometry,nr));else if(m.mode===hn.LINES)p=new Di(_,w);else if(m.mode===hn.LINE_STRIP)p=new ys(_,w);else if(m.mode===hn.LINE_LOOP)p=new lo(_,w);else if(m.mode===hn.POINTS)p=new co(_,w);else throw new Error("THREE.GLTFLoader: Primitive mode unsupported: "+m.mode);Object.keys(p.geometry.morphAttributes).length>0&&P_(p,r),p.name=t.createUniqueName(r.name||"mesh_"+e),$n(p,r),m.extensions&&Oi(s,p,m),t.assignFinalMaterial(p),u.push(p)}for(let f=0,g=u.length;f<g;f++)t.associations.set(u[f],{meshes:e,primitives:f});if(u.length===1)return r.extensions&&Oi(s,u[0],r),u[0];let d=new Dt;r.extensions&&Oi(s,d,r),t.associations.set(d,{meshes:e});for(let f=0,g=u.length;f<g;f++)d.add(u[f]);return d})}loadCamera(e){let t,n=this.json.cameras[e],s=n[n.type];if(!s){console.warn("THREE.GLTFLoader: Missing camera parameters.");return}return n.type==="perspective"?t=new xt(en.radToDeg(s.yfov),s.aspectRatio||1,s.znear||1,s.zfar||2e6):n.type==="orthographic"&&(t=new _s(-s.xmag,s.xmag,s.ymag,-s.ymag,s.znear,s.zfar)),n.name&&(t.name=this.createUniqueName(n.name)),$n(t,n),Promise.resolve(t)}loadSkin(e){let t=this.json.skins[e],n=[];for(let s=0,r=t.joints.length;s<r;s++)n.push(this._loadNodeShallow(t.joints[s]));return t.inverseBindMatrices!==void 0?n.push(this.getDependency("accessor",t.inverseBindMatrices)):n.push(null),Promise.all(n).then(function(s){let r=s.pop(),o=s,a=[],l=[];for(let c=0,h=o.length;c<h;c++){let u=o[c];if(u){a.push(u);let d=new Le;r!==null&&d.fromArray(r.array,c*16),l.push(d)}else console.warn('THREE.GLTFLoader: Joint "%s" could not be found.',t.joints[c])}return new so(a,l)})}loadAnimation(e){let t=this.json,n=this,s=t.animations[e],r=s.name?s.name:"animation_"+e,o=[],a=[],l=[],c=[],h=[];for(let u=0,d=s.channels.length;u<d;u++){let f=s.channels[u],g=s.samplers[f.sampler],_=f.target,m=_.node,p=s.parameters!==void 0?s.parameters[g.input]:g.input,w=s.parameters!==void 0?s.parameters[g.output]:g.output;_.node!==void 0&&(o.push(this.getDependency("node",m)),a.push(this.getDependency("accessor",p)),l.push(this.getDependency("accessor",w)),c.push(g),h.push(_))}return Promise.all([Promise.all(o),Promise.all(a),Promise.all(l),Promise.all(c),Promise.all(h)]).then(function(u){let d=u[0],f=u[1],g=u[2],_=u[3],m=u[4],p=[];for(let w=0,b=d.length;w<b;w++){let x=d[w],P=f[w],T=g[w],A=_[w],R=m[w];if(x===void 0)continue;x.updateMatrix&&x.updateMatrix();let M=n._createAnimationTracks(x,P,T,A,R);if(M)for(let v=0;v<M.length;v++)p.push(M[v])}return new mo(r,void 0,p)})}createNodeMesh(e){let t=this.json,n=this,s=t.nodes[e];return s.mesh===void 0?null:n.getDependency("mesh",s.mesh).then(function(r){let o=n._getNodeRef(n.meshCache,s.mesh,r);return s.weights!==void 0&&o.traverse(function(a){if(a.isMesh)for(let l=0,c=s.weights.length;l<c;l++)a.morphTargetInfluences[l]=s.weights[l]}),o})}loadNode(e){let t=this.json,n=this,s=t.nodes[e],r=n._loadNodeShallow(e),o=[],a=s.children||[];for(let c=0,h=a.length;c<h;c++)o.push(n.getDependency("node",a[c]));let l=s.skin===void 0?Promise.resolve(null):n.getDependency("skin",s.skin);return Promise.all([r,Promise.all(o),l]).then(function(c){let h=c[0],u=c[1],d=c[2];d!==null&&h.traverse(function(f){f.isSkinnedMesh&&f.bind(d,U_)});for(let f=0,g=u.length;f<g;f++)h.add(u[f]);return h})}_loadNodeShallow(e){let t=this.json,n=this.extensions,s=this;if(this.nodeCache[e]!==void 0)return this.nodeCache[e];let r=t.nodes[e],o=r.name?s.createUniqueName(r.name):"",a=[],l=s._invokeOne(function(c){return c.createNodeMesh&&c.createNodeMesh(e)});return l&&a.push(l),r.camera!==void 0&&a.push(s.getDependency("camera",r.camera).then(function(c){return s._getNodeRef(s.cameraCache,r.camera,c)})),s._invokeAll(function(c){return c.createNodeAttachment&&c.createNodeAttachment(e)}).forEach(function(c){a.push(c)}),this.nodeCache[e]=Promise.all(a).then(function(c){let h;if(r.isBone===!0?h=new Js:c.length>1?h=new Dt:c.length===1?h=c[0]:h=new ht,h!==c[0])for(let u=0,d=c.length;u<d;u++)h.add(c[u]);if(r.name&&(h.userData.name=r.name,h.name=o),$n(h,r),r.extensions&&Oi(n,h,r),r.matrix!==void 0){let u=new Le;u.fromArray(r.matrix),h.applyMatrix4(u)}else r.translation!==void 0&&h.position.fromArray(r.translation),r.rotation!==void 0&&h.quaternion.fromArray(r.rotation),r.scale!==void 0&&h.scale.fromArray(r.scale);return s.associations.has(h)||s.associations.set(h,{}),s.associations.get(h).nodes=e,h}),this.nodeCache[e]}loadScene(e){let t=this.extensions,n=this.json.scenes[e],s=this,r=new Dt;n.name&&(r.name=s.createUniqueName(n.name)),$n(r,n),n.extensions&&Oi(t,r,n);let o=n.nodes||[],a=[];for(let l=0,c=o.length;l<c;l++)a.push(s.getDependency("node",o[l]));return Promise.all(a).then(function(l){for(let h=0,u=l.length;h<u;h++)r.add(l[h]);let c=h=>{let u=new Map;for(let[d,f]of s.associations)(d instanceof $t||d instanceof Et)&&u.set(d,f);return h.traverse(d=>{let f=s.associations.get(d);f!=null&&u.set(d,f)}),u};return s.associations=c(r),r})}_createAnimationTracks(e,t,n,s,r){let o=[],a=e.name?e.name:e.uuid,l=[];xi[r.path]===xi.weights?e.traverse(function(d){d.morphTargetInfluences&&l.push(d.name?d.name:d.uuid)}):l.push(a);let c;switch(xi[r.path]){case xi.weights:c=Zn;break;case xi.rotation:c=Kn;break;case xi.position:case xi.scale:c=Jn;break;default:switch(n.itemSize){case 1:c=Zn;break;case 2:case 3:default:c=Jn;break}break}let h=s.interpolation!==void 0?R_[s.interpolation]:ps,u=this._getArrayFromAccessor(n);for(let d=0,f=l.length;d<f;d++){let g=new c(l[d]+"."+xi[r.path],t.array,u,h);s.interpolation==="CUBICSPLINE"&&this._createCubicSplineTrackInterpolant(g),o.push(g)}return o}_getArrayFromAccessor(e){let t=e.array;if(e.normalized){let n=yc(t.constructor),s=new Float32Array(t.length);for(let r=0,o=t.length;r<o;r++)s[r]=t[r]*n;t=s}return t}_createCubicSplineTrackInterpolant(e){e.createInterpolant=function(n){let s=this instanceof Kn?_c:Co;return new s(this.times,this.values,this.getValueSize()/3,n)},e.createInterpolant.isInterpolantFactoryMethodGLTFCubicSpline=!0}};function N_(i,e,t){let n=e.attributes,s=new Ot;if(n.POSITION!==void 0){let a=t.json.accessors[n.POSITION],l=a.min,c=a.max;if(l!==void 0&&c!==void 0){if(s.set(new C(l[0],l[1],l[2]),new C(c[0],c[1],c[2])),a.normalized){let h=yc(Es[a.componentType]);s.min.multiplyScalar(h),s.max.multiplyScalar(h)}}else{console.warn("THREE.GLTFLoader: Missing min/max properties for accessor POSITION.");return}}else return;let r=e.targets;if(r!==void 0){let a=new C,l=new C;for(let c=0,h=r.length;c<h;c++){let u=r[c];if(u.POSITION!==void 0){let d=t.json.accessors[u.POSITION],f=d.min,g=d.max;if(f!==void 0&&g!==void 0){if(l.setX(Math.max(Math.abs(f[0]),Math.abs(g[0]))),l.setY(Math.max(Math.abs(f[1]),Math.abs(g[1]))),l.setZ(Math.max(Math.abs(f[2]),Math.abs(g[2]))),d.normalized){let _=yc(Es[d.componentType]);l.multiplyScalar(_)}a.max(l)}else console.warn("THREE.GLTFLoader: Missing min/max properties for accessor POSITION.")}}s.expandByVector(a)}i.boundingBox=s;let o=new jt;s.getCenter(o.center),o.radius=s.min.distanceTo(s.max)/2,i.boundingSphere=o}function ku(i,e,t){let n=e.attributes,s=[];function r(o,a){return t.getDependency("accessor",o).then(function(l){i.setAttribute(a,l)})}for(let o in n){let a=xc[o]||o.toLowerCase();a in i.attributes||s.push(r(n[o],a))}if(e.indices!==void 0&&!i.index){let o=t.getDependency("accessor",e.indices).then(function(a){i.setIndex(a)});s.push(o)}return ke.workingColorSpace!==Ft&&"COLOR_0"in n&&console.warn(`THREE.GLTFLoader: Converting vertex colors from "srgb-linear" to "${ke.workingColorSpace}" not supported.`),$n(i,e),N_(i,e,t),Promise.all(s).then(function(){return e.targets!==void 0?I_(i,e.targets,t):i})}var rr=class i extends tt{constructor(){let e=i.SkyShader,t=new ln({name:e.name,uniforms:Fl.clone(e.uniforms),vertexShader:e.vertexShader,fragmentShader:e.fragmentShader,side:Ut,depthWrite:!1});super(new qn(1,1,1),t),this.isSky=!0}};rr.SkyShader={name:"SkyShader",uniforms:{turbidity:{value:2},rayleigh:{value:1},mieCoefficient:{value:.005},mieDirectionalG:{value:.8},sunPosition:{value:new C},up:{value:new C(0,1,0)}},vertexShader:`
		uniform vec3 sunPosition;
		uniform float rayleigh;
		uniform float turbidity;
		uniform float mieCoefficient;
		uniform vec3 up;

		varying vec3 vWorldPosition;
		varying vec3 vSunDirection;
		varying float vSunfade;
		varying vec3 vBetaR;
		varying vec3 vBetaM;
		varying float vSunE;

		// constants for atmospheric scattering
		const float e = 2.71828182845904523536028747135266249775724709369995957;
		const float pi = 3.141592653589793238462643383279502884197169;

		// wavelength of used primaries, according to preetham
		const vec3 lambda = vec3( 680E-9, 550E-9, 450E-9 );
		// this pre-calcuation replaces older TotalRayleigh(vec3 lambda) function:
		// (8.0 * pow(pi, 3.0) * pow(pow(n, 2.0) - 1.0, 2.0) * (6.0 + 3.0 * pn)) / (3.0 * N * pow(lambda, vec3(4.0)) * (6.0 - 7.0 * pn))
		const vec3 totalRayleigh = vec3( 5.804542996261093E-6, 1.3562911419845635E-5, 3.0265902468824876E-5 );

		// mie stuff
		// K coefficient for the primaries
		const float v = 4.0;
		const vec3 K = vec3( 0.686, 0.678, 0.666 );
		// MieConst = pi * pow( ( 2.0 * pi ) / lambda, vec3( v - 2.0 ) ) * K
		const vec3 MieConst = vec3( 1.8399918514433978E14, 2.7798023919660528E14, 4.0790479543861094E14 );

		// earth shadow hack
		// cutoffAngle = pi / 1.95;
		const float cutoffAngle = 1.6110731556870734;
		const float steepness = 1.5;
		const float EE = 1000.0;

		float sunIntensity( float zenithAngleCos ) {
			zenithAngleCos = clamp( zenithAngleCos, -1.0, 1.0 );
			return EE * max( 0.0, 1.0 - pow( e, -( ( cutoffAngle - acos( zenithAngleCos ) ) / steepness ) ) );
		}

		vec3 totalMie( float T ) {
			float c = ( 0.2 * T ) * 10E-18;
			return 0.434 * c * MieConst;
		}

		void main() {

			vec4 worldPosition = modelMatrix * vec4( position, 1.0 );
			vWorldPosition = worldPosition.xyz;

			gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
			gl_Position.z = gl_Position.w; // set z to camera.far

			vSunDirection = normalize( sunPosition );

			vSunE = sunIntensity( dot( vSunDirection, up ) );

			vSunfade = 1.0 - clamp( 1.0 - exp( ( sunPosition.y / 450000.0 ) ), 0.0, 1.0 );

			float rayleighCoefficient = rayleigh - ( 1.0 * ( 1.0 - vSunfade ) );

			// extinction (absorbtion + out scattering)
			// rayleigh coefficients
			vBetaR = totalRayleigh * rayleighCoefficient;

			// mie coefficients
			vBetaM = totalMie( turbidity ) * mieCoefficient;

		}`,fragmentShader:`
		varying vec3 vWorldPosition;
		varying vec3 vSunDirection;
		varying float vSunfade;
		varying vec3 vBetaR;
		varying vec3 vBetaM;
		varying float vSunE;

		uniform float mieDirectionalG;
		uniform vec3 up;

		// constants for atmospheric scattering
		const float pi = 3.141592653589793238462643383279502884197169;

		const float n = 1.0003; // refractive index of air
		const float N = 2.545E25; // number of molecules per unit volume for air at 288.15K and 1013mb (sea level -45 celsius)

		// optical length at zenith for molecules
		const float rayleighZenithLength = 8.4E3;
		const float mieZenithLength = 1.25E3;
		// 66 arc seconds -> degrees, and the cosine of that
		const float sunAngularDiameterCos = 0.999956676946448443553574619906976478926848692873900859324;

		// 3.0 / ( 16.0 * pi )
		const float THREE_OVER_SIXTEENPI = 0.05968310365946075;
		// 1.0 / ( 4.0 * pi )
		const float ONE_OVER_FOURPI = 0.07957747154594767;

		float rayleighPhase( float cosTheta ) {
			return THREE_OVER_SIXTEENPI * ( 1.0 + pow( cosTheta, 2.0 ) );
		}

		float hgPhase( float cosTheta, float g ) {
			float g2 = pow( g, 2.0 );
			float inverse = 1.0 / pow( 1.0 - 2.0 * g * cosTheta + g2, 1.5 );
			return ONE_OVER_FOURPI * ( ( 1.0 - g2 ) * inverse );
		}

		void main() {

			vec3 direction = normalize( vWorldPosition - cameraPosition );

			// optical length
			// cutoff angle at 90 to avoid singularity in next formula.
			float zenithAngle = acos( max( 0.0, dot( up, direction ) ) );
			float inverse = 1.0 / ( cos( zenithAngle ) + 0.15 * pow( 93.885 - ( ( zenithAngle * 180.0 ) / pi ), -1.253 ) );
			float sR = rayleighZenithLength * inverse;
			float sM = mieZenithLength * inverse;

			// combined extinction factor
			vec3 Fex = exp( -( vBetaR * sR + vBetaM * sM ) );

			// in scattering
			float cosTheta = dot( direction, vSunDirection );

			float rPhase = rayleighPhase( cosTheta * 0.5 + 0.5 );
			vec3 betaRTheta = vBetaR * rPhase;

			float mPhase = hgPhase( cosTheta, mieDirectionalG );
			vec3 betaMTheta = vBetaM * mPhase;

			vec3 Lin = pow( vSunE * ( ( betaRTheta + betaMTheta ) / ( vBetaR + vBetaM ) ) * ( 1.0 - Fex ), vec3( 1.5 ) );
			Lin *= mix( vec3( 1.0 ), pow( vSunE * ( ( betaRTheta + betaMTheta ) / ( vBetaR + vBetaM ) ) * Fex, vec3( 1.0 / 2.0 ) ), clamp( pow( 1.0 - dot( up, vSunDirection ), 5.0 ), 0.0, 1.0 ) );

			// nightsky
			float theta = acos( direction.y ); // elevation --> y-axis, [-pi/2, pi/2]
			float phi = atan( direction.z, direction.x ); // azimuth --> x-axis [-pi/2, pi/2]
			vec2 uv = vec2( phi, theta ) / vec2( 2.0 * pi, pi ) + vec2( 0.5, 0.0 );
			vec3 L0 = vec3( 0.1 ) * Fex;

			// composition + solar disc
			float sundisk = smoothstep( sunAngularDiameterCos, sunAngularDiameterCos + 0.00002, cosTheta );
			L0 += ( vSunE * 19000.0 * Fex ) * sundisk;

			vec3 texColor = ( Lin + L0 ) * 0.04 + vec3( 0.0, 0.0003, 0.00075 );

			vec3 retColor = pow( texColor, vec3( 1.0 / ( 1.2 + ( 1.2 * vSunfade ) ) ) );

			gl_FragColor = vec4( retColor, 1.0 );

			#include <tonemapping_fragment>
			#include <colorspace_fragment>

		}`};var Ze,At,Tt,bt,nt,_t="assembled",As,Mn=!0,Io=performance.now(),oe=i=>document.querySelector(i),tn=matchMedia("(prefers-reduced-motion: reduce)"),Po=null,vn=null,or=!1,Tn=null,Rn=null,un=null,yi=null,Fi=null,Sc="warm",Rt=null,Mc=!1,vi=new Map;async function Gu(){if(!(or||nt)){or=!0,oe("#open").disabled=!0,oe("#state").textContent="\u041F\u043E\u0434\u0433\u043E\u0442\u0430\u0432\u043B\u0438\u0432\u0430\u0435\u043C \u043C\u043E\u0434\u0435\u043B\u044C\u2026";try{Ze=new eo({antialias:!0,alpha:!1}),Ze.setPixelRatio(Math.min(devicePixelRatio,1.7)),Ze.shadowMap.enabled=!0,Ze.shadowMap.autoUpdate=!1,Ze.shadowMap.needsUpdate=!0,Ze.shadowMap.type=Al,Ze.setClearColor(15657438),Ze.toneMapping=Tl,Ze.toneMappingExposure=.9,oe("#canvas").appendChild(Ze.domElement),At=new Ys,At.fog=new to(15657438,45,95),Tt=new xt(37,1,.1,150),Tt.position.set(18,9,22),bt=new Ro(Tt,Ze.domElement),bt.target.set(0,1.4,3),bt.minDistance=6,bt.maxDistance=65,bt.maxPolarAngle=Math.PI*.49,bt.enableDamping=!0,bt.addEventListener("change",()=>Mn=!0),bt.addEventListener("start",()=>{Tn=null,Rn=null});let i=new xs(Ze),e=new rr,t=new Ys;e.scale.setScalar(1e3),e.material.uniforms.turbidity.value=6,e.material.uniforms.rayleigh.value=1.3,e.material.uniforms.mieCoefficient.value=.005,e.material.uniforms.mieDirectionalG.value=.85,e.material.uniforms.sunPosition.value.set(-9,8,10),t.add(e),At.environment=i.fromScene(t,.04,.1,1500).texture,At.environmentIntensity=.35,e.geometry.dispose(),e.material.dispose(),i.dispose(),At.add(new _o(15397119,9075805,.65));let n=new Ss(16768942,2.6);n.position.set(-9,10,10),n.castShadow=!0,n.shadow.mapSize.set(1024,1024),Object.assign(n.shadow.camera,{left:-20,right:20,top:20,bottom:-20,near:.5,far:70}),n.shadow.bias=-3e-4,n.shadow.normalBias=.025,n.shadow.radius=3,At.add(n);let s=document.createElement("canvas");s.width=s.height=256;let r=s.getContext("2d"),o=r.createImageData(256,256),a=19;for(let d=0;d<o.data.length;d+=4){a=a*1664525+1013904223>>>0;let f=(a/4294967296-.5)*15;o.data[d]=195+f,o.data[d+1]=194+f,o.data[d+2]=175+f,o.data[d+3]=255}r.putImageData(o,0,0);let l=new ho(s);l.colorSpace=gt,l.wrapS=l.wrapT=Hn,l.repeat.set(18,18);let c=new tt(new Yn(180,180),new kt({color:16777215,map:l,roughness:1}));c.rotation.x=-Math.PI/2,c.position.y=-.4,c.receiveShadow=!0,At.add(c);let h=oe("#model"),u;if(h){let d=Uint8Array.from(atob(h.textContent.trim()),f=>f.charCodeAt(0));u=await new sr().parseAsync(d.buffer,"")}else u=await new sr().loadAsync("./stroyka-polished.glb");nt=u.scene,window.__houseQA={},nt.traverse(d=>{if(d.isMesh){d.castShadow=!0,d.receiveShadow=!0;for(let f of Array.isArray(d.material)?d.material:[d.material])f.name==="glass"&&(f.color.setRGB(.92,.96,.95),f.roughness=.055,f.transmission=.95,f.thickness=.02,f.ior=1.45),f.name==="roof"&&(f.color.setHex(4344658),f.metalness=.8,f.roughness=.35),f.name==="oak"&&f.color.setRGB(.8,.72,.61)}}),At.add(nt),oe("#open").hidden=!0,oe("#state").textContent="\u041C\u043E\u0434\u0435\u043B\u044C \u0437\u0430\u0433\u0440\u0443\u0436\u0435\u043D\u0430 \xB7 \u0432\u0440\u0430\u0449\u0430\u0439\u0442\u0435 \u043C\u044B\u0448\u044C\u044E \u0438\u043B\u0438 \u043F\u0430\u043B\u044C\u0446\u0435\u043C",oe("#toolbar").hidden=!1,window.__HOUSE_STATUS__={loaded:!0,meshCount:0,mode:_t,spread:0},nt.traverse(d=>{d.isMesh&&window.__HOUSE_STATUS__.meshCount++}),Fi=Du(nt,At),qu(Sc),yi=Pu({camera:Tt,canvas:Ze.domElement,data:Cu,isActive:()=>_t==="walk",onChange:d=>{window.__HOUSE_STATUS__.walk=d,Mn=!0}}),Rt=Ru({house:nt,scene:At,renderer:Ze,camera:Tt,controls:bt,onUpdate:(d,f)=>{window.__HOUSE_STATUS__.construction=d,window.__houseQA.construction=f,oe("#build-title").textContent!==d.title&&(oe("#build-title").textContent=d.title),oe("#build-caption").textContent!==d.caption&&(oe("#build-caption").textContent=d.caption),oe("#build-number").textContent=String(d.index+1).padStart(2,"0")+" / 07",oe("#build-progress").value=Math.round(d.progress*100),oe("#build-output").textContent=Math.round(d.progress*100)+"%",oe("#build-play").textContent=d.playing?"\u041F\u0430\u0443\u0437\u0430":"\u041F\u0440\u043E\u0434\u043E\u043B\u0436\u0438\u0442\u044C",oe("#build-play").setAttribute("aria-pressed",String(d.playing)),oe("#build-play").disabled=tn.matches,document.querySelectorAll("[data-build-step]").forEach(g=>g.setAttribute("aria-pressed",String(Number(g.dataset.buildStep)===d.index))),Mn=!0},onComplete:()=>Xt("assembled")}),or=!1,z_(),Bi(0,"assembled"),ar(),!Mc&&!tn.matches&&(Mc=!0,Xu(!0)),Io=performance.now(),Tc()}catch(i){oe("#state").textContent="\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u043E\u0442\u043A\u0440\u044B\u0442\u044C 3D \u043D\u0430 \u044D\u0442\u043E\u043C \u0443\u0441\u0442\u0440\u043E\u0439\u0441\u0442\u0432\u0435. \u041E\u0442\u043A\u0440\u043E\u0439\u0442\u0435 PNG-\u0440\u0435\u043D\u0434\u0435\u0440\u044B \u0438\u0437 \u043A\u043E\u043C\u043F\u043B\u0435\u043A\u0442\u0430.",or=!1,Ze&&(Ze.dispose(),Ze.domElement.remove(),Ze=null),nt=null,oe("#open").disabled=!1,window.__HOUSE_STATUS__={loaded:!1,error:String(i)}}}}function ar(){if(!Ze)return;let i=oe("#canvas"),e=i.clientWidth,t=i.clientHeight;Ze.setSize(e,t),Tt.aspect=e/t,Tt.zoom=_t==="walk"?1:Math.min(1,Math.max(.4,Tt.aspect/1.3)),Tt.updateProjectionMatrix(),Mn=!0}var bc=["09_wall_core","10_insulation","11_vent_gap","12_cladding","13_inner_finish"],O_=["05_roof","14_rafters","15_roof_underlay","16_roof_battens"],Wu={"09_wall_core":["\u041D\u0435\u0441\u0443\u0449\u0438\u0439 \u0441\u043B\u043E\u0439","\u0424\u043E\u0440\u043C\u0438\u0440\u0443\u0435\u0442 \u043A\u043E\u043D\u0441\u0442\u0440\u0443\u043A\u0446\u0438\u044E \u0441\u0442\u0435\u043D\u044B \u0438 \u043F\u0435\u0440\u0435\u0434\u0430\u0451\u0442 \u043D\u0430\u0433\u0440\u0443\u0437\u043A\u0438. \u041C\u0430\u0442\u0435\u0440\u0438\u0430\u043B \u0432\u044B\u0431\u0438\u0440\u0430\u044E\u0442 \u0432\u043C\u0435\u0441\u0442\u0435 \u0441 \u043A\u043E\u043D\u0441\u0442\u0440\u0443\u043A\u0442\u0438\u0432\u043D\u043E\u0439 \u0441\u0445\u0435\u043C\u043E\u0439 \u0434\u043E\u043C\u0430.","\u0420\u0430\u0441\u0447\u0451\u0442, \u043C\u0430\u0442\u0435\u0440\u0438\u0430\u043B \u0438 \u0442\u043E\u043B\u0449\u0438\u043D\u0430 \u0434\u043B\u044F \u044D\u0442\u043E\u0433\u043E \u044D\u0441\u043A\u0438\u0437\u0430 \u043D\u0435 \u0443\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043D\u044B."],"10_insulation":["\u0422\u0435\u043F\u043B\u043E\u0438\u0437\u043E\u043B\u044F\u0446\u0438\u044F","\u041F\u043E\u043C\u043E\u0433\u0430\u0435\u0442 \u0443\u043C\u0435\u043D\u044C\u0448\u0438\u0442\u044C \u0442\u0435\u043F\u043B\u043E\u043F\u0435\u0440\u0435\u0434\u0430\u0447\u0443 \u0447\u0435\u0440\u0435\u0437 \u043E\u0433\u0440\u0430\u0436\u0434\u0435\u043D\u0438\u0435. \u042D\u0444\u0444\u0435\u043A\u0442 \u0437\u0430\u0432\u0438\u0441\u0438\u0442 \u043E\u0442 \u0432\u0441\u0435\u0439 \u0441\u0442\u0435\u043D\u044B \u0438 \u043A\u0430\u0447\u0435\u0441\u0442\u0432\u0430 \u0432\u044B\u043F\u043E\u043B\u043D\u0435\u043D\u0438\u044F \u0443\u0437\u043B\u043E\u0432.","\u0412\u043B\u0430\u0433\u0430, \u0441\u043E\u0432\u043C\u0435\u0441\u0442\u0438\u043C\u043E\u0441\u0442\u044C \u0441\u043B\u043E\u0451\u0432 \u0438 \u0445\u0430\u0440\u0430\u043A\u0442\u0435\u0440\u0438\u0441\u0442\u0438\u043A\u0438 \u0443\u0442\u0435\u043F\u043B\u0438\u0442\u0435\u043B\u044F \u0442\u0440\u0435\u0431\u0443\u044E\u0442 \u043F\u0440\u043E\u0432\u0435\u0440\u043A\u0438."],"11_vent_gap":["\u0417\u0430\u0449\u0438\u0442\u043D\u044B\u0439 \u0441\u043B\u043E\u0439","\u041F\u043E\u043A\u0430\u0437\u044B\u0432\u0430\u0435\u0442 \u043C\u0435\u0441\u0442\u043E \u0437\u0430\u0449\u0438\u0442\u043D\u043E\u0433\u043E \u0441\u043B\u043E\u044F \u0432 \u0432\u044B\u0431\u0440\u0430\u043D\u043D\u043E\u0439 \u0443\u0447\u0435\u0431\u043D\u043E\u0439 \u0441\u0445\u0435\u043C\u0435. \u0415\u0433\u043E \u043D\u0430\u0437\u043D\u0430\u0447\u0435\u043D\u0438\u0435 \u0437\u0430\u0432\u0438\u0441\u0438\u0442 \u043E\u0442 \u0442\u0438\u043F\u0430 \u0444\u0430\u0441\u0430\u0434\u0430.","\u041C\u0435\u043C\u0431\u0440\u0430\u043D\u0430, \u0432\u043E\u0437\u0434\u0443\u0448\u043D\u044B\u0439 \u0437\u0430\u0437\u043E\u0440 \u0438 \u043F\u0430\u0440\u043E\u0438\u0437\u043E\u043B\u044F\u0446\u0438\u044F \u043D\u0435 \u0432\u0437\u0430\u0438\u043C\u043E\u0437\u0430\u043C\u0435\u043D\u044F\u0435\u043C\u044B; \u043A\u043E\u043D\u043A\u0440\u0435\u0442\u043D\u043E\u0435 \u0440\u0435\u0448\u0435\u043D\u0438\u0435 \u043D\u0435 \u0432\u044B\u0431\u0440\u0430\u043D\u043E."],"12_cladding":["\u041D\u0430\u0440\u0443\u0436\u043D\u0430\u044F \u043E\u0442\u0434\u0435\u043B\u043A\u0430","\u0417\u0430\u0434\u0430\u0451\u0442 \u0432\u043D\u0435\u0448\u043D\u0438\u0439 \u0432\u0438\u0434 \u0438 \u0437\u0430\u0449\u0438\u0449\u0430\u0435\u0442 \u043D\u0438\u0436\u0435\u043B\u0435\u0436\u0430\u0449\u0438\u0435 \u0441\u043B\u043E\u0438 \u0432 \u043F\u0440\u0435\u0434\u0435\u043B\u0430\u0445 \u0432\u044B\u0431\u0440\u0430\u043D\u043D\u043E\u0439 \u0441\u0438\u0441\u0442\u0435\u043C\u044B \u0444\u0430\u0441\u0430\u0434\u0430.","\u041D\u0443\u0436\u043D\u043E \u0443\u0447\u0438\u0442\u044B\u0432\u0430\u0442\u044C \u043E\u0431\u0441\u043B\u0443\u0436\u0438\u0432\u0430\u043D\u0438\u0435, \u043A\u0440\u0435\u043F\u043B\u0435\u043D\u0438\u044F, \u0432\u043B\u0430\u0433\u0443 \u0438 \u0442\u0440\u0435\u0431\u043E\u0432\u0430\u043D\u0438\u044F \u043A\u043E\u043D\u043A\u0440\u0435\u0442\u043D\u043E\u0433\u043E \u043C\u0430\u0442\u0435\u0440\u0438\u0430\u043B\u0430."],"13_inner_finish":["\u0412\u043D\u0443\u0442\u0440\u0435\u043D\u043D\u044F\u044F \u043E\u0442\u0434\u0435\u043B\u043A\u0430","\u0424\u043E\u0440\u043C\u0438\u0440\u0443\u0435\u0442 \u043F\u043E\u0432\u0435\u0440\u0445\u043D\u043E\u0441\u0442\u044C \u0441\u043E \u0441\u0442\u043E\u0440\u043E\u043D\u044B \u043F\u043E\u043C\u0435\u0449\u0435\u043D\u0438\u044F \u0438 \u0432\u043B\u0438\u044F\u0435\u0442 \u043D\u0430 \u0440\u0435\u043C\u043E\u043D\u0442 \u0438 \u044D\u043A\u0441\u043F\u043B\u0443\u0430\u0442\u0430\u0446\u0438\u044E.","\u0421\u043E\u0441\u0442\u0430\u0432 \u0438 \u043F\u0440\u0438\u0433\u043E\u0434\u043D\u043E\u0441\u0442\u044C \u0434\u043B\u044F \u0432\u043B\u0430\u0436\u043D\u044B\u0445 \u043F\u043E\u043C\u0435\u0449\u0435\u043D\u0438\u0439 \u043F\u043E\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0430\u044E\u0442\u0441\u044F \u043E\u0442\u0434\u0435\u043B\u044C\u043D\u043E."],"14_rafters":["\u0421\u0442\u0440\u043E\u043F\u0438\u043B\u044C\u043D\u0430\u044F \u0441\u0438\u0441\u0442\u0435\u043C\u0430","\u0412\u0438\u0437\u0443\u0430\u043B\u0438\u0437\u0438\u0440\u0443\u0435\u0442 \u043D\u0435\u0441\u0443\u0449\u0443\u044E \u0441\u0445\u0435\u043C\u0443 \u043A\u0440\u043E\u0432\u043B\u0438 \u0438 \u043F\u043E\u043B\u043E\u0436\u0435\u043D\u0438\u0435 \u0434\u0435\u0440\u0435\u0432\u044F\u043D\u043D\u044B\u0445 \u044D\u043B\u0435\u043C\u0435\u043D\u0442\u043E\u0432.","\u0421\u0435\u0447\u0435\u043D\u0438\u044F, \u0448\u0430\u0433, \u043D\u0430\u0433\u0440\u0443\u0437\u043A\u0438 \u0438 \u0441\u043E\u0435\u0434\u0438\u043D\u0435\u043D\u0438\u044F \u0437\u0434\u0435\u0441\u044C \u043D\u0435 \u0440\u0430\u0441\u0441\u0447\u0438\u0442\u0430\u043D\u044B."],"15_roof_underlay":["\u041F\u043E\u0434\u043A\u0440\u043E\u0432\u0435\u043B\u044C\u043D\u044B\u0439 \u0441\u043B\u043E\u0439","\u041F\u043E\u043A\u0430\u0437\u044B\u0432\u0430\u0435\u0442 \u043E\u0442\u0434\u0435\u043B\u044C\u043D\u044B\u0439 \u0441\u043B\u043E\u0439 \u043F\u043E\u0434 \u043A\u0440\u043E\u0432\u0435\u043B\u044C\u043D\u044B\u043C \u043F\u043E\u043A\u0440\u044B\u0442\u0438\u0435\u043C.","\u0422\u0438\u043F \u043C\u0435\u043C\u0431\u0440\u0430\u043D\u044B, \u0432\u0435\u043D\u0442\u0438\u043B\u044F\u0446\u0438\u044F \u0438 \u043F\u0440\u0438\u043C\u044B\u043A\u0430\u043D\u0438\u044F \u0437\u0430\u0432\u0438\u0441\u044F\u0442 \u043E\u0442 \u0441\u043E\u0433\u043B\u0430\u0441\u043E\u0432\u0430\u043D\u043D\u043E\u0433\u043E \u0440\u0435\u0448\u0435\u043D\u0438\u044F."],"16_roof_battens":["\u041E\u0431\u0440\u0435\u0448\u0451\u0442\u043A\u0430","\u041F\u043E\u043A\u0430\u0437\u044B\u0432\u0430\u0435\u0442 \u043F\u0440\u043E\u043C\u0435\u0436\u0443\u0442\u043E\u0447\u043D\u044B\u0435 \u044D\u043B\u0435\u043C\u0435\u043D\u0442\u044B \u0434\u043B\u044F \u043A\u0440\u0435\u043F\u043B\u0435\u043D\u0438\u044F \u043F\u043E\u043A\u0440\u044B\u0442\u0438\u044F.","\u0428\u0430\u0433, \u0441\u0435\u0447\u0435\u043D\u0438\u044F \u0438 \u043A\u0440\u0435\u043F\u043B\u0435\u043D\u0438\u044F \u043F\u043E\u0434\u0431\u0438\u0440\u0430\u044E\u0442 \u043F\u043E\u0434 \u043A\u043E\u043D\u043A\u0440\u0435\u0442\u043D\u043E\u0435 \u043F\u043E\u043A\u0440\u044B\u0442\u0438\u0435."],"05_roof":["\u0424\u0430\u043B\u044C\u0446\u0435\u0432\u0430\u044F \u0441\u0442\u0430\u043B\u044C\u043D\u0430\u044F \u043A\u0440\u043E\u0432\u043B\u044F","\u041F\u0440\u0435\u0434\u043B\u0430\u0433\u0430\u0435\u043C\u044B\u0439 \u0432\u0430\u0440\u0438\u0430\u043D\u0442: \u0441\u0442\u0430\u043B\u044C\u043D\u044B\u0435 \u043B\u0438\u0441\u0442\u044B \u0441 \u0441\u043E\u0435\u0434\u0438\u043D\u0435\u043D\u0438\u0435\u043C \u0444\u0430\u043B\u044C\u0446\u0430\u043C\u0438. \u0412 \u043C\u043E\u0434\u0435\u043B\u0438 \u043F\u043E\u043A\u0430\u0437\u0430\u043D \u0432\u043D\u0435\u0448\u043D\u0438\u0439 \u0432\u0438\u0434 \u0442\u0430\u043A\u043E\u0433\u043E \u043F\u043E\u043A\u0440\u044B\u0442\u0438\u044F.","\u041F\u0440\u043E\u0438\u0437\u0432\u043E\u0434\u0438\u0442\u0435\u043B\u044C, \u0442\u043E\u043B\u0449\u0438\u043D\u0430 \u0441\u0442\u0430\u043B\u0438, \u0437\u0430\u0449\u0438\u0442\u043D\u043E\u0435 \u043F\u043E\u043A\u0440\u044B\u0442\u0438\u0435, \u043A\u0440\u0435\u043F\u043B\u0435\u043D\u0438\u044F, \u0448\u0443\u043C \u0434\u043E\u0436\u0434\u044F \u0438 \u0433\u0430\u0440\u0430\u043D\u0442\u0438\u044F \u0435\u0449\u0451 \u043D\u0435 \u043F\u043E\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043D\u044B. \u0426\u0435\u043D\u0430 \u0437\u0430\u0432\u0438\u0441\u0438\u0442 \u043E\u0442 \u0441\u043E\u0433\u043B\u0430\u0441\u043E\u0432\u0430\u043D\u043D\u043E\u0439 \u0441\u0438\u0441\u0442\u0435\u043C\u044B \u0438 \u043A\u043E\u043C\u043F\u043B\u0435\u043A\u0442\u0430\u0446\u0438\u0438."]};function wc(){vn&&(At.remove(vn),vn.geometry.dispose(),vn.material.dispose(),vn=null)}function Ec(i){Po=i,window.__HOUSE_STATUS__.selectedLayer=i,wc();let e=nt.getObjectByName(i);nt.updateMatrixWorld(!0),vn=new Mo(e,11950884),vn.material.transparent=!0,vn.material.opacity=.35,At.add(vn);let t=Wu[i];oe("#detail-title").textContent=t[0],oe("#detail-purpose").textContent=t[1],oe("#detail-caution").textContent=t[2],oe("#detail").hidden=!1,document.querySelectorAll("[data-layer]").forEach(n=>n.setAttribute("aria-pressed",String(n.dataset.layer===i))),ar(),Mn=!0}function Xt(i){if(!nt)return;if(Rt&&Rt.cancel(),oe("#build-hud").hidden=!0,oe("#construction-panel").hidden=!0,Qn(),yi&&yi.leave(),_t=i,bt.enabled=i!=="walk",Tt.fov=i==="walk"?68:37,Mn=!0,wc(),Po=null,oe("#detail").hidden=!0,Ze.shadowMap.needsUpdate=!0,window.__HOUSE_STATUS__.mode=i,window.__HOUSE_STATUS__.selectedLayer=null,nt.traverse(n=>n.visible=!0),vi.clear(),Bi(i==="exploded"||i==="wall"?1:0,i),i==="cutaway"||i==="plan"){for(let n of["04_ceiling",...O_,...bc])nt.getObjectByName(n).visible=!1;nt.traverse(n=>{(n.name.startsWith("south facade")||n.name.startsWith("east facade")||n.name.startsWith("pergola"))&&(n.visible=!1)})}let e={assembled:[18,9,22,0,1.4,3],exploded:[24,19,25,1,4.4,0],terrace:[10,4,14,3,1.15,7],wall:[17,5,-6,8,1.5,-1.35],cutaway:[14,25,18,0,0,0],plan:[0,32,.01,0,0,0],inside:[5,1.65,3.9,2,1.3,-.1]},t=e[i]||e.inside;if(bt.minDistance=i==="inside"?.3:i==="wall"||i==="terrace"?3:6,bt.maxDistance=i==="inside"?12:65,Tn=new C(...t.slice(0,3)),Rn=new C(...t.slice(3)),document.querySelectorAll("[data-mode]").forEach(n=>n.setAttribute("aria-pressed",String(n.dataset.mode===i))),oe("#spread-controls").hidden=i!=="exploded",oe("#layer-controls").hidden=!(i==="wall"||i==="exploded"),oe("#state").textContent={assembled:"\u0412\u0440\u0430\u0449\u0430\u0439\u0442\u0435 \u043C\u043E\u0434\u0435\u043B\u044C. \u041C\u043E\u0436\u043D\u043E \u0432\u044B\u0431\u0440\u0430\u0442\u044C \u0443\u0437\u0435\u043B \u0441\u0442\u0435\u043D\u044B \u0438\u043B\u0438 \u0440\u0430\u0441\u043A\u0440\u044B\u0442\u044C \u043A\u0440\u043E\u0432\u043B\u044E.",exploded:"\u041F\u0440\u0435\u0434\u043B\u0430\u0433\u0430\u0435\u043C\u0430\u044F \u0444\u0430\u043B\u044C\u0446\u0435\u0432\u0430\u044F \u0441\u0442\u0430\u043B\u044C\u043D\u0430\u044F \u043A\u0440\u043E\u0432\u043B\u044F. \u041F\u043E\u043B\u0437\u0443\u043D\u043E\u043A \u0443\u043F\u0440\u0430\u0432\u043B\u044F\u0435\u0442 \u0440\u0430\u0437\u043D\u0435\u0441\u0435\u043D\u0438\u0435\u043C \u0441\u043B\u043E\u0451\u0432.",wall:"\u0423\u0447\u0435\u0431\u043D\u044B\u0439 \u0444\u0440\u0430\u0433\u043C\u0435\u043D\u0442 \u0441\u0442\u0435\u043D\u044B. \u0412\u044B\u0431\u0435\u0440\u0438\u0442\u0435 \u0441\u043B\u043E\u0439 \u0434\u043B\u044F \u043F\u043E\u044F\u0441\u043D\u0435\u043D\u0438\u044F; \u0441\u043E\u0441\u0442\u0430\u0432 \u0442\u0440\u0435\u0431\u0443\u0435\u0442 \u043F\u0440\u043E\u0432\u0435\u0440\u043A\u0438.",cutaway:"\u041E\u0442\u043A\u0440\u044B\u0442\u0430\u044F \u043F\u043B\u0430\u043D\u0438\u0440\u043E\u0432\u043A\u0430 \u0438 \u043C\u0435\u0431\u0435\u043B\u044C. \u0421\u043E\u0441\u0442\u0430\u0432 \u043F\u043E\u043C\u0435\u0449\u0435\u043D\u0438\u0439 \u043F\u043E\u043A\u0430 \u043D\u0435 \u0441\u043E\u0433\u043B\u0430\u0441\u043E\u0432\u0430\u043D.",plan:"\u041F\u043B\u0430\u043D \u0441\u0432\u0435\u0440\u0445\u0443. \u041F\u0440\u043E\u043F\u043E\u0440\u0446\u0438\u0438 \u0438 \u0440\u0430\u0437\u043C\u0435\u0440\u044B \u0442\u0440\u0435\u0431\u0443\u044E\u0442 \u0441\u043E\u0433\u043B\u0430\u0441\u043E\u0432\u0430\u043D\u0438\u044F.",terrace:"\u0422\u0435\u0440\u0440\u0430\u0441\u0430 \u043A\u0440\u0443\u043F\u043D\u044B\u043C \u043F\u043B\u0430\u043D\u043E\u043C: \u0434\u0435\u0440\u0435\u0432\u044F\u043D\u043D\u044B\u0439 \u043D\u0430\u0441\u0442\u0438\u043B \u0438 \u043F\u0435\u0440\u0433\u043E\u043B\u0430. \u041F\u043E\u0440\u043E\u0434\u0430 \u0434\u0440\u0435\u0432\u0435\u0441\u0438\u043D\u044B, \u0437\u0430\u0449\u0438\u0442\u0430 \u0438 \u043A\u0440\u0435\u043F\u043B\u0435\u043D\u0438\u044F \u043F\u043E\u043A\u0430 \u043D\u0435 \u0432\u044B\u0431\u0440\u0430\u043D\u044B.",inside:"\u041A\u043E\u043D\u0442\u0440\u043E\u043B\u044C\u043D\u044B\u0439 \u0440\u0430\u043A\u0443\u0440\u0441 \u0433\u043E\u0441\u0442\u0438\u043D\u043E\u0439. \u042D\u0442\u043E \u043E\u0441\u043C\u043E\u0442\u0440, \u0430 \u043D\u0435 \u043F\u0440\u043E\u0433\u0443\u043B\u043A\u0430 \u0441 \u043F\u0440\u043E\u0432\u0435\u0440\u043A\u043E\u0439 \u0441\u0442\u043E\u043B\u043A\u043D\u043E\u0432\u0435\u043D\u0438\u0439."}[i],oe("#walk-hud").hidden=i!=="walk",oe("#walk-panel").hidden=i!=="walk",oe("#interior-controls").hidden=!["walk","inside","cutaway","plan"].includes(i),Fi.apply(Sc),i==="walk"){Tn=Rn=null;for(let n of vi.keys()){let s=nt.getObjectByName(n);s.position.x=0,s.position.y=0}nt.updateMatrixWorld(!0),yi.enter(),oe("#state").textContent="\u041F\u0440\u043E\u0433\u0443\u043B\u043A\u0430: \u043F\u0440\u043E\u0432\u043E\u0434\u0438\u0442\u0435 \u043F\u043E \u0438\u0437\u043E\u0431\u0440\u0430\u0436\u0435\u043D\u0438\u044E \u0434\u043B\u044F \u043E\u0431\u0437\u043E\u0440\u0430; \u043F\u0435\u0440\u0435\u043C\u0435\u0449\u0430\u0439\u0442\u0435\u0441\u044C \u0441\u0442\u0440\u0435\u043B\u043A\u0430\u043C\u0438 \u043D\u0430 \u044D\u043A\u0440\u0430\u043D\u0435 \u0438\u043B\u0438 \u043A\u043B\u0430\u0432\u0438\u0448\u0430\u043C\u0438 WASD. \u0421\u0442\u0435\u043D\u044B, \u0441\u0442\u0435\u043A\u043B\u043E \u0438 \u043C\u0435\u0431\u0435\u043B\u044C \u043E\u0433\u0440\u0430\u043D\u0438\u0447\u0438\u0432\u0430\u044E\u0442 \u043F\u0440\u043E\u0445\u043E\u0434."}ar(),i==="wall"&&Ec("10_insulation")}var F_=i=>{let e=en.clamp(i,0,1);return e*e*(3-2*e)},Vu=(i,e,t)=>F_((i-e)/(t-e));function Qn(){un=null;let i=oe("#play");i&&(i.textContent="\u041F\u043E\u043A\u0430\u0437\u0430\u0442\u044C \u0440\u0430\u0437\u0431\u043E\u0440\u043A\u0443",i.setAttribute("aria-pressed","false")),window.__HOUSE_STATUS__&&(window.__HOUSE_STATUS__.playing=!1)}function Bi(i,e="exploded"){let t=en.clamp(i,0,1);window.__HOUSE_STATUS__.spread=t,oe("#spread").value=Math.round(t*100),oe("#spread-value").textContent=Math.round(t*100)+"%";let n={"05_roof":[5.1,0,.25],"16_roof_battens":[4.4,.13,.38],"15_roof_underlay":[3.8,.26,.51],"14_rafters":[2.7,.39,.64],"04_ceiling":[1.1,.52,.77]};for(let[o,[a,l,c]]of Object.entries(n))vi.set(o,{x:0,y:e==="exploded"?a*Vu(t,l,c):0});let s=e==="wall"?t:Vu(t,.69,1);for(let[o,a]of Object.entries({"09_wall_core":.2,"10_insulation":.9,"11_vent_gap":1.6,"12_cladding":2.3,"13_inner_finish":-.3}))vi.set(o,{x:e==="exploded"||e==="wall"?a*s:0,y:0});let r=t===0?"\u0414\u043E\u043C \u0441\u043E\u0431\u0440\u0430\u043D":t<.2?"01 / \u0421\u0442\u0430\u043B\u044C\u043D\u043E\u0435 \u043F\u043E\u043A\u0440\u044B\u0442\u0438\u0435":t<.35?"02 / \u041E\u0431\u0440\u0435\u0448\u0451\u0442\u043A\u0430":t<.48?"03 / \u041F\u043E\u0434\u043A\u0440\u043E\u0432\u0435\u043B\u044C\u043D\u044B\u0439 \u0441\u043B\u043E\u0439":t<.61?"04 / \u0421\u0442\u0440\u043E\u043F\u0438\u043B\u0430":t<.77?"05 / \u041F\u0435\u0440\u0435\u043A\u0440\u044B\u0442\u0438\u0435":t<1?"06 / \u0424\u0440\u0430\u0433\u043C\u0435\u043D\u0442 \u0441\u0442\u0435\u043D\u044B":"\u0412\u0441\u0435 \u0441\u043B\u043E\u0438 \u0440\u0430\u0441\u043A\u0440\u044B\u0442\u044B";oe("#assembly-stage").textContent=r,window.__HOUSE_STATUS__.stage=r,Mn=!0}function B_(){if(!nt)return;if(un){Qn();return}_t!=="exploded"&&Xt("exploded");let i=window.__HOUSE_STATUS__.spread>=.999?0:window.__HOUSE_STATUS__.spread;if(Bi(i),tn.matches){Bi(1),oe("#state").textContent="\u0421\u043B\u043E\u0438 \u0440\u0430\u0441\u043A\u0440\u044B\u0442\u044B \u0431\u0435\u0437 \u0430\u043D\u0438\u043C\u0430\u0446\u0438\u0438: \u0443\u0447\u0442\u0435\u043D\u0430 \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0430 \u0443\u043C\u0435\u043D\u044C\u0448\u0435\u043D\u0438\u044F \u0434\u0432\u0438\u0436\u0435\u043D\u0438\u044F.";return}un={progress:i,direction:1},window.__HOUSE_STATUS__.playing=!0,oe("#play").textContent="\u041F\u0430\u0443\u0437\u0430",oe("#play").setAttribute("aria-pressed","true")}function Xu(i=!0){if(nt){Xt("assembled"),_t="construction",Mc=!0,window.__HOUSE_STATUS__.mode="construction",Tn=Rn=null;for(let e of vi.keys()){let t=nt.getObjectByName(e);t.position.x=0,t.position.y=0}nt.updateMatrixWorld(!0),oe("#build-hud").hidden=!1,oe("#construction-panel").hidden=!1,Rt.start({autoplay:i&&!tn.matches}),oe("#state").textContent="\u0418\u0437 \u043F\u043B\u0430\u043D\u0430 \u2014 \u0432 \u0434\u043E\u043C. \u041F\u043E\u043A\u0430\u0437 \u043C\u043E\u0436\u043D\u043E \u043E\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u044C, \u0432\u044B\u0431\u0440\u0430\u0442\u044C \u044D\u0442\u0430\u043F \u0438\u043B\u0438 \u0441\u0440\u0430\u0437\u0443 \u043F\u0435\u0440\u0435\u0439\u0442\u0438 \u043A \u043E\u0441\u043C\u043E\u0442\u0440\u0443.",document.querySelectorAll("[data-mode]").forEach(e=>e.setAttribute("aria-pressed","false")),ar()}}function Ac(){nt&&(Xt("assembled"),document.querySelector("[data-mode=assembled]").focus({preventScroll:!0}))}function qu(i){if(!Fi)return;let e=Fi.apply(i);Sc=i,oe("#walk-style-name").textContent=e.title,window.__HOUSE_STATUS__.interiorStyle=i,oe("#style-description").textContent=e.description,document.querySelectorAll("[data-style]").forEach(t=>t.setAttribute("aria-pressed",String(t.dataset.style===i))),Mn=!0,Ze.shadowMap.needsUpdate=!0}function Tc(){As=requestAnimationFrame(Tc);let i=performance.now(),e=Math.max(0,(i-Io)/1e3);if(Io=i,_t==="construction"&&Rt.update(e,tn.matches),_t==="walk"&&yi.update(e),un)if(tn.matches){let n=un.direction<0;Bi(n?0:1),Qn(),n&&Xt("assembled")}else{let n=un.direction;un.progress=en.clamp(un.progress+n*e/7,0,1),Bi(un.progress),n===1&&un.progress>=1?Qn():n===-1&&un.progress<=0&&(Qn(),Xt("assembled"))}let t=!1;if(nt){let n=tn.matches?1:1-Math.exp(-6*e);for(let[s,r]of vi){let o=nt.getObjectByName(s);Math.abs(o.position.x-r.x)+Math.abs(o.position.y-r.y)>.002&&(t=!0,o.position.x=en.lerp(o.position.x,r.x,n),o.position.y=en.lerp(o.position.y,r.y,n))}vn&&t&&vn.setFromObject(nt.getObjectByName(Po)),t&&(Ze.shadowMap.needsUpdate=!0),window.__houseQA.camera={x:Tt.position.x,y:Tt.position.y,z:Tt.position.z},window.__houseQA.positions=Object.fromEntries([...vi].map(([s])=>{let r=nt.getObjectByName(s);return[s,{x:r.position.x,y:r.position.y}]}))}if(Tn&&Rn){let n=tn.matches?1:1-Math.exp(-4.5*e);Tt.position.lerp(Tn,n),bt.target.lerp(Rn,n),Mn=!0,Tt.position.distanceTo(Tn)+bt.target.distanceTo(Rn)<.015&&(Tt.position.copy(Tn),bt.target.copy(Rn),Tn=Rn=null)}_t!=="walk"&&_t!=="construction"&&bt.update(),(Mn||t)&&(Ze.render(At,Tt),Mn=!1)}function z_(){let i=new vo,e=new we,t=null,n=Ze.domElement;n.addEventListener("pointerdown",s=>{t=[s.clientX,s.clientY]}),n.addEventListener("pointerup",s=>{if(_t==="walk"||_t==="construction"||!t||Math.hypot(s.clientX-t[0],s.clientY-t[1])>6)return;t=null;let r=n.getBoundingClientRect();e.set((s.clientX-r.left)/r.width*2-1,-(s.clientY-r.top)/r.height*2+1),i.setFromCamera(e,Tt);let o=i.intersectObject(nt,!0).filter(l=>{let c=l.object;for(;c;){if(!c.visible)return!1;c=c.parent}return!0});if(!o.length)return;let a=o[0].object;for(;a&&!Wu[a.name];)a=a.parent;if(a){let l=a.name;Xt(bc.includes(l)?"wall":"exploded"),Ec(l)}})}function k_(){Rt&&(Rt.dispose(),Rt=null),oe("#build-hud").hidden=!0,oe("#construction-panel").hidden=!0,yi&&(yi.dispose(),yi=null),Fi&&(Fi.dispose(),Fi=null),oe("#walk-hud").hidden=!0,oe("#walk-panel").hidden=!0,oe("#interior-controls").hidden=!0,Qn(),cancelAnimationFrame(As),As=null,wc(),bt&&bt.dispose();let i=new Set,e=new Set,t=new Set;At&&(At.traverse(n=>{n.geometry&&i.add(n.geometry);for(let s of Array.isArray(n.material)?n.material:n.material?[n.material]:[]){e.add(s);for(let r of Object.values(s))r?.isTexture&&t.add(r)}}),At.environment&&t.add(At.environment)),i.forEach(n=>n.dispose()),e.forEach(n=>n.dispose()),t.forEach(n=>n.dispose()),Ze&&(Ze.dispose(),Ze.forceContextLoss(),Ze.domElement.remove()),Ze=null,nt=null,At=null,bt=null,or=!1,_t="assembled",Tn=Rn=null,vi.clear(),oe("#spread-controls").hidden=!0,Po=null,oe("#toolbar").hidden=!0,oe("#layer-controls").hidden=!0,oe("#detail").hidden=!0,oe("#open").hidden=!1,oe("#open").disabled=!1,oe("#state").textContent="3D \u0437\u0430\u043A\u0440\u044B\u0442\u043E. \u041C\u043E\u0436\u043D\u043E \u043E\u0442\u043A\u0440\u044B\u0442\u044C \u043C\u043E\u0434\u0435\u043B\u044C \u0441\u043D\u043E\u0432\u0430.",window.__HOUSE_STATUS__={loaded:!1,mode:"closed"},document.querySelectorAll("[data-mode]").forEach(n=>n.setAttribute("aria-pressed",String(n.dataset.mode==="assembled"))),oe("#open").focus()}oe("#play").addEventListener("click",B_);oe("#spread").addEventListener("input",i=>{Qn(),_t!=="exploded"&&Xt("exploded"),Bi(Number(i.target.value)/100)});oe("#assemble").addEventListener("click",()=>{if(_t!=="exploded"||tn.matches){Xt("assembled");return}Qn(),un={progress:window.__HOUSE_STATUS__.spread,direction:-1},window.__HOUSE_STATUS__.playing=!0,oe("#play").textContent="\u041F\u0430\u0443\u0437\u0430",oe("#play").setAttribute("aria-pressed","true"),oe("#state").textContent="\u0421\u043E\u0431\u0438\u0440\u0430\u0435\u043C \u0434\u043E\u043C \u0432 \u043E\u0431\u0440\u0430\u0442\u043D\u043E\u043C \u043F\u043E\u0440\u044F\u0434\u043A\u0435. \u041C\u043E\u0436\u043D\u043E \u043E\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u044C \u0438\u043B\u0438 \u0438\u0437\u043C\u0435\u043D\u0438\u0442\u044C \u043F\u043E\u043B\u043E\u0436\u0435\u043D\u0438\u0435 \u043F\u043E\u043B\u0437\u0443\u043D\u043A\u043E\u043C."});document.querySelectorAll("[data-style]").forEach(i=>i.addEventListener("click",()=>qu(i.dataset.style)));oe("#exit-walk").addEventListener("click",()=>Xt("inside"));document.addEventListener("keydown",i=>{i.key==="Escape"&&_t==="walk"&&Xt("inside")});oe("#build-replay").addEventListener("click",()=>Xu());oe("#build-skip").addEventListener("click",Ac);oe("#build-complete").addEventListener("click",Ac);oe("#build-play").addEventListener("click",()=>{Rt?.active&&!tn.matches&&Rt.toggle()});oe("#build-progress").addEventListener("input",i=>{Rt?.active&&Rt.seek(Number(i.target.value)/100)});document.querySelectorAll("[data-build-step]").forEach(i=>i.addEventListener("click",()=>{Rt?.active&&Rt.seek([.13,.27,.49,.65,.81,.97,1][Number(i.dataset.buildStep)])}));document.addEventListener("keydown",i=>{i.key==="Escape"&&_t==="construction"&&(i.preventDefault(),Ac())});tn.addEventListener("change",()=>{tn.matches&&Rt?.active&&Rt.pause(),oe("#build-play").disabled=tn.matches});oe("#close").addEventListener("click",k_);oe("#open").addEventListener("click",Gu);document.querySelectorAll("[data-mode]").forEach(i=>i.addEventListener("click",()=>Xt(i.dataset.mode)));document.querySelectorAll("[data-layer]").forEach(i=>i.addEventListener("click",()=>{let e=i.dataset.layer;bc.includes(e)?_t!=="wall"&&_t!=="exploded"&&Xt("wall"):_t!=="exploded"&&Xt("exploded"),Ec(e)}));window.addEventListener("resize",ar);document.addEventListener("visibilitychange",()=>{document.hidden?(Rt?.active&&Rt.pause(),Qn(),cancelAnimationFrame(As),As=null):Ze&&!As&&(Io=performance.now(),Tc())});innerWidth>900&&Gu();})();
/*! Bundled license information:

three/build/three.module.js:
  (**
   * @license
   * Copyright 2010-2024 Three.js Authors
   * SPDX-License-Identifier: MIT
   *)
*/

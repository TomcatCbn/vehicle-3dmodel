import * as THREE from 'three';
import { WHEEL_RADIUS } from '../drive-state.js';

const WIDTH=12,WHEELBASE=2.836,HALF_TRACK=.817,SAMPLES=2000;
const point=(x,z)=>new THREE.Vector3(x,0,z);
const corners=[[-8,-52],[-30,-52],[-42,-44],[-47,-28],[-47,-4],[-40,8],[-45,19],[-39,32],[-27,39],[-8,41],[16,41],[34,35],[42,23],[42,7],[36,-4],[26,-8],[23,-19],[31,-28],[38,-35],[37,-44],[27,-52],[9,-52]];
const course=new THREE.CatmullRomCurve3(corners.map(([x,z])=>point(x*1.6,z*1.6)),true,'centripetal',.5);
course.arcLengthDivisions=2400;
const length=course.getLength();
function frameAt(u){
  const t=course.getUtoTmapping(u),h=.00001,wrap=t=>(t+1)%1;
  const p=course.getPoint(t),before=course.getPoint(wrap(t-h)),after=course.getPoint(wrap(t+h));
  const d=after.clone().sub(before).multiplyScalar(1/(2*h));
  const dd=after.clone().add(before).addScaledVector(p,-2).multiplyScalar(1/(h*h));
  const curvature=(d.z*dd.x-d.x*dd.z)/Math.pow(d.lengthSq(),1.5);
  return {tangent:d.normalize(),curvature};
}
const curvatureAt=u=>frameAt(u).curvature;

const wheelTable=Array.from({length:SAMPLES+1},()=>({fl:0,fr:0,rl:0,rr:0}));
for(let i=1;i<=SAMPLES;i++){
  const k=curvatureAt((i-.5)/SAMPLES),ds=length/SAMPLES,prev=wheelTable[i-1],next=wheelTable[i];
  for(const [front,id,z] of [[true,'fl',-HALF_TRACK],[true,'fr',HALF_TRACK],[false,'rl',-HALF_TRACK],[false,'rr',HALF_TRACK]]){
    const lateral=1-k*z;next[id]=prev[id]+ds*(front?Math.hypot(lateral,WHEELBASE*k):lateral);
  }
}
const lapWheels=wheelTable.at(-1);

function accumulate(indices){const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(indices.positions,3));g.setIndex(indices.faces);g.computeVertexNormals();return g;}
function makeRibbon(centers,inner,outer,y,material){
  const positions=[],faces=[];
  for(let i=0;i<=SAMPLES;i++){
    const p=centers[i],t=course.getTangentAt(i/SAMPLES),side=point(t.z,-t.x).normalize();
    positions.push(p.x+side.x*inner,y,p.z+side.z*inner,p.x+side.x*outer,y,p.z+side.z*outer);
    if(i<SAMPLES){const n=i*2;faces.push(n,n+2,n+1,n+1,n+2,n+3);}
  }
  const mesh=new THREE.Mesh(accumulate({positions,faces}),material);mesh.receiveShadow=true;return mesh;
}
function makeLine(centers,offset,y,material){return makeRibbon(centers,offset-.04,offset+.04,y,material);}
function wheelDistanceAt(distance){
  const lap=Math.floor(distance/length),local=((distance%length)+length)%length,u=local/length*SAMPLES,index=Math.min(SAMPLES-1,Math.floor(u)),f=u-index;
  return Object.fromEntries(['fl','fr','rl','rr'].map(id=>[id,(lap*lapWheels[id]+THREE.MathUtils.lerp(wheelTable[index][id],wheelTable[index+1][id],f))/WHEEL_RADIUS]));
}

export function sampleRaceTrack(distance,direction=1){
  const lap=Math.floor(distance/length),local=((distance%length)+length)%length,u=local/length;
  const rearAxle=course.getPointAt(u),frame=frameAt(u),tangent=frame.tangent,turn=frame.curvature;
  // The path belongs to the rear axle. Its no-slip direction sets the body
  // heading; reverse retraces it with negative wheel travel, without flipping.
  const position=rearAxle.clone().addScaledVector(tangent,WHEELBASE/2),yaw=Math.atan2(tangent.z,-tangent.x);
  return {position,yaw,curvature:turn,steeringByWheel:{
    fl:Math.atan2(WHEELBASE*turn,1+HALF_TRACK*turn),fr:Math.atan2(WHEELBASE*turn,1-HALF_TRACK*turn),
  },wheelAngles:wheelDistanceAt(distance),lap:lap+1,length};
}

export function createRaceTrack(scene){
  const root=new THREE.Group();root.name='AXIS Raceway';root.visible=false;scene.add(root);
  const centers=Array.from({length:SAMPLES+1},(_,i)=>course.getPointAt(i/SAMPLES));
  const grass=new THREE.Mesh(new THREE.PlaneGeometry(320,300),new THREE.MeshStandardMaterial({color:'#38433b',roughness:1}));grass.rotation.x=-Math.PI/2;grass.position.y=-.035;grass.receiveShadow=true;root.add(grass);
  const asphalt=new THREE.MeshStandardMaterial({color:'#292d32',roughness:.92,metalness:.02});
  const gravel=new THREE.MeshStandardMaterial({color:'#62635d',roughness:1});
  root.add(makeRibbon(centers,-WIDTH/2,WIDTH/2,-.005,asphalt),makeRibbon(centers,-10.5,-WIDTH/2,-.012,gravel),makeRibbon(centers,WIDTH/2,10.5,-.012,gravel));
  const white=new THREE.MeshStandardMaterial({color:'#e5e3db',roughness:.7});
  root.add(makeLine(centers,-5.05,.012,white),makeLine(centers,5.05,.012,white));
  const red=new THREE.MeshStandardMaterial({color:'#d72d35',roughness:.68});
  const curbGeometry=new THREE.BoxGeometry(2.1,.10,.72),redCurbs=new THREE.InstancedMesh(curbGeometry,red,180),whiteCurbs=new THREE.InstancedMesh(curbGeometry,white,180),dummy=new THREE.Object3D();
  let redIndex=0,whiteIndex=0;
  for(let i=0;i<180;i++)for(const sideOfTrack of [-1,1]){
    const u=(i+.5)/180,p=course.getPointAt(u),t=course.getTangentAt(u),side=point(t.z,-t.x).normalize();
    dummy.position.copy(p).addScaledVector(side,sideOfTrack*6.15);dummy.position.y=.045;dummy.rotation.y=Math.atan2(t.z,-t.x);dummy.updateMatrix();
    const target=i%2?whiteCurbs:redCurbs,index=i%2?whiteIndex++:redIndex++;target.setMatrixAt(index,dummy.matrix);
  }
  redCurbs.count=redIndex;whiteCurbs.count=whiteIndex;root.add(redCurbs,whiteCurbs);
  // Checkerboard start line on the pit straight.
  const checkerGeometry=new THREE.BoxGeometry(.48,.024,1),black=new THREE.MeshStandardMaterial({color:'#171a1d'}),startWhite=new THREE.MeshStandardMaterial({color:'#f2f1eb'});
  const blacks=new THREE.InstancedMesh(checkerGeometry,black,24),whites=new THREE.InstancedMesh(checkerGeometry,startWhite,24);let bi=0,wi=0;
  const start=centers[0],startTangent=course.getTangentAt(0),startYaw=Math.atan2(startTangent.z,-startTangent.x);
  for(let row=0;row<2;row++)for(let col=0;col<12;col++){
    dummy.position.copy(start).add(point(Math.sin(startYaw),-Math.cos(startYaw)).multiplyScalar((col-5.5))).add(point(-Math.cos(startYaw),Math.sin(startYaw)).multiplyScalar((row-.5)*.48));dummy.position.y=.02;dummy.rotation.y=startYaw;dummy.updateMatrix();
    const target=(row+col)%2?whites:blacks,index=(row+col)%2?wi++:bi++;target.setMatrixAt(index,dummy.matrix);
  }
  blacks.count=bi;whites.count=wi;root.add(blacks,whites);
  // Pit garages along the start straight and tiered spectator seating beyond the back straight.
  const concrete=new THREE.MeshStandardMaterial({color:'#737878',roughness:.83}),windowMaterial=new THREE.MeshStandardMaterial({color:'#26333a',roughness:.22,metalness:.25}),seatMaterial=new THREE.MeshStandardMaterial({color:'#a1333c',roughness:.68});
  const garage=new THREE.Mesh(new THREE.BoxGeometry(34,4.2,5.5),concrete);garage.position.set(6.4,2.1,-100.8);garage.castShadow=true;root.add(garage);
  for(let x=-11;x<=19;x+=5){const pane=new THREE.Mesh(new THREE.BoxGeometry(3.5,1.6,.05),windowMaterial);pane.position.set(x*1.6,2.7,-98.02);root.add(pane);}
  const signCanvas=document.createElement('canvas');signCanvas.width=512;signCanvas.height=96;const context=signCanvas.getContext('2d');context.fillStyle='#101519';context.fillRect(0,0,512,96);context.fillStyle='#dbe8e1';context.font='600 42px sans-serif';context.textAlign='center';context.fillText('AXIS  RACEWAY',256,63);
  const sign=new THREE.Mesh(new THREE.PlaneGeometry(14,2.1),new THREE.MeshBasicMaterial({map:new THREE.CanvasTexture(signCanvas),toneMapped:false}));sign.position.set(8,4.15,-98.0);root.add(sign);
  for(let x=-12;x<=22;x+=4){const tier=new THREE.Mesh(new THREE.BoxGeometry(3.7,.55,3.3),concrete);tier.position.set(x*1.6,2.2,78.4);tier.castShadow=true;root.add(tier);const chair=new THREE.Mesh(new THREE.BoxGeometry(.78,.42,.52),seatMaterial);chair.position.set(x*1.6,2.58,77.25);root.add(chair);}
  const floodlight=new THREE.MeshStandardMaterial({color:'#d9d3bd',emissive:'#d9d3bd',emissiveIntensity:.25});
  for(const i of[125,375,625,875]){const p=centers[i],t=course.getTangentAt(i/SAMPLES),side=point(t.z,-t.x).normalize();for(const sign of[-1,1]){const pole=new THREE.Mesh(new THREE.BoxGeometry(.15,6,.15),concrete);pole.position.copy(p).addScaledVector(side,sign*12);pole.position.y=3;root.add(pole);const lamp=new THREE.Object3D();lamp.position.copy(pole.position);lamp.position.y=6;const lens=new THREE.Mesh(new THREE.BoxGeometry(.55,.12,.3),floodlight);lens.position.copy(lamp.position);root.add(lens);}}
  return {root,length,update(){},sample:sampleRaceTrack};
}

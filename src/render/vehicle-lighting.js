import * as THREE from 'three';
import { deriveLighting } from '../lighting-state.js';

const styles={
  lowBeam:{color:'#dff4ff',gain:3,min:4},highBeam:{color:'#eaf7ff',gain:3,min:15},
  tailLight:{color:'#ff1024',gain:4,min:4},brakeLight:{color:'#ff1020',gain:2,min:10},
  reverseLight:{color:'#e8f5ff',gain:3,min:9},ambientLight:{gain:3,min:5},
  chargeIndicator:{color:'#36ff95',gain:3,min:7},
};

export function createVehicleLighting(root) {
  const lamps=[],spotlights=[],ambientLights=[],rearLights=[],reverseLights=[],chargeLights=[];
  const tailGroups=new Map();
  root.updateMatrixWorld(true);
  const ownerOf=node=>{for(let p=node.parent;p&&p!==root;p=p.parent)if(p.userData.part)return p;return node;};
  const positionOn=(owner,point)=>owner.worldToLocal(point.clone());
  function spill(owner,center,color,intensity,distance,offset){
    const light=new THREE.PointLight(color,0,distance,2);
    light.position.copy(positionOn(owner,center.clone().add(offset)));light.visible=false;owner.add(light);
    light.userData.onIntensity=intensity;return light;
  }
  // Collect before adding children, so a traversal never visits newly added lamps.
  const nodes=[];root.traverse(node=>nodes.push(node));
  for(const node of nodes){
    if(node.isMesh&&node.userData.lightRole){
      const role=node.userData.lightRole,material=node.material,style=styles[role];
      lamps.push({role,material,emissiveIntensity:material.emissiveIntensity,color:material.color.clone()});
      if(style?.color)material.emissive.set(style.color);
      const owner=ownerOf(node),center=new THREE.Box3().setFromObject(node).getCenter(new THREE.Vector3());
      if(role==='tailLight'){
        const box=tailGroups.get(owner)??new THREE.Box3();box.union(new THREE.Box3().setFromObject(node));tailGroups.set(owner,box);
      }
      if(role==='reverseLight'){
        const light=new THREE.SpotLight('#e8f5ff',0,8,.65,.8,1.8),target=new THREE.Object3D();
        light.position.copy(positionOn(owner,center.clone().add(new THREE.Vector3(.08,0,0))));
        target.position.copy(positionOn(owner,center.clone().add(new THREE.Vector3(4,-1,0))));
        light.target=target;light.visible=false;owner.add(light,target);reverseLights.push(light);
      }
      if(role==='chargeIndicator')chargeLights.push(spill(owner,center,'#36ff95',2,.8,new THREE.Vector3(0,.03,-.04)));
    }
    if(node.userData.lightAnchor==='headlight'){
      const light=new THREE.SpotLight('#dff4ff',260,32,.46,.65,1.6),target=new THREE.Object3D();
      target.position.set(-14,-.65,0);light.visible=false;light.castShadow=false;light.target=target;
      node.add(light,target);spotlights.push(light);
    }
    if(node.userData.lightAnchor==='ambient'){
      const light=new THREE.PointLight('#ffffff',0,2.8,2);light.visible=false;node.add(light);ambientLights.push(light);
    }
  }
  for(const [owner,box] of tailGroups){
    const center=box.getCenter(new THREE.Vector3());
    rearLights.push(spill(owner,center,'#ff1830',.7,2.8,new THREE.Vector3(.35,-.03,Math.sign(center.z)*.2)));
  }

  function update(state,motion={}) {
    const derived=deriveLighting(state.lighting,motion),ambientEnabled=derived.ambientColor!==null;
    for(const lamp of lamps){
      const enabled=lamp.role==='chargeIndicator'?Boolean(state.charging):lamp.role==='ambientLight'?ambientEnabled:Boolean(derived[lamp.role]);
      const style=styles[lamp.role]??{gain:1,min:0};
      if(lamp.role==='ambientLight'&&ambientEnabled)lamp.material.emissive.set(derived.ambientColor);
      lamp.material.emissiveIntensity=enabled?Math.max(style.min,lamp.emissiveIntensity*style.gain):0;
      lamp.material.color.copy(lamp.color).multiplyScalar(enabled?1:.25);
    }
    for(const light of spotlights){
      light.visible=derived.lowBeam;light.intensity=derived.highBeam?750:260;
      light.distance=derived.highBeam?55:32;light.angle=derived.highBeam?.34:.46;
    }
    for(const light of ambientLights){
      light.visible=ambientEnabled;light.intensity=ambientEnabled?18:0;
      if(ambientEnabled)light.color.set(derived.ambientColor);
    }
    for(const light of rearLights){
      light.visible=derived.tailLight||derived.brakeLight;light.intensity=derived.brakeLight?3.5:derived.tailLight?.7:0;
    }
    for(const light of reverseLights){light.visible=derived.reverseLight;light.intensity=derived.reverseLight?32:0;}
    for(const light of chargeLights){light.visible=Boolean(state.charging);light.intensity=state.charging?2:0;}
  }
  return {lamps,spotlights,ambientLights,rearLights,reverseLights,chargeLights,update};
}

import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

const dark=new THREE.MeshBasicMaterial({color:0});
const glass=new THREE.MeshBasicMaterial({transparent:true,opacity:0,depthWrite:false});

/** Preserve opaque occluders, but let glow pass through the authored glazing. */
export function maskForLampBloom(scene) {
  const saved=[],hidden=[],background=scene.background,environment=scene.environment,fog=scene.fog;
  scene.background=new THREE.Color(0);scene.environment=null;scene.fog=null;
  scene.traverse(node=>{
    if(!node.isMesh)return;
    if(node.isReflector){hidden.push([node,node.visible]);node.visible=false;return;}
    saved.push([node,node.material]);
    const mask=material=>node.userData.lightRole&&material.emissiveIntensity>0&&material.opacity>.1
      ?material:material.transmission>0?glass:dark;
    node.material=Array.isArray(node.material)?node.material.map(mask):mask(node.material);
  });
  return ()=>{
    for(const [node,material] of saved)node.material=material;
    for(const [node,visible] of hidden)node.visible=visible;
    scene.background=background;scene.environment=environment;scene.fog=fog;
  };
}

export function createPresentation(renderer,scene,camera) {
  const glow=new EffectComposer(renderer);glow.renderToScreen=false;
  glow.addPass(new RenderPass(scene,camera));
  const bloom=new UnrealBloomPass(new THREE.Vector2(1,1),.65,.22,.3);glow.addPass(bloom);
  const target=new THREE.WebGLRenderTarget(1,1,{type:THREE.HalfFloatType,samples:4});
  const final=new EffectComposer(renderer,target);final.addPass(new RenderPass(scene,camera));
  const composite=new ShaderPass({
    uniforms:{tDiffuse:{value:null},glowTexture:{value:null}},
    vertexShader:'varying vec2 vUv; void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
    fragmentShader:'uniform sampler2D tDiffuse; uniform sampler2D glowTexture; varying vec2 vUv; void main(){vec4 base=texture2D(tDiffuse,vUv);gl_FragColor=vec4(base.rgb+texture2D(glowTexture,vUv).rgb*.65,base.a);}',
  });
  final.addPass(composite);final.addPass(new OutputPass());
  return {
    resize(width,height){
      final.setPixelRatio(renderer.getPixelRatio());final.setSize(width,height);
      glow.setPixelRatio(Math.min(renderer.getPixelRatio(),1));glow.setSize(width*.7,height*.7);
    },
    render(){
      const restore=maskForLampBloom(scene),shadowAuto=renderer.shadowMap.autoUpdate;
      renderer.shadowMap.autoUpdate=false;
      try{glow.render();}finally{restore();renderer.shadowMap.autoUpdate=shadowAuto;}
      // This target contains only the blurred bloom, without a second lamp core.
      composite.uniforms.glowTexture.value=bloom.renderTargetsHorizontal[0].texture;
      final.render();
    },
  };
}

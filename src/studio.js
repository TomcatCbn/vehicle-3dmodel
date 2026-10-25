import * as THREE from 'three';
import { RGBELoader } from 'three/addons/loaders/RGBELoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { Reflector } from 'three/addons/objects/Reflector.js';

export async function createStudio(renderer, scene) {
  const pmrem = new THREE.PMREMGenerator(renderer);
  try {
    const hdr = await new RGBELoader().loadAsync('/environments/studio-small-09.hdr');
    scene.environment = pmrem.fromEquirectangular(hdr).texture;
    hdr.dispose();
  } catch {
    const room = new RoomEnvironment();
    scene.environment = pmrem.fromScene(room,.06).texture;
    room.dispose();
  }
  pmrem.dispose();
  scene.environmentIntensity = .8;
  scene.environmentRotation.y = 1.7;
  const sky = document.createElement('canvas');sky.width=16;sky.height=1024;
  const context=sky.getContext('2d');
  const gradient=context.createLinearGradient(0,0,0,1024);
  // Linear texture data keeps the horizon under the same tone mapping as floor fog.
  for(const [stop,color] of [[0,'#485a72'],[.3,'#b5aaa7'],[.6,'#b5aaa7'],[.8,'#75696b'],[1,'#242b34']]){
    const linear=new THREE.Color(color);
    gradient.addColorStop(stop,`rgb(${Math.round(linear.r*255)},${Math.round(linear.g*255)},${Math.round(linear.b*255)})`);
  }
  context.fillStyle=gradient;context.fillRect(0,0,16,1024);
  const backdrop=new THREE.CanvasTexture(sky);backdrop.colorSpace=THREE.LinearSRGBColorSpace;
  scene.background=backdrop;
  scene.fog=new THREE.Fog('#b5aaa7',18,60);
  scene.add(new THREE.HemisphereLight('#b9cce2','#5f4a3d',.35));
  const key=new THREE.DirectionalLight('#fff0da',2.8);key.position.set(-4,6,3);key.castShadow=true;
  key.shadow.mapSize.set(2048,2048);Object.assign(key.shadow.camera,{left:-5,right:5,top:5,bottom:-5,near:.1,far:20});
  key.shadow.bias=-.00015;key.shadow.normalBias=.012;key.shadow.radius=4;key.shadow.blurSamples=12;scene.add(key);
  const fill=new THREE.DirectionalLight('#bacfe5',.65);fill.position.set(2,3,-5);scene.add(fill);
  const rim=new THREE.DirectionalLight('#ffd1a5',1.6);rim.position.set(5,3,-2);scene.add(rim);
  const geometry=new THREE.PlaneGeometry(150,150);
  const ground=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:'#777078',roughness:.24,metalness:.2}));
  ground.rotation.x=-Math.PI/2;ground.position.y=-.003;ground.receiveShadow=true;scene.add(ground);
  const reflectionShader={
    name:'Satin floor reflection',
    uniforms:{...THREE.UniformsUtils.clone(Reflector.ReflectorShader.uniforms),blur:{value:1/650},strength:{value:.24}},
    vertexShader:Reflector.ReflectorShader.vertexShader,
    fragmentShader:`
      uniform vec3 color;uniform sampler2D tDiffuse;uniform float blur;uniform float strength;varying vec4 vUv;
      #include <logdepthbuf_pars_fragment>
      void main(){
        #include <logdepthbuf_fragment>
        vec2 uv=vUv.xy/vUv.w;
        vec3 reflected=texture2D(tDiffuse,uv).rgb*.24;
        reflected+=texture2D(tDiffuse,uv+vec2(blur,0.)).rgb*.12;
        reflected+=texture2D(tDiffuse,uv-vec2(blur,0.)).rgb*.12;
        reflected+=texture2D(tDiffuse,uv+vec2(0.,blur)).rgb*.12;
        reflected+=texture2D(tDiffuse,uv-vec2(0.,blur)).rgb*.12;
        reflected+=texture2D(tDiffuse,uv+vec2(blur,blur)).rgb*.07;
        reflected+=texture2D(tDiffuse,uv-vec2(blur,blur)).rgb*.07;
        reflected+=texture2D(tDiffuse,uv+vec2(blur,-blur)).rgb*.07;
        reflected+=texture2D(tDiffuse,uv+vec2(-blur,blur)).rgb*.07;
        gl_FragColor=vec4(reflected,strength*(1.-smoothstep(12.,35.,vUv.w)));
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`
  };
  const mirror=new Reflector(new THREE.PlaneGeometry(150,150),{textureWidth:1024,textureHeight:1024,clipBias:.003,multisample:0,shader:reflectionShader});
  mirror.rotation.x=-Math.PI/2;mirror.position.y=-.001;mirror.material.transparent=true;mirror.material.depthWrite=false;scene.add(mirror);
  const contactCanvas=document.createElement('canvas');contactCanvas.width=512;contactCanvas.height=256;
  const ctx=contactCanvas.getContext('2d');
  const shadowGradient=ctx.createRadialGradient(256,128,15,256,128,230);
  shadowGradient.addColorStop(0,'rgba(0,0,0,.7)');shadowGradient.addColorStop(.6,'rgba(0,0,0,.38)');shadowGradient.addColorStop(1,'rgba(0,0,0,0)');
  ctx.fillStyle=shadowGradient;ctx.fillRect(0,0,512,256);
  const contact=new THREE.Mesh(new THREE.PlaneGeometry(5.4,2.9),new THREE.MeshBasicMaterial({map:new THREE.CanvasTexture(contactCanvas),transparent:true,depthWrite:false,opacity:.65}));
  contact.rotation.x=-Math.PI/2;contact.position.y=.001;scene.add(contact);
  const wheelShadows=[];
  for(const x of [-1.418,1.418])for(const z of [-.817,.817]){
    const wheelShadow=new THREE.Mesh(new THREE.PlaneGeometry(.68,.48),contact.material.clone());
    wheelShadow.rotation.x=-Math.PI/2;wheelShadow.position.set(x,.002,z);scene.add(wheelShadow);wheelShadows.push(wheelShadow);
  }
  const stageFog=scene.fog,isolatedBackdrop=new THREE.Color('#151d22'),keyPosition=key.position.clone();
  scene.add(key.target);
  return {setDriving(value){
    ground.visible=!value;mirror.visible=!value;
    stageFog.near=value?35:18;stageFog.far=value?120:60;
  },setIsolated(value,box){
    for(const object of [ground,mirror,contact,...wheelShadows])object.visible=!value;
    scene.background=value?isolatedBackdrop:backdrop;scene.fog=value?null:stageFog;
    const center=value?box.getCenter(new THREE.Vector3()):new THREE.Vector3();
    const radius=value?box.getSize(new THREE.Vector3()).length()*.65:5;
    key.position.copy(keyPosition).add(center);key.target.position.copy(center);key.target.updateMatrixWorld(true);
    Object.assign(key.shadow.camera,{left:-radius,right:radius,top:radius,bottom:-radius});key.shadow.camera.updateProjectionMatrix();
    key.shadow.normalBias=value?.0004:.012;key.shadow.needsUpdate=true;
  }, update(progress){
    const floorY=THREE.MathUtils.lerp(-.003,-1.22,progress);
    ground.position.y=floorY;mirror.position.y=floorY+.002;contact.position.y=floorY+.004;
    contact.material.opacity=.65*(1-progress);mirror.material.uniforms.strength.value=.24*(1-progress*.65);
    for(const wheelShadow of wheelShadows){wheelShadow.position.y=floorY+.005;wheelShadow.material.opacity=.8*(1-progress);}
    scene.environmentIntensity=THREE.MathUtils.lerp(.8,.65,progress);
  }};
}

/** Finish the presentation with actual signal commands. Sleep blocks all other
 * commands, so switch lights off and lock before entering sleep. */
export async function shutdownAfterEntrance(getState,sendCommand) {
  const current=()=>getState();
  if((current().powerState??current().power_state)==='sleep')return true;
  const steps=[
    [s=>s.lighting?.headlights!=='off',{type:'set_headlight',mode:'off'}],
    [s=>Boolean(s.lighting?.tailLights??s.lighting?.tail_lights),{type:'toggle_tail_light'}],
    [s=>s.lighting?.ambient&&s.lighting.ambient!=='off',{type:'set_ambient',color:'off'}],
    [s=>!s.locked,{type:'toggle_lock'}],
    [s=>(s.powerState??s.power_state)!=='sleep',{type:'set_power',state:'sleep'}],
  ];
  for(const [needed,command] of steps)if(needed(current())&&!await sendCommand(command))return false;
  return true;
}

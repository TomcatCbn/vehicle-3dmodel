export const AMBIENT_COLORS = Object.freeze({ off: null, warm: '#FFD9A0', ice: '#8FD8FF', purple: '#B49AFF' });

export function createLightingState() {
  return { headlights: 'low', tailLights: true, ambient: 'off' };
}

export function deriveLighting(lighting, motion = {}) {
  const headlights = ['off', 'low', 'high'].includes(lighting.headlights) ? lighting.headlights : 'off';
  return {
    lowBeam: headlights === 'low' || headlights === 'high',
    highBeam: headlights === 'high',
    tailLight: Boolean(lighting.tailLights),
    brakeLight: Boolean(motion.braking),
    reverseLight: Boolean(motion.reversing),
    ambientColor: Object.hasOwn(AMBIENT_COLORS, lighting.ambient) ? AMBIENT_COLORS[lighting.ambient] : null,
  };
}

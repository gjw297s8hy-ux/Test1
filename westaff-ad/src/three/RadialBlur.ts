import {Effect} from 'postprocessing';
import {Uniform} from 'three';

/** Flou radial (zoom blur) + surexposition, piloté par l'intensité de transition. */
const frag = /* glsl */ `
uniform float strength;
uniform float exposure;
void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) {
  vec2 dir = uv - vec2(0.5, 0.46);
  vec4 acc = vec4(0.0); float tot = 0.0;
  for (int i = 0; i < 20; i++) {
    float k = float(i) / 19.0; float w = 1.0 - k * 0.6;
    acc += texture2D(inputBuffer, uv - dir * strength * k) * w; tot += w;
  }
  vec4 c = strength > 0.0001 ? acc / tot : inputColor;
  outputColor = vec4(c.rgb * exposure, c.a);
}`;
export class RadialBlurEffect extends Effect {
  constructor() {
    super('RadialBlurEffect', frag, {uniforms: new Map<string, Uniform>([['strength', new Uniform(0)], ['exposure', new Uniform(1)]])});
  }
  set(strength: number, exposure: number) {
    (this.uniforms.get('strength') as Uniform).value = strength;
    (this.uniforms.get('exposure') as Uniform).value = exposure;
  }
}

import {Effect} from 'postprocessing';
import {Uniform} from 'three';
/** Objectif grand-angle (distorsion en barillet), aberration chromatique sur les bords, « punch » de zoom. */
const frag = /* glsl */ `
uniform float k; uniform float ca;
void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) {
  vec2 c = uv - 0.5; c.x *= 0.5625;
  float r2 = dot(c, c);
  vec2 d = c * (1.0 - k * 0.6 + k * r2 * 3.0); d.x /= 0.5625;
  vec2 u = d + 0.5;
  vec2 off = (u - 0.5) * ca * r2 * 4.0;
  vec3 col = vec3(texture2D(inputBuffer, u + off).r, texture2D(inputBuffer, u).g, texture2D(inputBuffer, u - off).b);
  float edge = step(0.0, u.x) * step(u.x, 1.0) * step(0.0, u.y) * step(u.y, 1.0);
  outputColor = vec4(col * edge, 1.0);
}`;
export class LensFXEffect extends Effect {
  constructor() { super('LensFXEffect', frag, {uniforms: new Map<string, Uniform>([['k', new Uniform(0.12)], ['ca', new Uniform(0.02)]])}); }
  set(k: number, ca: number) { (this.uniforms.get('k') as Uniform).value = k; (this.uniforms.get('ca') as Uniform).value = ca; }
}

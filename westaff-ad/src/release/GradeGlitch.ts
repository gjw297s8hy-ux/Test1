import {Effect} from 'postprocessing';
import {Uniform} from 'three';

/**
 * Étalonnage « drill » (froid, blancs brûlés, noirs bleutés) + glitch (tranches décalées, RVB séparé, blocs étirés).
 * Inspiré de la référence fournie ; intensité du glitch pilotée frame par frame.
 */
const frag = /* glsl */ `
uniform float glitch; uniform float seed;
float h(float n){ return fract(sin(n*91.3458)*47453.5453); }
void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) {
  vec2 u = uv;
  if (glitch > 0.001) {
    float band = floor(uv.y * 34.0);
    float r = h(band + seed * 13.0);
    if (r < glitch * 0.85) u.x += (h(band * 3.1 + seed) - 0.5) * 0.22 * glitch;
    float blk = h(floor(uv.x * 9.0) + seed * 7.0);
    if (blk < glitch * 0.35) u.y = floor(u.y * 6.0 + h(seed)) / 6.0 + (uv.y - floor(uv.y * 6.0) / 6.0) * 0.15; // étirement vertical
  }
  float sp = 0.004 + glitch * 0.025;
  vec3 c = vec3(texture2D(inputBuffer, u + vec2(sp, 0.0)).r, texture2D(inputBuffer, u).g, texture2D(inputBuffer, u - vec2(sp, 0.0)).b);
  float l = dot(c, vec3(0.299, 0.587, 0.114));
  vec3 g = mix(c, vec3(l), 0.32);                       // désaturation partielle (le rouge reste présent)
  g += vec3(-0.015, 0.02, 0.05) * pow(1.0 - l, 2.0);     // ombres bleu-acier
  g += vec3(0.9, 0.95, 1.0) * max(0.0, l - 0.72) * 0.55; // blancs brûlés
  g = (g - 0.5) * 1.12 + 0.5;
  outputColor = vec4(clamp(g, 0.0, 1.0), inputColor.a);
}`;
export class GradeGlitchEffect extends Effect {
  constructor() { super('GradeGlitchEffect', frag, {uniforms: new Map<string, Uniform>([['glitch', new Uniform(0)], ['seed', new Uniform(0)]])}); }
  set(glitch: number, seed: number) { (this.uniforms.get('glitch') as Uniform).value = glitch; (this.uniforms.get('seed') as Uniform).value = seed; }
}

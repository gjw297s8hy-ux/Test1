import {Effect} from 'postprocessing';
import {Uniform} from 'three';

/**
 * Étalonnage « drill » (froid, blancs brûlés, noirs bleutés) + glitch (tranches décalées, RVB séparé, blocs étirés).
 * Inspiré de la référence fournie ; intensité du glitch pilotée frame par frame.
 */
const frag = /* glsl */ `
uniform float glitch; uniform float seed; uniform float perceptual; uniform float amount;
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
  vec3 lin = c; if (perceptual > 0.5) c = pow(max(c, 0.0), vec3(1.0 / 2.2));
  float l = dot(c, vec3(0.299, 0.587, 0.114));
  // DA rouge & noir : on garde les rouges, tout le reste passe en noir & blanc contrasté
  float redness = smoothstep(0.04, 0.22, c.r - max(c.g, c.b));
  vec3 g = mix(vec3(l), c * vec3(1.15, 0.85, 0.85), redness);
  g = pow(max(g, 0.0), vec3(1.04));                        // noirs denses
  g += vec3(1.0) * max(0.0, l - 0.78) * 0.45;              // blancs brûlés
  g = (g - 0.35) * 1.1 + 0.35;
  g = mix(c, g, amount);
  g = clamp(g, 0.0, 1.0); if (perceptual > 0.5) g = pow(g, vec3(2.2));
  outputColor = vec4(g, inputColor.a);
}`;
export class GradeGlitchEffect extends Effect {
  constructor() { super('GradeGlitchEffect', frag, {uniforms: new Map<string, Uniform>([['glitch', new Uniform(0)], ['seed', new Uniform(0)], ['perceptual', new Uniform(0)], ['amount', new Uniform(1)]])}); }
  mode(perceptual: boolean, amount = 1) { (this.uniforms.get('perceptual') as Uniform).value = perceptual ? 1 : 0; (this.uniforms.get('amount') as Uniform).value = amount; }
  set(glitch: number, seed: number) { (this.uniforms.get('glitch') as Uniform).value = glitch; (this.uniforms.get('seed') as Uniform).value = seed; }
}

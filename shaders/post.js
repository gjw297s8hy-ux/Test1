// Post-processing chain (all HDR, half-float):
// scene -> [DOF] -> transition comp -> motion-blur accumulation -> bloom (mip chain) -> filmic grade -> 8-bit
import * as THREE from 'three';
import { noiseGLSL } from './noise.glsl.js';

const VS = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;

function fsTri() {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(new Float32Array([-1, -1, 0, 3, -1, 0, -1, 3, 0]), 3));
  g.setAttribute('uv', new THREE.BufferAttribute(new Float32Array([0, 0, 2, 0, 0, 2]), 2));
  return g;
}

export class Post {
  constructor(renderer, W, H, q, fx) {
    this.r = renderer; this.W = W; this.H = H; this.q = q; this.fx = fx;
    const rtOpts = { type: THREE.HalfFloatType, format: THREE.RGBAFormat, colorSpace: THREE.LinearSRGBColorSpace, depthBuffer: false };
    this.sceneRT = [0, 1].map(() => {
      const rt = new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, samples: q.msaa || 0 });
      rt.depthTexture = new THREE.DepthTexture(W, H, THREE.FloatType);
      return rt;
    });
    this.dofRT = [0, 1].map(() => new THREE.WebGLRenderTarget(W, H, { ...rtOpts, depthBuffer: true, samples: q.msaa || 0 }));
    this.compRT = new THREE.WebGLRenderTarget(W, H, rtOpts);
    this.accRT = new THREE.WebGLRenderTarget(W, H, { ...rtOpts, type: THREE.FloatType });
    this.mips = [];
    let w = W, h = H;
    for (let i = 0; i < 7; i++) { w = Math.max(1, w >> 1); h = Math.max(1, h >> 1); this.mips.push(new THREE.WebGLRenderTarget(w, h, rtOpts)); }
    this.ups = this.mips.map((m) => new THREE.WebGLRenderTarget(m.width, m.height, rtOpts));

    this.cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    this.quad = new THREE.Mesh(fsTri());
    this.quad.frustumCulled = false;
    this.scene = new THREE.Scene(); this.scene.add(this.quad);

    this.mDof = new THREE.ShaderMaterial({
      vertexShader: VS, depthTest: false, depthWrite: false,
      uniforms: { tColor: { value: null }, tDepth: { value: null }, uNear: { value: 0.1 }, uFar: { value: 100 }, uFocus: { value: 5 }, uAperture: { value: 0 }, uMaxCoC: { value: 12 }, uRes: { value: new THREE.Vector2(W, H) } },
      fragmentShader: /* glsl */ `
        uniform sampler2D tColor, tDepth; uniform float uNear, uFar, uFocus, uAperture, uMaxCoC; uniform vec2 uRes; varying vec2 vUv;
        float lin(float d){ float z = d*2.0-1.0; return 2.0*uNear*uFar/(uFar+uNear-z*(uFar-uNear)); }
        float coc(vec2 uv){ float z = lin(texture2D(tDepth, uv).r); return clamp(uAperture * abs(z-uFocus)/max(z,1e-3) * uRes.y/1000.0, 0.0, uMaxCoC); }
        void main(){
          vec4 base = texture2D(tColor, vUv);
          float c0 = coc(vUv);
          if (uAperture <= 0.0 || c0 < 0.5) { gl_FragColor = base; return; }
          vec3 acc = base.rgb; float wsum = 1.0;
          const float GA = 2.39996323;
          for (int i = 1; i < 32; i++) {
            float fi = float(i);
            float r = sqrt(fi / 32.0) * c0;
            vec2 o = vec2(cos(fi*GA), sin(fi*GA)) * r / uRes;
            vec2 uv = vUv + o;
            float cs = coc(uv);
            float w = smoothstep(r - 1.0, r + 1.0, max(cs, c0 * 0.6));
            vec3 s = texture2D(tColor, uv).rgb;
            w *= 1.0 + 0.6 * smoothstep(1.5, 6.0, dot(s, vec3(0.3,0.5,0.2))); // bokeh highlight bias
            acc += s * w; wsum += w;
          }
          gl_FragColor = vec4(acc / wsum, 1.0);
        }`,
    });

    this.mComp = new THREE.ShaderMaterial({
      vertexShader: VS, depthTest: false, depthWrite: false,
      uniforms: { tA: { value: null }, tB: { value: null }, uP: { value: 0 }, uMode: { value: 0 }, uTime: { value: 0 }, uAspect: { value: W / H }, uGold: { value: new THREE.Color('#D6AE57') } },
      fragmentShader: noiseGLSL + /* glsl */ `
        uniform sampler2D tA, tB; uniform float uP, uMode, uTime, uAspect; uniform vec3 uGold; varying vec2 vUv;
        vec2 zoom(vec2 uv, float z){ return (uv-0.5)/z+0.5; }
        void main(){
          float p = clamp(uP, 0.0, 1.0);
          vec2 q = (vUv-0.5) * vec2(uAspect, 1.0);
          float r = length(q);
          vec3 a, b, c;
          if (uMode < 0.5) {               // crossfade (single scene or plain)
            c = mix(texture2D(tA, vUv).rgb, texture2D(tB, vUv).rgb, p);
          } else if (uMode < 1.5) {        // portal: B revealed inside an expanding gold ring, A pushes in
            a = texture2D(tA, zoom(vUv, 1.0 + p*0.6)).rgb;
            b = texture2D(tB, zoom(vUv, 1.25 - p*0.25)).rgb;
            float R = pow(p, 1.6) * 1.25;
            float n = snoise(vec3(q*6.0, uTime*0.8)) * 0.02;
            float m = smoothstep(R + 0.01, R - 0.01, r + n);
            float ring = exp(-pow((r + n - R) * 38.0, 2.0)) * smoothstep(0.0, 0.08, p) * smoothstep(1.0, 0.85, p);
            c = mix(a, b, m) + uGold * ring * 6.0;
          } else if (uMode < 2.5) {        // beam: a vertical light blade widens, floods, then reveals B
            a = texture2D(tA, vUv).rgb; b = texture2D(tB, vUv).rgb;
            float w = pow(p, 1.4) * 0.75;
            float d = abs(q.x);
            float m = smoothstep(w + 0.02, w - 0.02, d);
            float flash = exp(-pow((p - 0.5) * 5.0, 2.0));
            float blade = exp(-pow((d - w) * 30.0, 2.0)) * (1.0 - p);
            c = mix(a, b, m) + vec3(1.0, 0.93, 0.8) * (blade * 5.0 + flash * 1.8 * exp(-d*3.0));
          } else if (uMode < 3.5) {        // spot: A irises down into a moving warm spotlight, B irises up from it
            a = texture2D(tA, vUv).rgb; b = texture2D(tB, vUv).rgb;
            vec2 cen = vec2(0.12 * sin(p * 3.14159), 0.05);
            float rr = length(q - cen);
            float closeR = mix(1.3, 0.0, smoothstep(0.0, 0.5, p));
            float openR = mix(0.0, 1.3, smoothstep(0.5, 1.0, p));
            float ma = smoothstep(closeR + 0.15, closeR - 0.05, rr);
            float mb = smoothstep(openR + 0.15, openR - 0.05, rr);
            vec3 warm = vec3(1.0, 0.82, 0.55);
            float core = exp(-rr*rr*40.0) * exp(-pow((p-0.5)*6.0, 2.0)) * 4.0;
            c = (p < 0.5 ? a * ma : b * mb) + warm * core;
          } else {                          // dissolve: noise burn with incandescent gold edge
            a = texture2D(tA, vUv).rgb; b = texture2D(tB, vUv).rgb;
            float n = fbm3(vec3(q * 5.0, 1.7)) * 0.5 + 0.5;
            float t = p * 1.2 - 0.1;
            float m = smoothstep(t - 0.03, t + 0.03, n);
            float edge = exp(-pow((n - t) * 25.0, 2.0)) * step(0.01, p) * step(p, 0.99);
            c = mix(b, a, m) + uGold * edge * 5.0;
          }
          gl_FragColor = vec4(c, 1.0);
        }`,
    });

    this.mAcc = new THREE.ShaderMaterial({
      vertexShader: VS, depthTest: false, depthWrite: false, transparent: true,
      blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor,
      uniforms: { tSrc: { value: null }, uW: { value: 1 } },
      fragmentShader: `uniform sampler2D tSrc; uniform float uW; varying vec2 vUv; void main(){ gl_FragColor = vec4(min(texture2D(tSrc, vUv).rgb, vec3(64.0)) * uW, 1.0); }`,
    });

    this.mDown = new THREE.ShaderMaterial({
      vertexShader: VS, depthTest: false, depthWrite: false,
      uniforms: { tSrc: { value: null }, uTexel: { value: new THREE.Vector2() }, uThreshold: { value: 1 }, uFirst: { value: 0 } },
      fragmentShader: /* glsl */ `
        uniform sampler2D tSrc; uniform vec2 uTexel; uniform float uThreshold, uFirst; varying vec2 vUv;
        vec3 s(vec2 o){ return texture2D(tSrc, vUv + o * uTexel).rgb; }
        void main(){
          // 13-tap (CoD:AW) downsample, Karis-weighted on first level to kill fireflies
          vec3 a=s(vec2(-2,2)), b=s(vec2(0,2)), c=s(vec2(2,2)), d=s(vec2(-2,0)), e=s(vec2(0,0)), f=s(vec2(2,0)), g=s(vec2(-2,-2)), h=s(vec2(0,-2)), i=s(vec2(2,-2));
          vec3 j=s(vec2(-1,1)), k=s(vec2(1,1)), l=s(vec2(-1,-1)), m=s(vec2(1,-1));
          vec3 col = e*0.125 + (a+c+g+i)*0.03125 + (b+d+f+h)*0.0625 + (j+k+l+m)*0.125;
          if (uFirst > 0.5) {
            float br = max(col.r, max(col.g, col.b));
            float soft = clamp(br - uThreshold + 0.5, 0.0, 1.0); soft = soft*soft*0.5;
            float contrib = max(soft, br - uThreshold) / max(br, 1e-4);
            col *= contrib;
            col /= 1.0 + dot(col, vec3(0.2126, 0.7152, 0.0722)) * 0.25;
          }
          gl_FragColor = vec4(col, 1.0);
        }`,
    });

    this.mUp = new THREE.ShaderMaterial({
      vertexShader: VS, depthTest: false, depthWrite: false,
      uniforms: { tLow: { value: null }, tHigh: { value: null }, uTexel: { value: new THREE.Vector2() }, uRadius: { value: 0.85 } },
      fragmentShader: /* glsl */ `
        uniform sampler2D tLow, tHigh; uniform vec2 uTexel; uniform float uRadius; varying vec2 vUv;
        void main(){
          vec2 t = uTexel;
          vec3 u = texture2D(tLow, vUv + vec2(-t.x, t.y)).rgb + texture2D(tLow, vUv + vec2(t.x, t.y)).rgb
                 + texture2D(tLow, vUv + vec2(-t.x, -t.y)).rgb + texture2D(tLow, vUv + vec2(t.x, -t.y)).rgb
                 + 2.0*(texture2D(tLow, vUv + vec2(0.0, t.y)).rgb + texture2D(tLow, vUv + vec2(0.0, -t.y)).rgb + texture2D(tLow, vUv + vec2(t.x, 0.0)).rgb + texture2D(tLow, vUv + vec2(-t.x, 0.0)).rgb)
                 + 4.0*texture2D(tLow, vUv).rgb;
          u /= 16.0;
          gl_FragColor = vec4(texture2D(tHigh, vUv).rgb + u * uRadius, 1.0);
        }`,
    });

    this.mFinal = new THREE.ShaderMaterial({
      vertexShader: VS, depthTest: false, depthWrite: false,
      uniforms: {
        tHdr: { value: null }, tBloom: { value: null }, uBloom: { value: 0.5 }, uExposure: { value: 1 }, uCA: { value: 0.001 },
        uDistort: { value: 0.02 }, uVignette: { value: 0.35 }, uGrain: { value: 0.02 }, uFrame: { value: 0 }, uAspect: { value: W / H },
        uFade: { value: 1 }, uLift: { value: new THREE.Vector3(0, 0, 0) }, uTint: { value: new THREE.Vector3(1, 1, 1) }, uSat: { value: 1.05 }, uContrast: { value: 1.06 },
      },
      fragmentShader: /* glsl */ `
        uniform sampler2D tHdr, tBloom; uniform float uBloom, uExposure, uCA, uDistort, uVignette, uGrain, uFrame, uAspect, uFade, uSat, uContrast;
        uniform vec3 uLift, uTint; varying vec2 vUv;
        vec3 RRTAndODTFit(vec3 v){ vec3 a = v*(v+0.0245786)-0.000090537; vec3 b = v*(0.983729*v+0.4329510)+0.238081; return a/b; }
        vec3 aces(vec3 c){
          const mat3 I = mat3(0.59719,0.07600,0.02840, 0.35458,0.90834,0.13383, 0.04823,0.01566,0.83777);
          const mat3 O = mat3(1.60475,-0.10208,-0.00327, -0.53108,1.10813,-0.07276, -0.07367,-0.00605,1.07602);
          return clamp(O * RRTAndODTFit(I * c), 0.0, 1.0);
        }
        float h(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
        vec3 srgb(vec3 c){ return mix(c*12.92, 1.055*pow(c, vec3(1.0/2.4))-0.055, step(0.0031308, c)); }
        void main(){
          vec2 c = vUv - 0.5; vec2 cq = c * vec2(uAspect, 1.0);
          float r2 = dot(cq, cq);
          vec2 uv = 0.5 + c * (1.0 - uDistort * r2);       // gentle barrel (zoomed to hide edges)
          uv = 0.5 + (uv - 0.5) * (1.0 - uDistort * 0.18);
          vec2 dir = (uv - 0.5) * uCA * (0.3 + r2 * 2.0) * 10.0;
          vec3 col;
          col.r = texture2D(tHdr, uv + dir).r + texture2D(tBloom, uv + dir).r * uBloom;
          col.g = texture2D(tHdr, uv).g + texture2D(tBloom, uv).g * uBloom;
          col.b = texture2D(tHdr, uv - dir).b + texture2D(tBloom, uv - dir).b * uBloom;
          col *= uExposure * uFade;
          col = col * uTint + uLift;
          col = aces(col);
          float l = dot(col, vec3(0.2126, 0.7152, 0.0722));
          col = mix(vec3(l), col, uSat);
          col = clamp((col - 0.5) * uContrast + 0.5, 0.0, 1.0);
          col *= 1.0 - uVignette * smoothstep(0.15, 0.95, r2 * 1.6);
          vec3 o = srgb(col);
          float g = h(vUv * vec2(1931.7, 2713.3) + uFrame * 17.13) - 0.5;
          o += g * uGrain * (1.0 - o * 0.6);                // luminance-aware grain
          o += (h(vUv * 4096.0 + uFrame) - 0.5) / 255.0;    // dither
          gl_FragColor = vec4(o, 1.0);
        }`,
    });
  }

  pass(mat, target) {
    this.quad.material = mat;
    this.r.setRenderTarget(target);
    this.r.render(this.scene, this.cam);
  }

  /** Render a scene object ({scene, camera, dof}) into slot i, returns HDR texture. */
  renderScene(s, i) {
    const r = this.r;
    r.setRenderTarget(this.sceneRT[i]);
    r.setClearColor(s.clear || 0x050507, 1);
    r.clear();
    s.camera.layers.set(0);
    r.render(s.scene, s.camera);
    let out = this.sceneRT[i];
    if (this.q.dof && s.dof && s.dof.aperture > 0) {
      const u = this.mDof.uniforms;
      u.tColor.value = this.sceneRT[i].texture; u.tDepth.value = this.sceneRT[i].depthTexture;
      u.uNear.value = s.camera.near; u.uFar.value = s.camera.far; u.uFocus.value = s.dof.focus; u.uAperture.value = s.dof.aperture; u.uMaxCoC.value = s.dof.maxCoC || 14;
      this.pass(this.mDof, this.dofRT[i]);
      out = this.dofRT[i];
    }
    // overlay layer (titles): always sharp, composited after DOF with its own depth
    s.camera.layers.set(1);
    r.setRenderTarget(out);
    r.autoClear = false;
    r.clearDepth();
    r.render(s.scene, s.camera);
    r.autoClear = true;
    s.camera.layers.set(0);
    return out.texture;
  }

  comp(texA, texB, p, mode, time) {
    const u = this.mComp.uniforms;
    u.tA.value = texA; u.tB.value = texB || texA; u.uP.value = texB ? p : 0; u.uMode.value = texB ? mode : 0; u.uTime.value = time;
    this.pass(this.mComp, this.compRT);
  }

  clearAcc() { this.r.setRenderTarget(this.accRT); this.r.setClearColor(0, 1); this.r.clear(); }
  accumulate(w) { this.mAcc.uniforms.tSrc.value = this.compRT.texture; this.mAcc.uniforms.uW.value = w; this.pass(this.mAcc, this.accRT); }

  finish(frame, grade = {}) {
    const fx = this.fx;
    const src = this.accRT.texture;
    // bloom
    let prev = src;
    this.mips.forEach((m, i) => {
      const u = this.mDown.uniforms; u.tSrc.value = prev; u.uFirst.value = i === 0 ? 1 : 0; u.uThreshold.value = grade.threshold ?? fx.bloom.threshold;
      u.uTexel.value.set(1 / (i === 0 ? this.W : this.mips[i - 1].width), 1 / (i === 0 ? this.H : this.mips[i - 1].height));
      this.pass(this.mDown, m); prev = m.texture;
    });
    let low = this.mips[this.mips.length - 1].texture;
    for (let i = this.mips.length - 2; i >= 0; i--) {
      const u = this.mUp.uniforms; u.tLow.value = low; u.tHigh.value = this.mips[i].texture; u.uRadius.value = fx.bloom.radius;
      u.uTexel.value.set(1 / this.mips[i + 1].width, 1 / this.mips[i + 1].height);
      this.pass(this.mUp, this.ups[i]); low = this.ups[i].texture;
    }
    const u = this.mFinal.uniforms;
    u.tHdr.value = src; u.tBloom.value = low;
    u.uBloom.value = fx.bloom.enabled ? (grade.bloom ?? fx.bloom.strength) : 0;
    u.uExposure.value = (grade.exposure ?? 1) * fx.exposure;
    u.uCA.value = grade.ca ?? fx.chromaticAberration; u.uDistort.value = fx.lensDistortion; u.uVignette.value = grade.vignette ?? fx.vignette;
    u.uGrain.value = fx.grain; u.uFrame.value = frame % 997; u.uFade.value = grade.fade ?? 1;
    u.uSat.value = grade.sat ?? 1.05; u.uContrast.value = grade.contrast ?? 1.06;
    u.uTint.value.set(...(grade.tint || [1, 1, 1])); u.uLift.value.set(...(grade.lift || [0, 0, 0]));
    this.pass(this.mFinal, null);
  }
}

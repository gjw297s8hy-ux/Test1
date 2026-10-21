# WESTAFF PLACE — 30 s cinematic vertical ad

A complete, reproducible production: six procedural 3D scenes built in Three.js (PBR materials,
real extruded typography, GPU particles, volumetric beams), rendered frame-by-frame in headless
Chromium, finished with a custom HDR post chain, and scored with an original synthesized soundtrack.

**Deliverable:** `renders/westaff_place_master_1080x1920_60fps.mp4` — 1080×1920, 60 fps, H.264 High,
AAC 48 kHz stereo, 30.0 s. A silent alternate (`…_silent.mp4`) and a verification report
(`…_report.json`) sit next to it. Contact sheets per scene: `previews/final/`.

## Why this toolchain

The production environment was inspected first (see *Environment* below). After Effects was not
reachable (no app connected to the Filmit MCP; the local AE MCP needs AE running on the same
machine), Blender is not installed, and there is no GPU. Headless Chromium with SwiftShader does
provide WebGL2 with float render targets, so the whole film is real-time-style 3D rendered offline
on CPU — deterministic, scriptable, and editable as code.

## Run it

```bash
npm install
npm run fonts                                   # OFL fonts -> Three.js typeface JSON (incl. accents)
npm run audio                                   # synthesize audio/westaff_place_mix_48k.wav
node scripts/render.mjs --q draft --stills 3,7.5,12,16,21,28    # inspect frames -> previews/draft
node scripts/render.mjs --q preview --w 540 --h 960 --fps 30 --out renders/preview.mp4 --workers 2
node scripts/render.mjs --q final --codec prores --out renders/master_video.mov --workers 3
node scripts/master.mjs --video renders/master_video.mov        # mux + verify + contact sheets
```

Quality presets live in `config/config.json` (`preview`, `draft`, `final`, `uhd`). `uhd`
(2160×3840) works but costs ~4× the final render time on CPU.

## Layout

| Path | Role |
| --- | --- |
| `config/config.json` | Brand, handle, palette, copy, resolution/FPS/duration, quality presets, scene timing, transitions, effects |
| `src/engine/` | Deterministic frame engine (`main.js`), shared helpers (`lib.js`: easing, 3D text, procedural textures, studio env maps) |
| `scenes/s1…s6_*.js` | One module per scene; each returns `{scene, camera, update(t), dof, grade}` |
| `scenes/common/` | Ticket factory (PBR maps drawn procedurally), kinetic title system |
| `materials/` | PBR library: gold, brushed anisotropic silver, chrome, smoked glass, holographic (iridescence), velvet (sheen) |
| `shaders/` | Simplex/curl noise, particle fields, volumetric beams, haze, glints, post chain |
| `scripts/` | `render.mjs` (headless renderer → ffmpeg), `audio.py` (score), `master.mjs` (delivery + QC), `build-fonts.mjs` |
| `assets/fonts/` | Cinzel + Montserrat (SIL OFL) converted to typeface JSON |
| `audio/` | Generated 48 kHz mix |
| `renders/`, `previews/` | Outputs and inspection frames |

## Pipeline

Per frame: scene → MSAA HDR target → depth-of-field (CoC gather) → title overlay layer (always
sharp, composited after DOF) → transition compositor (portal / light-beam / spotlight / crossfade)
→ motion-blur accumulation (2 sub-frames, 180° shutter) → 7-level bloom → ACES filmic tone map,
light lens distortion, chromatic aberration, vignette, grain, dither → 8-bit → ffmpeg.
Everything is a pure function of the frame index (seeded RNG, analytic particle motion), so any frame
range can be re-rendered in parallel and concatenated.

## Scenes and edit (120 BPM, every cut on a beat)

| Time | Scene | Built from |
| --- | --- | --- |
| 0–4 | Awakening | 48k curl-noise particles → energy ring, push-through, hero gold ticket (guilloche micro-engraving, embossed foil, bevelled notched geometry), title lands on the 3.0 s impact |
| 4–9 | Football | Superellipse bowl, 3 tiers with shader crowd (anti-aliased), LED fascias, cantilever roof with truss and 192 floodlight units, volumetric beams, mown pitch with regulation markings, chrome/gold truncated-icosahedron ball |
| 9–14 | Concert | Box-truss rig, 20 moving heads + 10 sky beams on a bar-by-bar choreography, laser fans, pixel-grid LED wall, 3,600 instanced crowd silhouettes |
| 14–18 | Theatre | Gold proscenium with fluted columns and mouldings, velvet traveler curtains with live folds, valance + fringe, balconies, dust in spotlights, comedy/tragedy masks modelled from SDF outlines, ticket portal |
| 18–24 | Ticket reveal | FOOTBALL / CONCERT / SPECTACLE tickets with own motifs and accents, extruded labels, orbit to a fan formation, holographic € tag with falling chevrons |
| 24–30 | Finale | Tickets burn into 42k particles sampled from their surfaces, spiral onto points sampled from the wordmark; WESTAFF in brushed silver with gold bevels, PLACE in gold, tagline and contact |

## Audio

`scripts/audio.py` synthesizes everything (no samples, no third-party audio): sub pulses, particle
shimmer grains, risers, whooshes, cinematic impacts with metallic partials, drums, bass, pads, arps,
Karplus-Strong harp, bells, crowd beds, a synthesized hall reverb. Master: −16 LUFS integrated,
−1.0 dBTP (4× oversampled true-peak check).

## Known compromises (honest list)

- **Logo:** no logo file was present anywhere in the environment. The WESTAFF PLACE wordmark is a
  typographic reconstruction from the brief (extruded silver WESTAFF with gold accents, PLACE in gold
  beneath). The real logo should replace it before any public use: provide the file and the scene-6
  wordmark (built in `scenes/s6_finale.js`) can be rebuilt around it (`brand.logoFile` is reserved
  in the config for this; it is not wired up yet).
- **Social handle:** none was provided, so the end card shows `@COMPTE_OFFICIEL` exactly as in the
  brief. Set `brand.socialHandle` in the config and re-render 27–30 s.
- **Resolution:** master is 1080×1920 (the brief's fallback). 2160×3840 is supported (`--q uhd`) but
  would take ~6 h on this CPU-only machine.
- **Rendering:** rasterized PBR with image-based lighting, not path tracing: reflections come from
  art-directed environment maps (no ray-traced inter-reflections), volumetrics are shaded cones/sheets.
- **After Effects:** not used (not reachable). Compositing/finishing is done by the custom post chain.

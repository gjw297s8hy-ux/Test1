# REVIEW — « Vos vidéos pour vos business »

Output: `renders/vos-videos-pour-vos-business.mp4` — 1920×1080, 60 fps, 30.0 s, 1 800 frames, H.264 + AAC 48 kHz, 23 MB.

## v3 (person's notes: new hook sentence, a photoreal 3D chart that makes sales climb)
- Hook is now « VOS VIDÉOS POUR VOS BUSINESS »; the 3D voxel word is BUSINESS; the phone posts « nouvelle vidéo
  pour notre business ».
- The frames-per-scene chart was replaced by a photoreal Three.js studio shot: PBR lime bars with clearcoat, softbox
  environment map, ACES tone mapping, soft shadows, an ink arrow taking off. The chart carries no figures: any
  number there would be invented.
- `dead_stretch` 11.5–15.5 s is kept: check cannot see the WebGL canvas, and the camera moves through it.

## v2 (person's notes: colours didn't go together; new end title)
- Palette moved from four inks (orange, cobalt, paper, ink) to three: ink #111111, cream #F2EEE6, lime #C8F43A.
- End card is now the offer « VOS VIDÉOS, FLYERS, TEASERS — À PRIX COÛTANT. » (read « Marc plutôt » as « marque
  plutôt »). The « Claude × HyperFrames » lockup and the install command were removed: the film is now a promo.

## Creative calls
- The 4 X reference posts could not be opened from the build sandbox (x.com is blocked by its network policy), so
  the look comes from the subject: a screen-print poster (four flat inks, Archivo Black, second plate off register).
- Storyline A was built (the person's own sentence carried through type → 3D → data → UI → end card).
  Not built: B « L'atelier en une prise » (one continuous take across a desk), C « Split screen to one » (four panes
  collapsing into one). See `STORYLINES.md`.
- Every number on screen is real: 2 424 is the cube count computed at build, 1 800 the film's frame count, the bars
  are the frames per scene (4/6/6/8/6 s at 60 fps), the end command is the one used to install HyperFrames.
- The phone UI is a generic composer/feed, not any real network's UI or branding; no engagement numbers are shown.

## Measured vs looked at
- `hyperframes check`: ok (0 errors). Rendered file probed (duration, fps, frame count) and 14 decoded frames looked at.
- Audio measured, not heard: integrated −16.5 LUFS, sample peak −1.4 dBFS, sound present across the film except a
  deliberate ~1 s hold before the dive into the O (2.5–3.3 s).
- The music bed is a placeholder generated in code (`scripts/make_bed.py`, 120 BPM) because no music source was
  reachable (no HeyGen sign-in, no network for local models). Swap `assets/bed.wav` for a real track (30 s).
- Sound effects: the HyperFrames bundled library (Pixabay licence, see `assets/sfx/CREDITS.md`).

## Kept on purpose
- `line_unread` on the mini-film inside the phone: it is footage playing, cut every 0.25 s like a montage.
- `timeline_track_too_dense` on the phone scene.

## Weakest shot, with more time
- 16–24 s (phone): the phone UI text is small at phone viewing size; a punch-in on the Publier button would read better.
- The 3D shot ends on a fast dive through cubes that is hard to follow; a slower dive or a cleaner face would help.

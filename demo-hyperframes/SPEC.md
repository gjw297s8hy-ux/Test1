# SPEC — « Vos vidéos pour vos business »

GOAL:    a business owner sees what a video can do for them (type, 3D, a sales chart that climbs, a posted
         film) and remembers « vos vidéos, flyers, teasers à prix coûtant ».
OUTPUT:  HyperFrames, 1920 x 1080, 60 fps
TIME:    30 s x 60 = 1 800 frames. 120 BPM -> 30 frames per beat, 120 per bar (2 s). 15 bars.
LOOK:    screen-print poster. Three flat inks, no gradients on grounds (v2: orange + cobalt clashed):
           ink #111111, cream #F2EEE6, acid lime #C8F43A (accent).
         Every ground is one ink; type is ink on lime/cream, cream or lime on ink. Never lime on cream.
         Lime is the accent: one focus per frame (DÉPOTE, the current bar, the button, the end card).
         Display: Archivo Black 400, uppercase, tracking -0.02em, hero words 60-90% of frame width.
         Numerals: League Gothic 400. Small copy: Montserrat 700, >= 34 px.
         Medium: second plate printed 10 px off register (cream under ink or lime) on hero words; paper grain 5 %.
         3D: flat 3-tone toon shading in the same inks, hard shadow at 0.35.
OBJECTS: the sentence (type), 2 000+ printed cubes forming DÉPOTE, a bar chart of this film's frames per scene,
         a phone (black body, 44 px corner radius, notch, real-looking composer UI), a big arrow cursor (5 % frame).
MOTION:  enter expo.out / power4.out; camera power2.inOut; exit and zoom-through power3.in.
         Hits are tl.set at 0 ms. Springs: back.out(1.4) on position/scale only.
         Word stagger 60-120 ms. Exits 40-50 % shorter than entrances.
SHOTS:
  0.0-4.0  PHRASE   VOS / VIDÉOS / POUR VOS / BUSINESS, one per beat on a new ground (lime, ink, cream, ink);
                    BUSINESS prints its two plates; camera dives into the upper counter of the B -> ink.     [impacts per word]
  4.0-10.0 MATIÈRE  ink ground, dark floor fading into fog; cubes fly in and assemble BUSINESS (seeded delays), orbit 35° -> 0°;
                    « N CUBES. ZÉRO CAMÉRA. »; a wave flips cubes lime -> cream; camera dives into a cream cube.
  10.0-16.0 VENTES   photoreal studio: cream cove, softbox environment, ACES; six lacquered lime bars rise out
                    of the floor, a glossy ink arrow climbs over them and takes off; « VOS VENTES GRIMPENT. »;
                    whip left. No figures on the chart (illustrative, no invented numbers).                                            [pops, whoosh]
  16.0-24.0 ÉCRAN   ink ground; phone lands from the whip; « nouvelle vidéo pour notre business » typed in the composer, video attached;
                    cursor clicks Publier -> button morphs into « Publié »; post plays; tap -> lime iris.
  24.0-30.0 FIN     lime ground; « VOS VIDÉOS, » « FLYERS, » « TEASERS » one line per beat; riser ->
                    « À PRIX COÛTANT. » prints, cream plate off register, holds 3.5 s.
BANNED:  dark void with small floating things; glow, bloom, particles as decoration; purple/blue gradients, glass;
         cream + serif + mono-label look; everything centred; fade + slide-up on everything; titles that drift after
         landing; HUD/corner brackets; three cards in a row; docked logo; click rings; invented engagement numbers.
QA:      t=0 (thumbnail: FAIS-MOI fills frame), 3.9 (ink flood), 7.5 (voxel word readable), 12.6 (bars + arrow),
         14.6 (chart wide), 19.6 (click), 25.3 (offer list), 29.5 (À PRIX COÛTANT).

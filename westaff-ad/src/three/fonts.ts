import {staticFile, delayRender, continueRender} from 'remotion';
import {useEffect, useState} from 'react';
import {TTFLoader} from 'three/examples/jsm/loaders/TTFLoader.js';
import {Font, FontLoader} from 'three/examples/jsm/loaders/FontLoader.js';

/** Charge une police OTF/TTF en Font three.js (glyphes extrudables) + l'enregistre pour le Canvas 2D. */
export const useFonts = () => {
  const [fonts, setFonts] = useState<{display: Font; bold: Font} | null>(null);
  const [handle] = useState(() => delayRender('fonts'));
  useEffect(() => {
    const load3D = async (file: string) => {
      const buf = await (await fetch(staticFile(file))).arrayBuffer();
      const loader = new TTFLoader();
      loader.reversed = true; // contours CFF (OTF) : sens inverse des TrueType → trous des lettres corrects
      const json = loader.parse(buf);
      return new FontLoader().parse(json);
    };
    const load2D = async (family: string, file: string) => {
      const ff = new FontFace(family, `url(${staticFile(file)})`);
      await ff.load();
      (document as any).fonts.add(ff);
    };
    Promise.all([
      load3D('fonts/InterDisplay-Black.otf'),
      load3D('fonts/Inter-ExtraBold.otf'),
      load2D('WDisplay', 'fonts/InterDisplay-Black.otf'),
      load2D('WBold', 'fonts/Inter-ExtraBold.otf'),
      load2D('WSemi', 'fonts/Inter-SemiBold.otf'),
      load2D('WMedium', 'fonts/Inter-Medium.otf'),
    ]).then(([display, bold]) => {
      setFonts({display, bold});
      continueRender(handle);
    });
  }, [handle]);
  return fonts;
};

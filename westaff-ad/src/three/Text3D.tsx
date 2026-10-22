import React, {useMemo} from 'react';
import * as THREE from 'three';
import {TextGeometry} from 'three/examples/jsm/geometries/TextGeometry.js';
import type {Font} from 'three/examples/jsm/loaders/FontLoader.js';

export type LetterAnim = (i: number, n: number) => {y?: number; z?: number; rx?: number; ry?: number; s?: number; x?: number};

type Props = JSX.IntrinsicElements['group'] & {
  font: Font; text: string; size: number; depth?: number; tracking?: number;
  material: THREE.Material | THREE.Material[]; anim?: LetterAnim; align?: 'center' | 'left'; castShadow?: boolean;
};

/** Texte extrudé lettre par lettre (biseau, pivot centré) pour une animation cinétique par glyphe. */
export const Text3D: React.FC<Props> = ({font, text, size, depth = 0.25, tracking = 0, material, anim, align = 'center', castShadow = false, ...rest}) => {
  const glyphs = useMemo(() => {
    const scale = size / (font.data as any).resolution;
    let x = 0;
    const out: {geo: THREE.BufferGeometry | null; x: number}[] = [];
    for (const ch of [...text]) {
      const gd = (font.data as any).glyphs[ch] || (font.data as any).glyphs['?'];
      const adv = (gd?.ha ?? 500) * scale;
      let geo: THREE.BufferGeometry | null = null;
      if (ch.trim()) {
        geo = new TextGeometry(ch, {
          font, size, depth: size * depth, curveSegments: 10,
          bevelEnabled: true, bevelThickness: size * 0.035, bevelSize: size * 0.018, bevelSegments: 4,
        });
        geo.computeBoundingBox();
        const bb = geo.boundingBox!;
        const cx = (bb.min.x + bb.max.x) / 2;
        geo.translate(-cx, -size * 0.36, -(size * depth) / 2);
        out.push({geo, x: x + cx});
      } else out.push({geo: null, x: x + adv / 2});
      x += adv + tracking * size;
    }
    const total = x - tracking * size;
    const off = align === 'center' ? -total / 2 : 0;
    out.forEach((g) => (g.x += off));
    return out;
  }, [font, text, size, depth, tracking, align]);

  return (
    <group {...rest}>
      {glyphs.map((g, i) => {
        if (!g.geo) return null;
        const a = anim ? anim(i, glyphs.length) : {};
        const s = a.s ?? 1;
        return (
          <mesh key={i} geometry={g.geo} material={material as any}
            position={[g.x + (a.x ?? 0), a.y ?? 0, a.z ?? 0]} rotation={[a.rx ?? 0, a.ry ?? 0, 0]}
            scale={[s, s, s]} visible={s > 0.001} castShadow={castShadow} />
        );
      })}
    </group>
  );
};

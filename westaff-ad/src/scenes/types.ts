import type {Font} from 'three/examples/jsm/loaders/FontLoader.js';
export type Fonts = {display: Font; bold: Font; gothic?: Font};
export type CamState = {pos: [number, number, number]; target: [number, number, number]; fov: number; roll?: number};
export type SceneLook = {background: string; fog?: {color: string; density: number}; env: number; exposure: number; bloom: number};

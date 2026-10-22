import {Config} from '@remotion/cli/config';

// Rendu CPU (pas de GPU dans ce conteneur) : WebGL logiciel via SwiftShader/ANGLE.
// Sur une machine avec GPU, remplacez par 'angle' (ou 'egl' sous Linux) pour accélérer.
Config.setChromiumOpenGlRenderer((process.env.REMOTION_GL as any) || 'swangle');
Config.setVideoImageFormat('jpeg');
Config.setJpegQuality(95);
Config.setConcurrency(Number(process.env.REMOTION_CONCURRENCY || 3));
Config.setDelayRenderTimeoutInMilliseconds(120000);
if (process.env.REMOTION_BROWSER) Config.setBrowserExecutable(process.env.REMOTION_BROWSER);

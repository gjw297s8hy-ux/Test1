import React from 'react';
import {Composition} from 'remotion';
import {Ad} from './Ad';
import {VIDEO} from './brand';
import {Release} from './release/Release';
import {REL} from './release/config';

export const RemotionRoot: React.FC = () => (
  <>
  <Composition id="Ad" component={Ad} durationInFrames={VIDEO.fps * VIDEO.seconds} fps={VIDEO.fps} width={VIDEO.width} height={VIDEO.height}
    defaultProps={{showSafeZones: false, forceFallback: false, withAudio: true}} />
  <Composition id="NPNG-PR" component={Release} durationInFrames={REL.video.fps * REL.video.seconds} fps={REL.video.fps} width={REL.video.width} height={REL.video.height}
    defaultProps={{withAudio: true, photoreal: true}} />
  <Composition id="NPNG" component={Release} durationInFrames={REL.video.fps * REL.video.seconds} fps={REL.video.fps} width={REL.video.width} height={REL.video.height}
    defaultProps={{withAudio: true}} />
  </>
);

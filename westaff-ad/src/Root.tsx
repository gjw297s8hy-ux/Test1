import React from 'react';
import {Composition} from 'remotion';
import {Ad} from './Ad';
import {VIDEO} from './brand';

export const RemotionRoot: React.FC = () => (
  <Composition id="Ad" component={Ad} durationInFrames={VIDEO.fps * VIDEO.seconds} fps={VIDEO.fps} width={VIDEO.width} height={VIDEO.height}
    defaultProps={{showSafeZones: false, forceFallback: false, withAudio: true}} />
);

import Phaser from 'phaser';
import { GreywaterScene } from './scenes/GreywaterScene';

new Phaser.Game({
  type: Phaser.AUTO,
  width: 960,
  height: 640,
  parent: 'game',
  physics: { default: 'arcade', arcade: { gravity: { x: 0, y: 0 } } },
  scene: [GreywaterScene],
  pixelArt: true,
});
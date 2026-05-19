import Phaser from 'phaser';

export class GreywaterScene extends Phaser.Scene {
  private player!: Phaser.GameObjects.Rectangle;
  private wasd!: {
    W: Phaser.Input.Keyboard.Key;
    A: Phaser.Input.Keyboard.Key;
    S: Phaser.Input.Keyboard.Key;
    D: Phaser.Input.Keyboard.Key;
  };

  constructor() {
    super('greywater');
  }

  create() {
    this.cameras.main.setBackgroundColor('#2d2d3a');

    this.add
      .text(480, 40, 'Greywater Township', {
        color: '#ffffff',
        fontSize: '28px',
      })
      .setOrigin(0.5, 0);

    this.player = this.add.rectangle(480, 320, 32, 48, 0xff6b6b);
    this.wasd = this.input.keyboard!.addKeys('W,A,S,D') as typeof this.wasd;
  }

  update() {
    const speed = 3;
    if (this.wasd.A.isDown) this.player.x -= speed;
    if (this.wasd.D.isDown) this.player.x += speed;
    if (this.wasd.W.isDown) this.player.y -= speed;
    if (this.wasd.S.isDown) this.player.y += speed;
  }
}
import Phaser from 'phaser';
// Kenney "Tiny Town" tile index constants.
// Source: Tilemap/tilemap_packed.png  (12 cols x 11 rows = 132 tiles, 16x16, 1px gap)
// Index formula:  index = row * 12 + col
//
// Names marked with `// ?` are visual-guess and may need renaming after you
// open the sheet in an image viewer. Indices themselves are correct.
const MAP_W = 50;
const MAP_H = 25;
const TILE_SCALE = 2;       


export class GreywaterScene extends Phaser.Scene {
  private player!: Phaser.GameObjects.Sprite;
  private cursors!: Phaser.Types.Input.Keyboard.CursorKeys;
  private wasd!: {
    W: Phaser.Input.Keyboard.Key;
    A: Phaser.Input.Keyboard.Key;
    S: Phaser.Input.Keyboard.Key;
    D: Phaser.Input.Keyboard.Key;
  };

  constructor() {
    super('greywater');
  }

  preload() {
    this.load.spritesheet('tiny-town', '/tilesets/tiny-town.png', {
      frameWidth: 16,
      frameHeight: 16,
    });
    this.load.spritesheet('tiny-dungeon', '/tilesets/tiny-dungeon.png', {
      frameWidth: 16,
      frameHeight: 16,
    });
    this.load.tilemapTiledJSON('town-map', '/maps/tiny_town_v1.tmj');
  }
  create() {
    // Load the map from the Tiled JSON
    const map = this.make.tilemap({ key: 'town-map' });

    // Hook up the tileset image (first arg = name in Tiled, second = key from preload)
    const townTileset    = map.addTilesetImage('tiny-town',    'tiny-town');
    const dungeonTileset = map.addTilesetImage('tiny-dungeon', 'tiny-dungeon');
    if (!townTileset || !dungeonTileset) throw new Error('Tileset not found in tilemap');
    const tilesets = [townTileset, dungeonTileset];

    const layers = map.layers.map(l =>
      map.createLayer(l.name, tilesets, 0, 0)?.setScale(TILE_SCALE)
    );

    // 8. Label + player on top of the map (depth 10 ensures they render above tiles)
    this.cameras.main.setBackgroundColor('#2d2d3a');
    this.add.text(480, 4, 'Greywater Township', { color: '#ffffff', fontSize: '20px' })
      .setOrigin(0.5, 0)
      .setDepth(10);  
    
    this.player = this.add.sprite(320, 280, 'tiny-dungeon', 85)   // ← swap 96 for your chosen index
      .setScale(TILE_SCALE)
      .setDepth(10);

    this.cursors = this.input.keyboard!.createCursorKeys();
    this.wasd = this.input.keyboard!.addKeys('W,A,S,D') as typeof this.wasd;

    const worldW = map.widthInPixels * TILE_SCALE;
    const worldH = map.heightInPixels * TILE_SCALE;
    this.cameras.main.setBounds(0, 0, worldW, worldH);
    this.cameras.main.startFollow(this.player, true, 0.1, 0.1);
  }

  update() {
    const speed = 3;
    if (this.wasd.A.isDown) this.player.x -= speed;
    if (this.wasd.D.isDown) this.player.x += speed;
    if (this.wasd.W.isDown) this.player.y -= speed;
    if (this.wasd.S.isDown) this.player.y += speed;
  }
}
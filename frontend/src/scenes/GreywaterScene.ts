import Phaser from 'phaser';
// Kenney "Tiny Town" tile index constants.
// Source: Tilemap/tilemap_packed.png  (12 cols x 11 rows = 132 tiles, 16x16, 1px gap)
// Index formula:  index = row * 12 + col
//
// Names marked with `// ?` are visual-guess and may need renaming after you
// open the sheet in an image viewer. Indices themselves are correct.
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000';
const MAP_W = 50;
const MAP_H = 25;
const TILE_SCALE = 2;       
const NPCs = [
  { name: 'Guard',  tile: 97,  x: 25, y: 20 },
  { name: 'Miller', tile: 100, x: 33, y: 9  },
  { name: 'Reeve',  tile: 84,  x: 25, y: 10 },
];
type NPC = typeof NPCs[number];
const INTERACT_RANGE = 60;

export class GreywaterScene extends Phaser.Scene {
  private player!: Phaser.GameObjects.Sprite;
  private cursors!: Phaser.Types.Input.Keyboard.CursorKeys;
  private wasd!: {
    W: Phaser.Input.Keyboard.Key;
    A: Phaser.Input.Keyboard.Key;
    S: Phaser.Input.Keyboard.Key;
    D: Phaser.Input.Keyboard.Key;
  };
  private eKey!: Phaser.Input.Keyboard.Key;
  private npcSprites: { sprite: Phaser.GameObjects.Sprite; data: NPC }[] = [];
  private dialogueUI: {
    panel: Phaser.GameObjects.Rectangle;
    nameText: Phaser.GameObjects.Text;
    bodyText: Phaser.GameObjects.Text;
    hint: Phaser.GameObjects.Text;
  } | null = null;

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
    this.eKey = this.input.keyboard!.addKey('E');

    const worldW = map.widthInPixels * TILE_SCALE;
    const worldH = map.heightInPixels * TILE_SCALE;
    this.cameras.main.setBounds(0, 0, worldW, worldH);
    this.cameras.main.startFollow(this.player, true, 0.1, 0.1);

    NPCs.forEach(npc => {
      const worldX = npc.x * 16 * TILE_SCALE;
      const worldY = npc.y * 16 * TILE_SCALE;
      const sprite = this.add.sprite(worldX, worldY, 'tiny-dungeon', npc.tile)
        .setScale(TILE_SCALE)
        .setDepth(10)
        .setInteractive({ useHandCursor: true });
      this.add.text(worldX, worldY - 20, npc.name, {
        color: '#fff', fontSize: '12px', backgroundColor: '#0006', padding: { x: 2 }
      }).setOrigin(0.5, 1).setDepth(11);
      sprite.on('pointerdown', () => this.openDialogue(npc));
      this.npcSprites.push({ sprite, data: npc });
    });
  }

  update() {
    // E toggles dialogue (JustDown fires once per press, not every frame)
    if (Phaser.Input.Keyboard.JustDown(this.eKey)) {
      if (this.dialogueUI) {
        this.closeDialogue();
      } else {
        const nearest = this.findNearestNPC();
        if (nearest) this.openDialogue(nearest);
      }
    }

    // Movement is gated: no walking while reading
    if (this.dialogueUI) return;

    const speed = 3;
    if (this.wasd.A.isDown) this.player.x -= speed;
    if (this.wasd.D.isDown) this.player.x += speed;
    if (this.wasd.W.isDown) this.player.y -= speed;
    if (this.wasd.S.isDown) this.player.y += speed;
  }

  private findNearestNPC(): NPC | null {
    let bestData: NPC | null = null;
    let bestDist = Infinity;
    for (const { sprite, data } of this.npcSprites) {
      const dist = Phaser.Math.Distance.Between(sprite.x, sprite.y, this.player.x, this.player.y);
      if (dist <= INTERACT_RANGE && dist < bestDist) {
        bestDist = dist;
        bestData = data;
      }
    }
    return bestData;
  }
  private async openDialogue(npc: NPC) {
    if (this.dialogueUI) this.closeDialogue();
  
    const cam = this.cameras.main;
    const panelH = 100;
    const panelY = cam.height - panelH;
  
    const panel = this.add.rectangle(0, panelY, cam.width, panelH, 0x000000, 0.75)
      .setOrigin(0, 0)
      .setScrollFactor(0)
      .setDepth(100)
      .setInteractive();
  
    const nameText = this.add.text(20, panelY + 12, npc.name, {
      color: '#ffcf5a', fontSize: '18px', fontStyle: 'bold',
    }).setScrollFactor(0).setDepth(101);
  
    const bodyText = this.add.text(20, panelY + 40, '...', {
      color: '#ffffff', fontSize: '14px',
      wordWrap: { width: cam.width - 40 },
    }).setScrollFactor(0).setDepth(101);
  
    const hint = this.add.text(cam.width - 12, panelY + panelH - 8, '[E] or click to close', {
      color: '#aaaaaa', fontSize: '10px',
    }).setOrigin(1, 1).setScrollFactor(0).setDepth(101);
  
    panel.on('pointerdown', () => this.closeDialogue());
    this.dialogueUI = { panel, nameText, bodyText, hint };
  
    const currentUI = this.dialogueUI;
    const npcId = npc.name.toLowerCase();
  
    try {
      const res = await fetch(`${BACKEND_URL}/npcs/${npcId}/dialogue`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (this.dialogueUI === currentUI) currentUI.bodyText.setText(data.dialogue);
    } catch (err) {
      if (this.dialogueUI === currentUI) {
        currentUI.bodyText.setText(`[couldn't reach server: ${err}]`);
      }
    }
  }

  private closeDialogue() {
    if (!this.dialogueUI) return;
    Object.values(this.dialogueUI).forEach(o => o.destroy());
    this.dialogueUI = null;
  }
}
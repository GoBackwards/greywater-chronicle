import Phaser from 'phaser';
// Kenney "Tiny Town" tile index constants.
// Source: Tilemap/tilemap_packed.png  (12 cols x 11 rows = 132 tiles, 16x16, 1px gap)
// Index formula:  index = row * 12 + col
//
// Names marked with `// ?` are visual-guess and may need renaming after you
// open the sheet in an image viewer. Indices themselves are correct.
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000';
const TILE_SCALE = 2;
const NPCs = [
  { name: 'Guard',  tile: 97,  x: 25, y: 20 },
  { name: 'Miller', tile: 100, x: 33, y: 9  },
  { name: 'Reeve',  tile: 84,  x: 25, y: 10 },
];
type NPC = typeof NPCs[number];

type WorldSnapshot = {
  revision: number;
  mill_status: 'broken' | 'working';
};

type PlayerSession = {
  player_id: string;
  session_token: string;
};

const INTERACT_RANGE = 60;

type PendingRepairCommand = {
  readonly command_id: string;
  readonly expected_revision: number;
};

export class GreywaterScene extends Phaser.Scene {
  private player!: Phaser.Physics.Arcade.Sprite;
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

  private worldSnapshot: WorldSnapshot | null = null;
  private worldStatusText!: Phaser.GameObjects.Text;
  private playerSession: PlayerSession | null = null;
  private sessionStatusText!: Phaser.GameObjects.Text;
  private repairControlText!: Phaser.GameObjects.Text;
  private repairInFlight = false;
  private pendingRepairCommand: PendingRepairCommand | null = null;
  private millWheel!: Phaser.GameObjects.Image;
  private millStateText!: Phaser.GameObjects.Text;

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

    const groundLayer = map.createLayer(
      'Ground',
      tilesets,
      0,
      0,
    );

    const structuresLayer = map.createLayer(
      'StructuresBelowActors',
      tilesets,
      0,
      0,
    );

    const foregroundLayer = map.createLayer(
      'ForegroundAboveActors',
      tilesets,
      0,
      0,
    );

    if (
      !groundLayer ||
      !structuresLayer ||
      !foregroundLayer
    ) {
      throw new Error('Required tilemap layer is missing');
    }

    groundLayer
      .setScale(TILE_SCALE)
      .setDepth(0);

    structuresLayer
      .setScale(TILE_SCALE)
      .setDepth(10);

    foregroundLayer
      .setScale(TILE_SCALE)
      .setDepth(30);

    // Actors render between lower structures (depth 10) and foreground tiles (depth 30).
    this.cameras.main.setBackgroundColor('#2d2d3a');
    this.add.text(480, 4, 'Greywater Township', { color: '#ffffff', fontSize: '20px' })
      .setOrigin(0.5, 0)
      .setDepth(10);

    this.player = this.physics.add.sprite(
      320,
      280,
      'tiny-dungeon',
      85,
    )
      .setScale(TILE_SCALE)
      .setDepth(20)
      .setBodySize(10, 6, false)
      .setOffset(3, 10)
      .setCollideWorldBounds(true);

    this.wasd = this.input.keyboard!.addKeys('W,A,S,D') as typeof this.wasd;
    this.eKey = this.input.keyboard!.addKey('E');

    const worldW = map.widthInPixels * TILE_SCALE;
    const worldH = map.heightInPixels * TILE_SCALE;
    this.physics.world.setBounds(
      0,
      0,
      worldW,
      worldH,
    );
    this.createCollisionBodies(map);
    this.createMillVisual(map);
    this.cameras.main.setBounds(
      0,
      0,
      worldW,
      worldH,
    );

    this.cameras.main.startFollow(this.player, true, 0.1, 0.1);

    NPCs.forEach(npc => {
      const worldX = npc.x * 16 * TILE_SCALE;
      const worldY = npc.y * 16 * TILE_SCALE;
      const sprite = this.add.sprite(worldX, worldY, 'tiny-dungeon', npc.tile)
        .setScale(TILE_SCALE)
        .setDepth(20)
        .setInteractive({ useHandCursor: true });
      this.add.text(worldX, worldY - 20, npc.name, {
        color: '#fff', fontSize: '12px', backgroundColor: '#0006', padding: { x: 2 }
      }).setOrigin(0.5, 1).setDepth(21);
      sprite.on('pointerdown', () => this.openDialogue(npc));
      this.npcSprites.push({ sprite, data: npc });
    });

    this.worldStatusText = this.add.text(
      12,
      32,
      'World: loading...',
      {
        color: '#ffffff',
        fontSize: '14px',
        backgroundColor: '#000000',
        padding: { x: 6, y: 4 },
      },
    )
      .setScrollFactor(0)
      .setDepth(100);

    this.sessionStatusText = this.add.text(
      12,
      60,
      'Session: connecting...',
      {
        color: '#ffffff',
        fontSize: '14px',
        backgroundColor: '#000000',
        padding: { x: 6, y: 4 },
      },
    )
      .setScrollFactor(0)
      .setDepth(100);

    this.repairControlText = this.add.text(
      12,
      88,
      'Repair: waiting...',
      {
        color: '#aaaaaa',
        fontSize: '14px',
        backgroundColor: '#000000',
        padding: { x: 6, y: 4 },
      },
    )
      .setScrollFactor(0)
      .setDepth(100);

    this.repairControlText.on('pointerdown', () => {
      void this.repairMill();
    });

    this.updateRepairControl();

    void this.loadWorldState();
    void this.initializePlayerSession();
  }

  private createCollisionBodies(
    map: Phaser.Tilemaps.Tilemap,
  ): void {
    const collisionLayer = map.getObjectLayer('Collision');

    if (!collisionLayer || collisionLayer.objects.length === 0) {
      throw new Error(
        'Collision object layer is missing or empty',
      );
    }

    const collisionBodies = this.physics.add.staticGroup();

    for (const object of collisionLayer.objects) {
      const { x, y, width, height } = object;
      if (object.rectangle !== true) {
        throw new Error(
          `Unsupported collision shape: ${
            object.name || object.id
          }`,
        );
      }

      if (
        typeof x !== 'number' ||
        typeof y !== 'number' ||
        typeof width !== 'number' ||
        typeof height !== 'number' ||
        !Number.isFinite(x) ||
        !Number.isFinite(y) ||
        !Number.isFinite(width) ||
        !Number.isFinite(height) ||
        width <= 0 ||
        height <= 0
      ) {
        throw new Error(
          `Invalid collision rectangle: ${
            object.name || object.id
          }`,
        );
      }

      if ((object.rotation ?? 0) !== 0) {
        throw new Error(
          `Rotated collision rectangle is unsupported: ${
            object.name || object.id
          }`,
        );
      }

      const scaledWidth = width * TILE_SCALE;
      const scaledHeight = height * TILE_SCALE;

      const centerX =
        x * TILE_SCALE + scaledWidth / 2;
      const centerY =
        y * TILE_SCALE + scaledHeight / 2;

      const collisionZone = this.add.zone(
        centerX,
        centerY,
        scaledWidth,
        scaledHeight,
      );

      collisionBodies.add(collisionZone);
    }

    this.physics.add.collider(
      this.player,
      collisionBodies,
    );
  }

  private createMillVisual(
    map: Phaser.Tilemaps.Tilemap,
  ): void {
    const mill = map
      .getObjectLayer('Collision')
      ?.objects.find(object => object.name === 'mill');

    if (
      !mill ||
      mill.rectangle !== true ||
      typeof mill.x !== 'number' ||
      typeof mill.y !== 'number' ||
      typeof mill.width !== 'number' ||
      typeof mill.height !== 'number' ||
      !Number.isFinite(mill.x) ||
      !Number.isFinite(mill.y) ||
      !Number.isFinite(mill.width) ||
      !Number.isFinite(mill.height) ||
      mill.width <= 0 ||
      mill.height <= 0
    ) {
      throw new Error('Mill map object is missing or invalid');
    }

    const wheelX =
      (mill.x + mill.width - 8) * TILE_SCALE;
    const wheelY =
      (mill.y + mill.height / 2) * TILE_SCALE;

    this.millWheel = this.add.image(
      wheelX,
      wheelY,
      'tiny-dungeon',
      19,
    )
      .setScale(TILE_SCALE)
      .setDepth(11)
      .setVisible(false);

    this.millStateText = this.add.text(
      wheelX,
      wheelY + 20,
      '',
      {
        color: '#ffffff',
        fontSize: '12px',
        backgroundColor: '#000000aa',
        padding: { x: 3, y: 2 },
      },
    )
      .setOrigin(0.5, 0)
      .setDepth(12)
      .setVisible(false);
  }

  private updateMillVisual(): void {
    const status = this.worldSnapshot?.mill_status;
    const hasCanonicalState = status !== undefined;

    this.millWheel.setVisible(hasCanonicalState);
    this.millStateText.setVisible(hasCanonicalState);

    if (status === undefined) return;

    if (status === 'broken') {
      this.millWheel
        .setTint(0x75615b)
        .setAngle(-20);

      this.millStateText
        .setText('MILL: BROKEN')
        .setColor('#ef8b8b');

      return;
    }

    this.millWheel
      .clearTint()
      .setAngle(0);

    this.millStateText
      .setText('MILL: WORKING')
      .setColor('#8ee68e');
  }

  private async loadWorldState(): Promise<void> {
    try {
      const response = await fetch(`${BACKEND_URL}/world`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data: unknown = await response.json();

      if (
        typeof data !== 'object' ||
        data === null ||
        !('revision' in data) ||
        typeof data.revision !== 'number' ||
        !Number.isSafeInteger(data.revision) ||
        data.revision < 0 ||
        !('mill_status' in data) ||
        (
          data.mill_status !== 'broken' &&
          data.mill_status !== 'working'
        )
      ) {
        throw new Error('Invalid world response');
      }

      this.worldSnapshot = {
        revision: data.revision,
        mill_status: data.mill_status,
      };

      this.worldStatusText.setText(
        `Mill: ${this.worldSnapshot.mill_status}` +
        ` | revision ${this.worldSnapshot.revision}`,
      );
    } catch (error) {
      this.worldSnapshot = null;
      this.worldStatusText.setText('World: unavailable');
      console.error('Could not load world state', error);
    } finally {
      this.updateMillVisual();
      this.updateRepairControl();
    }
  }

  private async initializePlayerSession(): Promise<void> {
    this.playerSession = null;
    this.sessionStatusText.setText('Session: connecting...');

    try {
      const response = await fetch(
        `${BACKEND_URL}/sessions`,
        { method: 'POST' },
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data: unknown = await response.json();

      if (
        typeof data !== 'object' ||
        data === null ||
        !('player_id' in data) ||
        typeof data.player_id !== 'string' ||
        data.player_id.trim().length === 0 ||
        !('session_token' in data) ||
        typeof data.session_token !== 'string' ||
        data.session_token.trim().length === 0
      ) {
        throw new Error('Invalid session response');
      }

      this.playerSession = {
        player_id: data.player_id,
        session_token: data.session_token,
      };

      this.sessionStatusText.setText(
        `Player: ${this.playerSession.player_id}`,
      );
    } catch (error) {
      this.playerSession = null;
      this.sessionStatusText.setText('Session: unavailable');
      console.error('Could not initialize player session', error);
    } finally {
      this.updateRepairControl();
    }
  }

  private updateRepairControl(): void {
    this.repairControlText.disableInteractive();

    if (this.repairInFlight) {
      this.repairControlText
        .setText('Repairing mill...')
        .setColor('#aaaaaa');
      return;
    }

    if (this.worldSnapshot?.mill_status === 'working') {
      this.repairControlText
        .setText('Mill already working')
        .setColor('#aaaaaa');
      return;
    }

    if (this.worldSnapshot === null || this.playerSession === null) {
      this.repairControlText
        .setText('Repair unavailable')
        .setColor('#aaaaaa');
      return;
    }

    const label =
      this.pendingRepairCommand === null
        ? '[Repair mill]'
        : '[Retry repair mill]';

    this.repairControlText
      .setText(label)
      .setColor('#ffcf5a')
      .setInteractive({ useHandCursor: true });
  }

  private async repairMill(): Promise<void> {
    if (
      this.repairInFlight ||
      this.worldSnapshot?.mill_status !== 'broken' ||
      this.playerSession === null
    ) {
      return;
    }

    const session = this.playerSession;

    const command = this.pendingRepairCommand ?? {
      command_id: globalThis.crypto.randomUUID(),
      expected_revision: this.worldSnapshot.revision,
    };

    this.pendingRepairCommand = command;
    this.repairInFlight = true;
    this.updateRepairControl();

    try {
      const response = await fetch(
        `${BACKEND_URL}/commands/repair-mill`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${session.session_token}`,
          },
          body: JSON.stringify(command),
        },
      );

      if (response.ok) {
        this.pendingRepairCommand = null;
        await this.loadWorldState();
        return;
      }

      if (response.status >= 400 && response.status < 500) {
        this.pendingRepairCommand = null;

        if (response.status === 401) {
          this.playerSession = null;
          this.sessionStatusText.setText('Session: unavailable');
        }

        await this.loadWorldState();
      }

      throw new Error(`HTTP ${response.status}`);
    } catch (error) {
      console.error('Could not repair mill', error);
    } finally {
      this.repairInFlight = false;
      this.updateRepairControl();
    }
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

    // Always stop the previous frame's velocity first.
    this.player.setVelocity(0, 0);

    // Movement is gated: no walking while reading.
    if (this.dialogueUI) return;

    const speed = 180;
    let velocityX = 0;
    let velocityY = 0;

    if (this.wasd.A.isDown) velocityX -= speed;
    if (this.wasd.D.isDown) velocityX += speed;
    if (this.wasd.W.isDown) velocityY -= speed;
    if (this.wasd.S.isDown) velocityY += speed;

    if (velocityX !== 0 && velocityY !== 0) {
      const diagonalScale = 1 / Math.sqrt(2);
      velocityX *= diagonalScale;
      velocityY *= diagonalScale;
    }

    this.player.setVelocity(velocityX, velocityY);
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

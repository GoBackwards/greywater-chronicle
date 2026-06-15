**# Week 1 — Foundation**

**Goal: Repo scaffolding, playable empty town, end-to-end deployment by Sunday.**

**---**

**## Day 1 — Tuesday**

**Set up the repo with the folder structure (backend, frontend, chronicle, devlog,**

**docs, eval). Locked in the stack: Phaser 3 + TypeScript for the game, FastAPI**

**for the backend, Postgres later, Anthropic Claude for NPC dialogue, Vercel +**

**Render for hosting. Created the GitHub Project board and labeled the first**

**five issues for this week. Wrote the README with a thesis paragraph — surprisingly**

**hard to articulate the project in one paragraph, ended up rewriting it three times.**

**Tomorrow: FastAPI skeleton with a health endpoint and CI on GitHub Actions.**

**---**

**## Day 2**

**setup uv**

deployed FastAPI service with one endpoint, with tests, with CI passing

**## Day 3**

setup frontend (Vite + Phaser) scaffolds

## Day 4

downloaded Kenney Tiny Town tileset, set up public/ asset pipeline, hand-coded first 20×15 town with a manual mapData[][] array

## Day 5

installed Tiled editor, bumped map to 50×25, fixed "External tilesets unsupported" by embedding the tileset and re-exporting

## Day 6

added second tileset (Tiny Dungeon) with multi-tileset createLayer, wired camera scrolling (setBounds + startFollow + setScrollFactor for HUD), replaced placeholder rectangle with character sprite from the tileset
# greywwater-chronicle
  
  An AI-driven persistent world where the consequences of one player's actions reshape the world for everyone who follows.
  
  ## Status
  Week 1 of 8. Building the foundation.
  
  ## What this is
  This project is an idea that exploring the combination of game and AI. I am big fan of the film Ready Player One, animie like Sword Art Online.       Thinking the open world game would be much fun if it has the dynamic storylines, every player is influential in the open world and have their         different individual experience. 
  
  ## How it works
  - **The Chronicle** — a structured event log of everything meaningful that has happened across all expeditions. Each event has typed consequences         that mutate world state.
  - **The Consequence Engine** — a deterministic function from chronicle history to current world state for any zone. Buildings, NPC dispositions,           town flags, all derived from events.
  - **The Narrative Director** *(week 5)* — a hierarchical planner that selects which past events to surface in the current expedition based on             dramatic arc and player choices, then conditions LLM-driven NPC dialogue on the relevant chronicle context.
  
  ## Demo
  Live demo and 90-second video coming week 8.
  
  ## Devlog
  See [devlog/](./devlog/) for weekly progress.

  ## License
  Distributed under the MIT License. See `LICENSE` for more information.

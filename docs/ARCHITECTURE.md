# Discord Game Bot – Architecture & Developer Guide

This document provides an overview of the architecture, features, and extension points of the Discord Game Bot. It is intended for contributors and for tools like GitHub Copilot to understand the codebase and assist with development.

---

## 1. Overview

The bot is a multi-game Discord bot built with `discord.py`. It supports several games, persistent leaderboards, AFK detection, and robust error handling. The main entry point is `bot.py`.

---

## 2. Core Structure

- **bot.py**: Main entry point. Sets up the bot, loads all games, registers commands, handles events, and manages error logging.
- **common/**: Shared modules for configuration, database, commands, and utilities.
- **games/**: Each game is implemented as a separate module with its own commands and logic.

---

## 3. Command System

- **Slash Commands**: All major commands are registered as slash commands using `discord.py`'s `app_commands` and `commands` extensions.
- **Game Commands**: Each game module exposes a `setup_*_command` function to register its commands with the bot.
- **Leaderboard & Help**: Common commands for stats and help are registered from `common/commands/`.
- **Sync Command**: `/sync` (owner only) syncs slash commands with Discord.

---

## 4. Game Modules

Each game is in its own folder under `games/` and follows this pattern:
- `commands_XXXX.py`: Registers commands, handles game logic, and state.
- `game_XXXX.py`, `ui_XXXX.py`, etc.: Contain the core logic and UI helpers.
- Games are referenced by a unique ID (e.g., 1001 for Memory Match).

### Supported Games
- **Memory Match** (1001)
- **Tic Tac Toe** (1002)
- **Rock Paper Scissors** (1003)
- **Action Game** (1004)
- **Counting Game** (1005)
- **Coinflip** (1006)
- **Slots** (1007)
- **Mines** (1008)
- **Currency System** (2000) — Persistent coins, daily/weekly/give/request, and level-based multipliers.

---

## 5. State & Persistence

- **active_games**: A global dictionary tracking active games by game ID and channel.
- **Database**: SQLite (`game_stats.db`) for persistent stats, history, and leaderboards. Managed via `common/database/`.
- **State Persistence**: On shutdown, each game's state is saved using its `persist_all_state` function.

---

## 6. Error Handling & Logging

- All errors are logged to `discord_bot.log` and the console.
- Critical errors are sent to a designated Discord channel (if configured).
- User-facing errors are sent as ephemeral messages.

---

## 7. AFK Detection

- A background task checks for inactive games and ends them if no moves are made within the configured timeout (`AFK_TIMEOUT_SECONDS`).

---

## 8. Challenge & Reaction System

- Challenges are sent as messages with accept/decline reactions.
- The `on_raw_reaction_add` event uses a unified handler to process challenge responses for all games.

---

## 9. Adding a New Game

1. Create a new folder in `games/` as `game_XXXX_gamename/`.
2. Implement the game logic and commands.
3. Expose a `setup_*_command(bot)` function.
4. Register the game in `bot.py` (see `setup_all_games`).
5. Add the game ID to `GAME_IDS` in `common/commands/leaderboard.py`.
6. Update documentation as needed.

---

## 10. Currency & Leveling System (XP)

- **Currency System**: Persistent coins tracked per user/server. Commands: `/bal`, `/give`, `/request`, `/daily`, `/weekly`.
- **Gambling Games**: Coinflip, Slots, and Mines are implemented as separate modules. Each uses the currency system for bets and rewards, and is fully extensible.
- **Leveling System**: Hidden XP/level system. Users earn XP by playing games, using currency commands, and counting. Level affects daily/weekly/counting rewards.
- **Level-based Scaling**: Coin rewards for `/daily`, `/weekly`, and counting are multiplied by a factor based on user level (5% per level above 1).
- **/lvl Command**: Only `/lvl` and help text reveal user level/XP. All other XP/leveling is hidden.
- **Extensible**: System is designed for easy addition of new XP sources, games, and reward scaling.

---

## 11. Key Files & Functions

- `bot.py`: Main event loop, command registration, error handling, AFK checker.
- `common/config/game_config.py`: Bot and game configuration.
- `common/database/`: Database schema and queries.
- `common/utils/`: Utilities for game management, state, and localization.
- `games/game_XXXX_*/`: Game logic and commands.

---

## 12. Useful References

- See `README.md` for user-facing instructions and features.
- See each game's `commands_XXXX.py` for command registration and logic.
- See `common/commands/leaderboard.py` for stats and leaderboard integration.

---

## 13. Contact & Support

For questions, open an issue on GitHub or contact the maintainer via Discord.

---

## 2025-06-10: Major Game Logic and UX Refactor

### Memory Match (game_1001)
- **Card reveal/hide logic moved to game logic**: The delay and hiding of unmatched cards is now handled in `game_1001.py`, not the UI. This ensures the board state is always correct, even if the UI is interrupted or delayed.
- **Joker card handling**: Joker logic and delayed hiding of the non-joker card is now managed by the game logic, with board updates after the delay.
- **Turn switching and state**: Turn switching is robust and always handled in the game logic after a failed match.
- **Game end detection**: All win/tie conditions, including special 4x5 and 5x5 rules, are enforced in the game logic.
- **AFK/game state**: Last activity time is tracked for AFK detection and cleanup.

### Tic Tac Toe (game_1002)
- **Play Again logic unified**: The Play Again button always starts the same mode (classic or endless) as the previous game, and always appears after any game ends.
- **Game end UX**: Both classic and endless modes now show a yellow (gold) embed with a clear result when the game ends.
- **/ttt_end and Play Again**: These work for both modes and always prompt for replay in the correct mode.
- **AFK/game state**: Robust detection and cleanup for all games, including endless Tic Tac Toe.

### Counting Game (game_1005)
- **Anti-cheat improvement**: The anti-cheat message only triggers for user-deleted counting messages, not bot messages.

### General Architecture/UX Patterns
- **Game logic owns all state**: All game state transitions, delays, and win/lose logic are handled in the game logic files, not the UI. The UI only calls game methods and updates the display.
- **UI is stateless**: UI files (e.g., `ui_1001.py`, `ui_1002.py`) do not manage game state or timing. They only reflect the current state from the game logic.
- **AFK/cleanup**: All games now track last activity and can be cleaned up if players go AFK.
- **Database updates**: Game results are always logged to the database at game end.

---

*This file is intended for developers and tools like GitHub Copilot to understand the codebase and assist with contributions.*

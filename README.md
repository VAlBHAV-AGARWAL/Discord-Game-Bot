# Discord Game Bot 🎮

A feature-rich Discord bot that brings multiple interactive games to your server! Challenge your friends to Memory Match, Tic Tac Toe, Rock Paper Scissors, and the new Action Game, all while tracking stats and competing on leaderboards.

## 2025-06-10: Major Game Logic and UX Refactor

### What's New
- **Memory Match (game_1001):** Card reveal/hide delay logic is now in the game logic, not the UI. Joker card handling and turn switching are robust. Game end detection and AFK cleanup improved.
- **Tic Tac Toe (game_1002):** Play Again always starts the correct mode. Game end always shows a gold embed with result. `/ttt_end` and Play Again work for both classic and endless. AFK/game state is robust.
- **Counting Game (game_1005):** Anti-cheat only warns for user-deleted counting messages, not bot messages.
- **General:** All game state, timing, and win/lose logic is handled in the game logic files. UI files are stateless and only update the display. AFK detection and cleanup is robust for all games.

### Upgrading/Using the Bot
- No action needed for existing users. All games now have more reliable state, better anti-cheat, and improved UX.
- For developers: See `docs/ARCHITECTURE.md` for new architecture and UX patterns. All game logic should own state and timing; UI should only reflect state.

## 🎯 Features

### 🎲 Multiple Games
- **Memory Match** (ID: 1001) - Test your memory by matching pairs of emojis
- **Tic Tac Toe** (ID: 1002) - Classic strategy game with a modern Discord twist
- **Rock Paper Scissors** (ID: 1003) - Quick rounds of the timeless hand game
- **Action Game** (ID: 1004) - Engage in exciting action-based challenges (description to be added)
- **Counting Game** (ID: 1005) - Count together in a dedicated channel. Don’t break the sequence! Milestones, cooldown, leaderboard, anti-cheat, and localization included.
- **Coinflip** (ID: 1006) - Gamble your coins on a coin flip. Win or lose your bet instantly!
- **Slots** (ID: 1007) - Spin the slots and try your luck for big multipliers.
- **Mines** (ID: 1008) - Play a Minesweeper-inspired game. Avoid bombs, cash out for bigger rewards!
- **Currency System** - Persistent coins, daily/weekly/give/request, and level-based multipliers.

### 📊 Advanced Features
- **Persistent Leaderboards** - Track wins, losses, and win rates across all games
- **Player Statistics** - Individual and global stats tracking
- **AFK Detection** - Automatic game termination for inactive players
- **Challenge System** - Send and accept game invitations with reactions
- **Error Handling** - Robust error logging and recovery mechanisms
- **Hidden Leveling System** - Earn XP by playing games, using currency commands, and counting. Level up to increase your daily, weekly, and counting rewards! Level and XP are hidden except for `/lvl` and help.
- **Level-based Reward Scaling** - Coin rewards for `/daily`, `/weekly`, and counting are multiplied by your level (5% per level above 1).

### 🛡️ Technical Features
- Slash command support
- Database persistence for stats
- Multi-game state management
- Sharding safety checks
- Comprehensive logging system

## 📋 Prerequisites

- Python 3.8 or higher
- Discord.py 2.0+
- A Discord Bot Token
- SQLite3 (included with Python)

## 🚀 Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/yourusername/discord-game-bot.git
    cd discord-game-bot
    ```

2.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up environment variables**
    Create a `.env` file in the root directory:
    ```env
    DISCORD_BOT_TOKEN=your_bot_token_here
    ```

4.  **Configure the bot (optional)**
    Edit `common/config/game_config.py` to customize:
    - Command prefix
    - AFK timeout duration
    - Emoji reactions and categories (for Memory Match)
    - Other settings

5.  **Run the bot**
    ```bash
    python bot.py
    ```
    *(Note: Your main script is `bot.py`, not `main.py` as previously listed)*

## 📝 Requirements File

Create a `requirements.txt` file with:
```
discord.py>=2.0.0
python-dotenv>=0.19.0
aiofiles>=0.8.0
```

## 🎮 Usage

### Slash Commands

All commands support Discord's slash command interface for better user experience.

#### Game Commands
- `/challenge @user` - Challenge someone to Memory Match
- `/tictactoe @user` - Start a Tic Tac Toe game
- `/rps @user` - Challenge to Rock Paper Scissors
- `/action_game_command @user` - (Example) Start an Action Game (Update with actual command)
- `/counting <#channel>` — Set a channel for the Counting Game
- `/counting reset` — Reset the Counting Game
- `/counting leaderboard` — Show the Counting Game leaderboard
- `/counting stats [@user]` — Show your or another user's Counting Game stats
- `/counting set_cooldown <minutes>` — Set Counting Game cooldown (admin)
- `/counting set_language <lang>` — Set Counting Game language (admin)
- `/coinflip <amount>` — Gamble your coins on a coin flip
- `/slots <amount>` — Spin the slots and win big
- `/mines <amount>` — Play Mines and try to avoid the bombs
- `/suggest <text>` — Suggest a new game or feature

#### Currency Commands
- `/bal [@user]` - Check your (or another user's) coin balance
- `/give @user <amount>` - Give coins to another user
- `/request @user <amount>` - Request coins from another user
- `/daily` - Claim your daily coins reward (level-scaled)
- `/weekly` - Claim your weekly coins reward (level-scaled)

#### Stats Commands
- `/leaderboard [game]` - View top players for a specific game or overall
- `/stats [@user]` - View detailed statistics for yourself or another player

#### Utility Commands
- `/help` - Display help information about the bot and its commands
- `/sync` - (Owner only) Sync slash commands with Discord
- `/lvl [@user]` - Show your (or another user's) level and XP progress

### Playing Games

1.  **Starting a Game**
    - Use the appropriate command and mention your opponent
    - They'll receive a challenge notification with accept/decline reactions
    - Once accepted, the game begins!

2.  **During Gameplay**
    - Follow the on-screen instructions for each game
    - Games have AFK protection - make moves within the timeout period
    - Either player can request to end the game early

3.  **Game Completion**
    - Stats are automatically updated
    - Winners gain points on the leaderboard
    - View your progress with `/stats`

## 🏗️ Project Structure

```
discord-game-bot/
├── bot.py                  # Bot entry point and core logic
├── .env                    # Environment variables (create this)
├── requirements.txt        # Python dependencies
├── game_stats.db           # SQLite database (auto-generated)
├── discord_bot.log         # Bot logs (auto-generated)
│
├── common/                 # Shared modules
│   ├── config/
│   │   └── game_config.py  # Bot and game configuration
│   ├── database/           # Database operations (schema, queries)
│   ├── commands/           # Common commands
│   │   ├── help.py         # Help command
│   │   └── leaderboard.py  # Stats commands
│   └── utils/              # Utility modules
│       ├── game_utils.py   # Game management
│       └── persistent_state.py # State persistence (if any)
│
└── games/                  # Game modules
    ├── game_1001_matching/   # Memory Match
    ├── game_1002_tictactoe/  # Tic Tac Toe
    ├── game_1003_rps/        # Rock Paper Scissors
    └── game_1004_action/     # Action Game
```

## 🔧 Configuration

### Bot Settings (`common/config/game_config.py`)
- `COMMAND_PREFIX`: Default command prefix (for non-slash commands)
- `AFK_TIMEOUT_SECONDS`: Time before inactive games are terminated
- `ACCEPT_EMOJI` / `DECLINE_EMOJI`: Emojis for challenge responses
- `EMOJI_CATEGORIES`: Customizable emoji sets for the Memory Match game.
- Various game-specific settings (e.g., board dimensions, reveal delays).

### Database
The bot uses SQLite for persistent storage (`game_stats.db`). The database is automatically created on first run and includes:
- Player statistics
- Game history
- Leaderboard data

## 🐛 Troubleshooting

### Common Issues

1.  **Bot not responding to commands**
    - Ensure the bot has proper permissions in the channel
    - Check if slash commands are synced (`/sync`)
    - Verify the bot token is correct in `.env`

2.  **Games ending unexpectedly**
    - Check the `AFK_TIMEOUT_SECONDS` setting in `common/config/game_config.py`
    - Ensure players are making moves within the timeout period

3.  **Database errors**
    - The bot will create the database automatically
    - Check file permissions in the bot directory

### Logging
- Logs are saved to `discord_bot.log`
- Console output shows real-time errors
- Critical errors are logged to a designated channel (if configured)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes:

1.  Fork the repository
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

### Adding New Games

To add a new game:
1.  Create a new folder in `games/` following the naming convention `game_XXXX_gamename/`
2.  Implement the game logic and commands within that folder.
3.  Import and register the game's setup function in `bot.py` (see `setup_all_games` function).
4.  If the game has stats, add its ID to `GAME_IDS` in `common/commands/leaderboard.py` and ensure `bot.py` initializes it in `active_games`.
5.  Update this README (Features, Usage/Commands, Project Structure).

## 📄 License

This project is licensed under the MIT License - see the `LICENSE` file for details.

## 🙏 Acknowledgments

- Built with [discord.py](https://github.com/Rapptz/discord.py)
- Inspired by classic games and modern Discord interactions
- Thanks to all contributors and testers

## 📞 Support

If you encounter any issues or have questions:
- Open an issue on GitHub
- Contact the bot developer through Discord
- Check the logs for detailed error information

---

**Note**: This bot requires proper Discord permissions including:
- Send Messages
- Read Message History
- Add Reactions
- Manage Messages
- Use Slash Commands

Make sure to invite the bot with appropriate permissions for the best experience!

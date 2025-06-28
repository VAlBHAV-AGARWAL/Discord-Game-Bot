"""
Help command for the game bot.
"""
import discord
from discord import app_commands, Interaction
from discord.ext import commands
import logging

# Import game IDs from leaderboard
from common.commands.leaderboard import GAME_IDS

logger = logging.getLogger("discord_bot")

class HelpView(discord.ui.View):
    def __init__(self, ctx, command_prefix):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.command_prefix = command_prefix
        self.last_selection = "overview"
    
    @discord.ui.select(
        placeholder="Select game or category",
        options=[
            discord.SelectOption(label="Overview", value="overview", description="General bot overview"),
            discord.SelectOption(label="Memory Match", value="1001", description="Memory Match Game"),
            discord.SelectOption(label="Tic Tac Toe", value="1002", description="Tic Tac Toe Game"),
            discord.SelectOption(label="Rock Paper Scissors", value="1003", description="RPS Game"),
            discord.SelectOption(label="Action Commands", value="1004", description="Anime/Cute Action Commands"),
            discord.SelectOption(label="Counting Game", value="1005", description="Counting Game (Channel-based)")
        ]
    )
    async def help_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle selection of help category."""
        selection = select.values[0]
        self.last_selection = selection
        # Create embed based on selection
        if selection == "overview":
            embed = create_overview_embed(self.command_prefix)
        elif selection == "general":
            embed = create_general_commands_embed(self.command_prefix)
        else:
            embed = create_game_help_embed(selection, self.command_prefix)
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        """Disable the view when it times out."""
        for item in self.children:
            item.disabled = True
        try:
            # Try to update the message with disabled buttons
            message = await self.ctx.fetch_message(self.message.id)
            await message.edit(view=self)
        except:
            pass

def create_overview_embed(command_prefix):
    embed = discord.Embed(
        title="Game Bot Help",
        description=f"Welcome to the Game Bot! This bot lets you play various games with other server members.",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="Available Games",
        value=(
            "• **Memory Match** - Match pairs of cards to win\n"
            "• **Tic Tac Toe** - Classic X and O game\n"
            "• **Rock Paper Scissors** - Classic RPS, challenge a friend\n"
            "• **Action Commands** - Fun anime/cute actions like !slap, !hug, !pat, etc.\n"
            "• **Counting Game** - Count numbers in order in a channel"
        ),
        inline=False
    )
    embed.add_field(
        name="XP, Leveling & Rewards",
        value=(
            "• Earn XP by playing games, using currency commands, and counting.\n"
            "• Level up to increase your daily, weekly, and counting rewards!\n"
            "• Your level is hidden except for `/lvl` and this help.\n"
            "• Use `/lvl` to check your level and XP progress."
        ),
        inline=False
    )
    embed.add_field(
        name="Quick Start",
        value=(
            f"Use `{command_prefix}help` and select a game from the dropdown menu for detailed instructions.\n"
            f"Challenge someone with {command_prefix}matching_game @user or {command_prefix}tic-tac-toe @user"
        ),
        inline=False
    )
    embed.add_field(
        name="Stats & Leaderboards",
        value=(
            f"Check your stats with `{command_prefix}stats`\n"
            f"View leaderboards with `{command_prefix}leaderboard`"
        ),
        inline=False
    )
    embed.set_footer(text="Select a specific game or 'General Commands' from the dropdown for more information")
    return embed

def create_general_commands_embed(command_prefix):
    embed = discord.Embed(
        title="General Commands",
        description="These commands work across all games",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="Leveling & XP System",
        value=(
            "• The bot features a centralized, hidden XP/leveling system.\n"
            "• Earn XP by playing games (including Coinflip, Slots, Mines), using currency commands, and counting.\n"
            "• Level up to increase your daily, weekly, and counting coin rewards (5% per level above 1).\n"
            "• Your level and XP are hidden except for `/lvl` and this help.\n"
            "• Use `/lvl [@user]` to check your (or another user's) level and XP progress."
        ),
        inline=False
    )
    embed.add_field(
        name="Statistics",
        value=(
            f"`{command_prefix}stats [game] [@user]` - Show your or another user's game statistics\n"
            f"• `game` - (Optional) Filter by specific game\n"
            f"• `user` - (Optional) User to show stats for"
        ),
        inline=False
    )
    
    embed.add_field(
        name="Leaderboard",
        value=(
            f"`{command_prefix}leaderboard [scope] [game]` - Show the game leaderboard\n"
            f"• `scope` - (Optional) 'server' or 'global' (default: server)\n"
            f"• `game` - (Optional) Filter by specific game\n"
            f"• Use the pagination buttons to navigate\n"
            f"• Use 'Search Player' to find a specific player"
        ),
        inline=False
    )
    
    embed.add_field(
        name="Help",
        value=(
            f"`{command_prefix}help` - Show this help menu\n"
            f"• Select a game from the dropdown for specific help"
        ),
        inline=False
    )
    
    return embed

def create_game_help_embed(game_id, command_prefix):
    """Create a help embed for a specific game."""
    game_name = GAME_IDS.get(game_id, "Unknown Game")
    embed = None
    if game_id == "1001":  # Memory Match
        embed = discord.Embed(
            title="Memory Match Help",
            description="Match pairs of emojis to win! The player with the most matches wins.",
            color=discord.Color.blue()
        )
        
        # Add game rules
        embed.add_field(
            name="How to Play",
            value=(
                "1. Challenge another user to start a game\n"
                "2. Take turns selecting two cards\n"
                "3. If the cards match, you get a point and another turn\n"
                "4. If they don't match, it's the other player's turn\n"
                "5. The player with more than half of all possible matches wins!\n"
                "6. Watch out for the joker card - it gives you a point but doesn't match with anything!"
            ),
            inline=False
        )
        
        # Add commands
        embed.add_field(
            name="Commands",
            value=(
                f"`{command_prefix}matching_game @user [category] [rows] [cols]` - Challenge someone to a Memory Match game\n"
                f"• `category` - (Optional) Emoji category: food, animals, faces, etc.\n"
                f"• `rows`/`cols` - (Optional) Grid size, e.g. 4 5 for 4x5\n"
                f"`{command_prefix}matching_accept` - Accept a Memory Match challenge\n"
                f"`{command_prefix}matching_decline` - Decline a Memory Match challenge\n"
                f"`{command_prefix}matching_end` - End the current Memory Match game"
            ),
            inline=False
        )
        
    elif game_id == "1002":  # Tic Tac Toe
        embed = discord.Embed(
            title="Tic Tac Toe Help",
            description="Classic X and O game. Get three in a row to win!",
            color=discord.Color.blue()
        )
        
        # Add game rules
        embed.add_field(
            name="How to Play (Classic)",
            value=(
                "1. Challenge another user to start a game\n"
                "2. Players take turns placing their symbol (X or O) on the board\n"
                "3. The first player to get three of their symbols in a row (horizontally, vertically, or diagonally) wins\n"
                "4. If the board fills up with no winner, the game is a draw"
            ),
            inline=False
        )
        embed.add_field(
            name="How to Play (Endless Mode)",
            value=(
                "1. Challenge with `/ttt_endless @user`\n"
                "2. Each player can only have 3 marks on the board at a time\n"
                "3. Placing a new mark removes your oldest mark\n"
                "4. Win by getting three in a row as usual"
            ),
            inline=False
        )
        
        # Add commands
        embed.add_field(
            name="Commands",
            value=(
                f"`{command_prefix}tictactoe @user` - Challenge someone to a Tic Tac Toe game\n"
                f"`{command_prefix}ttt_endless @user` - Challenge someone to Endless Tic Tac Toe\n"
                f"`{command_prefix}ttt_accept` - Accept a Tic Tac Toe challenge\n"
                f"`{command_prefix}ttt_decline` - Decline a Tic Tac Toe challenge\n"
                f"`{command_prefix}ttt_end` - End the current Tic Tac Toe game"
            ),
            inline=False
        )
    
    elif game_id == "1003":  # RPS
        embed = discord.Embed(
            title="Rock Paper Scissors Help",
            description="Challenge a friend to a quick game of RPS!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="How to Play (Classic)",
            value=(
                "1. Challenge another user to start a game\n"
                "2. Both players pick rock, paper, or scissors\n"
                "3. Winner is decided by classic rules (rock > scissors > paper > rock)"
            ),
            inline=False
        )
        embed.add_field(
            name="How to Play (Action Variant)",
            value=(
                "1. Challenge with `/rps_action @user`\n"
                "2. Both players pick an action (e.g. slap, hug, etc.)\n"
                "3. Then play RPS; winner performs their action on the loser with a fun GIF!"
            ),
            inline=False
        )
        embed.add_field(
            name="Commands",
            value=(
                f"`{command_prefix}rps @user` - Challenge someone to RPS\n"
                f"`{command_prefix}rps_action @user` - Challenge someone to Action RPS\n"
                f"`{command_prefix}rps_accept` - Accept an RPS challenge\n"
                f"`{command_prefix}rps_decline` - Decline an RPS challenge\n"
                f"`{command_prefix}rps_end` - End the current RPS game"
            ),
            inline=False
        )
        embed.add_field(
            name="Notes",
            value="• Accept/decline with command or reaction\n• Stats tracked for leaderboard\n• Action RPS lets you perform fun actions if you win!",
            inline=False
        )
        return embed
    elif game_id == "1004":  # Action Game
        embed = discord.Embed(
            title="Action Commands Help",
            description="Fun anime/cute actions like !slap, !hug, !pat, etc.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="How to Use",
            value=(
                "Use the following commands to perform actions on other users.\n" 
                "Example: `!hug @user`\n"
                "You must mention another user."
            ),
            inline=False
        )
        embed.add_field(
            name="Available Actions",
            value=(
                "`cuddle`, `hug`, `kiss`, `kick`, `dance`, `laugh`, `lick`, `nom`, `pat`, `poke`, `slap`, `stare`, `highfive`, `bite`, `greet`, `punch`, `handholding`, `tickle`, `kill`, `hold`, `pats`, `wave`, `boop`, `snuggle`, `bully`"
            ),
            inline=False
        )
        embed.add_field(
            name="Example",
            value="`!pat @user` or `!slap @user`",
            inline=False
        )
        embed.set_footer(text="All action commands use !, not /. Enjoy!")
        return embed
    elif game_id == "1005":  # Counting Game
        embed = discord.Embed(
            title="Counting Game Help",
            description="Count together in a dedicated channel. Don't break the sequence!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="How to Play",
            value=(
                "1. Use `/counting <#channel>` to set a channel for counting.\n"
                "2. In that channel, users must send numbers in order, starting from 1.\n"
                "3. Each user must wait a cooldown (default 15 minutes, configurable) after their last correct number before posting again.\n"
                "4. The bot reacts with ✅ for correct numbers.\n"
                "5. If someone breaks the sequence, posts too soon, or cheats, the bot reacts with ❌, resets the count, and warns.\n"
                "6. Milestones (100, 500, 1000, etc.) are celebrated!\n"
                "7. Special role rewards for milestone achievers.\n"
                "8. Use `/counting leaderboard` and `/counting stats` for stats.\n"
                "9. Use `/counting set_cooldown <minutes>` (admin) to change cooldown.\n"
                "10. Cheating (deleting/editing messages) is detected and warned."
            ),
            inline=False
        )
        embed.add_field(
            name="Commands",
            value=(
                "• `/counting <#channel>` — Set the counting channel.\n"
                "• `/counting reset` — Reset the counting game and clear all defaults.\n"
                "• `/counting leaderboard` — Show the counting leaderboard.\n"
                "• `/counting set_cooldown <minutes>` — Set cooldown (admin only).\n"
                "• `/suggest <text>` — Suggest a new game or feature."
            ),
            inline=False
        )
        embed.add_field(
            name="Anti-Cheat",
            value="Deleting or editing counting messages will be detected and warned.",
            inline=False
        )
        embed.add_field(
            name="Localization",
            value="The bot supports multiple languages (English by default).",
            inline=False
        )
        embed.add_field(
            name="Milestones & Rewards",
            value="Special celebrations and role rewards for milestone numbers!",
            inline=False
        )
        embed.add_field(
            name="XP, Leveling & Reward Scaling",
            value=(
                "• Earn XP by counting, claiming daily/weekly, playing games, and using currency commands.\n"
                "• Level up to increase your daily, weekly, and counting coin rewards!\n"
                "• Your level and XP are hidden except for `/lvl` and this help.\n"
                "• Use `/lvl` to check your level and XP progress."
            ),
            inline=False
        )
    if embed:
        embed.add_field(
            name="Notes",
            value=(
                "• Games timeout after inactivity (where applicable)\n"
                "• Game stats are tracked for the leaderboard (where applicable)"
            ),
            inline=False
        )
    return embed

async def setup_help_command(bot):
    """Set up the help command."""
    @bot.hybrid_command(name="help", description="Show information about available games")
    async def help_cmd(ctx):
        """Show help information about the available games."""
        try:
            view = HelpView(ctx, bot.command_prefix)
            embed = create_overview_embed(bot.command_prefix)
            msg = await ctx.send(embed=embed, view=view)
            view.message = msg
        except Exception as e:
            logger.error(f"Error showing help: {e}")
            await ctx.send("Error showing help. Please try again.")

    return {"help": help_cmd}

# --- KEEP ONLY THIS FOR SLASH COMMANDS ---
class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show all available commands and games.")
    async def help(self, interaction: Interaction):
        embed = discord.Embed(title="Mahiru Matching Game Bot Help", color=discord.Color.blurple())
        embed.add_field(
            name="🎮 Game Commands",
            value=(
                "`/matching` - Play the matching game\n"
                "`/tictactoe` - Play Tic-Tac-Toe\n"
                "`/rps` - Play Rock Paper Scissors\n"
                "`/action` - Play the Action game\n"
                "`/counting` - Set/reset the counting channel\n"
                "`/slots` - Spin the slots and win big!\n"
                "`/coinflip` - Gamble your coins on a coin flip\n"
                "`/mines` - Play the Mines game (Stake/BC.Game style)\n"
            ),
            inline=False
        )
        embed.add_field(
            name="💰 Currency & Leveling",
            value=(
                "`/coins` - Check your coin balance\n"
                "`/give` - Give coins to another user\n"
                "`/request` - Request coins from another user\n"
                "`/daily` - Claim your daily coins reward\n"
                "`/weekly` - Claim your weekly coins reward\n"
                "`/lvl` - Show your level and XP progress\n"
            ),
            inline=False
        )
        embed.add_field(
            name="🏆 Stats & Leaderboards",
            value=(
                "`/leaderboard` - View top players for a specific game or overall\n"
                "`/counting_leaderboard` - Show the counting leaderboard\n"
            ),
            inline=False
        )
        embed.add_field(
            name="🛠️ Utility",
            value=(
                "`/help` - Show this help message\n"
            ),
            inline=False
        )
        embed.set_footer(text="Use /<command> or !<command> for text versions where available. Enjoy the games!")
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
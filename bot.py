"""
Discord Game Bot with support for multiple games.
"""
import os
import asyncio
import discord
import logging
import traceback
import sys
import time
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Custom log formatter that safely handles emojis
class SafeFormatter(logging.Formatter):
    def format(self, record):
        try:
            return super().format(record)
        except UnicodeEncodeError:
            record.msg = str(record.msg).encode('utf-8', 'replace').decode('utf-8')
            if hasattr(record, 'args') and record.args:
                record.args = tuple(
                    str(arg).encode('utf-8', 'replace').decode('utf-8') 
                    if isinstance(arg, str) else arg 
                    for arg in record.args
                )
            return super().format(record)

# Import from common modules
from common.config import (
    COMMAND_PREFIX, AFK_TIMEOUT_SECONDS, 
    ACCEPT_EMOJI, DECLINE_EMOJI
)
from common.database import database
from common.database.database import init_currency, init_leveling
from common.utils.game_utils import active_games
from common.utils.challenge_system import handle_reaction as unified_handle_reaction
from common.commands.leaderboard import setup_leaderboard_commands, GAME_IDS
from common.commands.help import setup_help_command
from common.commands.lvl import setup_level_command
from common.utils.persistent_state import send_critical_error, check_sharding_safety

# Import game modules
# Memory Match Game (ID: 1001)
from games.game_1001_matching.commands_1001 import (
    setup_challenge_command, end_game_internal,
    end_game_confirmations, pending_challenges, persist_all_state as persist_matching_state,
    matching_accept, matching_decline
)

# Tic Tac Toe Game (ID: 1002)
from games.game_1002_tictactoe.commands_1002 import (
    setup_tictactoe_command, end_ttt_game_internal,
    end_ttt_confirmations, persist_all_state as persist_ttt_state,
    ttt_accept, ttt_decline
)

# Rock Paper Scissors Game (ID: 1003)
from games.game_1003_rps.commands_1003 import (
    setup_rps_command, pending_rps_challenges, persist_all_state as persist_rps_state,
    rps_accept, rps_decline
)

# Action Fun Game (ID: 1004)
from games.game_1004_action.commands_1004 import setup_action_commands

# Counting Game (ID: 1005)
from games.game_1005_counting.counting import setup as setup_counting_game

# Currency/Coin Commands (ID: 2000)
from games.game_2000_currency.commands_2000 import setup_currency_commands
from games.game_1006_coinflip.commands_1006 import Coinflip, setup_coinflip_command
from games.game_1007_slots.commands_1007 import Slots, setup_slots_command
from games.game_1008_mines.commands_1008 import Mines, setup_mines_command

# Setup logging
file_handler = logging.FileHandler("discord_bot.log", encoding='utf-8')
console_handler = logging.StreamHandler(sys.stdout)

# Apply the safe formatter to both handlers
formatter = SafeFormatter('%(asctime)s [%(levelname)s] %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logging.basicConfig(
    level=logging.ERROR,  # Only show errors by default, can be changed to INFO
    format='%(asctime)s [%(levelname)s] %(message)s', # This format is overridden by handlers
    handlers=[
        file_handler,
        console_handler
    ]
)
logger = logging.getLogger("discord_bot")

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Setup intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

# Create bot
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

# Error handler
@bot.event
async def on_error(event, *args, **kwargs):
    error_type, error_value, error_traceback = sys.exc_info()
    error_msg = f"Error in {event}: {error_type.__name__}: {error_value}\n"
    error_msg += "".join(traceback.format_tb(error_traceback))
    logger.error(error_msg)
    # Send to critical error log channel
    await send_critical_error(bot, error_msg)
    # If this is during command execution, try to notify the user
    if event == "on_command_error" and args:
        ctx = args[0]
        try:
            await ctx.send(f"An error occurred: {error_type.__name__}. Check logs for details.", delete_after=5.0)
        except:
            pass

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        # Silently ignore unknown commands (no reply to user)
        logger.error(f"CommandNotFound: {error}")
        return
    error_msg = f"Command '{getattr(ctx.command, 'name', None)}' error for {ctx.author} in {getattr(ctx.channel, 'name', None)}: {error}"
    logger.error(error_msg)
    await send_critical_error(bot, error_msg)
    try:
        if isinstance(error, commands.CommandInvokeError):
            await ctx.send(f"Error executing command: {error.original.__class__.__name__}. Check logs for details.", delete_after=5.0)
        else:
            await ctx.send(f"Command error: {error.__class__.__name__}. Check logs for details.", delete_after=5.0)
    except:
        pass

@bot.event
async def on_ready():
    """When the bot is ready."""
    # Initialize database
    database["init_db"]()
    init_currency()  # Initialize coins table
    init_leveling()  # Initialize leveling table
    
    # Start background tasks
    bot.loop.create_task(check_afk_games())
    
    # Log bot info
    app_info = await bot.application_info()
    logger.info(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    logger.info(f"Owner: {app_info.owner}")
    logger.info(f"Discord.py version: {discord.__version__}")
    
    # Set bot status
    game_names = list(GAME_IDS.values())
    status_text = f"{game_names[0]} & {game_names[1]}"
    await bot.change_presence(activity=discord.Game(name=status_text))
    
    print(f"{bot.user.name} is ready!")

async def check_afk_games():
    """Background task to check for AFK players and end inactive games."""
    while not bot.is_closed():
        try:
            current_time = time.time()
            
            # Check Memory Match Games (ID: 1001)
            game_id = "1001"
            channels_to_check = list(active_games[game_id].keys()) if game_id in active_games else []
            for channel_id in channels_to_check:
                game = active_games[game_id].get(channel_id)
                if not game:
                    continue
                
                # Check if the game has been inactive for too long
                if current_time - game.last_activity_time > AFK_TIMEOUT_SECONDS:
                    # Get the channel
                    channel = bot.get_channel(channel_id)
                    if not channel:
                        # Channel no longer exists, remove the game
                        if channel_id in active_games[game_id]:
                            del active_games[game_id][channel_id]
                        continue
                    
                    # End the game due to AFK
                    await end_game_internal(
                        channel, 
                        game, 
                        None, 
                        f"Game ended due to inactivity (no moves for {int(AFK_TIMEOUT_SECONDS/60)} minutes)."
                    )
            
            # Check Tic Tac Toe Games (ID: 1002)
            game_id = "1002"
            channels_to_check = list(active_games[game_id].keys()) if game_id in active_games else []
            for channel_id in channels_to_check:
                game = active_games[game_id].get(channel_id)
                if not game:
                    continue
                
                # Check if the game has been inactive for too long
                if current_time - game.last_activity_time > AFK_TIMEOUT_SECONDS:
                    # Get the channel
                    channel = bot.get_channel(channel_id)
                    if not channel:
                        # Channel no longer exists, remove the game
                        if channel_id in active_games[game_id]:
                            del active_games[game_id][channel_id]
                        continue
                    
                    # End the game due to AFK
                    await end_ttt_game_internal(
                        channel, 
                        game, 
                        None, 
                        f"Game ended due to inactivity (no moves for {int(AFK_TIMEOUT_SECONDS/60)} minutes)."
                    )
            
            # Check Rock Paper Scissors Games (ID: 1003)
            game_id = "1003"
            channels_to_check = list(active_games[game_id].keys()) if game_id in active_games else []
            for channel_id in channels_to_check:
                game = active_games[game_id].get(channel_id)
                if not game:
                    continue
                
                # Check if the game has been inactive for too long
                if current_time - game.last_activity_time > AFK_TIMEOUT_SECONDS:
                    # Get the channel
                    channel = bot.get_channel(channel_id)
                    if not channel:
                        # Channel no longer exists, remove the game
                        if channel_id in active_games[game_id]:
                            del active_games[game_id][channel_id]
                        continue
                    
                    # End the game due to AFK by removing it from active games
                    # No need for special handling as RPS games are stateless between rounds
                    if channel_id in active_games[game_id]:
                        del active_games[game_id][channel_id]
                        await channel.send(f"Rock Paper Scissors game ended due to inactivity (no moves for {int(AFK_TIMEOUT_SECONDS/60)} minutes).")
            
            # Check Endless Tic Tac Toe Games (ID: 1002_endless)
            game_id = "1002_endless"
            channels_to_check = list(active_games[game_id].keys()) if game_id in active_games else []
            for channel_id in channels_to_check:
                game = active_games[game_id].get(channel_id)
                if not game:
                    continue
                if current_time - game.last_activity_time > AFK_TIMEOUT_SECONDS:
                    channel = bot.get_channel(channel_id)
                    if not channel:
                        if channel_id in active_games[game_id]:
                            del active_games[game_id][channel_id]
                        continue
                    # End the endless game due to AFK
                    # Mark as over and remove from active_games
                    game.game_over = True
                    try:
                        await game.update_board("Game ended due to inactivity (no moves for 3 minutes).")
                        if hasattr(game, 'board_message') and game.board_message:
                            await game.board_message.edit(view=None)
                    except Exception:
                        pass
                    del active_games[game_id][channel_id]
                    await channel.send(f"Endless Tic Tac Toe game ended due to inactivity (no moves for 3 minutes).")
            
            # Sleep for a while before checking again (every 10 seconds)
            await asyncio.sleep(10)
        
        except Exception as e:
            logger.error(f"Error in AFK checker: {e}")
            await asyncio.sleep(30)  # Sleep longer on error

# --- Fix for reaction handlers and state serialization ---
# Utility for key parsing (add if not present)
def parse_key(key):
    guild_id, channel_id = key.split(":")
    return int(guild_id) if guild_id != "None" else None, int(channel_id)

@bot.event
async def on_raw_reaction_add(payload):
    """Handle reactions using the unified challenge system."""
    try:
        # Ignore bot's own reactions
        if payload.user_id == bot.user.id:
            return
            
        # Get channel and message
        channel = bot.get_channel(payload.channel_id)
        if not channel:
            return
            
        try:
            message = await channel.fetch_message(payload.message_id)
        except (discord.errors.NotFound, discord.errors.Forbidden):
            return
            
        # Check if this is a bot message
        if message.author.id != bot.user.id:
            return
            
        # Get user
        user = None
        if payload.guild_id:
            guild = bot.get_guild(payload.guild_id)
            if guild:
                user = guild.get_member(payload.user_id)
                if not user:
                    user = await guild.fetch_member(payload.user_id)
        else:
            user = bot.get_user(payload.user_id)
            
        if not user:
            return
            
        # Use unified challenge system to handle the reaction
        emoji = str(payload.emoji)
        await unified_handle_reaction(payload, message, user, emoji)
        
    except Exception as e:
        logger.error(f"Error handling reaction: {e}")

@bot.command(name="sync", description="Sync slash commands with Discord")
@commands.is_owner()
async def sync(ctx):
    """Sync slash commands with Discord."""
    try:
        logger.info("Syncing slash commands...")
        await bot.tree.sync()
        await ctx.send("Slash commands synced successfully!", delete_after=1.0)
        await ctx.message.delete(delay=1.0)
        logger.info("Slash commands synced successfully")
    except Exception as e:
        logger.error(f"Error syncing slash commands: {e}")
        await ctx.send(f"Error syncing slash commands: {e}", delete_after=1.0)

async def setup_all_games():
    """Set up all game modules."""
    # Register the common commands
    leaderboard_commands = await setup_leaderboard_commands(bot)
    help_commands = await setup_help_command(bot)
    # Set up matching game commands (ID: 1001)
    await setup_challenge_command(bot)
    # Set up tic tac toe commands (ID: 1002)
    await setup_tictactoe_command(bot)
    # Set up Rock Paper Scissors commands (ID: 1003)
    await setup_rps_command(bot)
    # Set up Action Fun Game (ID: 1004)
    setup_action_commands(bot)
    # Set up Counting Game (ID: 1005)
    await setup_counting_game(bot)
    # Set up Currency/Coin Commands (ID: 2000)
    await setup_currency_commands(bot)
    # Set up Coinflip (ID: 1006)
    await bot.add_cog(Coinflip(bot))
    # Set up Slots (ID: 1007)
    await bot.add_cog(Slots(bot))
    # Set up Mines (ID: 1008)
    await bot.add_cog(Mines(bot))
    logger.info(f"Registered commands: {', '.join(list(leaderboard_commands.keys()) + list(help_commands.keys()))}")

# Run the bot
async def main():
    """Main entry point."""
    try:
        check_sharding_safety()
        # Initialize active_games dictionary
        for game_id in GAME_IDS:
            active_games[game_id] = {}
        # Setup all games
        await setup_all_games()
        await setup_level_command(bot)
        # Start the bot
        await bot.start(TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot shutdown initiated via keyboard interrupt")
        await bot.close()
    finally:
        # On shutdown, persist all state for all games
        persist_matching_state()
        persist_ttt_state()
        persist_rps_state()
        logger.info("Bot has been shutdown")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot shutdown initiated by user (KeyboardInterrupt)")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        print(f"Unhandled error: {e}")

# --- Permissions Utility ---
def has_permissions(ctx, perms):
    """Check if the bot has the required permissions in the context's channel."""
    if not ctx.guild:
        return True  # DMs, assume allowed
    channel = ctx.channel
    bot_member = ctx.guild.me
    missing = [perm for perm in perms if not getattr(channel.permissions_for(bot_member), perm, False)]
    return missing
async def require_permissions(ctx, perms):
    missing = has_permissions(ctx, perms)
    if missing:
        await ctx.send(f"❌ I am missing the following permissions: {', '.join(missing)}", delete_after=10)
        return False
    return True
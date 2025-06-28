"""
Command handlers for the Memory Match Game (ID: 1001).
"""
import asyncio
import discord
import logging
import uuid
import time
import random
from discord import app_commands
from discord.ext import commands

from common.config import (
    CHALLENGE_TIMEOUT_SECONDS, 
    ACCEPT_EMOJI, DECLINE_EMOJI, EPHEMERAL_MESSAGE_DURATION,
    EMOJI_CATEGORIES
)
from common.database import database
from common.utils.game_utils import (
    active_games,
    update_database_with_game_results
)
from common.utils.challenge_system import (
    create_challenge, 
    register_accept_handler,
    register_decline_handler,
    GameChallenge
)
from games.game_1001_matching.game_1001 import MemoryGame
from games.game_1001_matching.ui_1001 import GameView

logger = logging.getLogger("discord_bot")

# Game-specific storage
GAME_ID = "1001"  # Unique identifier for Memory Match Game
GAME_NAME = "Memory Match"

async def category_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Provide autocomplete suggestions for emoji categories."""
    categories = list(EMOJI_CATEGORIES.keys())
    return [
        app_commands.Choice(name=cat, value=cat)
        for cat in categories if current.lower() in cat.lower()
    ][:25]  # Discord limits to 25 choices

async def accept_memory_match_challenge(challenge: GameChallenge) -> bool:
    """
    Handle accepting a Memory Match challenge.
    
    Args:
        challenge: The GameChallenge object
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if there's already an active game in this channel
        if challenge.channel.id in active_games.get(GAME_ID, {}):
            await challenge.channel.send("There's already an active game in this channel. Finish or end that game first.")
            return False
        
        # Extract game-specific parameters
        category = challenge.extra_params.get('category', 'animals')
        rows = challenge.extra_params.get('rows', 5)
        cols = challenge.extra_params.get('cols', 5)
        bet = challenge.extra_params.get('bet', 0)
        
        # Check acceptor's balance if bet > 0
        if bet > 0:
            from common.database.database import get_balance
            if get_balance(challenge.target.id, challenge.channel.guild.id) < bet:
                await challenge.channel.send(f"{challenge.target.mention} does not have enough coins to accept the bet of {bet}. Please set a reasonable bet.")
                return False
        
        # Create the game
        game = MemoryGame(challenge.challenger, challenge.target, challenge.channel, category, rows, cols)
        game.bet = bet  # Attach bet to game instance
        
        # Make sure the active_games dictionary is initialized for this game ID
        if GAME_ID not in active_games:
            active_games[GAME_ID] = {}
            
        # Store the game
        active_games[GAME_ID][challenge.channel.id] = game
        
        # Create game view
        view = GameView(game)
        
        # Send initial game state
        grid_size_info = f"{cols}x{rows}"
        await challenge.channel.send(
            f"📝 Memory Match Game started: {challenge.challenger.mention} vs {challenge.target.mention} "
            f"with **{category}** emojis | **Grid:** {grid_size_info}\n"
            f"🎲 **{game.current_player.mention} will go first!**"
        )
        
        # Send the main game messages (board and buttons separate)
        try:
            board_message, buttons_message = await view.send_initial_messages(challenge.channel)
        except Exception as e:
            logger.error(f"Error sending initial game messages: {e}")
            await challenge.channel.send("Error displaying the game. Please try starting a new game.")
            # Clean up active game if setup failed critically
            if challenge.channel.id in active_games[GAME_ID]:
                del active_games[GAME_ID][challenge.channel.id]
            return False
        
        logger.info(
            f"Memory Match game started in channel {challenge.channel.id}: "
            f"{challenge.challenger.display_name} vs {challenge.target.display_name} "
            f"with category {category} and grid size {grid_size_info}"
        )
        return True
        
    except Exception as e:
        logger.error(f"Error accepting Memory Match challenge: {e}")
        await challenge.channel.send("Error starting game. Please try again.")
        return False

async def decline_memory_match_challenge(challenge: GameChallenge) -> bool:
    """
    Handle declining a Memory Match challenge.
    
    Args:
        challenge: The GameChallenge object
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create the decline embed
        embed = discord.Embed(
            title="Challenge Declined",
            description=f"{challenge.target.mention} has declined {challenge.challenger.mention}'s Memory Match challenge.",
            color=discord.Color.red()
        )
        
        # Try to edit the original challenge message
        try:
            message = await challenge.channel.fetch_message(challenge.message_id)
            await message.edit(embed=embed)
            await message.clear_reactions()
        except (discord.errors.NotFound, discord.errors.Forbidden):
            # Message might have been deleted or we lack permissions
            # Send a new message instead
            await challenge.channel.send(embed=embed)
            
        logger.info(
            f"Memory Match challenge declined in channel {challenge.channel.id}: "
            f"{challenge.challenger.display_name} -> {challenge.target.display_name}"
        )
        return True
        
    except Exception as e:
        logger.error(f"Error declining Memory Match challenge: {e}")
        await challenge.channel.send("Error declining challenge. Please try again.")
        return False

async def setup_challenge_command(bot):
    """Alias for setup_memory_match_commands to maintain compatibility with bot.py imports."""
    return await setup_memory_match_commands(bot)

async def setup_memory_match_commands(bot):
    """Set up the Memory Match challenge command."""
    # Register handlers with the challenge system
    register_accept_handler(GAME_ID, accept_memory_match_challenge)
    register_decline_handler(GAME_ID, decline_memory_match_challenge)
    # Register matching_accept and matching_decline as prefix commands only
    from .matching_accept_decline import register_accept_decline_commands
    register_accept_decline_commands(bot)
    
    @bot.hybrid_command(
        name="matching_game", 
        description="Challenge another player to a Memory Match game"
    )
    @app_commands.describe(
        user="The user to challenge",
        category="The emoji category to use (faces, animals, food, moon, etc.)",
        grid_size="Optional: Set grid size (default: 5x5, mobile-friendly: 4x5)",
        bet="Optional: Set a coin bet amount"
    )
    @app_commands.choices(grid_size=[
        app_commands.Choice(name="5x5 (Standard)", value="5x5"),
        app_commands.Choice(name="4x5 (Mobile-friendly)", value="4x5")
    ])
    @app_commands.autocomplete(category=category_autocomplete)
    async def challenge(ctx, user: discord.Member, category: str = None, grid_size: str = "5x5", bet: int = 0):
        """Challenge another user to a Memory Match game."""
        await ctx.interaction.response.defer()  # Immediately acknowledge the interaction
        try:            
            # Check if challenging self
            if user.id == ctx.author.id:
                await ctx.send("You can't challenge yourself!")
                return
                
            # Check if challenging a bot
            if user.bot:
                await ctx.send("You can't challenge a bot!")
                return
                
            # Check if there's already an active game in this channel
            if ctx.channel.id in active_games.get(GAME_ID, {}):
                await ctx.send("There's already an active game in this channel. Finish or end that game first.")
                return
                
            # Validate category if provided
            if category and category.lower() not in EMOJI_CATEGORIES:
                available_cats = ", ".join(EMOJI_CATEGORIES.keys())
                await ctx.send(f"Invalid category. Available categories: {available_cats}")
                return
                
            # If no category provided, select random one
            if not category:
                category = random.choice(list(EMOJI_CATEGORIES.keys()))
            
            # Parse grid size
            rows, cols = 5, 5  # Default
            if grid_size == "4x5":
                rows, cols = 5, 4  # 4 columns, 5 rows (mobile-friendly)
            
            # Prepare embed fields
            embed_fields = {
                "📊 Category | 📏 Grid Size": f"{category} | {cols}x{rows}"
            }
            if bet > 0:
                embed_fields["💰 Bet"] = f"{bet} coins (winner takes all)"

            # Send plain challenge message
            await ctx.send(f"{ctx.author.mention} challenges {user.mention}")
            
            # Create challenge with the unified system
            challenge_obj = await create_challenge(
                challenger=ctx.author,
                target=user,
                channel=ctx.channel,
                game_id=GAME_ID,
                game_name=GAME_NAME,
                category=category,
                rows=rows,
                cols=cols,
                embed_fields=embed_fields,
                embed_description=f"{ctx.author.mention} challenges {user.mention} to a game!"
            )
            
            if not challenge_obj:
                # create_challenge already sent an error message
                return
                
            # Store bet in game/session state for later use
            challenge_obj.extra_params['bet'] = bet
            
            logger.info(
                f"Memory Match challenge created in channel {ctx.channel.id}: "
                f"{ctx.author.display_name} -> {user.display_name}"
            )
        
        except Exception as e:
            logger.error(f"Error creating challenge: {e}")
            await ctx.send("Error creating challenge. Please try again.")
        # (No need to send bet as a separate message anymore)

    @bot.hybrid_command(name="matching_end", description="End the current Memory Match game in this channel")
    async def end_game(ctx):
        """End the current Memory Match game in this channel (you will forfeit)."""
        try:
            # Check if there's an active game in this channel
            if ctx.channel.id not in active_games.get(GAME_ID, {}):
                await ctx.send("There's no active Memory Match game in this channel.")
                return
                
            game = active_games[GAME_ID][ctx.channel.id]
            
            # Check if the user is one of the players
            if ctx.author.id != game.player1.id and ctx.author.id != game.player2.id:
                await ctx.send("Only players in the current game can end it.")
                return
            
            # Determine winner (the opponent of the person who forfeited)
            winner = game.player2 if ctx.author.id == game.player1.id else game.player1
            loser = ctx.author
            
            # Mark the game as over
            game.game_over = True

            # Transfer bet to winner if applicable (do this BEFORE sending embed)
            bet = getattr(game, 'bet', 0)
            if bet > 0:
                from common.database.database import add_coins
                add_coins(winner.id, ctx.channel.guild.id, bet * 2)  # Winner receives double the bet amount

            # Create game end embed
            embed = discord.Embed(
                title="\U0001F3F3\uFE0F Game Forfeited!",
                description=f"{loser.mention} has forfeited the game!\n\n\U0001F3C6 **{winner.mention} wins by forfeit!**",
                color=discord.Color.red()
            )

            # Add final scores and bet winnings (if any)
            if bet > 0:
                embed.add_field(
                    name="Final Scores",
                    value=f"{game.player1.display_name}: {game.scores.get(game.player1.id, 0)}\n"
                          f"{game.player2.display_name}: {game.scores.get(game.player2.id, 0)}",
                    inline=True
                )
                embed.add_field(
                    name="Bet Winnings",
                    value=f"\U0001F4B0 {winner.display_name} wins {bet * 2} coins! (Bet: {bet})",
                    inline=True
                )
            else:
                embed.add_field(
                    name="Final Scores",
                    value=f"{game.player1.display_name}: {game.scores.get(game.player1.id, 0)}\n"
                          f"{game.player2.display_name}: {game.scores.get(game.player2.id, 0)}",
                    inline=False
                )

            embed.set_footer(text=f"Game ended by forfeit")

            # Send the game end message
            await ctx.channel.send(embed=embed)

            # Update database with results
            await update_database_with_game_results(
                channel=ctx.channel,
                winner=winner,
                loser=loser,
                game_id=GAME_ID
            )

            # Delete the buttons message if it exists
            if hasattr(game, 'buttons_message') and game.buttons_message:
                try:
                    await game.buttons_message.delete()
                except:
                    pass

            # Update the board to show the final state
            await game.update_board("Game Over - Forfeited")

            # Remove the game from active games
            del active_games[GAME_ID][ctx.channel.id]

            logger.info(f"Memory Match game ended in channel {ctx.channel.id} by forfeit from {loser.display_name}")
            
        except Exception as e:
            logger.error(f"Error processing end game request: {e}")
            await ctx.send("Error ending the game. Please try again.")

    # Register the Memory Match commands with the bot
    return {
        "matching_game": challenge,
        "matching_end": end_game
    }

async def end_memory_match_game_internal(channel, game, ended_by=None, reason="Game ended."):
    """End a Memory Match game and clean up resources.
    
    Args:
        channel: Discord channel where the game is taking place
        game: The MemoryGame instance
        ended_by: The user who ended the game
        reason: The reason the game ended
    """
    try:
        # Check if game exists and isn't already over
        if channel.id not in active_games.get(GAME_ID, {}) or game.game_over:
            return
        
        # Mark the game as over
        game.game_over = True

        # Determine winner by score
        p1_score = game.scores.get(game.player1.id, 0)
        p2_score = game.scores.get(game.player2.id, 0)
        if p1_score > p2_score:
            winner = game.player1
            loser = game.player2
        elif p2_score > p1_score:
            winner = game.player2
            loser = game.player1
        else:
            winner = None  # Tie
            loser = None

        # Transfer bet to winner if applicable (do this BEFORE sending embed)
        bet = getattr(game, 'bet', 0)
        if bet > 0 and winner:
            from common.database.database import add_coins
            add_coins(winner.id, channel.guild.id, bet * 2)

        # Create game end embed
        if winner:
            desc = f"🏆 {winner.display_name} wins! {bet * 2 if bet > 0 else ''}{' Coins given.' if bet > 0 else ''} Final Scores: {game.player1.display_name}={p1_score}, {game.player2.display_name}={p2_score}"
        else:
            desc = f"🏆 Game Over! It's a tie! Final Scores: {game.player1.display_name}={p1_score}, {game.player2.display_name}={p2_score}"
        embed = discord.Embed(
            title="Game Over!",
            description=desc,
            color=discord.Color.gold()
        )
        if bet > 0 and winner:
            embed.add_field(
                name="Bet Winnings",
                value=f"💰 {winner.display_name} wins {bet * 2} coins! (Bet: {bet})",
                inline=False
            )
        elif bet > 0 and not winner:
            embed.add_field(
                name="Bet Refund",
                value=f"It's a tie! Both players are refunded {bet} coins. (Bet: {bet})",
                inline=False
            )
        elif bet > 0:
            embed.add_field(
                name="Bet",
                value=f"Bet: {bet}",
                inline=False
            )
        embed.set_footer(text=reason)

        # Send the game end message
        await channel.send(embed=embed)
        # Update database with results
        from common.database.database import update_database_with_game_results
        await update_database_with_game_results(
            channel=channel,
            winner=winner,
            loser=loser,
            game_id=GAME_ID,
            bet=bet
        )

        # Delete the buttons message if it exists
        if hasattr(game, 'buttons_message') and game.buttons_message:
            try:
                await game.buttons_message.delete()
            except:
                pass
        
        # Update the board to show the final state
        await game.update_board("Game Over - Ended manually")
        
        # Remove the game from active games
        del active_games[GAME_ID][channel.id]
        
        logger.info(f"Memory Match game ended in channel {channel.id}: {reason}")
        
    except Exception as e:
        logger.error(f"Error ending Memory Match game: {e}")
        # Try to remove the game from active games
        try:
            if GAME_ID in active_games and channel.id in active_games[GAME_ID]:
                del active_games[GAME_ID][channel.id]
        except:
            pass 

def persist_all_state():
    """
    Persist all relevant Memory Match game state to disk (stub implementation).
    Extend this to save active games or other state if needed.
    """
    pass

# Fix ImportError for end_game_internal
async def end_game_internal(*args, **kwargs):
    pass

# Fix ImportError for end_game_confirmations
end_game_confirmations = {}

# Import the unified challenge system's pending_challenges
from common.utils.challenge_system import pending_challenges

# Import and re-export matching_accept and matching_decline for bot.py compatibility
from .matching_accept_decline import matching_accept, matching_decline

# Export matching_accept and matching_decline only if they exist in globals
import sys
mod = sys.modules[__name__]
if 'accept_challenge' in globals():
    setattr(mod, 'matching_accept', globals()['accept_challenge'])
if 'decline_challenge' in globals():
    setattr(mod, 'matching_decline', globals()['decline_challenge'])

@app_commands.default_permissions()
class GameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="matching_game", description="Start a Memory Match game with optional coin bet.")
    @app_commands.describe(user="Opponent to challenge", category="Emoji category", grid_size="Grid size (e.g. 4x5, 5x5)", bet="Optional coin bet amount")
    async def matching_game(self, interaction: discord.Interaction, user: discord.Member, category: str, grid_size: str, bet: int = 0):
        await interaction.response.defer()  # Immediately acknowledge the interaction
        from common.database.database import get_balance, remove_coins, add_coins
        challenger = interaction.user
        acceptor = user
        guild_id = interaction.guild.id
        # Validate bet
        if bet < 0:
            await interaction.response.send_message("Bet must be zero or a positive number.", ephemeral=True)
            return
        if bet > 0:
            if get_balance(challenger.id, guild_id) < bet:
                await interaction.response.send_message(f"You don't have enough coins to bet {bet}.", ephemeral=True)
                return
        # Check if challenging self
        if user.id == challenger.id:
            await interaction.response.send_message("You can't challenge yourself!", ephemeral=True)
            return
        # Check if challenging a bot
        if user.bot:
            await interaction.response.send_message("You can't challenge a bot!", ephemeral=True)
            return
        # Check if there's already an active game in this channel
        if interaction.channel.id in active_games.get(GAME_ID, {}):
            await interaction.response.send_message("There's already an active game in this channel. Finish or end that game first.", ephemeral=True)
            return
        # Validate category if provided
        if category and category.lower() not in EMOJI_CATEGORIES:
            available_cats = ", ".join(EMOJI_CATEGORIES.keys())
            await interaction.response.send_message(f"Invalid category. Available categories: {available_cats}", ephemeral=True)
            return
        # If no category provided, select random one
        if not category:
            category = random.choice(list(EMOJI_CATEGORIES.keys()))
        # Parse grid size
        rows, cols = 5, 5  # Default
        if grid_size == "4x5":
            rows, cols = 5, 4  # 4 columns, 5 rows (mobile-friendly)
        # Create challenge with the unified system
        challenge_obj = await create_challenge(
            challenger=challenger,
            target=user,
            channel=interaction.channel,
            game_id=GAME_ID,
            game_name=GAME_NAME,
            category=category,
            rows=rows,
            cols=cols,
            embed_fields={
                "📊 Category | 📏 Grid Size": f"{category} | {cols}x{rows}"
            }
        )
        if not challenge_obj:
            return
        # Store bet in game/session state for later use
        challenge_obj.extra_params['bet'] = bet
        logger.info(
            f"Memory Match challenge created in channel {interaction.channel.id}: "
            f"{challenger.display_name} -> {user.display_name}"
        )
        # Add bet info to challenge embed if bet > 0
        if bet > 0:
            await interaction.followup.send(f"💰 **Bet:** {bet} coins. Winner takes all!", ephemeral=False)

    # In the challenge accept logic (matching_accept):
    # After acceptor accepts, check their balance if bet > 0
    # If not enough, send a message and abort the game, suggest a lower bet
    # ...existing code...

    # In the game forfeit/end logic:
    # If a player forfeits, transfer bet to winner
    # If a player wins, transfer total bet (2x) to winner
    # ...existing code...

    # In end_game and end_memory_match_game_internal, fix bet access:
    # Use getattr(game, 'bet', 0) instead of game.extra_params.get('bet', 0)
    # Show bet and winnings in the embed if bet > 0
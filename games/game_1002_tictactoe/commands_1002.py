"""
Command handlers for the Tic Tac Toe Game (ID: 1002).
"""
import asyncio
import discord
import logging
import uuid
import time
from discord import app_commands
from discord.ext import commands

from common.config import (
    CHALLENGE_TIMEOUT_SECONDS, 
    ACCEPT_EMOJI, DECLINE_EMOJI, EPHEMERAL_MESSAGE_DURATION
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
    GameChallenge,
    accept_challenge as unified_accept_challenge,
    decline_challenge as unified_decline_challenge
)
from games.game_1002_tictactoe.game_1002 import TicTacToeGame
from games.game_1002_tictactoe.ui_1002 import TicTacToeView

logger = logging.getLogger("discord_bot")

# Game-specific storage
GAME_ID = "1002"  # Unique identifier for Tic Tac Toe Game
GAME_NAME = "Tic Tac Toe"

async def accept_tictactoe_challenge(challenge: GameChallenge) -> bool:
    """
    Handle accepting a Tic Tac Toe challenge.
    
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
        # Extract bet from challenge
        bet = challenge.extra_params.get('bet', 0)
        # Check acceptor's balance if bet > 0
        if bet > 0:
            from common.database.database import get_balance
            if get_balance(challenge.target.id, challenge.channel.guild.id) < bet:
                await challenge.channel.send(f"{challenge.target.mention} does not have enough coins to accept the bet of {bet}. Please set a reasonable bet.")
                return False
        # Create the game
        game = TicTacToeGame(challenge.challenger, challenge.target, challenge.channel)
        game.bet = bet  # Attach bet to game instance
        
        # Make sure the active_games dictionary is initialized for this game ID
        if GAME_ID not in active_games:
            active_games[GAME_ID] = {}
            
        # Store the game
        active_games[GAME_ID][challenge.channel.id] = game
        
        # Create game view
        view = TicTacToeView(game)
        
        # Send initial game state
        await challenge.channel.send(f"Tic Tac Toe Game started: {challenge.challenger.mention} vs {challenge.target.mention}")
        board_msg = await challenge.channel.send(embed=game.get_board_embed(), view=view)
        game.board_message = board_msg
        game.board_message_id = board_msg.id
        
        logger.info(
            f"Tic Tac Toe game started in channel {challenge.channel.id}: "
            f"{challenge.challenger.display_name} vs {challenge.target.display_name}"
        )
        return True
        
    except Exception as e:
        logger.error(f"Error accepting Tic Tac Toe challenge: {e}")
        await challenge.channel.send("Error starting game. Please try again.")
        return False

async def decline_tictactoe_challenge(challenge: GameChallenge) -> bool:
    """
    Handle declining a Tic Tac Toe challenge.
    
    Args:
        challenge: The GameChallenge object
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create the decline embed
        embed = discord.Embed(
            title="Challenge Declined",
            description=f"{challenge.target.mention} has declined {challenge.challenger.mention}'s Tic Tac Toe challenge.",
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
            f"Tic Tac Toe challenge declined in channel {challenge.channel.id}: "
            f"{challenge.challenger.display_name} -> {challenge.target.display_name}"
        )
        return True
        
    except Exception as e:
        logger.error(f"Error declining Tic Tac Toe challenge: {e}")
        await challenge.channel.send("Error declining challenge. Please try again.")
        return False

async def setup_tictactoe_command(bot):
    """Set up the Tic Tac Toe challenge command."""
    
    # Register handlers with the challenge system
    register_accept_handler(GAME_ID, accept_tictactoe_challenge)
    register_decline_handler(GAME_ID, decline_tictactoe_challenge)
    # Register endless mode handlers
    async def accept_endless_ttt_challenge(challenge):
        from games.game_1002_tictactoe.game_1002 import EndlessTicTacToeGame
        if "1002_endless" not in active_games:
            active_games["1002_endless"] = {}
        if challenge.channel.id in active_games["1002_endless"]:
            await challenge.channel.send("There's already an active endless game in this channel. Finish or end that game first.")
            return False
        # Extract bet from challenge
        bet = challenge.extra_params.get('bet', 0)
        # Check acceptor's balance if bet > 0
        if bet > 0:
            from common.database.database import get_balance
            if get_balance(challenge.target.id, challenge.channel.guild.id) < bet:
                await challenge.channel.send(f"{challenge.target.mention} does not have enough coins to accept the bet of {bet}. Please set a reasonable bet.")
                return False
        # Create the game
        game = EndlessTicTacToeGame(challenge.challenger, challenge.target, challenge.channel)
        game.bet = bet  # Attach bet to game instance
        
        active_games["1002_endless"][challenge.channel.id] = game
        view = TicTacToeView(game, endless=True)
        await challenge.channel.send(f"Endless Tic Tac Toe started: {challenge.challenger.mention} vs {challenge.target.mention}\nEach player can only have 3 marks on the board at a time. Placing a new mark removes your oldest.")
        board_msg = await challenge.channel.send(embed=game.get_board_embed(), view=view)
        game.board_message = board_msg
        game.board_message_id = board_msg.id
        logger.info(f"Endless Tic Tac Toe game started in channel {challenge.channel.id}: {challenge.challenger.display_name} vs {challenge.target.display_name}")
        return True
    async def decline_endless_ttt_challenge(challenge):
        embed = discord.Embed(
            title="Challenge Declined",
            description=f"{challenge.target.mention} has declined {challenge.challenger.mention}'s Endless Tic Tac Toe challenge.",
            color=discord.Color.red()
        )
        try:
            message = await challenge.channel.fetch_message(challenge.message_id)
            await message.edit(embed=embed)
            await message.clear_reactions()
        except Exception:
            await challenge.channel.send(embed=embed)
        logger.info(f"Endless Tic Tac Toe challenge declined in channel {challenge.channel.id}: {challenge.challenger.display_name} -> {challenge.target.display_name}")
        return True
    register_accept_handler("1002_endless", accept_endless_ttt_challenge)
    register_decline_handler("1002_endless", decline_endless_ttt_challenge)
    
    @bot.hybrid_command(
        name="tictactoe", 
        description="Challenge another player to a Tic Tac Toe game"
    )
    @app_commands.describe(
        user="The user to challenge",
        bet="Optional: Set a coin bet amount"
    )
    async def challenge(ctx, user: discord.Member, bet: int = 0):
        """Challenge another user to a Tic Tac Toe game with optional bet."""
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
            # Validate bet
            if bet < 0:
                await ctx.send("Bet must be zero or a positive number.")
                return
            if bet > 0:
                from common.database.database import get_balance
                if get_balance(ctx.author.id, ctx.guild.id) < bet:
                    await ctx.send(f"You don't have enough coins to bet {bet}.")
                    return

            # Prepare embed fields
            embed_fields = {}
            if bet > 0:
                embed_fields["💰 Bet"] = f"{bet} coins (winner takes all)"

            # Compose the heading and embed in a single message
            heading = f"{ctx.author.mention} challenges {user.mention}"
            embed = discord.Embed(
                title="\u2694\ufe0f Game Challenge! \u2694\ufe0f",
                description=f"\u2728 {ctx.author.mention} challenges {user.mention} to a game! \u2728",
                color=discord.Color.orange()
            )
            embed.add_field(name="\U0001F3AE Game", value="Tic Tac Toe", inline=True)
            embed.add_field(name="\u23F1\ufe0f Timeout", value=f"{CHALLENGE_TIMEOUT_SECONDS} seconds", inline=True)
            embed.add_field(name="\u270F\ufe0f Instructions", value="React with \u2705 to accept or \u274C to decline below.", inline=False)
            if bet > 0:
                embed.add_field(name="\U0001F4B0 Bet", value=f"{bet} coins (winner takes all)", inline=False)
            embed.set_footer(text=f"May the best player win! | Game ID: {GAME_ID}")
            # Send the heading and embed as a reply to the user command
            await ctx.reply(content=heading, embed=embed, mention_author=False)

            # Create challenge with the unified system
            challenge_obj = await create_challenge(
                challenger=ctx.author,
                target=user,
                channel=ctx.channel,
                game_id=GAME_ID,
                game_name=GAME_NAME,
                embed_fields=embed_fields,
                embed_description=f"{ctx.author.mention} challenges {user.mention} to a game!"
            )
            if not challenge_obj:
                return
            challenge_obj.extra_params['bet'] = bet
            logger.info(
                f"Tic Tac Toe challenge created in channel {ctx.channel.id}: "
                f"{ctx.author.display_name} -> {user.display_name}"
            )
        
        except Exception as e:
            logger.error(f"Error creating challenge: {e}")
            await ctx.send("Error creating challenge. Please try again.")

    @bot.command(name="ttt_accept", help="Accept a pending Tic Tac Toe challenge (classic or endless)")
    async def ttt_accept(ctx):
        """Accept a pending Tic Tac Toe challenge (classic or endless)."""
        success = await unified_accept_challenge(ctx, ctx.author)
        if success:
            await ctx.send("Challenge accepted! Game started.", ephemeral=True)

    @bot.command(name="ttt_decline", help="Decline a pending Tic Tac Toe challenge (classic or endless)")
    async def ttt_decline(ctx):
        """Decline a pending Tic Tac Toe challenge (classic or endless)."""
        success = await unified_decline_challenge(ctx, ctx.author)
        if success:
            await ctx.send("Challenge declined.", ephemeral=True)
            
    @bot.hybrid_command(name="ttt_end", description="End the current Tic Tac Toe game in this channel (you will forfeit)")
    async def end_ttt_game(ctx):
        key = ctx.channel.id
        game = None
        game_type = None
        # Check for classic game
        if "1002" in active_games and key in active_games["1002"]:
            game = active_games["1002"][key]
            game_type = "1002"
        # Check for endless game
        elif "1002_endless" in active_games and key in active_games["1002_endless"]:
            game = active_games["1002_endless"][key]
            game_type = "1002_endless"
        if not game:
            await ctx.send("No active Tic Tac Toe game found in this channel.")
            return
        
        # Check if the user is one of the players
        if ctx.author.id != game.player1.id and ctx.author.id != game.player2.id:
            await ctx.send("Only players in the current game can end it.")
            return
        
        # Determine winner (the opponent of the person who forfeited)
        winner = game.player2 if ctx.author.id == game.player1.id else game.player1
        loser = ctx.author
        
        # Mark the game as over
        game.game_over = True
        game.winner = winner  # Set the winner for database update
        
        # Transfer bet to winner if applicable (do this BEFORE sending embed)
        bet = getattr(game, 'bet', 0)
        if bet > 0:
            from common.database.database import add_coins
            add_coins(winner.id, ctx.channel.guild.id, bet * 2)
        
        # Create the forfeit embed with the requested format
        board_display = game._get_board_display()
        
        embed = discord.Embed(
            title="Tic Tac Toe - Game Over!",
            description=board_display,
            color=discord.Color.red()
        )
        
        # Add player information
        embed.add_field(
            name="Players",
            value=f"{game.player1.display_name}: {game.symbols[game.player1.id]}\n{game.player2.display_name}: {game.symbols[game.player2.id]}",
            inline=False
        )
        
        # Add result
        embed.add_field(
            name="Result",
            value=f"Won by {winner.display_name} by default",
            inline=False
        )
        
        # Add reason
        embed.add_field(
            name="Reason",
            value=f"• {loser.display_name} Forfitted",
            inline=False
        )
        
        # Add bet information if there was a bet
        if bet > 0:
            embed.add_field(
                name="Bet Winnings",
                value=f"Bet amount {bet} coins won by {winner.display_name}",
                inline=False
            )
        
        # Send the forfeit message
        await ctx.channel.send(embed=embed)
        
        # Delete the game board message if it exists
        if hasattr(game, 'board_message') and game.board_message:
            try:
                await game.board_message.delete()
            except:
                pass
        
        # Remove the game from active_games
        del active_games[game_type][key]
        
        # Update database with results
        await update_database_with_game_results(
            channel=ctx.channel,
            winner=winner,
            loser=loser,
            game_id=GAME_ID,
            bet=bet
        )
    
    @bot.hybrid_command(
        name="ttt_endless", 
        description="Start an endless Tic Tac Toe game (3-move limit per player, oldest mark removed)"
    )
    @app_commands.describe(
        user="The user to challenge",
        bet="Optional: Set a coin bet amount"
    )
    async def ttt_endless(ctx, user: discord.Member, bet: int = 0):
        """Start an endless Tic Tac Toe game (3-move limit per player, oldest mark removed) with optional bet."""
        try:
            # Check if challenging self
            if user.id == ctx.author.id:
                await ctx.send("You can't challenge yourself to an endless game!")
                return
            # Check if challenging a bot
            if user.bot:
                await ctx.send("You can't challenge a bot to an endless game!")
                return
            # Check if there's already an active endless game in this channel
            if ctx.channel.id in active_games.get("1002_endless", {}):
                await ctx.send("There's already an active endless game in this channel. Finish or end that game first.")
                return
            # Validate bet
            if bet < 0:
                await ctx.send("Bet must be zero or a positive number.")
                return
            if bet > 0:
                from common.database.database import get_balance
                if get_balance(ctx.author.id, ctx.guild.id) < bet:
                    await ctx.send(f"You don't have enough coins to bet {bet}.")
                    return

            # Prepare embed fields
            embed_fields = {}
            if bet > 0:
                embed_fields["💰 Bet"] = f"{bet} coins (winner takes all)"
            # Create challenge with the unified system, mark as endless
            challenge_obj = await create_challenge(
                challenger=ctx.author,
                target=user,
                channel=ctx.channel,
                game_id="1002_endless",
                game_name=GAME_NAME,
                endless=True,
                embed_fields=embed_fields,
                embed_description=f"{ctx.author.mention} challenges {user.mention} to an endless game!"
            )
            if not challenge_obj:
                return
            challenge_obj.extra_params['bet'] = bet
            logger.info(
                f"Endless Tic Tac Toe challenge created in channel {ctx.channel.id}: "
                f"{ctx.author.display_name} -> {user.display_name}"
            )
        except Exception as e:
            logger.error(f"Error creating endless challenge: {e}")
            await ctx.send("Error creating endless challenge. Please try again.")

    # Register the Tic Tac Toe commands with the bot
    return {
        "tictactoe": challenge,
        "ttt_accept": ttt_accept,
        "ttt_decline": ttt_decline,
        "ttt_end": end_ttt_game,
        "ttt_endless": ttt_endless
    }

async def end_ttt_game_internal(channel, game, ended_by=None, reason="Game ended.", forfeit=False):
    """End a Tic Tac Toe game and clean up resources.
    
    Args:
        channel: Discord channel where the game is taking place
        game: The TicTacToeGame instance
        ended_by: The user who ended the game
        reason: The reason the game ended
        forfeit: Whether this is a forfeit (ended_by forfeits to the other player)
    """
    try:
        # Mark the game as over
        game.game_over = True
        # Remove from active_games
        game_id = "1002_endless" if hasattr(game, 'moves') and hasattr(game, 'turn') else "1002"
        if game_id in active_games and channel.id in active_games[game_id]:
            del active_games[game_id][channel.id]
        
        # Determine winner and loser for forfeit
        winner = None
        loser = None
        if forfeit and ended_by:
            winner = game.player2 if ended_by.id == game.player1.id else game.player1
            loser = ended_by
            game.winner = winner  # Set the winner for database update
        else:
            winner = getattr(game, 'winner', None)
            loser = (game.player2 if winner == game.player1 else game.player1) if winner else None
        
        # Transfer bet to winner if applicable (do this BEFORE sending embed)
        bet = getattr(game, 'bet', 0)
        from common.database.database import add_coins
        if bet > 0 and winner:
            add_coins(winner.id, channel.guild.id, bet * 2)
        # Refund bet to both players if tie
        refund_text = None
        if bet > 0 and not winner:
            add_coins(game.player1.id, channel.guild.id, bet)
            add_coins(game.player2.id, channel.guild.id, bet)
            refund_text = f"Both players are refunded {bet} coins."
        
        if forfeit:
            # Create forfeit embed with the requested format
            board_display = game._get_board_display()
            
            embed = discord.Embed(
                title="Tic Tac Toe - Game Over!",
                description=board_display,
                color=discord.Color.red()
            )
            
            # Add player information
            embed.add_field(
                name="Players",
                value=f"{game.player1.display_name}: {game.symbols[game.player1.id]}\n{game.player2.display_name}: {game.symbols[game.player2.id]}",
                inline=False
            )
            
            # Add result
            embed.add_field(
                name="Result",
                value=f"Won by {winner.display_name} by default",
                inline=False
            )
            
            # Add reason
            embed.add_field(
                name="Reason",
                value=f"• {loser.display_name} Forfitted",
                inline=False
            )
            
            # Add bet information if there was a bet
            if bet > 0:
                embed.add_field(
                    name="Bet Winnings",
                    value=f"Bet amount {bet} coins won by {winner.display_name}",
                    inline=False
                )
            
            # Delete the game board message if it exists
            if hasattr(game, 'board_message') and game.board_message:
                try:
                    await game.board_message.delete()
                except:
                    pass
        else:
            # Create regular game end embed (yellow)
            embed = game.get_board_embed()
            embed.color = discord.Color.gold()
            embed.title = embed.title.split('-')[0].strip() + " - Game Over!"
            embed.add_field(name="Reason", value=f"• {reason}", inline=True)
            if winner:
                embed.add_field(name="Result", value=f"• 🏆 {winner.mention} wins!")
                if bet > 0:
                    embed.add_field(name="Bet Winnings", value=f"💰 {winner.display_name} wins {bet * 2} coins!", inline=False)
            else:
                embed.add_field(name="Result", value=f"• 🤝 It's a draw!")
                if refund_text:
                    embed.add_field(name="Bet Refund", value=f"{refund_text}", inline=False)
            if ended_by:
                embed.set_footer(text=f"Game ended by {ended_by.display_name}")
            
            # Update the board to show final state
            try:
                from games.game_1002_tictactoe.ui_1002 import TicTacToeView, PlayAgainButton
                await game.update_board("Game Over!")
                # Show Play Again button for correct mode
                play_again_view = discord.ui.View()
                endless = game_id == "1002_endless"
                play_again_view.add_item(PlayAgainButton(game.player1, game.player2, endless=endless))
                # Add Play Again with Bet button if there was a bet
                if bet > 0:
                    class PlayAgainWithBetButton(discord.ui.Button):
                        def __init__(self, player1, player2, bet, endless=False):
                            super().__init__(label=f"Play Again with Bet ({bet})", style=discord.ButtonStyle.success)
                            self.player1 = player1
                            self.player2 = player2
                            self.bet = bet
                            self.endless = endless
                        async def callback(self, interaction: discord.Interaction):
                            if interaction.user.id not in [self.player1.id, self.player2.id]:
                                await interaction.response.send_message("Only the original players can start a new game.", ephemeral=True)
                                return
                            # Check both players' balances
                            from common.database.database import get_balance
                            guild_id = interaction.guild.id if interaction.guild else 0
                            if get_balance(self.player1.id, guild_id) < self.bet or get_balance(self.player2.id, guild_id) < self.bet:
                                await interaction.response.send_message("Both players must have enough coins to play again with the same bet.", ephemeral=True)
                                return
                            # Start a new game with the same bet
                            if self.endless:
                                from games.game_1002_tictactoe.game_1002 import EndlessTicTacToeGame
                                new_game = EndlessTicTacToeGame(self.player1, self.player2, interaction.channel)
                                new_game.bet = self.bet
                                if "1002_endless" not in active_games:
                                    active_games["1002_endless"] = {}
                                active_games["1002_endless"][interaction.channel.id] = new_game
                                view = TicTacToeView(new_game, endless=True)
                                await interaction.channel.send(f"Endless Tic Tac Toe started: {self.player1.mention} vs {self.player2.mention}\nEach player can only have 3 marks on the board at a time. Placing a new mark removes your oldest.")
                                board_msg = await interaction.channel.send(embed=new_game.get_board_embed(), view=view)
                                new_game.board_message = board_msg
                                new_game.board_message_id = board_msg.id
                            else:
                                from games.game_1002_tictactoe.game_1002 import TicTacToeGame
                                new_game = TicTacToeGame(self.player1, self.player2, interaction.channel)
                                new_game.bet = self.bet
                                if "1002" not in active_games:
                                    active_games["1002"] = {}
                                active_games["1002"][interaction.channel.id] = new_game
                                view = TicTacToeView(new_game)
                                await interaction.channel.send(f"Tic Tac Toe Game started: {self.player1.mention} vs {self.player2.mention}")
                                board_msg = await interaction.channel.send(embed=new_game.get_board_embed(), view=view)
                                new_game.board_message = board_msg
                                new_game.board_message_id = board_msg.id
                            await interaction.response.defer()
                    play_again_view.add_item(PlayAgainWithBetButton(game.player1, game.player2, bet, endless=endless))
                await channel.send(content="Want to play again?", view=play_again_view)
                if hasattr(game, 'board_message') and game.board_message:
                    await game.board_message.edit(view=None)
            except Exception:
                pass
        
        # Send the game end message
        await channel.send(embed=embed)
        
        # Update database with results (add this after sending the embed)
        await update_database_with_game_results(
            channel=channel,
            winner=winner,
            loser=loser,
            game_id=GAME_ID,
            bet=bet
        )
    except Exception as e:
        logger.error(f"Error ending Tic Tac Toe game: {e}")
        try:
            if "1002" in active_games and channel.id in active_games["1002"]:
                del active_games["1002"][channel.id]
            if "1002_endless" in active_games and channel.id in active_games["1002_endless"]:
                del active_games["1002_endless"][channel.id]
        except:
            pass

# Fix ImportError for end_ttt_confirmations
end_ttt_confirmations = {}

def persist_all_state():
    """
    Persist all relevant Tic Tac Toe game state to disk (stub implementation).
    Extend this to save active games or other state if needed.
    """
    pass

# Export ttt_accept and ttt_decline for bot.py compatibility
import types

def get_ttt_accept_decline():
    async def ttt_accept(ctx):
        success = await unified_accept_challenge(ctx, ctx.author)
        if success:
            await ctx.send("Challenge accepted! Game started.", ephemeral=True)
    async def ttt_decline(ctx):
        success = await unified_decline_challenge(ctx, ctx.author)
        if success:
            await ctx.send("Challenge declined.", ephemeral=True)
    return ttt_accept, ttt_decline

ttt_accept, ttt_decline = get_ttt_accept_decline()
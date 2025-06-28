"""
Command handlers for the Rock Paper Scissors Games (ID: 1003).
"""
import asyncio
import discord
import logging
import uuid
import time
from discord import app_commands
from discord.ext import commands
import aiohttp
import traceback

from common.config import (
    CHALLENGE_TIMEOUT_SECONDS,
    ACCEPT_EMOJI, DECLINE_EMOJI, EPHEMERAL_MESSAGE_DURATION
)
from common.database import database
from common.utils.game_utils import (
    active_games, handle_challenge_expiration,
    generate_confirmation_id, handle_confirmation_expiration
)
from common.utils.persistent_state import save_state, load_state
from games.game_1003_rps.game_1003 import BasicRPSGame, ActionRPSGame, RPS_EMOJIS
from games.game_1003_rps.ui_1003 import RPSView, ActionSelectView, PlayAgainButton, PlayAgainWithBetButton

from common.utils.challenge_system import (
    create_challenge as unified_create_challenge,
    register_accept_handler,
    register_decline_handler,
    GameChallenge,
    accept_challenge as unified_accept_challenge,
    decline_challenge as unified_decline_challenge
)

logger = logging.getLogger("discord_bot")

# Game-specific storage
GAME_ID = "1003"  # Unique identifier for RPS Games

# Define game types
BASIC_GAME_TYPE = "basic"  # Regular RPS
ACTION_GAME_TYPE = "action"  # RPS with actions

# Track challenges
pending_rps_challenges = None

async def accept_rps_challenge(challenge: GameChallenge) -> bool:
    """Handle accepting an RPS challenge, including bet validation and deduction."""
    try:
        from common.database.database import get_balance, remove_coins
        game_type = challenge.extra_params.get('game_type', BASIC_GAME_TYPE)
        bet = challenge.extra_params.get('bet', 0)
        guild_id = challenge.channel.guild.id if hasattr(challenge.channel, 'guild') and challenge.channel.guild else 0
        # Check acceptor's balance if bet > 0
        if bet > 0:
            if get_balance(challenge.target.id, guild_id) < bet:
                await challenge.channel.send(f"{challenge.target.mention} does not have enough coins to accept the bet of {bet}. Please set a reasonable bet.")
                return False
            if get_balance(challenge.challenger.id, guild_id) < bet:
                await challenge.channel.send(f"{challenge.challenger.mention} does not have enough coins to cover their bet. Challenge cancelled.")
                return False
            # Deduct bet from both players
            if not remove_coins(challenge.challenger.id, guild_id, bet):
                await challenge.channel.send(f"{challenge.challenger.mention} could not pay the bet. Challenge cancelled.")
                return False
            if not remove_coins(challenge.target.id, guild_id, bet):
                # Refund challenger if acceptor fails
                from common.database.database import add_coins
                add_coins(challenge.challenger.id, guild_id, bet)
                await challenge.channel.send(f"{challenge.target.mention} could not pay the bet. Challenge cancelled.")
                return False
        # Start the appropriate game
        if game_type == BASIC_GAME_TYPE:
            await start_basic_rps(challenge.channel, challenge.challenger, challenge.target)
            # Attach bet to game instance
            game = active_games[GAME_ID][challenge.channel.id]
            game.bet = bet
        else:
            await start_action_rps(challenge.channel, challenge.challenger, challenge.target)
            game = active_games[GAME_ID][challenge.channel.id]
            game.bet = bet
        logger.info(f"RPS game started: {challenge.challenger.display_name} vs {challenge.target.display_name} (bet={bet})")
        return True
    except Exception as e:
        logger.error(f"Error accepting RPS challenge: {e}")
        await challenge.channel.send("Error starting game. Please try again.")
        return False

async def decline_rps_challenge(challenge: GameChallenge) -> bool:
    """Handle declining an RPS challenge."""
    try:
        embed = discord.Embed(
            title="Challenge Declined",
            description=f"{challenge.target.mention} has declined {challenge.challenger.mention}'s Rock Paper Scissors challenge.",
            color=discord.Color.red()
        )
        
        try:
            message = await challenge.channel.fetch_message(challenge.message_id)
            await message.edit(embed=embed)
            await message.clear_reactions()
        except:
            await challenge.channel.send(embed=embed)
            
        logger.info(f"RPS challenge declined: {challenge.challenger.display_name} -> {challenge.target.display_name}")
        return True
    except Exception as e:
        logger.error(f"Error declining RPS challenge: {e}")
        return False

async def setup_rps_command(bot):
    """Set up both RPS game commands."""
    
    # Register handlers with the challenge system
    register_accept_handler(GAME_ID, accept_rps_challenge)
    register_decline_handler(GAME_ID, decline_rps_challenge)
    register_accept_handler(f"{GAME_ID}_action", accept_rps_challenge)
    register_decline_handler(f"{GAME_ID}_action", decline_rps_challenge)

    #---------- Basic RPS Command ----------#
    @bot.hybrid_command(
        name="rps",
        description="Challenge another player to Rock Paper Scissors"
    )
    @app_commands.describe(
        user="The user to challenge",
        bet="Optional: Set a coin bet amount"
    )
    async def rps_challenge(ctx, user: discord.Member, bet: int = 0):
        """Challenge another user to a basic Rock Paper Scissors game with optional bet."""
        await create_challenge(ctx, user, BASIC_GAME_TYPE, bet=bet)
        
    #---------- Action RPS Command ----------#
    @bot.hybrid_command(
        name="rps_action",
        description="Challenge another player to Rock Paper Scissors Action"
    )
    @app_commands.describe(
        user="The user to challenge",
        bet="Optional: Set a coin bet amount"
    )
    async def rps_action_challenge(ctx, user: discord.Member, bet: int = 0):
        """Challenge another user to a Rock Paper Scissors Action game with optional bet."""
        await create_challenge(ctx, user, ACTION_GAME_TYPE, bet=bet)

    @bot.command(name="rps_accept", help="Accept a pending Rock Paper Scissors challenge")
    async def rps_accept(ctx):
        """Accept a pending RPS challenge."""
        success = await unified_accept_challenge(ctx, ctx.author)
        if success:
            await ctx.send("Challenge accepted!", ephemeral=True)

    @bot.command(name="rps_decline", help="Decline a pending Rock Paper Scissors challenge")
    async def rps_decline(ctx):
        """Decline a pending RPS challenge."""
        success = await unified_decline_challenge(ctx, ctx.author)
        if success:
            await ctx.send("Challenge declined.", ephemeral=True)

    @bot.hybrid_command(
        name="rps_end", 
        description="End the current Rock Paper Scissors game in this channel"
    )
    async def rps_end(ctx):
        try:
            key = ctx.channel.id
            game_state = active_games.get(GAME_ID, {}).get(key)
            if not game_state:
                await ctx.send("There's no active Rock Paper Scissors game in this channel.")
                return
            if ctx.author.id not in [game_state.player1.id, game_state.player2.id]:
                await ctx.send("Only players in the current game can end it.")
                return
            # Forfeit confirmation button
            class ForfeitView(discord.ui.View):
                def __init__(self, author_id, timeout=60):
                    super().__init__(timeout=timeout)
                    self.author_id = author_id
                    self.value = None
                @discord.ui.button(label="Forfeit and End Game", style=discord.ButtonStyle.danger)
                async def forfeit(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != self.author_id:
                        await interaction.response.send_message("Only the player who requested to end can confirm.", ephemeral=True)
                        return
                    await interaction.response.defer()
                    self.value = True
                    self.stop()
            
            view = ForfeitView(ctx.author.id)
            msg = await ctx.send(f"{ctx.author.mention}, are you sure you want to forfeit and end the game? You will lose.", view=view)
            timeout = await view.wait()
            if not view.value:
                await msg.edit(content="Game end cancelled.", view=None)
                return
            
            player1_id = game_state.player1.id
            player2_id = game_state.player2.id
            loser_id = ctx.author.id
            winner_id = player2_id if loser_id == player1_id else player1_id
            winner = await ctx.bot.fetch_user(winner_id)
            loser = await ctx.bot.fetch_user(loser_id)
            bet = getattr(game_state, 'bet', 0)
            from common.database.database import add_coins
            if bet > 0:
                add_coins(winner.id, ctx.guild.id, bet * 2)
            embed = discord.Embed(
                title="Rock Paper Scissors Game Forfeited",
                description=f"{loser.mention} has forfeited. {winner.mention} wins!",
                color=discord.Color.red()
            )
            if bet > 0:
                embed.add_field(
                    name="Bet Winnings",
                    value=f"💰 {winner.display_name} wins {bet * 2} coins!",
                    inline=False
                )
            await ctx.send(embed=embed)
            if key in active_games.get(GAME_ID, {}):
                del active_games[GAME_ID][key]
            persist_all_state()
            # Update database with results (add this after sending the embed)
            from common.database.database import update_database_with_game_results
            await update_database_with_game_results(
                channel=game_state.channel,
                winner=game_state.winner if hasattr(game_state, 'winner') else None,
                loser=(game_state.player2 if game_state.winner == game_state.player1 else game_state.player1) if game_state.winner else None,
                game_id=GAME_ID,
                bet=bet
            )
            logger.info(f"RPS game forfeited in channel {ctx.channel.id}: {loser.display_name} forfeited, {winner.display_name} wins.")
        except Exception as e:
            logger.error(f"Error processing forfeit end game: {e}")
            await ctx.send("Error processing end game request. Please try again.")

#---------- Shared Command Functions ----------#
async def create_challenge(ctx, user, game_type, bet: int = 0):
    """Create a challenge for either RPS game type, with optional bet."""
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
            await ctx.send("There's already an active game in this channel. Finish that game first.")
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
        # Format game type for display
        display_game_type = "Rock Paper Scissors" if game_type == BASIC_GAME_TYPE else "Rock Paper Scissors Action"
        # Prepare embed fields
        embed_fields = {"🎯 Game Type": display_game_type}
        if bet > 0:
            embed_fields["💰 Bet"] = f"{bet} coins (winner takes all)"
        # Send the plain challenge message first
        await ctx.send(f"{ctx.author.mention} challenges {user.mention}")
        # Use unified challenge system
        challenge_obj = await unified_create_challenge(
            challenger=ctx.author,
            target=user,
            channel=ctx.channel,
            game_id=GAME_ID if game_type == BASIC_GAME_TYPE else f"{GAME_ID}_action",
            game_name=display_game_type,
            game_type=game_type,
            embed_fields=embed_fields
        )
        if not challenge_obj:
            return
        challenge_obj.extra_params['bet'] = bet
        logger.info(f"RPS challenge created: {ctx.author.display_name} -> {user.display_name}")
    except Exception as e:
        logger.error(f"Error creating RPS challenge: {e}")
        await ctx.send("Error creating challenge. Please try again.")

#---------- Game Starter Functions ----------#

async def start_basic_rps(channel, player1, player2):
    """Start a basic Rock Paper Scissors game."""
    # Create the game instance
    game = BasicRPSGame(player1, player2, channel)
    
    # Store in active games
    if GAME_ID not in active_games:
        active_games[GAME_ID] = {}
    active_games[GAME_ID][channel.id] = game
    persist_all_state()
    
    # Send game start message
    start_message = await channel.send(f"🎮 Rock Paper Scissors started: {player1.mention} vs {player2.mention}")
    
    # Send private prompts to both players using buttons on a public message
    view = StartRPSView(game)
    choice_message = await channel.send(
        f"**{player1.mention}** and **{player2.mention}**, click the button below to make your choice!",
        view=view
    )
    
    # Store the message ID for later deletion
    game.choice_message = choice_message
    
    logger.info(f"Basic RPS game started in channel {channel.id}: {player1.display_name} vs {player2.display_name}")

async def start_action_rps(channel, player1, player2):
    """Start a Rock Paper Scissors Action game."""
    # Create the game instance
    game = ActionRPSGame(player1, player2, channel)
    
    # Store in active games
    if GAME_ID not in active_games:
        active_games[GAME_ID] = {}
    active_games[GAME_ID][channel.id] = game
    persist_all_state()
    
    # Send game start message
    game.start_message = await channel.send(f"🎮 Rock Paper Scissors Action started: {player1.mention} vs {player2.mention}")
    
    # First send action selection messages to both players using buttons on a public message
    view = StartActionRPSView(game)
    action_message = await channel.send(
        f"**{player1.mention}** and **{player2.mention}**, click the button below to choose your action!",
        view=view
    )
    
    # Store the message ID for later deletion
    game.action_message = action_message
    
    logger.info(f"Action RPS game started in channel {channel.id}: {player1.display_name} vs {player2.display_name}")

# Add these new view classes to handle interaction-based prompts

class StartRPSView(discord.ui.View):
    """View with buttons for players to start their turns."""
    def __init__(self, game):
        super().__init__(timeout=180)  # 3 minute timeout
        self.game = game
        
    @discord.ui.button(label="Make Your Choice", style=discord.ButtonStyle.primary)
    async def choose_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button that players click to make their choice."""
        try:
            # Check if this is one of the players
            if interaction.user.id not in [self.game.player1.id, self.game.player2.id]:
                await interaction.response.send_message("You are not part of this game!", ephemeral=True)
                return
                
            # Check if they've already made a choice
            if self.game.choices[interaction.user.id] is not None:
                await interaction.response.send_message("You've already made your choice!", ephemeral=True)
                return
                
            # Create the RPS view for this player
            async def on_choice_made(choice_interaction, choice):
                # Check if both players have now chosen
                if self.game.is_complete():
                    # Delete the choice message if both players have made their choices
                    if hasattr(self.game, 'choice_message') and self.game.choice_message:
                        try:
                            await self.game.choice_message.delete()
                            self.game.choice_message = None
                        except:
                            logger.warning("Failed to delete choice message")
                    
                    # Delete the action message in action RPS game
                    if isinstance(self.game, ActionRPSGame) and hasattr(self.game, 'rps_message') and self.game.rps_message:
                        try:
                            await self.game.rps_message.delete()
                            self.game.rps_message = None
                        except:
                            logger.warning("Failed to delete RPS message")
                            
                    # Process the result, determining which type of game this is
                    if isinstance(self.game, ActionRPSGame):
                        await process_action_rps_result(self.game)
                    else:
                        await process_basic_rps_result(self.game)
                
            view = RPSView(self.game, interaction.user.id, on_choice_made)
            
            # Send as ephemeral response to the interaction
            try:
                await interaction.response.send_message(
                    f"Choose Rock, Paper, or Scissors:", 
                    view=view, 
                    ephemeral=True
                )
            except (discord.errors.NotFound, discord.errors.HTTPException, aiohttp.ClientOSError) as e:
                # If interaction expired or network error, send a new message to the channel
                logger.warning(f"Interaction response failed: {str(e)}. Sending fallback message.")
                player = interaction.user
                await interaction.channel.send(
                    f"{player.mention}, your interaction expired. Please click the button again to make your choice.",
                    delete_after=10
                )
        except Exception as e:
            logger.error(f"Error in RPS choose_button: {e}\n{traceback.format_exc()}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "An error occurred. Please try again.", 
                        ephemeral=True
                    )
            except:
                pass

class StartActionRPSView(discord.ui.View):
    """View with buttons for players to start their action selection."""
    def __init__(self, game):
        super().__init__(timeout=180)  # 3 minute timeout
        self.game = game
        
    @discord.ui.button(label="Choose Your Action", style=discord.ButtonStyle.primary)
    async def action_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button that players click to choose their action."""
        try:
            # Check if this is one of the players
            if interaction.user.id not in [self.game.player1.id, self.game.player2.id]:
                await interaction.response.send_message("You are not part of this game!", ephemeral=True)
                return
                
            # Check if they've already selected an action
            if self.game.actions[interaction.user.id] is not None:
                await interaction.response.send_message("You've already selected an action!", ephemeral=True)
                return
                
            # Create the action selection view for this player
            async def on_action_selected(action_interaction, action):
                # Check if both players have selected their actions
                if self.game.are_actions_selected():
                    # Delete the previous action message since both have chosen
                    if hasattr(self.game, 'action_message') and self.game.action_message:
                        try:
                            await self.game.action_message.delete()
                            self.game.action_message = None
                        except:
                            logger.warning("Failed to delete action message")
                    
                    # Send RPS choice buttons to both players
                    view = StartRPSView(self.game)
                    rps_message = await interaction.channel.send(
                        f"Both players have selected their actions! **{self.game.player1.mention}** and **{self.game.player2.mention}**, click the button below to make your Rock, Paper, Scissors choice!",
                        view=view
                    )
                    
                    # Store the message for later deletion
                    self.game.rps_message = rps_message
            
            view = ActionSelectView(self.game, interaction.user.id, on_action_selected)
            
            # Send as ephemeral response to the interaction
            try:
                await interaction.response.send_message(
                    f"Choose what action you want to perform if you win:", 
                    view=view, 
                    ephemeral=True
                )
            except (discord.errors.NotFound, discord.errors.HTTPException, aiohttp.ClientOSError) as e:
                # If interaction expired or network error, send a new message to the channel
                logger.warning(f"Interaction response failed: {str(e)}. Sending fallback message.")
                player = interaction.user
                await interaction.channel.send(
                    f"{player.mention}, your interaction expired. Please click the button again to choose your action.",
                    delete_after=10
                )
        except Exception as e:
            logger.error(f"Error in RPS action_button: {e}\n{traceback.format_exc()}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "An error occurred. Please try again.", 
                        ephemeral=True
                    )
            except:
                pass

#---------- Game Resolution Functions ----------#

async def process_basic_rps_result(game):
    """Process and display results for a basic RPS game, including bet payout."""
    from common.database.database import add_coins
    result = game.determine_result()
    bet = getattr(game, 'bet', 0)
    # Create embed for result
    embed = discord.Embed(
        title="Rock Paper Scissors Result",
        description=result["message"],
        color=discord.Color.blue()
    )
    embed.add_field(
        name=f"{game.player1.display_name}'s Choice",
        value=f"{result['player1']['emoji']} {result['player1']['choice'].capitalize()}",
        inline=True
    )
    embed.add_field(
        name=f"{game.player2.display_name}'s Choice",
        value=f"{result['player2']['emoji']} {result['player2']['choice'].capitalize()}",
        inline=True
    )
    # Payout if bet and winner
    if bet > 0 and game.winner:
        add_coins(game.winner.id, game.channel.guild.id, bet * 2)
        embed.add_field(
            name="Bet Winnings",
            value=f"💰 {game.winner.display_name} wins {bet * 2} coins! (Bet: {bet})",
            inline=False
        )
    elif bet > 0 and not game.winner:
        embed.add_field(
            name="Bet Refund",
            value=f"It's a tie! Both players are refunded {bet} coins. (Bet: {bet})",
            inline=False
        )
        # Refund both players
        from common.database.database import add_coins
        add_coins(game.player1.id, game.channel.guild.id, bet)
        add_coins(game.player2.id, game.channel.guild.id, bet)
    elif bet > 0:
        embed.add_field(
            name="Bet",
            value=f"Bet: {bet}",
            inline=False
        )
    
    # Create view with play again button
    view = discord.ui.View()
    
    async def play_again_callback(interaction):
        # Check if user is one of the players
        if interaction.user.id not in [game.player1.id, game.player2.id]:
            await interaction.response.send_message(
                "Only the original players can start a new game.",
                ephemeral=True
            )
            return
            
        # Reset the game
        game.reset()
        
        # Remove from active games to avoid conflicts
        if game.channel.id in active_games.get(GAME_ID, {}):
            del active_games[GAME_ID][game.channel.id]
            persist_all_state()
            
        # Try to delete the old result message
        if hasattr(game, 'result_message') and game.result_message:
            try:
                await game.result_message.delete()
            except:
                pass
                
        # Start a new game
        await start_basic_rps(game.channel, game.player1, game.player2)
        
        # Disable the button
        for child in view.children:
            child.disabled = True
        await interaction.message.edit(view=view)
    
    # Add play again button
    view.add_item(PlayAgainButton(play_again_callback))
    if bet > 0:
        view.add_item(PlayAgainWithBetButton(game.player1, game.player2, bet, is_action=False))
    
    # Delete any remaining game messages
    for msg_attr in ['choice_message', 'start_message']:
        if hasattr(game, msg_attr) and getattr(game, msg_attr):
            try:
                msg = getattr(game, msg_attr)
                await msg.delete()
            except:
                pass
    
    # Send the result message
    game.result_message = await game.channel.send(embed=embed, view=view)
    
    # Remove from active games
    if game.channel.id in active_games.get(GAME_ID, {}):
        del active_games[GAME_ID][game.channel.id]
    
    # Update database with results (add this after sending the embed)
    from common.database.database import update_database_with_game_results
    await update_database_with_game_results(
        channel=game.channel,
        winner=game.winner if hasattr(game, 'winner') else None,
        loser=(game.player2 if game.winner == game.player1 else game.player1) if game.winner else None,
        game_id=GAME_ID,
        bet=bet
    )
    
    logger.info(f"Basic RPS game ended in channel {game.channel.id}")

async def process_action_rps_result(game):
    """Process and display results for an action RPS game, including bet payout."""
    from common.database.database import add_coins
    result = game.determine_action_result()
    bet = getattr(game, 'bet', 0)
    embed = discord.Embed(
        title="Rock Paper Scissors Action Result",
        description=result["message"],
        color=discord.Color.blue()
    )
    embed.add_field(
        name=f"{game.player1.display_name}'s Choice",
        value=f"{result['player1']['emoji']} {result['player1']['choice'].capitalize()}",
        inline=True
    )
    embed.add_field(
        name=f"{game.player2.display_name}'s Choice",
        value=f"{result['player2']['emoji']} {result['player2']['choice'].capitalize()}",
        inline=True
    )
    # Payout if bet and winner
    if bet > 0 and game.winner:
        add_coins(game.winner.id, game.channel.guild.id, bet * 2)
        embed.add_field(
            name="Bet Winnings",
            value=f"💰 {game.winner.display_name} wins {bet * 2} coins!",
            inline=False
        )
    elif bet > 0:
        embed.add_field(
            name="Bet",
            value=f"Bet: {bet}",
            inline=False
        )
    
    # Delete any remaining game messages to avoid clutter
    for msg_attr in ['choice_message', 'action_message', 'rps_message', 'start_message']:
        if hasattr(game, msg_attr) and getattr(game, msg_attr):
            try:
                msg = getattr(game, msg_attr)
                await msg.delete()
            except:
                pass
    
    # Send the initial result message
    game.result_message = await game.channel.send(embed=embed)
    
    # If there's a winner, fetch and display the action GIF
    if game.winner and result.get("action"):
        # Get the action and participants
        action = result["action"]
        actor = result["actor"]
        target = result["target"]
        
        # Get a random GIF for this action
        gif_url = await game.fetch_gif(action)
        
        # Format the action message
        action_text = f"**{actor.display_name}** {action}s **{target.display_name}**!"
        
        # Create the action embed
        action_embed = discord.Embed(
            title="Action Result",
            description=action_text,
            color=discord.Color.gold()
        )
        
        # Add the GIF if found
        if gif_url:
            action_embed.set_image(url=gif_url)
        
        # Create view with play again button
        view = discord.ui.View()
        
        async def play_again_callback(interaction):
            # Check if user is one of the players
            if interaction.user.id not in [game.player1.id, game.player2.id]:
                await interaction.response.send_message(
                    "Only the original players can start a new game.",
                    ephemeral=True
                )
                return
                
            # Reset the game
            game.reset()
            
            # Remove from active games to avoid conflicts
            if game.channel.id in active_games.get(GAME_ID, {}):
                del active_games[GAME_ID][game.channel.id]
            
            # Try to delete the old result messages
            if hasattr(game, 'result_message') and game.result_message:
                try:
                    await game.result_message.delete()
                except:
                    pass
                    
            # Start a new game
            await start_action_rps(game.channel, game.player1, game.player2)
            
            # Disable the button
            for child in view.children:
                child.disabled = True
            await interaction.message.edit(view=view)
        
        # Add play again button
        view.add_item(PlayAgainButton(play_again_callback))
        if bet > 0:
            view.add_item(PlayAgainWithBetButton(game.player1, game.player2, bet, is_action=True))
        
        # Send the action result with Play Again button
        await game.channel.send(embed=action_embed, view=view)
    else:
        view = discord.ui.View()
        async def play_again_callback(interaction):
            # Check if user is one of the players
            if interaction.user.id not in [game.player1.id, game.player2.id]:
                await interaction.response.send_message(
                    "Only the original players can start a new game.",
                    ephemeral=True
                )
                return
                
            # Reset the game
            game.reset()
            
            # Remove from active games to avoid conflicts
            if game.channel.id in active_games.get(GAME_ID, {}):
                del active_games[GAME_ID][game.channel.id]
                
            # Try to delete the old result message
            if hasattr(game, 'result_message') and game.result_message:
                try:
                    await game.result_message.delete()
                except:
                    pass
                
            # Start a new game
            await start_action_rps(game.channel, game.player1, game.player2)
            
            # Disable the button
            for child in view.children:
                child.disabled = True
            await interaction.message.edit(view=view)
        
        # Add play again button
        view.add_item(PlayAgainButton(play_again_callback))
        if bet > 0:
            view.add_item(PlayAgainWithBetButton(game.player1, game.player2, bet, is_action=True))
        await game.channel.send("It's a tie! No action performed.", view=view)
    
    # Remove from active games
    if game.channel.id in active_games.get(GAME_ID, {}):
        del active_games[GAME_ID][game.channel.id]
    
    # Update database with results (add this after sending the embed)
    from common.database.database import update_database_with_game_results
    await update_database_with_game_results(
        channel=game.channel,
        winner=game.winner if hasattr(game, 'winner') else None,
        loser=(game.player2 if game.winner == game.player1 else game.player1) if game.winner else None,
        game_id=GAME_ID,
        bet=bet
    )
    
    logger.info(f"Action RPS game ended in channel {game.channel.id}")

# Export rps_accept and rps_decline for bot.py compatibility

rps_accept = None
rps_decline = None

def persist_all_state():
    """Persist all relevant RPS game state to disk (stub implementation). Extend as needed."""
    pass
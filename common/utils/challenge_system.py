"""
Unified challenge system for Discord games.
"""
import time
import asyncio
import discord
import logging
import uuid
from typing import Dict, Tuple, Any, Callable, Awaitable

from common.config import ACCEPT_EMOJI, DECLINE_EMOJI, CHALLENGE_TIMEOUT_SECONDS

logger = logging.getLogger("discord_bot")

class GameChallenge:
    """Represents a challenge from one player to another for a game."""
    
    def __init__(self, challenger, target, channel, message_id, game_id, **kwargs):
        """
        Initialize a new game challenge.
        
        Args:
            challenger (discord.Member): The player issuing the challenge
            target (discord.Member): The player being challenged
            channel (discord.TextChannel): The channel where the challenge was issued
            message_id (int): The ID of the challenge message
            game_id (str): The ID of the game being challenged
            **kwargs: Additional game-specific parameters
        """
        self.challenger = challenger
        self.target = target
        self.channel = channel
        self.message_id = message_id
        self.game_id = game_id
        self.extra_params = kwargs
        self.created_at = time.time()
        self.id = str(uuid.uuid4())
    
    def is_expired(self, timeout=CHALLENGE_TIMEOUT_SECONDS):
        """
        Check if the challenge has expired.
        
        Args:
            timeout (int, optional): The timeout in seconds
            
        Returns:
            bool: True if the challenge has expired, False otherwise
        """
        return time.time() - self.created_at > timeout
    
    def get_key(self):
        """
        Get the key for storing this challenge in the challenges dictionary.
        
        Returns:
            tuple: (target_id, channel_id)
        """
        return (self.target.id, self.channel.id)
    
    def to_dict(self):
        """
        Convert the challenge to a dictionary for storage.
        
        Returns:
            dict: The challenge as a dictionary
        """
        return {
            "challenger": self.challenger,
            "target": self.target,
            "channel": self.channel,
            "message_id": self.message_id,
            "game_id": self.game_id,
            "created_at": self.created_at,
            "id": self.id,
            **self.extra_params
        }
    
    @classmethod
    def from_dict(cls, data):
        """
        Create a challenge from a dictionary.
        
        Args:
            data (dict): The challenge data
            
        Returns:
            GameChallenge: The challenge object
        """
        kwargs = {k: v for k, v in data.items() 
                 if k not in ["challenger", "target", "channel", "message_id", "game_id", "created_at", "id"]}
        
        challenge = cls(
            data["challenger"],
            data["target"],
            data["channel"],
            data["message_id"],
            data["game_id"],
            **kwargs
        )
        challenge.created_at = data["created_at"]
        challenge.id = data["id"]
        return challenge

# Dictionary to store all pending challenges
# Key: (target_id, channel_id) -> Value: GameChallenge
pending_challenges: Dict[Tuple[int, int], GameChallenge] = {}

# Dictionary to store game-specific accept handlers
# Key: game_id -> Value: async function(challenge)
accept_handlers: Dict[str, Callable[[GameChallenge], Awaitable[bool]]] = {}

# Dictionary to store game-specific decline handlers
# Key: game_id -> Value: async function(challenge)
decline_handlers: Dict[str, Callable[[GameChallenge], Awaitable[bool]]] = {}

async def create_challenge(challenger, target, channel, game_id, **kwargs):
    """
    Create a new game challenge.
    
    Args:
        challenger (discord.Member): The player issuing the challenge
        target (discord.Member): The player being challenged
        channel (discord.TextChannel): The channel where the challenge was issued
        game_id (str): The ID of the game being challenged
        **kwargs: Additional game-specific parameters
        
    Returns:
        GameChallenge or None: The created challenge, or None if creation failed
    """
    try:
        # Check if there's already a pending challenge to this user in this channel
        key = (target.id, channel.id)
        if key in pending_challenges:
            await channel.send(f"{target.mention} already has a pending challenge in this channel.")
            return None
        
        # Create the challenge embed
        embed = discord.Embed(
            title="⚔️ Game Challenge! ⚔️",
            description=f"💥 {challenger.mention} challenges {target.mention} to a game! 💥",
            color=discord.Color.orange()
        )
        
        # Add game-specific information
        game_name = kwargs.get("game_name", f"Game {game_id}")
        embed.add_field(name="🎮 Game", value=game_name, inline=True)
        embed.add_field(name="⏳ Timeout", value=f"{int(CHALLENGE_TIMEOUT_SECONDS)} seconds", inline=True)
        
        # Add any additional fields from kwargs
        for field_name, field_value in kwargs.get("embed_fields", {}).items():
            embed.add_field(name=field_name, value=field_value, inline=False)
        
        embed.add_field(
            name="📝 Instructions", 
            value=f"React with {ACCEPT_EMOJI} to accept or {DECLINE_EMOJI} to decline below.",
            inline=False
        )
        
        embed.set_thumbnail(url=challenger.display_avatar.url)
        embed.set_footer(text=f"May the best player win! | Game ID: {game_id}")
        
        # Send the challenge message
        challenge_msg = await channel.send(embed=embed)
        
        # Add reaction options
        await challenge_msg.add_reaction(ACCEPT_EMOJI)
        await challenge_msg.add_reaction(DECLINE_EMOJI)
        
        # Create the challenge object
        challenge = GameChallenge(
            challenger, 
            target, 
            channel, 
            challenge_msg.id, 
            game_id,
            **kwargs
        )
        
        # Store the challenge
        pending_challenges[key] = challenge
        
        # Set up challenge expiration
        asyncio.create_task(handle_challenge_expiration(challenge))
        
        return challenge
        
    except Exception as e:
        logger.error(f"Error creating challenge: {e}")
        await channel.send("Error creating challenge. Please try again.")
        return None

async def handle_challenge_expiration(challenge):
    """
    Handle the expiration of a challenge.
    
    Args:
        challenge (GameChallenge): The challenge to check
    """
    await asyncio.sleep(CHALLENGE_TIMEOUT_SECONDS)
    
    key = challenge.get_key()
    if key in pending_challenges and pending_challenges[key].id == challenge.id:
        # Challenge is still pending and hasn't been replaced
        try:
            # Remove the challenge
            del pending_challenges[key]
            
            # Try to get the message
            try:
                message = await challenge.channel.fetch_message(challenge.message_id)
                
                # Update the embed
                embed = discord.Embed(
                    title="Challenge Expired",
                    description=f"{challenge.target.mention} did not respond to {challenge.challenger.mention}'s challenge in time.",
                    color=discord.Color.red()
                )
                
                await message.edit(embed=embed)
                await message.clear_reactions()
                
            except (discord.errors.NotFound, discord.errors.Forbidden):
                # Message might have been deleted or we lack permissions
                pass
                
            logger.info(f"Challenge expired: {challenge.challenger.display_name} -> {challenge.target.display_name} in channel {challenge.channel.id}")
            
        except Exception as e:
            logger.error(f"Error handling challenge expiration: {e}")

def register_accept_handler(game_id, handler):
    """
    Register a handler for accepting challenges for a specific game.
    
    Args:
        game_id (str): The ID of the game
        handler (callable): The handler function
    """
    accept_handlers[game_id] = handler

def register_decline_handler(game_id, handler):
    """
    Register a handler for declining challenges for a specific game.
    
    Args:
        game_id (str): The ID of the game
        handler (callable): The handler function
    """
    decline_handlers[game_id] = handler

async def accept_challenge(ctx, user):
    """
    Accept a challenge.
    
    Args:
        ctx (commands.Context): The command context
        user (discord.Member): The user accepting the challenge
        
    Returns:
        bool: True if the challenge was accepted, False otherwise
    """
    key = (user.id, ctx.channel.id)
    if key not in pending_challenges:
        await ctx.send("You don't have any pending challenges in this channel.")
        return False
    
    challenge = pending_challenges[key]
    
    # Remove the challenge from pending
    del pending_challenges[key]
    
    # Call the game-specific accept handler
    if challenge.game_id in accept_handlers:
        return await accept_handlers[challenge.game_id](challenge)
    else:
        await ctx.send(f"No handler registered for game ID {challenge.game_id}.")
        return False

async def decline_challenge(ctx, user):
    """
    Decline a challenge.
    
    Args:
        ctx (commands.Context): The command context
        user (discord.Member): The user declining the challenge
        
    Returns:
        bool: True if the challenge was declined, False otherwise
    """
    key = (user.id, ctx.channel.id)
    if key not in pending_challenges:
        await ctx.send("You don't have any pending challenges in this channel.")
        return False
    
    challenge = pending_challenges[key]
    
    # Remove the challenge from pending
    del pending_challenges[key]
    
    # Call the game-specific decline handler
    if challenge.game_id in decline_handlers:
        return await decline_handlers[challenge.game_id](challenge)
    else:
        # Default decline behavior
        try:
            # Create the decline embed
            embed = discord.Embed(
                title="Challenge Declined",
                description=f"{user.mention} has declined {challenge.challenger.mention}'s challenge.",
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
                
            logger.info(f"Challenge declined: {challenge.challenger.display_name} -> {user.display_name} in channel {challenge.channel.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error declining challenge: {e}")
            await challenge.channel.send("Error declining challenge. Please try again.")
            return False

# ---
# handle_reaction is the unified entry point for reaction-based challenge acceptance/decline.
# Call this from bot.py's on_raw_reaction_add for all games (1001, 1002, 1003).
# ---
async def handle_reaction(payload, message, user, emoji):
    """
    Handle a reaction to a challenge message.
    
    Args:
        payload (discord.RawReactionActionEvent): The reaction payload
        message (discord.Message): The message that was reacted to
        user (discord.Member): The user who reacted
        emoji (str): The emoji that was used
        
    Returns:
        bool: True if the reaction was handled, False otherwise
    """
    # Check if this is a reaction to a challenge message
    key = (user.id, payload.channel_id)
    if key not in pending_challenges:
        return False
    
    challenge = pending_challenges[key]
    if challenge.message_id != payload.message_id:
        return False
    
    # This is a reaction to a challenge message
    if emoji == ACCEPT_EMOJI:
        # Remove the challenge from pending first to avoid duplicate processing
        del pending_challenges[key]
        
        # Call the game-specific accept handler
        if challenge.game_id in accept_handlers:
            try:
                # Delete the challenge message
                try:
                    await message.delete()
                except (discord.errors.NotFound, discord.errors.Forbidden):
                    pass
                
                # Call the handler
                return await accept_handlers[challenge.game_id](challenge)
            except Exception as e:
                logger.error(f"Error in accept handler for game {challenge.game_id}: {e}")
                await challenge.channel.send("Error accepting challenge. Please try again.")
                return False
        else:
            await challenge.channel.send(f"No handler registered for game ID {challenge.game_id}.")
            return False
        
    elif emoji == DECLINE_EMOJI:
        # Remove the challenge from pending first to avoid duplicate processing
        del pending_challenges[key]
        
        # Call the game-specific decline handler or use default
        if challenge.game_id in decline_handlers:
            try:
                return await decline_handlers[challenge.game_id](challenge)
            except Exception as e:
                logger.error(f"Error in decline handler for game {challenge.game_id}: {e}")
                await challenge.channel.send("Error declining challenge. Please try again.")
                return False
        else:
            # Default decline behavior
            try:
                # Create the decline embed
                embed = discord.Embed(
                    title="Challenge Declined",
                    description=f"{user.mention} has declined {challenge.challenger.mention}'s challenge.",
                    color=discord.Color.red()
                )
                
                # Try to edit the original challenge message
                try:
                    await message.edit(embed=embed)
                    await message.clear_reactions()
                except (discord.errors.NotFound, discord.errors.Forbidden):
                    # Message might have been deleted or we lack permissions
                    # Send a new message instead
                    await challenge.channel.send(embed=embed)
                    
                logger.info(f"Challenge declined: {challenge.challenger.display_name} -> {user.display_name} in channel {challenge.channel.id}")
                return True
                
            except Exception as e:
                logger.error(f"Error declining challenge: {e}")
                await challenge.channel.send("Error declining challenge. Please try again.")
                return False
    
    return False

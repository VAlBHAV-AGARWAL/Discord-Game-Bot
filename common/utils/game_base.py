"""
Base class for Discord games to standardize implementation.
"""
import time
import discord
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("discord_bot")

class DiscordGame(ABC):
    """Base class for all Discord games."""
    
    def __init__(self, player1, player2, channel, game_id):
        """
        Initialize a new game.
        
        Args:
            player1 (discord.Member): The first player
            player2 (discord.Member): The second player
            channel (discord.TextChannel): The channel where the game is played
            game_id (str): The unique ID for this game type
        """
        self.player1 = player1
        self.player2 = player2
        self.channel = channel
        self.game_id = game_id
        self.last_activity_time = time.time()
        self.game_over = False
        self.board_message = None
        self.board_message_id = None
    
    def update_activity_time(self):
        """Update the last activity time to prevent AFK timeout."""
        self.last_activity_time = time.time()
    
    @abstractmethod
    async def get_board_embed(self):
        """
        Get the embed for displaying the game board.
        
        Returns:
            discord.Embed: The embed to display
        """
        pass
    
    @abstractmethod
    def get_winner(self):
        """
        Get the winner of the game, if any.
        
        Returns:
            discord.Member or None: The winner, or None if no winner yet
        """
        pass
    
    @abstractmethod
    async def make_move(self, player, move_data):
        """
        Make a move in the game.
        
        Args:
            player (discord.Member): The player making the move
            move_data: The data for the move (depends on the game)
            
        Returns:
            bool: True if the move was valid, False otherwise
        """
        pass
    
    async def update_board(self, message=None):
        """
        Update the game board message.
        
        Args:
            message (str, optional): Additional message to display
        """
        if not self.board_message:
            return
            
        try:
            embed = await self.get_board_embed()
            if message:
                embed.set_footer(text=message)
            await self.board_message.edit(embed=embed)
        except Exception as e:
            logger.error(f"Error updating game board: {e}")
    
    async def end_game(self, ended_by=None, reason="Game ended."):
        """
        End the game.
        
        Args:
            ended_by (discord.Member, optional): The player who ended the game
            reason (str, optional): The reason the game ended
            
        Returns:
            bool: True if the game was ended successfully, False otherwise
        """
        if self.game_over:
            return False
            
        self.game_over = True
        
        # Create game end embed
        embed = discord.Embed(
            title=f"Game Ended",
            description=f"Game between {self.player1.mention} and {self.player2.mention} has ended.",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="Reason", 
            value=f"• {reason}",
            inline=True
        )
        
        winner = self.get_winner()
        if winner:
            embed.add_field(
                name="Result",
                value=f"• 🏆 {winner.mention} wins!"
            )
        else:
            embed.add_field(
                name="Result",
                value=f"• 🤝 It's a draw!"
            )
        
        if ended_by:
            embed.set_footer(text=f"Game ended by {ended_by.display_name}")
        
        # Send the game end message
        await self.channel.send(embed=embed)
        
        # Update the game board to show final state
        await self.update_board("Game Over!")
        
        return True
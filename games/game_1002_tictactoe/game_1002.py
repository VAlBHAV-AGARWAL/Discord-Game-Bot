"""
Game logic for the Discord Tic Tac Toe Game (ID: 1002).
"""
import random
import discord
import logging
import traceback
import time
from collections import deque

from common.database import database

logger = logging.getLogger("discord_bot")

class TicTacToeGame:
    """Main game class that handles the Tic Tac Toe game logic and state."""
    def __init__(self, player1, player2, channel):
        self.player1 = player1  # X player
        self.player2 = player2  # O player
        self.channel = channel
        
        # Game state
        self.board = [[None for _ in range(3)] for _ in range(3)]
        self.current_player = random.choice([player1, player2])
        self.winner = None
        self.game_over = False
        self.board_message = None
        
        # Track last activity time for AFK detection
        self.last_activity_time = time.time()
        
        # Symbols for players
        self.symbols = {
            player1.id: "❌",
            player2.id: "⭕"
        }
        
        logger.info(f"Tic Tac Toe game created between {player1.display_name} and {player2.display_name}")
    
    def make_move(self, row, col, player):
        """Attempt to make a move at the specified position.
        
        Args:
            row: Row index (0-2)
            col: Column index (0-2)
            player: The player making the move
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Check if game is over
            if self.game_over:
                return False, "Game is already over."
            
            # Check if it's the player's turn
            if player.id != self.current_player.id:
                return False, "It's not your turn."
            
            # Check if the position is valid
            if not (0 <= row < 3 and 0 <= col < 3):
                return False, "Invalid position."
            
            # Check if the position is already occupied
            if self.board[row][col] is not None:
                return False, "That position is already taken."
            
            # Make the move
            self.board[row][col] = self.symbols[player.id]
            
            # Update last activity time
            self.last_activity_time = time.time()
            
            # Check for win or draw
            winner_symbol = self._check_winner()
            if winner_symbol:
                self.game_over = True
                if winner_symbol == self.symbols[self.player1.id]:
                    self.winner = self.player1
                else:
                    self.winner = self.player2
                    
                logger.info(f"Tic Tac Toe game won by {self.winner.display_name}")
                return True, f"{self.winner.display_name} wins!"
            
            # Check for draw
            if self._is_board_full():
                self.game_over = True
                logger.info("Tic Tac Toe game ended in a draw")
                return True, "It's a draw!"
            
            # Switch turns
            self._switch_turn()
            return True, f"Move made. It's now {self.current_player.display_name}'s turn."
            
        except Exception as e:
            logger.error(f"Error in make_move: {e}\n{traceback.format_exc()}")
            return False, f"An error occurred: {type(e).__name__}"
    
    def _switch_turn(self):
        """Switch to the other player's turn."""
        self.current_player = self.player2 if self.current_player == self.player1 else self.player1
    
    def _check_winner(self):
        """Check if there's a winner.
        
        Returns:
            The winning symbol (X or O) or None if no winner
        """
        # Check rows
        for row in range(3):
            if self.board[row][0] is not None and self.board[row][0] == self.board[row][1] == self.board[row][2]:
                return self.board[row][0]
        
        # Check columns
        for col in range(3):
            if self.board[0][col] is not None and self.board[0][col] == self.board[1][col] == self.board[2][col]:
                return self.board[0][col]
        
        # Check diagonals
        if self.board[0][0] is not None and self.board[0][0] == self.board[1][1] == self.board[2][2]:
            return self.board[0][0]
        
        if self.board[0][2] is not None and self.board[0][2] == self.board[1][1] == self.board[2][0]:
            return self.board[0][2]
        
        return None
    
    def _is_board_full(self):
        """Check if the board is full."""
        for row in range(3):
            for col in range(3):
                if self.board[row][col] is None:
                    return False
        return True
    
    def get_board_embed(self):
        """Create an embed to display the current game state."""
        # Create the board display
        board_display = self._get_board_display()
        
        # Create the embed
        if self.game_over:
            color = discord.Color.gold()
            title = "Tic Tac Toe - Game Over!"
        else:
            color = discord.Color.blue()
            title = "Tic Tac Toe"
        
        embed = discord.Embed(
            title=title,
            description=board_display,
            color=color
        )
        
        # Add player information
        embed.add_field(
            name="Players",
            value=f"{self.player1.display_name}: ❌\n{self.player2.display_name}: ⭕",
            inline=True
        )
        
        # Add current turn or result
        if self.game_over:
            if self.winner:
                result = f"🏆 {self.winner.mention} wins!"
            else:
                result = "🤝 It's a draw!"
            
            embed.add_field(
                name="Result",
                value=result,
                inline=True
            )
        else:
            embed.add_field(
                name="Current Turn",
                value=f"{self.current_player.mention} ({self.symbols[self.current_player.id]})",
                inline=True
            )
        
        return embed
    
    def _get_board_display(self):
        """Generate a text representation of the game board."""
        # Use a white square emoji for empty cells, or player symbol
        empty_cell = "⬜"
        row_separator = "\n──────────────\n" # Horizontal line separator
        col_separator = " │ " # Vertical line separator

        board_rows_str = []
        for r in range(3):
            row_cells = []
            for c in range(3):
                cell_content = self.board[r][c]
                if cell_content is None:
                    row_cells.append(empty_cell)
                else:
                    # Symbols are now emojis, no padding needed
                    row_cells.append(cell_content) 
            board_rows_str.append(col_separator.join(row_cells))
        
        # Join all rows with the separator
        board_str = row_separator.join(board_rows_str)
        
        # Return formatted as code block
        return f"```\n{board_str}\n```"
    
    async def update_board(self, status_message=None):
        """Update the board message with the current game state."""
        try:
            embed = self.get_board_embed()
            
            if status_message:
                embed.set_footer(text=status_message)
            
            if self.board_message:
                try:
                    await self.board_message.edit(embed=embed)
                except discord.NotFound:
                    logger.warning("Board message not found, creating new one")
                    self.board_message = await self.channel.send(embed=embed)
                except Exception as e:
                    logger.error(f"Error updating board message: {e}\n{traceback.format_exc()}")
                    # Try to send a new message if update fails
                    try:
                        self.board_message = await self.channel.send(embed=embed)
                    except Exception as e2:
                        logger.error(f"Failed to create new board message after update error: {e2}")
            else:
                try:
                    self.board_message = await self.channel.send(embed=embed)
                except Exception as e:
                    logger.error(f"Error creating board message: {e}\n{traceback.format_exc()}")
                    raise
        except Exception as e:
            logger.error(f"Error in update_board: {e}\n{traceback.format_exc()}")
    
    def get_winner(self):
        """Get the winner of the game, or None if no winner or game not over."""
        if not self.game_over:
            return None
        return self.winner

class EndlessTicTacToeGame:
    def __init__(self, player1, player2, channel):
        self.player1 = player1
        self.player2 = player2
        self.channel = channel
        self.board = [[None for _ in range(3)] for _ in range(3)]
        self.turn = self.player1
        self.moves = {player1.id: deque(maxlen=3), player2.id: deque(maxlen=3)}  # store (row, col) tuples
        self.symbols = {player1.id: '❌', player2.id: '⭕'}
        self.game_over = False
        self.board_message = None
        self.board_message_id = None
        # Track last activity time for AFK detection
        self.last_activity_time = time.time()

    def get_current_symbol(self):
        return self.symbols[self.turn.id]

    def is_valid_move(self, row, col, user_id=None):
        # Only allow move if cell is empty or occupied by the player's own oldest mark
        if self.board[row][col] is None:
            return True
        # If player has 3 marks, allow replacing their own oldest
        pid = user_id if user_id is not None else self.turn.id
        moves = self.moves[pid]
        if len(moves) == 3 and moves[0] == (row, col):
            return True
        return False

    def make_move(self, row, col, user=None):
        if self.game_over:
            return False, "Game is already over."
        if user and user.id != self.turn.id:
            return False, "It's not your turn."
        if not self.is_valid_move(row, col, user_id=(user.id if user else self.turn.id)):
            return False, "You cannot place a mark here. You can only remove your own oldest mark or place on an empty tile."
        pid = self.turn.id
        symbol = self.symbols[pid]
        # Remove oldest mark if already 3
        if len(self.moves[pid]) == 3:
            old_row, old_col = self.moves[pid].popleft()
            self.board[old_row][old_col] = None
        self.board[row][col] = symbol
        self.moves[pid].append((row, col))
        # Update last activity time on move
        self.last_activity_time = time.time()
        if self.check_win(symbol):
            self.game_over = True
            return True, f"{self.turn.mention} wins!"
        # Switch turn
        self.turn = self.player2 if self.turn == self.player1 else self.player1
        return True, None

    def check_win(self, symbol):
        b = self.board
        # Check rows, columns, diagonals
        for i in range(3):
            if all(b[i][j] == symbol for j in range(3)):
                return True
            if all(b[j][i] == symbol for j in range(3)):
                return True
        if all(b[i][i] == symbol for i in range(3)):
            return True
        if all(b[i][2-i] == symbol for i in range(3)):
            return True
        return False

    def get_board_embed(self):
        # Use the same board formatting as classic mode
        board_display = self._get_board_display()
        if self.game_over:
            color = discord.Color.gold()
            title = "Endless Tic Tac Toe - Game Over!"
        else:
            color = discord.Color.purple()
            title = "Endless Tic Tac Toe"
        embed = discord.Embed(
            title=title,
            description=board_display,
            color=color
        )
        embed.add_field(name="Players", value=f"{self.player1.display_name}: ❌\n{self.player2.display_name}: ⭕", inline=True)
        if self.game_over:
            # Show result
            winner = None
            if hasattr(self, 'winner') and self.winner:
                winner = self.winner
            if winner:
                result = f"🏆 {winner.mention} wins!"
            else:
                result = "🤝 It's a draw!"
            embed.add_field(name="Result", value=result, inline=True)
        else:
            embed.add_field(name="Current Turn", value=f"{self.turn.mention} ({self.symbols[self.turn.id]})", inline=True)
        embed.set_footer(text="Each player can only have 3 marks at a time. Placing a new mark removes your oldest.")
        return embed

    def _get_board_display(self):
        empty_cell = "⬜"
        row_separator = "\n──────────────\n"
        col_separator = " │ "
        board_rows_str = []
        for r in range(3):
            row_cells = []
            for c in range(3):
                cell_content = self.board[r][c]
                if cell_content is None:
                    row_cells.append(empty_cell)
                else:
                    row_cells.append(cell_content)
            board_rows_str.append(col_separator.join(row_cells))
        board_str = row_separator.join(board_rows_str)
        return f"```\n{board_str}\n```"

    async def update_board(self, status=None):
        if self.board_message is not None:
            embed = self.get_board_embed()
            if status:
                embed.add_field(name="Status", value=status, inline=False)
            # If the game is over, remove the buttons (set view=None)
            if self.game_over:
                await self.board_message.edit(embed=embed, view=None)
            else:
                await self.board_message.edit(embed=embed)
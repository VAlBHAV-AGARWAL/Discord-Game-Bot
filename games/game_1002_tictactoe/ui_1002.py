"""
UI components for the Discord Tic Tac Toe Game (ID: 1002).
"""
import discord
import logging
import traceback
import time

from common.config import EPHEMERAL_MESSAGE_DURATION
from games.game_1002_tictactoe.game_1002 import TicTacToeGame
from common.utils.game_utils import active_games

logger = logging.getLogger("discord_bot")

class PlayAgainButton(discord.ui.Button):
    """Button to start a new Tic Tac Toe game with the same players and same mode (classic or endless)."""
    def __init__(self, player1, player2, endless=False):
        super().__init__(
            style=discord.ButtonStyle.success,
            label="Play Again",
            emoji="🔄"
        )
        self.player1 = player1
        self.player2 = player2
        self.endless = endless
    
    async def callback(self, interaction):
        try:
            if interaction.user.id not in [self.player1.id, self.player2.id]:
                await interaction.response.send_message(
                    "Only the original players can start a new game.",
                    ephemeral=True
                )
                return
            await interaction.response.defer()
            challenger = self.player1 if interaction.user.id == self.player2.id else self.player2
            if self.endless:
                from games.game_1002_tictactoe.game_1002 import EndlessTicTacToeGame
                game = EndlessTicTacToeGame(interaction.user, challenger, interaction.channel)
                game_id = "1002_endless"
            else:
                from games.game_1002_tictactoe.game_1002 import TicTacToeGame
                game = TicTacToeGame(interaction.user, challenger, interaction.channel)
                game_id = "1002"
            if game_id not in active_games:
                active_games[game_id] = {}
            active_games[game_id][interaction.channel.id] = game
            self.disabled = True
            await interaction.message.edit(view=self.view)
            await interaction.channel.send(f"🎮 {'Endless ' if self.endless else ''}Tic Tac Toe Game started: {interaction.user.mention} vs {challenger.mention}")
            from games.game_1002_tictactoe.ui_1002 import TicTacToeView
            view = TicTacToeView(game, endless=self.endless)
            initial_embed = game.get_board_embed()
            try:
                game_message = await interaction.channel.send(embed=initial_embed, view=view)
                game.board_message = game_message
                game.board_message_id = game_message.id
            except Exception as e:
                logger.error(f"Error sending initial game message with view: {e}")
                await interaction.channel.send("Error displaying the game. Please try starting a new game.")
                if game_id in active_games and interaction.channel.id in active_games[game_id]:
                    del active_games[game_id][interaction.channel.id]
                return
            logger.info(f"New {'Endless ' if self.endless else ''}Tic Tac Toe game started via Play Again in channel {interaction.channel.id}: {interaction.user.display_name} vs {challenger.display_name}")
        except Exception as e:
            logger.error(f"Error in PlayAgainButton callback: {e}\n{traceback.format_exc()}")
            await interaction.followup.send(f"Error starting new game: {type(e).__name__}. Please use the /tictactoe or /ttt_endless command instead.")

class TicTacToeButton(discord.ui.Button):
    """A button for a Tic Tac Toe square."""
    def __init__(self, row, col):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="\u200B",  # Zero-width space as default label
            row=row
        )
        self.row_idx = row
        self.col_idx = col
    
    async def callback(self, interaction):
        view = self.view
        game = view.game # Get game from view
        
        try:
            # Defer immediately. If ephemeral, followup messages will also be ephemeral.
            # If you intend to update the public game message, consider deferring without ephemeral thinking.
            await interaction.response.defer(ephemeral=True) 

            # Ensure this view is still active
            if view.is_finished():
                await interaction.followup.send(
                    "This game interface has expired. Please use a newer one."
                )
                return
            
            # Make sure it's the current player's turn
            if interaction.user.id != game.current_player.id:
                await interaction.followup.send(
                    "It's not your turn!",
                    ephemeral=True # Explicitly set ephemeral
                )
                return
            
            # Make the move - directly pass row and col from button
            success, result = game.make_move(self.row_idx, self.col_idx, interaction.user)
            
            if not success:
                await interaction.followup.send(
                    result
                )
                return
            
            # If move is successful, update the public game message (board and buttons)
            # Ensure game.board_message exists and is the one to edit.
            if game.board_message:
                await view.update_view()  # This should call game.board_message.edit(view=view)
                await game.update_board(result) # Pass the result message to update_board
            else:
                logger.error("game.board_message is not set, cannot update Tic Tac Toe UI after move.")
                await interaction.followup.send("Error updating game display. Board message not found.")

            # Check if the game ended after this move
            if game.game_over:
                # Remove from active_games for endless mode if present
                if hasattr(game, 'board_message_id') and hasattr(game, 'channel'):
                    endless_games = active_games.get("1002_endless", {})
                    if game.channel.id in endless_games:
                        del endless_games[game.channel.id]
                # Create play again button and view
                play_again_view = discord.ui.View()
                play_again_view.add_item(PlayAgainButton(game.player1, game.player2))
                # Determine game over message based on result
                if "wins" in result:
                    game_over_message = f"🏆 **Game Over!** {game.winner.mention} wins!"
                else: # draw
                    game_over_message = f"🤝 **Game Over!** It's a tie!"
                # Send the play again message
                await interaction.channel.send(
                    content=game_over_message,
                    view=play_again_view
                )
                # Stop the view since the game is over
                view.stop()

            # No explicit followup needed here if the original message is edited and defer was ephemeral.
            # If defer was not ephemeral, and you want to confirm the interaction, 
            # a followup might be desired, or ensure edit_message handles it.
            
        except discord.errors.NotFound:
            logger.warning(f"Interaction or message not found during TicTacToeButton callback. User: {interaction.user.id}")
            # No response possible if interaction is gone
        except discord.errors.HTTPException as http_err:
            logger.error(f"HTTPException in button callback: {http_err}\n{traceback.format_exc()}")
            # Try to send a followup if interaction not fully dead
            if interaction.response.is_done():
                try:
                    await interaction.followup.send(f"A network error occurred: {http_err.status}. Please try again.", ephemeral=True)
                except:
                    pass # Failed to send followup
            else:
                # This case should ideally not happen if we deferred.
                pass 
        except Exception as e:
            error_msg = f"Error in button callback: {e}\n{traceback.format_exc()}"
            logger.error(error_msg)
            
            # Generic error followup
            if interaction.response.is_done():
                try:
                    await interaction.followup.send(
                        f"Error processing button: {type(e).__name__}. Please try again.", 
                        ephemeral=True
                    )
                except:
                    pass # Failed to send followup
            else:
                # This case should ideally not happen if we deferred.
                pass

class TicTacToeView(discord.ui.View):
    """View that displays the Tic Tac Toe game buttons."""
    def __init__(self, game, endless=False):
        super().__init__(timeout=180)
        self.game = game
        self.endless = endless
        for row in range(3):
            for col in range(3):
                self.add_item(self.TTTButton(row, col, self))

    class TTTButton(discord.ui.Button):
        def __init__(self, row, col, parent_view):
            super().__init__(style=discord.ButtonStyle.secondary, label="\u200B", row=row)
            self.row = row
            self.col = col
            self.parent_view = parent_view
            self.update_label()

        def get_current_player(self):
            game = self.parent_view.game
            if hasattr(game, 'current_player'):
                return game.current_player
            elif hasattr(game, 'turn'):
                return game.turn
            return None

        def update_label(self):
            game = self.parent_view.game
            endless = getattr(self.parent_view, 'endless', False)
            cell = game.board[self.row][self.col]
            # Default style and label
            self.style = discord.ButtonStyle.secondary
            self.disabled = False
            # Emoji mapping
            emoji_map = {'X': '❌', 'O': '⭕', '❌': '❌', '⭕': '⭕'}
            # Endless mode: show emoji, disable if not available
            if endless:
                # Use emoji for X/O
                if cell == 'X' or cell == '❌':
                    self.label = '❌'
                elif cell == 'O' or cell == '⭕':
                    self.label = '⭕'
                else:
                    self.label = '\u200B'
                # Disable if not available for current player
                pid = self.get_current_player().id
                moves = game.moves[pid]
                if cell is not None:
                    # Only allow replacing your own oldest if you have 3 marks and this is the oldest
                    if len(moves) == 3 and moves[0] == (self.row, self.col):
                        self.disabled = False
                    else:
                        self.disabled = True
                else:
                    self.disabled = False
            else:
                # Classic mode
                if cell == '❌' or cell == 'X':
                    self.label = '❌'
                elif cell == '⭕' or cell == 'O':
                    self.label = '⭕'
                else:
                    self.label = '\u200B'
                # Disable if cell is taken or game is over
                self.disabled = (cell is not None) or game.game_over

        async def callback(self, interaction: discord.Interaction):
            game = self.parent_view.game
            endless = getattr(self.parent_view, 'endless', False)
            current_player = self.get_current_player()
            if game.game_over:
                await interaction.response.send_message("Game is already over.", ephemeral=True)
                return
            if interaction.user.id != current_player.id:
                await interaction.response.send_message("It's not your turn!", ephemeral=True)
                return
            if endless:
                valid, msg = game.make_move(self.row, self.col, user=interaction.user)
                if not valid:
                    await interaction.response.send_message(msg, ephemeral=True)
                    return
            else:
                success, msg = game.make_move(self.row, self.col, interaction.user)
                if not success:
                    await interaction.response.send_message(msg, ephemeral=True)
                    return
            # Update all button labels
            for item in self.parent_view.children:
                if isinstance(item, self.__class__):
                    item.update_label()
            await game.update_board(msg)
            await interaction.response.defer()

            # --- FIX: Endless mode cleanup and Play Again button ---
            if endless and game.game_over:
                endless_games = active_games.get("1002_endless", {})
                if game.channel.id in endless_games:
                    del endless_games[game.channel.id]
                play_again_view = discord.ui.View()
                play_again_view.add_item(PlayAgainButton(game.player1, game.player2, endless=True))
                if msg and "wins" in msg:
                    game_over_message = f"🏆 **Game Over!** {interaction.user.mention} wins!"
                else:
                    game_over_message = f"🤝 **Game Over!** It's a tie!"
                await interaction.channel.send(
                    content=game_over_message,
                    view=play_again_view
                )
                self.parent_view.stop()
            elif not endless and game.game_over:
                classic_games = active_games.get("1002", {})
                if game.channel.id in classic_games:
                    del classic_games[game.channel.id]
                play_again_view = discord.ui.View()
                play_again_view.add_item(PlayAgainButton(game.player1, game.player2, endless=False))
                if msg and "wins" in msg and hasattr(game, 'winner') and game.winner:
                    game_over_message = f"🏆 **Game Over!** {game.winner.mention} wins!"
                else:
                    game_over_message = f"🤝 **Game Over!** It's a tie!"
                await interaction.channel.send(
                    content=game_over_message,
                    view=play_again_view
                )
                self.parent_view.stop()
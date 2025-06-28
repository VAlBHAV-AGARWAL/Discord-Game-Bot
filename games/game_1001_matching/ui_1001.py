"""
UI components for the Discord Emoji Memory Match Game (ID: 1001).
"""
import discord
import logging
import traceback
import math
import time
import asyncio # Added for sleep
import random # For selecting random category

from common.config import EPHEMERAL_MESSAGE_DURATION, ROWS, COLUMNS, REVEAL_DELAY_SECONDS, EMOJI_CATEGORIES # Added EMOJI_CATEGORIES
from games.game_1001_matching.game_1001 import MemoryGame
from common.utils.game_utils import active_games

logger = logging.getLogger("discord_bot")

class PlayAgainButton(discord.ui.Button):
    """Button to start a new Memory Match game with the same players."""
    def __init__(self, player1, player2, grid_rows, grid_cols):
        super().__init__(
            style=discord.ButtonStyle.success,
            label="Play Again",
            emoji="🔄"
        )
        self.player1 = player1
        self.player2 = player2
        self.grid_rows = grid_rows
        self.grid_cols = grid_cols
    
    async def callback(self, interaction):
        try:
            # Only allow the original players to press the button
            if interaction.user.id not in [self.player1.id, self.player2.id]:
                await interaction.response.send_message(
                    "Only the original players can start a new game.",
                    ephemeral=True
                )
                return
            
            # Defer response to give time for processing
            await interaction.response.defer()
            
            # Select a random category
            category = random.choice(list(EMOJI_CATEGORIES.keys()))
            
            # Use the original player order for consistency, randomization will happen in MemoryGame
            # Create the game instance
            game = MemoryGame(self.player1, self.player2, interaction.channel, category, self.grid_rows, self.grid_cols)
            
            # Make sure the active_games dictionary is initialized for this game ID
            game_id = "1001"
            if game_id not in active_games:
                active_games[game_id] = {}
                
            # Store the game
            active_games[game_id][interaction.channel.id] = game
            
            # Disable this button to prevent multiple clicks
            self.disabled = True
            await interaction.message.edit(view=self.view)
            
            # Send initial informational message
            await interaction.channel.send(f"📝 Memory Match Game started with **random category {category}**: {self.player1.mention} vs {self.player2.mention}\n🎲 **{game.current_player.mention} will go first!**")

            # Create game view
            view = GameView(game)
            
            # Send the main game messages (board and buttons separate)
            try:
                board_message, buttons_message = await view.send_initial_messages(interaction.channel)
                # The board_message and board_message_id are already set in send_initial_messages
            except Exception as e:
                logger.error(f"Error sending initial game messages: {e}")
                await interaction.channel.send("Error displaying the game. Please try starting a new game.")
                # Clean up active game if setup failed critically
                if game_id in active_games and interaction.channel.id in active_games[game_id]:
                    del active_games[game_id][interaction.channel.id]
                return
            
            logger.info(f"New Memory Match game started via Play Again in channel {interaction.channel.id}: {self.player1.display_name} vs {self.player2.display_name}")
            
        except Exception as e:
            logger.error(f"Error in PlayAgainButton callback: {e}\n{traceback.format_exc()}")
            await interaction.followup.send(f"Error starting new game: {type(e).__name__}. Please use the /matching_game command instead.")

class PlayAgainWithBetButton(discord.ui.Button):
    """Button to start a new Memory Match game with the same players and bet."""
    def __init__(self, player1, player2, grid_rows, grid_cols, bet):
        super().__init__(
            style=discord.ButtonStyle.success,
            label=f"Play Again with Bet ({bet})",
            emoji="💰"
        )
        self.player1 = player1
        self.player2 = player2
        self.grid_rows = grid_rows
        self.grid_cols = grid_cols
        self.bet = bet

    async def callback(self, interaction):
        from common.database.database import get_balance, remove_coins
        try:
            if interaction.user.id not in [self.player1.id, self.player2.id]:
                await interaction.response.send_message(
                    "Only the original players can start a new game.", ephemeral=True
                )
                return
            guild_id = interaction.guild.id if interaction.guild else 0
            if get_balance(self.player1.id, guild_id) < self.bet or get_balance(self.player2.id, guild_id) < self.bet:
                await interaction.response.send_message(
                    "Both players must have enough coins to play again with the same bet.", ephemeral=True
                )
                return
            await interaction.response.defer()
            # Deduct bet from both players
            remove_coins(self.player1.id, guild_id, self.bet)
            remove_coins(self.player2.id, guild_id, self.bet)
            # Use a random category for now (could be improved to use previous)
            category = random.choice(list(EMOJI_CATEGORIES.keys()))
            game = MemoryGame(self.player1, self.player2, interaction.channel, category, self.grid_rows, self.grid_cols)
            game.bet = self.bet
            game_id = "1001"
            if game_id not in active_games:
                active_games[game_id] = {}
            active_games[game_id][interaction.channel.id] = game
            self.disabled = True
            await interaction.message.edit(view=self.view)
            await interaction.channel.send(f"📝 Memory Match Game started with bet **{self.bet}**: {self.player1.mention} vs {self.player2.mention}\n🎲 **{game.current_player.mention} will go first!**")
            view = GameView(game)
            try:
                board_message, buttons_message = await view.send_initial_messages(interaction.channel)
            except Exception as e:
                logger.error(f"Error sending initial game messages: {e}")
                await interaction.channel.send("Error displaying the game. Please try starting a new game.")
                if game_id in active_games and interaction.channel.id in active_games[game_id]:
                    del active_games[game_id][interaction.channel.id]
                return
            logger.info(f"New Memory Match game started via Play Again with Bet in channel {interaction.channel.id}: {self.player1.display_name} vs {self.player2.display_name}")
        except Exception as e:
            logger.error(f"Error in PlayAgainWithBetButton callback: {e}\n{traceback.format_exc()}")
            await interaction.followup.send(f"Error starting new game: {type(e).__name__}. Please use the /matching_game command instead.")

class CardButton(discord.ui.Button):
    """A button representing a card in the memory match game."""
    def __init__(self, row, col, card=None, button_number=0):
        # Each game row maps to a UI row
        ui_row = row  
        
        # All buttons are always gray, only their disabled state changes
        style = discord.ButtonStyle.secondary
        label = str(button_number) if button_number > 0 else f"{row+1},{col+1}"
        
        # Button is disabled if card is matched or if it's not the player's turn
        disabled = False
        if card and card.is_matched:
            disabled = True
        
        super().__init__(
            style=style,
            label=label,
            disabled=disabled,
            row=ui_row
        )
        self.row_idx = row
        self.col_idx = col
    
    async def callback(self, interaction):
        view = self.view
        game = view.game # Get game from view
        
        try:
            # Defer interaction early. 
            # Game updates are typically to the public message, so thinking=True might be an option
            # but if select_card sends ephemeral messages on errors, deferring ephemerally is safer.
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
                    ephemeral=True
                )
                return
            
            # select_card will handle further interaction responses (edit_message or followup.send)
            await view.select_card(interaction, self.row_idx, self.col_idx)
            
        except discord.errors.NotFound:
            logger.warning(f"Interaction or message not found during CardButton callback. User: {interaction.user.id}")
            # No response possible if interaction is gone
        except discord.errors.HTTPException as http_err:
            logger.error(f"HTTPException in CardButton callback: {http_err}\n{traceback.format_exc()}")
            if interaction.response.is_done(): # Check if already responded (e.g. by select_card)
                try:
                    await interaction.followup.send(f"A network error occurred: {http_err.status}. Please try again.", ephemeral=True)
                except:
                    pass 
        except Exception as e:
            error_msg = f"Error in button callback: {e}\n{traceback.format_exc()}"
            logger.error(error_msg)
            
            if interaction.response.is_done(): # Check if already responded by select_card before error
                try:
                    await interaction.followup.send(
                        f"Error processing button: {type(e).__name__}. Please try again.", 
                        ephemeral=True
                    )
                except:
                    pass

class GameView(discord.ui.View):
    """View that displays the game buttons and handles card selection."""
    def __init__(self, game):
        super().__init__(timeout=None)  # No timeout
        self.game = game
        self.selected_cards = []  # Will store (row, col) tuples
        self.buttons_message = None  # Will store the message containing this view
        
        try:
            # Add buttons for each card position
            self._add_buttons()
        except Exception as e:
            error_msg = f"Error creating game view: {e}\n{traceback.format_exc()}"
            logger.error(error_msg)
    
    def _add_buttons(self):
        """Add card buttons to the view based on the current game state."""
        # Clear any existing buttons
        self.clear_items()
        
        try:
            # Keep track of how many buttons we've added to each UI row
            buttons_per_ui_row = {}
            
            # Keep a counter for button numbers
            button_counter = 1
            
            # Organize by game rows
            for r in range(self.game.rows):
                for c in range(self.game.columns):
                    card = self.game.get_card(r, c)
                    if not card:
                        button_counter += 1
                        continue
                    
                    # Each game row corresponds to a UI row
                    ui_row = r
                    
                    # Make sure we don't exceed 5 buttons per UI row
                    buttons_in_this_row = buttons_per_ui_row.get(ui_row, 0)
                    if buttons_in_this_row >= 5:
                        # If we've already added 5 buttons to this UI row, we need to move to the next row
                        logger.warning(f"UI row {ui_row} already has 5 buttons; this shouldn't happen with a 5-column grid")
                        continue
                    
                    # Add this button with the numbered label
                    btn = CardButton(r, c, card, button_counter)
                    self.add_item(btn)
                    
                    # Update our counter
                    buttons_per_ui_row[ui_row] = buttons_in_this_row + 1
                    button_counter += 1
            
            # Log button layout for debugging
            button_count = len(self.children)
            if button_count > 0:
                layout_info = []
                # Group buttons by UI row for better logging
                ui_row_buttons = {}
                for btn in self.children:
                    if isinstance(btn, CardButton):
                        if btn.row not in ui_row_buttons:
                            ui_row_buttons[btn.row] = []
                        ui_row_buttons[btn.row].append(f"({btn.row_idx+1},{btn.col_idx+1})")
                
                # Create formatted layout info
                for ui_row, buttons in sorted(ui_row_buttons.items()):
                    layout_info.append(f"UI Row {ui_row}: {' '.join(buttons)}")
                
                logger.info(f"Added {button_count} buttons across {len(ui_row_buttons)} UI rows")
                logger.info(f"Button layout: {'; '.join(layout_info)}")
            else:
                logger.warning("No buttons were added to the view")
                
        except Exception as e:
            error_msg = f"Error adding buttons: {e}\n{traceback.format_exc()}"
            logger.error(error_msg)
    
    async def send_initial_messages(self, channel):
        """Send the initial board and buttons messages."""
        try:
            # Send the game board embed first
            initial_embed = self.game.get_board_embed()
            board_message = await channel.send(embed=initial_embed)
            self.game.board_message = board_message
            self.game.board_message_id = board_message.id
            
            # Then send the buttons view as a separate message
            buttons_message = await channel.send(content=f"Click a number to select a card. {self.game.current_player.mention}'s turn:", view=self)
            self.buttons_message = buttons_message
            self.game.buttons_message = buttons_message  # Store it in the game object too
            
            # Log successful setup
            logger.info(f"Initial game messages sent for Memory Match in channel {channel.id}")
            
            return board_message, buttons_message
        except Exception as e:
            logger.error(f"Error sending initial messages: {e}\n{traceback.format_exc()}")
            raise

    async def select_card(self, interaction, row, col):
        try:
            card = self.game.get_card(row, col)
            if not card or card.is_matched:
                await interaction.followup.send(
                    "This card has already been matched!", 
                    ephemeral=True
                )
                return
            for r, c in self.selected_cards:
                if r == row and c == col:
                    await interaction.followup.send(
                        "You already selected this card!", 
                        ephemeral=True
                    )
                    return
            self.game.last_activity_time = time.time()
            self.selected_cards.append((row, col))
            card.is_revealed = True
            if len(self.selected_cards) == 1:
                for child in self.children:
                    if isinstance(child, CardButton) and child.row_idx == row and child.col_idx == col:
                        child.disabled = True
                await interaction.edit_original_response(view=self)
                await self.game.update_board(f"{interaction.user.display_name} selected card at ({row+1},{col+1})...")
                return
            if len(self.selected_cards) == 2:
                row1, col1 = self.selected_cards[0]
                card1 = self.game.get_card(row1, col1)
                for child in self.children:
                    child.disabled = True
                await interaction.edit_original_response(view=self)
                await self.game.update_board(f"{interaction.user.display_name} selected cards at ({row1+1},{col1+1}) and ({row+1},{col+1})...")
                # Call game logic (now handles delay and hiding)
                success, result_message, game_ended = await self.game.make_move(row1, col1, row, col, interaction.user)
                if not success:
                    await interaction.followup.send(result_message, ephemeral=True)
                    self.selected_cards = []
                    new_view = GameView(self.game)
                    await self._replace_buttons_message(interaction.channel, new_view)
                    return
                if game_ended:
                    play_again_view = discord.ui.View()
                    play_again_view.add_item(PlayAgainButton(
                        self.game.player1, 
                        self.game.player2,
                        self.game.rows,
                        self.game.columns
                    ))
                    if getattr(self.game, 'bet', 0) > 0:
                        play_again_view.add_item(PlayAgainWithBetButton(
                            self.game.player1,
                            self.game.player2,
                            self.game.rows,
                            self.game.columns,
                            self.game.bet
                        ))
                    if self.game.winner:
                        winner_name = self.game.winner.display_name
                        game_over_message = f"🏆 **Game Over!** {winner_name} wins! Final Scores: {self.game.player1.display_name}={self.game.scores[self.game.player1.id]}, {self.game.player2.display_name}={self.game.scores[self.game.player2.id]}"
                    else:
                        game_over_message = f"🤝 **Game Over!** It's a tie! Final Scores: {self.game.player1.display_name}={self.game.scores[self.game.player1.id]}, {self.game.player2.display_name}={self.game.scores[self.game.player2.id]}"
                    if self.buttons_message:
                        try:
                            await self.buttons_message.delete()
                        except:
                            pass
                    await self.game.update_board("Game Over!")
                    await interaction.channel.send(content=game_over_message, view=play_again_view)
                    self.stop()
                    return
                # For both match and no match, just reset and update UI
                self.selected_cards = []
                new_view = GameView(self.game)
                await self._replace_buttons_message(interaction.channel, new_view)
        except Exception as e:
            logger.error(f"Error in select_card: {e}\n{traceback.format_exc()}")
            await interaction.followup.send("An error occurred while processing your selection.", ephemeral=True)
            self.selected_cards = []
            try:
                new_view = GameView(self.game)
                await self._replace_buttons_message(interaction.channel, new_view)
            except:
                pass

    async def _replace_buttons_message(self, channel, new_view):
        """Replace the current buttons message with a new one."""
        try:
            # Delete the old buttons message
            if self.buttons_message:
                try:
                    await self.buttons_message.delete()
                except Exception as e:
                    logger.error(f"Error deleting old buttons message: {e}")
                    # Continue even if delete fails
                    pass
            
            # Send a new buttons message with the new view and mention the current player
            content = f"Click a number to select a card. {self.game.current_player.mention}'s turn:"
            buttons_message = await channel.send(content=content, view=new_view)
            
            # Store the reference in multiple places to ensure consistency
            new_view.buttons_message = buttons_message
            self.game.buttons_message = buttons_message
            self.buttons_message = buttons_message  # Update in this view too for any clean-up
            
            logger.info(f"Replaced buttons message for {self.game.current_player.display_name}'s turn")
            
        except Exception as e:
            logger.error(f"Error replacing buttons message: {e}\n{traceback.format_exc()}")

    def _update_buttons_for_game_state(self, force_disable_all=False):
        """Updates the buttons based on the current game state."""
        # Clear existing buttons and recreate all buttons with current card states
        self.clear_items()
        
        button_idx_counter = 1 # Start numbering from 1
        # Organize by game rows
        for r in range(self.game.rows):
            for c in range(self.game.columns):
                card = self.game.get_card(r, c)
                if not card: 
                    button_idx_counter += 1
                    continue
                
                # Create button with current number - all buttons are gray
                btn = CardButton(r, c, card, button_idx_counter)
                
                # Force disable if requested (e.g., game over)
                if force_disable_all:
                    btn.disabled = True
                
                self.add_item(btn)
                button_idx_counter += 1

    async def on_timeout(self):
        # This view has timeout=None, so this won't be called automatically
        # If a timeout were set, this is where cleanup would happen.
        logger.info(f"GameView for game in channel {self.game.channel.id} timed out (theoretically). Stopping view.")
        message = self.game.buttons_message # or self.message if it's directly set by discord.py
        if message:
            await message.edit(view=None) # Remove buttons
        self.stop()

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        logger.error(f"Error in GameView item {item}: {error}\n{traceback.format_exc()}")
        if interaction.response.is_done():
            await interaction.followup.send(f"An error occurred with the interface: {type(error).__name__}", ephemeral=True)
        else:
            await interaction.response.send_message(f"An error occurred with the interface: {type(error).__name__}", ephemeral=True)
import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from common.database.database import get_balance, add_coins, remove_coins, add_xp

CURRENCY_NAME = "Coins"
DIAMOND_EMOJI = "💎"
BOMB_EMOJI = "💣"
QUESTION_EMOJI = "❓"
CASHOUT_EMOJI = "💰"
MINES_XP = 5

class MinesView(discord.ui.View):
    def __init__(self, user_id, bet, bot, guild_id, num_mines=5):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.bot = bot
        self.bet = bet
        self.guild_id = guild_id
        self.num_mines = num_mines
        self.revealed = set()
        self.bombs = set(random.sample(range(25), num_mines))
        self.multiplier = 1.0
        self.active = True
        for i in range(25):
            self.add_item(self.MineButton(i, self))
        # Cashout button will be sent as a separate message

    async def send_initial_messages(self, channel, user=None):
        # Compose a single message with content and embed
        bet_info = f" Bet - {self.bet}" if hasattr(self, 'bet') else ""
        content = f"{user.mention} is playing Mines!{bet_info}" if user else None
        embed = discord.Embed(title="Mines Game", description=f"Click the tiles to reveal. Cash out anytime. Mines: {self.num_mines}", color=discord.Color.blurple())
        embed.set_footer(text="Cash out anytime using !out")
        board_message = await channel.send(content=content, embed=embed, view=self)
        self.board_message = board_message  # Store for reveal_all_mines
        return board_message

    def calculate_multiplier(self, revealed_override=None):
        import math
        x = len(self.revealed) if revealed_override is None else revealed_override
        m = self.num_mines
        t = 25
        if x == 0:
            return 1.0
        numerator = math.comb(t, x)
        denominator = math.comb(t - m, x)
        if denominator == 0:
            return 0
        house_edge = 0.99
        return round((numerator / denominator) * house_edge, 2)

    class MineButton(discord.ui.Button):
        def __init__(self, idx, parent_view):
            super().__init__(style=discord.ButtonStyle.secondary, label=QUESTION_EMOJI, row=idx//5)
            self.idx = idx
            self.parent_view = parent_view
        async def callback(self, interaction: discord.Interaction):
            if not self.parent_view.active:
                embed = discord.Embed(description="❌ **Game has ended!**", color=discord.Color.red())
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            if interaction.user.id != self.parent_view.user_id:
                embed = discord.Embed(description="🚫 **Not your game or game ended!**", color=discord.Color.red())
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            if self.idx in self.parent_view.revealed:
                embed = discord.Embed(description="⚠️ **Already revealed!**", color=discord.Color.orange())
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            self.parent_view.revealed.add(self.idx)
            if self.idx in self.parent_view.bombs:
                self.style = discord.ButtonStyle.danger
                self.label = BOMB_EMOJI
                self.parent_view.active = False
                remove_coins(self.parent_view.user_id, self.parent_view.guild_id, self.parent_view.bet)
                embed = discord.Embed(description=f"{BOMB_EMOJI} Bomb! You lost {self.parent_view.bet} {CURRENCY_NAME}.", color=discord.Color.red())
                await interaction.response.edit_message(content=None, embed=embed, view=self.parent_view)
                await self.parent_view.reveal_all_mines()
                self.parent_view.disable_all()
                if hasattr(self.parent_view, 'cashout_message'):
                    try:
                        await self.parent_view.cashout_message.delete()
                    except Exception:
                        pass
                return
            else:
                self.style = discord.ButtonStyle.success
                self.label = DIAMOND_EMOJI
                self.parent_view.multiplier = self.parent_view.calculate_multiplier()
                embed = discord.Embed(description=f"{DIAMOND_EMOJI} Safe! {self.parent_view.multiplier:.2f}x. Cash out anytime.", color=discord.Color.green())
                await interaction.response.edit_message(content=None, embed=embed, view=self.parent_view)

    class CashoutButton(discord.ui.Button):
        def __init__(self, parent_view):
            # This class is now unused, but kept for compatibility if needed elsewhere
            super().__init__(style=discord.ButtonStyle.success, label=CASHOUT_EMOJI)
            self.parent_view = parent_view
        async def callback(self, interaction: discord.Interaction):
            await interaction.response.send_message("Cashout via button is disabled. Use !out instead.", ephemeral=True)

    async def reveal_all_mines(self):
        # Reveal all tiles: bombs and diamonds
        for item in self.children:
            if isinstance(item, self.MineButton):
                if item.idx in self.bombs:
                    item.style = discord.ButtonStyle.danger
                    item.label = BOMB_EMOJI
                elif item.idx in self.revealed:
                    item.style = discord.ButtonStyle.success
                    item.label = DIAMOND_EMOJI
                else:
                    item.style = discord.ButtonStyle.secondary
                    item.label = QUESTION_EMOJI
                item.disabled = True
        self.disable_all()  # Ensure all buttons are disabled after game ends
        # Update the board message
        if hasattr(self, 'board_message') and self.board_message:
            try:
                await self.board_message.edit(view=self)
            except:
                pass
        # After updating the board, also try to delete the cashout message if it exists and game is over
        if not self.active and hasattr(self, 'cashout_message') and self.cashout_message:
            try:
                await self.cashout_message.delete()
            except Exception:
                pass
            self.cashout_message = None

    def disable_all(self):
        for item in self.children:
            item.disabled = True
        # Also disable the cashout button if it exists
        if hasattr(self, 'cashout_view') and self.cashout_view:
            for item in self.cashout_view.children:
                item.disabled = True
            # Edit the message to disable the button
            if hasattr(self, 'cashout_message') and self.cashout_message:
                try:
                    asyncio.create_task(self.cashout_message.edit(view=self.cashout_view))
                except Exception:
                    pass

class Mines(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}  # {user_id: MinesView}

    @app_commands.command(name="mines", description="Play Mines and try to avoid the bombs!")
    @app_commands.describe(amount="Amount of coins to bet", mines="Number of mines (default 5)")
    async def mines(self, interaction: discord.Interaction, amount: int, mines: int = 5):
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        # Prevent multiple active games per user
        if user_id in self.active_games and self.active_games[user_id].active:
            embed = discord.Embed(description="You already have an active Mines game! Please finish or end it before starting a new one.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        if amount <= 0:
            embed = discord.Embed(description="Amount must be positive.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        if mines < 1 or mines >= 25:
            embed = discord.Embed(description="Number of mines must be between 1 and 24.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        if get_balance(user_id, guild_id) < amount:
            embed = discord.Embed(description="You don't have enough coins!", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        view = MinesView(user_id, amount, self.bot, guild_id, num_mines=mines)
        self.active_games[user_id] = view
        # Start AFK timer
        async def afk_check():
            await asyncio.sleep(60)
            if view.active and len(view.revealed) == 0:
                view.active = False
                view.disable_all()
                embed = discord.Embed(description=f"⏰ {interaction.user.mention} lost {amount} {CURRENCY_NAME} due to inactivity! (AFK)", color=discord.Color.red())
                if hasattr(view, 'board_message') and view.board_message:
                    try:
                        await view.board_message.edit(embed=embed, view=view)
                    except Exception:
                        pass
                # Clean up
                if user_id in self.active_games:
                    del self.active_games[user_id]
        asyncio.create_task(afk_check())
        # Send a single message with content and embed as the initial response
        content = f"{interaction.user.mention} is playing Mines!"
        embed = discord.Embed(title="Mines Game", description=f"Click the tiles to reveal. Cash out anytime. Mines: {mines}", color=discord.Color.blurple())
        embed.set_footer(text="Cash out anytime using `!out`")
        await interaction.response.send_message(content=content, embed=embed, view=view)
        view.board_message = None  # Not needed for this pattern
        # Remove from active_games when game ends (patch MinesView to do this)
        def end_game_cleanup():
            if user_id in self.active_games:
                del self.active_games[user_id]
        view._end_game_cleanup = end_game_cleanup

    @commands.command(name="out", help="Cash out your winnings in Mines.")
    async def out(self, ctx):
        user_id = ctx.author.id
        guild_id = ctx.guild.id if ctx.guild else None
        view = self.active_games.get(user_id)
        if not view or not view.active:
            await ctx.send("You don't have an active Mines game to cash out!", ephemeral=True)
            return
        # Calculate winnings
        win = int(view.bet * view.multiplier)
        add_coins(user_id, guild_id, win)
        view.active = False
        view.disable_all()
        embed = discord.Embed(description=f"{CASHOUT_EMOJI} You cashed out and won {win} {CURRENCY_NAME}! Multiplier: {view.multiplier:.2f}x", color=discord.Color.gold())
        if hasattr(view, 'board_message') and view.board_message:
            try:
                await view.board_message.edit(embed=embed, view=view)
            except Exception:
                pass
        # Send a gold embed message to the channel announcing the win
        announce_embed = discord.Embed(description=f"{ctx.author.mention} cashed out and won {win} {CURRENCY_NAME}!", color=discord.Color.gold())
        await ctx.send(embed=announce_embed, ephemeral=False)
        # Clean up
        if user_id in self.active_games:
            del self.active_games[user_id]

# Patch MinesView to call cleanup on end
old_disable_all = getattr(MinesView, 'disable_all', None)
def new_disable_all(self):
    if old_disable_all:
        old_disable_all(self)
    if hasattr(self, '_end_game_cleanup'):
        self._end_game_cleanup()
MinesView.disable_all = new_disable_all

async def setup_mines_command(bot):
    cog = Mines(bot)
    await bot.add_cog(cog)
    bot.add_command(cog.mines_text)

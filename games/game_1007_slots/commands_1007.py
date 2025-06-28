import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from common.database.database import get_balance, add_coins, remove_coins, add_xp
from datetime import datetime, timedelta

COIN_EMOJI = "🪙"
FIVE_X_EMOJI = "🍀"
TWO_X_EMOJI = "🍒"
ONE_X_EMOJIS = ["🍋", "🍊"]
TRASH_EMOJI = "🗑️"
CURRENCY_NAME = "Coins"
SLOTS_XP = 5

# All symbols for the slot machine
SLOT_SYMBOLS = [COIN_EMOJI, FIVE_X_EMOJI, TWO_X_EMOJI, ONE_X_EMOJIS[0], ONE_X_EMOJIS[1], TRASH_EMOJI]
# Multipliers for 3 of a kind
SLOT_MULTIPLIERS = {
    COIN_EMOJI: 10,
    FIVE_X_EMOJI: 5,
    TWO_X_EMOJI: 2,
    ONE_X_EMOJIS[0]: 1,
    ONE_X_EMOJIS[1]: 1,
    TRASH_EMOJI: 0.5
}

class Slots(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}  # {user_id: datetime}

    async def _check_cooldown(self, ctx_or_interaction, user_id, command_name):
        now = datetime.utcnow()
        key = f"{user_id}:{command_name}"
        cooldown_until = self.cooldowns.get(key)
        if cooldown_until and cooldown_until > now:
            seconds_left = int((cooldown_until - now).total_seconds())
            # Send or update cooldown message with countdown
            if hasattr(ctx_or_interaction, 'send'):
                # Text command
                msg = await ctx_or_interaction.send(f"I understand the Rush but calm down, Let me breath, try again in {seconds_left} seconds.")
                for i in range(seconds_left, 0, -1):
                    await asyncio.sleep(1)
                    await msg.edit(content=f"I understand the Rush but calm down, Let me breath, try again in {i-1} seconds.")
                await msg.delete()
            else:
                # Slash command
                embed = discord.Embed(description=f"I understand the Rush but calm down, Let me breath, try again in {seconds_left} seconds.", color=discord.Color.orange())
                msg = await ctx_or_interaction.response.send_message(embed=embed, ephemeral=True)
                # Try to get the message object for editing
                try:
                    msg_obj = await ctx_or_interaction.original_response()
                    for i in range(seconds_left, 0, -1):
                        await asyncio.sleep(1)
                        embed.description = f"I understand the Rush but calm down, Let me breath, try again in {i-1} seconds."
                        await msg_obj.edit(embed=embed)
                    await msg_obj.delete()
                except Exception:
                    pass
            return True
        return False

    @app_commands.command(name="slots", description="Spin the slots and win big!")
    @app_commands.describe(amount="Amount of coins to bet")
    async def slots(self, interaction: discord.Interaction, amount: int):
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        if await self._check_cooldown(interaction, user_id, 'slots'):
            return
        if amount <= 0:
            embed = discord.Embed(description="Amount must be positive.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        if get_balance(user_id, guild_id) < amount:
            embed = discord.Embed(description="You don't have enough coins!", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        # Roll the slots
        row = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
        # Animate reveal
        border = "━━━━━━━━━━━━━━"
        slot_template = (
            f"{border}\n"
            f"┃  {{0}}  ┃  {{1}}  ┃  {{2}}  ┃\n"
            f"{border}"
        )
        placeholder = "❔"
        embed = discord.Embed(title="🎰 SLOTS 🎰", description=slot_template.format(placeholder, placeholder, placeholder), color=discord.Color.gold())
        await interaction.response.send_message(embed=embed, ephemeral=False)
        await asyncio.sleep(0.7)
        embed.description = slot_template.format(row[0], placeholder, placeholder)
        await interaction.edit_original_response(embed=embed)
        await asyncio.sleep(0.7)
        embed.description = slot_template.format(row[0], row[1], placeholder)
        await interaction.edit_original_response(embed=embed)
        await asyncio.sleep(0.7)
        embed.description = slot_template.format(row[0], row[1], row[2])
        await interaction.edit_original_response(embed=embed)
        # Determine payout
        slot_row = f"┃  {row[0]}  ┃  {row[1]}  ┃  {row[2]}  ┃"
        payout = 0
        result_msg = ""
        # 3 of a kind
        if row[0] == row[1] == row[2]:
            payout = int(amount * SLOT_MULTIPLIERS[row[0]])
            result_msg = f"**JACKPOT! 3 of a kind! You won {payout} {CURRENCY_NAME}! Multiplier: {SLOT_MULTIPLIERS[row[0]]}x** 🎉"
        # 2 of a kind (center matches left or right, but not all 3)
        elif row[1] == row[0] or row[1] == row[2]:
            payout = int(amount * 0.25)
            if payout > 0:
                result_msg = f"**2 of a kind! You won {payout} {CURRENCY_NAME}! Multiplier: 0.25x**"
            else:
                result_msg = f"**2 of a kind! But your bet was too low for a payout.**"
        else:
            result_msg = f"**No match! You lost {amount} {CURRENCY_NAME}.**"
        # Update balance
        remove_coins(user_id, guild_id, amount)
        if payout > 0:
            add_coins(user_id, guild_id, payout)
        add_xp(user_id, guild_id, SLOTS_XP)
        # Show result
        result_text = (
            f"{border}\n{slot_row}\n{border}\n"
            f"{result_msg}"
        )
        color = discord.Color.green() if payout > 0 else discord.Color.red()
        result_embed = discord.Embed(title="Slots Result", description=result_text, color=color)
        await interaction.edit_original_response(embed=result_embed)
        # At the end, set cooldown
        self.cooldowns[f"{user_id}:slots"] = datetime.utcnow() + timedelta(seconds=20)

    @commands.command(name="slots", help="Play slots. Usage: !slots <amount>")
    async def slots_text(self, ctx, amount: int = None):
        user_id = ctx.author.id
        if await self._check_cooldown(ctx, user_id, 'slots'):
            return
        if amount is None or amount <= 0:
            embed = discord.Embed(description="Usage: !slots <amount> (e.g. !slots 50)", color=discord.Color.orange())
            embed.set_author(name="Slots Game", icon_url=getattr(ctx.guild.me, 'avatar', None))
            embed.set_footer(text="Try /slots for the animated version!")
            await ctx.send(embed=embed)
            return
        guild_id = ctx.guild.id if ctx.guild else 0
        if get_balance(user_id, guild_id) < amount:
            embed = discord.Embed(description="You don't have enough coins!", color=discord.Color.red())
            embed.set_author(name="Slots Game", icon_url=getattr(ctx.guild.me, 'avatar', None))
            await ctx.send(embed=embed)
            return
        slot_symbols = [
            (COIN_EMOJI, 10),
            (FIVE_X_EMOJI, 5),
            (TWO_X_EMOJI, 2),
            (ONE_X_EMOJIS[0], 1),
            (ONE_X_EMOJIS[1], 1),
            (TRASH_EMOJI, 0.5)
        ]
        symbols = [s[0] for s in slot_symbols]
        multipliers = {s[0]: s[1] for s in slot_symbols}
        row = [random.choice(symbols) for _ in range(3)]
        payout = 0
        result_msg = ""
        # 3 of a kind
        if row[0] == row[1] == row[2]:
            payout = int(amount * multipliers[row[0]])  # Only the win, not win+bet
            result_msg = f"JACKPOT! 3 of a kind! You won {payout} {CURRENCY_NAME}! Multiplier: {multipliers[row[0]]}x"
        # 2 of a kind (center matches left or right, but not all 3)
        elif row[1] == row[0] or row[1] == row[2]:
            payout = int(amount * 0.25)
            if payout > 0:
                result_msg = f"2 of a kind! You won {payout} {CURRENCY_NAME}! Multiplier: 0.25x"
            else:
                result_msg = f"2 of a kind! But your bet was too low for a payout."
        else:
            result_msg = f"No match! You lost {amount} {CURRENCY_NAME}."
        remove_coins(user_id, guild_id, amount)
        if payout > 0:
            add_coins(user_id, guild_id, payout)
        add_xp(user_id, guild_id, SLOTS_XP)
        slot_row = '| ' + ' | '.join(row) + ' |'
        color = discord.Color.green() if payout > 0 else discord.Color.red()
        embed = discord.Embed(title="Slots Result", description=f"{slot_row}\n{result_msg}", color=color)
        embed.set_footer(text="Try /slots for the animated version!")
        await ctx.send(embed=embed)
        # At the end, set cooldown
        self.cooldowns[f"{user_id}:slots"] = datetime.utcnow() + timedelta(seconds=20)

async def setup_slots_command(bot):
    cog = Slots(bot)
    await bot.add_cog(cog)
    bot.add_command(cog.slots_text)

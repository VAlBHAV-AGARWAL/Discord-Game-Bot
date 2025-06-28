import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from common.database.database import get_balance, add_coins, remove_coins, add_xp
from datetime import datetime, timedelta

COIN_EMOJI = "🪙"
CURRENCY_NAME = "Coins"
COINFLIP_XP = 5

class Coinflip(commands.Cog):
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

    @app_commands.command(name="coinflip", description="Gamble your coins on a coin flip!")
    @app_commands.describe(amount="Amount of coins to bet", choice="Your guess: heads or tails")
    async def coinflip(self, interaction: discord.Interaction, amount: int, choice: str):
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        username = interaction.user.display_name
        if await self._check_cooldown(interaction, user_id, 'coinflip'):
            return
        choice = choice.lower()
        if amount <= 0:
            embed = discord.Embed(description="Amount must be positive.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        if choice not in ["heads", "tails", "head", "tail","h", "t"]:
            embed = discord.Embed(description="Choice must be 'heads' or 'tails'.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        if get_balance(user_id, guild_id) < amount:
            embed = discord.Embed(description="You don't have enough coins!", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        # Normalize choice
        user_choice = "heads" if choice.startswith("head") else "tails"
        await interaction.response.send_message(f"Flipping the coin... {COIN_EMOJI}", ephemeral=False)
        await asyncio.sleep(2)
        result = random.choice(["heads", "tails"])
        result_emoji = "Heads" if result == "heads" else "Tails"
        win = (user_choice == result)
        embed = discord.Embed(color=discord.Color.yellow())
        embed.description = (
            f"{username} spent {amount} {COIN_EMOJI} and chose {user_choice}\n"
            f"The coin spins... {result_emoji} "
        )
        if win:
            add_coins(user_id, guild_id, amount * 2)
            add_xp(user_id, guild_id, COINFLIP_XP)
            embed.description += f"and you won {amount * 2} {COIN_EMOJI}!"
        else:
            remove_coins(user_id, guild_id, amount)
            add_xp(user_id, guild_id, COINFLIP_XP)
            embed.description += f"and you lost it all... 😔"
        await interaction.edit_original_response(content=None, embed=embed)
        # At the end, set cooldown
        self.cooldowns[f"{user_id}:coinflip"] = datetime.utcnow() + timedelta(seconds=20)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type.name == "component" and interaction.data.get("custom_id") == "play_again_coinflip":
            user_id = interaction.user.id
            # Only allow the original user to play again
            # Try to extract bet and choice from embed (not perfect, but works for now)
            if hasattr(interaction.message, 'embeds') and interaction.message.embeds:
                desc = interaction.message.embeds[0].description
                import re
                match = re.search(r"spent (\d+) .* and chose (\w+)", desc)
                if match:
                    amount = int(match.group(1))
                    choice = match.group(2)
                    await self.coinflip(interaction, amount, choice)
                else:
                    await interaction.response.send_message("Could not determine bet/choice for replay.", ephemeral=True)
        elif interaction.type == discord.InteractionType.application_command:
            # Reset cooldowns for slash command usage
            user_id = interaction.user.id
            self.cooldowns.pop(f"{user_id}:coinflip", None)

    @commands.command(name="coinflip", aliases=["cf"], help="Flip a coin and bet coins. Usage: !coinflip <h/t> <amount> or !cf <amount> <h/t>")
    async def coinflip_text(self, ctx, arg1: str = None, arg2: str = None):
        user_id = ctx.author.id
        if await self._check_cooldown(ctx, user_id, 'coinflip'):
            return
        valid_heads = ["h", "head", "heads"]
        valid_tails = ["t", "tail", "tails"]
        side = None
        amount = None
        # Try to parse both orders
        if arg1 is None or arg2 is None:
            embed = discord.Embed(description="Usage: !coinflip <h/t> <amount> or !cf <amount> <h/t> (e.g. !cf h 50 or !cf 50 h)", color=discord.Color.orange())
            embed.set_author(name="Coinflip Game", icon_url=getattr(ctx.guild.me, 'avatar', None))
            embed.set_footer(text="Try /coinflip for the animated version!")
            await ctx.send(embed=embed)
            return
        # Determine which arg is side and which is amount
        if arg1.lower() in valid_heads + valid_tails:
            side = arg1.lower()
            try:
                amount = int(arg2)
            except Exception:
                amount = None
        elif arg2.lower() in valid_heads + valid_tails:
            side = arg2.lower()
            try:
                amount = int(arg1)
            except Exception:
                amount = None
        else:
            embed = discord.Embed(description="You must choose either head(s) or tail(s) (h/t) and a valid amount. Example: !cf h 50 or !cf 50 h", color=discord.Color.red())
            embed.set_author(name="Coinflip Game", icon_url=getattr(ctx.guild.me, 'avatar', None))
            await ctx.send(embed=embed)
            return
        if side in valid_heads:
            user_choice = "heads"
        elif side in valid_tails:
            user_choice = "tails"
        else:
            embed = discord.Embed(description="You must choose either head(s) or tail(s) (h/t). Example: !cf h 50 or !cf 50 h", color=discord.Color.red())
            embed.set_author(name="Coinflip Game", icon_url=getattr(ctx.guild.me, 'avatar', None))
            await ctx.send(embed=embed)
            return
        if amount is None or amount <= 0:
            embed = discord.Embed(description="Amount must be positive.", color=discord.Color.red())
            embed.set_author(name="Coinflip Game", icon_url=getattr(ctx.guild.me, 'avatar', None))
            await ctx.send(embed=embed)
            return
        guild_id = ctx.guild.id if ctx.guild else 0
        if get_balance(user_id, guild_id) < amount:
            embed = discord.Embed(description="You don't have enough coins!", color=discord.Color.red())
            embed.set_author(name="Coinflip Game", icon_url=getattr(ctx.guild.me, 'avatar', None))
            await ctx.send(embed=embed)
            return
        # Animated version for text command
        flipping_msg = await ctx.send(f"Flipping the coin... {COIN_EMOJI}")
        await asyncio.sleep(2)
        result = random.choice(["heads", "tails"])
        win = (user_choice == result)
        if win:
            add_coins(user_id, guild_id, amount * 2)
            add_xp(user_id, guild_id, COINFLIP_XP)
            embed = discord.Embed(title="Coinflip Result", description=f"🪙 {ctx.author.display_name} chose {user_choice}. The coin landed on {result}. You won {amount * 2} {CURRENCY_NAME}!", color=discord.Color.green())
            embed.set_footer(text="Try /coinflip for the animated version!")
        else:
            remove_coins(user_id, guild_id, amount)
            add_xp(user_id, guild_id, COINFLIP_XP)
            embed = discord.Embed(title="Coinflip Result", description=f"🪙 {ctx.author.display_name} chose {user_choice}. The coin landed on {result}. You lost your bet.", color=discord.Color.red())
            embed.set_footer(text="Try /coinflip for the animated version!")
        await flipping_msg.edit(content=None, embed=embed)
        # At the end, set cooldown
        self.cooldowns[f"{user_id}:coinflip"] = datetime.utcnow() + timedelta(seconds=20)

async def setup_coinflip_command(bot):
    cog = Coinflip(bot)
    await bot.add_cog(cog)
    bot.add_command(cog.coinflip_text)

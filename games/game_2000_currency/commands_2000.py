import discord
from discord.ext import commands
from discord import app_commands
import time
from common.database import database
from common.database.database import get_balance, add_coins, remove_coins, get_last_daily, set_last_daily, get_last_weekly, set_last_weekly, get_level, get_xp, add_xp, xp_for_next_level
from datetime import datetime, timezone

COIN_EMOJI = "🪙"
CURRENCY_NAME = "Coins"
DAILY_AMOUNT = 100
WEEKLY_AMOUNT = 700
XP_DAILY = 20
XP_WEEKLY = 100
XP_GIVE = 5
XP_REQUEST = 2
LEVEL_MULTIPLIER = 0.05  # 5% per level above 1

class Currency(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="coins", description="Check your coin balance.")
    async def coins(self, interaction: discord.Interaction):
        bal = get_balance(interaction.user.id, interaction.guild.id)
        embed = discord.Embed(
            title=f"{COIN_EMOJI} Your Coins",
            description=f"**{bal} {COIN_EMOJI}**",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Earn more coins by playing games or claiming daily/weekly rewards!")
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="give", description="Give coins to another user.")
    @app_commands.describe(user="User to give coins to", amount="Amount of coins to give")
    async def give(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if user.id == interaction.user.id:
            embed = discord.Embed(description="You can't give coins to yourself!", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        if amount <= 0:
            embed = discord.Embed(description="Amount must be positive.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        if remove_coins(interaction.user.id, interaction.guild.id, amount):
            add_coins(user.id, interaction.guild.id, amount)
            add_xp(interaction.user.id, interaction.guild.id, XP_GIVE)
            embed = discord.Embed(
                description=f"{interaction.user.display_name} gave {amount} {COIN_EMOJI} to {user.display_name}",
                color=discord.Color.gold()
            )
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(description="You don't have enough coins!", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="request", description="Request coins from another user.")
    @app_commands.describe(user="User to request coins from", amount="Amount of coins to request")
    async def request(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if user.id == interaction.user.id:
            await interaction.response.send_message("You can't request coins from yourself!", ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message("Amount must be positive.", ephemeral=True)
            return
        add_xp(interaction.user.id, interaction.guild.id, XP_REQUEST)
        embed = discord.Embed(
            description=f"{user.mention}, {interaction.user.mention} is requesting {amount} {CURRENCY_NAME} from you!\nReact with ✅ to pay or ❌ to decline.",
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

        def check(reaction, reactor):
            return (
                reaction.message.id == msg.id and
                reactor.id == user.id and
                str(reaction.emoji) in ["✅", "❌"]
            )

        try:
            reaction, reactor = await interaction.client.wait_for(
                "reaction_add", timeout=60.0, check=check
            )
        except Exception:
            await msg.edit(embed=discord.Embed(description=f"Request expired. No response from {user.mention}.", color=discord.Color.red()))
            return

        if str(reaction.emoji) == "✅":
            if remove_coins(user.id, interaction.guild.id, amount):
                add_coins(interaction.user.id, interaction.guild.id, amount)
                embed = discord.Embed(
                    description=f"{user.display_name} paid {amount} {COIN_EMOJI} to {interaction.user.display_name}.",
                    color=discord.Color.green()
                )
                await msg.edit(embed=embed)
            else:
                embed = discord.Embed(
                    description=f"{user.display_name} does not have enough coins to pay!",
                    color=discord.Color.red()
                )
                await msg.edit(embed=embed)
        else:
            embed = discord.Embed(
                description=f"{user.display_name} declined the request.",
                color=discord.Color.red()
            )
            await msg.edit(embed=embed)

    @app_commands.command(name="daily", description="Claim your daily coins reward.")
    async def daily(self, interaction: discord.Interaction):
        from common.database.database import get_last_daily, set_last_daily
        now = datetime.now(timezone.utc)
        last = get_last_daily(interaction.user.id, interaction.guild.id)
        if last and isinstance(last, int):
            last = datetime.fromtimestamp(last, tz=timezone.utc)
        elif last and isinstance(last, str):
            try:
                last = datetime.fromisoformat(last)
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
            except Exception:
                last = None
        if last and (now - last).total_seconds() < 86400:
            seconds_left = 86400 - int((now - last).total_seconds())
            hours, remainder = divmod(seconds_left, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_left = f"{hours}h {minutes}m {seconds}s"
            embed = discord.Embed(description=f"⏰ You have already claimed your daily reward! Come back in **{time_left}**.", color=discord.Color.orange())
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        set_last_daily(interaction.user.id, interaction.guild.id, now)
        add_coins(interaction.user.id, interaction.guild.id, 100)
        embed = discord.Embed(description=f"🎁 You claimed your daily reward: **100 {COIN_EMOJI}**!", color=discord.Color.green())
        embed.set_footer(text="Come back tomorrow for more coins!")
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="weekly", description="Claim your weekly coins reward.")
    async def weekly(self, interaction: discord.Interaction):
        from common.database.database import get_last_weekly, set_last_weekly
        now = datetime.now(timezone.utc)  # <-- FIXED
        last = get_last_weekly(interaction.user.id, interaction.guild.id)
        if last and isinstance(last, int):
            last = datetime.fromtimestamp(last, tz=timezone.utc)
        if last and (now - last).total_seconds() < 604800:
            seconds_left = 604800 - int((now - last).total_seconds())
            hours, remainder = divmod(seconds_left, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_left = f"{hours}h {minutes}m {seconds}s"
            embed = discord.Embed(description=f"⏰ You have already claimed your weekly reward! Come back in **{time_left}**.", color=discord.Color.orange())
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        set_last_weekly(interaction.user.id, interaction.guild.id, now)
        add_coins(interaction.user.id, interaction.guild.id, 500)
        embed = discord.Embed(description=f"🎉 You claimed your weekly reward: **500 {COIN_EMOJI}**!", color=discord.Color.green())
        embed.set_footer(text="Come back next week for more coins!")
        await interaction.response.send_message(embed=embed, ephemeral=False)

    # @app_commands.command(name="lvl", ...) is already registered in common/commands/lvl.py
    # Remove this duplicate to avoid Command 'lvl' already registered error.

    @commands.command(name="bal", help="Check your coin balance.")
    async def bal_text(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        bal = get_balance(user.id, ctx.guild.id)
        embed = discord.Embed(
            description=f"{user.display_name} has {bal} {COIN_EMOJI}",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)

async def setup_currency_commands(bot):
    await bot.add_cog(Currency(bot))

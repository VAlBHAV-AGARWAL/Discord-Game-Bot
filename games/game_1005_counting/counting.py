import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import time
import os
import logging
from common.utils import persistent_state
from common.utils.localization import localization
from common.database.database import add_xp, get_level, add_coins

COUNTING_STATE_FILE = os.path.join(os.path.dirname(__file__), 'counting_state.json')
TICK_EMOJI = "✅"
CROSS_EMOJI = "❌"
DEFAULT_COOLDOWN = 15 * 60  # 15 minutes
MILESTONES = [100, 500, 1000, 5000, 10000]
REWARD_ROLE_NAME = "Counting Champion"
COUNT_XP = 5
COUNT_COIN_BASE = 2
LEVEL_MULTIPLIER = 0.05
logger = logging.getLogger("discord_bot")

class Counting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.state = persistent_state.load_state(COUNTING_STATE_FILE, default={})

    def save(self):
        persistent_state.save_state(COUNTING_STATE_FILE, self.state)

    def get_locale(self, guild_id):
        # Example: get language from state or config, fallback to English
        lang = self.state.get(guild_id, {}).get('lang', 'en')
        return lambda key, **kwargs: localization.get(key, lang=lang, **kwargs)

    @app_commands.command(name="counting", description="Set or reset the counting channel.")
    @app_commands.describe(channel="Channel to use for counting", reset="Reset the counting game")
    async def counting(self, interaction: discord.Interaction, channel: discord.TextChannel = None, reset: bool = False):
        guild_id = str(interaction.guild.id)
        locale = self.get_locale(guild_id)
        if reset:
            if guild_id in self.state:
                del self.state[guild_id]
                self.save()
            embed = discord.Embed(description=locale('reset'), color=discord.Color.blurple())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        elif channel:
            self.state[guild_id] = {"channel_id": channel.id, "last_number": 0, "last_user": None, "user_timestamps": {}, "highest_streak": 0, "contributions": {}, "cooldown": DEFAULT_COOLDOWN}
            self.save()
            embed = discord.Embed(description=locale('set_channel', channel=channel.mention), color=discord.Color.blurple())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(description="Please specify a channel or use reset.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="counting_set_cooldown", description="Set the cooldown (admin only)")
    @app_commands.describe(minutes="Cooldown in minutes")
    async def counting_set_cooldown(self, interaction: discord.Interaction, minutes: int):
        guild_id = str(interaction.guild.id)
        locale = self.get_locale(guild_id)
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(description=locale('no_permission'), color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        if guild_id not in self.state:
            embed = discord.Embed(description="Counting game not set up.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        self.state[guild_id]["cooldown"] = minutes * 60
        self.save()
        embed = discord.Embed(description=locale('set_cooldown', minutes=minutes), color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="counting_leaderboard", description="Show the counting leaderboard")
    async def counting_leaderboard(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        locale = self.get_locale(guild_id)
        state = self.state.get(guild_id, {})
        contrib = state.get("contributions", {})
        if not contrib:
            embed = discord.Embed(description=locale('no_stats'), color=discord.Color.blurple())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        sorted_stats = sorted(contrib.items(), key=lambda x: (-x[1].get('streak', 0), -x[1].get('contrib', 0)))
        desc = ""
        for i, (uid, data) in enumerate(sorted_stats[:10], 1):
            member = interaction.guild.get_member(int(uid))
            mention = member.mention if member else f"<@{uid}>"
            desc += locale('leaderboard_entry', rank=i, mention=mention, streak=data.get('streak', 0), contrib=data.get('contrib', 0)) + "\n"
        embed = discord.Embed(title=locale('leaderboard_title'), description=desc, color=discord.Color.gold())
        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        guild_id = str(message.guild.id)
        if guild_id not in self.state:
            return
        state = self.state[guild_id]
        if message.channel.id != state["channel_id"]:
            return
        locale = self.get_locale(guild_id)
        try:
            number = int(message.content.strip())
        except ValueError:
            return  # Ignore non-number messages
        last_number = state.get("last_number", 0)
        last_user = state.get("last_user", None)
        user_timestamps = state.setdefault("user_timestamps", {})
        now = time.time()
        cooldown = state.get("cooldown", DEFAULT_COOLDOWN)
        # Cooldown check
        last_time = user_timestamps.get(str(message.author.id), 0)
        if now - last_time < cooldown:
            await message.add_reaction(CROSS_EMOJI)
            embed = discord.Embed(
                description=locale('wait_cooldown', mention=message.author.mention, minutes=int(cooldown/60)),
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed, delete_after=10)
            try:
                await message.delete()
            except Exception:
                pass
            return
        # Accept the next number if it is last_number + 1
        if number == last_number + 1:
            await message.add_reaction(TICK_EMOJI)
            state["last_number"] = number
            state["last_user"] = message.author.id
            user_timestamps[str(message.author.id)] = now
            # Stats
            contrib = state.setdefault("contributions", {})
            user_stats = contrib.setdefault(str(message.author.id), {"streak": 0, "contrib": 0})
            user_stats["contrib"] += 1
            user_stats["streak"] = user_stats.get("streak", 0) + 1
            # Highest streak
            if user_stats["streak"] > state.get("highest_streak", 0):
                state["highest_streak"] = user_stats["streak"]
            # XP and coin reward
            level = get_level(message.author.id, message.guild.id)
            coin_reward = level  # 1 coin per level
            xp_reward = level    # 1 xp per level
            add_xp(message.author.id, message.guild.id, xp_reward)
            add_coins(message.author.id, message.guild.id, coin_reward)
            # Milestone
            if number in MILESTONES:
                await message.channel.send(locale('milestone', number=number))
                # Role reward
                role = discord.utils.get(message.guild.roles, name=REWARD_ROLE_NAME)
                if not role:
                    try:
                        role = await message.guild.create_role(name=REWARD_ROLE_NAME, color=discord.Color.gold())
                    except Exception:
                        role = None
                if role:
                    try:
                        await message.author.add_roles(role, reason="Counting milestone reward")
                        await message.channel.send(locale('role_awarded', mention=message.author.mention, role=REWARD_ROLE_NAME, number=number))
                    except Exception:
                        pass
            self.save()
        else:
            await message.add_reaction(CROSS_EMOJI)
            # Penalty for ruining the count
            level = get_level(message.author.id, message.guild.id)
            coin_reward = level
            penalty = coin_reward * 10
            from common.database.database import remove_coins
            remove_coins(message.author.id, message.guild.id, penalty)
            embed = discord.Embed(
                description=f"{message.author.mention} ruined the count and lost {penalty} coins as a penalty! Start the count again from 1.",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)
            try:
                await message.delete()
            except Exception:
                pass
            state["last_number"] = 0
            state["last_user"] = None
            state["user_timestamps"] = {}
            # Reset all streaks
            for u in state.get("contributions", {}).values():
                u["streak"] = 0
            self.save()

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        # Only act if the deleted message was a user counting message in the counting channel
        if not message.guild or message.author.bot:
            return
        guild_id = str(message.guild.id)
        if guild_id not in self.state:
            return
        state = self.state[guild_id]
        if message.channel.id != state.get("channel_id"):
            return
        # Only act if the message was a valid number (not a bot message)
        try:
            int(message.content.strip())
        except Exception:
            return
        # Remove the anti-cheat warning for bot message deletions
        # Optionally: log or ignore silently
        # (No warning message)
        return

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        # Anti-cheat: warn if a counting message is edited
        if after.guild and str(after.guild.id) in self.state:
            state = self.state[str(after.guild.id)]
            if after.channel.id == state.get("channel_id"):
                await after.channel.send(f"{after.author.mention} edited a counting message. Cheating is not allowed!")

    # The /suggest command has been moved to common/utils/suggest.py and is no longer implemented here.

async def setup(bot):
    await bot.add_cog(Counting(bot))

import discord
from discord import app_commands
from discord.ext import commands
from common.database.database import get_level, get_xp, xp_for_next_level

class Level(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="lvl", description="Show your level and XP progress.")
    @app_commands.describe(user="User to check (optional)")
    async def lvl(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        level = get_level(user.id, interaction.guild.id)
        xp = get_xp(user.id, interaction.guild.id)
        next_xp = xp_for_next_level(level)
        embed = discord.Embed(title=f"Level for {user.display_name}", color=discord.Color.blue())
        embed.add_field(name="Level", value=str(level))
        embed.add_field(name="XP", value=f"{xp} / {next_xp}")
        embed.set_footer(text="Earn XP by playing games and using commands!")
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup_level_command(bot):
    await bot.add_cog(Level(bot))

import logging
from common.utils.challenge_system import accept_challenge, decline_challenge

logger = logging.getLogger("discord_bot")

def register_accept_decline_commands(bot):
    @bot.command(name="matching_accept", help="Accept a pending Memory Match challenge")
    async def matching_accept(ctx):
        """Accept a pending Memory Match challenge."""
        success = await accept_challenge(ctx, ctx.author)
        if success:
            await ctx.send("Challenge accepted!", ephemeral=True)
    
    @bot.command(name="matching_decline", help="Decline a pending Memory Match challenge")
    async def matching_decline(ctx):
        """Decline a pending Memory Match challenge."""
        success = await decline_challenge(ctx, ctx.author)
        if success:
            await ctx.send("Challenge declined.", ephemeral=True)
    
    return matching_accept, matching_decline

# For direct import
matching_accept, matching_decline = None, None
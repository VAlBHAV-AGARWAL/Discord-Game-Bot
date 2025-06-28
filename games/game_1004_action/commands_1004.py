import os
import discord
from discord.ext import commands
import random
import aiohttp
from dotenv import load_dotenv
from datetime import datetime, timedelta
import asyncio

load_dotenv()
TENOR_API_KEY = os.getenv("TENOR_API_KEY")

# List of supported actions
ACTIONS = [
    "cuddle", "hug", "Laugh", "dance", "kick", "kiss", "lick", "nom", "pat", "poke", "slap", "stare", "highfive", "bite", "Hello", "punch", "handholding", "tickle", "kill", "hold", "pats", "wave", "boop", "snuggle", "bully"
]

# Example funny comments for each action
FUNNY_COMMENTS = {
    "cuddle": "{p1} cuddles {p2}! So warm and fuzzy!",
    "hug": "{p1} gives {p2} a big hug!",
    "kiss": "{p1} kisses {p2}! Smooch!",
    "lick": "{p1} licks {p2}! That's a bit weird...",
    "nom": "*nom nom* {p1} noms {p2}!",
    "pat": "Good job {p2}, here here, a pat from {p1}",
    "poke": "{p1} pokes {p2}! Are you awake?",
    "slap": "{p1} slapped {p2}! You deserve it!",
    "stare": "{p1} stares at {p2}! Are you For Real...",
    "highfive": "{p1} gives {p2} a high five! Up top!",
    "bite": "{p1} bites {p2}! Chomp!",
    "Hello": "{p1} greets {p2}! A wild greeting appears!",
    "punch": "{p1} punches {p2}! POW! Right in the kisser!",
    "handholding": "{p1} holds hands with {p2}! How lewd!",
    "tickle": "{p1} tickles {p2}! Can't stop laughing!",
    "kill": "{p1} kills {p2}! Oh no! That's a bit too far...",
    "hold": "{p1} holds {p2} tightly!",
    "pats": "{p1} gives {p2} lots of pats!",
    "wave": "{p1} waves at {p2}! Waving hello!",
    "boop": "{p1} boops {p2} right on the nose!",
    "snuggle": "{p1} snuggles {p2}! Snuggle time!",
    "bully": "{p1} bullies {p2}! Bully mode activated!",
    "Laugh": "{p1} laughs at {p2}! That's hilarious!",
    "dance": "{p1} dances with {p2}! Let's groove!",
    "kick": "{p1} kicks {p2}! Ouch! That must hurt!",
}

# Helper to fetch a random Tenor GIF URL for an action
async def fetch_tenor_gif(action: str) -> str:
    if not TENOR_API_KEY:
        return None
    query = f"anime {action}"
    url = f"https://tenor.googleapis.com/v2/search?q={query}&key={TENOR_API_KEY}&limit=20&media_filter=gif"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            results = data.get("results", [])
            if not results:
                return None
            gif = random.choice(results)
            media_formats = gif.get("media_formats", {})
            gif_url = None
            if "gif" in media_formats:
                gif_url = media_formats["gif"].get("url")
            elif "mediumgif" in media_formats:
                gif_url = media_formats["mediumgif"].get("url")
            return gif_url
    return None

# Add a cooldowns dict to the module
action_cooldowns = {}  # {user_id: datetime}

async def _check_action_cooldown(ctx, user_id, action):
    now = datetime.utcnow()
    key = f"{user_id}:{action}"
    cooldown_until = action_cooldowns.get(key)
    if cooldown_until and cooldown_until > now:
        seconds_left = int((cooldown_until - now).total_seconds())
        msg = await ctx.send(f"I understand the Rush but calm down, Let me breath, try again in {seconds_left} seconds.")
        for i in range(seconds_left, 0, -1):
            await asyncio.sleep(1)
            await msg.edit(content=f"I understand the Rush but calm down, Let me breath, try again in {i-1} seconds.")
        await msg.delete()
        return True
    return False

# Main setup function for the bot
def setup(bot):
    for action in ACTIONS:
        async def action_command(ctx, member: discord.Member = None, action=action):
            if member is None or member == ctx.author:
                await ctx.send(f"You can't {action} yourself! Try mentioning someone else.")
                return
            gif_url = await fetch_tenor_gif(action)
            if not gif_url:
                await ctx.send(f"No GIF found for {action}.")
                return
            p1 = ctx.author.display_name
            p2 = member.display_name
            comment = FUNNY_COMMENTS.get(action, f"{action.title()} time!")
            embed = discord.Embed(
                title=comment.format(p1=p1, p2=p2),
                color=discord.Color.random()
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        bot.command(name=action)(action_command)

def setup_action_commands(bot):
    for action in ACTIONS:
        async def action_command(ctx, member: discord.Member = None, action=action):
            user_id = ctx.author.id
            if await _check_action_cooldown(ctx, user_id, action):
                return
            if member is None or member == ctx.author:
                await ctx.send(f"You can't {action} yourself! Try mentioning someone else.")
                return
            gif_url = await fetch_tenor_gif(action)
            if not gif_url:
                await ctx.send(f"No GIF found for {action}.")
                return
            p1 = ctx.author.display_name
            p2 = member.display_name
            comment = FUNNY_COMMENTS.get(action, f"{action.title()} time!")
            embed = discord.Embed(
                title=comment.format(p1=p1, p2=p2),
                color=discord.Color.random()
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
            # Set cooldown at the end
            action_cooldowns[f"{user_id}:{action}"] = datetime.utcnow() + timedelta(seconds=20)
        bot.command(name=action)(action_command)

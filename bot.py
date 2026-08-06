import discord
from discord.ext import commands
from discord import app_commands
import anthropic
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

@bot.event
async def on_ready():
    print(f"✅ {bot.user} online")
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"❌ Sync error: {e}")

def rewrite_review(raw_message: str, stars: int) -> str:
    star_emoji = "⭐" * stars + "☆" * (5 - stars)
    
    prompt = f"""Rewrite this review professionally. Keep it genuine, concise (2-4 sentences), 
and compelling. Improve grammar and flow without changing the core message.

Rating: {star_emoji} ({stars}/5)
Raw review: {raw_message}

ONLY output the rewritten review. Nothing else."""
    
    try:
        msg = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text.strip()
    except Exception as e:
        print(f"❌ Claude error: {e}")
        return raw_message

@bot.tree.command(name="vouch", description="Transform your review into a polished masterpiece")
@app_commands.describe(
    message="Your raw review text",
    stars="Rating: 1 to 5 stars",
    screenshot="Screenshot URL (optional)"
)
async def vouch(
    interaction: discord.Interaction,
    message: str,
    stars: int,
    screenshot: str = None
):
    if not 1 <= stars <= 5:
        await interaction.response.send_message(
            "❌ Stars must be between 1 and 5",
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    polished = rewrite_review(message, stars)
    
    star_display = "⭐" * stars + "☆" * (5 - stars)
    
    embed = discord.Embed(
        title="✨ Review Posted",
        description=polished,
        color=discord.Color.gold()
    )
    embed.add_field(name="Rating", value=star_display, inline=False)
    embed.add_field(name="By", value=interaction.user.mention, inline=True)
    embed.add_field(name="Timestamp", value=f"<t:{int(interaction.created_at.timestamp())}:R>", inline=True)
    
    if screenshot:
        embed.set_image(url=screenshot)
    
    embed.set_footer(text="Powered by Review Bot | Claude Rewrite")
    
    await interaction.followup.send(embed=embed)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

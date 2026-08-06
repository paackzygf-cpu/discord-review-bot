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
CUSTOMER_ROLE_ID = 1526624357370171423
REVIEWS_CHANNEL_ID = 1526624416073777253
LAST_VOUCH_MESSAGE_ID = None

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

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

class VouchModal(discord.ui.Modal):
    def __init__(self, parent_view):
        super().__init__(title="LEAVE A VOUCH")
        self.parent_view = parent_view
        self.review_input = discord.ui.TextInput(
            label="Your Review",
            placeholder="Write your honest review here...",
            required=True,
            max_length=1000,
            style=discord.TextStyle.paragraph,
            min_length=10
        )
        self.stars_input = discord.ui.TextInput(
            label="Rating (1-5 stars)",
            placeholder="Enter: 1, 2, 3, 4, or 5",
            required=True,
            max_length=1
        )
        self.add_item(self.review_input)
        self.add_item(self.stars_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            stars = int(self.stars_input.value)
            if not 1 <= stars <= 5:
                await interaction.response.send_message("❌ Rating must be between 1 and 5", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Rating must be a number (1-5)", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        polished = rewrite_review(self.review_input.value, stars)
        star_display = "⭐" * stars + "☆" * (5 - stars)
        
        embed = discord.Embed(
            title="✨ Review Posted",
            description=polished,
            color=discord.Color.gold()
        )
        embed.add_field(name="Rating", value=star_display, inline=False)
        embed.add_field(name="By", value=interaction.user.mention, inline=True)
        embed.add_field(name="Timestamp", value=f"<t:{int(interaction.created_at.timestamp())}:R>", inline=True)
        embed.set_thumbnail(url=interaction.user.avatar.url)
        
        reviews_channel = bot.get_channel(REVIEWS_CHANNEL_ID)
        if reviews_channel:
            await reviews_channel.send(embed=embed)
        
        await interaction.response.send_message("✅ Review posted in #reviews!", ephemeral=True)

class VouchButton(discord.ui.View):
    def __init__(self, channel):
        super().__init__(timeout=None)
        self.channel = channel
    
    @discord.ui.button(label="Leave a vouch", emoji="⭐", style=discord.ButtonStyle.primary)
    async def vouch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        customer_role = interaction.guild.get_role(CUSTOMER_ROLE_ID)
        if not customer_role or customer_role not in interaction.user.roles:
            await interaction.response.send_message(
                f"❌ Only members with the <@&{CUSTOMER_ROLE_ID}> role can leave a vouch",
                ephemeral=True
            )
            return
        
        await interaction.response.send_modal(VouchModal(self))

@bot.tree.command(name="vouch", description="Leave a review with stars and optional screenshot")
@app_commands.describe(
    message="Your review (required)",
    stars="Rating 1-5 (required)",
    screenshot="Upload a screenshot (optional)"
)
async def vouch(
    interaction: discord.Interaction,
    message: str,
    stars: int,
    screenshot: discord.Attachment = None
):
    customer_role = interaction.guild.get_role(CUSTOMER_ROLE_ID)
    if not customer_role or customer_role not in interaction.user.roles:
        await interaction.response.send_message(
            f"❌ Only members with the <@&{CUSTOMER_ROLE_ID}> role can leave a vouch",
            ephemeral=True
        )
        return
    
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
    embed.set_thumbnail(url=interaction.user.avatar.url)
    
    if screenshot:
        embed.set_image(url=screenshot.url)
    
    reviews_channel = bot.get_channel(REVIEWS_CHANNEL_ID)
    if reviews_channel:
        await reviews_channel.send(embed=embed)
    
    await interaction.response.send_message("✅ Review posted in #reviews!", ephemeral=True)

@bot.tree.command(name="init_vouch", description="Initialize the vouch panel (admin only)")
@app_commands.checks.has_permissions(manage_messages=True)
async def init_vouch(interaction: discord.Interaction):
    reviews_channel = bot.get_channel(REVIEWS_CHANNEL_ID)
    if not reviews_channel:
        await interaction.response.send_message("❌ Reviews channel not found", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="WANT TO LEAVE A VOUCH ?",
        description="Use the button below.\nChoose a rating, write your review, and add screenshots if needed.",
        color=discord.Color.gold()
    )
    
    await reviews_channel.send(embed=embed, view=VouchButton(reviews_channel))
    await interaction.response.send_message("✅ Vouch panel initialized in #reviews!", ephemeral=True)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

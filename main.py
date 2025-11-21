import discord
from discord.ext import commands
from discord import app_commands, Message
import csv
import os
import re
from dotenv import load_dotenv


load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


def csv_path(guild_id: int) -> str:
    return f"{guild_id}.csv"


def ensure_csv_exists(guild_id: int):
    path = csv_path(guild_id)
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["message", "mentions", "extra"])  # CSV header


def extract_mentions(msg: discord.Message):
    mentions = [f"@{m.name}" for m in msg.mentions]
    text_no_mentions = re.sub(r"<@!?\d+>", "", msg.content).strip()
    return text_no_mentions, ",".join(mentions)


@bot.event
async def on_ready():
    print(f"Bot connecté : {bot.user}")

    # Create CSV for each guild the bot is in
    for guild in bot.guilds:
        ensure_csv_exists(guild.id)

    try:
        synced = await bot.tree.sync()
        print(f"Slash commands synchronisés ({len(synced)})")
    except Exception as e:
        print("Erreur sync:", e)


# ================
#  COMMAND: /scrap
# ================

@bot.tree.command(name="scrap", description="Scrape the channel and send the CSV.")
async def scrap(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    guild_id = interaction.guild.id
    ensure_csv_exists(guild_id)
    path = csv_path(guild_id)

    rows = []

    async for msg in interaction.channel.history(limit=None):
        text, ats = extract_mentions(msg)
        rows.append([text, ats, ""])

    # Write new CSV
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["message", "mentions", "extra"])
        writer.writerows(rows)

    await interaction.followup.send(
        content="Voici ton CSV 👇",
        file=discord.File(path)
    )


# =========================
#  COMMAND: /from_file
# =========================

@bot.tree.command(name="download", description="download the csv")
async def download(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    guild_id = interaction.guild.id
    ensure_csv_exists(guild_id)
    path = csv_path(guild_id)
    await interaction.followup.send(
        content="voici ton CSV",
        file=discord.File(path)
    )

@bot.tree.command(name="from_file", description="Add rows from an uploaded CSV file.")
@app_commands.describe(csv_file="Le fichier CSV à importer")
async def from_file(interaction: discord.Interaction, csv_file: discord.Attachment):
    if not csv_file.filename.endswith(".csv"):
        return await interaction.response.send_message("Le fichier doit être un CSV.", ephemeral=True)

    await interaction.response.defer(thinking=True)

    guild_id = interaction.guild.id
    ensure_csv_exists(guild_id)
    path = csv_path(guild_id)

    # Download file
    data = await csv_file.read()
    tmp_name = "upload_temp.csv"
    with open(tmp_name, "wb") as f:
        f.write(data)

    # Append rows
    with open(tmp_name, "r", encoding="utf-8") as f_in, \
         open(path, "a", newline="", encoding="utf-8") as f_out:

        reader = csv.reader(f_in)
        writer = csv.writer(f_out)

        next(reader, None)  # skip header
        for row in reader:
            writer.writerow(row)

    os.remove(tmp_name)

    await interaction.followup.send("L'importation est faite ✔️")


# ======================
#   COMMAND: /add
# ======================


@bot.tree.context_menu(name="Add to CSV")
async def add_context_menu(interaction: discord.Interaction, message: discord.Message):
    # This function is triggered when user right-clicks a message > Apps > Add to CSV
    extra_modal = ExtraInputModal(message)
    await interaction.response.send_modal(extra_modal)


class ExtraInputModal(discord.ui.Modal, title="Add info to CSV"):
    extra_field = discord.ui.TextInput(
        label="Extra info, like the person if not already @",
        placeholder="Optional additional text",
        required=False
    )

    def __init__(self, message: discord.Message):
        super().__init__()
        self.message = message

    async def on_submit(self, interaction: discord.Interaction):
        # Extract message info
        text, ats = extract_mentions(self.message)

        # 2) Extra text
        extra_text = self.extra_field.value if self.extra_field.value else ""

        # 3) Write the line to CSV
        guild_id = interaction.guild.id
        ensure_csv_exists(guild_id)
        path = csv_path(guild_id)

        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([text, ats, extra_text if extra_text else ""])

        await interaction.response.send_message("Added to CSV ✔️", ephemeral=True)


bot.run(TOKEN)


import discord
from discord.ext import commands
from discord import app_commands
import random
import math
import os

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────
# READY
# ─────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(e)

# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
TEAL = 0x11F1D3

def make_embed(title, description=None):
    em = discord.Embed(title=title, description=description, color=TEAL)
    em.set_footer(text="⚠️ For fun only — predictions are random and not accurate")
    return em

def nCr(n, r):
    f = math.factorial
    return f(n) // f(r) // f(n - r)

def mines_multiplier(tiles_opened, num_mines):
    house_edge = 0.01
    return (0.99 - house_edge) * nCr(25, tiles_opened) / nCr(25 - num_mines, tiles_opened)

# ─────────────────────────────────────────
# /mines
# ─────────────────────────────────────────
@bot.tree.command(name="mines", description="Predict safe tiles in Bloxflip Mines (just for fun!)")
@app_commands.describe(
    num_mines="Number of mines (1-24)",
    tiles_to_open="How many tiles you want to open"
)
async def mines(interaction: discord.Interaction, num_mines: int, tiles_to_open: int):
    if not (1 <= num_mines <= 20):
        await interaction.response.send_message("❌ Mines must be between 1 and 20.", ephemeral=True)
        return
    if not (1 <= tiles_to_open <= 25 - num_mines):
        await interaction.response.send_message(f"❌ Tiles to open must be between 1 and {25 - num_mines}.", ephemeral=True)
        return

    all_tiles = list(range(1, 26))
    mine_positions = random.sample(all_tiles, num_mines)
    safe_tiles = [t for t in all_tiles if t not in mine_positions]
    suggested = random.sample(safe_tiles, min(tiles_to_open, len(safe_tiles)))

    win_chance = (nCr(25 - num_mines, tiles_to_open) / nCr(25, tiles_to_open)) * 100
    multiplier = mines_multiplier(tiles_to_open, num_mines)

    # Display tiles as a 5x5 grid
    grid = ""
    for i in range(1, 26):
        if i in suggested:
            grid += "💎 "
        else:
            grid += "⬜ "
        if i % 5 == 0:
            grid += "\n"

    em = make_embed("🎯 Mines Prediction")
    em.add_field(name="Suggested Safe Tiles", value=f"```{', '.join(map(str, sorted(suggested)))}```", inline=False)
    em.add_field(name="Grid", value=grid, inline=False)
    em.add_field(name="📊 Win Chance", value=f"`{win_chance:.1f}%`", inline=True)
    em.add_field(name="💰 Multiplier", value=f"`{multiplier:.2f}x`", inline=True)
    em.add_field(name="💣 Mines", value=f"`{num_mines}`", inline=True)

    await interaction.response.send_message(embed=em)

# ─────────────────────────────────────────
# /crash
# ─────────────────────────────────────────
@bot.tree.command(name="crash", description="See crash odds for a target multiplier (just for fun!)")
@app_commands.describe(multiplier="The crash multiplier you're targeting (e.g. 2.0)")
async def crash(interaction: discord.Interaction, multiplier: float):
    if multiplier < 1.01:
        await interaction.response.send_message("❌ Multiplier must be at least 1.01.", ephemeral=True)
        return

    chance = (1 - (1/33 + (32/33) * (0.01 + 0.99 * (1 - 1/multiplier)))) * 100
    predicted = round(random.uniform(1.0, multiplier * 1.5), 2)

    em = make_embed("📈 Crash Prediction")
    em.add_field(name="🎯 Target Multiplier", value=f"`{multiplier}x`", inline=True)
    em.add_field(name="🔮 Predicted Crash", value=f"`{predicted}x`", inline=True)
    em.add_field(
        name="📊 Odds of Reaching Target",
        value=f"`{chance:.2f}%` chance the game reaches `{multiplier}x` or higher",
        inline=False
    )

    color_bar = "🟢" * int(chance / 10) + "🔴" * (10 - int(chance / 10))
    em.add_field(name="Confidence", value=color_bar, inline=False)

    await interaction.response.send_message(embed=em)

# ─────────────────────────────────────────
# /roulette
# ─────────────────────────────────────────
ROULETTE_OPTIONS = ["🔴 Red", "⚫ Black", "🟢 Green"]
ROULETTE_WEIGHTS = [47, 47, 6]

@bot.tree.command(name="roulette", description="Predict the next Bloxflip roulette result (just for fun!)")
async def roulette(interaction: discord.Interaction):
    result = random.choices(ROULETTE_OPTIONS, weights=ROULETTE_WEIGHTS, k=1)[0]
    confidence = random.randint(55, 92)

    history = random.choices(ROULETTE_OPTIONS, weights=ROULETTE_WEIGHTS, k=5)
    history_str = " → ".join(history)

    em = make_embed("🎰 Roulette Prediction")
    em.add_field(name="🔮 Predicted Result", value=f"**{result}**", inline=True)
    em.add_field(name="📊 Confidence", value=f"`{confidence}%`", inline=True)
    em.add_field(name="📜 Simulated History", value=history_str, inline=False)

    await interaction.response.send_message(embed=em)

# ─────────────────────────────────────────
# /towers
# ─────────────────────────────────────────
DIFFICULTIES = {
    "easy": {"cols": 4, "safe": 3},
    "medium": {"cols": 4, "safe": 2},
    "hard": {"cols": 4, "safe": 1},
    "expert": {"cols": 4, "safe": 1},
}

@bot.tree.command(name="towers", description="Predict safe columns in Bloxflip Towers (just for fun!)")
@app_commands.describe(
    difficulty="Difficulty: easy, medium, hard, or expert",
    floors="How many floors to predict (1-8)"
)
async def towers(interaction: discord.Interaction, difficulty: str, floors: int):
    difficulty = difficulty.lower()
    if difficulty not in DIFFICULTIES:
        await interaction.response.send_message("❌ Choose: easy, medium, hard, or expert", ephemeral=True)
        return
    if not (1 <= floors <= 8):
        await interaction.response.send_message("❌ Floors must be between 1 and 8.", ephemeral=True)
        return

    d = DIFFICULTIES[difficulty]
    cols = d["cols"]
    safe_per_row = d["safe"]

    grid_lines = []
    for floor in range(floors, 0, -1):
        safe_cols = random.sample(range(1, cols + 1), safe_per_row)
        row = ""
        for c in range(1, cols + 1):
            row += "💎 " if c in safe_cols else "💣 "
        grid_lines.append(f"Floor {floor}: {row}")

    em = make_embed("🏰 Towers Prediction", f"Difficulty: **{difficulty.capitalize()}**")
    em.add_field(name="Predicted Safe Path", value="\n".join(grid_lines), inline=False)
    em.add_field(name="⚠️ Reminder", value="This is completely random — just for fun!", inline=False)

    await interaction.response.send_message(embed=em)

# ─────────────────────────────────────────
# /value
# ─────────────────────────────────────────
@bot.tree.command(name="value", description="Calculate expected value for crash bets")
@app_commands.describe(
    multiplier="Target crash multiplier",
    bet="Bet amount in Robux",
    games="Number of games"
)
async def value(interaction: discord.Interaction, multiplier: float, bet: int, games: int):
    if multiplier < 1.01:
        await interaction.response.send_message("❌ Multiplier must be at least 1.01.", ephemeral=True)
        return

    chance = 1/33 + (32/33) * (0.01 + 0.99 * (1 - 1/multiplier))
    ev_per_game = ((multiplier - 1) * bet * (1 - chance)) + (-bet * chance)
    total_ev = ev_per_game * games

    profit_or_loss = "lose" if total_ev < 0 else "gain"
    em = make_embed("💸 Expected Value Calculator")
    em.add_field(name="🎯 Multiplier", value=f"`{multiplier}x`", inline=True)
    em.add_field(name="💰 Bet", value=f"`R${bet}`", inline=True)
    em.add_field(name="🎮 Games", value=f"`{games}`", inline=True)
    em.add_field(
        name="📊 Expected Outcome",
        value=f"Over **{games}** games you're expected to **{profit_or_loss} R${abs(round(total_ev, 2))}**",
        inline=False
    )

    await interaction.response.send_message(embed=em)

# ─────────────────────────────────────────
# /help
# ─────────────────────────────────────────
@bot.tree.command(name="help", description="Show all available commands")
async def help_cmd(interaction: discord.Interaction):
    em = make_embed("📋 Bloxflip Predictor Commands")
    em.add_field(name="/mines", value="Predict safe tiles in Mines", inline=False)
    em.add_field(name="/crash", value="See odds for a crash multiplier", inline=False)
    em.add_field(name="/roulette", value="Predict next roulette result", inline=False)
    em.add_field(name="/towers", value="Predict safe columns in Towers", inline=False)
    em.add_field(name="/value", value="Calculate expected value for crash bets", inline=False)
    await interaction.response.send_message(embed=em)

# ─────────────────────────────────────────
bot.run(TOKEN)

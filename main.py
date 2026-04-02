import interactions
import random
import cloudscraper
import os

# ====================== SETTINGS ======================
SafeMines  = ':white_check_mark:'
TileMines  = ':x:'
SafeTowers = ':white_check_mark:'
TileTowers = ':x:'

# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
BOT_TOKEN     = os.getenv("TOKEN")           # Set this in Railway Variables
SERVER_ID     = 0                            # ← CHANGE THIS to your server ID (or leave 0 for global)
BUYER_ROLE_ID = 0                            # ← CHANGE THIS to your buyer role ID (or leave 0 to allow all)
OWNER_ID      = 1393776676755738715          # Your Discord user ID (always has access)
# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←

bot = interactions.Client(token=BOT_TOKEN)

# ====================== HELPERS ======================
def has_access(ctx):
    if ctx.author.id == OWNER_ID:
        return True
    if BUYER_ROLE_ID == 0:
        return True
    return BUYER_ROLE_ID in [r.id for r in getattr(ctx.author, 'roles', [])]

def generate_mines_grid(safe_tiles: int) -> str:
    board = [0] * 25
    for pos in random.sample(range(25), safe_tiles):
        board[pos] = 1
    grid = ""
    for i in range(25):
        grid += SafeMines if board[i] else TileMines
        if (i + 1) % 5 == 0 and i != 24:
            grid += "\n"
    return grid

def generate_towers(rows: int) -> str:
    patterns = [
        f"{SafeTowers}{TileTowers}{TileTowers}",
        f"{TileTowers}{SafeTowers}{TileTowers}",
        f"{TileTowers}{TileTowers}{SafeTowers}"
    ]
    return "".join(random.choice(patterns) + "\n" for _ in range(rows))

def is_valid_bloxflip_id(game_id: str) -> bool:
    return bool(game_id and len(game_id) > 15 and "-" in game_id)


# ====================== COMMANDS ======================
@interactions.slash_command(
    name="mines",
    description="Generates a Mines grid",
    scopes=[SERVER_ID] if SERVER_ID else None
)
@interactions.slash_option(name="game_id", description="Put your Bloxflip game ID here", opt_type=interactions.OptionType.STRING, required=True)
@interactions.slash_option(name="safe_clicks", description="How many safe spots (1-23)", opt_type=interactions.OptionType.INTEGER, required=True, min_value=1, max_value=23)
async def mines_cmd(ctx: interactions.SlashContext, game_id: str, safe_clicks: int):
    if not has_access(ctx):
        await ctx.send(f"Not Eligible! {ctx.author.mention}", ephemeral=True)
        return
    if not is_valid_bloxflip_id(game_id):
        await ctx.send("Invalid Game ID!", ephemeral=True)
        return

    grid = generate_mines_grid(safe_clicks)
    embed = interactions.Embed(title="Mines", description="Generated Tiles!", color=0xFC4431)
    embed.add_field(name=f"{safe_clicks} Clicks", value=grid or "Error generating grid", inline=False)

    await ctx.send(embed=embed)
    print(f"{ctx.author} used /mines | Game ID: {game_id} | Safe Clicks: {safe_clicks}")


@interactions.slash_command(
    name="towers",
    description="Generates a Towers grid",
    scopes=[SERVER_ID] if SERVER_ID else None
)
@interactions.slash_option(name="game_id", description="Put your Bloxflip game ID here", opt_type=interactions.OptionType.STRING, required=True)
@interactions.slash_option(name="rows", description="How many rows (1-8)", opt_type=interactions.OptionType.INTEGER, required=True, min_value=1, max_value=8)
async def towers_cmd(ctx: interactions.SlashContext, game_id: str, rows: int):
    if not has_access(ctx):
        await ctx.send(f"Not Eligible! {ctx.author.mention}", ephemeral=True)
        return
    if not is_valid_bloxflip_id(game_id):
        await ctx.send("Invalid Game ID!", ephemeral=True)
        return

    result = generate_towers(rows)
    embed = interactions.Embed(title="Towers", description="Generated Tower!", color=0xFC4431)
    embed.add_field(name=f"{rows} Rows", value=result, inline=False)

    await ctx.send(embed=embed)
    print(f"{ctx.author} used /towers | Game ID: {game_id} | Rows: {rows}")


@interactions.slash_command(
    name="crash",
    description="Predict a Crash Game",
    scopes=[SERVER_ID] if SERVER_ID else None
)
async def crash_cmd(ctx: interactions.SlashContext):
    if not has_access(ctx):
        await ctx.send(f"Not Eligible! {ctx.author.mention}", ephemeral=True)
        return

    try:
        scraper = cloudscraper.create_scraper()
        data = scraper.get("https://rest-bf.blox.land/games/crash", timeout=10).json()

        history = data.get("history", [])
        if not history:
            await ctx.send("No crash history available.", ephemeral=True)
            return

        prev = history[0]["crashPoint"]
        game_id = data.get("current", {}).get("_id", "Unknown")

        av2 = prev + (history[1]["crashPoint"] if len(history) > 1 else prev)
        chancenum = 100 / prev if prev > 0 else 0
        estnum = (1 / (1 - chancenum / 100) + av2) / 2 if chancenum > 0 else 1.0

        estimate = f"{estnum:.2f}"
        chance = f"{chancenum:.2f}"

        embed = interactions.Embed(title="Crash", description=f"{ctx.author.mention}", color=0xFC4431)
        embed.add_field(name="Crash Estimate", value=f"```{estimate}X```", inline=False)
        embed.add_field(name="Game ID", value=f"```{game_id}```", inline=False)
        embed.add_field(name="Chance", value=f"```{chance}/100```", inline=False)

        await ctx.send(embed=embed)
        print(f"{ctx.author} used /crash → {estimate}X")

    except Exception as e:
        print(f"Crash error: {e}")
        await ctx.send("Failed to fetch crash data. Try again later.", ephemeral=True)


# ====================== STARTUP ======================
@interactions.listen()
async def on_ready():
    print(f"✅ Bot is now online as {bot.user}")

bot.start()

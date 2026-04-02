import interactions
import random
import cloudscraper
import os

# ====================== SETTINGS ======================
SafeMines  = ':white_check_mark:'
TileMines  = ':x:'
SafeTowers = ':white_check_mark:'
TileTowers = ':x:'

BOT_TOKEN  = os.getenv("TOKEN")
OWNER_ID   = int(os.getenv("OWNER_ID", "0"))
# ======================================================

bot = interactions.Client(token=BOT_TOKEN)

# In-memory token store: {user_id: app.at token}
user_tokens = {}


# ====================== HELPERS ======================
def get_scraper(app_at: str):
    scraper = cloudscraper.create_scraper()
    scraper.cookies.set("app.at", app_at, domain="bloxflip.com")
    scraper.headers.update({
        "accept": "application/json, text/plain, */*",
        "referer": "https://bloxflip.com/mines",
        "x-currency": "ROCOINS",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    })
    return scraper

def generate_mines_grid(mine_count: int, safe_clicks: int, uncovered: list) -> str:
    board = [0] * 25
    available = [i for i in range(25) if i not in uncovered]
    safe_positions = random.sample(available, min(safe_clicks, len(available)))
    for pos in safe_positions:
        board[pos] = 1
    grid = ""
    for i in range(25):
        if i in uncovered:
            grid += ':diamond_shape_with_a_dot_inside:'
        elif board[i]:
            grid += SafeMines
        else:
            grid += TileMines
        if (i + 1) % 5 == 0 and i != 24:
            grid += "\n"
    return grid

def generate_towers_grid(rows: int) -> str:
    patterns = [
        f"{SafeTowers}{TileTowers}{TileTowers}",
        f"{TileTowers}{SafeTowers}{TileTowers}",
        f"{TileTowers}{TileTowers}{SafeTowers}"
    ]
    return "\n".join(random.choice(patterns) for _ in range(rows))

def is_valid_bloxflip_id(game_id: str) -> bool:
    return bool(game_id and len(game_id) > 15 and "-" in game_id)


# ====================== /login ======================
@interactions.slash_command(name="login", description="Login with your Bloxflip app.at cookie")
@interactions.slash_option(
    name="token",
    description="Your app.at cookie from bloxflip.com",
    opt_type=interactions.OptionType.STRING,
    required=True
)
async def login_cmd(ctx: interactions.SlashContext, token: str):
    # Verify token works
    try:
        scraper = get_scraper(token)
        resp = scraper.get("https://bloxflip.com/api/games/mines", timeout=10).json()
        if not resp.get("success"):
            await ctx.send("❌ Invalid token — make sure you copied the full `app.at` cookie.", ephemeral=True)
            return
    except Exception as e:
        await ctx.send(f"❌ Failed to verify token: {e}", ephemeral=True)
        return

    user_tokens[ctx.author.id] = token
    await ctx.send("✅ Logged in successfully! You can now use `/mines` and `/towers`.", ephemeral=True)
    print(f"{ctx.author} logged in")


# ====================== /mines ======================
@interactions.slash_command(name="mines", description="Predict your active Bloxflip Mines game")
@interactions.slash_option(
    name="safe_clicks",
    description="How many safe tiles to suggest (1-23)",
    opt_type=interactions.OptionType.INTEGER,
    required=True,
    min_value=1,
    max_value=23
)
async def mines_cmd(ctx: interactions.SlashContext, safe_clicks: int):
    token = user_tokens.get(ctx.author.id)
    if not token:
        await ctx.send("❌ You need to `/login` first with your Bloxflip `app.at` cookie.", ephemeral=True)
        return

    try:
        scraper = get_scraper(token)
        data = scraper.get("https://bloxflip.com/api/games/mines", timeout=10).json()

        if not data.get("success"):
            await ctx.send("❌ Failed to fetch game data. Try `/login` again.", ephemeral=True)
            return

        if not data.get("hasGame"):
            await ctx.send("❌ You don't have an active Mines game. Start one on Bloxflip first!", ephemeral=True)
            return

        game = data["game"]
        mine_count = game.get("minesAmount", 3)
        uncovered = game.get("uncoveredLocations", [])
        uuid = game.get("uuid", "unknown")
        bet = game.get("betAmount", 0)
        multiplier = data.get("multiplier", 1)

        grid = generate_mines_grid(mine_count, safe_clicks, uncovered)

        embed = interactions.Embed(title="Mines Predictor", description="Predicted safe tiles for your active game!", color=0xFC4431)
        embed.add_field(name="Game ID", value=f"```{uuid}```", inline=False)
        embed.add_field(name="Mines", value=f"```{mine_count}```", inline=True)
        embed.add_field(name="Bet", value=f"```{bet}```", inline=True)
        embed.add_field(name="Multiplier", value=f"```{multiplier:.2f}x```", inline=True)
        embed.add_field(name=f"Suggested Tiles ({safe_clicks} clicks)", value=grid, inline=False)
        embed.set_footer(text="⚠️ For fun only — predictions are random")

        await ctx.send(embed=embed)
        print(f"{ctx.author} used /mines | Mines: {mine_count} | Safe: {safe_clicks}")

    except Exception as e:
        print(f"Mines error: {e}")
        await ctx.send("❌ Error fetching your game. Try `/login` again.", ephemeral=True)


# ====================== /towers ======================
@interactions.slash_command(name="towers", description="Predict safe columns for Bloxflip Towers")
@interactions.slash_option(
    name="game_id",
    description="Your Bloxflip game ID",
    opt_type=interactions.OptionType.STRING,
    required=True
)
@interactions.slash_option(
    name="rows",
    description="How many rows to predict (1-8)",
    opt_type=interactions.OptionType.INTEGER,
    required=True,
    min_value=1,
    max_value=8
)
async def towers_cmd(ctx: interactions.SlashContext, game_id: str, rows: int):
    if not is_valid_bloxflip_id(game_id):
        await ctx.send("❌ Invalid Game ID!", ephemeral=True)
        return

    result = generate_towers_grid(rows)
    embed = interactions.Embed(title="Towers Predictor", description="Generated Tower!", color=0xFC4431)
    embed.add_field(name="Game ID", value=f"```{game_id}```", inline=False)
    embed.add_field(name=f"{rows} Rows", value=result, inline=False)
    embed.set_footer(text="⚠️ For fun only — predictions are random")

    await ctx.send(embed=embed)
    print(f"{ctx.author} used /towers | Rows: {rows}")


# ====================== /crash ======================
@interactions.slash_command(name="crash", description="Predict the next Bloxflip Crash multiplier")
async def crash_cmd(ctx: interactions.SlashContext):
    try:
        scraper = cloudscraper.create_scraper()
        data = scraper.get("https://rest-bf.blox.land/games/crash", timeout=10).json()

        history = data.get("history", [])
        if not history:
            await ctx.send("❌ No crash history available.", ephemeral=True)
            return

        prev = history[0]["crashPoint"]
        game_id = data.get("current", {}).get("_id", "Unknown")
        av2 = prev + (history[1]["crashPoint"] if len(history) > 1 else prev)
        chancenum = 100 / prev if prev > 0 else 0
        estnum = (1 / (1 - chancenum / 100) + av2) / 2 if chancenum > 0 else 1.0

        estimate = f"{estnum:.2f}"
        chance = f"{chancenum:.2f}"

        embed = interactions.Embed(title="Crash Predictor", description=f"{ctx.author.mention}", color=0xFC4431)
        embed.add_field(name="Crash Estimate", value=f"```{estimate}X```", inline=False)
        embed.add_field(name="Game ID", value=f"```{game_id}```", inline=False)
        embed.add_field(name="Chance", value=f"```{chance}/100```", inline=False)
        embed.set_footer(text="⚠️ For fun only — predictions are random")

        await ctx.send(embed=embed)
        print(f"{ctx.author} used /crash → {estimate}X")

    except Exception as e:
        print(f"Crash error: {e}")
        await ctx.send("❌ Failed to fetch crash data. Try again later.", ephemeral=True)


# ====================== STARTUP ======================
@interactions.listen()
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")

bot.start()

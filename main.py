import interactions
import random
import requests
import os

# ====================== SETTINGS ======================
SafeMines  = ':white_check_mark:'
TileMines  = ':x:'
SafeTowers = ':white_check_mark:'
TileTowers = ':x:'

BOT_TOKEN = os.getenv("TOKEN")
# ======================================================

bot = interactions.Client(token=BOT_TOKEN)

user_tokens = {}  # {user_id: app_at}


# ====================== HELPERS ======================
def fetch_mines(app_at: str):
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9",
        "referer": "https://bloxflip.com/mines",
        "x-currency": "ROCOINS",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "cookie": f"app.at={app_at}"
    }
    resp = requests.get("https://bloxflip.com/api/games/mines", headers=headers, timeout=10)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text[:500]}")
    return resp.json()

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

def generate_towers(rows: int) -> str:
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
@interactions.slash_option(name="token", description="Your app.at cookie value", opt_type=interactions.OptionType.STRING, required=True)
async def login_cmd(ctx: interactions.SlashContext, token: str):
    try:
        data = fetch_mines(token)
        if not data.get("success"):
            await ctx.send("❌ Invalid token.", ephemeral=True)
            return
    except Exception as e:
        await ctx.send(f"❌ Error: {e}", ephemeral=True)
        return

    user_tokens[ctx.author.id] = token
    await ctx.send("✅ Logged in! Use `/mines` to predict your active game.", ephemeral=True)
    print(f"{ctx.author} logged in")


# ====================== /mines ======================
@interactions.slash_command(name="mines", description="Predict your active Bloxflip Mines game")
@interactions.slash_option(name="safe_clicks", description="How many safe tiles to suggest (1-23)", opt_type=interactions.OptionType.INTEGER, required=True, min_value=1, max_value=23)
async def mines_cmd(ctx: interactions.SlashContext, safe_clicks: int):
    token = user_tokens.get(ctx.author.id)
    if not token:
        await ctx.send("❌ Use `/login` first!", ephemeral=True)
        return

    try:
        data = fetch_mines(token)
        if not data.get("success"):
            await ctx.send("❌ Failed to fetch game. Try `/login` again.", ephemeral=True)
            return
        if not data.get("hasGame"):
            await ctx.send("❌ No active Mines game. Start one on Bloxflip first!", ephemeral=True)
            return

        game = data["game"]
        mine_count = game.get("minesAmount", 3)
        uncovered = game.get("uncoveredLocations", [])
        uuid = game.get("uuid", "unknown")
        bet = game.get("betAmount", 0)
        multiplier = data.get("multiplier", 1)

        grid = generate_mines_grid(mine_count, safe_clicks, uncovered)

        embed = interactions.Embed(title="Mines", description="Generated Tiles!", color=0xFC4431)
        embed.add_field(name="Game ID", value=f"```{uuid}```", inline=False)
        embed.add_field(name="Mines", value=f"```{mine_count}```", inline=True)
        embed.add_field(name="Bet", value=f"```{bet}```", inline=True)
        embed.add_field(name="Multiplier", value=f"```{multiplier:.2f}x```", inline=True)
        embed.add_field(name=f"{safe_clicks} Clicks", value=grid, inline=False)

        await ctx.send(embed=embed)
        print(f"{ctx.author} used /mines | Mines: {mine_count} | Safe: {safe_clicks}")

    except Exception as e:
        print(f"Mines error: {e}")
        await ctx.send(f"❌ Error: {e}", ephemeral=True)


# ====================== /towers ======================
@interactions.slash_command(name="towers", description="Generates a Towers grid")
@interactions.slash_option(name="game_id", description="Your Bloxflip game ID", opt_type=interactions.OptionType.STRING, required=True)
@interactions.slash_option(name="rows", description="How many rows (1-8)", opt_type=interactions.OptionType.INTEGER, required=True, min_value=1, max_value=8)
async def towers_cmd(ctx: interactions.SlashContext, game_id: str, rows: int):
    if not is_valid_bloxflip_id(game_id):
        await ctx.send("Invalid Game ID!", ephemeral=True)
        return

    result = generate_towers(rows)
    embed = interactions.Embed(title="Towers", description="Generated Tower!", color=0xFC4431)
    embed.add_field(name="Game ID", value=f"```{game_id}```", inline=False)
    embed.add_field(name=f"{rows} Rows", value=result, inline=False)

    await ctx.send(embed=embed)
    print(f"{ctx.author} used /towers | Rows: {rows}")


# ====================== /crash ======================
@interactions.slash_command(name="crash", description="Predict a Crash Game")
async def crash_cmd(ctx: interactions.SlashContext):
    try:
        scraper = requests.Session()
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

        embed = interactions.Embed(title="Crash", description=f"{ctx.author.mention}", color=0xFC4431)
        embed.add_field(name="Crash Estimate", value=f"```{estnum:.2f}X```", inline=False)
        embed.add_field(name="Game ID", value=f"```{game_id}```", inline=False)
        embed.add_field(name="Chance", value=f"```{chancenum:.2f}/100```", inline=False)

        await ctx.send(embed=embed)
        print(f"{ctx.author} used /crash → {estnum:.2f}X")

    except Exception as e:
        print(f"Crash error: {e}")
        await ctx.send("Failed to fetch crash data.", ephemeral=True)


# ====================== STARTUP ======================
@interactions.listen()
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")

bot.start()

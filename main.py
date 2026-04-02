import discord
from discord.ext import commands
from discord import app_commands
import random
import os

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# READY EVENT
# =========================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(e)

# =========================
# 🎲 DICE COMMAND
# =========================
@bot.tree.command(name="dice", description="Roll a dice")
async def dice(interaction: discord.Interaction):
    roll = random.randint(1, 6)
    await interaction.response.send_message(f"🎲 You rolled: **{roll}**")

# =========================
# 🎯 MINES GAME
# =========================

GRID_SIZE = 5
MINES_COUNT = 3

class MinesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.grid = ["safe"] * 25
        for i in random.sample(range(25), MINES_COUNT):
            self.grid[i] = "mine"

    @discord.ui.button(label="⬜", style=discord.ButtonStyle.secondary)
    async def tile0(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.reveal(interaction, button, 0)

    @discord.ui.button(label="⬜", style=discord.ButtonStyle.secondary)
    async def tile1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.reveal(interaction, button, 1)

    @discord.ui.button(label="⬜", style=discord.ButtonStyle.secondary)
    async def tile2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.reveal(interaction, button, 2)

    @discord.ui.button(label="⬜", style=discord.ButtonStyle.secondary)
    async def tile3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.reveal(interaction, button, 3)

    @discord.ui.button(label="⬜", style=discord.ButtonStyle.secondary)
    async def tile4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.reveal(interaction, button, 4)

    async def reveal(self, interaction, button, index):
        if self.grid[index] == "mine":
            button.label = "💣"
            button.style = discord.ButtonStyle.danger
            self.disable_all_items()
            await interaction.response.edit_message(content="💥 You hit a mine!", view=self)
        else:
            button.label = "💎"
            button.style = discord.ButtonStyle.success
            await interaction.response.edit_message(view=self)

@bot.tree.command(name="mines", description="Play mines")
async def mines(interaction: discord.Interaction):
    view = MinesView()
    await interaction.response.send_message("🎯 Mines Game!", view=view)

# =========================
# 🃏 BLACKJACK GAME
# =========================

cards = [2,3,4,5,6,7,8,9,10,10,10,10,11]

def draw():
    return random.choice(cards)

def hand_value(hand):
    total = sum(hand)
    while total > 21 and 11 in hand:
        hand[hand.index(11)] = 1
        total = sum(hand)
    return total

class BlackjackView(discord.ui.View):
    def __init__(self, player, dealer):
        super().__init__(timeout=60)
        self.player = player
        self.dealer = dealer

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.append(draw())
        total = hand_value(self.player)

        if total > 21:
            self.disable_all_items()
            await interaction.response.edit_message(
                content=f"💥 Bust! Your hand: {self.player} ({total})",
                view=self
            )
        else:
            await interaction.response.edit_message(
                content=f"Your hand: {self.player} ({total})",
                view=self
            )

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        while hand_value(self.dealer) < 17:
            self.dealer.append(draw())

        player_total = hand_value(self.player)
        dealer_total = hand_value(self.dealer)

        result = ""
        if dealer_total > 21 or player_total > dealer_total:
            result = "🎉 You win!"
        elif player_total < dealer_total:
            result = "😢 You lose!"
        else:
            result = "🤝 Tie!"

        self.disable_all_items()

        await interaction.response.edit_message(
            content=f"""
🃏 Blackjack Result

Your hand: {self.player} ({player_total})
Dealer: {self.dealer} ({dealer_total})

{result}
""",
            view=self
        )

@bot.tree.command(name="blackjack", description="Play blackjack")
async def blackjack(interaction: discord.Interaction):
    player = [draw(), draw()]
    dealer = [draw(), draw()]

    view = BlackjackView(player, dealer)

    await interaction.response.send_message(
        f"🃏 Blackjack!\nYour hand: {player} ({hand_value(player)})",
        view=view
    )

# =========================

bot.run(TOKEN)

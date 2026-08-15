python
import discord
from discord import app_commands
from discord.ext import tasks
import requests
import os
from dotenv import load_dotenv


# =========================
# CONFIGURATION
# =========================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1537916356559765545

# Default Roblox player
PLAYER_USERNAME = "ExamplePlayer"
PLAYER_ID = 123456789
PLAYER_DISPLAY_NAME = "Example"


# =========================
# DISCORD SETUP
# =========================

intents = discord.Intents.default()

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

GUILD = discord.Object(id=GUILD_ID)


# =========================
# WATCHER STATE
# =========================

watching = False
previous_status = None
previous_game = None
watch_channel = None


# =========================
# ROBLOX PRESENCE
# =========================

def get_roblox_presence():

    url = "https://presence.roblox.com/v1/presence/users"

    data = {
        "userIds": [PLAYER_ID]
    }

    response = requests.post(
        url,
        json=data,
        timeout=10
    )

    response.raise_for_status()

    presence = response.json()["userPresences"][0]

    return presence


def get_status_text(presence):

    presence_type = presence["userPresenceType"]

    if presence_type == 0:
        return "Offline"

    elif presence_type == 1:
        return "Online"

    elif presence_type == 2:
        return "In Game"

    elif presence_type == 3:
        return "In Roblox Studio"

    return "Unknown"


# =========================
# ROBLOX GAME DETECTION
# =========================

def get_game_name_from_universe(universe_id):

    if not universe_id:
        return None

    url = "https://games.roblox.com/v1/games"

    params = {
        "universeIds": universe_id
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json().get("data", [])

        if not data:
            return None

        return data[0].get("name")

    except requests.RequestException as error:

        print(
            f"Game lookup failed: {error}"
        )

        return None


def get_current_game(presence):

    # =========================
    # METHOD 1:
    # Roblox's lastLocation
    # =========================

    last_location = presence.get("lastLocation")

    if last_location:
        return last_location

    # =========================
    # METHOD 2:
    # Universe ID lookup
    # =========================

    universe_id = presence.get("universeId")

    if universe_id:

        return get_game_name_from_universe(
            universe_id
        )

    # =========================
    # NO GAME INFORMATION
    # =========================

    print(
        "Roblox did not provide a game name, "
        "universeId, or usable experience data."
    )

    return None


# =========================
# GET CURRENT PLAYER STATE
# =========================

def get_current_player_state():

    presence = get_roblox_presence()

    current_status = get_status_text(
        presence
    )

    current_game = None

    if current_status == "In Game":

        current_game = get_current_game(
            presence
        )

    return current_status, current_game


# =========================
# DISCORD EVENTS
# =========================

@client.event
async def on_ready():

    await tree.sync(guild=GUILD)

    print(
        f"Logged in as {client.user}!"
    )

    print(
        "Roblox Status Checker is online."
    )

    print(
        "Slash commands synced."
    )


# =========================
# /ping
# =========================

@tree.command(
    name="ping",
    description="Check if the bot is working.",
    guild=GUILD
)
async def ping(interaction: discord.Interaction):

    await interaction.response.send_message(
        "Pong! 🏓"
    )


# =========================
# /status
# =========================

@tree.command(
    name="status",
    description="Immediately check the Roblox player's current status.",
    guild=GUILD
)
async def status(interaction: discord.Interaction):

    try:

        presence = get_roblox_presence()

        print(
            "DEBUG - Roblox response:",
            presence
        )

        current_status = get_status_text(
            presence
        )

        if current_status == "In Game":

            game_name = get_current_game(
                presence
            )

            if game_name:

                await interaction.response.send_message(
                    f"**{PLAYER_DISPLAY_NAME}** "
                    f"(**{PLAYER_USERNAME}**) is currently "
                    f"**In Game** 🎮\n"
                    f"Playing: **{game_name}**"
                )

            else:

                await interaction.response.send_message(
                    f"**{PLAYER_DISPLAY_NAME}** "
                    f"(**{PLAYER_USERNAME}**) is currently "
                    f"**In Game** 🎮\n"
                    f"⚠️ I couldn't identify the experience."
                )

            return

        await interaction.response.send_message(
            f"**{PLAYER_DISPLAY_NAME}** "
            f"(**{PLAYER_USERNAME}**) is currently "
            f"**{current_status}**."
        )

    except requests.RequestException as error:

        print(
            f"Status lookup failed: {error}"
        )

        await interaction.response.send_message(
            "❌ Roblox's presence service could not "
            "be reached. Please try again later."
        )


# =========================
# /startwatch
# =========================

@tree.command(
    name="startwatch",
    description="Start monitoring the Roblox player every 30 seconds.",
    guild=GUILD
)
async def startwatch(interaction: discord.Interaction):

    global watching
    global watch_channel
    global previous_status
    global previous_game

    if watching:

        await interaction.response.send_message(
            f"👀 **{PLAYER_DISPLAY_NAME}** "
            f"(**{PLAYER_USERNAME}**) "
            f"is already being watched."
        )

        return

    try:

        presence = get_roblox_presence()

        previous_status = get_status_text(
            presence
        )

        previous_game = None

        if previous_status == "In Game":

            previous_game = get_current_game(
                presence
            )

    except requests.RequestException as error:

        print(
            f"Initial watcher lookup failed: {error}"
        )

        await interaction.response.send_message(
            "❌ I couldn't get the player's current "
            "Roblox status. Please try again."
        )

        return

    watching = True
    watch_channel = interaction.channel

    watch_loop.start()

    message = (
        f"👀 Started watching "
        f"**{PLAYER_DISPLAY_NAME}** "
        f"(**{PLAYER_USERNAME}**) "
        f"every 30 seconds.\n"
        f"Current status: **{previous_status}**"
    )

    if previous_game:

        message += (
            f"\n🎮 Playing: **{previous_game}**"
        )

    await interaction.response.send_message(
        message
    )


# =========================
# /stopwatch
# =========================

@tree.command(
    name="stopwatch",
    description="Stop monitoring the Roblox player.",
    guild=GUILD
)
async def stopwatch(interaction: discord.Interaction):

    global watching
    global previous_status
    global previous_game
    global watch_channel

    if not watching:

        await interaction.response.send_message(
            "😴 I'm not currently watching anyone."
        )

        return

    watching = False

    previous_status = None
    previous_game = None
    watch_channel = None

    watch_loop.cancel()

    await interaction.response.send_message(
        "🛑 Automatic monitoring stopped."
    )


# =========================
# /player
# =========================

@tree.command(
    name="player",
    description="Show the Roblox account currently being monitored.",
    guild=GUILD
)
async def player(interaction: discord.Interaction):

    await interaction.response.send_message(
        f"👤 Currently monitoring "
        f"**{PLAYER_DISPLAY_NAME}** "
        f"(**{PLAYER_USERNAME}**) "
        f"(ID: `{PLAYER_ID}`)."
    )


# =========================
# /watchstatus
# =========================

@tree.command(
    name="watchstatus",
    description="Show whether automatic monitoring is running.",
    guild=GUILD
)
async def watchstatus(interaction: discord.Interaction):

    if watching:

        await interaction.response.send_message(
            f"🟢 Automatic monitoring is **running**.\n"
            f"Watching: **{PLAYER_DISPLAY_NAME}** "
            f"(**{PLAYER_USERNAME}**)"
        )

    else:

        await interaction.response.send_message(
            "🔴 Automatic monitoring is **stopped**."
        )


# =========================
# /setplayer
# =========================

@tree.command(
    name="setplayer",
    description="Change the Roblox account being monitored.",
    guild=GUILD
)
@app_commands.describe(
    username="The Roblox username to monitor"
)
async def setplayer(
    interaction: discord.Interaction,
    username: str
):

    global PLAYER_USERNAME
    global PLAYER_DISPLAY_NAME
    global PLAYER_ID
    global previous_status
    global previous_game

    url = "https://users.roblox.com/v1/usernames/users"

    data = {
        "usernames": [username],
        "excludeBannedUsers": False
    }

    try:

        response = requests.post(
            url,
            json=data,
            timeout=10
        )

        response.raise_for_status()

        users = response.json()["data"]

    except requests.RequestException as error:

        print(
            f"User lookup failed: {error}"
        )

        await interaction.response.send_message(
            "❌ Roblox's user lookup failed. "
            "Please try again later."
        )

        return

    if not users:

        await interaction.response.send_message(
            f"❌ I couldn't find a Roblox user "
            f"named `{username}`."
        )

        return

    # =========================
    # GET USER INFORMATION
    # =========================

    new_username = users[0]["name"]
    new_display_name = users[0]["displayName"]
    new_id = users[0]["id"]

    # =========================
    # CHECK IF ALREADY WATCHING
    # =========================

    if new_id == PLAYER_ID:

        await interaction.response.send_message(
            f"👀 **{PLAYER_DISPLAY_NAME}** "
            f"(**{PLAYER_USERNAME}**) "
            f"is already being watched."
        )

        return

    # =========================
    # UPDATE MONITORED PLAYER
    # =========================

    PLAYER_USERNAME = new_username
    PLAYER_DISPLAY_NAME = new_display_name
    PLAYER_ID = new_id

    # =========================
    # UPDATE WATCHER STATE
    # =========================

    if watching:

        try:

            presence = get_roblox_presence()

            previous_status = get_status_text(
                presence
            )

            previous_game = None

            if previous_status == "In Game":

                previous_game = get_current_game(
                    presence
                )

            print(
                f"Watcher target changed to "
                f"{PLAYER_DISPLAY_NAME} "
                f"({PLAYER_USERNAME}). "
                f"New baseline: "
                f"{previous_status}"
            )

        except requests.RequestException as error:

            print(
                f"Failed to refresh watcher state: {error}"
            )

            # The player was changed successfully,
            # but we couldn't establish a baseline.
            previous_status = None
            previous_game = None

            await interaction.response.send_message(
                f"✅ Now monitoring "
                f"**{PLAYER_DISPLAY_NAME}** "
                f"(**{PLAYER_USERNAME}**) "
                f"(ID: `{PLAYER_ID}`).\n"
                f"⚠️ I couldn't get their current "
                f"status, so the next check will "
                f"establish the watcher baseline."
            )

            return

    else:

        # Not currently watching.
        # These will be initialized when /startwatch
        # is used.
        previous_status = None
        previous_game = None

    await interaction.response.send_message(
        f"✅ Now monitoring "
        f"**{PLAYER_DISPLAY_NAME}** "
        f"(**{PLAYER_USERNAME}**) "
        f"(ID: `{PLAYER_ID}`)."
    )


# =========================
# /help
# =========================

@tree.command(
    name="help",
    description="Show all available commands.",
    guild=GUILD
)
async def help_command(
    interaction: discord.Interaction
):

    message = (
        "**🤖 Roblox Status Checker**\n\n"

        "**`/ping`**\n"
        "Checks if the bot is working.\n\n"

        "**`/status`**\n"
        "Immediately checks the player's current "
        "Roblox status and game.\n\n"

        "**`/startwatch`**\n"
        "Starts automatic monitoring every 30 "
        "seconds.\n\n"

        "**`/stopwatch`**\n"
        "Stops automatic monitoring.\n\n"

        "**`/setplayer username:`**\n"
        "Changes the Roblox account being monitored.\n"
        "If the selected account is already being "
        "watched, the bot won't change anything.\n\n"

        "**`/player`**\n"
        "Shows the currently monitored Roblox "
        "account.\n\n"

        "**`/watchstatus`**\n"
        "Shows whether automatic monitoring is "
        "running.\n\n"

        "**`/help`**\n"
        "Shows all available commands."
    )

    await interaction.response.send_message(
        message
    )


# =========================
# 30-SECOND WATCHER
# =========================

@tasks.loop(seconds=30)
async def watch_loop():

    global previous_status
    global previous_game

    try:

        presence = get_roblox_presence()

        current_status = get_status_text(
            presence
        )

        print(
            f"Checked {PLAYER_DISPLAY_NAME} "
            f"({PLAYER_USERNAME}): "
            f"{current_status}"
        )

        current_game = None

        if current_status == "In Game":

            current_game = get_current_game(
                presence
            )

            if current_game:

                print(
                    f"Currently playing: "
                    f"{current_game}"
                )

            else:

                print(
                    "In Game, but the experience "
                    "could not be identified."
                )

        # =========================
        # FIRST CHECK AFTER TARGET
        # =========================

        if previous_status is None:

            previous_status = current_status
            previous_game = current_game

            print(
                "Watcher baseline established."
            )

            return

        # =========================
        # NO STATUS CHANGE
        # =========================

        if current_status == previous_status:

            # Game changed while still In Game
            if (
                current_status == "In Game"
                and current_game != previous_game
            ):

                old_game = previous_game

                previous_game = current_game

                if watch_channel is not None:

                    if current_game:

                        if old_game:

                            message = (
                                f"🎮 **{PLAYER_DISPLAY_NAME}** "
                                f"(**{PLAYER_USERNAME}**) "
                                f"changed experience:\n"
                                f"**{old_game}** → "
                                f"**{current_game}**"
                            )

                        else:

                            message = (
                                f"🎮 **{PLAYER_DISPLAY_NAME}** "
                                f"(**{PLAYER_USERNAME}**) "
                                f"is playing "
                                f"**{current_game}**"
                            )

                    else:

                        message = (
                            f"🎮 **{PLAYER_DISPLAY_NAME}** "
                            f"(**{PLAYER_USERNAME}**) "
                            f"is in a game, but I "
                            f"couldn't identify it."
                        )

                    await watch_channel.send(
                        message
                    )

            else:

                print("No change.")

            return

        # =========================
        # STATUS CHANGED
        # =========================

        old_status = previous_status

        previous_status = current_status
        previous_game = current_game

        print(
            f"Status changed: "
            f"{old_status} -> {current_status}"
        )

        if watch_channel is None:
            return

        # =========================
        # ENTERED A GAME
        # =========================

        if current_status == "In Game":

            if current_game:

                message = (
                    f"🔄 **{PLAYER_DISPLAY_NAME}** "
                    f"(**{PLAYER_USERNAME}**) "
                    f"changed status:\n"
                    f"**{old_status}** → "
                    f"**In Game**\n"
                    f"🎮 Playing: **{current_game}**"
                )

            else:

                message = (
                    f"🔄 **{PLAYER_DISPLAY_NAME}** "
                    f"(**{PLAYER_USERNAME}**) "
                    f"changed status:\n"
                    f"**{old_status}** → "
                    f"**In Game**\n"
                    f"⚠️ I couldn't identify "
                    f"the experience."
                )

        # =========================
        # LEFT GAME / OTHER STATUS
        # =========================

        else:

            message = (
                f"🔄 **{PLAYER_DISPLAY_NAME}** "
                f"(**{PLAYER_USERNAME}**) "
                f"changed status:\n"
                f"**{old_status}** → "
                f"**{current_status}**"
            )

        await watch_channel.send(
            message
        )

    except requests.RequestException as error:

        print(
            f"⚠️ Roblox API error: {error}"
        )

    except Exception as error:

        print(
            f"⚠️ Watcher error: {error}"
        )


# =========================
# START BOT
# =========================

if not TOKEN:

    raise RuntimeError(
        "DISCORD_TOKEN was not found "
        "in the .env file."
    )

client.run(TOKEN)
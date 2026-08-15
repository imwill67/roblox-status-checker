python
import discord
from discord import app_commands
from discord.ext import tasks
import requests
import os
from dotenv import load_dotenv


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

GUILD_ID = 1537916356559765545

# Default Roblox player
PLAYER_USERNAME = "Weidergamer46"
PLAYER_ID = 3746020391
PLAYER_DISPLAY_NAME = "Will"


# ============================================================
# DISCORD SETUP
# ============================================================

intents = discord.Intents.default()

client = discord.Client(intents=intents)

tree = app_commands.CommandTree(client)

GUILD = discord.Object(id=GUILD_ID)


# ============================================================
# WATCHER STATE
# ============================================================

watching = False

previous_status = None
previous_game = None

watch_channel = None


# ============================================================
# ROBLOX PRESENCE
# ============================================================

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

    data = response.json()

    presences = data.get("userPresences", [])

    if not presences:
        raise RuntimeError(
            "Roblox returned no presence data."
        )

    return presences[0]


# ============================================================
# STATUS TEXT
# ============================================================

def get_status_text(presence):

    presence_type = presence.get(
        "userPresenceType"
    )

    if presence_type == 0:
        return "Offline"

    elif presence_type == 1:
        return "Online"

    elif presence_type == 2:
        return "In Game"

    elif presence_type == 3:
        return "In Roblox Studio"

    elif presence_type == 4:
        return "Invisible"

    return "Unknown"


# ============================================================
# GAME LOOKUP — UNIVERSE ID
# ============================================================

def get_game_name_from_universe(universe_id):

    if not universe_id:
        return None

    url = "https://games.roblox.com/v1/games"

    params = {
        "universeIds": str(universe_id)
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json().get(
            "data",
            []
        )

        if not data:
            return None

        return data[0].get("name")

    except requests.RequestException as error:

        print(
            f"⚠️ Universe game lookup failed: {error}"
        )

        return None


# ============================================================
# GAME LOOKUP — PLACE ID → UNIVERSE ID
# ============================================================

def get_universe_from_place(place_id):

    if not place_id:
        return None

    url = (
        "https://apis.roblox.com/"
        "universes/v1/places/"
        f"{place_id}/universe"
    )

    try:

        response = requests.get(
            url,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        return data.get("universeId")

    except requests.RequestException as error:

        print(
            f"⚠️ Place → universe lookup failed: {error}"
        )

        return None


# ============================================================
# GAME DETECTION
# ============================================================

def get_current_game(presence):

    # --------------------------------------------------------
    # METHOD 1:
    # Direct universeId from Presence API
    # --------------------------------------------------------

    universe_id = presence.get(
        "universeId"
    )

    if universe_id:

        print(
            f"DEBUG - Universe ID: {universe_id}"
        )

        game_name = get_game_name_from_universe(
            universe_id
        )

        if game_name:
            return game_name


    # --------------------------------------------------------
    # METHOD 2:
    # placeId → universeId → game name
    # --------------------------------------------------------

    place_id = presence.get(
        "placeId"
    )

    if place_id:

        print(
            f"DEBUG - Place ID: {place_id}"
        )

        universe_id = get_universe_from_place(
            place_id
        )

        if universe_id:

            print(
                f"DEBUG - Universe ID from place: "
                f"{universe_id}"
            )

            game_name = get_game_name_from_universe(
                universe_id
            )

            if game_name:
                return game_name


    # --------------------------------------------------------
    # METHOD 3:
    # lastLocation fallback
    # --------------------------------------------------------

    last_location = presence.get(
        "lastLocation"
    )

    if last_location:

        return last_location


    # --------------------------------------------------------
    # No game information available
    # --------------------------------------------------------

    print(
        "⚠️ Roblox reported In Game, "
        "but no usable game information "
        "was provided."
    )

    return None


# ============================================================
# GET CURRENT PLAYER STATE
# ============================================================

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


# ============================================================
# DISCORD EVENTS
# ============================================================

@client.event
async def on_ready():

    await tree.sync(
        guild=GUILD
    )

    print(
        f"Logged in as {client.user}!"
    )

    print(
        "Roblox Status Checker is online."
    )

    print(
        "Slash commands synced."
    )


# ============================================================
# /ping
# ============================================================

@tree.command(
    name="ping",
    description="Check if the bot is working.",
    guild=GUILD
)
async def ping(
    interaction: discord.Interaction
):

    await interaction.response.send_message(
        "Pong! 🏓"
    )


# ============================================================
# /status
# ============================================================

@tree.command(
    name="status",
    description="Immediately check the Roblox player's current status.",
    guild=GUILD
)
async def status(
    interaction: discord.Interaction
):

    try:

        presence = get_roblox_presence()

        print(
            "DEBUG - Roblox response:",
            presence
        )

        current_status = get_status_text(
            presence
        )

        # ----------------------------------------------------
        # IN GAME
        # ----------------------------------------------------

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
                    f"⚠️ Roblox did not provide enough "
                    f"information to identify the experience."
                )

            return


        # ----------------------------------------------------
        # OTHER STATUS
        # ----------------------------------------------------

        await interaction.response.send_message(
            f"**{PLAYER_DISPLAY_NAME}** "
            f"(**{PLAYER_USERNAME}**) is currently "
            f"**{current_status}**."
        )


    except requests.RequestException as error:

        print(
            f"❌ Status lookup failed: {error}"
        )

        await interaction.response.send_message(
            "❌ Roblox's presence service could not "
            "be reached. Please try again later."
        )

    except Exception as error:

        print(
            f"❌ Status command error: {error}"
        )

        await interaction.response.send_message(
            "❌ Something went wrong while checking "
            "the player's status."
        )


# ============================================================
# /startwatch
# ============================================================

@tree.command(
    name="startwatch",
    description="Start monitoring the Roblox player every 30 seconds.",
    guild=GUILD
)
async def startwatch(
    interaction: discord.Interaction
):

    global watching
    global watch_channel
    global previous_status
    global previous_game


    # --------------------------------------------------------
    # Already watching
    # --------------------------------------------------------

    if watching:

        await interaction.response.send_message(
            f"👀 **{PLAYER_DISPLAY_NAME}** "
            f"(**{PLAYER_USERNAME}**) "
            f"is already being watched."
        )

        return


    # --------------------------------------------------------
    # Initial lookup
    # --------------------------------------------------------

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
            f"❌ Initial watcher lookup failed: {error}"
        )

        await interaction.response.send_message(
            "❌ I couldn't get the player's current "
            "Roblox status. Please try again."
        )

        return

    except Exception as error:

        print(
            f"❌ Initial watcher error: {error}"
        )

        await interaction.response.send_message(
            "❌ Something went wrong while starting "
            "the watcher."
        )

        return


    # --------------------------------------------------------
    # Start watcher
    # --------------------------------------------------------

    watching = True

    watch_channel = interaction.channel

    watch_loop.start()


    # --------------------------------------------------------
    # Confirmation message
    # --------------------------------------------------------

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

    elif previous_status == "In Game":

        message += (
            "\n⚠️ The player is in a game, "
            "but Roblox did not provide its name."
        )


    await interaction.response.send_message(
        message
    )


# ============================================================
# /stopwatch
# ============================================================

@tree.command(
    name="stopwatch",
    description="Stop monitoring the Roblox player.",
    guild=GUILD
)
async def stopwatch(
    interaction: discord.Interaction
):

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


    if watch_loop.is_running():

        watch_loop.cancel()


    await interaction.response.send_message(
        "🛑 Automatic monitoring stopped."
    )


# ============================================================
# /player
# ============================================================

@tree.command(
    name="player",
    description="Show the Roblox account currently being monitored.",
    guild=GUILD
)
async def player(
    interaction: discord.Interaction
):

    await interaction.response.send_message(
        f"👤 Currently monitoring "
        f"**{PLAYER_DISPLAY_NAME}** "
        f"(**{PLAYER_USERNAME}**) "
        f"(ID: `{PLAYER_ID}`)."
    )


# ============================================================
# /watchstatus
# ============================================================

@tree.command(
    name="watchstatus",
    description="Show whether automatic monitoring is running.",
    guild=GUILD
)
async def watchstatus(
    interaction: discord.Interaction
):

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


# ============================================================
# /setplayer
# ============================================================

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


    url = (
        "https://users.roblox.com/"
        "v1/usernames/users"
    )

    data = {
        "usernames": [username],
        "excludeBannedUsers": False
    }


    # --------------------------------------------------------
    # Find Roblox user
    # --------------------------------------------------------

    try:

        response = requests.post(
            url,
            json=data,
            timeout=10
        )

        response.raise_for_status()

        users = response.json().get(
            "data",
            []
        )

    except requests.RequestException as error:

        print(
            f"❌ User lookup failed: {error}"
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


    # --------------------------------------------------------
    # Get user information
    # --------------------------------------------------------

    new_username = users[0]["name"]

    new_display_name = users[0]["displayName"]

    new_id = users[0]["id"]


    # --------------------------------------------------------
    # Already selected
    # --------------------------------------------------------

    if new_id == PLAYER_ID:

        await interaction.response.send_message(
            f"👀 **{PLAYER_DISPLAY_NAME}** "
            f"(**{PLAYER_USERNAME}**) "
            f"is already being watched."
        )

        return


    # --------------------------------------------------------
    # Update target
    # --------------------------------------------------------

    PLAYER_USERNAME = new_username

    PLAYER_DISPLAY_NAME = new_display_name

    PLAYER_ID = new_id


    # --------------------------------------------------------
    # Refresh watcher baseline if watching
    # --------------------------------------------------------

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
                f"⚠️ Failed to refresh watcher state: "
                f"{error}"
            )

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

        except Exception as error:

            print(
                f"⚠️ Failed to refresh watcher state: "
                f"{error}"
            )

            previous_status = None

            previous_game = None


    else:

        previous_status = None

        previous_game = None


    await interaction.response.send_message(
        f"✅ Now monitoring "
        f"**{PLAYER_DISPLAY_NAME}** "
        f"(**{PLAYER_USERNAME}**) "
        f"(ID: `{PLAYER_ID}`)."
    )


# ============================================================
# /help
# ============================================================

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
        "Changes the Roblox account being monitored.\n\n"

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


# ============================================================
# 30-SECOND WATCHER
# ============================================================

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


        # ----------------------------------------------------
        # Get game
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # First check
        # ----------------------------------------------------

        if previous_status is None:

            previous_status = current_status

            previous_game = current_game

            print(
                "Watcher baseline established."
            )

            return


        # ----------------------------------------------------
        # Same status
        # ----------------------------------------------------

        if current_status == previous_status:


            # ------------------------------------------------
            # Game changed while still in game
            # ------------------------------------------------

            if (
                current_status == "In Game"
                and current_game != previous_game
            ):

                old_game = previous_game

                previous_game = current_game


                if watch_channel is not None:

                    # ----------------------------------------
                    # New game identified
                    # ----------------------------------------

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


                    # ----------------------------------------
                    # Still in game, but name unavailable
                    # ----------------------------------------

                    else:

                        message = (
                            f"🎮 **{PLAYER_DISPLAY_NAME}** "
                            f"(**{PLAYER_USERNAME}**) "
                            f"is in a game, but Roblox "
                            f"didn't provide its name."
                        )


                    await watch_channel.send(
                        message
                    )


            else:

                print(
                    "No change."
                )


            return


        # ----------------------------------------------------
        # STATUS CHANGED
        # ----------------------------------------------------

        old_status = previous_status

        previous_status = current_status

        previous_game = current_game


        print(
            f"Status changed: "
            f"{old_status} -> {current_status}"
        )


        if watch_channel is None:

            return


        # ----------------------------------------------------
        # ENTERED GAME
        # ----------------------------------------------------

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
                    f"⚠️ Roblox did not provide "
                    f"the experience name."
                )


        # ----------------------------------------------------
        # LEFT GAME / OTHER STATUS
        # ----------------------------------------------------

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


    # ========================================================
    # ERROR HANDLING
    # ========================================================

    except requests.RequestException as error:

        print(
            f"⚠️ Roblox API error: {error}"
        )

    except Exception as error:

        print(
            f"⚠️ Watcher error: {error}"
        )


# ============================================================
# START BOT
# ============================================================

if not TOKEN:

    raise RuntimeError(
        "DISCORD_TOKEN was not found "
        "in the .env file."
    )


client.run(TOKEN)
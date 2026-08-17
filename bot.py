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

client = discord.Client(
    intents=intents
)

tree = app_commands.CommandTree(
    client
)

GUILD = discord.Object(
    id=GUILD_ID
)


# ============================================================
# WATCHER STATE
# ============================================================

watching = False

previous_status = None
previous_game = None

watch_channel = None


# ============================================================
# GAME CACHE
# ============================================================

# Saves successful lookups so we don't repeatedly
# ask Roblox for the same game's name.

game_cache = {}


# ============================================================
# ROBLOX SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": "RobloxStatusChecker/1.0",
    "Accept": "application/json",
    "Content-Type": "application/json"
})


# ============================================================
# ROBLOX PRESENCE
# ============================================================

def get_roblox_presence():

    url = (
        "https://presence.roblox.com/"
        "v1/presence/users"
    )

    payload = {
        "userIds": [
            PLAYER_ID
        ]
    }

    response = session.post(
        url,
        json=payload,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    presences = data.get(
        "userPresences",
        []
    )

    if not presences:

        raise RuntimeError(
            "Roblox returned no presence data."
        )

    presence = presences[0]

    print(
        "DEBUG - Full Roblox presence:"
    )

    print(
        presence
    )

    return presence


# ============================================================
# STATUS TEXT
# ============================================================

def get_status_text(presence):

    presence_type = presence.get(
        "userPresenceType"
    )

    if presence_type == 0:
        return "Offline"

    if presence_type == 1:
        return "Online"

    if presence_type == 2:
        return "In Game"

    if presence_type == 3:
        return "In Roblox Studio"

    if presence_type == 4:
        return "Invisible"

    return "Unknown"


# ============================================================
# GAME LOOKUP
# ============================================================

def get_game_name_from_universe(
    universe_id
):

    if not universe_id:
        return None

    # Convert to string because Roblox IDs
    # can sometimes arrive as integers.

    universe_id = str(
        universe_id
    )

    # --------------------------------------------------------
    # CACHE
    # --------------------------------------------------------

    if universe_id in game_cache:

        print(
            f"DEBUG - Game cache hit: "
            f"{universe_id}"
        )

        return game_cache[
            universe_id
        ]


    # --------------------------------------------------------
    # API REQUEST
    # --------------------------------------------------------

    url = (
        "https://games.roblox.com/"
        "v1/games"
    )

    params = {
        "universeIds": universe_id
    }

    try:

        response = session.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        games = data.get(
            "data",
            []
        )

        if not games:

            print(
                f"DEBUG - No game returned "
                f"for universe {universe_id}"
            )

            return None


        game_name = games[0].get(
            "name"
        )


        if game_name:

            game_cache[
                universe_id
            ] = game_name

            print(
                f"DEBUG - Universe "
                f"{universe_id} = "
                f"{game_name}"
            )

            return game_name


    except requests.RequestException as error:

        print(
            f"⚠️ Universe lookup failed: "
            f"{error}"
        )


    return None


# ============================================================
# PLACE ID → UNIVERSE ID
# ============================================================

def get_universe_from_place(
    place_id
):

    if not place_id:
        return None

    url = (
        "https://apis.roblox.com/"
        "universes/v1/places/"
        f"{place_id}/universe"
    )

    try:

        response = session.get(
            url,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        universe_id = data.get(
            "universeId"
        )

        if universe_id:

            print(
                f"DEBUG - Place "
                f"{place_id} → Universe "
                f"{universe_id}"
            )

        return universe_id


    except requests.RequestException as error:

        print(
            f"⚠️ Place → universe lookup "
            f"failed: {error}"
        )

        return None


# ============================================================
# CURRENT GAME DETECTION
# ============================================================

def get_current_game(
    presence
):

    # ========================================================
    # METHOD 1
    # Direct universeId
    # ========================================================

    universe_id = presence.get(
        "universeId"
    )

    if universe_id:

        print(
            f"DEBUG - Presence supplied "
            f"universeId: {universe_id}"
        )

        game_name = (
            get_game_name_from_universe(
                universe_id
            )
        )

        if game_name:
            return game_name


    # ========================================================
    # METHOD 2
    # placeId → universeId
    # ========================================================

    place_id = presence.get(
        "placeId"
    )

    if place_id:

        print(
            f"DEBUG - Presence supplied "
            f"placeId: {place_id}"
        )

        universe_id = (
            get_universe_from_place(
                place_id
            )
        )

        if universe_id:

            game_name = (
                get_game_name_from_universe(
                    universe_id
                )
            )

            if game_name:
                return game_name


    # ========================================================
    # METHOD 3
    # rootPlaceId → universeId
    # ========================================================

    root_place_id = presence.get(
        "rootPlaceId"
    )

    if root_place_id:

        print(
            f"DEBUG - Presence supplied "
            f"rootPlaceId: "
            f"{root_place_id}"
        )

        universe_id = (
            get_universe_from_place(
                root_place_id
            )
        )

        if universe_id:

            game_name = (
                get_game_name_from_universe(
                    universe_id
                )
            )

            if game_name:
                return game_name


    # ========================================================
    # METHOD 4
    # lastLocation
    # ========================================================

    last_location = presence.get(
        "lastLocation"
    )

    if last_location:

        print(
            f"DEBUG - Using lastLocation: "
            f"{last_location}"
        )

        return last_location


    # ========================================================
    # NOTHING AVAILABLE
    # ========================================================

    print(
        "⚠️ Roblox says the player is "
        "In Game, but the experience "
        "information is unavailable."
    )

    print(
        "DEBUG - placeId:",
        presence.get("placeId")
    )

    print(
        "DEBUG - rootPlaceId:",
        presence.get("rootPlaceId")
    )

    print(
        "DEBUG - gameId:",
        presence.get("gameId")
    )

    print(
        "DEBUG - universeId:",
        presence.get("universeId")
    )

    print(
        "DEBUG - lastLocation:",
        presence.get("lastLocation")
    )

    return None


# ============================================================
# CURRENT PLAYER STATE
# ============================================================

def get_current_player_state():

    presence = (
        get_roblox_presence()
    )

    current_status = (
        get_status_text(
            presence
        )
    )

    current_game = None

    if current_status == "In Game":

        current_game = (
            get_current_game(
                presence
            )
        )

    return (
        current_status,
        current_game
    )


# ============================================================
# DISCORD READY
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
# /PING
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
# /STATUS
# ============================================================

@tree.command(
    name="status",
    description=(
        "Immediately check the Roblox "
        "player's current status."
    ),
    guild=GUILD
)
async def status(
    interaction: discord.Interaction
):

    try:

        presence = (
            get_roblox_presence()
        )

        current_status = (
            get_status_text(
                presence
            )
        )

        # ----------------------------------------------------
        # IN GAME
        # ----------------------------------------------------

        if current_status == "In Game":

            game_name = (
                get_current_game(
                    presence
                )
            )

            if game_name:

                await interaction.response.send_message(
                    f"**{PLAYER_DISPLAY_NAME}** "
                    f"(**{PLAYER_USERNAME}**) "
                    f"is currently **In Game** 🎮\n"
                    f"Playing: **{game_name}**"
                )

            else:

                await interaction.response.send_message(
                    f"**{PLAYER_DISPLAY_NAME}** "
                    f"(**{PLAYER_USERNAME}**) "
                    f"is currently **In Game** 🎮\n"
                    f"⚠️ Roblox is hiding the "
                    f"experience information."
                )

            return


        # ----------------------------------------------------
        # OTHER STATUS
        # ----------------------------------------------------

        await interaction.response.send_message(
            f"**{PLAYER_DISPLAY_NAME}** "
            f"(**{PLAYER_USERNAME}**) "
            f"is currently "
            f"**{current_status}**."
        )


    except requests.RequestException as error:

        print(
            f"❌ Status lookup failed: "
            f"{error}"
        )

        await interaction.response.send_message(
            "❌ Roblox's presence service "
            "could not be reached."
        )


    except Exception as error:

        print(
            f"❌ Status command error: "
            f"{error}"
        )

        await interaction.response.send_message(
            "❌ Something went wrong while "
            "checking the player's status."
        )


# ============================================================
# /STARTWATCH
# ============================================================

@tree.command(
    name="startwatch",
    description=(
        "Start monitoring the Roblox "
        "player every 30 seconds."
    ),
    guild=GUILD
)
async def startwatch(
    interaction: discord.Interaction
):

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


    # --------------------------------------------------------
    # INITIAL LOOKUP
    # --------------------------------------------------------

    try:

        presence = (
            get_roblox_presence()
        )

        previous_status = (
            get_status_text(
                presence
            )
        )

        previous_game = None

        if previous_status == "In Game":

            previous_game = (
                get_current_game(
                    presence
                )
            )


    except requests.RequestException as error:

        print(
            f"❌ Initial watcher lookup "
            f"failed: {error}"
        )

        await interaction.response.send_message(
            "❌ I couldn't get the player's "
            "current Roblox status."
        )

        return


    except Exception as error:

        print(
            f"❌ Initial watcher error: "
            f"{error}"
        )

        await interaction.response.send_message(
            "❌ Something went wrong while "
            "starting the watcher."
        )

        return


    # --------------------------------------------------------
    # START WATCHER
    # --------------------------------------------------------

    watching = True

    watch_channel = (
        interaction.channel
    )

    watch_loop.start()


    # --------------------------------------------------------
    # CONFIRMATION
    # --------------------------------------------------------

    message = (
        f"👀 Started watching "
        f"**{PLAYER_DISPLAY_NAME}** "
        f"(**{PLAYER_USERNAME}**) "
        f"every 30 seconds.\n"
        f"Current status: "
        f"**{previous_status}**"
    )


    if previous_game:

        message += (
            f"\n🎮 Playing: "
            f"**{previous_game}**"
        )

    elif previous_status == "In Game":

        message += (
            "\n⚠️ Roblox isn't providing "
            "the experience information."
        )


    await interaction.response.send_message(
        message
    )


# ============================================================
# /STOPWATCH
# ============================================================

@tree.command(
    name="stopwatch",
    description=(
        "Stop monitoring the Roblox player."
    ),
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
# /PLAYER
# ============================================================

@tree.command(
    name="player",
    description=(
        "Show the Roblox account currently "
        "being monitored."
    ),
    guild=GUILD
)
async def player(
    interaction: discord.Interaction
):

    await interaction.response.send_message(
        f"👤 Currently monitoring "
        f"**{PLAYER_DISPLAY_NAME}** "
        f"(**{PLAYER_USERNAME}**)\n"
        f"ID: `{PLAYER_ID}`"
    )


# ============================================================
# /WATCHSTATUS
# ============================================================

@tree.command(
    name="watchstatus",
    description=(
        "Show whether automatic monitoring "
        "is running."
    ),
    guild=GUILD
)
async def watchstatus(
    interaction: discord.Interaction
):

    if watching:

        await interaction.response.send_message(
            f"🟢 Automatic monitoring is "
            f"**running**.\n"
            f"Watching: "
            f"**{PLAYER_DISPLAY_NAME}** "
            f"(**{PLAYER_USERNAME}**)"
        )

    else:

        await interaction.response.send_message(
            "🔴 Automatic monitoring is "
            " **stopped**."
        )


# ============================================================
# /SETPLAYER
# ============================================================

@tree.command(
    name="setplayer",
    description=(
        "Change the Roblox account "
        "being monitored."
    ),
    guild=GUILD
)
@app_commands.describe(
    username=(
        "The Roblox username to monitor"
    )
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

    payload = {
        "usernames": [
            username
        ],
        "excludeBannedUsers": False
    }


    # --------------------------------------------------------
    # USER LOOKUP
    # --------------------------------------------------------

    try:

        response = session.post(
            url,
            json=payload,
            timeout=10
        )

        response.raise_for_status()

        users = response.json().get(
            "data",
            []
        )


    except requests.RequestException as error:

        print(
            f"❌ User lookup failed: "
            f"{error}"
        )

        await interaction.response.send_message(
            "❌ Roblox's user lookup failed."
        )

        return


    if not users:

        await interaction.response.send_message(
            f"❌ I couldn't find a Roblox "
            f"user named `{username}`."
        )

        return


    # --------------------------------------------------------
    # USER INFORMATION
    # --------------------------------------------------------

    new_username = users[0][
        "name"
    ]

    new_display_name = users[0][
        "displayName"
    ]

    new_id = users[0][
        "id"
    ]


    # --------------------------------------------------------
    # ALREADY SELECTED
    # --------------------------------------------------------

    if new_id == PLAYER_ID:

        await interaction.response.send_message(
            f"👀 **{PLAYER_DISPLAY_NAME}** "
            f"(**{PLAYER_USERNAME}**) "
            f"is already being watched."
        )

        return


    # --------------------------------------------------------
    # UPDATE PLAYER
    # --------------------------------------------------------

    PLAYER_USERNAME = (
        new_username
    )

    PLAYER_DISPLAY_NAME = (
        new_display_name
    )

    PLAYER_ID = new_id


    # --------------------------------------------------------
    # REFRESH WATCHER BASELINE
    # --------------------------------------------------------

    if watching:

        try:

            presence = (
                get_roblox_presence()
            )

            previous_status = (
                get_status_text(
                    presence
                )
            )

            previous_game = None

            if previous_status == "In Game":

                previous_game = (
                    get_current_game(
                        presence
                    )
                )

        except Exception as error:

            print(
                f"⚠️ Failed to refresh "
                f"watcher state: {error}"
            )

            previous_status = None

            previous_game = None


    else:

        previous_status = None

        previous_game = None


    await interaction.response.send_message(
        f"✅ Now monitoring "
        f"**{PLAYER_DISPLAY_NAME}** "
        f"(**{PLAYER_USERNAME}**)\n"
        f"ID: `{PLAYER_ID}`"
    )


# ============================================================
# /HELP
# ============================================================

@tree.command(
    name="help",
    description=(
        "Show all available commands."
    ),
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
        "Immediately checks the player's "
        "current status and experience.\n\n"

        "**`/startwatch`**\n"
        "Starts automatic monitoring every "
        "30 seconds.\n\n"

        "**`/stopwatch`**\n"
        "Stops automatic monitoring.\n\n"

        "**`/setplayer username:`**\n"
        "Changes the Roblox account being "
        "monitored.\n\n"

        "**`/player`**\n"
        "Shows the currently monitored "
        "Roblox account.\n\n"

        "**`/watchstatus`**\n"
        "Shows whether automatic monitoring "
        "is running.\n\n"

        "**`/help`**\n"
        "Shows this help message."
    )


    await interaction.response.send_message(
        message
    )


# ============================================================
# 30-SECOND WATCHER
# ============================================================

@tasks.loop(
    seconds=30
)
async def watch_loop():

    global previous_status
    global previous_game


    try:

        # ----------------------------------------------------
        # GET PRESENCE
        # ----------------------------------------------------

        presence = (
            get_roblox_presence()
        )

        current_status = (
            get_status_text(
                presence
            )
        )


        print(
            f"Checked "
            f"{PLAYER_DISPLAY_NAME} "
            f"({PLAYER_USERNAME}): "
            f"{current_status}"
        )


        # ----------------------------------------------------
        # GET CURRENT GAME
        # ----------------------------------------------------

        current_game = None

        if current_status == "In Game":

            current_game = (
                get_current_game(
                    presence
                )
            )

            if current_game:

                print(
                    f"Currently playing: "
                    f"{current_game}"
                )

            else:

                print(
                    "In Game, but Roblox "
                    "did not expose the "
                    "experience."
                )


        # ----------------------------------------------------
        # FIRST CHECK
        # ----------------------------------------------------

        if previous_status is None:

            previous_status = (
                current_status
            )

            previous_game = (
                current_game
            )

            print(
                "Watcher baseline established."
            )

            return


        # ----------------------------------------------------
        # SAME STATUS
        # ----------------------------------------------------

        if current_status == previous_status:

            # ------------------------------------------------
            # GAME CHANGED
            # ------------------------------------------------

            if (
                current_status == "In Game"
                and current_game != previous_game
            ):

                old_game = (
                    previous_game
                )

                previous_game = (
                    current_game
                )


                if watch_channel is not None:

                    # ----------------------------------------
                    # NEW GAME FOUND
                    # ----------------------------------------

                    if current_game:

                        if old_game:

                            message = (
                                f"🎮 "
                                f"**{PLAYER_DISPLAY_NAME}** "
                                f"(**{PLAYER_USERNAME}**) "
                                f"changed experience:\n"
                                f"**{old_game}** → "
                                f"**{current_game}**"
                            )

                        else:

                            message = (
                                f"🎮 "
                                f"**{PLAYER_DISPLAY_NAME}** "
                                f"(**{PLAYER_USERNAME}**) "
                                f"is playing "
                                f"**{current_game}**"
                            )


                    # ----------------------------------------
                    # GAME UNKNOWN
                    # ----------------------------------------

                    else:

                        message = (
                            f"🎮 "
                            f"**{PLAYER_DISPLAY_NAME}** "
                            f"(**{PLAYER_USERNAME}**) "
                            f"is in a game, but "
                            f"Roblox didn't expose "
                            f"the experience name."
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

        old_status = (
            previous_status
        )

        previous_status = (
            current_status
        )

        previous_game = (
            current_game
        )


        print(
            f"Status changed: "
            f"{old_status} → "
            f"{current_status}"
        )


        if watch_channel is None:

            return


        # ----------------------------------------------------
        # ENTERED GAME
        # ----------------------------------------------------

        if current_status == "In Game":

            if current_game:

                message = (
                    f"🔄 "
                    f"**{PLAYER_DISPLAY_NAME}** "
                    f"(**{PLAYER_USERNAME}**) "
                    f"changed status:\n"
                    f"**{old_status}** → "
                    f"**In Game**\n"
                    f"🎮 Playing: "
                    f"**{current_game}**"
                )

            else:

                message = (
                    f"🔄 "
                    f"**{PLAYER_DISPLAY_NAME}** "
                    f"(**{PLAYER_USERNAME}**) "
                    f"changed status:\n"
                    f"**{old_status}** → "
                    f"**In Game**\n"
                    f"⚠️ Roblox did not expose "
                    f"the experience name."
                )


        # ----------------------------------------------------
        # LEFT GAME / OTHER STATUS
        # ----------------------------------------------------

        else:

            message = (
                f"🔄 "
                f"**{PLAYER_DISPLAY_NAME}** "
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
            f"⚠️ Roblox API error: "
            f"{error}"
        )

    except Exception as error:

        print(
            f"⚠️ Watcher error: "
            f"{error}"
        )


# ============================================================
# START BOT
# ============================================================

if not TOKEN:

    raise RuntimeError(
        "DISCORD_TOKEN was not found "
        "in the .env file."
    )


client.run(
    TOKEN
)
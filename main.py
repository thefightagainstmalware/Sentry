import json, discord, aiohttp, os, re, subprocess
from discord.ext import tasks  # type: ignore
from dotenv import load_dotenv
from typing import Dict, Tuple, Union, cast, no_type_check


class RateLimitClient(discord.Bot):
    ratelimit: int
    time_remaining: int


discord_invite_re = re.compile(
    r"(https?:\/\/)?(www\.)?(discord\.(gg)|discord(?:app)?\.com\/invite)\/[^\s\/]+?(?=\b)"
)

uuid_re = re.compile(
    r"[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}",
    flags=re.IGNORECASE,
)


def build_dict_data(
    original_data: Dict[str, Union[str, int]],
) -> Dict[str, Dict[str, Union[str, int]]]:
    """
    Builds a new dict with the original data, to not ping you every second you're online
    """
    new_data = {}
    if original_data is None:
        return new_data
    for k, v in original_data.items():
        new_data[k] = {"discord_id": v, "is_online": False}
    return new_data


def build_json_data(
    original_data: Dict[str, Dict[str, Union[str, int]]],
) -> Dict[str, Union[str, int]]:
    new_data = {}
    if original_data is None:
        return new_data
    for k, v in original_data.items():
        new_data[k] = v["discord_id"]
    return new_data


load_dotenv()

if os.getenv("MAIN_GUILD_ID") is not None:
    client = RateLimitClient(debug_guilds=[int(os.getenv("MAIN_GUILD_ID"))]) # type: ignore
else:
    client = RateLimitClient() # type: ignore

if not os.path.exists("players.json"):
    with open("players.json", "w") as f:
        json.dump({}, f)

watched_players = build_dict_data(json.load(open("players.json")))
if os.path.exists(".git"):
    try:
        VERSION = (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
            .decode("utf-8")
            .strip()
        )
    except Exception:
        VERSION = "unknown"
else:
    VERSION = "unknown"


async def get_uuid(username: str) -> str:
    async with aiohttp.ClientSession() as session:
        if not uuid_re.match(username):
            async with session.get(
                "https://api.mojang.com/users/profiles/minecraft/{}".format(username)
            ) as resp:
                uuid: str = (await resp.json())["id"]
        else:
            uuid = username.replace("-", "").lower()
        return uuid


async def is_player_online(uuid: str) -> bool:
    global client
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://api.hypixel.net/player?key={os.getenv('HYPIXEL_API_KEY')}&uuid={uuid}"
        ) as resp:
            if resp.status == 200:
                client.ratelimit = int(resp.headers["ratelimit-remaining"])
                client.time_remaining = int(resp.headers["ratelimit-reset"])
                data = await resp.json()
                if data["player"] is None:
                    return False
                if (
                    "lastLogin" not in data["player"]
                    or "lastLogout" not in data["player"]
                ):
                    return False  # appear offline
                return (data["player"]["lastLogin"] or 0) > (
                    data["player"]["lastLogout"] or 0
                )
            else:
                return False


async def get_discord_info(username: str = "", uuid: str = "") -> Tuple[str, str]:
    async with aiohttp.ClientSession() as session:
        if uuid == "":
            uuid = await get_uuid(username)
        async with session.get(
            f"https://api.hypixel.net/player?key={os.getenv('HYPIXEL_API_KEY')}&uuid={uuid}"
        ) as resp:
            if resp.status == 200:
                client.ratelimit = int(resp.headers["ratelimit-remaining"])
                client.time_remaining = int(resp.headers["ratelimit-reset"])
                data = await resp.json()
                if data["player"] is None:
                    return "", uuid
                try:
                    return data["player"]["socialMedia"]["links"]["DISCORD"], uuid
                except KeyError:
                    return "", uuid
            else:
                return "", uuid


@tasks.loop(seconds=1)  # type: ignore
async def check_online() -> None:
    if hasattr(client, "ratelimit"):
        if client.ratelimit == 0 and client.time_remaining > 0:
            client.time_remaining -= 1
            return
        elif client.time_remaining == 0:
            client.ratelimit = 120
    if watched_players == None:
        return
    for k, v in watched_players.items():
        player_online = await is_player_online(k)
        if player_online != v["is_online"]:
            v["is_online"] = player_online
            if player_online:
                user = await client.fetch_user(cast(int, v["discord_id"]))
                await user.send(f"Account with uuid {k} logged in")


@client.event
async def on_ready() -> None:
    print("We have logged in as {0.user}".format(client))
    check_online.start()
    await client.change_presence(
        activity=discord.Activity( # type: ignore
            type=discord.ActivityType.watching, name=" the gates of Hypixel"
        )
    )


@client.command()  # type: ignore
async def watch(
    ctx: discord.ApplicationContext, username: str = "", uuid: str = ""
) -> None:
    """Watch your Minecraft account"""
    global watched_players
    if watched_players and username in watched_players:
        await ctx.respond(f"{username} is already being watched!")
        return
    if username == "" and uuid == "":
        await ctx.respond("You need to provide a username or uuid")
        return
    discord_username, uuid = await get_discord_info(username, uuid)
    if discord_username == "":
        await ctx.respond(
            "I couldn't find your discord informaton! Link it to your Hypixel profile!"
        )
        return
    elif discord_username != str(ctx.author):
        if discord_invite_re.fullmatch(discord_username):
            url = discord_username
            try:
                invite = await client.fetch_invite(url)
            except discord.NotFound:
                await ctx.respond(
                    f"It looks like there's an invite ({url}) in your Hypixel profile's discord, but it doesn't exist!"
                )
                return
            if isinstance(invite.inviter, type(None)):
                await ctx.respond(
                    f"It looks like there's an invite ({url}) in your Hypixel profile's discord, but it doesn't have an inviter! <@{client.owner_id}> investigate!"
                )
                return
            if invite.inviter.id != ctx.author.id:  # type: ignore
                await ctx.respond(
                    f"It looks like there's an invite ({url}) in your Hypixel profile's discord, but you didn't create it!"
                )
                return
        else:
            await ctx.respond(
                f"Your MC account is linked to {discord_username}'s discord account! Change it to {ctx.author}"
            )
            return
    watched_players[uuid] = {"discord_id": ctx.author.id, "is_online": False}  # type: ignore
    await ctx.respond(f"Your account is now being watched!")
    json.dump(build_json_data(watched_players), open("players.json", "w"))


@client.command()  # type: ignore
async def unwatch(
    ctx: discord.ApplicationContext, username: str = "", uuid: str = ""
) -> None:
    """Unwatch your Minecraft account"""
    global watched_players
    if username == "" and uuid == "":
        await ctx.respond("You need to specify a username or uuid!")
        return
    if username != "":
        uuid = await get_uuid(username)
    if uuid in watched_players:
        if watched_players[uuid]["discord_id"] != ctx.author.id: # type: ignore
            await ctx.respond(f"You can't unwatch someone else!")
            return
        await ctx.respond(f"You are no longer being watched!")
        del watched_players[uuid]
        json.dump(build_json_data(watched_players), open("players.json", "w"))
    else:
        await ctx.respond(f"You are not being watched!")

@no_type_check
@client.command()  # type: ignore
async def info(ctx: discord.ApplicationContext) -> None:
    """Get information about the bot"""
    info_embed = discord.Embed(
        title=client.user.name,
        description="This bot is a bot that watches your Hypixel account and sends you a message when you log in.\nFork me on GitHub: https://github.com/thefightagainstmalware/Sentry",
        color=discord.Color.blue(),
    )
    info_embed.set_footer(
        text=f"{client.user.name} ver: {VERSION}", icon_url=client.user.avatar.url
    )
    await ctx.respond(embed=info_embed)


client.run(os.getenv("DISCORD_TOKEN"))

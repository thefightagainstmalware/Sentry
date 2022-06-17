import json, discord, aiohttp, os
from discord.ext import tasks, commands
from dotenv import load_dotenv
from typing import Optional


def build_dict_data(
    original_data: "dict[str, str]",
) -> "dict[str, dict[str, str | bool]]":
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
    original_data: "dict[str, dict[str, str | bool]]",
) -> "dict[str, str]":
    new_data = {}
    if original_data is None:
        return new_data
    for k, v in original_data.items():
        new_data[k] = v["discord_id"]
    return new_data

load_dotenv()

client = discord.Bot(debug_guilds=[910733698452815912])
if not os.path.exists("players.json"):
    with open("players.json", "w") as f:
        json.dump({}, f)
    
watched_players = build_dict_data(json.load(open("players.json"))) or {}


async def is_player_online(uuid: str) -> bool:
    global client
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://api.hypixel.net/player?key={os.getenv('HYPIXEL_API_KEY')}&uuid={uuid}"
        ) as resp:
            if resp.status == 200:
                client.ratelimit = resp.headers["ratelimit-remaining"]
                client.time_remaining = resp.headers["ratelimit-reset"]
                data = await resp.json()
                if data["player"] is None:
                    return False
                return (data["player"]["lastLogin"]) > (data["player"]["lastLogout"] or 0)
            else:
                return False


async def get_discord_info(username: str) -> "Optional[tuple[str]]":
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.mojang.com/users/profiles/minecraft/{}".format(username)) as resp:
            uuid: str = (await resp.json())["id"]
        async with session.get(
            f"https://api.hypixel.net/player?key={os.getenv('HYPIXEL_API_KEY')}&uuid={uuid}"
        ) as resp:
            if resp.status == 200:
                client.ratelimit = resp.headers["ratelimit-remaining"]
                client.time_remaining = resp.headers["ratelimit-reset"]
                data = await resp.json()
                if data["player"] is None:
                    return "", uuid
                try:
                    return data["player"]["socialMedia"]["links"]["DISCORD"], uuid
                except KeyError:
                    return "", uuid
            else:
                return "", uuid


@tasks.loop(seconds=1)
async def check_online():
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
                print(v["discord_id"])
                user = await client.fetch_user(v["discord_id"])
                print(user)
                await user.send(f"Account with uuid {k} logged in")


@client.event
async def on_ready():
    print("We have logged in as {0.user}".format(client))
    check_online.start()


@client.command()
async def watch(ctx: commands.Context, username: str):
    global watched_players
    if watched_players and username in watched_players:
        await ctx.respond(f"{username} is already being watched!")
        return
    discord_username, uuid = await get_discord_info(username)
    if discord_username is None:
        await ctx.respond("I couldn't find your discord informaton! Link it to your hypixel profile!")
        return
    elif discord_username != str(ctx.author):
        await ctx.respond(f"Your MC account is linked to {discord_username}'s discord account! Change it to {ctx.author}")
        return
    watched_players[uuid] = {"discord_id": ctx.author.id, "is_online": False}
    await ctx.respond(f"Your account is now being watched!")
    json.dump(build_json_data(watched_players), open("players.json", "w"))
    print(build_json_data(watched_players))

client.run(os.getenv("DISCORD_TOKEN"))
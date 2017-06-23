import asyncio
import json
import discord
from discord.ext import commands
from radio import Radio

if not discord.opus.is_loaded():
    discord.opus.load_opus("opus")

try:
    with open("config.json", "r") as config_file:
        config = json.load(config_file)

    token = config["token"]
    command_prefix = commands.when_mentioned_or(config["command_prefix"])
    description = config["description"]
except FileNotFoundError:
    print("[Error] Unable to find the config.json file.")
except KeyError:
    print("[Error] Invalid configuration file.")
except Exception as e:
    print(f"[Error] {e}")
else:
    bot = commands.Bot(command_prefix=command_prefix, description=description)
    bot.add_cog(Radio(bot, config))
    bot.run(token)
import re
import discord
import json
import asyncio
from random import shuffle
from urllib.parse import urlparse
from discord.ext import commands

if not discord.opus.is_loaded():
    discord.opus.load_opus("opus")

class Radio:
    def __init__(self, bot, config, playlist=None):
        self.bot = bot
        self.config = config
        self.voice = None
        self.player = None
        self.current_id = None
        self.voice_channel = None
        self.skip_count = 0
        self.voters = []
        self.vol = self.config["volume"]
        self.play_next_song = asyncio.Event()
        if playlist is not None:
            self.playlist = playlist
        else:
            self.playlist = []
        self.stack = []

    async def on_ready(self):
        await self.bot.change_presence(game=discord.Game(name="%help"))

    async def on_message(self, message):
        if "youtube" in message.content and message.channel.id == self.config["music_channel"] and not message.author.bot:
            try:
                url = re.search("(?P<url>https?://[^\s]+)", message.content).group("url")
                param = urlparse(url).query
                if param[0:2] != "v=":
                    param = "".join(("v=", param.split("v=")[1]))
                if "list" not in param and param[2:] not in self.playlist and param[2:] not in self.stack:
                    self.playlist.append(param[2:])
                    with open(self.config["playlist_path"], "a") as data:
                        data.write(param + "\n") 
            except Exception as e:
                print(e)
        self.bot.process_commands(message)

    def toggle_next(self):
        self.bot.loop.call_soon_threadsafe(self.play_next_song.set)

    @commands.command(pass_context=True, no_pm=True)
    async def volume(self, ctx, vol : int=None):
        """ Set the volume of the radio, any value between 0 and 100 """
        if ctx.message.author.voice_channel is None or ctx.message.author.bot:
                await self.bot.say("You are not in the voice channel!")
                return False
        elif ctx.message.author.voice_channel != self.voice_channel:
                await self.bot.say("You are not in the voice channel!")
                return False

        if vol is None:
            await self.bot.say(f"Volume is {self.vol*100}%")

        elif vol >= 0 and vol <= 100 and not ctx.message.author.bot:
            self.vol = vol * .01
            if self.player is not None:
                self.player.volume = self.vol
                await self.bot.say(f"Set player volume to {vol}%")

    @commands.command(pass_context=True, no_pm=True)
    async def summon(self, ctx):
        """
        Summons the bot to your current voice channel
        """
        try:
            if ctx.message.author.voice_channel is None or ctx.message.author.bot:
                return False

            if self.player is not None:
                if self.player.is_playing():
                    await self.bot.say("Bot is currently playing a song! Cannot move.")
                    return False
            
            self.voice_channel = ctx.message.author.voice_channel
            if self.voice is None:
                try:
                    self.voice = await self.bot.join_voice_channel(self.voice_channel)
                except Exception as e:
                    self.voice = None
                    self.voice_channel = None
                    print(e)
                    return False
            else:
                await self.voice.move_to(self.voice_channel)
                return False

            while len(self.voice_channel.voice_members) > 1:
                self.play_next_song.clear()
                self.skip_count = 0
                self.voters = []
                self.current_id = self.playlist.pop()
                self.stack.append(self.current_id)
                if len(self.playlist) == 0:
                    self.playlist = self.stack
                    shuffle(self.playlist)
                    self.stack = []
                self.player = await self.voice.create_ytdl_player(self.current_id, after=self.toggle_next, before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5")
                await self.bot.change_presence(game=discord.Game(name=self.player.title))
                self.player.volume = self.vol
                self.player.start()
                await self.play_next_song.wait()
            
            await self.voice.disconnect()
            await self.bot.change_presence(game=discord.Game(name="%help"))

            self.voice = None
            self.player = None
            self.current_id = None
            self.voice_channel = None
            self.skip_count = 0
            self.voters = []
        except:
            pass

    @commands.command(pass_context=True, no_pm=True)
    async def skip(self, ctx):
        """Skips the currently playing song, if any."""
        if self.player is not None:
            if ctx.message.author not in self.voice_channel.voice_members:
                await self.bot.say("You are not in the voice channel!")
                return
            elif ctx.message.author in self.voters:
                await self.bot.say("You have already voted!")
                return
            elif ctx.message.author.bot:
                return
            bots_in_channel = 0
            self.skip_count += 1
            self.voters.append(ctx.message.author)
            for user in self.voice_channel.voice_members:
                if user.bot:
                    bots_in_channel += 1
            current_user_amount = len(self.voice_channel.voice_members) - bots_in_channel
            required_to_skip = int(current_user_amount+1 * self.config["skip_percentage"])
            
            await self.bot.say(f"{self.skip_count}/{required_to_skip} users have voted to skip!")
            if self.skip_count >= required_to_skip:
                await self.bot.say("Skipping song!")
                self.player.stop()
                self.skip_count = 0
                self.voters = []
        else:
            self.voters = []
            self.skip_count = 0


    @commands.command(pass_context=True, no_pm=True)
    async def playing(self, ctx):
        """Retrieves the currently playing song, if any."""
        if self.current_id is not None:
            if self.current_id[:2] == "v=":
                 self.current_id = self.current_id[2:]


            title = self.player.title
            url = self.player.url
            mins, seconds = divmod(self.player.duration, 60)
            desc = f"Duration: {mins}:{seconds}\nViews: {self.player.views}\nUploader: {self.player.uploader}"
            embed = discord.Embed(type="rich", title=title, url=url, description=desc)
            embed.set_thumbnail(url=f"https://img.youtube.com/vi/{self.current_id}/0.jpg")

            await self.bot.say(embed=embed)


# Initalize
with open("config.json", "r") as f:
    config = json.load(f)

playlist = []
with open(config["playlist_path"], "r") as data:
    for video in data:
        playlist.append(video.replace("\n", ""))

shuffle(playlist)

bot = commands.Bot(command_prefix=commands.when_mentioned_or(config["prefix"]), description=config["description"])
bot.add_cog(Radio(bot, config, playlist))
bot.run(config["token"])

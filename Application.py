import re
import discord
import json
from discord.ext import commands
from random import choice, shuffle
import asyncio

if not discord.opus.is_loaded():
    discord.opus.load_opus('opus')

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
        self.play_next_song = asyncio.Event()
        if playlist is not None:
            self.playlist = playlist
        else:
            self.playlist = []
        self.stack = []

    async def on_message(self, message):
        if 'youtube' in message.content and message.channel.id == self.config["music_channel"]:
            try:
                url = re.search("(?P<url>https?://[^\s]+)", message.content).group("url")
                param = re.search("(\?|\&)([^=]+)\=([^&]+)", url)[0]
                if 'list' not in param and param[3:] not in playlist:
                    param = param[3:]
                    print(f"Appended video: {param}")
                    self.playlist.append(param)
                    with open(self.config['playlist_path'], "a+") as data:
                        data.write(param + '\n') 
            except Exception as e:
                print(e)
        self.bot.process_commands(message)

    def toggle_next(self):
        self.bot.loop.call_soon_threadsafe(self.play_next_song.set)

    @commands.command(pass_context=True, no_pm=True)
    async def summon(self, ctx):
        '''
        Summons the bot to your current voice channel
        '''
        try:
            if ctx.message.author.voice_channel is None:
                return False
            
            self.voice_channel = ctx.message.author.voice_channel
            if self.voice is None:
                self.voice = await bot.join_voice_channel(self.voice_channel)
            else:
                await self.voice.move_to(self.voice_channel)
                return False

            while True:
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
                await bot.change_presence(game=discord.Game(name=self.player.title))
                self.player.volume = self.config['volume']
                self.player.start()
                await self.play_next_song.wait()
        except:
            pass    

    @commands.command(pass_context=True, no_pm=True)
    async def skip(self, ctx):
        """Skips the currently playing song, if any."""
        if self.player is not None:
            if ctx.message.author not in self.voice_channel.voice_members:
                await self.bot.say("You are not in the voice channel!")
                return
            if ctx.message.author in self.voters:
                await self.bot.say("You have already voted!")
                return
            self.skip_count += 1
            self.voters.append(ctx.message.author)

            current_user_amount = len(self.voice_channel.voice_members)
            required_to_skip = int((current_user_amount  + 1)* self.config['skip_percentage'])

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
            await self.bot.say(f"https://www.youtube.com/watch?v={self.current_id}")

# Initalize
with open('config.json', 'r') as f:
    config = json.load(f)

playlist = []
with open(config['playlist_path'], "r") as data:
    for video in data:
        playlist.append(video)

shuffle(playlist)

bot = commands.Bot(command_prefix=commands.when_mentioned_or(config['prefix']), description=config['description'])
bot.add_cog(Radio(bot, config, playlist))
bot.run(config['token'])
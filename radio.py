from __future__ import unicode_literals
import asyncio
import discord
from discord.ext import commands

import re
import urllib.parse as urlparse
from collections import deque
from random import shuffle

class Radio:
    """
    Radio cog for Discord.py Rewrite.
    Plays music from a #music channel or songs queued by the users.
    """
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config["radio"]

        self.queue = deque()

        self.player = None
        self.video_id = None
        self.voice = None
        self.play_next_song = asyncio.Event()

        try:
            with open(self.config["playlist_file"], "r") as playlist:
                temp = []

                for song in playlist:
                    temp.append(song.rstrip("\n"))

                if self.config["shuffle"]:
                    shuffle(temp)
                
                self.playlist = deque(temp)

        except FileNotFoundError:
            print("[Error] Unable to load a playlist file.")
            return

        print(f"[Radio] initalized.")

    async def on_ready(self):
        await self.set_status()

    async def on_message(self, message):
        if not message.author.bot and message.channel.id == self.config["music_channel"]:
            self.process_links(message.content)

    def toggle_next(self):
        self.bot.loop.call_soon_threadsafe(self.play_next_song.set)

    def process_links(self, content):
        urls = re.findall(r"(https?://\S+)", content)
        for url in urls:
            if "youtube" in url:
                parsed = urlparse.urlparse(url)
                params = urlparse.parse_qs(parsed.query)
                if "v" in params:
                    self.add_video(params["v"][0])

    def add_video(self, video_id):
        print(f"[Add Video] {video_id}")
        if video_id not in self.playlist:
            self.playlist.appendleft(video_id)
            with open(self.config["playlist_file"], "a") as data:
                data.write(video_id + "\n")
        self.queue.appendleft(video_id)

    def retrieve_next_video(self):
        video_id = None
        if len(self.queue) > 0:
            video_id = self.queue.pop()
        elif len(self.playlist) > 0:
            video_id = self.playlist.pop()
            self.playlist.appendleft(video_id)
        print(f"[Retrieve Video] {video_id}")
        return video_id

    async def set_status(self, status=None):
        if status is not None:
            await self.bot.change_presence(game=discord.Game(name=status))
        else:
            await self.bot.change_presence(game=discord.Game(name=self.config["status"]))

    @commands.command(pass_context=True, no_pm=True)
    async def summon(self, ctx):
        """Summons the bot to your voice channel."""
        if ctx.message.author.voice_channel is None:
            return

        if self.player is not None:
            if self.player.is_playing():
                return

        voice_channel = ctx.message.author.voice_channel

        if self.voice is None:
            self.voice = await self.bot.join_voice_channel(voice_channel)

        while len(voice_channel.voice_members) > 1:
            self.play_next_song.clear()

            self.video_id = self.retrieve_next_video()

            if self.video_id is None:
                break

            url = f"https://www.youtube.com/watch?v={self.video_id}"
            
            self.player = await self.voice.create_ytdl_player(url, after=self.toggle_next, before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5")
            await self.set_status(self.player.title)
            self.player.volume = self.config["volume"]
            self.player.start()
            await self.play_next_song.wait()

        await self.voice.disconnect()
        await self.set_status()
        self.player = None
        self.video_id = None
        self.voice = None
    
    @commands.command(pass_context=True, no_pm=True)
    async def now(self, ctx):
        """Displays currently playing video."""
        if self.video_id is not None and self.player is not None:
            title = self.player.title
            url = self.player.url
            mins, seconds = divmod(self.player.duration, 60)
            desc = (f"Duration: {mins}:{seconds:02d}\n"
                    f"Views: {self.player.views}\n"
                    f"Uploader: {self.player.uploader}")
            embed = discord.Embed(type="rich", title=title, url=url, description=desc)
            embed.set_thumbnail(url=f"https://img.youtube.com/vi/{self.video_id}/0.jpg")
            await self.bot.say(embed=embed)

    @commands.command(pass_context=True, no_pm=True)
    async def add(self, ctx):
        """Add YouTube video to queue by URL."""
        # process_links will still be called even if this is the
        # music channel, this just prevents duplication of videos.
        if ctx.message.channel.id != self.config["music_channel"]:
            self.process_links(ctx.message.content)


    @commands.command(pass_context=True, no_pm=True)
    async def skip(self, ctx):
        """Skips the currently playing video."""
        if self.player is not None:
            self.player.stop()

    @commands.command(pass_context=True, no_pm=True)
    async def pause(self, ctx):
        """Pauses the currently playing video"""
        if self.player is not None:
            self.player.pause()

    @commands.command(pass_context=True, no_pm=True)
    async def resume(self, ctx):
        """Unpauses the currently playing video"""
        if self.player is not None:
            self.player.resume()
    
    @commands.command(pass_context=True, no_pm=True)
    async def volume(self, ctx, vol:int):
        """Sets the volume of the player between 0 and 100"""
        if vol > 0 and vol <= 100:
            vol = vol * .01
            if self.player is not None:
                self.config["volume"] = vol
                self.player.volume = vol

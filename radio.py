from __future__ import unicode_literals
import asyncio
import discord
from discord.ext import commands
import youtube_dl

import re
import functools
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

        self.video_id = None
        self.voice = None
        self.play_next_song = asyncio.Event()
        self.info = None

        self.ydl_opts = {
            "format": "opus[abr>0]/bestaudio/best",
            "prefer_ffmpeg": True
        }

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
            await self.process_links(message.content, queue=False)

    def toggle_next(self, error):
        self.bot.loop.call_soon_threadsafe(self.play_next_song.set)

    async def youtube_dl_process(self, url):
        ''' Uses youtube-dl to process the link and return 1 url '''

        opts = {"noplaylist": True, "playlistend": 1, 'ignoreerrors': True}

        ydl = youtube_dl.YoutubeDL(opts)
        func = functools.partial(ydl.extract_info, url, download=False)
        info = await self.bot.loop.run_in_executor(None, func)
        if "entries" in info:
            info = info['entries'][0]

        return info

    async def process_links(self, content, queue=False):
        urls = re.findall(r"(https?://\S+)", content)
        for url in urls:
            if "youtube" in url:
                info = await self.youtube_dl_process(url)

                if info:
                    parsed = urlparse.urlparse(info["webpage_url"])
                    params = urlparse.parse_qs(parsed.query)
                    if "v" in params:
                        self.add_video(params["v"][0], queue=queue)
            elif "soundcloud" in url:
                info = await self.youtube_dl_process(url)

                if info:
                    self.add_video(info["webpage_url"], queue=queue)

    def add_video(self, video_id, queue=False):
        print(f"[Add Video] {video_id}")
        if video_id not in self.playlist:
            self.playlist.appendleft(video_id)
            with open(self.config["playlist_file"], "a") as data:
                data.write(video_id + "\n")
        if video_id not in self.queue and queue:
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
        if ctx.message.author.voice is None:
            return
        
        voice_channel = ctx.message.author.voice.channel

        if self.voice is None:
            self.voice = await voice_channel.connect()
        else:
            await self.voice.move_to(ctx.message.author.voice.channel)
            return

        while len(voice_channel.members) > 1:
            self.play_next_song.clear()

            self.video_id = self.retrieve_next_video()
            if "soundcloud" in self.video_id:
                url = self.video_id
            else:
                url = f"https://www.youtube.com/watch?v={self.video_id}"

            if self.video_id is None:
                break
            
            ydl = youtube_dl.YoutubeDL(self.ydl_opts)
            func = functools.partial(ydl.extract_info, url, download=False)

            self.info = await self.bot.loop.run_in_executor(None, func)
            download_url = self.info["formats"][0]["url"]
            
            before_args = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
            self.voice.play(discord.FFmpegPCMAudio(download_url, before_options=before_args), after=self.toggle_next)
            # Change the volume of the audio
            self.voice.source = discord.PCMVolumeTransformer(self.voice.source, volume=self.config["volume"])

            await self.set_status(self.info["title"])
            await self.play_next_song.wait()

        await self.voice.disconnect()
        await self.set_status()
        self.voice = None
        self.video_id = None
        self.voice = None
    
    @commands.command(pass_context=True, no_pm=True)
    async def now(self, ctx):
        """Displays currently playing video."""
        if self.video_id is not None and self.voice is not None and self.info is not None:
            title = self.info["title"]
            url = self.info["webpage_url"]
            uploader = self.info["uploader"]
            mins, seconds = divmod(self.info["duration"], 60)
            if "soundcloud" in url:
                desc = (f"Duration: {mins}:{seconds:02d}\n"
                        f"Uploader: {uploader}")
            else:
                view_count = self.info["view_count"]
                desc = (f"Duration: {mins}:{seconds:02d}\n"
                        f"Views: {view_count}\n"
                        f"Uploader: {uploader}")
            embed = discord.Embed(type="rich", title=title, url=url, description=desc)
            embed.set_thumbnail(url=self.info["thumbnail"])
            await ctx.send(embed=embed)

    @commands.command(pass_context=True, no_pm=True)
    async def add(self, ctx):
        """Add YouTube video to queue by URL."""
        # process_links will still be called even if this is the
        # music channel, this just prevents duplication of videos.
        if ctx.message.channel.id != self.config["music_channel"]:
            self.process_links(ctx.message.content, queue=True)

    @commands.command(pass_context=True, no_pm=True)
    async def skip(self, ctx):
        """Skips the currently playing video."""
        if self.voice is not None:
            self.voice.stop()

    @commands.command(pass_context=True, no_pm=True)
    async def pause(self, ctx):
        """Pauses the currently playing video"""
        if self.voice is not None:
            self.voice.pause()

    @commands.command(pass_context=True, no_pm=True)
    async def resume(self, ctx):
        """Unpauses the currently playing video"""
        if self.voice is not None:
            self.voice.resume()
    
    @commands.command(pass_context=True, no_pm=True)
    async def volume(self, ctx, vol:int):
        """Sets the volume of the player between 0 and 100"""
        if vol > 0 and vol <= 100:
            vol = vol * .01
            if self.voice is not None:
                self.config["volume"] = vol
                self.voice.source.volume = vol

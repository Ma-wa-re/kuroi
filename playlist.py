import discord
import asyncio

from random import choice
import json
import re

playlist = []
with open("videos.txt", "r") as data:
    for video in data:
        playlist.append(video)

if not discord.opus.is_loaded():
    discord.opus.load_opus('opus')

client = discord.Client()

play_next_song = asyncio.Event()

video = None

def toggle_next():
    client.loop.call_soon_threadsafe(play_next_song.set)

@client.event
async def on_ready():
    print("Logged in!")

@client.event
async def on_message(message):
    global video
    if message.content.startswith('%summon') and message.author.id == "314215966903107586":
        try:
            if message.author.voice_channel is None:
                return False
            
            voice = await client.join_voice_channel(message.author.voice_channel)

            while True:
                play_next_song.clear()
                video = choice(playlist)
                player = await voice.create_ytdl_player(video, after=toggle_next)
                player.start()
                await play_next_song.wait()
        except:
            pass
    if 'youtube' in message.content and message.channel.id == "280778849615216640":
        try:
            url = re.search("(?P<url>https?://[^\s]+)", message.content).group("url")
            param = re.search("(\?|\&)([^=]+)\=([^&]+)", url)[0]
            if 'list' not in param and param not in playlist:
                print(f"Appended video: {param[3:]}")
                playlist.append(param[3:])
                with open("videos.txt", "a+") as data:
                    data.write(param[3:] + '\n') 
        except Exception as e:
            print(e)
    if message.content.startswith('%playing'):
        if video is not None and message.channel.id != "280778849615216640":
            await client.send_message(message.channel, f"https://www.youtube.com/watch?v={video}")
            

client.run("")

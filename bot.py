import os
import asyncio
import random
import discord
import yt_dlp
import spotipy
import logging
from discord.ext import commands
from discord import User
from spotipy.oauth2 import SpotifyClientCredentials
from queue import Queue
from typing import Dict

from dotenv import load_dotenv

load_dotenv()



# ffmpeg setup
FFMPEG_PATH = os.getenv('ffmpeg_path')
SPOTIFY_ID = os.getenv('spotify_id')
SPOTIFY_SECRET = os.getenv('spotify_secret')
DISCORD_TOKEN = os.getenv('discord_token')



# Initialize the bot with a command prefix
intents = discord.Intents.default()
intents.message_content = True # enable the intent for reading message content (required for text commands)
bot = commands.Bot(command_prefix="!", intents=intents)

# Spotify API setup
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=SPOTIFY_ID,
                                                           client_secret=SPOTIFY_SECRET))


# Initialize global variables
music_queue: Queue[Dict] = Queue(maxsize=100)
is_playing: bool = False
current_song: str = ""
current_song_name: str = ""
current_song_provider: User = None
voice_client: discord.VoiceClient = None




'''
    Event handler for the when the bot spins up, and some associated commands that manage the bot's joined channel-state
'''
@bot.event
async def on_ready() -> None:
    await bot.tree.sync()
    print(f'{bot.user.name} has connected to Discord!')

@bot.tree.command(name="join")
async def join(interaction: discord.Interaction) -> None:
    global voice_client
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        voice_client = await channel.connect()
        await interaction.response.send_message(f"Joined {channel.name}!")
    else:
        await interaction.response.send_message("You need to join a voice channel first!")

@bot.tree.command(name="leave")
async def leave(interaction: discord.Interaction) -> None:
    global voice_client
    if voice_client:
        await voice_client.disconnect()
        voice_client = None
        await interaction.response.send_message("Disconnected from the voice channel.")
    else:
        await interaction.response.send_message("I'm not currently connected to any voice channel.")




'''
    Command to play music from a YouTube URL. It will add the song to the queue if not already playing,
    or if it is, it will play the next song in the queue if available.
'''
@bot.tree.command(name="play")
async def play(interaction: discord.Interaction) -> None:
# async def play(interaction: discord.Interaction, url: str = None) -> None:
    global is_playing, current_song, current_song_name, voice_client

    await interaction.response.defer()

    if voice_client is None:
        await interaction.followup.send("I need to join a voice channel first! Use `/join` to make me join.")
        # await interaction.response.send_message("I need to join a voice channel first! Use `/join` to make me join.")
        return

    def play_next(_) -> None:
        global is_playing, current_song, current_song_name, current_song_provider, not_found
        if not music_queue.empty():
            not_found = False  # Reset the flag for song not found error
            is_playing = True
            current_song_data = music_queue.get() # Dequeue the next song
            current_song_artists = current_song_data.pop("artists", "")
            current_song_provider = current_song_data.pop("provider", 'Unknown')
            current_song_name = list(current_song_data.keys())[0]
            current_song = fetch_music(current_song_name + " " + current_song_artists)

            if current_song == None:
                not_found = True
                return
            voice_client.play(discord.FFmpegPCMAudio(current_song, executable=FFMPEG_PATH, options='-vn'), after=play_next)

            # Create a new task to update the chat with the next song info, if the bot is running in an event loop
            loop = asyncio.get_running_loop()
            if loop.is_running():
                asyncio.create_task(update_chat_on_next_song(interaction=interaction, song_name=current_song_name, song_artist=current_song_artists, url=current_song_data[current_song_name]))
            else:
                # Use the existing loop to run the task
                loop.run_until_complete(update_chat_on_next_song(interaction=interaction, song_name=current_song_name, song_artist=current_song_artists, url=current_song_data[current_song_name]))
            # asyncio.create_task(update_chat_on_next_song(interaction=interaction, song_name=current_song_name, song_artist=current_song_artists, url=current_song_data[current_song_name]))
        else:
            # await interaction.response.send_message(f"No more songs in the queue. Enjoy your music!")
            is_playing = False

    if not is_playing and not music_queue.empty():
        play_next(None)  # Starts playing the next song
        await interaction.followup.send("Now playing: " + '**' + current_song_name + '**')
    elif not is_playing and music_queue.empty(): 
        await interaction.followup.send("The queue is empty. Add some songs to start playing!")
        return
    elif not_found:
        await interaction.followup.send("I couldn't find that song. Please check the spelling and try again.")
    else:
        await interaction.followup.send("Music is already playing!")
        # await interaction.response.send_message(f"{interaction.user} added some groovy tunes to the queue.")
        # music_queue.put(url)  # Enqueue the song if already playing


async def update_chat_on_next_song(interaction: discord.Interaction, song_name: str, song_artist: str, url:str):
    await interaction.response.send_message(f"!! [{song_name}]({url}) by {song_artist} is now playing !!")



@bot.tree.command(name="clear_queue")
async def clear_queue(interaction: discord.Interaction) -> None:
    global music_queue
    music_queue.queue.clear()
    await interaction.response.send_message("Cleared the music queue!")





'''
    Simple voice_client commands to control pause, resume, and skip features
'''
@bot.tree.command(name="pause")
async def pause(interaction: discord.Interaction) -> None:
    global voice_client

    pauser = interaction.user
    pause_response = random.choice([f"{pauser.mention} is consciously stopping the vibes, probably to beat his meat.", f"Everybody 'boo' {pauser.mention}, who tf pauses the queue like that?"])
    await interaction.response.send_message(pause_response)

    if voice_client.is_playing():
        voice_client.pause()

@bot.tree.command(name="resume")
async def resume(interaction: discord.Interaction) -> None:
    global voice_client

    if voice_client.is_paused():
        voice_client.resume()

@bot.tree.command(name="skip")
async def skip(interaction: discord.Interaction) -> None:
    global voice_client

    skipper = interaction.user
    skip_response = random.choice([f"{skipper.mention} is being a bitch and is skipping {current_song_provider.mention}", f"{current_song_provider.mention} stop playing fucking trash, {skipper.mention} is skipping that shit."])
    if not skipper.__eq__(current_song_provider):
        await interaction.response.send_message(skip_response)

    if voice_client.is_playing():
        voice_client.stop()  # This will trigger `play_next` to start the next song





'''
    Spotify Integration to lend the ability to play songs based off a spotify link
'''
@bot.tree.command(name="add")
async def add_to_queue(interaction: discord.Interaction, spotify_url: str) -> None:
    global music_queue

    # acknowledge the interaction and defer it
    await interaction.response.send_message("Looking for your song brah, one sec...")
    # await interaction.response.defer()

    # Get song details from Spotify
    try:
        track_id: str = spotify_url.split("track/")[1].split("?")[0]
        track = sp.track(track_id)
        song_name = track['name']
        song_artists = track['artists'][0]['name']
        song_name_track: str = song_name + " " + song_artists
        
        # loop = asyncio.get_event_loop()
        # url = await loop.run_in_executor(None, lambda: fetch_music(song_name=song_name_track))

        # Add to the queue
        music_queue.put({song_name:spotify_url,"artists": song_artists, "provider":interaction.user})  # Enqueue the song
        # music_queue.put({song_name:url,"provider":interaction.user})  # Enqueue the song
        await interaction.followup.send(f"{interaction.user.mention} added [{song_name}]({spotify_url}) by {song_artists} to the queue!")
    except Exception as e:
        await interaction.followup.send("Error adding the song. Make sure the link is a valid Spotify track URL.")



def fetch_music(song_name: str) -> str | None:
    # Search on YouTube
    with yt_dlp.YoutubeDL({'format': 'bestaudio',
                           'username':'oauth',
                           'password':'',
                           'socket_timeout':15}) as ydl:
        info = ydl.extract_info(f"ytsearch:{song_name}", download=False)

        try:
            url: str = info['entries'][0]['url']
        except IndexError:
            return None
        return url




bot.run(token=DISCORD_TOKEN)
# bot.run(token=DISCORD_TOKEN, log_level=logging.DEBUG)


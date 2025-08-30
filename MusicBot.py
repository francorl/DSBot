# Importing libraries and modules
import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import yt_dlp # NEW
from collections import deque # NEW
import asyncio # NEW
from concurrent.futures import ThreadPoolExecutor


yt_executor = ThreadPoolExecutor(max_workers=4)

# Environment variables for tokens and other sensitive data
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Create the structure for queueing songs - Dictionary of queues
SONG_QUEUES = {}

async def search_ytdlp_async(query, ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(yt_executor, lambda: _extract(query, ydl_opts))

def _extract(query, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(query, download=False)


# Setup of intents. Intents are permissions the bot has on the server
intents = discord.Intents.default()
intents.message_content = True

# Bot setup
bot = commands.Bot(command_prefix="/", intents=intents)

# Add this global variable at the top (after bot is created)
main_loop = None

# Bot ready-up code
@bot.event
async def on_ready():
    global main_loop
    main_loop = asyncio.get_running_loop()  # Save the main event loop
    # Set custom status here
    activity = discord.Activity(type=discord.ActivityType.playing, name="Unreal Engine 5")
    await bot.change_presence(activity=activity)
    await bot.tree.sync()
    print(f"{bot.user} is online!")


@bot.tree.command(name="skip", description="Skips the current playing song")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client and (interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused()):
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("Skipped the current song.")
    else:
        await interaction.response.send_message("Not playing anything to skip.")


@bot.tree.command(name="pause", description="Pause the currently playing song.")
async def pause(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client

    # Check if the bot is in a voice channel
    if voice_client is None:
        return await interaction.response.send_message("I'm not in a voice channel.")

    # Check if something is actually playing
    if not voice_client.is_playing():
        return await interaction.response.send_message("Nothing is currently playing.")
    
    # Pause the track
    voice_client.pause()
    await interaction.response.send_message("Playback paused!")


@bot.tree.command(name="resume", description="Resume the currently paused song.")
async def resume(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client

    # Check if the bot is in a voice channel
    if voice_client is None:
        return await interaction.response.send_message("I'm not in a voice channel.")

    # Check if it's actually paused
    if not voice_client.is_paused():
        return await interaction.response.send_message("I’m not paused right now.")
    
    # Resume playback
    voice_client.resume()
    await interaction.response.send_message("Playback resumed!")

@bot.tree.command(name="queue", description="Shows the current song queue.")
async def queue(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    queue = SONG_QUEUES.get(guild_id, deque())
    
    if not queue:
        await interaction.response.send_message("The queue is empty.")
    else:
        queue_list = "\n".join([f"{i+1}. {title}" for i, (_, title) in enumerate(queue)])
        await interaction.response.send_message(f"Current Queue:\n{queue_list}")    


@bot.tree.command(name="stop", description="Stop playback and clear the queue.")
async def stop(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client

    # Check if the bot is in a voice channel
    if not voice_client or not voice_client.is_connected():
        return await interaction.response.send_message("I'm not connected to any voice channel.")

    # Clear the guild's queue
    guild_id_str = str(interaction.guild_id)
    if guild_id_str in SONG_QUEUES:
        SONG_QUEUES[guild_id_str].clear()

    # If something is playing or paused, stop it
    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()

    # (Optional) Disconnect from the channel
    await voice_client.disconnect()

    await interaction.response.send_message("Stopped playback and disconnected!")


@bot.tree.command(name="play", description="Play a song or playlist.")
@app_commands.describe(song_query="Search query or playlist URL")
async def play(interaction: discord.Interaction, song_query: str):
    await interaction.response.defer()

    voice_channel = interaction.user.voice.channel
    if voice_channel is None:
        await interaction.followup.send("You must be in a voice channel.")
        return

    voice_client = interaction.guild.voice_client
    if voice_client is None:
        voice_client = await voice_channel.connect()
    elif voice_channel != voice_client.channel:
        await voice_client.move_to(voice_channel)

    ydl_options = {
        "format": "bestaudio[abr<=96]/bestaudio",
        "noplaylist": False,
        "quiet": True,
        "extract_flat": False,
    }

    query = song_query if song_query.startswith("http") else f"ytsearch1:{song_query}"

    try:
        results = await search_ytdlp_async(query, ydl_options)
    except Exception as e:
        await interaction.followup.send(f"Error fetching results: {e}")
        return

    # Handle playlist or single track
    if "entries" in results:
        tracks = results["entries"]
    else:
        tracks = [results]

    guild_id = str(interaction.guild_id)
    if SONG_QUEUES.get(guild_id) is None:
        SONG_QUEUES[guild_id] = deque()

    # Only store the query/URL and title in the queue
    for track in tracks:
        track_query = track.get("webpage_url", track.get("url", song_query))
        title = track.get("title", "Untitled")
        SONG_QUEUES[guild_id].append((track_query, title))

    if len(tracks) == 1:
        message = f"Added to queue: **{tracks[0]['title']}**"
    else:
        message = f"Queued **{len(tracks)}** tracks from playlist."

    await interaction.followup.send(message)

    if not voice_client.is_playing() and not voice_client.is_paused():
        await play_next_song(voice_client, guild_id, interaction.channel)


async def play_next_song(voice_client, guild_id, channel):
    if SONG_QUEUES[guild_id]:
        track_query, title = SONG_QUEUES[guild_id].popleft()

        # Download audio_url only now
        ydl_options = {
            "format": "bestaudio[abr<=96]/bestaudio",
            "quiet": True,
            "extract_flat": False,
        }
        try:
            result = await search_ytdlp_async(track_query, ydl_options)
            audio_url = result["url"]
        except Exception as e:
            await channel.send(f"Error fetching audio for **{title}**: {e}")
            # Try next song
            if main_loop and not main_loop.is_closed():
                asyncio.run_coroutine_threadsafe(play_next_song(voice_client, guild_id, channel), main_loop)
            return

        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn -c:a libopus -b:a 96k",
        }

        source = discord.FFmpegOpusAudio(audio_url, **ffmpeg_options, executable="bin\\ffmpeg\\ffmpeg.exe")

        def after_play(error):
            if error:
                print(f"Error playing {title}: {error}")
            if main_loop and not main_loop.is_closed():
                asyncio.run_coroutine_threadsafe(play_next_song(voice_client, guild_id, channel), main_loop)

        voice_client.play(source, after=after_play)
        await channel.send(f"Now playing: **{title}**")
    else:
        await voice_client.disconnect()
        SONG_QUEUES[guild_id] = deque()


@bot.tree.command(name="ping", description="Show the bot's latency (ping).")
async def ping(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! Latency: {latency_ms} ms")


# Run the bot
bot.run(TOKEN)

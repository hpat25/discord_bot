#made by Lucia Ulate, Reva Mahesh, Honey Patel and Emily Messenger

import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import yt_dlp
import asyncio
from collections import deque 

# Load token and guild and queue
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1438688578560593980
SONG_QUEUES = {}

# ---------------------- YTDLP SEARCH --------------------------

async def search_ytdlp_async(query, ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, lambda: _extract(query, ydl_opts)
    )

def _extract(query, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(query, download=False)



# Intents
intents = discord.Intents.default()
intents.message_content = True

# Bot
bot = commands.Bot(command_prefix="!", intents=intents)

#---------------------- ON READY EVENT --------------------------------
# When the bot is ready
@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    synced = await bot.tree.sync(guild=guild)
    print(f"Synced {len(synced)} commands for guild {GUILD_ID}")
    print(f"{bot.user} is ready to serve!")


#---------------------- MESSAGE EVENT -------------------------------- (when someone sends a message, it does this)
@bot.event
async def on_message(msg):

    # Ignore bot messages
    if msg.author.bot:
        return

    # Ignore system messages (joins, boosts, pins, etc.)
    if msg.type != discord.MessageType.default:
        return

    # Ignore messages with only images/files
    if not msg.content or msg.content.strip() == "":
        return

    # Respond only to real user text
    await msg.channel.send(
        f'Like the great philosopher {msg.author.mention} once said: "{msg.content}"'
    )

    # Allow prefix commands (e.g. !play)
    await bot.process_commands(msg)

    # Allow slash commands (e.g. /greet)
    await bot.process_application_commands(msg)


#---------------------- Greet Command ---------------------------------------------
@bot.tree.command(name="greet", description="say HALLO!!! to someone") #/greet
async def greet(interaction: discord.Interaction):
    username = interaction.user.mention
    await interaction.response.send_message("HALLO!!! " + username)

#---------------------- Skip Command ---------------------------------------------
@bot.tree.command(name="skip", description="Skips the current playing song") #/skip
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client and (interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused()):
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("Skipped the current song.")
    else:
        await interaction.response.send_message("Not playing anything to skip.")

#---------------------- Pause Command ---------------------------------------------
@bot.tree.command(name="pause", description="Pause the currently playing song.") #/pause
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

#---------------------- Resume Command ---------------------------------------------
@bot.tree.command(name="resume", description="Resume the currently paused song.") 
async def resume(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client

# Check if the bot is in a voice channel
    if voice_client is None:
        return await interaction.response.send_message("I'm not in a voice channel.")
# Check if it's actually paused
    if not voice_client.is_paused():
        return await interaction.response.send_message("I’m not paused right now.")
    voice_client.resume()
    await interaction.response.send_message("Playback resumed!")

#-----------------------Stop command -----------------------------
@bot.tree.command(name="stop", description="Stop playback and clear the queue.") 
async def stop(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client

# Check if the bot is in a voice channel
    if not voice_client or not voice_client.is_connected():
        return await interaction.response.send_message("Not in any Voice Channel.")
    
# Clear the server's queue
    guild_id_str = str(interaction.guild_id)
    if guild_id_str in SONG_QUEUES:
        SONG_QUEUES[guild_id_str].clear()

# If something is playing or paused, stop it
    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()

#Disconnect from the channel
    await voice_client.disconnect()
    await interaction.response.send_message("Stopped playback and disconnected!")


#---------------------- Play Command ---------------------------------------------
@bot.tree.command(name="play", description="Play a song from YouTube") #/play
async def play(interaction: discord.Interaction, song_query: str):
    await interaction.response.defer()

    # User must be in voice channel
    if interaction.user.voice is None:
        await interaction.followup.send("You must be in a voice channel.")
        return
    voice_channel = interaction.user.voice.channel
    voice_client = interaction.guild.voice_client

    # Connect or move to proper channel
    if voice_client is None:
        voice_client = await voice_channel.connect()
    elif voice_client.channel != voice_channel:
        await voice_client.move_to(voice_channel)

    # YT-DLP options
    ydl_options = {
        "format": "bestaudio[abr<=96]/bestaudio",
        "noplaylist": True,
        "youtube_include_dash_manifest": False,
        "youtube_include_hls_manifest": False,
    }

    query = "ytsearch1:" + song_query
    results = await search_ytdlp_async(query, ydl_options)
    tracks = results.get("entries", [])

    if not tracks:
        await interaction.followup.send("No results found.")
        return
# Get first track info
    first_track = tracks[0]
    audio_url = first_track["url"]
    title = first_track.get("title", "untitled")
# Add to queue
    guild_id = str(interaction.guild_id)
# Initialize queue if not present
    if SONG_QUEUES.get(guild_id) is None:
        SONG_QUEUES[guild_id] = deque()

# Add song to the queue
    SONG_QUEUES[guild_id].append((audio_url, title))

# Notify user
    if voice_client.is_playing() or voice_client.is_paused():
        await interaction.followup.send(f"Added to queue: **{title}**")
    else:
        await interaction.followup.send(f"Now playing: **{title}**")
        await play_next_song(voice_client, guild_id, interaction.channel)

#---------------------- Play Next Song Helper Function -----------------------------
async def play_next_song(voice_client, guild_id, channel):
    if SONG_QUEUES[guild_id]:
        audio_url, title = SONG_QUEUES[guild_id].popleft()

        
        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn"
        }

        source = discord.FFmpegOpusAudio(
        audio_url,
        executable=r"C:\Users\lucia\OneDrive\Documents\Code\discord-bot\WIC_Discord_Bot\bin\ffmpeg\ffmpeg.exe",
        **ffmpeg_options
    )
        def after_play(error):
            if error:
                print(f"Error playing {title}: {error}")
            asyncio.run_coroutine_threadsafe(play_next_song(voice_client, guild_id, channel), bot.loop)

        voice_client.play(source, after=after_play)
        asyncio.create_task(channel.send(f"Now playing: **{title}**"))
    else:
        await voice_client.disconnect()
        SONG_QUEUES[guild_id] = deque()


# ---------------------- RUN BOT -------------------------------

bot.run(TOKEN)

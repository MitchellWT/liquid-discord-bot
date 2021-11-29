import discord
import yt_dlp
import random
import string
import asyncio
import os

from discord.ext import commands
from discord.ext.commands import command
from googleapiclient.discovery import build
from .downloader import Downloader

# Plays music from file, defines discord commands
class Player(commands.Cog, name='Player'):
    # Initializes player with discord bot
    def __init__(self, bot):
        self.bot = bot
        self.player = {
            "audio_files": []
        }

    # Returns a random color for a discord.Embed object
    def random_color(self):
        return discord.Color.from_rgb(random.randint(1, 255), random.randint(1, 255), random.randint(1, 255))

    # Clears bot queue after the bot leaves the voice channel
    @commands.Cog.listener('on_voice_state_update')
    async def queue_clear(self, user, before, after):
        if after.channel is None and user.id == self.bot.user.id:
            try:
                self.player[user.guild.id]['queue'].clear()
            except KeyError:
                # Data missing from player dictionary
                print(f"ERROR: Unable to get guild ID. (ID: {user.guild.id})")
    
    # Generates a unique file name
    async def filename_generator(self):
        characters = list(string.ascii_letters+string.digits)
        filename = ''

        for _ in range(random.randint(10, 25)):
            filename += random.choice(characters)

        if filename not in self.player['audio_files']:
            return filename

        return await self.filename_generator()

    # Used to add a full playlist to the queue
    async def playlist(self, data, msg):
        for song in data['queue']:
            self.player[msg.guild.id]['queue'].append({
                'title': song,
                'author': msg.author.name, 
                'command': msg.message.content.replace('-play', '').replace('liquid play', '').strip(),
                'message': msg
            })

    # Adds song to the queue
    async def queue(self, msg, song):
        downloader_info = await Downloader.get_info(self, url=song)
        info = downloader_info[0]
        queueObject = downloader_info[1]
        title = 'Bottom Text'

        if ('title' in info): 
            title = info['title']
        elif ('entries' in info):
            title = info['entries'][0]['title']

        # For adding playlist to queue
        if queueObject['queue']:
            await self.playlist(queueObject, msg)
            # Needs to be embeded to increase output quality
            return await msg.send(f"Added playlist {queueObject['title']} to queue!".title())
        
        self.player[msg.guild.id]['queue'].append({
            'title': title, 
            'author': msg.author.name,
            'command': msg.message.content.replace('-play', '').replace('liquid play', '').strip(),
            'message': msg
        })
        return await msg.send(f"{title} added to queue!".title())

    # Makes the bot leave voice channel If music is not being played
    async def leave_check(self, msg):
        if msg.voice_client is not None:
            await asyncio.sleep(180)

            if msg.voice_client is not None and msg.voice_client.is_playing() is False and msg.voice_client.is_paused() is False:
                await msg.voice_client.disconnect()

    # Removes all dictionary data, audio files, and audio file names
    async def clear_data(self, msg):
        name = self.player[msg.guild.id]['name']
        os.remove(name)
        self.player['audio_files'].remove(name)

    # Loops the currently playing song 
    async def loop_song(self, msg):
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(self.player[msg.guild.id]['name']))
        loop = asyncio.get_event_loop()

        try:
            msg.voice_client.play(source, after=lambda a: loop.create_task(self.done(msg)))
            msg.voice_client.source.volume = self.player[msg.guild.id]['volume']
        except Exception as E:
            print(E)

    # Clean up function for when a song finishes playing
    async def done(self, msg, msgId: int = None):
        # Removes message from channel
        if msgId:
            try:
                message = await msg.channel.fetch_message(msgId)
                await message.delete()
            except Exception as E:
                print(E)

        # When 'reset' command is called
        if self.player[msg.guild.id]['reset'] is True:
            self.player[msg.guild.id]['reset'] = False
            return await self.loop_song(msg)

        # When 'repeat' command is called
        if msg.guild.id in self.player and self.player[msg.guild.id]['repeat'] is True:
            return await self.loop_song(msg)

        await self.clear_data(msg)
        
        # Removes song from queue
        if self.player[msg.guild.id]['queue']:
            new_song = self.player[msg.guild.id]['queue'].pop(0)
            return await self.start_song(msg=new_song['message'], song=new_song['command'])
        else:
            await self.leave_check(msg)

    # Starts playing a new song
    async def start_song(self, msg, song):
        options = {
            'audioquality': 5,
            'format': 'bestaudio',
            'outtmpl': '{}',
            'restrictfilenames': True,
            'flatplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'logtostderr': False,
            "extractaudio": True,
            "audioformat": "opus",
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0'
        }.copy()
        audio_name = await self.filename_generator()

        self.player['audio_files'].append(audio_name)
        options['outtmpl'] = options['outtmpl'].format(audio_name)

        # Sets up downloader 
        youtube_downloader = yt_dlp.YoutubeDL(options)
        downloader = await Downloader.video_url(song, youtube_downloader=youtube_downloader, loop=self.bot.loop)
        if downloader is None:
            return await msg.send('It looks like this video is age restricted, I can\'t play it!\nOr it\'s a spotify link!')
        download = downloader[0]
        data = downloader[1]
        self.player[msg.guild.id]['name'] = audio_name
        # Sets up embed object, feedback on discord purposes
        embed = discord.Embed(
            colour=self.random_color(), 
            title='Now playing',
            description=download.title, 
            url=download.url
        )
        embed.set_thumbnail(url=download.thumbnail)
        embed.set_footer(
            text=f'Requested by {msg.author.display_name}', 
            icon_url=msg.author.avatar_url
        )
        loop = asyncio.get_event_loop()

        # For adding playlist to queue
        if data['queue']:
            await self.playlist(data, msg)
        
        # Sets class based variables and prepares for return
        msgId = await msg.send(embed=embed)
        self.player[msg.guild.id]['player'] = download
        self.player[msg.guild.id]['author'] = msg
        msg.voice_client.play(download, after=lambda a: loop.create_task(self.done(msg, msgId.id)))
        msg.voice_client.source.volume = self.player[msg.guild.id]['volume']
        
        return msg.voice_client

    # Play command, can play from youtube URL, youtube search terms, soundcloud URL, and bandcamp URL
    @command(name='play', help='Plays a song or adds a song to the queue')
    async def play(self, msg, *, song):
        if msg.guild.id in self.player:
            # For adding songs to the queue
            if msg.voice_client.is_playing() is True or self.player[msg.guild.id]['queue']:
                return await self.queue(msg, song)

            # For playing with no queued songs
            if msg.voice_client.is_playing() is False and not self.player[msg.guild.id]['queue']:
                return await self.start_song(msg, song)

        else:
            # Only place where self.player is created, other than in the constrcutor 
            self.player[msg.guild.id] = {
                'player': None,
                'queue': [],
                'author': msg.author.name,
                'msg': msg,
                'name': None,
                "reset": False,
                'repeat': False,
                'volume': 0.5
            }
            return await self.start_song(msg, song)

    # Performs some checks to see If play can execute correctly
    @play.before_invoke
    async def before_play(self, msg):
        # Check If user requesting song is in a voice channel
        if msg.author.voice is None:
            return await msg.send('Please join a voice channel to play music!'.title())

        # Check If bot is in voice channel
        if msg.voice_client is None:
            await msg.author.voice.channel.connect()

        # Check If bot and user are in the same voice channel
        if msg.voice_client.channel != msg.author.voice.channel:
            # Check If song is playing (no queue) and moves If not playing
            if msg.voice_client.is_playing() is False and not self.player[msg.guild.id]['queue']:
                return await msg.voice_client.move_to(msg.author.voice.channel)
            else:
                return await msg.send("Please join the same voice channel as the bot to add song to queue!")
        return await msg.send('One moment, I\'m sussing it out!')

    # Repeat command, loops the currently playing song, Toggleable
    @command(name='repeat', help='Loops the currently playing song')
    async def repeat(self, msg):
        if msg.guild.id in self.player:
            if msg.voice_client.is_playing() is True:
                if self.player[msg.guild.id]['repeat'] is True:
                    self.player[msg.guild.id]['repeat'] = False
                else:
                    self.player[msg.guild.id]['repeat'] = True

                return await msg.message.add_reaction(emoji='✅')

            return await msg.send("No audio currently playing!")
        return await msg.send("Bot not in voice channel or playing music!")

    # Reset command, resets the currently playing song to the beginning
    @command(name='reset', aliases=['restart-loop'], help='Resets the currently playing song to the beginning')
    async def reset(self, msg):
        # Check If song is playing
        if msg.voice_client is None:
            return await msg.send(f"{msg.author.display_name}, there is no audio currently playing from the bot!")
        # Check If the bot and user are in the same voice channel
        elif msg.author.voice is None or msg.author.voice.channel != msg.voice_client.channel:
            return await msg.send(f"{msg.author.display_name}, you must be in the same voice channel as the bot!")
        # Check If audio playing and If a song is in queue
        elif self.player[msg.guild.id]['queue'] and msg.voice_client.is_playing() is False:
            return await msg.send("No audio currently playing or songs in queue!".title(), delete_after=25)

        self.player[msg.guild.id]['reset'] = True
        msg.voice_client.stop()
        return await msg.message.add_reaction(emoji='✅')

    # Skip command, skips the currently playing song
    @command(name='skip', help='Skips the currently playing song')
    async def skip(self, msg):
        # Check If song is playing
        if msg.voice_client is None:
            return await msg.send("No music currently playing!".title(), delete_after=60)
        # Check If the bot and user are in the same voice channel
        elif msg.author.voice is None or msg.author.voice.channel != msg.voice_client.channel:
            return await msg.send("Please join the same voice channel as the bot!")
        # Check If a song is in queue
        elif not self.player[msg.guild.id]['queue'] and msg.voice_client.is_playing() is False:
            return await msg.send("No songs in queue to skip!".title(), delete_after=60)

        self.player[msg.guild.id]['repeat'] = False
        msg.voice_client.stop()
        return await msg.message.add_reaction(emoji='✅')

    # Stop command, stop the currently playing song
    @command(name='stop', help='Stops the currently playing song')
    async def stop(self, msg):
        # Check the bot is connected to a voice channel
        if msg.voice_client is None:
            return await msg.send("Bot is not connected to a voice channel!")
        # Check If the bot and user are in the same voice channel
        elif msg.author.voice is None:
            return await msg.send("You must be in the same voice channel as the bot!")
        elif msg.author.voice is not None and msg.voice_client is not None:
            if msg.voice_client.is_playing() is True or self.player[msg.guild.id]['queue']:
                self.player[msg.guild.id]['queue'].clear()
                self.player[msg.guild.id]['repeat'] = False
                msg.voice_client.stop()
                return await msg.message.add_reaction(emoji='✅')
            else:
                return await msg.send(f"{msg.author.display_name}, there is no audio currently playing or songs in queue!")

    # Leave command, forces the bot to leave the voice channel
    @command(name='leave', aliases=['get-out', 'disconnect', 'leave-voice'], help='Liquid will leave the voice channel')
    async def leave(self, msg):
        if msg.author.voice is not None and msg.voice_client is not None:
            if msg.voice_client.is_playing() is True or self.player[msg.guild.id]['queue']:
                self.player[msg.guild.id]['queue'].clear()
                msg.voice_client.stop()
                return await msg.voice_client.disconnect(), await msg.message.add_reaction(emoji='✅')
            else:
                return await msg.voice_client.disconnect(), await msg.message.add_reaction(emoji='✅')
        else:
            return await msg.send("You must be in the same voice channel as bot to disconnect it via this command!")

    # Pause command, pauses the currently playing song
    @command(name='pause', case_insensitive=True, help='Pause the currently playing song')
    async def pause(self, msg):
        if msg.author.voice is not None and msg.voice_client is not None:
            # Check If song is currently paused
            if msg.voice_client.is_paused() is True:
                return await msg.send("Song is already paused!")
            elif msg.voice_client.is_paused() is False:
                msg.voice_client.pause()
                await msg.message.add_reaction(emoji='✅')

    # Resume command, resumes a paused song from the queue
    @command(name='resume', help='Resumes the currently paused song, If it\'s paused')
    async def resume(self, msg):
        if msg.author.voice is not None and msg.voice_client is not None:
            # Check If song is currently playing
            if msg.voice_client.is_paused() is False:
                return await msg.send("Song is already playing!")
            elif msg.voice_client.is_paused() is True:
                msg.voice_client.resume()
                return await msg.message.add_reaction(emoji='✅')

    # Queue command, shows the current song queue
    @command(name='queue', aliases=['song-list', 'q', 'current-songs'], help='Shows the current song queue')
    async def _queue(self, msg):
        # Check If song is in queue
        if msg.voice_client is not None and msg.guild.id in self.player and self.player[msg.guild.id]['queue']:
            # Sets up embed object, feedback on discord purposes
            embed = discord.Embed(colour=self.random_color(), title='queue')
            embed.set_footer(
                text=f'Command used by {msg.author.name}', 
                icon_url=msg.author.avatar_url
            )
            # Adds songs to embed object
            for song in self.player[msg.guild.id]['queue']:
                embed.add_field(
                    name=f"{song['author']}", 
                    value=song['title'], 
                    inline=False
                )
            return await msg.send(embed=embed, delete_after=120)
        
        return await msg.send("No songs in queue!")

    # Song-info command, shows information on the currently playing song
    @command(name='song-info', aliases=['song?', 'nowplaying', 'current-song'], help='Shows information on currently playing song')
    async def song_info(self, msg):
        # Check If song is playing
        if msg.voice_client is not None and msg.voice_client.is_playing() is True:
            # Sets up embed object, feedback on discord purposes
            embed = discord.Embed(
                colour=self.random_color(), 
                title='Currently Playing',
                description=self.player[msg.guild.id]['player'].title
            )
            embed.set_footer(
                text=f"{self.player[msg.guild.id]['author'].author.name}", 
                icon_url=msg.author.avatar_url
            )
            embed.set_thumbnail(url=self.player[msg.guild.id]['player'].thumbnail)
            return await msg.send(embed=embed, delete_after=120)

        return await msg.send(f"No songs currently playing!".title(), delete_after=30)

    # Join command, forces the bot to join to a channel
    @command(name='join', aliases=['move-bot', 'move-b', 'mb', 'mbot'], help='Liquid will join the voice channel your in')
    async def join(self, msg, *, channel: discord.VoiceChannel = None):
        # Check If bot is in another channel
        if msg.voice_client is not None:
            None
            # return await msg.send(f"Bot is already in a voice channel\nDid you mean to use {msg.prefix}moveTo?")
        elif msg.voice_client is None:
            # Check If channel variables was passed
            if channel is None:
                return await msg.author.voice.channel.connect(), await msg.message.add_reaction(emoji='✅')
            else:
                return await channel.connect(), await msg.message.add_reaction(emoji='✅')
        elif msg.voice_client.is_playing() is False and not self.player[msg.guild.id]['queue']:
            return await msg.author.voice.channel.connect(), await msg.message.add_reaction(emoji='✅')

    # Performs check before join command is executed
    @join.before_invoke
    async def before_join(self, msg):
        if msg.author.voice is None:
            return await msg.send("You are not in a voice channel!")

    # Executed when an error occures from the join command
    @join.error
    async def join_error(self, msg, error):
        if isinstance(error, commands.BadArgument):
            return msg.send(error)
        elif error.args[0] == 'Command raised an exception: Exception: playing':
            return await msg.send("Please join the same voice channel as the bot to add song to queue!".title())

    # Volume command, changes the volume output from the bot
    @command(name='volume', aliases=['vol'], help='Change output volume of liquid')
    async def volume(self, msg, vol: int):
        if vol > 200:
            vol = 200

        vol = vol / 100
        
        if msg.author.voice is not None and msg.voice_client is not None \
        and msg.voice_client.channel == msg.author.voice.channel and msg.voice_client.is_playing() is True:
            msg.voice_client.source.volume = vol
            self.player[msg.guild.id]['volume'] = vol
            return await msg.message.add_reaction(emoji='✅')
        else:
            return await msg.send("Please join the same voice channel as the bot to use the command!".title(), delete_after=30)

    # Executed when an error occures from the volume command
    @volume.error
    async def volume_error(self, msg,error):
        if isinstance(error, commands.MissingPermissions):
            return await msg.send("Manage channels or admin perms required to change volume!", delete_after=30)

# Adds player to bot
def setup(bot):
    bot.add_cog(Player(bot))

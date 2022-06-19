import discord
import os
from pytube import YouTube

from discord.ext import commands, tasks
import discord.utils

client = commands.Bot(command_prefix="!")

# GLOBALS:
global current_delete_loop_time, current_play_loop_time, help_language
current_delete_loop_time = 10
current_play_loop_time = 1
help_language = "PL"


class Song:
    def __init__(self, url, voice_channel):
        self.title = None
        self.song_path = None
        self.length = None
        self.song_link = url
        self.channel = voice_channel
        self.download_song()

    def download_song(self):
        """Self-command: download song from a given yt link"""
        yt = YouTube(self.song_link)
        self.length = int(yt.length)
        self.title = yt.title
        video = yt.streams.filter(only_audio=True).first()

        # check for destination to save file
        destination = './Songs'

        # download the file
        try:
            out_file = video.download(output_path=destination)

            # save the file
            base, ext = os.path.splitext(out_file)
            new_file = base + '.mp3'
            os.rename(out_file, new_file)
        except FileExistsError:
            # if song is currently downloaded - skip this part
            pass

        # save song path
        self.song_path = new_file

        # delete all songs which are not .mp3 format
        for file in os.listdir("./Songs"):
            if file.endswith(".mp4"):
                song_directory = "./Songs/" + file
                os.remove(song_directory)

    def play_me(self):
        """Self-command: play song on voice channel"""
        self.channel.play(discord.FFmpegPCMAudio(source=self.song_path, executable="ffmpeg"))


class SongsManager(Song):
    def __init__(self):
        self.songs = []
        self.current_song = None
        self.next_song = None
        self.songs_played = []

        self.songs_shuffler()

    def new_song(self, song):
        """Add a new song to queue"""
        self.songs.append(song)
        number = 1
        for s in self.songs:
            print(f"Poz number {number}: " + s.title)
            number += 1
        self.songs_shuffler()

    def songs_shuffler(self):
        """Method used to shuffle songs form a list - bring songs under its position in list songs to play"""
        try:
            self.current_song = self.songs[0]
        except IndexError:
            pass
        try:
            self.next_song = self.songs[1]
        except IndexError:
            pass

    def song_remover(self, song):
        """Remove given song (used to deleting already played songs)"""
        os.remove(song.song_path)
        self.songs_played.remove(song)

    @staticmethod
    def songs_cleaner():
        """Delete all songs after bot's disconnect form voice channel"""
        for file in os.listdir("./Songs"):
            if file.endswith(".mp3"):
                try:
                    os.remove(file)
                except FileNotFoundError:
                    pass


class MusicBot(commands.Cog, SongsManager):
    """Main bot class"""

    def __init__(self, bot):
        self.bot = bot
        self.music_manager = SongsManager()
        self.bot_id = self.bot.owner_id
        self.bot_voice = None
        self.play_songs.start()
        self.song_cleaner.start()

    @commands.Cog.listener()
    async def on_ready(self):
        print('We have logged in as {0.user}'.format(client))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.content.startswith('!p'):
            await self.play_music(message)
        elif message.content.startswith('!info'):
            """Currently not working, work in progress..."""
            # message_channel = ""
            # await message_channel.send(('Muzyczny bot vol. 1. Komendy: \n'
            #                             '!p <link> - odtwarza podaną piosenkę (dostępny jest jedynie YT) \n'
            #                             '!skip - przeskakuje do kolejnej piosenki \n'
            #                             '!stop - wyłącza odtwarzanie muzyki \n'
            #                             '!resume - wznawia odtwarzanie muzyki'
            #                             '!reset - wyłącza odtwarzanie muzyki i czyści listę piosenek \n'
            #                             '!disconnect - bot opuszcza kanał'))
            pass
        elif message.content.startswith('!next'):
            self.bot.voice_clients[0].stop()
            self.music_manager.songs_shuffler()
            await self.play_music(message)
        elif message.content.startswith('!stop'):
            self.bot.voice_clients[0].pause()
        elif message.content.startswith('!resume'):
            self.bot.voice_clients[0].resume()
        elif message.content.startswith('!disconnect'):
            await self.bot_voice.disconnect()
            self.music_manager.songs_cleaner()

    @tasks.loop(seconds=current_play_loop_time)
    async def play_songs(self):  # tu jest dobrze, złe przypisanie głosu bota
        self.music_manager.songs_shuffler()
        if self.bot_voice is not None:  # check if bot has a user voice channel (= user is on voice channel)
            if len(self.music_manager.songs) != 0:  # check for songs ready to play
                if not self.bot_voice.is_playing():  # check if bot is already playing a music
                    self.music_manager.songs_shuffler()
                    song = self.music_manager.current_song
                    song.play_me()
                    self.music_manager.songs.remove(song)
                    self.music_manager.songs_played.append(song)

    @tasks.loop(minutes=current_delete_loop_time)
    async def song_cleaner(self):
        if not len(self.music_manager.songs_played) == 0:  # check for songs ready to delete
            for song in self.music_manager.songs_played:
                self.music_manager.song_remover(song)

    async def play_music(self, message):
        """Play music from user's url"""

        # Find user voice channel
        def find_user():
            user_id = message.author.id
            user_guild = message.author.guild
            user_guild_channels = user_guild.voice_channels
            current_user_channel = None
            for channel in user_guild_channels:
                all_channel_members = list(channel.voice_states.keys())
                if user_id in all_channel_members:
                    current_user_channel = channel
                    break
            return current_user_channel

        # Find bot voice channel
        def find_bot():
            bot_guild_channels = self.bot.voice_clients
            bot_channel = bot_guild_channels[0]
            bot_channel_name = bot_channel.channel
            return bot_channel_name

        # Connect bot to user channel:
        voice_channel = find_user()
        try:
            await voice_channel.connect()
        except discord.ClientException:
            # Check, if user is still on bot voice channel
            # If not, reconnect to user channel
            user_ch = find_user()
            bot_ch = find_bot()
            if user_ch != bot_ch:
                bot_guild_channel = self.bot.voice_clients[0]
                await bot_guild_channel.disconnect()
                voice_channel = find_user()
                await voice_channel.connect()

        # Add song to queue
        url = message.content.split(" ")[1]
        self.bot_voice = self.bot.voice_clients[0]  # save as variable current bots voice connection
        song = Song(url, self.bot_voice)
        self.music_manager.songs.append(song)
        self.music_manager.songs_shuffler()


client.add_cog(MusicBot(client))

client.run(token)

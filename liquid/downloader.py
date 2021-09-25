import discord
import asyncio
import youtube_dl

# Downloads music from youtube using youtube_dl
class Downloader(discord.PCMVolumeTransformer):
    # Initializes downloader with source and data
    def __init__(self, source, data):
        super().__init__(source, 1)

        self.data = data
        self.title = data.get('title')
        self.url = data.get("url")
        self.thumbnail = data.get('thumbnail')
        self.duration = data.get('duration')
        self.views = data.get('view_count')
        self.playlist = {}

    # Downloads the song file and it's data
    @classmethod
    async def video_url(cls, url, youtube_downloader, *, loop = None, stream = False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: youtube_downloader.extract_info(url, download = not stream))
        song_list = {'queue': []}
        
        if 'entries' in data:
            if len(data['entries']) > 1:
                playlist_titles = [title['title'] for title in data['entries']]
                song_list = {
                    'queue': playlist_titles
                }
                song_list['queue'].pop(0)

            data = data['entries'][0]

        filename = data['url'] if stream else youtube_downloader.prepare_filename(data)
        
        return cls(discord.FFmpegPCMAudio(filename, **{
            'options': '-vn'
        }), data=data), song_list

    # Gets info of the next song but not downloading the actual file
    async def get_info(self, url):
        youtube = youtube_dl.YoutubeDL({
            'default_search': 'auto',
            "ignoreerrors": True,
            'quiet': True,
            "no_warnings": True,
            "simulate": True,
            "nooverwrites": True,
            "keepvideo": False,
            "noplaylist": True,
            "skip_download": False,
            'source_address': '0.0.0.0'
        })
        info = youtube.extract_info(url, download=False)
        queueObject = {'queue': []}

        if 'entries' in queueObject:
            if len(queueObject['entries']) > 1:
                playlist_titles = [title['title'] for title in queueObject['entries']]
                queueObject = {
                    'title': queueObject['title'], 
                    'queue': playlist_titles
                }

            info = info['entries'][0]['title']

        return info, queueObject

import discord
from discord.ext import commands, tasks
from discord.ext.commands import Bot
from discord.utils import get
import json
import logUtils as log
from config import conf
import asyncio
import random
from time import time, localtime, strftime
import datetime
from yt_dlp import YoutubeDL
import traceback
import re
import random
import lyricsgenius
import requests as rqso
import os
import threading

st = int(time())
conf = conf("config.json")
token = conf["DISCORD_BOT_TOKEN"]
prefix = conf["PREFIX"]
GENIUSAccessToken = conf["GENIUS_ACCESS_TOKEN"]
isDLSong = conf["AUDIO_DOWNLOAD"]
AAR = conf["AUDIO_AUTO_REMOVE"]
MPS = conf["MAX_PLAYLIST_SIZE"]
stay_time = conf["STAY_TIME"]
vol = conf["DEFAULT_VOLUME"]
BotOwnerID = conf["BotOwnerID"]
SendErrorLog= conf["SEND_ERROR_LOG"]
ReplyMention= conf["REPLY_MENTION"]

if not os.path.isdir("audio"): os.mkdir("audio") #os.system("rd /s /q audio"); os.mkdir("audio")
intents = discord.Intents.default()
intents.typing = intents.presences = False
intents.messages = intents.message_content = intents.guild_messages = intents.members = intents.guilds = intents.guild_messages = intents.voice_states = True
bot = discord.Client(intents=intents)
BotOwner = None

async def fetchOwner(): global BotOwner; BotOwner = await bot.fetch_user(BotOwnerID)
async def requests(url): return rqso.get(url, headers={"Range": "bytes=0-"}, timeout=5, verify=False)
def exceptionE(msg=""): e = traceback.format_exc(); log.error(f"{msg} \n{e}"); return e
def windowsPath(path):
    for a in ['<','>',':','"','/','\\','|','?','*']: path = path.replace(a, "_")
    return path

async def sendErrorLog(msg: discord.message.Message, dmsg: str = None) -> None:
    if SendErrorLog:
        await BotOwner.send(f"```py\n{msg}``````py\n{traceback.format_exc()}```\n{msg.content}\ndebugMsg = {dmsg}")
    else: log.warning(f"에러로그 전송 {SendErrorLog} 상태임")
    
async def msgReply(msg: discord.message.Message, obj: str = None, **kwargs) -> None:
    try: return await msg.reply(obj, **kwargs, mention_author=ReplyMention)
    except discord.errors.HTTPException: pass
    except: await sendErrorLog(msg, dmsg="msg.reply 예외처리"); return await msg.channel.send(obj, **kwargs)

def culc_length(l):
    h = "{0:02d}".format(int(l // 60 // 60))
    m = "{0:02d}".format(int(l // 60))
    s = "{0:02d}".format(int(l % 60))
    return f"{h}:{m}:{s}"

SVOL = {}; queues = {}; SLOOP = {}; NP = {} #queues
def check_queue(omsg, loopd=None):
    if SLOOP.get(omsg.guild.id) and loopd: queues[omsg.guild.id].insert(0, loopd)
    if omsg.guild.id in queues and len(queues[omsg.guild.id]) > 0: asyncio.run_coroutine_threadsafe(play_song(queues[omsg.guild.id][0][0]), bot.loop)
    else:
        async def handle_song_selection(omsg):
            def ucs(m): return m.content.startswith(f"{prefix}play ") or m.content.startswith(f"{prefix}p ") or m.content.startswith(f"{prefix}search ")
            try: await bot.wait_for("message", timeout=stay_time, check=ucs)
            except asyncio.TimeoutError:
                voice_client = discord.utils.get(bot.voice_clients, guild=omsg.guild)
                if voice_client and not voice_client.is_playing() and voice_client.is_connected():
                    asyncio.run_coroutine_threadsafe(omsg.channel.send(f"{stay_time}초 동안 곡 재생 명령이 없으므로 음성 채널을 떠남."), bot.loop)
                    asyncio.run_coroutine_threadsafe(voice_client.disconnect(), bot.loop)
        asyncio.run_coroutine_threadsafe(handle_song_selection(omsg), bot.loop)
async def play_song(msg):
    if not os.path.isdir("data"): os.mkdir("data")
    voice_client = discord.utils.get(bot.voice_clients, guild=msg.guild)
    if not voice_client: #봇이 음성 채널에 연결되지 않았다면 연결
        if msg.author.voice: voice_client = await msg.author.voice.channel.connect()
        else: queues[msg.guild.id].pop(0); return await msgReply(msg, "음성 채널에 먼저 접속해주세요!")
    elif voice_client and not msg.author.voice: voice_client = queues[msg.guild.id].pop(0); return await msgReply(msg, "음성 채널에 먼저 접속해주세요!")
    if not SVOL.get(msg.guild.id): SVOL[msg.guild.id] = vol
    if not voice_client.is_playing():
        d = queues[msg.guild.id].pop(0); NP[msg.guild.id] = d + [0]
        ydl_opts = {
            "nocheckcertificate": True,
            'format': d[1]["auInfo"],
            'outtmpl': f'data/{d[1]["YTID"]}',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': False,
            'cookiesfrombrowser': ('firefox',)
        }
        surl = f"data/{d[1]['YTID']}.mp3"; before_options = ""
        if os.path.isfile(surl): log.info(f"{surl} 파일 존재함!")
        elif os.path.isfile(surl.replace(".mp3", ".ts")): surl = surl.replace(".mp3", ".ts"); log.info(f"{surl} 파일 존재함!")
        else:
            with YoutubeDL({'format': d[1]["auInfo"], 'quiet': True, 'cookiesfrombrowser': ('firefox',)}) as ydl: info = ydl.extract_info(d[1]["YTID"], download=False)
            surl = info["url"]; before_options="-protocol_whitelist file,http,https,tcp,tls,crypto -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 1"
            def dlsong():
                try:
                    with YoutubeDL(ydl_opts) as ydl: ydl.download(d[1]["YTID"])
                except:
                    asyncio.run_coroutine_threadsafe(sendErrorLog(msg, dmsg="ydl 에서 다운로드 실패함"), bot.loop)
                    log.info(surl)
                    log.error(f"`{d[1]['YTID']}` 곡은 .m3u8 --> .ts 로 변환하여 로컬에 저장 예정!")
                    st = time(); ts = b""; m3u8 = rqso.get(surl, headers={"Range": "bytes=0-"}, timeout=5, verify=False) #403 에러로 인하여 .ts 링크가 저장되어 있는 m3u8링크
                    for u in m3u8.text.split("\n"):
                        if u.startswith("http"): u = rqso.get(u, headers={"Range": "bytes=0-"}, timeout=5, verify=False); ts += u.content
                    if ts:
                        with open(f"data/{d[1]['YTID']}.ts", 'wb') as f: f.write(ts); log.debug(f"{d[1]['YTID']} 수동 다운로드 완료! | {round(time() - st, 2)} Sec")
                    else: asyncio.run_coroutine_threadsafe(sendErrorLog(msg, dmsg=".ts 수동 다운로드도 실패함"), bot.loop)
            if isDLSong: threading.Thread(target=dlsong).start()
        voice_client.play(
            discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(surl, executable="ffmpeg/bin/ffmpeg.exe", before_options=before_options), volume=SVOL[msg.guild.id] / 100),
            after=lambda e: check_queue(msg, d) if not e else msgReply(msg, f"ERROR!\n\n{e}")
        )
        NP[msg.guild.id][2] = time()
        if not SLOOP.get(msg.guild.id): return await msgReply(msg, f"재생 중: [{d[1]['title']}]({d[1]['YTURL']}) ({culc_length(d[1]['duration'])})")
async def search_song(msg, search_query, isplayCommand=False):
    YTURLPT = r"(https?://)?(www\.)?(m\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)(?P<video_id>[\w-]{11})(?:&list=(?P<list_id>[\w-]+))?"
    match = re.match(YTURLPT, search_query)
    if match: video_id = match.group("video_id"); list_id = match.group("list_id")
    else: video_id = list_id = search_query[-11:]
    ydl_opts = {
        "nocheckcertificate": True,
        "noplaylist": True,
        "quiet": True,
        "extract_flat": True,
        'cookiesfrombrowser': ('firefox',)
    }
    if not isplayCommand:
        with YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(f"ytsearch10:{search_query}", download=False)
            if "entries" not in search_results or len(search_results["entries"]) == 0: return await msgReply(msg, f"{search_query} <-- 검색 결과가 없습니다!")
            else:
                sr = []
                for info in search_results["entries"]:
                    temple = {
                        "YTID": info.get("id"),
                        "YTURL": info.get("url"),
                        "duration": info.get('duration'),
                        "title": f"{info.get('channel')} - {info.get('title')}",
                        "thumb": f'https://i.ytimg.com/vi/{info.get("id")}/maxresdefault.jpg'
                    }
                    sr.append(temple)
                return sr
    else:
        with YoutubeDL({'quiet': True, 'cookiesfrombrowser': ('firefox',)}) as ydl: info = ydl.extract_info(video_id, download=False)
        auInfo = 0; viInfo = {}
        for i in info.get('formats', []):
            if   i["acodec"] != "none" and i["vcodec"] == "none": auInfo = i['format_id']
            elif i["acodec"] == "none" and i["vcodec"] != "none": viInfo[str(i["height"])] = i["format_id"]
        return {
            "YTID": video_id,
            "YTURL": f"https://youtu.be/{video_id}",
            "viInfo": dict(reversed(viInfo.items())),
            "auInfo": auInfo,
            "duration": info.get('duration'),
            "title": f"{info.get('channel')} - {info.get('title')}",
            "thumb": info.get('thumbnail')
        }
async def get_playlist_items(msg, list_id):
    ydl_opts = {
        "nocheckcertificate": True,
        "force_generic_extractor": True,
        "dump_single_json": True,
        "quiet": True,
        "extract_flat": True,
        'cookiesfrombrowser': ('firefox',)
    }
    try:
        with YoutubeDL(ydl_opts) as ydl: result = ydl.extract_info(f"https://www.youtube.com/playlist?list={list_id}", download=False)
        return [{"idx": i, "YTID": e["id"], "YTURL": f"https://youtu.be/{e['id']}", "title": f"{e.get('channel')} - {e.get('title')}", "url": f"https://www.youtube.com/watch?v={e['id']}"} for i, e in enumerate(result.get("entries", [])) if "id" in e]
    except Exception as e:
        await msgReply(msg, f"재생목록 불러오기 중 오류 발생: {e}")
        return None


# 주기적으로 0시를 체크하는 태스크
@tasks.loop(seconds=1)
async def check_midnight():
    now = datetime.datetime.now()
    if AAR and now.hour == 0 and now.minute == 0 and now.second == 0:
        # 0시에 실행할 작업을 여기에 추가
        for i in os.listdir("audio"):
            try: os.remove(f"data/{i}"); log.info(f"data/{i} 파일 삭제 완료!")
            except PermissionError: pass
            except: exceptionE()
    elif now.hour == 0 and now.minute == 0 and now.second == 0:
        for i in [i for i in os.listdir("audio") if i.endswith(".ts")]:
            try: os.remove(f"data/{i}"); log.info(f".ts | data/{i} 파일 삭제 완료!")
            except PermissionError: pass
            except: exceptionE()

# 봇이 준비되었을 때 실행되는 이벤트 핸들러
@bot.event
async def on_ready():
    log.info(f"{bot.user} 온라인!")
    await bot.change_presence(status=discord.Status.online, activity=discord.Activity(
        type=discord.ActivityType.listening, 
        name='"음악 전용" 봇 모드로 실행중!!'
    ))
    await fetchOwner()
    check_midnight.start()
    #for guild in bot.guilds: #봇이 로그인하고 난 후, 모든 채널을 순회하며 메시지를 가져옵니다.
    #    for channel in guild.text_channels: channel.history(limit=100)

@bot.event
async def on_message_delete(dmsg):
    chatLog = f"Server:{dmsg.guild} | Channel:{dmsg.channel} | User (Sent): {dmsg.author} | Deleted Message:{dmsg.content}"
    log.error(chatLog)
    with open("chatlog.txt", "a", encoding="UTF-8") as file: file.write(f'[{strftime("%Y-%m-%d %H:%M:%S", localtime())}] - {chatLog}\n\n')

@bot.event
async def on_message_edit(before, after): #수정 메시지 감지
    if before.content == after.content: return
    chatLog = f"Server:{after.guild} | Channel:{after.channel} | User: {after.author} | Message edited: Before = {before.content}, After = {after.content},"
    log.warning(chatLog)
    with open("chatlog.txt", "a", encoding="UTF-8") as file: file.write(f'[{strftime("%Y-%m-%d %H:%M:%S", localtime())}] - {chatLog}\n\n')
    if after.author == bot.user: return
    await on_message(after, isEdited=True)

@bot.event
async def on_message(msg, isEdited=False):
    if isinstance(msg.channel, discord.DMChannel) and msg.author == bot.user and msg.content.startswith("```py"): return #에러로그전송 로깅 제외
    if not isEdited:
        chatLog = f"Server:{msg.guild} | Channel:{msg.channel} | User: {msg.author} | Message:{msg.content}"
        log.chat(chatLog)
        with open("chatlog.txt", "a", encoding="UTF-8") as file: file.write(f'[{strftime("%Y-%m-%d %H:%M:%S", localtime())}] - {chatLog}\n\n')
    if msg.author == bot.user: return

    if msg.content.startswith(f"{prefix}play ") or msg.content.startswith(f"{prefix}p "):
        if len(msg.content.split()) > 1: url = msg.content.split()[1]
        else: return await msgReply(msg, f"재생할 YouTube 링크를 입력해주세요! 예: `{prefix}play [YouTube URL]`")
        YTURLPT = r"(https?://)?(www\.)?(m\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)(?P<video_id>[\w-]{11})"
        if not re.match(YTURLPT, url): return await msgReply(msg, f"유효한 YouTube 링크를 입력해주세요! 예: `{prefix}play [YouTube URL]`")
        if msg.guild.id not in queues: queues[msg.guild.id] = []
        else: await msgReply(msg, f"{len(queues[msg.guild.id]) + 1}번 | 대기열 추가 완료!")
        si = await search_song(msg, url, isplayCommand = True)
        queues[msg.guild.id].append([msg, si]) #queues
        return await play_song(msg)

    if msg.content.startswith(f"{prefix}playlist ") or msg.content.startswith(f"{prefix}pl "):
        if len(msg.content.split()) > 1: url = msg.content.split()[1]
        else: return await msgReply(msg, f"재생할 YouTube 링크를 입력해주세요! 예: `{prefix}playlist [YouTube URL]`")
        YTURLPT = r"(https?://)?(www\.)?(m\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)(?P<video_id>[\w-]{11})(?:&list=(?P<list_id>[\w-]+))?"
        match = re.match(YTURLPT, url)
        if not match:
            YTURLPT = r"(?:https?://)?(?:www\.)?(m\.)?youtube\.com/playlist\?list=(?P<list_id>[\w-]+)"
            match = re.match(YTURLPT, url)
            if not match: return await msgReply(msg, f"유효한 YouTube 링크를 입력해주세요! 예: `{prefix}playlist [YouTube URL]`")
            video_id = None; list_id = match.group("list_id")
        else: video_id = match.group("video_id"); list_id = match.group("list_id")

        playlist = await get_playlist_items(msg, list_id)
        start_index = next((i for i, l in enumerate(playlist) if l['YTID'] == video_id), 0)
        playlist = playlist[start_index:] + playlist[:start_index]
        if msg.guild.id not in queues: queues[msg.guild.id] = []
        plmsg = None
        for i, d in enumerate(playlist):
            si = await search_song(msg, d["url"], isplayCommand = True)
            queues[msg.guild.id].append([msg, si]) #queues
            if i == 0:
                plmsg = await msgReply(msg, f"{i + 1}/{d['idx'] + 1}/{len(playlist)}번 | {d['title']} | 대기열 추가 완료!")
                await play_song(msg)
            await plmsg.edit(content=f"{i + 1}/{d['idx'] + 1}/{len(playlist)}번 | {d['title']} | 대기열 추가 완료!")
        return

    if msg.content == f"{prefix}pause":
        voice_client = discord.utils.get(bot.voice_clients, guild=msg.guild)
        if voice_client and voice_client.is_playing(): return voice_client.pause()
        else: return await msgReply(msg, "재생 중인 음악이 없습니다!")

    if msg.content == f"{prefix}resume" or msg.content == f"{prefix}r":
        voice_client = discord.utils.get(bot.voice_clients, guild=msg.guild)
        if voice_client and voice_client.is_paused(): return voice_client.resume()
        else: return await msgReply(msg, "일시정지된 음악이 없습니다!")

    if msg.content == f"{prefix}stop":
        voice_client = discord.utils.get(bot.voice_clients, guild=msg.guild)
        if voice_client and voice_client.is_connected(): queues[msg.guild.id] = []; return await voice_client.disconnect()
        else: return await msgReply(msg, "봇이 음성 채널에 연결되어 있지 않습니다.")

    if msg.content == f"{prefix}skip" or msg.content == f"{prefix}s":
        voice_client = discord.utils.get(bot.voice_clients, guild=msg.guild)
        if voice_client: return voice_client.stop()
        else: return await msgReply(msg, "재생 중인 음악이 없습니다.")
    if msg.content.startswith(f"{prefix}skip ") or msg.content.startswith(f"{prefix}s "):
        try:
            num = int(msg.content.split()[1])
            if not queues.get(msg.guild.id): return await msgReply(msg, "재생 중인 음악이 없습니다.")
            elif len(queues[msg.guild.id]) < num or num <= 0: return await msgReply(msg, f"대기열에 {num}번은 존재하지 않습니다. (1~{len(queues[msg.guild.id])})")
            d = queues[msg.guild.id].pop(num - 1)
            await msgReply(msg, f"Removed | {num}. {d[1]['title']} ({culc_length(d[1]['duration'])}) [Youtube]({d[1]['YTURL']})")
            msg.content = f"{prefix}q"; return await on_message(msg, isEdited=True)
        except ValueError: return await msgReply(msg, f"숫자를 입력해주세요! 예: `{prefix}skip 2`")
        except: return await msgReply(msg, f"에러 발생!\n{exceptionE()}")
    if msg.content.startswith(f"{prefix}skipto ") or msg.content.startswith(f"{prefix}st "):
        try:
            num = int(msg.content.split()[1])
            if not queues.get(msg.guild.id): return await msgReply(msg, "재생 중인 음악이 없습니다.")
            elif len(queues[msg.guild.id]) < num or num <= 0: return await msgReply(msg, f"대기열에 {num}번 까지 존재하지 않습니다. (1~{len(queues[msg.guild.id])})")
            embed = discord.Embed(
                title="삭제된 대기열",
                color=0xFF0000
            )
            embed.set_author(name=bot.user, icon_url=bot.user.avatar.url)
            embed.set_thumbnail(url=queues[msg.guild.id][num-1][1]["thumb"])
            for i in range(num):
                d = queues[msg.guild.id].pop(0); embed.add_field(name=f"Removed | {i+1}. {d[1]['title']} ({culc_length(d[1]['duration'])})", value=f"[Youtube]({d[1]['YTURL']})", inline=False)
            embed.timestamp = msg.created_at
            embed.set_footer(text=f"Made By {BotOwner.name}", icon_url=BotOwner.avatar.url)
            await msgReply(msg, embed=embed)
            msg.content = f"{prefix}q"; return await on_message(msg, isEdited=True)
        except ValueError: return await msgReply(msg, f"숫자를 입력해주세요! 예: `{prefix}skipto 2`")
        except: return await msgReply(msg, f"에러 발생!\n{exceptionE()}")

    if msg.content == f"{prefix}np":
        voice_client = discord.utils.get(bot.voice_clients, guild=msg.guild)
        if not voice_client or not voice_client.is_playing(): return await msgReply(msg, "현재 재생 중인 음악이 없습니다!")
        d = NP[msg.guild.id]
        now = culc_length(time() - NP[msg.guild.id][2])
        total = culc_length(int(d[1]['duration']))
        msg = await msgReply(msg, f"{d[1]['title']} | {now}/{total} | [Youtube]({d[1]['YTURL']})")
        while time() - NP[msg.guild.id][2] <= d[1]['duration'] and voice_client.is_playing():
            now = culc_length(time() - NP[msg.guild.id][2])
            await msg.edit(content=f"{d[1]['title']} | {now}/{total} | [Youtube]({d[1]['YTURL']})")
            await asyncio.sleep(1)

    if msg.content == f"{prefix}queue" or msg.content == f"{prefix}q":
        if msg.guild.id not in queues or len(queues[msg.guild.id]) == 0: return await msgReply(msg, "현재 대기열에 음악이 없습니다!")
        embed = discord.Embed(
            title="현재 대기열",
            color=0xFF0000
        )
        embed.set_author(name=bot.user, icon_url=bot.user.avatar.url)
        embed.set_thumbnail(url=queues[msg.guild.id][0][1]["thumb"])
        for i, d in enumerate(queues[msg.guild.id]):
            embed.add_field(name=f"{i+1}. {d[1]['title']} ({culc_length(d[1]['duration'])})", value=f"[Youtube]({d[1]['YTURL']})", inline=False)
        embed.timestamp = msg.created_at
        embed.set_footer(text=f"Made By {BotOwner.name}", icon_url=BotOwner.avatar.url)
        await msgReply(msg, embed=embed)

    if msg.content == f"{prefix}volume" or msg.content == f"{prefix}v":
        voice_client = discord.utils.get(bot.voice_clients, guild=msg.guild)
        if not voice_client or not voice_client.is_playing(): return await msgReply(msg, "현재 재생 중인 음악이 없습니다!")
        return await msgReply(msg, f"{voice_client.source.volume * 100}%")
    if msg.content.startswith(f"{prefix}volume ") or msg.content.startswith(f"{prefix}v "):
        try:
            volume = int(msg.content.split()[1])
            if volume < 0 or volume > 100: return await msgReply(msg, "볼륨은 0에서 100 사이로 설정해주세요!")
            voice_client = discord.utils.get(bot.voice_clients, guild=msg.guild)
            if not voice_client or not voice_client.is_playing() or not SVOL.get(msg.guild.id): return await msgReply(msg, "현재 재생 중인 음악이 없습니다!")
            SVOL[msg.guild.id] = volume; voice_client.source.volume = volume / 100  # 볼륨 조정
            return await msgReply(msg, f"볼륨이 {volume}%로 설정되었습니다!")
        except (IndexError, ValueError): return await msgReply(msg, f"볼륨 값을 입력해주세요! 예: `{prefix}volume 20`")

    if msg.content.startswith(f"{prefix}search "):
        sl = []; search_query = msg.content.split(" ", 1)[1]
        if not search_query: return await msgReply(msg, f"검색할 음악 제목을 입력해주세요! 예: `{prefix}search [SongName]`")
        search_results = await search_song(msg, search_query)
        embed = discord.Embed(
            title=f"검색 결과 : {search_query}",
            color=0xFF0000
        )
        embed.set_author(name=bot.user, icon_url=bot.user.avatar.url)
        embed.set_thumbnail(url=search_results[0]["thumb"])
        for i, sr in enumerate(search_results):
            try:
                sl.append(sr["YTURL"])
                embed.add_field(name=f"{i+1}. {sr['title']} ({culc_length(sr['duration'])})", value=f"[Youtube]({sr['YTURL']})", inline=False)
            except: exceptionE(i+1)
        embed.add_field(name=f"0. 검색취소", value=f"{search_query} 검색을 취소합니다. (또는 30초 경과시 자동 취소됨)", inline=False)
        embed.timestamp = msg.created_at
        embed.set_footer(text=f"Made By {BotOwner.name}", icon_url=BotOwner.avatar.url)
        srmsg = await msgReply(msg, embed=embed)

        def ucs(m): return m.author == msg.author and m.content.isdigit() and 0 <= int(m.content) <= 10
        try:
            umsg = await bot.wait_for("message", timeout=30, check=ucs) #곡 번호 선택 대기
            idx = int(umsg.content) - 1
            if idx == -1: await srmsg.delete(); await umsg.delete(); return
            si = await search_song(msg, search_results[idx]["YTURL"], isplayCommand=True)
            await srmsgReply(msg, f"선택된 곡: [{si['title']}]({si['YTURL']})\n대기열에 추가되었습니다."); await srmsg.delete(); await umsg.delete()
            if msg.guild.id not in queues: queues[msg.guild.id] = []
            queues[msg.guild.id].append([msg, si]) #queues
            return await play_song(msg)
        except asyncio.TimeoutError: await msgReply(msg, "곡 선택 시간이 초과되었습니다. 다시 시도해주세요!"); await srmsg.delete(); return

    if msg.content == f"{prefix}shuffle":
        random.shuffle(queues[msg.guild.id])
        msg.content = f"{prefix}q"; return await on_message(msg, isEdited=True)
    
    if msg.content.startswith(f"{prefix}move ") or msg.content.startswith(f"{prefix}mv "):
        if len(msg.content.split()) < 3: return await msgReply(msg, f"대상과 위치를 둘 다 입력해주세요! 예: `{prefix}move 2 4`")
        _, tar, loc = msg.content.split(" ")
        try:
            tar = int(tar); loc = int(loc)
            if tar == loc: return await msgReply(msg, f"{tar} == {loc} | 이동 대상이 같은 위치로 이동함에 따라 스킵함")
            if len(queues[msg.guild.id]) < max(tar, loc) or min(tar, loc) <= 0: return await msgReply(msg, f"대기열에 {tar} or {loc}번 까지 존재하지 않습니다. (1~{len(queues[msg.guild.id])})")
            queues[msg.guild.id].insert(loc-1, queues[msg.guild.id].pop(tar-1))
            msg.content = f"{prefix}q"; return await on_message(msg, isEdited=True)
        except ValueError: return await msgReply(msg, f"숫자를 입력해주세요! 예: `{prefix}move 2 4`")
        except: return await msgReply(msg, f"에러 발생!\n{exceptionE()}")

    if msg.content == f"{prefix}loop" or msg.content == f"{prefix}l":
        if not SLOOP.get(msg.guild.id): SLOOP[msg.guild.id] = None
        SLOOP[msg.guild.id] = not SLOOP[msg.guild.id]
        if SLOOP[msg.guild.id]: d = NP[msg.guild.id]; npmsg = f"\n\n{d[1]['title']} ({culc_length(d[1]['duration'])}) [Youtube]({d[1]['YTURL']})"
        else: npmsg = ""
        await msgReply(msg, f"loop = {SLOOP[msg.guild.id]}{npmsg}")

    if msg.content == f"{prefix}lyrics" or msg.content == f"{prefix}ly":
        genius = lyricsgenius.Genius(GENIUSAccessToken)
        song = genius.search_song(NP[msg.guild.id][1]['title'])
        ly = song.lyrics if song else f"title : `{NP[msg.guild.id][1]['title']}`\n\n가사를 찾을 수 없습니다."
        await msgReply(msg, ly)

    if msg.content == f"{prefix}help" or msg.content == f"{prefix}h":
        embed = discord.Embed(
            title="명령어",
            color=0xFF0000
        )
        embed.set_author(name=bot.user, icon_url=bot.user.avatar.url)
        embed.set_thumbnail(url=bot.user.avatar.url)
        embed.add_field(name=f"{prefix}봇초대 (invite)", value="봇 초대 주소입니다.")
        embed.add_field(name=f"{prefix}help (h)", value="명령어를 보여줍니다.")
        embed.add_field(name=f"{prefix}ping", value=f"봇의 서버핑을 보여줍니다.")
        embed.add_field(name=f"{prefix}uptime (u)", value=f"가동 시간 확인")
        embed.add_field(name=f"{prefix}clear <지울 만큼의 숫자>", value=f"입력받은 개수의 메세지 삭제 (`{prefix}clear` 명령어는 포함하지 않음)")

        embed.add_field(name=f"{prefix}loop (l)", value=f"음악 반복을 실행/해제 합니다.")
        embed.add_field(name=f"{prefix}lyrics (ly)", value=f"현재 재생중인 음악의 가사를 가져옵니다.")
        embed.add_field(name=f"{prefix}move (mv) <이동할 만큼의 숫자>", value=f"대기열에서 음악을 이동합니다.")
        embed.add_field(name=f"{prefix}np", value=f"현재 재생중인 음악을 표시합니다.")
        embed.add_field(name=f"{prefix}pause", value=f"현재 재생중인 음악을 일시 중지합니다.")
        embed.add_field(name=f"{prefix}play (p) <링크>", value=f"YouTube 에서 음악을 재생합니다.")
        embed.add_field(name=f"{prefix}playlist (pl) <링크>", value=f"YouTube 재생목록에 있는 모든 음악을 재생합니다.")
        embed.add_field(name=f"{prefix}queue (q)", value=f"현재 재생중인 음악과 대기열을 표시합니다.")
        embed.add_field(name=f"{prefix}resume (r)", value=f"현재 재생중인 음악을 재개합니다.")
        embed.add_field(name=f"{prefix}search <검색어>", value=f"유튜브에서 검색하고 재생할 음원을 선택합니다.")
        embed.add_field(name=f"{prefix}shuffle", value=f"대기열 섞기")
        embed.add_field(name=f"{prefix}skip (s) [넘길 숫자]", value=f"현재 재생중인 음악을 넘기거나, 대기열부터 음악을 제거합니다.")
        embed.add_field(name=f"{prefix}skipto (st) <넘길 만큼의 숫자>", value=f"설정한 대기열 번호까지 음악을 넘깁니다.")
        embed.add_field(name=f"{prefix}stop", value=f"모든 음악을 멈추고 봇의 연결을 끊습니다.")
        embed.add_field(name=f"{prefix}volume (v) [0~100]", value=f"현재 재생중인 음악의 볼륨을 설정합니다.")
        embed.add_field(name=f"{prefix}join [음성 채널 ID]", value=f"봇을 음성 채널에 입장시킵니다.")
        embed.add_field(name=f"{prefix}leave", value=f"봇을 음성 채널에서 퇴장시킵니다.")

        embed.timestamp = msg.created_at
        embed.set_footer(text=f"Made By {BotOwner.name}", icon_url=BotOwner.avatar.url)
        return await msgReply(msg, embed=embed)

    if msg.content.startswith(f"{prefix}clear"):
        if not msg.author.guild_permissions.manage_messages: return await msgReply(msg, "권한이 없습니다.")
        try: amount = int(msg.content.split(" ")[1])
        except: amount = 0
        if amount < 1 or amount > 100: return await msgReply(msg, "1부터 100까지의 숫자만 입력하세요.")
        await msg.channel.purge(limit=amount + 1)
        #무조건 msg.channel.send 쓰기
        msg = await msg.channel.send(f"{amount}개의 메시지를 삭제했습니다. 이 메시지는 3초 후 삭제됩니다.")
        for i in range(3, 0, -1):
            await msg.edit(content=f"{amount}개의 메시지를 삭제했습니다. 이 메시지는 {i}초 후 삭제됩니다.")
            await asyncio.sleep(1)
        return await msg.delete()
    
    #기능 없이 음챗에만 접속
    if msg.content == f"{prefix}join":
        voice_client = discord.utils.get(bot.voice_clients, guild=msg.guild)
        if voice_client and voice_client.is_connected(): return await msgReply(msg, "이미 음성 채널에 접속해 있어요.")
        if msg.author.voice: voice_client = await msg.author.voice.channel.connect(reconnect=False)
        else: return await msgReply(msg, "음성 채널에 먼저 접속해주세요!")
    if msg.content.startswith(f"{prefix}join "):
        try: vcID = int(msg.content.split(" ")[1])
        except: return await msgReply(msg, "숫자로 구성된 음성 채널 ID로 입력하세요!")
        channel = msg.guild.get_channel(vcID)
        if channel and isinstance(channel, discord.VoiceChannel): await channel.connect(reconnect=False)
        else: return await msgReply(msg, f"해당 ID(<#{vcID}>) 의 음성 채널을 찾을 수 없어요.")
    if msg.content.startswith(f"{prefix}leave"):
        voice_client = discord.utils.get(bot.voice_clients, guild=msg.guild)
        if voice_client and voice_client.is_connected(): await voice_client.disconnect()
        else: return await msgReply(msg, "음성 채널에 접속해 있지 않아요.")

##/////////////////////////////////////////////////////////////따로뺴둠//////////////////////////////////////////////////////////////##

# 봇 초대 명령어
    if msg.content == f"{prefix}봇" or msg.content == f"{prefix}봇초대" or msg.content == f"{prefix}invite":

        embed = discord.Embed(
            title="봇 초대 링크 생성 (Bot Permissions)",
            color=0xFF0000
        )
        embed.set_author(name=bot.user, icon_url=bot.user.avatar.url)
        embed.set_thumbnail(url=bot.user.avatar.url)
        embed.add_field(name=f"1. Administrator", value="관리자 권한으로 초대링크 생성됨 (8)", inline=False)
        embed.add_field(name=f"2. 메시지 전송 및 관리, 음성채팅 연결 및 말하기", value="해당 권한으로 초대링크 생성됨 (277028562944)", inline=False)
        embed.add_field(name=f"0. 생성취소", value="링크 생성을 취소합니다. (또는 30초 경과시 자동 취소됨)", inline=False)

        embed.timestamp = msg.created_at
        embed.set_footer(text=f"Made By {BotOwner.name}", icon_url=BotOwner.avatar.url)
        srmsg = await msgReply(msg, embed=embed)

        def ucs(m): return m.author == msg.author and m.content.isdigit()
        try:
            umsg = await bot.wait_for("message", timeout=30, check=ucs)
            idx = int(umsg.content)
            await srmsg.delete(); await umsg.delete()
            if idx == 0: return
            elif idx == 1: perm = 8; pt = "관리자"
            elif idx == 2: perm = 277028562944; pt = "메시지 전송 및 관리, 음성채팅 연결 및 말하기"
            return await msgReply(msg, f"{pt} 권한으로 링크 생성 완료!\nhttps://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions={perm}&scope=bot+applications.commands")
        except asyncio.TimeoutError: await msgReply(msg, "곡 선택 시간이 초과되었습니다. 다시 시도해주세요!"); await srmsg.delete(); return

# Ping 명령어
    if msg.content == f"{prefix}핑" or msg.content == f"{prefix}ping":
        ping = f"서버 핑은 **{round(bot.latency * 1000)}ms** 입니다."; log.info(ping)
        return await msgReply(msg, ping)

# uptime 명령어
    if msg.content == f"{prefix}uptime" or msg.content == f"{prefix}u": return await msgReply(msg, f"<t:{st}:F>\n<t:{st}:R>")

bot.run(token) #봇을 실행합니다.
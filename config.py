import json
import os
import logUtils as log
import traceback

def conf(filename: str="config.json") -> dict:
    if os.path.isfile(filename):
        try:
            with open(filename, "r", encoding="utf-8") as c: return json.load(c)
        except: log.error(f"{filename} 파일 에러!\n\n{traceback.format_exc()}"); exit()
    else:
        with open(filename, "w", encoding="utf-8") as c: c.write(
            json.dumps(
                {
                    "DISCORD_BOT_TOKEN": "Make BOT First & GET TO https://discord.com/developers/applications",
                    "PREFIX": "!",
                    "BotOwnerID": "Input_Your_Discord_ID",
                    "GENIUS_ACCESS_TOKEN": "GET TO https://genius.com/api-clients",
                    "AUDIO_DOWNLOAD": True,
                    "AUDIO_AUTO_REMOVE": False,
                    "MAX_PLAYLIST_SIZE": 20,
                    "STAY_TIME": 300,
                    "DEFAULT_VOLUME": 20
                }, indent=2
            )
        )
        input(f"생성된 {filename} 파일을 수정하세요!"); exit()
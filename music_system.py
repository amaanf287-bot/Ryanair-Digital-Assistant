import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, urlparse

import aiohttp
import discord
from discord.ext import commands
import imageio_ffmpeg
import yt_dlp


RYANAIR_BLUE = 0x073590
ACCEPTANCE_FILE = Path("music_acceptance.json")
MAX_TRACK_SECONDS = 15 * 60
MAX_QUEUE_SIZE = 25
SEARCH_RESULTS = 5

MUSIC_RULES = (
    "1. You must be connected to a voice channel to use the music player.\n"
    "2. Only clean, family-friendly music is allowed.\n"
    "3. Explicit profanity, sexual content, hate/slurs, graphic violence, or drug-focused content is not allowed.\n"
    "4. Every requested song must pass the automated AI safety check before it can enter the queue.\n"
    "5. Songs that cannot be verified are blocked rather than played.\n"
    "6. Do not spam requests, deliberately bypass the safety system, or disrupt the voice channel."
)

BLOCKED_METADATA_TERMS = {"explicit", "uncensored", "nsfw", "18+"}
YOUTUBE_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
    "youtu.be", "www.youtu.be",
}


def _load_acceptance() -> dict[str, str]:
    try:
        raw = json.loads(ACCEPTANCE_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return {str(k): str(v) for k, v in raw.items()}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return {}


def _save_acceptance(data: dict[str, str]) -> None:
    try:
        ACCEPTANCE_FILE.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    except OSError as exc:
        print(f"MUSIC WARNING — could not save acceptance data: {exc}", flush=True)


def _format_duration(seconds: Optional[int]) -> str:
    if not seconds:
        return "Unknown length"
    minutes, sec = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{sec:02d}" if hours else f"{minutes}:{sec:02d}"


def _clean_title(value: str) -> str:
    value = re.sub(
        r"\s*[\[(].*?(official|lyrics?|audio|video|visuali[sz]er).*?[\])]+\s*",
        " ", value, flags=re.I,
    )
    return re.sub(r"\s+", " ", value).strip(" -–—|")[:200]


def _is_youtube_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
        return parsed.scheme in {"http", "https"} and parsed.hostname in YOUTUBE_HOSTS
    except Exception:
        return False


@dataclass
class Track:
    title: str
    webpage_url: str
    duration: Optional[int]
    uploader: str
    requester_id: int
    requester_name: str
    artist: str = ""
    song_title: str = ""


@dataclass
class SearchItem:
    title: str
    webpage_url: str
    duration: Optional[int]
    uploader: str


class MusicManager:
    def __init__(self, bot: commands.Bot, groq_client: Any = None):
        self.bot = bot
        self.groq_client = groq_client
        self.accepted = _load_acceptance()
        self.queues: dict[int, list[Track]] = {}
        self.current: dict[int, Track] = {}
        self.locks: dict[int, asyncio.Lock] = {}
        self.ffmpeg_executable = imageio_ffmpeg.get_ffmpeg_exe()

    def has_accepted(self, user_id: int) -> bool:
        return str(user_id) in self.accepted

    def accept(self, user_id: int) -> None:
        self.accepted[str(user_id)] = datetime.now(timezone.utc).isoformat()
        _save_acceptance(self.accepted)

    def _lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self.locks:
            self.locks[guild_id] = asyncio.Lock()
        return self.locks[guild_id]

    async def ensure_voice(self, guild: discord.Guild, user: discord.Member):
        if not user.voice or not user.voice.channel:
            return None, "You must be connected to a voice channel first."

        target = user.voice.channel
        voice = guild.voice_client
        try:
            if voice and voice.is_connected():
                if voice.channel.id != target.id:
                    if voice.is_playing() or voice.is_paused():
                        return None, f"Music is already active in **{voice.channel.name}**."
                    await voice.move_to(target)
            else:
                voice = await target.connect(self_deaf=True)
        except discord.ClientException as exc:
            return None, f"I could not connect to the voice channel: {exc}"
        except discord.Forbidden:
            return None, "I do not have permission to connect/speak in that voice channel."
        except Exception as exc:
            return None, f"Voice connection failed: {type(exc).__name__}."
        return voice, None

    async def search(self, query: str) -> list[SearchItem]:
        query = query.strip()
        if not query:
            return []
        if query.startswith(("http://", "https://")) and not _is_youtube_url(query):
            raise ValueError("Only YouTube links are accepted. You can also type a song name.")

        target = query if _is_youtube_url(query) else f"ytsearch{SEARCH_RESULTS}:{query}"
        opts = {
            "quiet": True, "no_warnings": True, "noplaylist": True,
            "skip_download": True, "extract_flat": "in_playlist",
            "default_search": "ytsearch", "socket_timeout": 15,
        }

        def _extract():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(target, download=False)

        info = await asyncio.to_thread(_extract)
        entries = info.get("entries") if isinstance(info, dict) else None
        if entries is None:
            entries = [info]

        results = []
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            duration = entry.get("duration")
            if duration and duration > MAX_TRACK_SECONDS:
                continue
            if entry.get("is_live") or entry.get("live_status") == "is_live":
                continue
            video_id = entry.get("id")
            url = entry.get("webpage_url") or entry.get("url")
            if url and not str(url).startswith("http") and video_id:
                url = f"https://www.youtube.com/watch?v={video_id}"
            elif not url and video_id:
                url = f"https://www.youtube.com/watch?v={video_id}"
            if not url:
                continue
            results.append(SearchItem(
                title=str(entry.get("title") or "Unknown track")[:200],
                webpage_url=str(url),
                duration=int(duration) if duration else None,
                uploader=str(entry.get("uploader") or entry.get("channel") or "Unknown artist")[:100],
            ))
            if len(results) >= SEARCH_RESULTS:
                break
        return results

    async def _full_info(self, url: str) -> dict[str, Any]:
        opts = {
            "quiet": True, "no_warnings": True, "noplaylist": True,
            "skip_download": True, "format": "bestaudio/best", "socket_timeout": 20,
        }

        def _extract():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)

        info = await asyncio.to_thread(_extract)
        if not isinstance(info, dict):
            raise RuntimeError("Could not read the selected track.")
        duration = info.get("duration")
        if duration and int(duration) > MAX_TRACK_SECONDS:
            raise ValueError("Tracks longer than 15 minutes are not allowed.")
        if info.get("is_live") or info.get("live_status") == "is_live":
            raise ValueError("Live streams are not allowed in the music player.")
        return info

    async def _identify_song(self, info: dict[str, Any]):
        direct_title = str(info.get("track") or "").strip()
        direct_artist = str(info.get("artist") or info.get("creator") or "").strip()
        if direct_title and direct_artist:
            return _clean_title(direct_artist), _clean_title(direct_title)

        title = str(info.get("title") or "")[:300]
        uploader = str(info.get("uploader") or info.get("channel") or "")[:200]
        if self.groq_client:
            system = (
                "Extract the most likely music artist and song title from YouTube metadata. "
                "Return ONLY compact JSON in the exact form "
                '{"artist":"...","title":"..."}. Do not add markdown.'
            )
            prompt = f"Video title: {title}\nUploader/channel: {uploader}"
            try:
                response = await asyncio.to_thread(
                    self.groq_client.chat.completions.create,
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                    max_tokens=100, temperature=0,
                )
                raw = response.choices[0].message.content.strip()
                raw = raw.removeprefix("```json").removesuffix("```").strip()
                parsed = json.loads(raw)
                artist = _clean_title(str(parsed.get("artist") or ""))
                song = _clean_title(str(parsed.get("title") or ""))
                if artist and song:
                    return artist, song
            except Exception as exc:
                print(f"MUSIC AI identify warning: {type(exc).__name__}: {exc}", flush=True)

        cleaned = _clean_title(title)
        for sep in (" - ", " – ", " — ", " | "):
            if sep in cleaned:
                left, right = cleaned.split(sep, 1)
                if left.strip() and right.strip():
                    return left.strip()[:100], right.strip()[:150]
        return _clean_title(uploader), cleaned

    async def _fetch_lyrics(self, artist: str, title: str):
        if not artist or not title:
            return None
        url = f"https://api.lyrics.ovh/v1/{quote(artist, safe='')}/{quote(title, safe='')}"
        timeout = aiohttp.ClientTimeout(total=12)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return None
                    data = await response.json(content_type=None)
                    lyrics = data.get("lyrics") if isinstance(data, dict) else None
                    if isinstance(lyrics, str) and len(lyrics.strip()) >= 20:
                        return lyrics.strip()
        except Exception as exc:
            print(f"MUSIC lyrics lookup warning: {type(exc).__name__}: {exc}", flush=True)
        return None

    async def safety_scan(self, info: dict[str, Any]):
        title = str(info.get("title") or "Unknown track")
        uploader = str(info.get("uploader") or info.get("channel") or "Unknown artist")
        metadata_text = f"{title} {uploader}".lower()
        if any(term in metadata_text for term in BLOCKED_METADATA_TERMS):
            return False, "The track metadata indicates explicit/unrestricted content.", "", ""

        if not self.groq_client:
            return False, "The AI music safety scanner is not configured, so this song cannot be verified.", "", ""

        artist, song_title = await self._identify_song(info)
        lyrics = await self._fetch_lyrics(artist, song_title)
        if not lyrics:
            return False, "I could not verify the song's lyrics, so strict safety mode blocked it.", artist, song_title

        system = (
            "You are a strict family-friendly music safety classifier for a Roblox/Discord community. "
            "Reject a song if its lyrics contain meaningful explicit profanity, sexual content or references, "
            "hate speech or slurs, graphic violence, encouragement of self-harm, or drug/alcohol glorification. "
            "Minor non-graphic sadness or ordinary romance is allowed. "
            "Return ONLY compact JSON with keys allowed (boolean) and reason (short string)."
        )
        prompt = (
            f"Artist: {artist}\nSong: {song_title}\nYouTube title: {title}\n\n"
            f"Lyrics to classify:\n{lyrics[:14000]}"
        )
        try:
            response = await asyncio.to_thread(
                self.groq_client.chat.completions.create,
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                max_tokens=180, temperature=0,
            )
            raw = response.choices[0].message.content.strip()
            raw = raw.removeprefix("```json").removesuffix("```").strip()
            parsed = json.loads(raw)
            allowed = parsed.get("allowed") is True
            reason = str(parsed.get("reason") or ("Passed AI safety scan." if allowed else "Rejected by AI safety scan."))[:300]
            return allowed, reason, artist, song_title
        except Exception as exc:
            print(f"MUSIC AI scan warning: {type(exc).__name__}: {exc}", flush=True)
            return False, "The AI safety scan failed, so strict safety mode blocked the track.", artist, song_title

    async def prepare_and_enqueue(self, guild, member, item: SearchItem):
        if not self.has_accepted(member.id):
            return False, "You must accept the music rules first with `!acceptmusicrules`."

        voice, error = await self.ensure_voice(guild, member)
        if error or not voice:
            return False, error or "Could not connect to voice."
        if len(self.queues.setdefault(guild.id, [])) >= MAX_QUEUE_SIZE:
            return False, "The music queue is full."

        try:
            info = await self._full_info(item.webpage_url)
        except Exception as exc:
            return False, str(exc)

        allowed, reason, artist, song_title = await self.safety_scan(info)
        if not allowed:
            return False, f"🛡️ **Blocked by music safety:** {reason}"

        track = Track(
            title=str(info.get("title") or item.title)[:200],
            webpage_url=str(info.get("webpage_url") or item.webpage_url),
            duration=int(info.get("duration")) if info.get("duration") else item.duration,
            uploader=str(info.get("uploader") or info.get("channel") or item.uploader)[:100],
            requester_id=member.id,
            requester_name=member.display_name,
            artist=artist,
            song_title=song_title,
        )

        async with self._lock(guild.id):
            queue = self.queues.setdefault(guild.id, [])
            queue.append(track)
            position = len(queue)
            if not voice.is_playing() and not voice.is_paused() and guild.id not in self.current:
                await self._play_next(guild.id)
                position = 0

        if position == 0:
            return True, f"✅ **Now playing:** {track.title}\n🛡️ AI safety check passed: {reason}"
        return True, f"✅ Added **{track.title}** to the queue at position **{position}**.\n🛡️ AI safety check passed: {reason}"

    async def _resolve_audio_url(self, webpage_url: str):
        opts = {
            "quiet": True, "no_warnings": True, "noplaylist": True,
            "format": "bestaudio/best", "socket_timeout": 20,
        }
        def _extract():
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(webpage_url, download=False)
                if not isinstance(info, dict):
                    raise RuntimeError("No audio information returned.")
                return str(info["url"])
        return await asyncio.to_thread(_extract)

    async def _play_next(self, guild_id: int):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            self.current.pop(guild_id, None)
            return
        voice = guild.voice_client
        if not voice or not voice.is_connected():
            self.current.pop(guild_id, None)
            return
        queue = self.queues.setdefault(guild_id, [])
        if not queue:
            self.current.pop(guild_id, None)
            return

        track = queue.pop(0)
        self.current[guild_id] = track
        try:
            audio_url = await self._resolve_audio_url(track.webpage_url)
            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(
                    audio_url,
                    executable=self.ffmpeg_executable,
                    before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                    options="-vn",
                ),
                volume=0.45,
            )
            def _after(error):
                if error:
                    print(f"MUSIC playback error in guild {guild_id}: {error}", flush=True)
                asyncio.run_coroutine_threadsafe(self._track_finished(guild_id), self.bot.loop)
            voice.play(source, after=_after)
        except Exception as exc:
            print(f"MUSIC could not start track {track.title}: {type(exc).__name__}: {exc}", flush=True)
            self.current.pop(guild_id, None)
            await self._play_next(guild_id)

    async def _track_finished(self, guild_id: int):
        self.current.pop(guild_id, None)
        await self._play_next(guild_id)

    async def pause_resume(self, guild, member):
        voice, error = await self.ensure_voice(guild, member)
        if error or not voice:
            return error or "Voice connection unavailable."
        if voice.is_paused():
            voice.resume()
            return "▶️ Music resumed."
        if voice.is_playing():
            voice.pause()
            return "⏸️ Music paused."
        return "Nothing is currently playing."

    async def skip(self, guild, member):
        voice, error = await self.ensure_voice(guild, member)
        if error or not voice:
            return error or "Voice connection unavailable."
        if voice.is_playing() or voice.is_paused():
            voice.stop()
            return "⏭️ Skipped the current song."
        return "Nothing is currently playing."

    async def stop(self, guild, member):
        voice = guild.voice_client
        if not member.voice or not member.voice.channel:
            return "You must be in a voice channel to control the music player."
        if not voice or not voice.is_connected():
            return "I am not connected to a voice channel."
        if voice.channel.id != member.voice.channel.id:
            return f"You must be in **{voice.channel.name}** to control this player."
        self.queues[guild.id] = []
        self.current.pop(guild.id, None)
        if voice.is_playing() or voice.is_paused():
            voice.stop()
        await voice.disconnect(force=True)
        return "⏹️ Queue cleared and I left the voice channel."

    def queue_text(self, guild_id: int):
        lines = []
        current = self.current.get(guild_id)
        if current:
            lines.append(f"**Now playing:** {current.title} — requested by {current.requester_name}")
        queue = self.queues.get(guild_id, [])
        if queue:
            lines.append("\n**Up next:**")
            for index, track in enumerate(queue[:10], 1):
                lines.append(f"`{index}.` {track.title} • {_format_duration(track.duration)} • {track.requester_name}")
            if len(queue) > 10:
                lines.append(f"…and {len(queue) - 10} more.")
        return "\n".join(lines) if lines else "The music queue is empty."


class AcceptMusicRulesView(discord.ui.View):
    def __init__(self, manager, owner_id):
        super().__init__(timeout=300)
        self.manager = manager
        self.owner_id = owner_id

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This rules panel belongs to another user.")
            return False
        return True

    @discord.ui.button(label="I Accept the Music Rules", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction, button):
        self.manager.accept(interaction.user.id)
        button.disabled = True
        button.label = "Rules Accepted"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            "✅ Music access enabled. Join a voice channel and use `!music` in the server to open your private player panel."
        )
        self.stop()


class SongSearchModal(discord.ui.Modal, title="Choose music"):
    query = discord.ui.TextInput(
        label="Song name or YouTube link",
        placeholder="Example: artist - song name",
        min_length=2,
        max_length=180,
    )

    def __init__(self, manager, owner_id, guild_id):
        super().__init__(timeout=180)
        self.manager = manager
        self.owner_id = owner_id
        self.guild_id = guild_id

    async def on_submit(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This music panel is not yours.")
            return
        guild = self.manager.bot.get_guild(self.guild_id)
        member = guild.get_member(interaction.user.id) if guild else None
        if not guild or not member or not member.voice or not member.voice.channel:
            await interaction.response.send_message("Join a voice channel before choosing music.")
            return

        await interaction.response.send_message("🔎 Searching for clean music options…")
        try:
            results = await self.manager.search(str(self.query))
        except Exception as exc:
            await interaction.followup.send(f"❌ Search failed: {exc}")
            return
        if not results:
            await interaction.followup.send(
                "No suitable results were found. Tracks over 15 minutes and live streams are excluded."
            )
            return

        embed = discord.Embed(
            title="🎵 Select a song",
            description="Choose one result below. The selected song will be AI safety-scanned **before** it is allowed to play.",
            color=RYANAIR_BLUE,
        )
        for index, result in enumerate(results, 1):
            embed.add_field(
                name=f"{index}. {result.title[:85]}",
                value=f"{result.uploader} • {_format_duration(result.duration)}",
                inline=False,
            )
        await interaction.followup.send(
            embed=embed,
            view=SongResultView(self.manager, self.owner_id, self.guild_id, results),
        )


class SongSelect(discord.ui.Select):
    def __init__(self, manager, owner_id, guild_id, results):
        self.manager = manager
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.results = results
        options = [
            discord.SelectOption(
                label=result.title[:100],
                description=f"{result.uploader[:70]} • {_format_duration(result.duration)}"[:100],
                value=str(index), emoji="🎵",
            )
            for index, result in enumerate(results)
        ]
        super().__init__(placeholder="Select a song to safety-check", min_values=1, max_values=1, options=options)

    async def callback(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This music selection belongs to another user.")
            return
        guild = self.manager.bot.get_guild(self.guild_id)
        member = guild.get_member(interaction.user.id) if guild else None
        if not guild or not member:
            await interaction.response.send_message("I can no longer find you in that server.")
            return
        if not member.voice or not member.voice.channel:
            await interaction.response.send_message("Join a voice channel before adding music.")
            return

        selected = self.results[int(self.values[0])]
        await interaction.response.send_message(f"🛡️ AI safety-scanning **{selected.title}** before playback…")
        ok, message = await self.manager.prepare_and_enqueue(guild, member, selected)
        await interaction.followup.send(message)
        if ok:
            self.disabled = True
            try:
                await interaction.message.edit(view=self.view)
            except Exception:
                pass


class SongResultView(discord.ui.View):
    def __init__(self, manager, owner_id, guild_id, results):
        super().__init__(timeout=300)
        self.add_item(SongSelect(manager, owner_id, guild_id, results))


class MusicPanelView(discord.ui.View):
    def __init__(self, manager, owner_id, guild_id):
        super().__init__(timeout=1800)
        self.manager = manager
        self.owner_id = owner_id
        self.guild_id = guild_id

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This private music panel is not yours.")
            return False
        return True

    def _guild_member(self, user_id):
        guild = self.manager.bot.get_guild(self.guild_id)
        return (guild, guild.get_member(user_id)) if guild else (None, None)

    @discord.ui.button(label="Choose Music", style=discord.ButtonStyle.primary, emoji="🎵", row=0)
    async def choose(self, interaction, button):
        guild, member = self._guild_member(interaction.user.id)
        if not guild or not member:
            await interaction.response.send_message("I can no longer find you in that server.")
            return
        if not member.voice or not member.voice.channel:
            await interaction.response.send_message("Join a voice channel before choosing music.")
            return
        await interaction.response.send_modal(SongSearchModal(self.manager, self.owner_id, self.guild_id))

    @discord.ui.button(label="Pause / Resume", style=discord.ButtonStyle.secondary, emoji="⏯️", row=0)
    async def pause_resume(self, interaction, button):
        guild, member = self._guild_member(interaction.user.id)
        if not guild or not member:
            await interaction.response.send_message("I can no longer find you in that server.")
            return
        await interaction.response.send_message(await self.manager.pause_resume(guild, member))

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary, emoji="⏭️", row=0)
    async def skip(self, interaction, button):
        guild, member = self._guild_member(interaction.user.id)
        if not guild or not member:
            await interaction.response.send_message("I can no longer find you in that server.")
            return
        await interaction.response.send_message(await self.manager.skip(guild, member))

    @discord.ui.button(label="Queue", style=discord.ButtonStyle.secondary, emoji="📜", row=1)
    async def queue(self, interaction, button):
        await interaction.response.send_message(self.manager.queue_text(self.guild_id))

    @discord.ui.button(label="Stop & Leave", style=discord.ButtonStyle.danger, emoji="⏹️", row=1)
    async def stop(self, interaction, button):
        guild, member = self._guild_member(interaction.user.id)
        if not guild or not member:
            await interaction.response.send_message("I can no longer find you in that server.")
            return
        await interaction.response.send_message(await self.manager.stop(guild, member))


async def _delete_command_message(ctx):
    try:
        await ctx.message.delete()
    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
        pass


def setup(bot: commands.Bot, groq_client: Any = None):
    existing = getattr(bot, "_ryanair_music_manager", None)
    if existing:
        return existing

    manager = MusicManager(bot, groq_client)
    bot._ryanair_music_manager = manager

    @bot.command(name="acceptmusicrules")
    @commands.guild_only()
    async def accept_music_rules(ctx):
        await _delete_command_message(ctx)
        if manager.has_accepted(ctx.author.id):
            try:
                await ctx.author.send(
                    "✅ You have already accepted the music rules. Join a voice channel and use `!music` in the server."
                )
            except discord.Forbidden:
                await ctx.send("You already have music access, but I could not DM you.", delete_after=8)
            return

        embed = discord.Embed(
            title="🎵 Music Player Rules",
            description=f"{MUSIC_RULES}\n\nPress **I Accept the Music Rules** below to unlock the player.",
            color=RYANAIR_BLUE,
        )
        embed.set_footer(text="Music access is optional and unverified tracks are blocked.")
        try:
            await ctx.author.send(embed=embed, view=AcceptMusicRulesView(manager, ctx.author.id))
        except discord.Forbidden:
            await ctx.send(
                f"{ctx.author.mention}, enable DMs from this server, then run `!acceptmusicrules` again.",
                delete_after=10,
            )

    @bot.command(name="music")
    @commands.guild_only()
    async def music_panel(ctx):
        await _delete_command_message(ctx)
        if not manager.has_accepted(ctx.author.id):
            try:
                await ctx.author.send("❌ You do not have music access yet. Run `!acceptmusicrules` in the server first.")
            except discord.Forbidden:
                await ctx.send(f"{ctx.author.mention}, run `!acceptmusicrules` first and enable DMs.", delete_after=10)
            return
        if not isinstance(ctx.author, discord.Member) or not ctx.author.voice or not ctx.author.voice.channel:
            try:
                await ctx.author.send("❌ Join a voice channel first, then run `!music` again.")
            except discord.Forbidden:
                await ctx.send(f"{ctx.author.mention}, join a voice channel first.", delete_after=8)
            return

        embed = discord.Embed(
            title="🎵 Private Music Player",
            description=(
                f"Server: **{ctx.guild.name}**\nVoice channel: **{ctx.author.voice.channel.name}**\n\n"
                "Use the controls below to choose and control music. Every selected song is checked before playback."
            ),
            color=RYANAIR_BLUE,
        )
        embed.add_field(
            name="🛡️ Safety",
            value=("AI scanner: **Online**\nStrict verification: **Enabled**" if groq_client
                   else "AI scanner: **Not configured — songs will be blocked**"),
            inline=False,
        )
        try:
            await ctx.author.send(embed=embed, view=MusicPanelView(manager, ctx.author.id, ctx.guild.id))
        except discord.Forbidden:
            await ctx.send(
                f"{ctx.author.mention}, I need permission to DM you for the private music panel.",
                delete_after=10,
            )

    @bot.command(name="commands")
    async def prefix_commands(ctx):
        embed = discord.Embed(
            title="⌨️ Text Commands",
            description="These commands do not use Discord slash-command slots.",
            color=RYANAIR_BLUE,
        )
        embed.add_field(
            name="🎵 Music",
            value=(
                "`!acceptmusicrules` — read and accept the music rules\n"
                "`!music` — open your private music control panel (you must be in VC)\n"
                "`!commands` — show this command list"
            ), inline=False,
        )
        embed.add_field(
            name="🛡️ Music safety",
            value="Songs are verified before playback. Tracks that cannot be safely verified are rejected.",
            inline=False,
        )
        try:
            await ctx.author.send(embed=embed)
            if ctx.guild:
                await _delete_command_message(ctx)
        except discord.Forbidden:
            await ctx.send(embed=embed, delete_after=20 if ctx.guild else None)

    print("Music system loaded: !acceptmusicrules, !music, !commands", flush=True)
    return manager

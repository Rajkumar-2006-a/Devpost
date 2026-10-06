"""
Video ingestion:
  1. Download (yt-dlp for YouTube URLs, or use local mp4)
  2. Transcribe with Whisper (word-level timestamps)
  3. Extract keyframes every N seconds (ffmpeg)
  4. Caption each keyframe with VLM
"""
from __future__ import annotations
import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    start: float   # seconds
    end: float     # seconds
    text: str


@dataclass
class Keyframe:
    timestamp: float      # seconds
    image_bytes: bytes
    caption: str = ""


@dataclass
class VideoContent:
    title: str
    duration: float
    segments: list[TranscriptSegment] = field(default_factory=list)
    keyframes: list[Keyframe] = field(default_factory=list)


async def process_video(path: Path, keyframe_interval: int = 30) -> VideoContent:
    """
    Full video processing pipeline.
    path: local mp4 file path
    """
    from app.config import get_settings
    settings = get_settings()

    # Step 1: Get duration
    duration = await _get_duration(path)
    title = path.stem

    # Step 2: Transcribe (runs in executor — Whisper is CPU-bound)
    logger.info(f"Transcribing {path.name} with Whisper ({settings.whisper_model})...")
    segments = await asyncio.get_event_loop().run_in_executor(
        None, _transcribe_sync, str(path), settings.whisper_model, settings.whisper_device
    )

    # Step 3: Extract keyframes
    logger.info(f"Extracting keyframes every {keyframe_interval}s...")
    keyframe_data = await _extract_keyframes(path, keyframe_interval, duration)

    # Step 4: Caption keyframes via VLM
    from app.services.llm.provider import get_vlm
    vlm = get_vlm()
    logger.info(f"Captioning {len(keyframe_data)} keyframes...")
    caption_tasks = [
        _caption_keyframe(vlm, ts, img_bytes)
        for ts, img_bytes in keyframe_data
    ]
    captioned = await asyncio.gather(*caption_tasks)

    keyframes = [
        Keyframe(timestamp=ts, image_bytes=img, caption=cap)
        for (ts, img), cap in zip(keyframe_data, captioned)
    ]

    return VideoContent(title=title, duration=duration, segments=segments, keyframes=keyframes)


async def download_youtube(url: str, output_dir: Path) -> Path:
    """Download a YouTube video using yt-dlp. Returns path to downloaded mp4."""
    import yt_dlp

    output_template = str(output_dir / "%(id)s.%(ext)s")
    ydl_opts = {
        "format": "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }

    info = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: _ydl_download(url, ydl_opts),
    )
    filename = info.get("_filename") or info.get("requested_downloads", [{}])[0].get("filepath", "")
    return Path(filename)


def _ydl_download(url: str, opts: dict) -> dict:
    import yt_dlp
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=True)


def _transcribe_sync(path: str, model_name: str, device: str) -> list[TranscriptSegment]:
    """Synchronous Whisper transcription (run in executor)."""
    import whisper
    model = whisper.load_model(model_name, device=device)
    result = model.transcribe(path, word_timestamps=False, verbose=False)
    segments = []
    for seg in result.get("segments", []):
        segments.append(TranscriptSegment(
            start=seg["start"],
            end=seg["end"],
            text=seg["text"].strip(),
        ))
    return segments


async def _get_duration(path: Path) -> float:
    """Get video duration in seconds via ffprobe."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    try:
        return float(stdout.decode().strip())
    except ValueError:
        return 0.0


async def _extract_keyframes(path: Path, interval: int, duration: float) -> list[tuple[float, bytes]]:
    """Extract one frame every `interval` seconds using ffmpeg."""
    frames: list[tuple[float, bytes]] = []
    timestamps = list(range(0, int(duration), interval))
    if not timestamps:
        timestamps = [0]

    async def grab_frame(ts: float) -> tuple[float, bytes] | None:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-ss", str(ts), "-i", str(path),
            "-vframes", "1", "-f", "image2", "-vcodec", "mjpeg", "pipe:1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        if stdout:
            return (ts, stdout)
        return None

    results = await asyncio.gather(*[grab_frame(ts) for ts in timestamps])
    return [r for r in results if r is not None]


async def _caption_keyframe(vlm, timestamp: float, img_bytes: bytes) -> str:
    from tenacity import retry, stop_after_attempt, wait_exponential

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _call():
        mins = int(timestamp) // 60
        secs = int(timestamp) % 60
        ts_str = f"{mins}:{secs:02d}"
        response = await vlm.generate(
            prompt=(
                f"You are analyzing a video frame at timestamp {ts_str} from a lecture or educational video. "
                "Describe what is shown on screen: if it's a slide, extract the key text and any diagram/figure; "
                "if it's a whiteboard, describe what is written; "
                "if it's code, transcribe it and explain; "
                "if it's just a speaker, say so briefly. "
                "Focus on information useful to a student (2-5 sentences)."
            ),
            images=[img_bytes],
            max_tokens=512,
            temperature=0.1,
        )
        return response.text.strip()

    try:
        return await _call()
    except Exception as e:
        mins = int(timestamp) // 60
        secs = int(timestamp) % 60
        logger.error(f"Keyframe captioning failed at {mins}:{secs:02d}: {e}")
        return f"[Video frame at {mins}:{secs:02d} — captioning failed]"

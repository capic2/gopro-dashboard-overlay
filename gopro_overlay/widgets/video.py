import subprocess
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

from gopro_overlay.dimensions import Dimension
from gopro_overlay.ffmpeg import FFMPEG
from gopro_overlay.point import Coordinate
from gopro_overlay.timeunits import timeunits
from gopro_overlay.widgets.widgets import Widget


class VideoFrameSource:
    def __init__(self, ffmpeg: FFMPEG, filepath: Path, dimensions: Dimension, fps: float = 10.0, fit: str = "cover"):
        self.ffmpeg = ffmpeg
        self.filepath = filepath
        self.dimensions = dimensions
        self.fps = fps
        self.fit = fit
        self.process = None
        self.next_index: Optional[int] = None
        self.frame_bytes = dimensions.x * dimensions.y * 4

    def close(self):
        if self.process is not None:
            try:
                self.process.terminate()
            except Exception:
                pass
            self.process = None
            self.next_index = None

    def __del__(self):
        self.close()

    def frame_at(self, seconds: float) -> Optional[Image.Image]:
        if seconds < 0:
            return None

        wanted_index = int(seconds * self.fps)

        if self.process is None or self.next_index is None or wanted_index < self.next_index:
            self._open(seconds)
            wanted_index = 0

        if wanted_index > self.next_index + int(self.fps * 2):
            self._open(seconds)
            wanted_index = 0

        while self.next_index < wanted_index:
            if self._read_frame_bytes() is None:
                return None
            self.next_index += 1

        data = self._read_frame_bytes()
        if data is None:
            return None

        self.next_index += 1
        return Image.frombytes(mode="RGBA", size=self.dimensions.tuple(), data=data)

    def _open(self, seconds: float):
        self.close()
        cmd = [
            str(self.ffmpeg._path()),
            "-hide_banner",
            "-loglevel", "error",
            "-ss", f"{seconds:.3f}",
            "-i", str(self.filepath),
            "-an",
            "-vf", self._video_filter(),
            "-f", "rawvideo",
            "-pix_fmt", "rgba",
            "-",
        ]
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.next_index = 0

    def _read_frame_bytes(self):
        data = self.process.stdout.read(self.frame_bytes)
        if len(data) != self.frame_bytes:
            self.close()
            return None
        return data

    def _video_filter(self):
        width = self.dimensions.x
        height = self.dimensions.y
        fps = f"fps={self.fps:g}"

        if self.fit == "stretch":
            return f"{fps},scale={width}:{height}"
        if self.fit == "contain":
            return f"{fps},scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black@0"
        return f"{fps},scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"


class Video(Widget):
    def __init__(self, at: Coordinate, entry, start_date, file: Path, dimensions: Dimension,
                 ffmpeg: FFMPEG, offset_seconds: float = 0.0, fps: float = 10.0, fit: str = "cover",
                 opacity: float = 1.0):
        self.at = at
        self.entry = entry
        self.start_date = start_date
        self.offset = timeunits(seconds=offset_seconds)
        self.opacity = opacity
        self.source = VideoFrameSource(ffmpeg=ffmpeg, filepath=file, dimensions=dimensions, fps=fps, fit=fit)

    def draw(self, image: Image.Image, draw: ImageDraw.ImageDraw):
        entry = self.entry()
        if entry is None:
            return

        elapsed = timeunits.from_timedelta(entry.dt - self.start_date) + self.offset
        frame = self.source.frame_at(elapsed.millis() / 1000)
        if frame is None:
            return

        if self.opacity < 1.0:
            alpha = frame.getchannel("A").point(lambda value: int(value * self.opacity))
            frame.putalpha(alpha)

        image.alpha_composite(frame, self.at.tuple())

"""Convert a Playwright .webm into a small animated GIF (ffmpeg two-pass palettegen/paletteuse).

    from video_to_gif import video_to_gif
    video_to_gif("run.webm", "out.gif", start=1.2, end=9.0)        # returns the final size in bytes

Stays under `max_bytes` by trying progressively cheaper settings (fps, width, colors);
raises GifTooLarge instead of writing an oversized file. Requires ffmpeg on PATH.
"""
import os, shutil, subprocess, sys, tempfile

class GifTooLarge(RuntimeError):
    pass

# (fps, max_width, colors): tried in order until the file fits.
LADDER = [(10, 720, 128), (10, 640, 96), (8, 560, 64), (8, 480, 48), (6, 400, 32)]

def _run(args):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args], check=True)

def video_to_gif(src, dst, start=0.0, end=None, max_seconds=20.0, max_bytes=1_500_000, ladder=LADDER):
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found on PATH")
    dur = max_seconds if end is None else min(max_seconds, max(0.5, end - start))
    tmp = tempfile.mkdtemp(prefix="gif-")
    out = os.path.join(tmp, "out.gif")
    try:
        for fps, width, colors in ladder:
            scale = f"fps={fps},scale='min({width},iw)':-2:flags=lanczos"
            pal = os.path.join(tmp, "pal.png")
            seek = ["-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", src]
            _run([*seek, "-vf", f"{scale},palettegen=max_colors={colors}:stats_mode=diff", pal])
            _run([*seek, "-i", pal, "-lavfi", f"{scale}[x];[x][1:v]paletteuse=dither=none:diff_mode=rectangle", "-loop", "0", out])
            if os.path.getsize(out) <= max_bytes:
                shutil.move(out, dst)
                return os.path.getsize(dst)
        raise GifTooLarge(f"{os.path.basename(dst)} is still {os.path.getsize(out)} bytes after the cheapest settings (limit {max_bytes})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("usage: video_to_gif.py in.webm out.gif [start_seconds] [end_seconds]")
    s = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    e = float(sys.argv[4]) if len(sys.argv) > 4 else None
    print(video_to_gif(sys.argv[1], sys.argv[2], start=s, end=e), "bytes")

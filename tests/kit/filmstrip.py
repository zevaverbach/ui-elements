"""Build a contact sheet (filmstrip.png) of key frames from a video, always including the last frame.

    from filmstrip import filmstrip
    filmstrip("run.webm", "filmstrip.png", frames=8)

Agents can usually read a PNG but not an animated GIF, so this is the image form of a recording.
Each frame is labelled with its timestamp. Requires ffmpeg and ffprobe on PATH.
"""
import os, subprocess, sys, tempfile, shutil

def _duration(src):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src],
                         capture_output=True, text=True, check=True).stdout.strip()
    return max(0.1, float(out))

def filmstrip(src, dst, frames=8, start=0.0, end=None, cols=3, width=420):
    frames = max(2, min(9, frames))
    total = _duration(src)
    end = total if end is None else min(end, total)     # never ask for frames past the end of the video
    start = min(start, max(0.0, end - 0.3))
    end = max(end, start + 0.2)
    times = [start + (end - start) * i / (frames - 1) for i in range(frames)]
    times[-1] = max(start, end - 0.08)          # the very last frame, not one past it
    tmp = tempfile.mkdtemp(prefix="strip-")
    try:
        for i, t in enumerate(times):
            label = f"{t:0.1f}s".replace(":", "\\:")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1",
                            "-vf", f"scale={width}:-2,drawtext=text='{label}':x=6:y=6:fontsize=16:fontcolor=white:box=1:boxcolor=black@0.6",
                            os.path.join(tmp, f"f{i:02d}.png")], check=True)
        rows = -(-len(times) // cols)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", "1", "-i", os.path.join(tmp, "f%02d.png"),
                        "-vf", f"tile={cols}x{rows}:padding=4:color=gray", "-frames:v", "1", dst], check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("usage: filmstrip.py in.webm out.png [frames]")
    filmstrip(sys.argv[1], sys.argv[2], frames=int(sys.argv[3]) if len(sys.argv) > 3 else 8)

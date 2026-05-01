#!/usr/bin/env python3
"""Local utility tools server. Run: python3 ~/tools/server.py"""

import base64
import datetime
import glob
import http.server
import json
import os
import re
import subprocess
import tempfile
import threading
import urllib.parse
import webbrowser

PORT = 8787
HOME = os.path.expanduser("~")
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))

# Load save destinations from optional config file. See README for format.
# Defaults to ~/Desktop only if no config is found.
CONFIG_PATH = os.path.join(HOME, ".toolkit-config.json")
DEFAULT_DESTINATIONS = {"desktop": os.path.join(HOME, "Desktop")}


def _load_destinations():
    try:
        with open(CONFIG_PATH, "r") as f:
            cfg = json.load(f)
        dests = cfg.get("save_destinations") or {}
        # expand ~ in user-provided paths
        return {k: os.path.expanduser(v) for k, v in dests.items()} or DEFAULT_DESTINATIONS
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_DESTINATIONS


SAVE_DESTINATIONS = _load_destinations()


def _choose_folder():
    """Open a native macOS folder picker and return the chosen POSIX path, or None."""
    try:
        result = subprocess.run(
            [
                "osascript", "-e",
                'try\n'
                '  set f to choose folder with prompt "Save image to folder:"\n'
                '  return POSIX path of f\n'
                'on error number -128\n'
                '  return ""\n'
                'end try',
            ],
            capture_output=True, text=True, timeout=120,
        )
        path = result.stdout.strip()
        return path or None
    except Exception:
        return None


def _parse_vtt(vtt):
    """Extract clean text from a WebVTT subtitle file, dedup repeated rolling lines."""
    out_lines = []
    prev = ""
    for raw in vtt.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE", "STYLE")):
            continue
        if "-->" in line or re.match(r"^\d+$", line):
            continue
        # strip inline timestamps and tags: <00:00:01.000>, <c>, </c>
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        # dedup rolling captions (youtube auto-captions repeat prior line)
        if line == prev or (prev and line in prev):
            continue
        if prev and prev in line:
            out_lines[-1] = line
        else:
            out_lines.append(line)
        prev = line
    # join into paragraphs every ~8 lines for readability
    paragraphs = []
    for i in range(0, len(out_lines), 8):
        paragraphs.append(" ".join(out_lines[i:i + 8]))
    return "\n\n".join(paragraphs)


class ToolsHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=TOOLS_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        # Serve HTML tools from the tools directory
        if parsed.path == "/teleprompter.html":
            self._serve_file(os.path.join(TOOLS_DIR, "teleprompter.html"))
        elif parsed.path == "/pizza.html":
            self._serve_file(os.path.join(TOOLS_DIR, "pizza.html"))
        elif parsed.path == "/redact.html":
            self._serve_file(os.path.join(TOOLS_DIR, "redact.html"))
        elif parsed.path == "/highlight.html":
            self._serve_file(os.path.join(TOOLS_DIR, "highlight.html"))
        elif parsed.path == "/annotate.html":
            self._serve_file(os.path.join(TOOLS_DIR, "annotate.html"))
        elif parsed.path == "/qrcode.html":
            self._serve_file(os.path.join(TOOLS_DIR, "qrcode.html"))
        elif parsed.path == "/api/destinations":
            # Return configured save destinations as [{key, label}, ...]
            items = [{"key": k, "label": k} for k in SAVE_DESTINATIONS.keys()]
            self._json_response({"destinations": items})
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/download":
            content_len = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_len))
            url = body.get("url", "").strip()

            if not url:
                self._json_response({"error": "No URL provided"}, 400)
                return

            output_dir = body.get("output_dir", os.path.join(HOME, "Downloads"))
            os.makedirs(output_dir, exist_ok=True)

            def run_download():
                try:
                    result = subprocess.run(
                        [
                            "python3", "-m", "yt_dlp",
                            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                            "--merge-output-format", "mp4",
                            "--print", "after_move:filepath",
                            "-o", os.path.join(output_dir, "%(title)s.%(ext)s"),
                            url,
                        ],
                        capture_output=True, text=True, timeout=300,
                    )
                    return result
                except Exception as e:
                    return None

            # Run synchronously (simple enough)
            result = run_download()
            if result and result.returncode == 0:
                filepath = result.stdout.strip().split("\n")[-1]
                filename = os.path.basename(filepath) if filepath else "download complete"
                self._json_response({"success": True, "filename": filename, "path": filepath})
            else:
                err = result.stderr if result else "Download failed"
                self._json_response({"error": str(err)}, 500)
        elif self.path == "/api/save-image":
            content_len = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_len))
            dest_key = body.get("destination", "")
            data_url = body.get("dataUrl", "")
            filename = (body.get("filename") or "").strip()

            if dest_key == "__choose":
                dest_dir = _choose_folder()
                if not dest_dir:
                    self._json_response({"cancelled": True})
                    return
            else:
                dest_dir = SAVE_DESTINATIONS.get(dest_key)
                if not dest_dir:
                    self._json_response({"error": f"Unknown destination: {dest_key}"}, 400)
                    return
            if not data_url.startswith("data:image/"):
                self._json_response({"error": "Invalid image data"}, 400)
                return

            try:
                header, b64 = data_url.split(",", 1)
                ext = "png"
                m = re.match(r"data:image/(\w+)", header)
                if m:
                    ext = m.group(1).lower().replace("jpeg", "jpg")

                if not filename:
                    filename = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S") + f".{ext}"
                else:
                    filename = re.sub(r"[^A-Za-z0-9._-]", "-", filename)
                    if not re.search(r"\.\w{2,5}$", filename):
                        filename += f".{ext}"

                os.makedirs(dest_dir, exist_ok=True)
                full_path = os.path.join(dest_dir, filename)
                with open(full_path, "wb") as f:
                    f.write(base64.b64decode(b64))
                self._json_response({"success": True, "path": full_path, "filename": filename})
            except Exception as e:
                self._json_response({"error": str(e)}, 500)
        elif self.path == "/api/transcript":
            content_len = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_len))
            url = body.get("url", "").strip()

            if not url:
                self._json_response({"error": "No URL provided"}, 400)
                return

            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    result = subprocess.run(
                        [
                            "python3", "-m", "yt_dlp",
                            "--write-auto-subs", "--write-subs",
                            "--sub-langs", "en.*,en",
                            "--sub-format", "vtt",
                            "--skip-download",
                            "--print", "%(title)s",
                            "--print", "%(channel)s",
                            "--print", "%(webpage_url)s",
                            "-o", os.path.join(tmpdir, "%(id)s.%(ext)s"),
                            url,
                        ],
                        capture_output=True, text=True, timeout=120,
                    )
                    if result.returncode != 0:
                        self._json_response({"error": (result.stderr or "yt-dlp failed")[-500:]}, 500)
                        return

                    meta = [line for line in result.stdout.splitlines() if line.strip()]
                    title = meta[0] if len(meta) > 0 else "Transcript"
                    channel = meta[1] if len(meta) > 1 else ""
                    webpage = meta[2] if len(meta) > 2 else url

                    vtt_files = sorted(glob.glob(os.path.join(tmpdir, "*.vtt")))
                    if not vtt_files:
                        self._json_response({"error": "No transcript available for this video"}, 404)
                        return

                    with open(vtt_files[0], "r", encoding="utf-8", errors="ignore") as f:
                        transcript = _parse_vtt(f.read())

                    md = f"# {title}\n\n"
                    if channel:
                        md += f"**Channel:** {channel}  \n"
                    md += f"**Source:** {webpage}\n\n---\n\n{transcript}\n"
                    self._json_response({"success": True, "title": title, "markdown": md})
            except subprocess.TimeoutExpired:
                self._json_response({"error": "Timed out fetching transcript"}, 500)
            except Exception as e:
                self._json_response({"error": str(e)}, 500)
        else:
            self._json_response({"error": "Not found"}, 404)

    def _serve_file(self, filepath):
        try:
            with open(filepath, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404)

    def _json_response(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # quiet


if __name__ == "__main__":
    server = http.server.HTTPServer(("127.0.0.1", PORT), ToolsHandler)
    print(f"Tools running at http://localhost:{PORT}")
    webbrowser.open(f"http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()

# hilary-toolkit

A small local web app that bundles a few one-page utilities I use day to day. Runs entirely on `localhost` — no accounts, no servers, no telemetry.

## The idea

I've been really into the concept of a personal "utility toolkit" — the kind of hyperspecific little apps you Google to see if they exist, start using one, and then realize it's a lead-gen funnel asking for your email so some company can market to you forever. (Just me?)

Instead, I ask Claude Code to make me extremely specific, simple apps that solve papercuts in my day. Each one is a single HTML file. No accounts, no tracking, no SaaS. They live on my laptop and do exactly the thing I need.

To make them easy to get to, I have a `/toolkit` slash command in Claude Code that boots a tiny local server and opens this page in the browser, with every tool one click away. No remembering which file is which.

I'm sharing this as:
1. A look at the kind of things I make (in case it sparks ideas)
2. A starting point for you to fork and add your own. Delete what you don't want, ask Claude to build the tools *you* keep wishing existed.

## What's in it

- **Teleprompter** — scrolling text reader for talking-head video recording
- **Download Video** — saves a video from any URL (YouTube, etc.) via `yt-dlp`
- **YouTube Transcript** — fetches a video's transcript and lets you copy or download it as Markdown
- **Redact** — black out parts of an image
- **Highlight** — highlight passages in an image
- **Annotate** — add markup to an image
- **QR Code** — turn any URL or text into a QR code, copy or download as PNG
- **Pizza Builder** — build a virtual pizza

## Quick install (paste this into Claude Code)

The fastest way to set this up is to hand the whole thing to Claude Code. Paste this into a new Claude Code session:

> Install the toolkit at https://github.com/hilgrid/hilary-toolkit by following its `## Setup instructions for Claude Code` section in the README. Then launch it.

That's it. Claude will read the instructions below, do the install, set up the slash command, and start the server.

## Setup instructions for Claude Code

If you're Claude Code following the prompt above, do these steps in order:

1. **Clone the repo to `~/tools`** (skip if it already exists):
   ```bash
   git clone https://github.com/hilgrid/hilary-toolkit.git ~/tools
   ```
2. **Install `yt-dlp`** (needed for the video downloader and transcript tools):
   ```bash
   pip install yt-dlp
   ```
   If `pip` isn't available, try `pip3` or `python3 -m pip install yt-dlp`.
3. **Create the `/toolkit` slash command** at `~/.claude/commands/toolkit.md` with this exact content:
   ```markdown
   ---
   description: Start the local utility toolkit
   allowed-tools: [Bash]
   ---

   1. Check if the server is already running on port 8787 (`lsof -ti:8787`). If so, open `http://localhost:8787` in the browser.
   2. If not, start it in the background: `nohup python3 ~/tools/server.py > /tmp/toolkit.log 2>&1 &`
   3. Open `http://localhost:8787`.
   4. Confirm with a one-liner like "Toolkit is open."
   ```
4. **(Optional)** Ask the user if they want to set up named save destinations for the image tools. If yes, create `~/.toolkit-config.json` in the format shown in the "Configure save destinations" section below.
5. **Start the server** in the background and open the browser:
   ```bash
   nohup python3 ~/tools/server.py > /tmp/toolkit.log 2>&1 &
   sleep 1 && open http://localhost:8787
   ```
6. **Tell the user**: the toolkit is installed, the `/toolkit` slash command is wired up, and the app is open in their browser. From now on they can just type `/toolkit` to launch it.

## Manual install

If you'd rather do it yourself:

```bash
pip install yt-dlp
git clone https://github.com/hilgrid/hilary-toolkit.git ~/tools
python3 ~/tools/server.py
```

It opens `http://localhost:8787` in your browser.

## Configure save destinations (optional)

The image tools (redact / highlight / annotate) can save directly to named folders. Create `~/.toolkit-config.json`:

```json
{
  "save_destinations": {
    "blog": "~/Sites/myblog/images",
    "desktop": "~/Desktop"
  }
}
```

If no config file exists, it defaults to `~/Desktop`.

## The `/toolkit` slash command (optional)

If you use Claude Code, drop this in `~/.claude/commands/toolkit.md` and you can launch the whole thing by typing `/toolkit`:

```markdown
---
description: Start the local utility toolkit
allowed-tools: [Bash]
---

1. Check if the server is already running on port 8787. If so, open `http://localhost:8787` in the browser.
2. If not, start it in the background: `python3 ~/tools/server.py &`
3. Confirm with a one-liner like "Toolkit is open."
```

## Adding your own tools

Each tool is a single HTML file in this directory. To add one:

1. Ask Claude (or write yourself) a self-contained `mytool.html`. Drop it in the repo root.
2. Add a button for it in `index.html` (copy one of the existing `<button class="tool-btn" data-tool="...">` lines).
3. If your tool needs to talk to the file system or call an external CLI, add a route in `server.py`. Otherwise it'll just work as a static page.

Reload `localhost:8787` and you're done.

## License

MIT

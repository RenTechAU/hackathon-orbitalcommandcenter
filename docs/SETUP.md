# Setup

## 0. It already runs

```bash
cd code
python3 src/main.py
```

Zero SDKs, zero keys, zero internet. You should see two conflicts resolve
differently. **If that works, you have a demo.** Everything below is upgrading
it, not building it.

## 1. Point Claude Code at this folder

```bash
cd code
claude
```

It reads `CLAUDE.md` automatically — that file tells it the architecture, the
constraints, and critically that it must **not invent SDK syntax** for the three
new vendor tools. Keep it updated as things change; it's the project's memory.

Useful first prompts:

- `read CLAUDE.md and docs/SDK_NOTES.md, then tell me what's not wired yet`
- `wire FalkorDB using the snippet in SDK_NOTES.md, keep the fallback working`
- `run src/main.py and confirm both conflicts still resolve differently`

## 2. Python env

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Keys

```bash
cp .env.example .env
```

Fill it in as you collect keys from the sponsor tables. Never commit `.env`.

## 4. FalkorDB — do this one first

Easiest path is Docker:

```bash
docker run -p 6379:6379 -p 3000:3000 -it --rm falkordb/falkordb:latest
```

Browser UI at http://localhost:3000 — **leave this open all day.** It's the
most photogenic artifact you'll produce and it goes straight in the demo.

Then:

```bash
export FALKOR_HOST=localhost FALKOR_PORT=6379
python3 src/main.py
```

The Cypher is already written in `src/memory/graph.py`. It should just work.

## 5. Everything else

One adapter at a time, in this order: LaserData → RocketRide → Guild.ai.
Run `src/main.py` after each. If a swap breaks the demo, flip `use_real=False`
and move on — a working fallback beats a broken integration at 6 PM.

## Git

```bash
git init && git add -A && git commit -m "walking skeleton green"
```

Commit hourly. Laptops die at hackathons.

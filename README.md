# trello_journal_migration

Migrate journal entries from Trello cards to Day One.

Fetches cards from a Trello board via the API, downloads all attachments, and produces a Day One-compatible `.zip` file (with embedded photos) that you can import via the web app, desktop, or mobile.

## Setup

Requires Python 3.12+.

```bash
pip install -r requirements.txt
cp config.example.json config.json
```

Edit `config.json` with your credentials:

- **trello.apiKey** — get from https://trello.com/power-ups/admin (API Key section)
- **trello.apiToken** — generate a token from the same page
- **trello.boardId** — the board ID from your Trello board URL (e.g., `https://trello.com/b/BOARD_ID/...`)

## Usage

```bash
# Preview what will be migrated (no file written)
python -m trello_journal_migration --dry-run

# Run the migration — downloads attachments and produces a zip
python -m trello_journal_migration

# Custom config or output directory
python -m trello_journal_migration --config my_config.json --output-dir my_output
```

Output is written to `output/Journal.zip` — a self-contained zip with the JSON and all attachment files embedded.

### Docker

```bash
# Build the image
docker build -t trello-journal-migration .

# Dry run — mount your config file in
docker run --rm \
  -v $(pwd)/config.json:/app/config.json:ro \
  trello-journal-migration --dry-run

# Run migration — mount config in and output directory out
docker run --rm \
  -v $(pwd)/config.json:/app/config.json:ro \
  -v $(pwd)/output:/app/output \
  trello-journal-migration
```

The output file will appear at `output/Journal.zip` on your host.

### Import via web app, desktop, or mobile

The default output is `output/Journal.zip` — a self-contained zip with `Journal.json` and a `photos/` folder containing all downloaded attachments. This matches Day One's native export format.

To import:

1. Run `python -m trello_journal_migration`
2. Go to [dayone.me](https://dayone.me) → Settings → Import, **or** use the Day One app (iOS/Android/Mac) → Settings → Import/Export
3. Select `output/Journal.zip`

Attachments are fully embedded in the zip and will appear inline in your journal entries.

## Configuration

| Field | Description |
|---|---|
| `trello.boardId` | Trello board to migrate from |
| `dayone.journalName` | Target Day One journal name (default: `"Journal"`) |
| `options.includeArchived` | Include archived/closed cards and lists (default: `false`) |
| `options.includeAttachments` | Append attachment links to entries (default: `true`) |
| `options.listFilter` | Array of list names to include. Empty = all lists. |

## How cards map to entries

| Trello | Day One |
|---|---|
| Card name | Entry title (H1 heading) |
| Card description | Entry body (markdown) |
| Due date (or last activity) | Creation date |
| Last activity date | Modified date |
| Labels + list name | Tags |
| Attachments | Downloaded and embedded in the import zip as photos |

## Project structure

```
trello_journal_migration/
  __main__.py    — CLI entry point
  trello.py      — Trello API client
  transform.py   — Card → Day One entry mapping
  dayone.py      — Day One JSON builder, file writer, and CLI importer
```
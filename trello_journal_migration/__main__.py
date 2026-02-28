"""
CLI entry point for Trello -> Day One migration.

Usage:
    python -m trello_journal_migration                        # produce Journal.zip
    python -m trello_journal_migration --dry-run              # preview without writing
    python -m trello_journal_migration --config other.json
"""

import argparse
import json
import os
import sys

from .trello import TrelloClient
from .transform import transform_cards
from .dayone import write_dayone_zip


def load_config(path: str) -> dict:
    """Load and parse the JSON config file."""
    try:
        with open(path, encoding="utf-8") as config_file:
            return json.load(config_file)
    except FileNotFoundError:
        print(f"Config file not found: {path}", file=sys.stderr)
        print("Copy config.example.json to config.json and fill in your credentials.", file=sys.stderr)
        sys.exit(1)


def download_attachments(client: TrelloClient, cards: list, download_dir: str) -> int:
    """
    Download all attachments from the given cards into download_dir.

    Each card's attachments get saved to a subfolder named after the card ID.
    The attachment dicts on each card are updated in-place with a "local_path"
    key pointing to the downloaded file.

    Returns the total number of files downloaded.
    """
    total_downloaded = 0

    for card in cards:
        attachments = card.get("attachments") or []
        if not attachments:
            continue

        card_folder = os.path.join(download_dir, card["id"])

        for attachment in attachments:
            url = attachment.get("url")
            if not url:
                continue

            filename = attachment.get("name") or os.path.basename(url)
            save_path = os.path.join(card_folder, filename)

            try:
                client.download_attachment(url, save_path)
                attachment["local_path"] = save_path
                total_downloaded += 1
                print(f"  Downloaded: {filename}")
            except Exception as err:
                print(f"  Failed to download {filename}: {err}")

    return total_downloaded


def main() -> None:
    # -- Parse command-line arguments --
    parser = argparse.ArgumentParser(
        description="Migrate Trello cards to Day One journal entries"
    )
    parser.add_argument("--config", default="config.json", help="Path to config file")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing output")
    parser.add_argument("--output-dir", default="output", help="Output directory")
    args = parser.parse_args()

    # -- Load config --
    config = load_config(args.config)
    trello_config = config["trello"]
    dayone_config = config.get("dayone", {})
    options = config.get("options", {})

    # -- Fetch cards from Trello --
    board_id = trello_config["boardId"]
    print(f"Connecting to Trello board: {board_id}")

    client = TrelloClient(
        api_key=trello_config["apiKey"],
        api_token=trello_config["apiToken"],
    )

    board = client.get_board(board_id)
    print(f'Board: "{board["name"]}"')

    lists, cards = client.get_all_cards_on_board(
        board_id,
        include_archived=options.get("includeArchived", False),
    )
    print(f"Found {len(lists)} lists, {len(cards)} cards")

    # -- Download attachments --
    include_attachments = options.get("includeAttachments", True)
    if include_attachments:
        download_dir = os.path.join(args.output_dir, "attachments")
        print(f"\nDownloading attachments to: {download_dir}")
        downloaded_count = download_attachments(client, cards, download_dir)
        print(f"Downloaded {downloaded_count} attachment(s)")

    # -- Transform cards into Day One entries --
    journal_name = dayone_config.get("journalName", "Journal")

    entries = transform_cards(
        cards,
        list_filter=options.get("listFilter", []),
        journal_name=journal_name,
        include_attachments=include_attachments,
    )
    print(f"\nTransformed {len(entries)} entries for Day One")

    # -- Dry run: just print a summary and exit --
    if args.dry_run:
        print("\n--- DRY RUN ---")
        print(f"Would create {len(entries)} Day One entries.")
        attachment_count = sum(len(e.get("attachment_paths", [])) for e in entries)
        print(f"Total attachments: {attachment_count}")
        if entries:
            print("\nSample entry:")
            print(json.dumps(entries[0], indent=2))
        return

    # -- Write the Day One import zip --
    zip_path = write_dayone_zip(entries, output_dir=args.output_dir)

    print(f"\nDay One import zip written to: {zip_path}")
    print("\nTo import into Day One:")
    print("  1. Go to dayone.me (web app) or open Day One on iOS/Android/Mac")
    print("  2. Settings -> Import (web) or File -> Import (desktop/mobile)")
    print(f"  3. Select {zip_path}")


if __name__ == "__main__":
    main()

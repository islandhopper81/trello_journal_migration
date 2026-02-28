"""
Transforms Trello cards into Day One entry objects.

Mapping:
    card name        -> entry title (markdown H1)
    card desc        -> entry body (markdown)
    card due or dateLastActivity -> entry creationDate
    card dateLastActivity -> entry modifiedDate
    card labels      -> entry tags
    card listName    -> additional tag
    card attachments -> downloaded files, embedded via dayone-moment:// refs

Attachment handling:
    Downloaded attachments get a numbered placeholder in the entry text
    (e.g. {{ATTACHMENT_0}}, {{ATTACHMENT_1}}). The dayone.write_dayone_zip()
    function replaces these with real dayone-moment://<identifier> references
    when it builds the photos array and knows the identifiers.
"""

from datetime import datetime, timezone
from typing import Optional

from .dayone import create_entry

# Placeholder format used in entry text, replaced during zip packaging
ATTACHMENT_PLACEHOLDER = "{{ATTACHMENT_%d}}"


def parse_trello_date(date_string: Optional[str]) -> str:
    """
    Convert a Trello date string to ISO 8601 format.
    Returns the current time if the input is missing or unparseable.
    """
    if not date_string:
        return datetime.now(timezone.utc).isoformat()

    # Trello uses ISO 8601 with "Z" suffix — normalize to "+00:00" for fromisoformat()
    try:
        parsed = datetime.fromisoformat(date_string.replace("Z", "+00:00"))
        return parsed.isoformat()
    except ValueError:
        return datetime.now(timezone.utc).isoformat()


def build_entry_body(card: dict, include_attachments: bool = True) -> str:
    """
    Build the markdown text for a Day One entry from a Trello card.

    Downloaded attachments get numbered placeholders that will be replaced
    with dayone-moment:// references during zip packaging. Attachments that
    weren't downloaded are listed as regular markdown links.
    """
    lines = []

    # Title
    lines.append(f"# {card['name']}")
    lines.append("")

    # Description
    description = (card.get("desc") or "").strip()
    if description:
        lines.append(description)
        lines.append("")

    # Attachments
    attachments = card.get("attachments") or []
    if include_attachments and attachments:
        downloaded = [a for a in attachments if a.get("local_path")]
        not_downloaded = [a for a in attachments if not a.get("local_path")]

        # Numbered placeholders for downloaded files
        for index, _attachment in enumerate(downloaded):
            placeholder = ATTACHMENT_PLACEHOLDER % index
            lines.append(f"![]({placeholder})")
            lines.append("")

        # Markdown links for anything that wasn't downloaded
        if not_downloaded:
            lines.append("## Other Attachments")
            lines.append("")
            for attachment in not_downloaded:
                display_name = attachment.get("name") or attachment.get("url", "link")
                url = attachment["url"]
                lines.append(f"- [{display_name}]({url})")
            lines.append("")

    return "\n".join(lines)


def collect_tags(card: dict) -> list:
    """
    Gather tags from a Trello card.
    Uses the list name as the first tag, then each label name.
    """
    tags = []

    list_name = card.get("listName")
    if list_name:
        tags.append(list_name)

    labels = card.get("labels") or []
    for label in labels:
        if label.get("name"):
            tags.append(label["name"])

    return tags


def card_to_entry(
    card: dict,
    journal_name: str = "Journal",
    include_attachments: bool = True,
) -> dict:
    """
    Convert a single Trello card to a Day One entry.

    The returned dict includes an extra "attachment_paths" key (list of local
    file paths) used during zip packaging and CLI import. This key is stripped
    from the final Day One JSON output.
    """
    body = build_entry_body(card, include_attachments=include_attachments)
    tags = collect_tags(card)

    # Prefer the due date for creation; fall back to last activity
    raw_creation_date = card.get("due") or card.get("dateLastActivity")
    creation_date = parse_trello_date(raw_creation_date)
    modified_date = parse_trello_date(card.get("dateLastActivity"))

    # Collect local paths of downloaded attachments (in order matching placeholders)
    attachment_paths = []
    if include_attachments:
        for attachment in card.get("attachments") or []:
            local_path = attachment.get("local_path")
            if local_path:
                attachment_paths.append(local_path)

    entry = create_entry(
        text=body,
        creation_date=creation_date,
        modified_date=modified_date,
        tags=tags,
        starred=False,
        journal=journal_name,
    )
    entry["attachment_paths"] = attachment_paths
    return entry


def transform_cards(
    cards: list,
    list_filter: Optional[list] = None,
    journal_name: str = "Journal",
    include_attachments: bool = True,
) -> list:
    """
    Transform a list of Trello cards into Day One entries.

    If list_filter is provided, only cards from those list names are included
    (case-insensitive match).
    """
    cards_to_convert = cards

    if list_filter:
        allowed_lists = {name.lower() for name in list_filter}
        cards_to_convert = [
            card for card in cards
            if card.get("listName", "").lower() in allowed_lists
        ]

    return [
        card_to_entry(card, journal_name=journal_name, include_attachments=include_attachments)
        for card in cards_to_convert
    ]

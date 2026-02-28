"""
Builds Day One-compatible import zip files with embedded attachments.

Day One's import format (used by the web app, iOS, macOS, Android) is a
.zip file containing:

    Journal.json          — entries with a "photos" array referencing files
    photos/
      <md5hash>.jpeg      — attachment files named by their MD5 hash

Each entry references its photos via:
    - A "photos" list with "md5", "identifier", and "type" fields
    - ![](dayone-moment://<identifier>) markdown in the entry text

"""

import hashlib
import json
import os
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Optional


def create_entry(
    text: str,
    creation_date: Optional[str] = None,
    modified_date: Optional[str] = None,
    tags: Optional[list] = None,
    starred: bool = False,
    journal: str = "Journal",
) -> dict:
    """Create a single Day One entry object."""
    right_now = datetime.now(timezone.utc).isoformat()

    return {
        "uuid": uuid.uuid4().hex.upper(),
        "creationDate": creation_date if creation_date else right_now,
        "modifiedDate": modified_date if modified_date else right_now,
        "text": text,
        "tags": tags if tags else [],
        "starred": starred,
        "journal": journal,
    }


def md5_of_file(file_path: str) -> str:
    """Compute the MD5 hex digest of a file."""
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def file_extension(file_path: str) -> str:
    """Get the lowercase file extension without the dot (e.g. 'jpeg', 'png')."""
    ext = os.path.splitext(file_path)[1].lstrip(".").lower()
    # Normalize common variants
    if ext == "jpg":
        return "jpeg"
    return ext


def build_dayone_json(entries: list) -> dict:
    """
    Wrap a list of entries in the Day One import envelope.

    Strips out internal keys (attachment_paths, attachment_photos) that
    aren't part of the Day One JSON spec.
    """
    internal_keys = {"attachment_paths", "attachment_photos"}

    cleaned_entries = []
    for entry in entries:
        clean = {k: v for k, v in entry.items() if k not in internal_keys}
        cleaned_entries.append(clean)

    return {
        "metadata": {"version": "1.0"},
        "entries": cleaned_entries,
    }


def write_dayone_zip(
    entries: list,
    output_dir: str = "output",
    filename: str = "Journal.zip",
) -> str:
    """
    Package entries and their downloaded attachments into a Day One
    import zip file.

    The zip contains:
        Journal.json        — the entries JSON with photos arrays
        photos/<md5>.<ext>  — each attachment file, named by MD5 hash

    This function also replaces {{ATTACHMENT_N}} placeholders in each
    entry's text with the real dayone-moment://<identifier> references.

    Returns the path to the zip file.
    """
    os.makedirs(output_dir, exist_ok=True)
    zip_path = os.path.join(output_dir, filename)

    # photo_files caches local_path -> (md5, ext) to avoid re-hashing
    photo_files = {}

    for entry in entries:
        photos_list = []
        attachment_paths = entry.get("attachment_paths") or []

        for index, local_path in enumerate(attachment_paths):
            if not os.path.isfile(local_path):
                print(f"  Warning: attachment not found, skipping: {local_path}")
                continue

            # Compute MD5 once per unique file
            if local_path not in photo_files:
                md5 = md5_of_file(local_path)
                ext = file_extension(local_path)
                photo_files[local_path] = (md5, ext)

            md5, ext = photo_files[local_path]
            identifier = uuid.uuid4().hex.upper()

            photos_list.append({
                "md5": md5,
                "identifier": identifier,
                "type": ext,
                "orderInEntry": index,
            })

            # Replace the numbered placeholder with the real Day One reference
            placeholder = "{{ATTACHMENT_%d}}" % index
            moment_ref = f"dayone-moment://{identifier}"
            entry["text"] = entry["text"].replace(placeholder, moment_ref)

        entry["photos"] = photos_list

    # Build the JSON payload (strips internal keys like attachment_paths)
    dayone_json = build_dayone_json(entries)

    # Write the zip
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        json_bytes = json.dumps(dayone_json, indent=2, ensure_ascii=False).encode("utf-8")
        zf.writestr("Journal.json", json_bytes)

        # Add each unique attachment file into the photos/ folder
        added_md5s = set()
        for local_path, (md5, ext) in photo_files.items():
            if md5 in added_md5s:
                continue
            archive_name = f"photos/{md5}.{ext}"
            zf.write(local_path, archive_name)
            added_md5s.add(md5)

    return zip_path


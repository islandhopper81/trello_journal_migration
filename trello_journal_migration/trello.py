"""Trello API client for fetching board data and downloading attachments."""

import os
from typing import Optional
from urllib.parse import urlparse

import requests

BASE_URL = "https://api.trello.com/1"


class TrelloClient:
    def __init__(self, api_key: str, api_token: str):
        if not api_key or not api_token:
            raise ValueError("Trello api_key and api_token are required")
        self._auth_params = {"key": api_key, "token": api_token}

    def _get(self, path: str, query_params: Optional[dict] = None):
        """Make an authenticated GET request to the Trello API."""
        # Merge any caller-provided params with the auth credentials
        params = dict(query_params) if query_params else {}
        params.update(self._auth_params)

        response = requests.get(f"{BASE_URL}{path}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_board(self, board_id: str) -> dict:
        """Get board metadata (name, description, url)."""
        return self._get(f"/boards/{board_id}", {"fields": "name,desc,url"})

    def get_lists(self, board_id: str, include_archived: bool = False) -> list:
        """Get all lists on a board."""
        card_filter = "all" if include_archived else "open"
        return self._get(f"/boards/{board_id}/lists", {"filter": card_filter})

    def get_cards(self, list_id: str, include_archived: bool = False) -> list:
        """Get all cards in a list, including their attachments and labels."""
        card_filter = "all" if include_archived else "open"
        return self._get(
            f"/lists/{list_id}/cards",
            {
                "filter": card_filter,
                "fields": "name,desc,dateLastActivity,due,labels,closed",
                "attachments": "true",
                "attachment_fields": "name,url,mimeType,date",
            },
        )

    def get_card_comments(self, board_id: str) -> dict:
        """
        Fetch all comment actions for a board in one request.

        Returns a dict mapping card_id -> list of comment actions,
        sorted oldest-first.
        """
        actions = self._get(
            f"/boards/{board_id}/actions",
            {"filter": "commentCard", "fields": "type,data,date", "limit": 1000},
        )
        comments_by_card = {}
        for action in actions:
            card_id = (action.get("data") or {}).get("card", {}).get("id")
            if card_id:
                comments_by_card.setdefault(card_id, []).append(action)
        for comments in comments_by_card.values():
            comments.sort(key=lambda a: a.get("date", ""))
        return comments_by_card

    def get_all_cards_on_board(self, board_id: str, include_archived: bool = False):
        """
        Fetch every card across every list on a board.

        Returns a tuple of (lists, cards). Each card dict gets two extra
        fields added: "listName" and "listId" so you know which list it
        came from.
        """
        lists = self.get_lists(board_id, include_archived=include_archived)
        comments_by_card = self.get_card_comments(board_id)
        all_cards = []

        for trello_list in lists:
            cards = self.get_cards(trello_list["id"], include_archived=include_archived)

            for card in cards:
                card["listName"] = trello_list["name"]
                card["listId"] = trello_list["id"]
                card["actions"] = comments_by_card.get(card["id"], [])
                all_cards.append(card)

        return lists, all_cards

    def download_attachment(self, url: str, save_to: str) -> str:
        """
        Download a Trello attachment file to a local path.

        Trello attachment URLs require auth for private boards, so we
        pass credentials as query params.

        Returns the path the file was saved to.
        """
        os.makedirs(os.path.dirname(save_to), exist_ok=True)

        # Trello-hosted URLs require auth via Authorization header; S3/CDN
        # pre-signed URLs already embed credentials and don't need extra headers.
        parsed = urlparse(url)
        headers = {}
        if parsed.netloc.endswith("trello.com"):
            key = self._auth_params["key"]
            token = self._auth_params["token"]
            headers["Authorization"] = f'OAuth oauth_consumer_key="{key}", oauth_token="{token}"'

        response = requests.get(url, headers=headers, timeout=60, stream=True)
        response.raise_for_status()

        with open(save_to, "wb") as download_file:
            for chunk in response.iter_content(chunk_size=8192):
                download_file.write(chunk)

        return save_to

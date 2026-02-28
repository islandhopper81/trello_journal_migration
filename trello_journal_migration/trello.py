"""Trello API client for fetching board data and downloading attachments."""

import os
from typing import Optional

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

    def get_all_cards_on_board(self, board_id: str, include_archived: bool = False):
        """
        Fetch every card across every list on a board.

        Returns a tuple of (lists, cards). Each card dict gets two extra
        fields added: "listName" and "listId" so you know which list it
        came from.
        """
        lists = self.get_lists(board_id, include_archived=include_archived)
        all_cards = []

        for trello_list in lists:
            cards = self.get_cards(trello_list["id"], include_archived=include_archived)

            for card in cards:
                card["listName"] = trello_list["name"]
                card["listId"] = trello_list["id"]
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

        response = requests.get(url, params=self._auth_params, timeout=60, stream=True)
        response.raise_for_status()

        with open(save_to, "wb") as download_file:
            for chunk in response.iter_content(chunk_size=8192):
                download_file.write(chunk)

        return save_to

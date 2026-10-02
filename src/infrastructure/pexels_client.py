from __future__ import annotations

from pathlib import Path

import requests


class PexelsPhoto:
    def __init__(self, data: dict) -> None:
        self.id: int = data["id"]
        self.width: int = data["width"]
        self.height: int = data["height"]
        self.photographer: str = data["photographer"]
        self.url_original: str = data["src"]["original"]
        self.url_large: str = data["src"]["large2x"]
        self.url_medium: str = data["src"]["medium"]
        self.url_tiny: str = data["src"]["tiny"]
        self.alt: str = data.get("alt", "")


class PexelsClient:
    _BASE = "https://api.pexels.com/v1"

    def __init__(self, api_key: str) -> None:
        self._session = requests.Session()
        self._session.headers.update({"Authorization": api_key})

    def get_photo(self, photo_id: int) -> PexelsPhoto:
        """Fetch a single photo by ID."""
        r = self._session.get(f"{self._BASE}/photos/{photo_id}", timeout=10)
        r.raise_for_status()
        return PexelsPhoto(r.json())

    def search(self, query: str, per_page: int = 5, orientation: str = "portrait") -> list[PexelsPhoto]:
        """Search Pexels and return up to per_page results."""
        r = self._session.get(
            f"{self._BASE}/search",
            params={"query": query, "per_page": per_page, "orientation": orientation},
            timeout=10,
        )
        r.raise_for_status()
        return [PexelsPhoto(p) for p in r.json().get("photos", [])]

    def download(self, photo: PexelsPhoto, dest: Path, size: str = "large") -> Path:
        """
        Download a photo to dest. size: 'original' | 'large' | 'medium'.
        Returns the path written.
        """
        url_map = {
            "original": photo.url_original,
            "large": photo.url_large,
            "medium": photo.url_medium,
        }
        url = url_map.get(size, photo.url_large)
        dest.parent.mkdir(parents=True, exist_ok=True)
        r = self._session.get(url, timeout=30, stream=True)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return dest

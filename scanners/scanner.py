from abc import ABC, abstractmethod
from datetime import datetime
from typing import List


class App:
    def __init__(
            self, 
            name: str,
            desc: str, 
            urls: List[str],
            scanner: str, 
            has_downloads: bool = True,
            last_updated: datetime = None,
        ):
        self.name = name
        self.desc = desc
        self.urls = urls
        self.scanner = scanner
        self.has_downloads = has_downloads
        self.last_updated = last_updated

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return self.name == other.name

    def __repr__(self):
        return str(self.name)


class Apps:
    def __init__(self, apps: List):
        self.apps = apps


class Scanner(ABC):

    @abstractmethod
    def find_matching_apps(self):
        pass

from abc import ABC, abstractmethod
from typing import List


class App:
    def __init__(self, name: str, desc: str, urls: List[str], scanner: str):
        self.name = name
        self.desc = desc
        self.urls = urls
        self.scanner = scanner

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

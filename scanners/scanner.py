from abc import ABC, abstractmethod
from typing import List


class App:
    def __init__(self, name: str, desc: str, urls: List[str], scanner: str, score: float = 0):
        assert 0 <= score <= 100, "Score must be between 0 and 100"
        self.name = name
        self.desc = desc
        self.urls = urls
        self.scanner = scanner
        self.score = score

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

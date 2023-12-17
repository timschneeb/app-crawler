from abc import ABC, abstractmethod


class App:
    def __init__(self, name, desc, urls, scanner_type):
        self.name = name
        self.desc = desc
        self.urls = urls
        self.scanner = scanner_type.__name__

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return self.name == other.name

    def __repr__(self):
        return str(self.name)


class Scanner(ABC):

    @abstractmethod
    def find_matching_apps(self):
        pass

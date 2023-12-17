from abc import ABC, abstractmethod


class App:
    def __init__(self, name, urls, scannerType):
        self.name = name
        self.urls = urls
        self.scanner = scannerType.__name__

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

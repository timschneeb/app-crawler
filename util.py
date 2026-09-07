import datetime
import glob
import os
from typing import List, Optional


def flatten(xss):
    return [x for xs in xss for x in xs]

def is_known_app(name, urls):
    readme = ""
    for path in readme_paths:
        with open(path) as file:
            readme += file.read().lower() + "\n"

    has_url = any(url.replace("https://", "").lower() in readme for url in urls)
    has_name = ('[' + name.lower() + ']') in readme
    return has_url or has_name

def filter_known_apps(apps, additional_excludes=None):
    if additional_excludes is None:
        additional_excludes = []

    readme = ""
    for path in readme_paths:
        with open(path) as file:
            readme += file.read().lower() + "\n"

    def filter_app(app):
        has_url = any(url.replace("https://", "").lower() in readme for url in app.urls)
        has_name = ('[' + app.name.lower() + ']') in readme
        is_excluded = app in additional_excludes
        # if not (has_url or has_name or is_excluded):
        #     print(app.name + " " + str(app.urls))
        return not (has_url or has_name or is_excluded)

    return list(filter(filter_app, apps))

def is_ignored(item):
    return item in ignore_list

def make_aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)

readme_paths = [] # Set by main.py

def _load_ignore_list() -> List[str]:
    base_dir = os.path.dirname(os.path.realpath(__file__))
    ignore_dir = os.path.join(base_dir, "ignore")
    paths = sorted(glob.glob(os.path.join(ignore_dir, "*.lst")))

    # Backward compatibility: also load the legacy single list file if present
    legacy_path = os.path.join(base_dir, "ignore_list.lst")
    if os.path.isfile(legacy_path) and legacy_path not in paths:
        paths.append(legacy_path)

    entries: List[str] = []
    seen = set()
    for path in paths:
        with open(path, 'r') as f:
            for line in f:
                entry = line.strip()
                if not entry or entry.startswith("#"):
                    continue
                if entry not in seen:
                    seen.add(entry)
                    entries.append(entry)
    return entries

ignore_list: List[str] = _load_ignore_list()

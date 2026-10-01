import itertools
import multiprocessing as mp
import os
from datetime import datetime

import requests
from tqdm import tqdm

import util
from .github_meta_scanner import GithubMetaScanner
from .scanner import App


class ShizukuModulesScanner(GithubMetaScanner):
    """Scans the community-maintained rushiranpise/shizuku-modules repo index.

    The upstream list may contain repositories that only mention Shizuku in their
    readme or description, so every candidate is cloned and checked for the strict
    Shizuku import marker, just like GithubMetaScanner. Repositories already cloned
    by GithubMetaScanner in the current run are skipped entirely.
    """

    log_prefix = "shizuku_modules"
    source_url = "https://raw.githubusercontent.com/rushiranpise/shizuku-modules/main/data/repos.json"

    def _parse_datetime(self, value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _fetch_entries(self):
        try:
            response = requests.get(self.source_url, timeout=30)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as e:
            print(f"{self.log_prefix}: failed to fetch {self.source_url}: {e}")
            return []

    def find_matching_apps(self):
        entries = self._fetch_entries()
        print(f"{self.log_prefix}: found {len(entries)} repos")

        excluded_urls = util.flatten([x.urls for x in self.exclude])

        full_results = []
        for entry in tqdm(entries, total=len(entries)):
            url = entry.get("html_url")
            full_name = entry.get("full_name") or ""

            if not isinstance(url, str) or not url.startswith("https://github.com/"):
                continue
            if entry.get("archived"):
                continue

            name = full_name.split("/")[-1] if "/" in full_name else url.rstrip("/").split("/")[-1]
            if (url in excluded_urls or
                    util.is_known_app(name, [url]) or
                    util.is_ignored(name) or util.is_ignored(url)):
                continue

            full_results.append(App(
                name,
                entry.get("description"),
                [url],
                type(self).__name__,
                bool(entry.get("release")),
                self._parse_datetime(entry.get("pushed_at")),
                is_original_content=True,
                popularity=entry.get("stargazers_count") or 0,
            ))

        filtered_results = util.filter_known_apps(full_results, self.exclude)

        # No stale clone cleanup here: it would delete GithubMetaScanner's freshly
        # cloned repositories. Its cleanup pass handles stale dirs on the next run.
        pool = mp.Pool(self.process_count, maxtasksperchild=1)
        apps = []
        apps.extend(pool.map(self.check_repo, filtered_results))
        pool.close()

        return list(itertools.chain.from_iterable(apps))

    def check_repo(self, args: App):
        # GithubMetaScanner runs before this scanner and has already fetched and
        # strict-grepped every repo left in the shared clone cache this run.
        if os.path.exists(os.path.join(self.clones_dir, self._repo_id(args.urls[0]))):
            return []
        return super().check_repo(args)

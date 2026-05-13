import argparse
import glob
import os
from datetime import datetime, timezone
from operator import attrgetter
from typing import List, Optional

import util
from cache import Cache
from report import write_report, write_sorted_reports
from scanners.scanner import App
from scanners.fdroid_scanner import FDroidScanner
from scanners.github_code_scanner import GithubCodeScanner
from scanners.github_meta_scanner import GithubMetaScanner


def scan_apps(github_auth: Optional[str]) -> List[App]:
    """Run all configured scanners and return a deduplicated, name-sorted list of apps.

    If `github_auth` is false the GitHub scanners are skipped. Raise a TypeError if a scanner
    returns something that is not an `App` instance so later code can safely use direct attribute access.
    """
    apps: List[App] = []
    apps.extend(FDroidScanner("https://f-droid.org/repo/index.xml").find_matching_apps())
    apps.extend(FDroidScanner("https://apt.izzysoft.de/fdroid/repo/index.xml").find_matching_apps())

    if github_auth:
        apps.extend(GithubCodeScanner(github_auth, exclude=apps, process_count=4).find_matching_apps())
        apps.extend(GithubMetaScanner(github_auth, exclude=apps, process_count=4).find_matching_apps())
    return sorted(set(apps), key=attrgetter('name'))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("targetPath")
    parser.add_argument('-o', "--offline", action='store_true', help="Offline mode; skip scan")
    args = parser.parse_args()

    github_auth = os.getenv("GITHUB_AUTH")
    if not args.offline and not github_auth:
        print("warning: GITHUB_AUTH env variable not set; skipping GitHub scanners")
        github_auth = None

    path = args.targetPath
    util.readme_paths = (
        glob.glob(path + '/*.md')
        + glob.glob(path + '/pages/UNLISTED.md')
        + glob.glob(path + '/pages/CLOSED_SOURCE.md')
    )

    report_path = os.path.join(os.getcwd(), "SUMMARY.md")
    sorted_report_path = os.path.join(os.getcwd(), "SUMMARY_SORTED.md")

    cache_dir = os.path.join(os.getcwd(), "cache")
    os.makedirs(cache_dir, exist_ok=True)

    cache = Cache(cache_dir)
    cached_apps = cache.load_all()

    def remove_ignored_entries(a: App) -> bool:
        return not (a.name in util.ignore_list or any(url in util.ignore_list for url in a.urls))

    apps: List[App] = []
    if not args.offline:
        # Run scanners and get current-run apps
        apps = util.filter_known_apps(scan_apps(github_auth))
        apps = list(filter(remove_ignored_entries, apps))

        # Ensure each app discovered in this run has a first_seen timestamp set to now (UTC)
        now = datetime.now(timezone.utc)
        for a in apps:
            if a.first_seen is None:
                a.first_seen = now

        # Save current run to cache
        cache.save_current_run(apps)
        print()

    # Merge duplicates by name, preserving the earliest first_seen date
    merged = {c.name: c for c in cached_apps}

    def _earliest(a_dt, b_dt):
        # Return the earliest non-None datetime, or None if both None
        if a_dt is None:
            return b_dt
        if b_dt is None:
            return a_dt
        return a_dt if a_dt <= b_dt else b_dt

    for a in apps:
        name = a.name
        if name in merged:
            existing = merged[name]
            e_fs = util.make_aware(existing.first_seen)
            a_fs = util.make_aware(a.first_seen)

            if e_fs is None and a_fs is not None:
                keep_new = True
            elif a_fs is None:
                keep_new = False
            else:
                keep_new = a_fs > e_fs

            if keep_new:
                merged[name] = a

            # Always preserve the earliest known first_seen (could be None if neither has it)
            merged[name].first_seen = _earliest(e_fs, a_fs)
        else:
            merged[name] = a

    apps = sorted(list(merged.values()), key=attrgetter('name'))
    apps = util.filter_known_apps(apps)
    apps = list(filter(remove_ignored_entries, apps))

    write_report(report_path, apps)
    write_sorted_reports(sorted_report_path, apps)

    # Print to console
    for app in apps:
        print(f"{app.scanner}: {app.name} {app.urls}")


if __name__ == '__main__':
    main()

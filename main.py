import argparse
import glob
import json
import os
import time
from operator import attrgetter

import util
from cache import Cache
from scanners.fdroid_scanner import FDroidScanner
from scanners.github_meta_scanner import GithubMetaScanner
from scanners.github_code_scanner import GithubCodeScanner
from scanners.scanner import Apps, App


def scan_apps(readme_paths, github_auth):
    apps = []
    apps.extend(FDroidScanner("https://f-droid.org/repo/index.xml").find_matching_apps())
    apps.extend(FDroidScanner("https://apt.izzysoft.de/fdroid/repo/index.xml").find_matching_apps())
    if github_auth is not None and len(github_auth) > 0:
        apps.extend(GithubCodeScanner(github_auth, readme_paths, exclude=apps, process_count=2).find_matching_apps())
        apps.extend(GithubMetaScanner(github_auth, readme_paths, exclude=apps, process_count=2).find_matching_apps())
    return sorted(set(apps), key=attrgetter('name'))


def write_report(report_path, apps):
    with (open(report_path, 'w') as f):
        report = ("## Scan results\n"
                  "> [!IMPORTANT]\n"
                  "> This file is automatically generated. Do not edit.\n"
                  "\n"
                  "This document tracks all GitHub repos and F-Droid apps that make use of Shizuku in some way but are not yet "
                  "listed in the awesome-shizuku list.\n"
                  "\n"
                  "Please note that many of these apps are often incomplete or sometimes even false positives.\n"
                  "\n"
                  "Typically, these apps will be added to the list as soon as possible; however, unfinished apps are usually left in this document until they reach a usable state.\n"
                  "\n")

        for app in apps:
            if len(app.urls) > 0:
                report += f" * [{app.name}]({app.urls[0]})"
            else:
                report += f" * {app.name}"

            if app.desc is not None:
                report += f" - {app.desc}"
            report += "\n"

        f.write(report)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("targetPath")
    args = parser.parse_args()

    github_auth = os.getenv("GITHUB_AUTH")
    if github_auth is None or len(github_auth) < 1:
        print("error: GITHUB_AUTH env variable not set; skipping GitHub scanners")

    summary_file = os.getenv("SUMMARY_FILE")
    if summary_file is None or len(summary_file) < 1:
        summary_file = "SUMMARY.md"

    path = args.targetPath
    readme_paths = glob.glob(path + '/*.md') + glob.glob(path + '/pages/UNLISTED.md')
    report_path = os.getcwd() + "/" + summary_file
    name_ignore_list_path = os.path.dirname(os.path.realpath(__file__)) + "/ignore_list.lst"

    ignore_list_file = open(name_ignore_list_path, 'r')
    ignore_list = ignore_list_file.read().splitlines(keepends=False)
    ignore_list_file.close()

    cache_dir = os.getcwd() + "/cache"
    if not os.path.exists(cache_dir):
        os.mkdir(cache_dir)

    cache = Cache(cache_dir)
    cached_apps = cache.load_all()

    def remove_ignored_entries(a):
        return not (a.name in ignore_list or any(url in ignore_list for url in a.urls))

    apps = util.filter_known_apps(readme_paths, scan_apps(readme_paths, github_auth))
    apps = list(filter(remove_ignored_entries, apps))
    cache.save_current_run(apps)
    print()

    apps.extend(cached_apps)
    apps = sorted(set(apps), key=attrgetter('name'))
    apps = util.filter_known_apps(readme_paths, apps)
    apps = list(filter(remove_ignored_entries, apps))

    write_report(report_path, apps)

    # Print to console
    for app in apps:
        print(app.scanner + ": " + app.name + " " + str(app.urls))
    time.sleep(0.5)


if __name__ == '__main__':
    main()

import itertools
import os
import subprocess
import time
import multiprocessing as mp
import tempfile

import util
from .scanner import Scanner, App

from github import Github, Auth
from github.GithubException import RateLimitExceededException
from tqdm import tqdm
from git import Repo


class GithubMetaScanner(Scanner):
    def __init__(self, auth_token, readme_path, exclude, process_count=1):
        self.auth = Github(auth=Auth.Token(auth_token))
        self.readme_path = readme_path
        self.exclude = exclude
        self.process_count = process_count

    def check_repo(self, args):
        temp_dir = tempfile.TemporaryDirectory()

        name = args.name
        url = args.urls[0]

        print("github_meta: cloning " + args.name + "...")
        Repo.clone_from(url, temp_dir.name, depth=1)
        app = []

        result = subprocess.Popen("grep -m 1 -rnw \"import rikka.shizuku.Shizuku\"",
                                  cwd=temp_dir.name,
                                  shell=True,
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.STDOUT)
        result.communicate()
        return_code = result.returncode

        if return_code == 0:
            app.append(App(name, [url], type(self)))

        temp_dir.cleanup()
        return app

    def find_matching_apps(self):
        results = self.auth.search_repositories('(shizuku AND NOT RepainterServicePriv) in:readme in:topics in:description language:Dart '
                                                'language:Kotlin language:Java', 'stars', 'desc')

        # print results
        print(f'github_meta: found {results.totalCount} repos')

        full_results = []
        for repo in tqdm(range(0, results.totalCount)):
            try:
                full_results.append(App(results[repo].name, [results[repo].html_url], type(self)))
                time.sleep(0.1)
            except RateLimitExceededException:
                print("github_meta: rate limit exceeded")
                time.sleep(60)
                full_results.append(App(results[repo].name, [results[repo].html_url], type(self)))

        filtered_results = util.filter_known_apps(self.readme_path, full_results, self.exclude)

        pool = mp.Pool(self.process_count, maxtasksperchild=1)
        apps = []
        apps.extend(pool.map(self.check_repo, filtered_results))
        pool.close()

        return list(itertools.chain.from_iterable(apps))

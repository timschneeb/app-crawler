import itertools
import os
import subprocess
import time
import multiprocessing as mp
import tempfile

from github.Repository import Repository

import util
from score import calc_github_score, has_github_downloads
from .scanner import Scanner, App

from github import Github, Auth
from github.GithubException import RateLimitExceededException
from tqdm import tqdm
from git import Repo


class GithubMetaScanner(Scanner):
    def __init__(self, auth_token, exclude, process_count=1):
        self.auth = Github(auth=Auth.Token(auth_token))
        self.exclude = exclude
        self.process_count = process_count

    def check_repo(self, args: App):
        temp_dir = tempfile.TemporaryDirectory()

        name = args.name
        desc = args.desc
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
            app.append(App(name, desc, [url], type(self).__name__, args.score))

        temp_dir.cleanup()
        return app

    def find_matching_apps(self):
        results = self.auth.search_repositories('(shizuku AND NOT RepainterServicePriv) in:readme in:topics in:description language:Dart '
                                                'language:Kotlin language:Java', 'stars', 'desc')

        # print results
        print(f'github_meta: found {results.totalCount} repos')

        full_results = []
        for repo_idx in tqdm(range(0, results.totalCount)):
            repo: Repository = results[repo_idx]
            
            if util.is_known_app(repo.name, [repo.html_url]) or util.is_ignored(repo.name) or util.is_ignored(repo.html_url):
                continue
    
            try:
                full_results.append(App(repo.name, repo.description, [repo.html_url], type(self).__name__, calc_github_score(repo), has_github_downloads(repo)))
                time.sleep(0.1)
            except RateLimitExceededException:
                print("github_meta: rate limit exceeded")
                time.sleep(60)
                full_results.append(App(repo.name, repo.description, [repo.html_url], type(self).__name__, calc_github_score(repo), has_github_downloads(repo)))

        filtered_results = util.filter_known_apps(full_results, self.exclude)

        pool = mp.Pool(self.process_count, maxtasksperchild=1)
        apps = []
        apps.extend(pool.map(self.check_repo, filtered_results))
        pool.close()

        return list(itertools.chain.from_iterable(apps))

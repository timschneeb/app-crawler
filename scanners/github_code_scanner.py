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


class GithubCodeScanner(Scanner):
    def __init__(self, auth_token, readme_paths, exclude, process_count=1):
        self.auth = Github(auth=Auth.Token(auth_token))
        self.readme_paths = readme_paths
        self.exclude = exclude
        self.process_count = process_count


    def find_matching_apps(self):
        results = self.auth.search_code('rikka.shizuku.ShizukuProvider language:XML NOT is:fork')

        # print results
        print(f'github_code: found {results.totalCount} repos')

        full_results = []
        for repo in tqdm(range(0, results.totalCount)):
            try:
                full_results.append(App(results[repo].repository.name, [results[repo].repository.html_url], type(self)))
                time.sleep(0.1)
            except RateLimitExceededException:
                print("github_code: rate limit exceeded")
                time.sleep(1)
                full_results.append(App(results[repo].repository.name, [results[repo].repository.html_url], type(self)))

        return util.filter_known_apps(self.readme_paths, full_results, self.exclude)

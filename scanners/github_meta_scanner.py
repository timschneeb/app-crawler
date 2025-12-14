import itertools
import multiprocessing as mp
import subprocess
import os
import hashlib
import shutil

from git import Repo
from github import Github, Auth
from tqdm import tqdm

import util
from .scanner import Scanner, App


class GithubMetaScanner(Scanner):
    def __init__(self, auth_token, exclude: list[App], process_count=1):
        self.auth = Github(auth=Auth.Token(auth_token))
        self.exclude = exclude
        self.process_count = process_count
        # directory where cached repo clones will be stored
        repo_root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        self.clones_dir = os.path.join(repo_root, 'cache', 'repos')
        os.makedirs(self.clones_dir, exist_ok=True)

    def _repo_id(self, url: str) -> str:
        # create a filesystem-safe id for the repo based on its URL
        h = hashlib.sha1(url.encode('utf-8')).hexdigest()
        return h

    def _ensure_clone(self, url: str) -> str:
        """Return path to a local clone for the given URL. Create a shallow clone if missing."""
        rid = self._repo_id(url)
        path = os.path.join(self.clones_dir, rid)
        if os.path.exists(path):
            # already exists; attempt a shallow fetch to update
            try:
                repo = Repo(path)
                # fetch latest from origin without pulling full history
                repo.remote().fetch(prune=True)
            except Exception as e:
                # if something is wrong with existing clone, remove and reclone
                try:
                    shutil.rmtree(path)
                except Exception:
                    pass
                raise e
        if not os.path.exists(path):
            try:
                Repo.clone_from(url, path, depth=1)
            except Exception as e:
                # In case of failure, ensure no partial dir remains
                if os.path.exists(path):
                    try:
                        shutil.rmtree(path)
                    except Exception:
                        pass
                raise e
        return path

    def check_repo(self, args: App):
        # Use cached clone if available to avoid full re-clone
        name = args.name
        desc = args.desc
        url = args.urls[0]

        print("github_meta: checking " + args.name + "...")
        app = []

        try:
            repo_path = self._ensure_clone(url)
        except Exception as e:
            print(f"github_meta: failed to clone {name} ({url}): {e}")
            return app

        # search for the target import string inside the repository
        result = subprocess.Popen("grep -m 1 -rnw \"import rikka.shizuku.Shizuku\"",
                                  cwd=repo_path,
                                  shell=True,
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.STDOUT)
        result.communicate()
        return_code = result.returncode

        if return_code == 0:
            app.append(App(name, desc, [url], type(self).__name__, args.has_downloads, args.last_updated))

        return app

    def _cleanup_stale_clones(self, desired_urls):
        """Remove cached clone directories that are not in desired_urls."""
        desired_ids = {self._repo_id(u) for u in desired_urls}
        try:
            for name in os.listdir(self.clones_dir):
                path = os.path.join(self.clones_dir, name)
                if not os.path.isdir(path):
                    continue
                if name not in desired_ids:
                    try:
                        print(f"github_meta: removing stale cached clone {name}")
                        shutil.rmtree(path)
                    except Exception as e:
                        print(f"github_meta: failed to remove {path}: {e}")
        except FileNotFoundError:
            return

    def find_matching_apps(self):
        results = self.auth.search_repositories('(shizuku AND NOT RepainterServicePriv) in:readme in:topics in:description language:Dart '
                                                'language:Kotlin language:Java', 'stars', 'desc')

        # print results
        print(f'github_meta: found {results.totalCount} repos')

        full_results = []
        for repo in tqdm(results, total=results.totalCount):
            if (repo.html_url in util.flatten([x.urls for x in self.exclude]) or 
                    util.is_known_app(repo.name, [repo.html_url]) or 
                    util.is_ignored(repo.name) or util.is_ignored(repo.html_url)):
                continue
    
            full_results.append(App(repo.name, repo.description, [repo.html_url], type(self).__name__,
                                    len(repo.get_releases().get_page(0)) > 0, repo.pushed_at))
            
        filtered_results = util.filter_known_apps(full_results, self.exclude)

        # Cleanup stale clones that are not present in this run
        desired_urls = [a.urls[0] for a in filtered_results]
        self._cleanup_stale_clones(desired_urls)

        pool = mp.Pool(self.process_count, maxtasksperchild=1)
        apps = []
        apps.extend(pool.map(self.check_repo, filtered_results))
        pool.close()

        return list(itertools.chain.from_iterable(apps))

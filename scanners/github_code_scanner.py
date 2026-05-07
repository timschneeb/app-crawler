from github import Github, Auth
from tqdm import tqdm

import util
from .scanner import Scanner, App


class GithubCodeScanner(Scanner):
    def __init__(self, auth_token, exclude: list[App], process_count=1):
        self.auth = Github(auth=Auth.Token(auth_token))
        self.exclude = exclude
        self.process_count = process_count

    def _check_original_content(self, repo) -> bool:
        """Check if repo owner is in the contributor list using GitHub API."""
        try:
            if repo.owner.type == "Organization":
                return True
            repo_owner = repo.owner.login.lower()
            # Get contributors from the repository
            contributors = repo.get_contributors()
            contributor_logins = {c.login.lower() for c in contributors}
            
            # Check if repo owner is in the contributor list
            return repo_owner in contributor_logins
        except Exception as e:
            print(f"github_code: failed to check contributors: {e}")
            # Default to True (assume original) if we can't determine
            return True

    def find_matching_apps(self):
        results = self.auth.search_code('rikka.shizuku.ShizukuProvider language:XML NOT is:fork')

        # print results
        print(f'github_code: found {results.totalCount} repos')

        processed_urls = []
        full_results = []

        # Manually iterate to safely catch GitHub API pagination errors
        iterator = iter(results)
        pbar = tqdm(total=results.totalCount)
        file = None

        while True:
            try:
                file = next(iterator)
                pbar.update(1)
            except StopIteration:
                break  # Reached the end normally
            except Exception as e:
                # GitHub often returns 404 when you page past the *actual* results
                print(f'\ngithub_code: API pagination stopped early (hit GitHub search limits): {e}')
                #break
                
            if file is None:
                print("github_code: warning: got None response, skipping")
                continue
                
            if (file.repository.html_url in util.flatten([x.urls for x in self.exclude]) or
                    file.repository.html_url in processed_urls or
                    util.is_known_app(file.repository.name, [file.repository.html_url]) or
                    util.is_ignored(file.repository.name) or util.is_ignored(file.repository.html_url)):
                continue

            try:
                is_original = self._check_original_content(file.repository)
                full_results.append(App(
                    file.repository.name,
                    file.repository.description,
                    [file.repository.html_url],
                    type(self).__name__,
                    len(file.repository.get_releases().get_page(0)) > 0,
                    file.repository.pushed_at,
                    is_original_content=is_original,
                    popularity=file.repository.stargazers_count,
                ))
                processed_urls.append(file.repository.html_url)
            except IndexError as e:
                print(f'github_code: index error: {e}')
                continue

        pbar.close()

        return util.filter_known_apps(full_results, self.exclude)

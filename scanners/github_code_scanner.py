from github import Github, Auth
from tqdm import tqdm

import util
from .scanner import Scanner, App


class GithubCodeScanner(Scanner):
    def __init__(self, auth_token, exclude: list[App], process_count=1):
        self.auth = Github(auth=Auth.Token(auth_token))
        self.exclude = exclude
        self.process_count = process_count


    def find_matching_apps(self):
        results = self.auth.search_code('rikka.shizuku.ShizukuProvider language:XML NOT is:fork')

        # print results
        print(f'github_code: found {results.totalCount} repos')

        processed_urls = []
        full_results = []
        for file in tqdm(results, total=results.totalCount):
            if (file.repository.html_url in util.flatten([x.urls for x in self.exclude]) or
                    file.repository.html_url in processed_urls or
                    util.is_known_app(file.repository.name, [file.repository.html_url]) or
                    util.is_ignored(file.repository.name) or util.is_ignored(file.repository.html_url)):
                continue
                        
            try:
                full_results.append(App(file.repository.name, file.repository.description, [file.repository.html_url], type(self).__name__,
                                        len(file.repository.get_releases().get_page(0)) > 0, file.repository.pushed_at))
                processed_urls.append(file.repository.html_url)
            except IndexError as e:
                print(f'github_code: index error: {e}')
                continue

        return util.filter_known_apps(full_results, self.exclude)

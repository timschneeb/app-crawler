import os

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

readme_paths = [] # Set by main.py

name_ignore_list_path = os.path.dirname(os.path.realpath(__file__)) + "/ignore_list.lst"
ignore_list_file = open(name_ignore_list_path, 'r')
ignore_list = ignore_list_file.read().splitlines(keepends=False)
ignore_list_file.close()

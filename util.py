def filter_known_apps(readme_path, apps, additional_excludes=None):
    if additional_excludes is None:
        additional_excludes = []

    with open(readme_path) as file:
        readme = file.read().lower()

        def filter_app(app):
            has_url = any(url.replace("https://", "").lower() in readme for url in app.urls)
            has_name = ('[' + app.name.lower() + ']') in readme
            is_excluded = app in additional_excludes
            # if not (has_url or has_name or is_excluded):
            #     print(app.name + " " + str(app.urls))
            return not (has_url or has_name or is_excluded)

        return list(filter(filter_app, apps))

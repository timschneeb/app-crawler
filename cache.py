import json
import os

from scanners.scanner import Apps, App


class Cache:
    def __init__(self, cache_directory):
        self.cache_directory = cache_directory
        self.cache_parts = 10
        pass

    def load_all(self):
        cache = []
        for i in range(1, self.cache_parts + 1):
            cache.extend(self.load_cache_part(i))
        return cache

    def save_current_run(self, apps):
        # Delete oldest cache part
        if os.path.exists(self.path(self.cache_parts)):
            os.remove(self.path(self.cache_parts))

        # Move each part one to the right
        for i in range(self.cache_parts - 1, 0, -1):
            print("Moving cache part " + str(i) + " to " + str(i + 1))
            if os.path.exists(self.path(i)):
                os.replace(self.path(i), self.path(i + 1))

        # Add current run
        self.save_cache(1, apps)

    def path(self, part_id):
        return self.cache_directory + '/cache' + str(part_id) + '.json'

    def load_cache_part(self, part_id):
        apps = []
        try:
            with open(self.path(part_id)) as f:
                for o in Apps(**json.loads(f.read())).apps:
                    apps.append(App(**o))

                print("Loaded cache part " + str(part_id))
                return apps
        except FileNotFoundError:
            return []
        except Exception as e:
            print("Cache not usable")
            print(e)
            return apps

    def save_cache(self, part_id, apps):
        with open(self.path(part_id), mode='w') as f:
            f.write(json.dumps(Apps(list(apps)), default=lambda o: o.__dict__, indent=4))

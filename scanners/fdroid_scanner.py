from .scanner import Scanner, App
import requests
from xml.dom import minidom


class FDroidScanner(Scanner):
    def __init__(self, fdroid_repo_xml):
        self.fdroid_repo_xml = fdroid_repo_xml

    def find_matching_apps(self):
        apps = []

        resp = requests.get(self.fdroid_repo_xml)
        if resp.status_code != 200:
            print("fdroid: error: " + self.fdroid_repo_xml + " returned " + str(resp.status_code) + " " + resp.reason)
            return apps

        dom = minidom.parseString(resp.content)
        elements = dom.getElementsByTagName('application')

        for element in elements:
            for package in element.getElementsByTagName("package"):
                perms_tags = package.getElementsByTagName("permissions")
                if len(perms_tags) > 0:
                    perms = perms_tags[0].firstChild.nodeValue
                    if perms is not None and "moe.shizuku.manager.permission.API_V23" in perms:
                        urls = []
                        if (source := element.getElementsByTagName("source")[0].firstChild) is not None:
                            urls.append(source.nodeValue)
                        if (web := element.getElementsByTagName("web")[0].firstChild) is not None:
                            urls.append(web.nodeValue)
                        urls.append("https://f-droid.org/packages/" + element.getElementsByTagName("id")[0].firstChild.nodeValue)
                        urls.append("https://f-droid.org/en/packages/" + element.getElementsByTagName("id")[0].firstChild.nodeValue)

                        apps.append(App(element.getElementsByTagName("name")[0].firstChild.nodeValue,
                                        element.getElementsByTagName("summary")[0].firstChild.nodeValue,
                                        urls, type(self).__name__, score=100)) # Apps from f-droid repos are always preferred
                        break

        print("fdroid: found " + str(len(apps)) + " apps")
        return apps

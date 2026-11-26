"""Validate published static pages; notify IndexNow only after deployment."""
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

HOST = "folvi.dpdns.org"
ROOT = "https://" + HOST
KEY = os.environ["INDEXNOW_KEY"]
KEY_URL = ROOT + "/" + KEY + ".txt"
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
EVENT = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())


def get(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {"User-Agent": "Get-On-Labs-SEO-Validation/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f"{url}: HTTP {response.status}")
        if response.geturl() != url:
            raise RuntimeError(f"Unexpected redirect: {url} -> {response.geturl()}")
        return response.read()


def git(*args):
    return subprocess.check_output(["git", *args])


def urls(xml):
    result = [node.text for node in ET.fromstring(xml).findall("s:url/s:loc", NS)]
    if not result or len(result) != len(set(result)):
        raise ValueError("Sitemap empty or has duplicate URLs")
    for url in result:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != HOST or parsed.query or parsed.fragment:
            raise ValueError(f"Invalid sitemap URL: {url}")
    return set(result)


def file_path(url):
    path = urllib.parse.urlsplit(url).path.lstrip("/")
    return path + "index.html" if not path or path.endswith("/") else path


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonicals = []
        self.jsonld = []
        self.in_json = False
        self.data = ""
        self.noindex = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonicals.append(attrs.get("href"))
        if tag == "meta" and attrs.get("name", "").lower() in ("robots", "googlebot", "bingbot"):
            self.noindex |= "noindex" in attrs.get("content", "").lower()
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self.in_json = True
            self.data = ""

    def handle_data(self, data):
        if self.in_json:
            self.data += data

    def handle_endtag(self, tag):
        if tag == "script" and self.in_json:
            self.jsonld.append(json.loads(self.data))
            self.in_json = False


def validate(current):
    if get(KEY_URL).decode().strip() != KEY:
        raise ValueError("IndexNow key file mismatch")
    if urls(get(ROOT + "/sitemap.xml")) != current:
        raise ValueError("Live sitemap differs from deployed revision")
    robots = get(ROOT + "/robots.txt").decode()
    if "Sitemap: " + ROOT + "/sitemap.xml" not in robots or "Disallow: /" in robots:
        raise ValueError("Unexpected robots.txt")
    for url in sorted(current):
        body = get(url)
        if body.replace(b"\r\n", b"\n") != Path(file_path(url)).read_bytes().replace(b"\r\n", b"\n"):
            raise ValueError(f"Live page differs from deployed revision: {url}")
        page = Page()
        page.feed(body.decode("utf-8"))
        if page.canonicals != [url] or page.noindex:
            raise ValueError(f"Canonical/indexability check failed: {url}")
        if url in (ROOT + "/still/", ROOT + "/buzzpa/"):
            graph = [node for item in page.jsonld for node in item.get("@graph", [item])]
            apps = [node for node in graph if node.get("@type") == "MobileApplication"]
            if len(apps) != 1 or apps[0].get("url") != url or not apps[0].get("installUrl", "").startswith("https://play.google.com/store/apps/details?id="):
                raise ValueError(f"Application JSON-LD check failed: {url}")
        print(f"Validated {url}")


def previous_head():
    run = EVENT.get("workflow_run")
    if not run:
        return None
    endpoint = f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/actions/workflows/{run['workflow_id']}/runs?branch=main&status=success&per_page=50"
    headers = {"Authorization": "Bearer " + os.environ["GH_TOKEN"], "Accept": "application/vnd.github+json", "User-Agent": "Get-On-Labs-SEO"}
    runs = json.loads(get(endpoint, headers))["workflow_runs"]
    older = [r for r in runs if r["run_number"] < run["run_number"]]
    if not older:
        return None
    return max(older, key=lambda r: r["run_number"])["head_sha"]


def changed_urls(current):
    previous = previous_head()
    if not previous:
        return current
    try:
        old = urls(git("show", previous + ":sitemap.xml"))
        changes = set(git("diff", "--name-only", "-z", previous, "HEAD").decode().strip("\0").split("\0"))
    except subprocess.CalledProcessError:
        return current
    if KEY + ".txt" in changes or any(p.startswith("assets/") for p in changes):
        return current | old
    return (current ^ old) | {u for u in current | old if file_path(u) in changes}


def main():
    current = urls(Path("sitemap.xml").read_bytes())
    for attempt in range(5):
        try:
            validate(current)
            break
        except (OSError, ValueError, RuntimeError) as error:
            if attempt == 4:
                raise
            print(f"Live validation retry {attempt + 1}: {error}")
            time.sleep(15)
    selected = sorted(changed_urls(current))
    if not selected:
        print("No changed canonical URLs; skipping IndexNow.")
        return
    payload = json.dumps({"host": HOST, "key": KEY, "keyLocation": KEY_URL, "urlList": selected}).encode()
    request = urllib.request.Request("https://api.indexnow.org/indexnow", data=payload, headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "Get-On-Labs-SEO/1.0"}, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status not in (200, 202):
            raise RuntimeError(f"Unexpected IndexNow response: {response.status}")
        print(f"IndexNow accepted request (HTTP {response.status}): {', '.join(selected)}")
        if response.status == 202:
            print("Key validation is pending at the search engine. Acceptance does not guarantee indexing.")


if __name__ == "__main__":
    main()

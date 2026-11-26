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
        self.missing_alt = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "img" and not attrs.get("alt", "").strip():
            self.missing_alt.append(attrs.get("src", "(unknown)"))
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
        if page.missing_alt:
            raise ValueError(f"Missing image alt text: {url}: {page.missing_alt}")
        if page.canonicals != [url] or page.noindex:
            raise ValueError(f"Canonical/indexability check failed: {url}")
        if url in (ROOT + "/still/", ROOT + "/buzzpa/"):
            graph = [node for item in page.jsonld for node in item.get("@graph", [item])]
            apps = [node for node in graph if node.get("@type") == "MobileApplication"]
            if len(apps) != 1 or apps[0].get("url") != url or not apps[0].get("installUrl", "").startswith("https://play.google.com/store/apps/details?id="):
                raise ValueError(f"Application JSON-LD check failed: {url}")
        if url in (ROOT + "/", ROOT + "/still/", ROOT + "/buzzpa/"):
            # Validate the dedicated social preview asset and its declared dimensions.
            import re
            import struct
            html = body.decode("utf-8")
            og = re.findall(r'<meta property="og:image" content="([^"]+)">', html)
            if len(og) != 1 or not og[0].startswith(ROOT + "/assets/og-"):
                raise ValueError(f"Missing dedicated Open Graph image: {url}")
            if '<meta property="og:image:width" content="1200">' not in html or '<meta property="og:image:height" content="630">' not in html:
                raise ValueError(f"Invalid Open Graph dimensions metadata: {url}")
            if '<meta name="twitter:card" content="summary_large_image">' not in html or '<meta name="robots" content="max-image-preview:large">' not in html:
                raise ValueError(f"Missing large image preview metadata: {url}")
            png = get(og[0])
            if not png.startswith(b"\x89PNG\r\n\x1a\n") or struct.unpack(">II", png[16:24]) != (1200, 630):
                raise ValueError(f"Invalid Open Graph PNG asset: {og[0]}")
            print(f"Validated social preview {og[0]}")
        if url == ROOT + "/buzzpa/":
            import re
            screenshots = re.findall(r'<div class="carousel-slide"[^>]*><img src="([^"]+)"', body.decode("utf-8"))
            if len(screenshots) != 3 or len(set(screenshots)) != 3:
                raise ValueError("Buzzpa carousel must contain three distinct screenshots")
            for screenshot in screenshots:
                if not screenshot.startswith("/assets/buzzpa-"):
                    raise ValueError(f"Unexpected Buzzpa screenshot: {screenshot}")
                if not get(ROOT + screenshot).startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError(f"Invalid Buzzpa screenshot: {screenshot}")
            print("Validated all three Buzzpa carousel images")
        print(f"Validated {url}")


def wait_for_pages():
    # The managed Pages workflow does not reliably trigger workflow_run.
    # Match its deployment to the exact pushed revision before submitting.
    sha = os.environ["GITHUB_SHA"]
    endpoint = f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/actions/runs?head_sha={sha}&per_page=50"
    headers = {"Authorization": "Bearer " + os.environ["GH_TOKEN"], "Accept": "application/vnd.github+json", "User-Agent": "Get-On-Labs-SEO"}
    for attempt in range(40):
        runs = json.loads(get(endpoint, headers))["workflow_runs"]
        pages = [r for r in runs if r["name"] == "pages build and deployment" and r["head_sha"] == sha]
        if pages:
            latest = max(pages, key=lambda r: r["run_number"])
            if latest["status"] == "completed":
                if latest["conclusion"] != "success":
                    raise RuntimeError(f"Pages deployment failed: {latest['html_url']}")
                print(f"Pages deployment succeeded: {latest['html_url']}")
                return
        print("Waiting for Pages deployment...", flush=True)
        time.sleep(15)
    raise RuntimeError("Timed out waiting for matching Pages deployment")


def changed_urls(current):
    previous = EVENT.get("before")
    if not previous or previous == "0" * 40:
        return current
    try:
        old = urls(git("show", previous + ":sitemap.xml"))
        changes = set(git("diff", "--name-only", "-z", previous, "HEAD").decode().strip("\0").split("\0"))
    except (subprocess.CalledProcessError, ValueError):
        return current
    if any(p.startswith(("assets/", ".github/")) or p == KEY + ".txt" for p in changes):
        return current | old
    return (current ^ old) | {u for u in current | old if file_path(u) in changes}


def main():
    wait_for_pages()
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

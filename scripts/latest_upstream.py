#!/usr/bin/env python3
import json
import re
import urllib.request

API = "https://hub.docker.com/v2/repositories/ponphil/litepan/tags?page_size=100"
PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)[-_]?beta$", re.I)

def get_json(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "LitePan-fnOS-builder/1.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

def main():
    url = API
    found = []
    pages = 0

    while url and pages < 5:
        data = get_json(url)
        for item in data.get("results", []):
            name = str(item.get("name", "")).strip()
            m = PATTERN.match(name)
            if not m:
                continue
            # 必须至少有 linux/amd64 镜像。
            images = item.get("images") or []
            has_amd64 = any(
                i.get("os") == "linux" and i.get("architecture") == "amd64"
                for i in images
            )
            # Docker Hub 有时列表接口不带完整 images；不因此误杀版本标签。
            if images and not has_amd64:
                continue
            found.append((
                tuple(int(x) for x in m.groups()),
                item.get("last_updated", ""),
                name,
            ))
        url = data.get("next")
        pages += 1

    if not found:
        raise SystemExit("没有在 ponphil/litepan Docker Hub 找到 vX.Y.Z-Beta 版本标签")

    found.sort(key=lambda x: (x[0], x[1]), reverse=True)
    print(found[0][2])

if __name__ == "__main__":
    main()

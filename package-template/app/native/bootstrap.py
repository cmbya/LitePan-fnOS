#!/usr/bin/env python3
import argparse
import io
import json
import os
import shutil
import stat
import struct
import tarfile
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

IMAGE = "ponphil/litepan"
PRIMARY_TAG = "v0.4.9-Beta"
FALLBACK_TAG = "beta"
REGISTRY = "https://registry-1.docker.io"
AUTH = "https://auth.docker.io/token"
ACCEPT = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
])


def log(msg):
    print(f"[LitePan fnOS] {msg}", flush=True)


def req(url, token=None, accept=None):
    headers = {"User-Agent": "LitePan-fnOS-native/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if accept:
        headers["Accept"] = accept
    return urllib.request.Request(url, headers=headers)


def get_token():
    q = urllib.parse.urlencode({
        "service": "registry.docker.io",
        "scope": f"repository:{IMAGE}:pull",
    })
    with urllib.request.urlopen(req(f"{AUTH}?{q}"), timeout=60) as r:
        data = json.load(r)
    token = data.get("token") or data.get("access_token")
    if not token:
        raise RuntimeError("Docker Hub 未返回拉取 token")
    return token


def get_json(url, token, accept=ACCEPT):
    with urllib.request.urlopen(req(url, token, accept), timeout=90) as r:
        return json.load(r), r.headers


def resolve_manifest(token, tag):
    data, headers = get_json(f"{REGISTRY}/v2/{IMAGE}/manifests/{tag}", token)
    if "manifests" in data:
        candidates = []
        for m in data.get("manifests", []):
            p = m.get("platform") or {}
            if p.get("os") == "linux" and p.get("architecture") == "amd64":
                candidates.append(m)
        if not candidates:
            raise RuntimeError(f"镜像 {IMAGE}:{tag} 没有 linux/amd64 架构")
        digest = candidates[0]["digest"]
        data, headers = get_json(f"{REGISTRY}/v2/{IMAGE}/manifests/{digest}", token)
        return data, digest
    digest = headers.get("Docker-Content-Digest", tag)
    return data, digest


def download_blob(token, digest, dst):
    url = f"{REGISTRY}/v2/{IMAGE}/blobs/{digest}"
    log(f"读取镜像层 {digest[:20]}...")
    with urllib.request.urlopen(req(url, token, "application/octet-stream"), timeout=300) as r, open(dst, "wb") as f:
        shutil.copyfileobj(r, f, length=1024 * 1024)


def extract_binary_from_layer(layer_path, dst):
    try:
        tf = tarfile.open(layer_path, mode="r:*")
    except tarfile.ReadError:
        return False
    with tf:
        for m in tf.getmembers():
            name = m.name.lstrip("./")
            if name == "app/litepan" and m.isfile():
                src = tf.extractfile(m)
                if src is None:
                    continue
                with open(dst, "wb") as out:
                    shutil.copyfileobj(src, out)
                return True
    return False


def validate_amd64_elf(path):
    if path.stat().st_size < 5 * 1024 * 1024:
        raise RuntimeError("提取到的 LitePan 二进制异常过小")
    with open(path, "rb") as f:
        hdr = f.read(64)
    if len(hdr) < 20 or hdr[:4] != b"\x7fELF":
        raise RuntimeError("提取结果不是 Linux ELF 可执行文件")
    endian = "<" if hdr[5] == 1 else ">"
    machine = struct.unpack(endian + "H", hdr[18:20])[0]
    if machine != 62:
        raise RuntimeError(f"提取的 ELF 不是 x86_64/amd64，e_machine={machine}")


def install(runtime, version_label):
    runtime.mkdir(parents=True, exist_ok=True)
    binary = runtime / "litepan"
    marker = runtime / "IMAGE_DIGEST"

    token = get_token()
    manifest = digest = used_tag = None
    errors = []
    for tag in (PRIMARY_TAG, FALLBACK_TAG):
        try:
            log(f"解析上游镜像 {IMAGE}:{tag}")
            manifest, digest = resolve_manifest(token, tag)
            used_tag = tag
            break
        except Exception as e:
            errors.append(f"{tag}: {e}")
    if manifest is None:
        raise RuntimeError("无法解析 LitePan 官方镜像：" + " | ".join(errors))

    existing = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
    if binary.is_file() and existing == str(digest):
        binary.chmod(0o755)
        log(f"LitePan 官方镜像 {used_tag} ({digest}) 已准备，跳过重复提取")
        return

    layers = manifest.get("layers") or []
    if not layers:
        raise RuntimeError("官方镜像 manifest 没有 layers")

    with tempfile.TemporaryDirectory(prefix="litepan-fnos-") as td_s:
        td = Path(td_s)
        extracted = td / "litepan"
        found = False
        # 从最上层开始查，保证拿到最终 rootfs 的 /app/litepan。
        for i, layer in enumerate(reversed(layers), 1):
            dg = layer.get("digest")
            if not dg:
                continue
            layer_file = td / f"layer-{i}.tar"
            download_blob(token, dg, layer_file)
            if extract_binary_from_layer(layer_file, extracted):
                found = True
                break
            try:
                layer_file.unlink()
            except OSError:
                pass
        if not found:
            raise RuntimeError("官方镜像各层中没有找到 /app/litepan")

        validate_amd64_elf(extracted)
        extracted.chmod(0o755)
        newbin = runtime / "litepan.new"
        shutil.copy2(extracted, newbin)
        newbin.chmod(0o755)
        os.replace(newbin, binary)
        marker.write_text(str(digest) + "\n", encoding="utf-8")
        (runtime / "UPSTREAM_TAG").write_text(used_tag + "\n", encoding="utf-8")
        (runtime / "PACKAGE_VERSION").write_text(version_label + "\n", encoding="utf-8")
        log(f"已从 {IMAGE}:{used_tag} 提取 linux/amd64 LitePan，可执行文件 {binary.stat().st_size} bytes")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runtime", required=True)
    ap.add_argument("--version", default="0.4.9-Beta")
    args = ap.parse_args()
    install(Path(args.runtime), args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

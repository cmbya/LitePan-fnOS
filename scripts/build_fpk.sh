#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG="${1:?用法: scripts/build_fpk.sh v0.4.9-Beta}"

VERSION_LABEL="${TAG#v}"
VERSION_NORM="$(printf '%s' "$VERSION_LABEL" | tr '[:upper:]' '[:lower:]')"

BUILD="$ROOT/.build"
PKG="$BUILD/package"
DIST="$ROOT/dist"

rm -rf "$BUILD"
mkdir -p "$PKG" "$DIST"
cp -a "$ROOT/package-template/." "$PKG/"

python3 - "$PKG" "$TAG" "$VERSION_LABEL" "$VERSION_NORM" <<'PY'
from pathlib import Path
import re, sys

pkg = Path(sys.argv[1])
tag = sys.argv[2]
version_label = sys.argv[3]
version_norm = sys.argv[4]

# manifest
p = pkg / "manifest"
s = p.read_text(encoding="utf-8")
s = re.sub(r"^version=.*$", f"version={version_norm}", s, flags=re.M)
s = re.sub(
    r"^desc=.*$",
    f"desc=LitePan Go {version_label} x86 原生飞牛版。不使用 Docker；安装时从上游官方 {tag} amd64 镜像提取二进制运行。",
    s,
    flags=re.M,
)
s = re.sub(
    r"^changelog=.*$",
    f"changelog=跟随上游 Docker Hub {tag}；x86_64 原生运行，无需 Docker；data 持久化，strm 与 mounts 使用飞牛共享目录。",
    s,
    flags=re.M,
)
s = re.sub(r"^checksum=.*$", "checksum=PLACEHOLDER", s, flags=re.M)
p.write_text(s, encoding="utf-8")

# bootstrap：固定到本次上游版本标签；beta 仅作为安装时兜底。
p = pkg / "app/native/bootstrap.py"
s = p.read_text(encoding="utf-8")
s = re.sub(r'^PRIMARY_TAG = ".*?"$', f'PRIMARY_TAG = "{tag}"', s, flags=re.M)
s = re.sub(
    r'ap\.add_argument\("--version", default=".*?"\)',
    f'ap.add_argument("--version", default="{version_label}")',
    s,
)
p.write_text(s, encoding="utf-8")

# lifecycle callbacks
for rel in ("cmd/install_callback", "cmd/upgrade_callback"):
    p = pkg / rel
    s = p.read_text(encoding="utf-8")
    s = re.sub(
        r'--version\s+"[^"]+"',
        f'--version "{version_label}"',
        s,
    )
    p.write_text(s, encoding="utf-8")

# install wizard help
p = pkg / "wizard/install"
s = p.read_text(encoding="utf-8")
s = re.sub(
    r'ponphil/litepan:v[0-9A-Za-z._-]+',
    f'ponphil/litepan:{tag}',
    s,
)
s = re.sub(
    r'v[0-9]+\.[0-9]+\.[0-9]+-Beta（失败时回退 beta）',
    f'{tag}（失败时回退 beta）',
    s,
)
p.write_text(s, encoding="utf-8")
PY

# app/ -> app.tgz
tar -czf "$PKG/app.tgz" -C "$PKG/app" .
rm -rf "$PKG/app"

MD5="$(md5sum "$PKG/app.tgz" | awk '{print $1}')"
python3 - "$PKG/manifest" "$MD5" <<'PY'
from pathlib import Path
import re, sys
p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
s = re.sub(r"^checksum=.*$", f"checksum={sys.argv[2]}", s, flags=re.M)
p.write_text(s, encoding="utf-8")
PY

OUT="$DIST/LitePan_${VERSION_LABEL}_fnOS_x86.fpk"

(
  cd "$PKG"
  tar -czf "$OUT" manifest ICON.PNG ICON_256.PNG LICENSE app.tgz config cmd wizard
)

# 基础校验
rm -rf "$BUILD/verify"
mkdir -p "$BUILD/verify"
tar -xzf "$OUT" -C "$BUILD/verify"

python3 - "$BUILD/verify" <<'PY'
from pathlib import Path
import hashlib, re, sys, tarfile

root = Path(sys.argv[1])
manifest = (root / "manifest").read_text(encoding="utf-8")

def get(k):
    m = re.search(rf"^{re.escape(k)}=(.*)$", manifest, re.M)
    if not m:
        raise SystemExit(f"manifest 缺少 {k}")
    return m.group(1).strip()

if get("platform") != "x86":
    raise SystemExit("platform 不是 x86")
if get("appname") != "litepan":
    raise SystemExit("appname 不是 litepan")

md5 = hashlib.md5((root / "app.tgz").read_bytes()).hexdigest()
if md5 != get("checksum"):
    raise SystemExit(f"checksum 不一致: manifest={get('checksum')} actual={md5}")

with tarfile.open(root / "app.tgz", "r:gz") as tf:
    names = {n.lstrip("./") for n in tf.getnames()}
    if "native/bootstrap.py" not in names:
        raise SystemExit("app.tgz 缺少 native/bootstrap.py")
    if "ui/config" not in names:
        raise SystemExit("app.tgz 缺少 ui/config")

print("FPK 静态校验通过")
PY

(
  cd "$DIST"
  sha256sum "$(basename "$OUT")" > SHA256SUMS.txt
)

echo "构建完成: $OUT"
cat "$DIST/SHA256SUMS.txt"

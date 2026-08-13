# LitePan-fnOS

LitePan Go 版的 fnOS x86 原生自动构建仓库。

## 自动更新来源

LitePan 当前 Go 版主要通过 Docker Hub 发布：
- 镜像：`ponphil/litepan`
- 滚动测试标签：`beta`
- 固定版本标签：例如 `v0.4.9-Beta`

本仓库每天检查一次 Docker Hub 中最新的 `vX.Y.Z-Beta` 固定版本标签。
发现新版本后自动生成 fnOS x86 FPK，并创建 GitHub Pre-release。

## 为什么不直接跟踪 GitHub Releases

当前 Ponphil/LitePan 的 Go 版 README 已经使用 `v0.4.9-Beta`，
但 GitHub Releases/Tags 并没有同步到同一版本，因此 Docker Hub 固定版本标签是更可靠的自动更新源。

## 运行方式

FPK 本身不运行 Docker。安装阶段通过 Docker Registry API 从上游官方镜像中提取
`linux/amd64` 的 `/app/litepan`，然后由 fnOS 原生启动。

## 手动构建

Actions -> Build LitePan fnOS FPK -> Run workflow

- `image_tag` 留空：自动选择最新 `vX.Y.Z-Beta`
- 也可以手动填写：`v0.4.9-Beta`

## 飞牛封装版本

`PACK_REV` 当前为 `native1`。

以后如果只修改 fnOS 封装而上游版本没变，把 `PACK_REV` 改成 `native2`，
再手动运行 Actions 即可生成新的 FPK。

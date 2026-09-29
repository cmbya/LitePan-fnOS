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

## 上游版本与旧包迁移

新 FPK 的 manifest、文件名和 Release tag 直接使用上游版本 `0.5.6-beta`，不再添加封装修订号。同一个上游版本只发布一次，不能静默替换同版本 FPK。

FnDepot 先前索引的版本为 `0.5.6-beta-native1`。已安装的旧包可能因版本号比较或安装来源无法自动升级；切换版本规则需要在设备上单独验证和迁移。

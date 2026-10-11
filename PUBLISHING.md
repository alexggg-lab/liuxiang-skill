# GitHub 发布步骤

建议仓库名称 `liuxiang-skill`，简介：

> 刘向 · 知识整理：为 Hermes 提供文章收录、Obsidian 整理与按需来源核验。

建议 Topics：`hermes`、`obsidian`、`agent-skills`、`knowledge-management`、`markdown`。

## 上传前

1. 将 README 中 GitHub 安装示例的用户名占位符改成真实用户名。
2. 核对 MIT 许可是否符合你的发布意图。
3. 在干净 Python 环境运行测试；保留实际验证记录。
4. 确认仓库不包含个人笔记、网页原图、密钥、`.venv`、数据库、缓存或本机路径。此包仅使用虚构示例。

## 第一次发布

可以在 GitHub 新建公开空仓库，将本目录内容上传。保留 `skills/liuxiang-skill` 层级，不要只上传 SKILL.md。

也可在本目录使用 Git 与 GitHub CLI，以下命令使用本项目的发布账号：

```sh
git init -b main
git add .
git commit -m "Release Liuxiang skill v0.1.0"
gh repo create alexggg-lab/liuxiang-skill --public --source=. --remote=origin --push
git tag v0.1.0
git push origin v0.1.0
gh release create v0.1.0 --title "刘向 v0.1.0" --notes-file RELEASE_NOTES.md
```

公开仓库建立后，从另一临时目录或独立 Hermes 测试配置验证 README 中的 Hub 安装命令，安装后准备依赖并运行 doctor。不要直接在自己的生产知识库测试新的安装流程。

GitHub Actions 配置已包含 Python 3.10/3.12、macOS/Linux 测试。实际推送后查看结果；本地通过不能代替 CI 已通过的声明。通过后可以给 Release 附上压缩包及 SHA256。

第一版先在 GitHub 发布，不必同时建立网站或申请其他平台收录。

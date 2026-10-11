# 刘向 · 知识整理

**把散落的文章，整理成有原文、有解读、有依据的 Obsidian 知识笔记。**

刘向是西汉典籍整理与校勘的重要人物。这个项目借用他的名字，将文章收录、分类整理和按需考证串成可复用的工作流程。历史背景可参阅[刘向文献编纂研究](https://www.nopss.gov.cn/n1/2022/0517/c373410-32423337.html)。

首版面向 Hermes，复用当前 Agent 的模型和联网能力，不新增 Agent。遵循 `SKILL.md` 结构，其他宿主可以手动加载，但尚未验证兼容性。

## 能做什么

- 收录公开文章网页，保留提取出的原文与配图顺序。
- 在同一笔记里保存概要、关键信息、个人想法、AI 解读和原文。
- 自动分类，保留发布方名称与独立的原始链接。
- 按 URL 去重；同名文章使用独立文件名。
- 保留手动编辑的属性及“我的想法”；其他正文修改后停止自动覆盖。
- 按需查询证据并回填核验范围、时间、逐项结论与来源短引文。

## 整理成品

文章结构固定为五段：

```text
这篇文章讲什么
值得留下的信息
我的想法
AI 解读
完整图文原文
```

作者主张、AI 建议和你的判断分别保存。样例见 [整理前](examples/原文示例.md) 与 [整理后](examples/整理结果示例.md)，内容为虚构示例。

## 安装到 Hermes

### 从下载包手动安装

解压后，将 `skills/liuxiang-skill` 整个文件夹放入当前 Hermes profile 的技能目录。默认是 `~/.hermes/skills/`；设置了 `HERMES_HOME` 时用 `$HERMES_HOME/skills/`。目标若已经存在，先检查版本并保留自定义内容。

示例：在本仓库根目录执行；目标文件夹不存在时复制。

```sh
HERMES_SKILLS="${HERMES_HOME:-$HOME/.hermes}/skills"
mkdir -p "$HERMES_SKILLS"
test ! -e "$HERMES_SKILLS/liuxiang-skill" && cp -R skills/liuxiang-skill "$HERMES_SKILLS/liuxiang-skill"
```

然后按照 [环境准备](skills/liuxiang-skill/references/setup.md) 创建独立虚拟环境，初始化知识库并运行 doctor。开启新会话，输入 `/liuxiang-skill` 加上具体要求。

### 发布到 GitHub 后安装

GitHub 仓库发布后执行：

```sh
hermes skills install alexggg-lab/liuxiang-skill/skills/liuxiang-skill
```

这是仓库中的独立技能目录，安装后仍需准备 Python 依赖并指定知识库路径。GitHub Hub 安装命令尚未在公开仓库实测；本包已验证离线手动安装结构。

## 怎么用

在 Hermes 中：

```text
/liuxiang-skill 把这个链接收录并整理到我的 Obsidian 知识库：<文章链接>
/liuxiang-skill 这个链接只保存原文，先不要解读：<文章链接>
/liuxiang-skill 核验这篇文章里有关融资金额的说法：<文章链接>
```

首次使用告诉 Hermes 知识库的真实路径。只保存原文不会调用模型；整理使用当前会话模型；核验需要宿主已有联网工具。

脚本也可以独立完成保存与校验，但不会自己生成解读或搜索证据。可用命令：`init`、`doctor`、`archive`、`import`、`read`、`apply`、`verify-prepare`、`verify-save`。运行 `--help` 查看参数。

## 数据与目录

```text
知识库/
├── 00_收件箱/                尚未整理的文章
├── 01_外部知识/<领域>/       已整理的单篇笔记
├── 05_原始素材/网页图片/     按文章保存的配图
└── _AI/刘向/                独立配置、URL 登记和核验请求
```

历史备份保存在知识库外部。项目不包含个人笔记、真实测试文章、运行数据库或 API Key。普通收录不外部核验；修改“核验状态”属性不会触发查证。

## 当前边界

- 版本 `0.1.0`：macOS 已验证，Linux 在 CI 中运行相同测试；不支持 Windows 原生运行。
- 公开静态网页为主；登录、验证码、反爬或 JavaScript 页面可能失败。失败时可以导入用户提供的 Markdown 正文。
- 最多保存40张配图，每个响应不超过20MB，不做 OCR。不识别文章容器时明确标记完整性待复核；不保证所有网页都能完整提取。
- 采用 Python 标准库锁及文件发布机制；保留已知冲突，但不宣称抵御所有外部编辑器并发写入。手工移动文件暂不自动修复登记。
- 核验脚本检查网页引文存在，不能代替对证据是否支持结论的判断。“已核验”仅覆盖本次选定说法。
- 原文归档在本地；整理内容进入宿主模型上下文，其处理方式由宿主配置决定。
- 第一版不包含日记、随手观察、后台任务或原有自定义插件，也不自动迁移原有收录登记。已有文章再次收录前应人工检查。

## 测试与发布

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

测试用虚构原文、模拟 HTTP 和临时知识库，覆盖去重、同名文章、原文保留、用户修改保护、图片顺序、核验和错误证据拒绝。无需真实 API Key，不访问个人知识库。具体发布步骤见 [发布说明](PUBLISHING.md)。

## 更新与卸载

手动安装：备份技能文件夹中的自定义改动，停止正在执行的整理，再替换技能文件夹，重新安装 requirements。不要删除知识库中的 `_AI/刘向`，否则会丢失 URL 登记和核验历史。

Hub 安装：按 Hermes 的技能更新机制更新，核对版本并重新检查依赖。

卸载只删除或通过 Hermes 卸载 `liuxiang-skill` 技能目录；知识库笔记、图片、配置和外部备份保留。若需清理这些数据，请先逐项确认自己的用途。

## 许可与参考

MIT License。项目受 [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) 的格式化技能组织方式与 [Hermes Skills](https://github.com/NousResearch/hermes-agent) 生态启发；实现提取自作者实际使用并迭代的本地文章工作流。第三方 Python 依赖遵循各自许可证，本仓库不包含其源码。

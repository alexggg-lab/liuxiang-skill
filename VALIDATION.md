# 发布候选验证记录

日期：2026-10-11。版本：0.1.0。环境：macOS、Python 3.14，独立新建虚拟环境。

- 从 requirements.txt 安装依赖成功：lxml 6.1.3、trafilatura 2.3.1。
- pip check：无依赖冲突。
- skill-creator 的 quick_validate.py：Skill is valid。
- 11项离线行为测试通过，全部使用临时知识库与虚构资料。
- 将完整技能目录复制到隔离安装路径后，init、doctor、import、apply 连续运行成功。
- 示例结果由实际发布包脚本生成，没有使用个人文章或真实配图。

覆盖：原文保留、URL 去重、同名不同链接、属性与个人想法保留、多行 tags 更新、手工正文冲突保护、错误整理 JSON、独立配置与重复初始化、软链接目标拒绝、图片顺序与来源、部分核验与 token 重放拒绝、伪造引文拒绝、私有地址拒绝。

尚未验证：公开 GitHub 仓库的 Hub 安装、Linux CI、Windows 原生环境、实际宿主模型端到端表现、所有网页格式与反爬行为。CI 配置已提供，推送后以实际结果为准。

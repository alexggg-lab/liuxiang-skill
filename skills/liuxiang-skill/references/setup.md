# 环境准备

要求 Python 3.10+，macOS 或 Linux。示例命令中先将 `SKILL_DIR`、`VAULT` 改成安装目录和自己的知识库路径；不要直接运行占位值。

```sh
SKILL_DIR="/实际安装目录/liuxiang-skill"
VAULT="/实际知识库目录"
VENV="${XDG_CACHE_HOME:-$HOME/.cache}/liuxiang-skill/venv"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install -r "$SKILL_DIR/requirements.txt"
PYTHON="$VENV/bin/python"
"$PYTHON" "$SKILL_DIR/scripts/liuxiang.py" --vault "$VAULT" init
"$PYTHON" "$SKILL_DIR/scripts/liuxiang.py" --vault "$VAULT" doctor
```

若 Hermes 使用远程终端或容器，VAULT 必须是该终端能访问的真实路径。暂不支持 Windows 原生 Python，因为文件锁使用 fcntl；Windows 用户可在 WSL 中自行验证。

运行数据在知识库 `_AI/刘向/`，与已有 `_AI/pipeline.json` 分开。配置文件 `_AI/刘向/config.json` 可编辑 `topics`、`tag_aliases`、`timezone`、`backup_directory`；备份目录必须位于知识库外部。领域名不可包含路径分隔符。默认备份目录是知识库同级 `<知识库名>-刘向备份`。

首次初始化可传 `--topics AI前沿 AI应用 商业观察` 和 `--backup-directory /实际备份目录`。再次 init 不覆盖配置，调整时直接编辑独立配置。

本版本不申请单独 API Key，不新增模型服务、Agent 或定时任务。AI 解读和联网查询使用当前 Hermes 已配置的能力。正文会进入宿主模型上下文，具体数据处理方式取决于宿主的模型供应商。

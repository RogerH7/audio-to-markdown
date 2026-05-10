# audio2md

把手机端分享的播客、视频链接自动转成 Markdown 知识库资料。

当前流程：

```text
手机飞书 Bot 收链接
  -> 本地监听器入队
  -> worker 下载音频
  -> ffmpeg 标准化音频
  -> OSS 临时中转
  -> 阿里云 Paraformer V2 转写
  -> DeepSeek V4 Flash 整理成笔记
  -> output/YYYY-MM-DD/*.md
  -> 飞书 Bot 回发结果
```

## 功能

- 支持通过飞书 Bot 从手机端提交链接。
- 支持 Bilibili、YouTube、小宇宙、通用音频直链等 `yt-dlp` 可处理来源。
- 使用阿里云百炼 `paraformer-v2` 做录音文件识别。
- 使用 DeepSeek OpenAI-compatible API 做摘要、结构化整理和笔记化。
- 使用 SQLite 做本地任务队列，避免重复提交。
- 使用 OSS 临时签名 URL 给 ASR 读取音频。
- 支持 OSS 临时音频按配置保留后自动清理。

## 目录结构

```text
AGENTS.md                    后续开发协作说明
config/
  config.example.yaml       示例配置，提交到 Git
docs/
  api_keys.md               API Key 申请与配置
  feishu_bot_setup.md       飞书 Bot 配置
  github_upload.md          GitHub 上传步骤
  model_costs.md            模型选型与费用估算
  workflow.md               日常运行说明
scripts/
  run_service.py            常驻服务：飞书监听 + worker + OSS 清理
  listen_lark.py            飞书事件监听
  run_worker.py             队列 worker
  cleanup_storage.py        OSS 临时音频清理
  check_config.py           环境与 OSS 连通性检查
src/podcast2md/
  核心实现
```

运行时生成的 `.env`、`config/config.yaml`、`data/`、`output/`、`logs/` 不会提交到 Git。

## 准备环境

需要：

- Python 3.10+
- `ffmpeg`
- `lark-cli`
- 阿里云百炼 API Key
- DeepSeek API Key
- 阿里云 OSS Bucket 与 AccessKey

安装 Python 依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

复制配置文件：

```bash
cp .env.example .env
cp config/config.example.yaml config/config.yaml
```

然后编辑 `.env`：

```bash
DASHSCOPE_API_KEY=
DEEPSEEK_API_KEY=
ALIYUN_ACCESS_KEY_ID=
ALIYUN_ACCESS_KEY_SECRET=
ALIYUN_OSS_ENDPOINT=https://oss-cn-beijing.aliyuncs.com
ALIYUN_OSS_BUCKET=
```

初始化队列：

```bash
python3 scripts/init_db.py
```

检查配置：

```bash
python3 scripts/check_config.py --network
```

## 日常使用

启动常驻服务：

```bash
python3 scripts/run_service.py
```

然后在手机端或电脑端给飞书 Bot 发送链接。默认配置下：

- 飞书消息接收是长连接事件驱动，不靠轮询飞书。
- worker 每 30 秒检查一次本地 SQLite 队列。
- OSS 临时音频默认保留 1 天，后台每 1 小时清理一次过期对象。

如果想更快处理队列：

```bash
python3 scripts/run_service.py --worker-poll-interval 10
```

如果想单次处理队列里的一个任务：

```bash
python3 scripts/run_worker.py --once
```

查看队列：

```bash
python3 scripts/list_queue.py --limit 10
```

重试失败任务：

```bash
python3 scripts/retry_task.py 3
```

## 配置保留时间

在 `config/config.yaml` 中调整：

```yaml
service:
  worker_poll_interval_seconds: 30

storage:
  delete_after_asr: false
  retention_days: 1
  cleanup_interval_seconds: 3600
```

含义：

- `worker_poll_interval_seconds`: worker 检查本地队列的间隔。
- `delete_after_asr: true` 且 `retention_days: 0`: ASR 完成后立刻删除 OSS 音频。
- `delete_after_asr: false` 且 `retention_days: 1` 或 `3`: 保留指定天数后由清理器删除。
- `cleanup_interval_seconds`: 常驻服务中清理器的运行间隔。

手动预览将删除哪些 OSS 对象：

```bash
python3 scripts/cleanup_storage.py --dry-run
```

手动执行一次清理：

```bash
python3 scripts/cleanup_storage.py
```

## 费用

当前推荐组合：

- ASR: 阿里云百炼 `paraformer-v2`
- 后处理: DeepSeek V4 Flash
- OSS: 只做临时音频中转

按 1 小时音频估算，超过免费额度后通常约 `0.32-0.41 元/小时`。详见 [docs/model_costs.md](docs/model_costs.md)。

## GitHub 上传

上传前先确认没有密钥或运行产物进入 Git：

```bash
git status --short --ignored
```

完整步骤见 [docs/github_upload.md](docs/github_upload.md)。

## 注意

- 不要提交 `.env`、`config/config.yaml`、cookies、队列数据库、ASR JSON、输出文档和音频文件。
- Bilibili 或 YouTube 遇到 403 时，可以在本地配置 `cookies_from_browser: "chrome"`，但不要把 cookies 提交到 Git。
- 本项目默认不包含许可证。公开发布前请根据你的分发意图选择合适的 License。

# 音视频转 Markdown 工作流

## 当前架构

```text
手机飞书分享链接
  -> 飞书 Bot 私聊消息
  -> scripts/listen_lark.py 监听事件
  -> data/queue.sqlite 入队去重
  -> scripts/run_worker.py 处理任务
  -> yt-dlp/requests 下载音频
  -> ffmpeg 转单声道 16k mp3
  -> 上传阿里云 OSS，生成临时 HTTPS URL
  -> 阿里云 Paraformer V2 转写
  -> DeepSeek V4 Flash 整理为知识库笔记
  -> output/YYYY-MM-DD/*.md
  -> 飞书 Bot 回发结果
```

## 日常自动模式

日常使用只需要在家里电脑开一个常驻进程：

```bash
python3 scripts/run_service.py
```

它会同时启动：

- `scripts/listen_lark.py`：监听飞书 Bot 收到的新消息，并把链接写入队列。
- `scripts/run_worker.py`：持续消费队列，自动下载、转写、整理成 Markdown。
- `scripts/cleanup_storage.py`：如果开启 OSS 保留期，定期清理过期临时音频。

电脑保持联网、终端不关闭时，手机端向飞书 Bot 发送 Bilibili、YouTube、小宇宙、播客链接后，会自动执行完整流程。

默认情况下，飞书消息接收是长连接事件驱动；只有本地 worker 会每 30 秒检查一次 SQLite 队列。这个间隔可以在 `config/config.yaml` 里调整：

```yaml
service:
  worker_poll_interval_seconds: 30
```

也可以启动时临时覆盖：

```bash
python3 scripts/run_service.py --worker-poll-interval 10
```

## 初始化

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 scripts/init_db.py
```

## 环境变量

详细申请步骤见 [api_keys.md](api_keys.md)。

项目会自动读取根目录 `.env`，推荐直接编辑 `.env`，不用每次手动 `export`：

```bash
DASHSCOPE_API_KEY="阿里云百炼 API Key"
DEEPSEEK_API_KEY="DeepSeek API Key"

ALIYUN_ACCESS_KEY_ID="阿里云 AccessKeyId"
ALIYUN_ACCESS_KEY_SECRET="阿里云 AccessKeySecret"
ALIYUN_OSS_ENDPOINT="https://oss-cn-xxx.aliyuncs.com"
ALIYUN_OSS_BUCKET="你的 bucket 名称，不是完整 URL"
```

阿里云 Paraformer V2 需要公网可访问的音频 URL，所以这里用 OSS 临时签名 URL 作为中转。

## 手动验证队列

```bash
python3 scripts/submit_url.py "https://www.bilibili.com/video/BVxxxx"
python3 scripts/list_queue.py
```

不调用外部 API 的 dry-run：

```bash
python3 scripts/run_worker.py --once --dry-run
```

真实处理一个任务：

```bash
python3 scripts/run_worker.py --once
```

持续后台处理：

```bash
python3 scripts/run_worker.py
```

## 飞书监听

```bash
python3 scripts/listen_lark.py
```

建议手机端分享时保留完整链接，例如：

```text
https://www.bilibili.com/video/BVxxxx
```

当前脚本也会自动识别常见裸链接，例如 `bilibili.com/video/BVxxxx`，并补成 `https://...`。

建议开两个终端：

1. 终端 A 跑 `python3 scripts/listen_lark.py`
2. 终端 B 跑 `python3 scripts/run_worker.py`

也可以直接用一个常驻服务同时启动监听和 worker：

```bash
python3 scripts/run_service.py
```

这样手机端给飞书 Bot 发送链接后，任务会自动入队并自动处理。

如果飞书后台暂时不能启用 `im.message.receive_v1`，先用轮询兜底：

```bash
lark-cli im +chat-search --as user --query "音视频转文档收件箱" --format table
python3 scripts/poll_lark_inbox.py --chat-id "oc_xxx" --as user --interval 60
```

轮询模式读取群消息并入队，不依赖事件订阅。

## OSS 临时文件

默认配置会保留阿里云 Paraformer V2 读取过的临时音频 3 天，便于排查问题，然后由清理器删除：

```yaml
storage:
  delete_after_asr: false
  retention_days: 3
  cleanup_interval_seconds: 3600
```

如果希望 ASR 完成后立刻删除，改成：

```yaml
storage:
  delete_after_asr: true
  retention_days: 0
```

如果只想保留 1 天，把 `retention_days` 改为 `1`。保留 1-3 天的 OSS 存储费用很低，但清理器必须持续运行，或者在 OSS 控制台为 `podcast2md/audio/` 前缀配置生命周期删除规则。

手动预览清理对象：

```bash
python3 scripts/cleanup_storage.py --dry-run
```

手动执行一次清理：

```bash
python3 scripts/cleanup_storage.py
```

模型选型和单小时费用估算见 [model_costs.md](model_costs.md)。

## B 站 / YouTube Cookies

如果遇到会员内容、年龄限制、登录态限制，在 `config/config.yaml` 中设置：

```yaml
download:
  cookie_file: "config/cookies/cookies.txt"
```

如果 B 站报 `HTTP Error 403: Forbidden`，优先尝试使用浏览器登录态：

```yaml
download:
  cookies_from_browser: "chrome"
```

然后把失败任务重新放回队列：

```bash
python3 scripts/retry_task.py 2
python3 scripts/run_worker.py --once
```

不要把 cookies 提交到版本控制。

## ASR 任务排查

真实转写时，worker 会提交阿里云 Paraformer V2 异步任务并轮询状态。13 分钟左右的视频通常应在几分钟内返回；如果长时间没有完成，可以另开终端查看最近的 DashScope ASR 任务：

```bash
python3 scripts/list_asr_tasks.py --page-size 10
```

如果 worker 被中断，把任务重新放回队列：

```bash
python3 scripts/retry_task.py 2
python3 scripts/run_worker.py --once
```

# 模型选型与费用估算

更新时间：2026-05-08

## 当前推荐

当前工作流继续使用：

```text
阿里云 Paraformer V2 负责音视频转文字
DeepSeek V4 Flash 负责文字稿后处理、摘要、笔记化
OSS 只作为临时音频中转，默认保留 1 天后自动清理
```

理由很直接：`paraformer-v2` 是这组候选里最便宜的可用离线 ASR 模型，已经在当前项目里跑通，并且支持时间戳、说话人分离、常见音视频格式和中英等多语种识别。`fun-asr-mtl` 适合更多语种覆盖，但成本约为 Paraformer V2 的 2.75 倍。`qwen3-tts-vd-2026-01-26` 和 `sambert-zhida-v1` 都是文本转语音，不适合这个音频转文字流程。

## 阿里云语音模型对比

| 模型 | 类型 | 价格 | 折算 1 小时 | 是否适合本工作流 | 结论 |
| --- | --- | ---: | ---: | --- | --- |
| `paraformer-v2` | 录音文件识别 ASR | 0.00008 元/秒 | 0.288 元/小时 | 适合 | 默认使用 |
| `fun-asr-mtl` | 录音文件识别 ASR | 0.00022 元/秒 | 0.792 元/小时 | 可用 | 多语种覆盖更宽，但贵很多 |
| `qwen3-asr-flash-filetrans` | 录音文件识别 ASR | 0.00022 元/秒 | 0.792 元/小时 | 可用 | 如果要试新千问 ASR 可以单独评测，但价格不优 |
| `qwen3-tts-vd-2026-01-26` | 文本转语音 TTS | 0.8 元/万字符 | 不按音频时长计费 | 不适合 | 这是生成语音，不是识别语音 |
| `sambert-zhida-v1` | 文本转语音 TTS | 1 元/万字符 | 不按音频时长计费 | 不适合 | 这是生成语音，不是识别语音 |

补充判断：

- 中文播客、Bilibili 视频、小宇宙这类长音频：优先 `paraformer-v2`。
- 明显多语种混杂、阿拉伯语/东南亚语/欧洲小语种较多：再考虑 `fun-asr-mtl`。
- 实时字幕或直播：需要单独评估实时 ASR，不走当前“下载文件 -> 离线识别”路线。
- TTS 模型只在以后需要“把笔记朗读成音频”时才有意义。

## 1 小时音频成本

按当前项目配置估算：

```text
ffmpeg 标准化：单声道 16kHz，64 kbps mp3
1 小时临时音频大小 ≈ 64 kbit/s × 3600 / 8 ≈ 28.8 MB
```

如果超过免费额度，单小时成本大致如下：

| 项目 | 估算 |
| --- | ---: |
| Paraformer V2 ASR | 0.288 元 |
| DeepSeek V4 Flash 后处理 | 通常约 0.03-0.08 元，预算按 0.10 元计 |
| OSS 临时存储、请求、可能的读取流量 | 通常 < 0.02 元 |
| 合计 | 约 0.32-0.41 元/小时 |

如果仍在阿里云百炼免费额度内，`paraformer-v2` 每月有 36,000 秒（10 小时）免费额度，前 10 小时的 ASR 成本会被抵扣；这时主要成本就是 DeepSeek 后处理和极小的 OSS 费用。

如果改用 `fun-asr-mtl`：

```text
0.00022 元/秒 × 3600 秒 = 0.792 元/小时
加 DeepSeek 和 OSS 后约 0.85-0.95 元/小时
```

## OSS Bucket 费用

Bucket 本身不是按“创建一个 bucket”收费，主要按实际用量收费：

- 存储容量：标准型本地冗余示例价 0.12 元/GB/月，按小时折算。
- 请求次数：读写请求有免费阶梯或按万次计费，当前个人工作流量级基本可以忽略。
- 流量：上行到 OSS 通常免费；是否产生下行费用取决于实际访问路径和计费口径。

当前配置默认保留 1 天：

```yaml
storage:
  delete_after_asr: false
  retention_days: 1
```

按 1 小时音频约 28.8 MB 计算，即使保留整整一个月，存储费也只有：

```text
0.0288 GB × 0.12 元/GB/月 ≈ 0.0035 元/月
```

如果只保留 1 天：

```text
0.0035 元/月 × 1/30 ≈ 0.00012 元
```

如果每天处理 10 小时音频，并且每份音频保留 1 天，常驻存量约 10 小时音频，存储费约：

```text
10 × 0.0288 GB × 0.12 元/GB/月 ≈ 0.035 元/月
```

因此，保留 1 天对总成本影响更低。OSS 在这个工作流里不是主要成本，主要成本仍然是 ASR 和 LLM 后处理。

## 价格来源

- [阿里云百炼模型价格](https://help.aliyun.com/zh/model-studio/model-pricing)
- [阿里云录音文件识别模型说明](https://www.alibabacloud.com/help/zh/model-studio/recording-file-recognition)
- [阿里云 TTS 模型说明](https://help.aliyun.com/zh/model-studio/text-to-speech)
- [阿里云 OSS 计费组成](https://help.aliyun.com/zh/oss/billing-overview)
- [阿里云 OSS 存储费用](https://help.aliyun.com/zh/oss/storage-fees)
- [DeepSeek API Pricing](https://api-docs.deepseek.com/quick_start/pricing)

# API Key 与云资源配置

本项目当前需要三类凭证：

1. `DASHSCOPE_API_KEY`：阿里云百炼 API Key，用于 Paraformer V2 语音转文字。
2. `DEEPSEEK_API_KEY`：DeepSeek API Key，用于转录后的 Markdown 笔记整理。
3. `ALIYUN_ACCESS_KEY_ID` / `ALIYUN_ACCESS_KEY_SECRET`：阿里云 RAM AccessKey，用于上传音频到 OSS 并生成临时 HTTPS URL。

## 阿里云百炼 API Key

官方文档：<https://help.aliyun.com/zh/model-studio/get-api-key>

步骤：

1. 打开阿里云百炼控制台：<https://bailian.console.aliyun.com/>
2. 页面右上角选择地域，建议中国内地使用「华北 2（北京）」。
3. 进入「API Key」页面。
4. 点击「创建 API Key」。
5. 归属业务空间建议先选「默认业务空间」。
6. 权限建议先选「全部」。后续稳定后再收窄 IP 白名单或权限。
7. 创建后复制完整 API Key，格式通常类似 `sk-...`。
8. 在本机配置：

```bash
export DASHSCOPE_API_KEY="sk-..."
```

注意：百炼 API Key 和 Coding Plan 专属 API Key 不是一回事。本项目调用 Paraformer V2 需要百炼通用 API Key。

## 阿里云 OSS RAM AccessKey

官方文档：<https://help.aliyun.com/zh/ram/user-guide/create-an-accesskey-pair>

Paraformer V2 的录音文件识别需要可公网访问的音频 URL，所以项目会先把音频上传到 OSS，再生成临时签名 URL。不要直接使用主账号 AccessKey，建议创建专用 RAM 用户。

建议步骤：

1. 进入 RAM 控制台：<https://ram.console.aliyun.com/>
2. 创建一个专用 RAM 用户，例如 `audio2md-oss-uploader`。
3. 授权它访问你的 OSS Bucket。最小权限可后续细化，MVP 阶段可先绑定 OSS 相关权限。
4. 进入该 RAM 用户详情页的「AccessKey」页签。
5. 点击「创建 AccessKey」。
6. 复制并妥善保存 `AccessKey ID` 和 `AccessKey Secret`。Secret 只在创建时显示一次。
7. 在本机配置：

```bash
export ALIYUN_ACCESS_KEY_ID="..."
export ALIYUN_ACCESS_KEY_SECRET="..."
export ALIYUN_OSS_ENDPOINT="https://oss-cn-xxx.aliyuncs.com"
export ALIYUN_OSS_BUCKET="你的-bucket-名称"
```

`ALIYUN_OSS_BUCKET` 只填 bucket 名称，不要填完整域名或 URL。例如：

```bash
ALIYUN_OSS_BUCKET=audio2md
```

不要写成：

```bash
ALIYUN_OSS_BUCKET=https://audio2md.oss-cn-beijing.aliyuncs.com
ALIYUN_OSS_BUCKET=audio2md.oss-cn-beijing.aliyuncs.com
```

## DeepSeek API Key

```bash
export DEEPSEEK_API_KEY="sk-..."
```

## 使用 .env 保存配置

项目会自动读取根目录 `.env` 文件。建议复制模板后填写：

```bash
cp .env.example .env
```

然后编辑 `.env`：

```bash
DASHSCOPE_API_KEY=sk-...
DEEPSEEK_API_KEY=sk-...

ALIYUN_ACCESS_KEY_ID=...
ALIYUN_ACCESS_KEY_SECRET=...
ALIYUN_OSS_ENDPOINT=https://oss-cn-beijing.aliyuncs.com
ALIYUN_OSS_BUCKET=你的-bucket-名称
```

`.env` 已经加入 `.gitignore`，不要把真实密钥提交到 Git。

## 依赖安装

真实调用 DeepSeek 和阿里云前，需要安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

如果只验证飞书入队和 dry-run，可以不配置 API Key。

## 验证配置

本地检查 `.env` 和依赖，不会打印完整密钥：

```bash
python3 scripts/check_config.py
```

同时测试 OSS 上传和临时 URL 生成：

```bash
python3 scripts/check_config.py --network
```

注意：`--network` 会向配置的 OSS bucket 上传一个很小的测试文件，用于验证 AccessKey、bucket、endpoint 和签名 URL 配置是否可用。

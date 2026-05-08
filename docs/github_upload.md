# GitHub 上传说明

## 提交前检查

确认这些文件不会被提交：

```bash
git status --short --ignored
```

应该看到 `.env`、`config/config.yaml`、`data/`、`output/`、`logs/`、`__pycache__/` 等位于 ignored 区域，而不是 staged 或 untracked 区域。

如果不确定是否有密钥泄漏，可以运行：

```bash
git diff --cached
```

重点检查：

- 不要出现 `sk-` 开头的 API Key。
- 不要出现阿里云 AccessKeySecret。
- 不要提交 cookies。
- 不要提交真实输出文档、ASR JSON 和队列数据库。

## 首次提交

如果项目还没有提交记录：

```bash
git add .gitignore .env.example README.md requirements.txt config/config.example.yaml docs scripts src
git commit -m "Initial audio to markdown workflow"
```

## 创建 GitHub 仓库

在 GitHub 新建一个空仓库，不要勾选自动生成 README、`.gitignore` 或 License。假设仓库地址是：

```text
git@github.com:<your-name>/audio2md.git
```

添加远程仓库并推送：

```bash
git remote add origin git@github.com:<your-name>/audio2md.git
git branch -M main
git push -u origin main
```

如果使用 HTTPS：

```bash
git remote add origin https://github.com/<your-name>/audio2md.git
git branch -M main
git push -u origin main
```

## 后续更新

```bash
git status --short
git add <changed-files>
git commit -m "Describe the change"
git push
```

## 建议的仓库说明

Repository description 可以写：

```text
Feishu Bot workflow for turning podcast and video links into Markdown notes with Aliyun Paraformer V2 and DeepSeek.
```

Topics 可以加：

```text
feishu, podcast, transcription, markdown, aliyun, deepseek, yt-dlp
```

## License

当前仓库没有默认许可证。公开发布前建议明确选择：

- 只给自己用：可以暂时不加 License。
- 希望别人自由使用和修改：MIT 是最简单的选择。
- 希望专利条款更明确：Apache-2.0。

License 是法律承诺，不建议在没有明确意图时随手添加。

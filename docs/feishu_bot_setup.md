# 飞书 Bot 接入步骤

这个项目的第一版使用 `lark-cli event consume im.message.receive_v1` 监听 Bot 私聊消息。家里电脑不需要暴露公网端口。

## 1. 创建飞书应用

1. 打开飞书开放平台，创建一个企业自建应用。
2. 开启「机器人」能力。
3. 将应用发布到你自己的可见范围。
4. 在飞书客户端里找到这个 Bot，给它发送一条普通文本消息。

## 2. 配置权限

至少需要：

- `im:message.p2p_msg:readonly`：读取你私聊 Bot 的消息事件。
- `im:message`：让 Bot 回复“已加入队列 / 处理完成 / 处理失败”。

事件订阅里开启：

- `im.message.receive_v1`

当前 MVP 建议先用「私聊 Bot」提交链接。群聊入口后续可以加，但权限和消息可见性会更复杂。

## 3. 初始化 lark-cli

在项目根目录运行：

```bash
lark-cli config init --new
```

根据终端提示填入飞书应用的 `App ID` 和 `App Secret`。不要把密钥写进仓库。

检查事件结构：

```bash
lark-cli event schema im.message.receive_v1 --json
```

短时间监听测试：

```bash
python3 scripts/listen_lark.py --timeout 30s
```

监听启动后，向 Bot 私聊发送一条 B 站、YouTube、小宇宙或音频链接。如果成功，会写入 `data/queue.sqlite`，并回复“已加入转写队列”。

## 4. 手机端分享方式

飞书手机端可以先用最简单的办法：

1. 从 Bilibili / YouTube / 小宇宙复制分享链接。
2. 打开飞书，发送给这个 Bot。
3. 家里电脑监听进程自动入队。

后续可以再做 iOS 快捷指令，把“分享链接 -> 发给飞书 Bot”变成一步。

## 5. 常见问题

如果监听启动失败，优先检查：

- 飞书应用是否已经发布到你的可见范围。
- Bot 是否能被你私聊。
- 权限是否包含 `im:message.p2p_msg:readonly` 和 `im:message`。
- 事件订阅是否开启 `im.message.receive_v1`。
- `lark-cli config init --new` 是否使用了同一个应用的 App ID / App Secret。

如果 Bot 能收到消息但不回复，通常是缺 `im:message` 权限。

## 6. 如果卡在事件订阅

`im.message.receive_v1` 在飞书后台通常显示为「接收消息 v2.0」，不是直接显示事件 ID。它要求：

1. 应用已经添加「机器人」能力。
2. 权限管理里已经申请并发布 `im:message.p2p_msg:readonly`。
3. 事件与回调里订阅「消息与群组 / 接收消息 v2.0」。
4. 应用已经发布到你的可见范围，否则飞书客户端里找不到这个 Bot。

如果后台要求选择事件接收方式，优先选「使用长连接接收事件」。本项目的 `lark-cli event consume` 适合长连接方式，不需要你暴露家里电脑端口。

长连接页面点「重新验证」之前，必须先在本机启动一个已经使用同一组 App ID/App Secret 的长连接客户端。也就是说，飞书后台不是在验证某个 URL，而是在检查你的客户端是否已经连上开放平台。

正确顺序：

```bash
lark-cli config init --new
python3 scripts/listen_lark.py --timeout 300s
```

看到终端输出类似 `[event] ready event_key=im.message.receive_v1` 或 `Feishu listener is ready` 后，再回到飞书开放平台点击「重新验证」。如果没有先启动监听进程，后台会显示「连接失败」。

## 6.1 Bot 能找到但没有输入框

如果飞书客户端能打开 Bot 页面，但页面底部没有消息输入框，通常说明它还不能作为“可接收用户消息的机器人会话”使用。优先检查：

1. 「添加应用能力」里确实添加并启用了「机器人」能力，不只是创建了一个应用。
2. 「权限管理」里已申请并发布 `im:message.p2p_msg:readonly`；如果只做群聊 @ 入口，则至少要有 `im:message.group_at_msg:readonly`。
3. 「事件与回调」里已添加「消息与群组 / 接收消息 v2.0」事件。
4. 「版本管理与发布」里创建了新版本，并把这个版本发布到了当前账号所在的可见范围。
5. 发布后重新打开飞书客户端，必要时退出重登或重新搜索应用。

如果这些都检查过仍没有输入框，不要继续卡在私聊入口。先使用下面的「轮询收件箱」模式：建一个普通群，把链接发到群里，本地 worker 用用户身份读取群消息并入队。这个模式不依赖 Bot 私聊输入框。

## 7. 不依赖事件订阅的兜底方案

如果飞书后台暂时无法启用事件订阅，可以先用「轮询收件箱」模式：

1. 在飞书里创建一个普通群，例如「音视频转文档收件箱」。
2. 手机上把链接发到这个群。
3. 本地用用户身份轮询这个群的消息。

先完成 lark-cli 应用配置：

```bash
lark-cli config init --new
```

给用户身份授权。至少需要读取消息；如果搜索群聊拿 `chat_id`，还需要读取群信息：

```bash
lark-cli auth login --scope "im:message:readonly"
lark-cli auth login --scope "im:chat:read"
```

搜索群聊 ID：

```bash
lark-cli im +chat-search --as user --query "音视频转文档收件箱" --format table
```

拿到 `oc_...` 形式的 `chat_id` 后，运行：

```bash
python3 scripts/poll_lark_inbox.py --chat-id "oc_xxx" --as user --once
```

持续轮询：

```bash
python3 scripts/poll_lark_inbox.py --chat-id "oc_xxx" --as user --interval 60
```

这个模式不需要 `im.message.receive_v1` 事件订阅，也不需要先把 Bot 私聊跑通。缺点是轮询有延迟，且默认不会自动在飞书里回复“已入队”；但足够支撑第一版手机分享入口。

# A股持仓飞书自动简报

这是一个真正云端版的每日投资简报方案：用 GitHub Actions 定时运行，不依赖电脑开机、不依赖本地 VPN。

## 运行时间

- 工作日 08:30，北京时间：早盘前简报
- 工作日 17:30，北京时间：收盘复盘

GitHub Actions 的定时任务使用 UTC 时间，所以配置里对应的是：

- 00:30 UTC = 北京时间 08:30
- 09:30 UTC = 北京时间 17:30

## 需要在 GitHub 设置的 Secrets

在你的 GitHub 仓库里进入：

Settings → Secrets and variables → Actions → New repository secret

添加以下 3 个 Secret：

| 名称 | 含义 |
|---|---|
| `OPENAI_API_KEY` | 用于生成报告的 OpenAI API Key |
| `FEISHU_WEBHOOK` | 飞书自定义机器人 Webhook |
| `FEISHU_SECRET` | 飞书机器人签名 Secret |

可选添加一个变量：

Settings → Secrets and variables → Actions → Variables

| 名称 | 默认值 | 含义 |
|---|---|---|
| `OPENAI_MODEL` | `gpt-4.1` | 生成报告使用的模型；如果你的账号支持更新模型，可以改成你想用的模型 |

## 手动测试

上传到 GitHub 并设置 Secrets 后：

1. 打开仓库的 Actions 页面。
2. 选择 `A股持仓飞书自动简报`。
3. 点击 `Run workflow`。
4. 选择 `morning` 或 `evening`。
5. 看飞书是否收到消息。

## 持仓列表

当前默认持仓：

- 兆易创新
- 东南网架
- 西藏矿业
- 川能动力
- 国联股份

如果以后换股，改 `stock_report/config.json` 即可。

## 安全提醒

不要把飞书 Webhook、飞书 Secret、OpenAI API Key 写进代码文件里。请只放在 GitHub Secrets。

这份自动简报用于投资研究和学习，不是持牌投顾服务，也不保证收益。

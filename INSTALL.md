# 微信读书 → Notion 自动同步：安装指南

本项目运行在 GitHub Actions 中。它定时从微信读书云端读取书架、划线、“写想法”和阅读数据，再同步到你自己的 Notion 数据库。手机、平板或网页阅读后，等待下一轮任务即可。

## 你需要准备

- GitHub 账号
- 微信读书 API Key：在微信读书 App 的「我 → 设置 → 微信读书 Skill」获取，或打开[微信读书 Skills 页面](https://weread.qq.com/r/weread-skills)
- Notion integration，以及一个分享给该 integration 的数据库

## 1. 创建自己的 GitHub 仓库

在项目页选择 **Use this template**（如果该选项可用），或 Fork 项目到自己的账号。若希望将项目设为私有，可在创建时选择 Private。不要直接使用项目维护者的 Notion 数据库。

项目源码：[nfwb/weread-notion-sync](https://github.com/nfwb/weread-notion-sync)

## 2. 在 Notion 创建并分享数据库

创建一个数据库，并添加以下属性。名称必须完全一致：

| 属性名 | Notion 类型 | 说明 |
| --- | --- | --- |
| `title` | Title | 书名 |
| `WeRead ID` | Rich text | 稳定的书籍标识，用于避免重复建页 |
| `作者` | Rich text | 作者 |
| `封面` | Files & media | 书籍封面 |
| `阅读进度` | Number，格式设为 Percent | 阅读进度 |
| `开始阅读时间` | Date | 首次观察到已开始阅读的时间 |
| `最后阅读时间` | Date | 微信读书返回的最近阅读时间 |
| `总共阅读时长` | Number | 累计时长，单位秒 |
| `最后同步时间` | Date | 最近一次同步时间 |

在 Notion 的 **Settings → Connections / Integrations** 创建 integration，复制其 secret，然后通过数据库页面右上角的 **… → Connections** 将该数据库分享给 integration。没有这一步，GitHub Actions 无权写入数据库。

## 3. 配置 GitHub Actions

打开自己仓库的 **Settings → Secrets and variables → Actions**。

在 **Secrets** 中新增：

| Name | Value |
| --- | --- |
| `WEREAD_API_KEY` | 你的微信读书 API Key |
| `NOTION_TOKEN` | 第 2 步创建的 Notion integration secret |

在 **Variables** 中新增：

| Name | Value |
| --- | --- |
| `NOTION_DATABASE_ID` | Notion 数据库 ID（从数据库链接中复制，不是父页面 ID） |

不要把 API Key 或 Notion Token 发给 AI、贴在 issue/讨论区或提交到仓库文件。

## 4. 运行首次同步

进入仓库 **Actions → Sync WeRead to Notion → Run workflow** 手动运行。打开运行记录确认结果为绿色成功，并到 Notion 检查是否出现书籍页面、封面、属性、划线和“写想法”。

默认计划每两小时运行一次。GitHub 计划任务可能比设定时间稍晚启动。

## 字段说明与限制

- 阅读进度储存在 `阅读进度` 属性中，页面正文不重复显示进度块。
- 每本书对应一条 Notion 记录；同步用 `WeRead ID` 更新现有记录。
- 从微信读书书架移除书籍不会删除或归档 Notion 页面。
- 微信读书 API 不提供历史上的真实开始阅读日期。若书已开始阅读、但 Notion 尚无日期，首次同步会记下应用首次观察到它的时间，并在之后保留。它不一定等于你实际开始读书的日期。
- `总共阅读时长` 的单位为秒。

## 常见问题

### Actions 报缺少环境变量

检查 Secrets 与 Variables 的名字拼写，并确认配置在运行的那个仓库，而不是源项目仓库。

### Notion 返回权限错误

确认 `NOTION_TOKEN` 属于正确的 integration，并且该 integration 已连接到目标数据库。

### 划线有了，但“写想法”没有

最新版同时读取划线接口 `/book/bookmarklist` 和个人想法接口 `/review/list/mine`。确认你的仓库使用了项目最新版本并重新运行 workflow。

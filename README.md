# nodeseek-bot


-----

# 🤖 NodeSeek 自动签到 Bot (Dockerized)

一个用于 [NodeSeek](https://www.nodeseek.com) 论坛的 Telegram 自动签到 Bot，基于 Python 开发，并采用 Docker 容器化部署，方便快速搭建和管理。

-----

## ✨ 主要功能

  * **自动化签到**: 定时为 NodeSeek 账号进行签到，获取积分。
  * **多账号支持**: 可添加多个 NodeSeek 账号进行管理和签到。
  * **Telegram 交互**:
      * 通过 Telegram 命令添加、查询、删除账号。
      * 手动触发签到或查询签到状态。*
      * 接收每日签到结果通知。
  * **容器化部署**: 基于 Docker，部署简单，环境隔离，易于迁移和管理。

-----

## 📝 更新日志

### 更新计划

1. 计划实现账户与TGid绑定，仅可查询和修改对应TGid所绑定的账户，推送也一样
2. 计划使用MySQL数据库作为数据存储，目前使用json文件存储数据
3. 如果有好的建议欢迎提出~

### v0.1.3（2025-07-25） 更新 

1. 优化并整理了代码
2. 修复了定时自动签到无法推送的问题
3. 修改了整体的签到判断逻辑，签到失败后会执行/check重新判断真实签到情况并推送结果
4. 取消了重试机制

### v0.1.2（2025-07-24） 更新 

1. 优化代码
2. 修改了Telegram推送模式，由 <群组> ==> <用户>
3. 修改了/start指令，现在会同时订阅推送
4. 增加了/help，/push指令
5. 修改了/check判定逻辑，现在会正确判断真实签到情况

### v0.1.1（2025-07-23） 更新

1. 优化代码
2. 完善telegram 命令交互功能

### v0.1.0（2025-07-22） 更新 

1. 完成基础自动签到功能
2. 完成Telegram 基本的命令交互与推送功能

> 所有历史更新可查看：[更新历史记录](https://github.com/qianhu111/nodeseek-bot/commits/main)

-----

## 🚀 快速开始

### 1\. 克隆仓库

首先，将本项目克隆到你的本地机器。

```bash
git clone https://github.com/qianhu111/nodeseek-bot.git
cd nodeseek-bot
```

### 2\. 配置环境变量

在项目根目录下创建一个名为 `.env` 的文件（如果不存在的话），并填入你的 Telegram Bot API Token、你的 Telegram 用户 ID 和管理员 ID。

**`.env` 文件示例:**

```
# .env 文件：用于存储 Bot 运行所需的环境变量

# 你的 Telegram Bot Token (必填)
TG_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN

# 用于接收签到通知的 Telegram 用户/群组 ID (必填)
TG_USER_ID=YOUR_TELEGRAM_USER_OR_GROUP_ID

# 拥有管理权限的 Telegram 用户 ID (可选，建议设置)
# 此ID的用户可以执行 /force, /delete 等敏感操作
TG_ADMIN_ID=YOUR_TELEGRAM_ADMIN_ID

# 签到模式（可选，默认为 false，即非默认模式）
# 如果设置为 true，Bot 将在启动时尝试立即签到，并在后续按计划执行
# DEFAULT_MODE=true
```

  * **如何获取 Bot Token**: 在 Telegram 中联系 `@BotFather`，按照指引创建新的 Bot 即可获得 Token。
  * **如何获取用户/管理员 ID**: 在 Telegram 中转发一条消息给 `@userinfobot` 或 `@getidsbot`，它会告诉你你的用户 ID。对于群组 ID，将 Bot 添加到群组后，转发群组内任意消息给 `@userinfobot` 即可获取群组 ID。

### 3\. 构建并运行 Docker 容器

本项目已预构建 Docker 镜像并发布到 Docker Hub，你可以直接拉取并运行。

```bash
# 从 Docker Hub 拉取最新镜像
docker pull qianhu111/nodeseek-bot:latest

# 使用 docker-compose 启动容器
# 确保你的 .env 文件已配置正确
docker compose up -d
```

**或者，如果你想自己重新构建镜像（例如修改了代码）：**

使用项目提供的 `build.sh` 脚本可以方便地进行管理：

```bash
./build.sh
```

运行脚本后，选择菜单中的 **`6. 重新构建镜像并启动`**，等待构建和启动完成。

### 4\. 使用 Bot

容器成功启动后，你的 Telegram Bot 就会上线。

1.  打开 Telegram，搜索你的 Bot 名称。
2.  发送 `/start` 命令，Bot 会回复欢迎信息和可用指令列表。
3.  根据提示，使用 `/add` 命令添加你的 NodeSeek 账号。

-----

## ⚙️ 管理命令

本项目提供了一个 `build.sh` 脚本，可以帮助你轻松管理 Docker 容器的生命周期。

```bash
./build.sh
```

**菜单选项说明:**

  * **1. 启动容器**: 启动已停止的 Bot 容器。
  * **2. 重启容器**: 重启正在运行的 Bot 容器，用于应用更新或问题排查。
  * **3. 停止容器**: 停止 Bot 容器的运行。
  * **4. 查看容器状态**: 查看 Bot 容器的当前运行状态（是否运行、端口映射等）。
  * **5. 查看容器日志**: 实时跟踪 Bot 的运行日志，方便调试和监控签到情况。
  * **6. 重新构建镜像并启动**: 当你更新了代码、`requirements.txt` 或 `Dockerfile` 后，使用此选项重新构建镜像并启动新的容器。
  * **7. 修改 .env 配置文件**: 在终端中方便地修改 Bot 的配置，修改后可能需要重启容器才能生效。
  * **8. 删除容器和镜像**: 删除 Bot 的运行容器和本地已构建的 Docker 镜像。
  * **9. 清理未使用的 Docker 数据**: 清理 Docker 产生的悬空镜像、停止的容器、未使用的网络等，释放磁盘空间。
  * **10. \!\!\! 彻底清空 Docker (危险操作) \!\!\!**: 删除 Docker 内所有容器、镜像、网络、卷及缓存数据。**请谨慎使用，此操作无法恢复！**

-----

## 💬 Telegram Bot 指令

在 Telegram 中向你的 Bot 发送以下指令：

  * `/start`: 获取欢迎信息和指令列表。
  * `/add <账号名称> <cookie>`: 添加或更新一个 NodeSeek 账号。例如：`/add MyAccount your_cookie_string_here`
  * `/list`: 查看所有已添加到 Bot 的 NodeSeek 账号。
  * `/last`: 查看最近一次所有账号的签到结果摘要。
  * `/check`: **(仅管理员可用)**查询所有账号当前的签到状态。
  * `/check <账号名称>`: 查询指定 NodeSeek 账号的签到状态。
  * `/force`: **(仅管理员可用)** 立即触发所有账号的签到过程。
  * `/retry <账号名称>`: 手动为指定账号进行补签。
  * `/delete <账号名称>`: **(仅管理员可用)** 从 Bot 中删除一个已添加的 NodeSeek 账号。
  * `/push <消息内容>`: **(仅管理员可用)** 向已订阅 Bot 的用户推送消息。
  * `/help`: 帮助信息。

-----

## 🤝 贡献

如果你有任何改进建议、新功能想法或发现 Bug，欢迎通过提交 Issue 或 Pull Request 的方式参与贡献！

-----

## 🙏 感谢名单

感谢以下人员和项目为本 Bot 提供灵感与帮助：

* @qianhu111 - 项目作者和主要开发者。

* @white_ashes - 提供脚本样本。

* @SerokVip - 提供签到逻辑思路和样本。

* Telegram群组《TG 白嫖大队》 - 帮助测试。

-----

## 📄 许可证

本项目采用 [MIT 许可证](https://opensource.org/licenses/MIT) 发布。

-----

## 🌟 Star 支持

如果你喜欢这个项目，欢迎点个 ⭐Star 支持一下！

[![Star History Chart](https://api.star-history.com/svg?repos=qianhu111/nodeseek-bot&type=Date)](https://www.star-history.com/#qianhu111/nodeseek-bot&Date)

-----

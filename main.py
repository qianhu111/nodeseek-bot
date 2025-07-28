import os
import json
import requests
import random
import time
import cloudscraper
import pytz
import asyncio
from datetime import datetime, timedelta
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import re # 用于正则表达式匹配签到收益
import traceback  # 新增，打印完整异常堆栈
from dateutil.parser import parse
import logging

# === 配置区域 ===
ACCOUNTS_FILE = "data/accounts.json"  # 存储账号信息的文件路径
SUBSCRIBERS_FILE = "data/subscribers.json"
SIGNIN_LOG_FILE = "data/last_signin.json"
CHINA_TZ = pytz.timezone("Asia/Shanghai")  # 使用上海时区
DEFAULT_MODE = (os.getenv("DEFAULT", "false").lower() == "true")  # 签到模式
ADMIN_USER_ID = int(os.getenv("TG_ADMIN_ID", "0"))  # 管理员TG ID
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# === 全局变量 ===
last_signin_result = ""  # 最近签到结果缓存
last_signin_time = None  # 最近签到时间缓存
pending_push = set()  # 记录等待输入推送内容的用户 ID 集合
is_signing_in = False  # 全局变量
tasks: list[asyncio.Task] = []  # 保存任务引用

# === 工具函数 ===
def get_now():
    """
    获取当前上海时区时间
    """
    return datetime.now(CHINA_TZ)

def wrap_md_code(text):
    return f"`{escape_markdown(text)}`"

def load_accounts():
    """
    从文件加载账号列表，返回列表格式
    """
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_accounts(accounts):
    """
    保存账号列表到文件
    """
    os.makedirs(os.path.dirname(ACCOUNTS_FILE), exist_ok=True)
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)

accounts = load_accounts()

def load_subscribers():
    if os.path.exists(SUBSCRIBERS_FILE):
        with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_subscribers(subscribers):
    os.makedirs(os.path.dirname(SUBSCRIBERS_FILE), exist_ok=True)
    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
        json.dump(subscribers, f, ensure_ascii=False, indent=2)

subscribers = load_subscribers()

def add_subscriber(user_id: int):
    if user_id not in subscribers:
        subscribers.append(user_id)
        save_subscribers(subscribers)

def parse_cookie(cookie_str):
    """
    将cookie字符串解析为字典
    """
    cookie_dict = {}
    for item in cookie_str.strip().split(';'):
        if '=' in item:
            k, v = item.split('=', 1)
            cookie_dict[k.strip()] = v.strip()
    return cookie_dict

def create_scraper():
    """
    创建cloudscraper实例，用于带浏览器伪装的请求
    """
    return cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )

def update_last_signin(result: str):
    """
    更新最近签到记录
    """
    global last_signin_result, last_signin_time
    last_signin_result = result
    last_signin_time = get_now()
    # 判断状态写入日志
    record_signin("success" if "成功" in result else "fail", result)

def load_signin_logs():
    try:
        with open(SIGNIN_LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except FileNotFoundError:
        logs = []
    return logs

def save_signin_logs(logs):
    # 保留最近 7 天内的数据
    threshold = get_now() - timedelta(days=7)
    logs = [
        entry for entry in logs
        if parse(entry["time"]) >= threshold
    ]
    os.makedirs(os.path.dirname(SIGNIN_LOG_FILE), exist_ok=True)
    with open(SIGNIN_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

def record_signin(status: str, message: str):
    """
    记录签到日志到 JSON 文件
    status: "success" 或 "fail"
    message: 提示信息
    """
    now_str = get_now().strftime("%Y-%m-%d %H:%M:%S %z")  # 带时区
    logs = load_signin_logs()
    logs.append({
        "time": now_str,
        "status": status,
        "message": message.strip()
    })
    save_signin_logs(logs)

def escape_markdown(text: str) -> str:
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    for ch in escape_chars:
        text = text.replace(ch, f'\\{ch}')
    return text

def handle_task_exception(task):
    try:
        task.result()
    except Exception as e:
        logger.error(f"[后台任务异常] {e}")
        logger.debug(traceback.format_exc())

def create_tracked_task(coro):
    task = asyncio.create_task(coro)
    task.add_done_callback(handle_task_exception)
    tasks.append(task)
    return task

# === 核心签到逻辑 ===

def check_signin_status(scraper, account_name, cookie_dict):
    """
    修改为调用api/attendance并根据其响应判断是否已签到。
    """
    url_sign = "https://www.nodeseek.com/api/attendance?random=false"

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Content-Length': '0',
        'Origin': 'https://www.nodeseek.com',
        'Referer': 'https://www.nodeseek.com/board',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
    }

    try:
        response = scraper.post(url_sign, headers=headers, cookies=cookie_dict, timeout=30)
        # 即使是错误状态码，也尝试解析JSON获取message
        if response.status_code != 200:
            try:
                error_data = response.json()
                msg_raw = error_data.get("message") or error_data.get("Message") or f"HTTP {response.status_code} 错误"
                if "Unauthorized" in msg_raw or response.status_code == 401:
                    return f"❌ `{wrap_md_code(account_name)}` Cookie失效或不正确"
                elif "重复" in msg_raw or "请勿重复" in msg_raw:
                    return f"✅ `{wrap_md_code(account_name)}` 已签到 (通过 /check 触发了重复签到)"
                else:
                    return f"❌ `{wrap_md_code(account_name)}` 状态检查失败: {msg_raw}"
            except json.JSONDecodeError:
                return f"❌ `{wrap_md_code(account_name)}` 状态检查失败，HTTP {response.status_code}，响应无法解析。"
        
        # 200 OK 响应处理
        json_data = response.json()
        msg_raw = json_data.get("message") or json_data.get("Message") or "未知消息"

        if "签到收益" in msg_raw:
            # 如果是首次签到成功，则表示之前未签到
            return f"❌ `{wrap_md_code(account_name)}` 未签到 (通过 /check 触发了首次签到)"
        elif "重复" in msg_raw or "请勿重复" in msg_raw:
            return f"✅ `{wrap_md_code(account_name)}` 已签到"
        elif "Unauthorized" in msg_raw:
            return f"❌ `{wrap_md_code(account_name)}` Cookie失效或不正确"
        else:
            return f"❌ `{wrap_md_code(account_name)}` 状态未知: {msg_raw}"

    except requests.exceptions.Timeout:
        return f"❌ `{wrap_md_code(account_name)}` 状态检查超时。"
    except requests.exceptions.RequestException as e:
        return f"❌ `{wrap_md_code(account_name)}` 状态检查网络异常: {e}"
    except json.JSONDecodeError:
        return f"❌ `{wrap_md_code(account_name)}` 状态检查响应解析失败。"
    except Exception as e:
        logger.error("详细错误信息", exc_info=True)  # 打印完整错误堆栈到控制台
        return f"❌ `{wrap_md_code(account_name)}` 状态检查发生未知错误: {e}"
    

def sign_in_single_account(account_name, cookie):
    """
    单账号签到逻辑，完全模拟JS脚本，直接调用api/attendance并根据返回message判断结果。
    不再预先调用 api/user。
    """
    url_sign = "https://www.nodeseek.com/api/attendance?random=false"

    scraper = create_scraper()
    cookie_dict = parse_cookie(cookie)

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Content-Length': '0', # POST请求体为空，所以长度为0
        'Origin': 'https://www.nodeseek.com',
        'Referer': 'https://www.nodeseek.com/board',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
    }

    try:
        resp_sign = scraper.post(url_sign, headers=headers, cookies=cookie_dict, timeout=30)
        resp_sign.raise_for_status() # 对4xx/5xx状态码抛出HTTPError

        json_data = resp_sign.json()
        # 兼容 message 和 Message 字段
        msg_raw = json_data.get("message") or json_data.get("Message") or "未知消息"
        
        # 签到成功判断
        if "签到收益" in msg_raw:
            match = re.search(r'(\d+)', msg_raw) # 使用正则表达式提取数字
            amount = match.group(1) if match else "未知"
            msg = f"✅ 账号 `{wrap_md_code(account_name)}` 签到成功，收益 {amount} 个🍗"
            print(msg)
            return msg
        # 重复签到判断：JS脚本就是通过这里判断已签到的
        elif "重复" in msg_raw or "请勿重复" in msg_raw:
            msg = f"⚠️ 账号 `{wrap_md_code(account_name)}` 今天已签到（重复签到）。"
            print(msg)
            return msg
        # Cookie失效判断：虽然不调用api/user，但api/attendance也可能返回类似信息
        elif "Unauthorized" in msg_raw or resp_sign.status_code == 401:
            msg = f"❌ 账号 `{wrap_md_code(account_name)}` Cookie已失效或不正确。"
            print(msg)
            return msg
        # 其他失败情况
        else:
            msg = f"❌ 账号 `{wrap_md_code(account_name)}` 签到失败: {msg_raw}"
            print(msg)
            return msg

    except requests.exceptions.HTTPError as e:
        # 处理HTTP错误状态码 (例如401 Unauthorized, 403 Forbidden等)
        try:
            # 尝试解析错误响应中的JSON消息
            error_data = e.response.json()
            error_message = error_data.get("message") or error_data.get("Message") or f"HTTP {e.response.status_code} 错误"
            
            # 在HTTPError中也判断是否是Cookie失效
            if "Unauthorized" in error_message or e.response.status_code == 401:
                msg = f"❌ 账号 `{wrap_md_code(account_name)}` Cookie已失效或不正确。"
            else:
                msg = f"❌ 账号 `{wrap_md_code(account_name)}` 签到请求失败: {error_message}"
        except json.JSONDecodeError:
            msg = f"❌ 账号 `{wrap_md_code(account_name)}` 签到请求失败，HTTP {e.response.status_code}，响应无法解析。"
        print(msg)
        return msg
    except requests.exceptions.Timeout:
        msg = f"❌ 账号 `{wrap_md_code(account_name)}` 签到请求超时。"
        print(msg)
        return msg
    except requests.exceptions.RequestException as e:
        msg = f"❌ 账号 `{wrap_md_code(account_name)}` 签到请求网络异常: {e}"
        print(msg)
        return msg
    except json.JSONDecodeError:
        msg = f"❌ 账号 `{wrap_md_code(account_name)}` 签到响应解析失败。"
        print(msg)
        return msg
    except Exception as e:
        msg = f"❌ 账号 `{wrap_md_code(account_name)}` 签到发生未知错误: {e}"
        print(msg)
        logger.error("详细错误信息", exc_info=True)  # 打印完整错误堆栈到控制台
        return msg

async def sign_in_all_accounts_async():
    """
    异步批量签到所有账号，加入重试机制，并防止重复签到。
    """
    global last_signin_result, last_signin_time, is_signing_in
    if is_signing_in:
        print("⚠️ 正在执行签到任务，跳过本次触发。")
        return

    is_signing_in = True
    try:
        if not accounts:
            print("⚠️ 无账号可签到")
            return

        summary = []
        for acc in accounts:
            delay_sec = random.randint(3, 6)
            print(f"⏳ {acc['name']} 延迟 {delay_sec}s 后签到...")
            await asyncio.sleep(delay_sec)

            # 第一次尝试
            result = await asyncio.to_thread(sign_in_single_account, acc['name'], acc['cookie'])

            # 如果出现错误，尝试判断是否需要重试
            if result.startswith("❌") or "失败" in result or "异常" in result:
                print(f"⚠️ 账号 {acc['name']} 第一次签到失败，准备重试...")
                await asyncio.sleep(3)  # 可调，避免立即连发请求
                retry_result = await asyncio.to_thread(sign_in_single_account, acc['name'], acc['cookie'])

                # 标记为“重试成功”或“重试失败”
                if not retry_result.startswith("❌"):
                    result = f"✅（重试成功）{retry_result}"
                else:
                    result = f"❌（重试失败）{retry_result}"

            summary.append(result)

        # 缓存结果
        last_signin_time = get_now()
        last_signin_result = "\n".join(summary)

        # 只推送一次，不再重复触发签到
        await send_tg_notification_async(f"📋 *NodeSeek 签到完成*\n\n{last_signin_result}")
    finally:
        is_signing_in = False

# === Telegram Bot 命令函数 ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    add_subscriber(user_id)

    await update.message.reply_text(
        "🤖 *欢迎使用 NodeSeek 签到 Bot！*\n\n"
        "📌 *指令说明:*\n"
        "➕ `/add <账号名称> <cookie>` 添加新账号\n"
        "📋 `/list` 查看所有账号\n"
        "📅 `/last` 查看最近签到记录\n"
        "🔍 `/check <账号名称>` 查询账号状态\n"
        "⚡ `/force` 立即签到（仅管理员）\n"
        "🔄 `/retry <账号名称>` 手动补签该账号\n"
        "🗑 `/delete <账号名称>` 删除账号（仅管理员）\n"
        "🛎️ `/help` 帮助信息",
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /add <账号名称> <cookie>：添加或更新账号，后台启动签到
    """
    try:
        if len(context.args) < 2:
            await update.message.reply_text("❌ 格式错误，请使用: `/add <账号名称> <cookie>`", parse_mode="Markdown")
            return

        name = context.args[0]
        cookie = " ".join(context.args[1:]).strip()

        found = False
        for account in accounts:
            if account["name"] == name:
                account["cookie"] = cookie
                save_accounts(accounts)
                found = True
                await update.message.reply_text(
                    f"✅ *账号 {name} 已更新*\n正在为该账号签到，请稍候...",
                    parse_mode="Markdown"
                )
                task = create_tracked_task(sign_in_and_report(update, context, name, cookie))
                break

        if not found:
            accounts.append({"name": name, "cookie": cookie})
            save_accounts(accounts)
            await update.message.reply_text(
                f"✅ *已添加账号:* `{name}`\n正在为该账号签到，请稍候...",
                parse_mode="Markdown"
            )
            task = create_tracked_task(sign_in_and_report(update, context, name, cookie))

    except Exception as e:
        logger.error("详细错误信息", exc_info=True)  # 打印完整错误堆栈到控制台
        await update.message.reply_text(f"⚠️ 添加账号时出错: `{e}`", parse_mode="Markdown")

# 辅助函数，用于在add命令后立即执行签到并报告结果
async def sign_in_and_report(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str, cookie: str):
    """
    在add命令后立即为单个账号签到并向用户报告结果。
    """
    print(f"正在为账号 {name} 执行初次签到...")
    # 这里直接调用 sign_in_single_account_with_retry，它现在会直接尝试签到
    result_message = await asyncio.to_thread(sign_in_single_account, name, cookie)
    await update.message.reply_text(result_message, parse_mode="Markdown")
    print(f"账号 {name} 初次签到完成，结果已报告。")

async def list_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /list：查看所有添加的账号
    """
    if not accounts:
        await update.message.reply_text("⚠️ 当前没有添加任何账号。")
        return

    lines = [f"📋 *已添加账号* ({len(accounts)} 个):"]
    for i, acc in enumerate(accounts, 1):
        lines.append(f"{i}. `{wrap_md_code(acc['name'])}`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /last：查看最近签到记录
    """
    logs = load_signin_logs()

    if not logs and last_signin_time is None:
        await update.message.reply_text("⚠️ 还没有执行过签到。")
        return

    # 优先用日志里最新的，如果日志为空，则用全局变量的时间和结果
    if logs:
        latest = logs[-1]  # 最近一次记录
        time_str = latest['time']
        status_str = '✅ 成功' if latest['status'] == 'success' else '❌ 失败'
        message_str = latest['message']
    else:
        # last_signin_time 是 datetime 类型，格式化为字符串
        time_str = last_signin_time.strftime("%Y-%m-%d %H:%M:%S %z") if last_signin_time else "未知时间"
        status_str = '未知状态'
        message_str = last_signin_result or "无内容"

    reply = (
        f"📅 *最近签到时间:*\n{time_str}\n\n"
        f"📋 *状态:*\n{status_str}\n\n"
        f"📝 *结果:*\n{message_str}"
    )

    await send_long_message(update.effective_chat.id, reply, context, parse_mode="Markdown")

async def check_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /check 或 /check <账号名称>：查询所有账号签到状态或指定账号签到状态。
    此函数现在将调用 api/attendance，并从其响应中判断是否已签到。
    """
    user_id = update.effective_user.id # 获取当前用户的ID

    if not accounts:
        await update.message.reply_text("⚠️ 当前没有任何账号，请先添加。")
        return

    lines = ["🔍 *账号签到状态:*"]
    scraper = create_scraper() 

    # 判断是查询单个账号还是所有账号
    if context.args:
        # 查询单个账号：所有人可用，无需权限检查
        account_name_to_check = context.args[0]
        found_account = None
        for acc in accounts:
            if acc['name'] == account_name_to_check:
                found_account = acc
                break
        
        if found_account:
            name = found_account['name']
            cookie_dict = parse_cookie(found_account['cookie'])
            status_message = await asyncio.to_thread(check_signin_status, scraper, name, cookie_dict)
            lines.append(status_message)
        else:
            lines.append(f"❌ 找不到名为 `{wrap_md_code(account_name_to_check)}` 的账号。")
    else:
        # 查询所有账号：仅管理员可用
        if user_id != ADMIN_USER_ID:
            await update.message.reply_text("❌ 你无权限使用该指令查询所有账号状态。请使用 `/check <账号名称>` 查询指定账号。", parse_mode="Markdown")
            return
        
        for acc in accounts:
            name = acc['name']
            cookie_dict = parse_cookie(acc['cookie'])
            status_message = await asyncio.to_thread(check_signin_status, scraper, name, cookie_dict)
            lines.append(status_message)

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def force_signin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /force：立即签到所有账号，仅管理员可用
    """
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("❌ 你无权限使用该指令。")
        return
    
    # ✅ 添加防止重复执行的判断
    if is_signing_in:
        await update.message.reply_text("⚠️ 当前正在执行签到任务，请稍后再试。")
        return
    
    await update.message.reply_text("⚡ 开始立即签到，请稍候...")
    try:
        await sign_in_all_accounts_async()
        update_last_signin("✅ 所有账号已完成签到")
        await update.message.reply_text("✅ 所有账号已完成签到")

        # ✅ 推送给所有订阅者
        for uid in subscribers:
            try:
                await context.bot.send_message(chat_id=uid, text="✅ 签到成功！可以去看看收益了～")
            except Exception as e:
                print(f"❌ 无法向用户 {uid} 推送消息: {e}")
                logger.error("详细错误信息", exc_info=True)  # 打印完整错误堆栈到控制台
    except Exception as e:
        logger.error("详细错误信息", exc_info=True)  # 打印完整错误堆栈到控制台
        errmsg = f"⚠️ 签到失败: {e}"
        update_last_signin(errmsg)
        await update.message.reply_text(errmsg)

async def retry_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /retry <账号名称>：手动补签指定账号
    """
    if len(context.args) < 1:
        await update.message.reply_text("❌ 格式错误，请使用: `/retry <账号名称>`", parse_mode="Markdown")
        return

    name = context.args[0]
    account = None
    for acc in accounts:
        if acc["name"] == name:
            account = acc
            break

    if not account:
        await update.message.reply_text(f"❌ 找不到名为 `{name}` 的账号。", parse_mode="Markdown")
        return

    await update.message.reply_text(f"🔄 开始为账号 `{name}` 补签，请稍候...", parse_mode="Markdown")
    # 直接调用带重试的签到函数
    result = await asyncio.to_thread(sign_in_single_account, name, account["cookie"])
    await update.message.reply_text(result, parse_mode="Markdown")

async def delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /delete <账号名称>：删除指定账号，仅管理员可用
    """
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("❌ 你无权限使用该指令。")
        return

    if len(context.args) < 1:
        await update.message.reply_text("❌ 格式错误，请使用: `/delete <账号名称>`", parse_mode="Markdown")
        return

    name = context.args[0]
    global accounts

    for i, acc in enumerate(accounts):
        if acc["name"] == name:
            del accounts[i]
            save_accounts(accounts)
            await update.message.reply_text(f"✅ 已删除账号: `{name}`", parse_mode="Markdown")
            return

    await update.message.reply_text(f"❌ 找不到名为 `{name}` 的账号。", parse_mode="Markdown")

async def push(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /push：触发广播模式，等待用户输入内容后群发
    """
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("❌ 你无权限使用该指令。")
        return

    chat_id = update.effective_chat.id
    pending_push.add(chat_id)
    await update.message.reply_text("📝 请发送你要推送的消息内容（支持多行）。")

async def handle_pending_push_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if chat_id not in pending_push or user_id != ADMIN_USER_ID:
        return  # 不是在等待状态或不是管理员，忽略

    pending_push.remove(chat_id)  # 清除等待状态
    message = update.message.text.strip()
    success_count = 0
    fail_count = 0

    for sub_id in subscribers:
        try:
            await context.bot.send_message(chat_id=sub_id, text=message, parse_mode="Markdown")
            success_count += 1
            if success_count % 20 == 0:
                await asyncio.sleep(1)  # 每 20 次暂停 1 秒
        except Exception as e:
            print(f"推送消息失败给用户 {sub_id}: {e}")
            logger.error("详细错误信息", exc_info=True)  # 打印完整错误堆栈到控制台
            fail_count += 1

    await update.message.reply_text(f"✅ 推送完成，成功: {success_count}，失败: {fail_count}")

# === Telegram 推送设置 ===

async def send_long_message(chat_id, text, context, parse_mode=None):
    """
    发送超长消息分段  以 4096 字符为最大长度进行切分
    """
    MAX_LEN = 4000
    for i in range(0, len(text), MAX_LEN):
        await context.bot.send_message(chat_id=chat_id, text=text[i:i+MAX_LEN], parse_mode="Markdown")

async def send_tg_notification_async(message):
    TELEGRAM_TOKEN = os.getenv("TG_BOT_TOKEN")
    if not TELEGRAM_TOKEN:
        print("⚠️ Telegram配置缺失，无法推送通知。")
        return

    from telegram import Bot
    from telegram.error import TelegramError

    bot = Bot(token=TELEGRAM_TOKEN)
    subscribers = load_subscribers()  # 🔔 确保已加载订阅者
    success_count = 0  # ✅ 初始化计数器

    for user_id in subscribers:
        try:
            await bot.send_message(chat_id=user_id, text=message, parse_mode="Markdown")
            success_count += 1
            if success_count % 20 == 0:
                await asyncio.sleep(1)  # 每 20 次暂停 1 秒
        except TelegramError as e:
            print(f"❌ 向用户 {user_id} 推送失败: {e}")

# === 定时循环任务 ===

async def signin_loop(app):
    while True:
        now = get_now()
        next_hour = random.randint(7, 8)
        next_minute = random.randint(0, 59)
        next_run = now.replace(hour=next_hour, minute=next_minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)

        wait_sec = (next_run - now).total_seconds()
        print(f"⏰ 距离下次签到还有 {int(wait_sec//3600)}小时 {int((wait_sec%3600)//60)}分")
        await asyncio.sleep(wait_sec)
        await sign_in_all_accounts_async()

# === 启动时任务 ===

async def on_startup(app):
    await app.bot.set_my_commands([
        BotCommand("start", "启动Bot"),
        BotCommand("add", "添加账号"),
        BotCommand("list", "查看所有账号"),
        BotCommand("last", "查看最近签到记录"),
        BotCommand("check", "查询签到状态"),
        BotCommand("force", "立即签到（管理员）"),
        BotCommand("retry", "补签指定账号"),
        BotCommand("delete", "删除账号（管理员）"),
        BotCommand("push", "广播消息（管理员）"),
        BotCommand("help", "帮助信息"),
    ])
    return [asyncio.create_task(signin_loop(app))]

# === 入口启动 ===

if __name__ == "__main__":
    # 🚨 不要使用 asyncio.run()，直接同步 run_polling
    TELEGRAM_TOKEN = os.getenv('TG_BOT_TOKEN')
    if not TELEGRAM_TOKEN:
        raise RuntimeError("环境变量 TG_BOT_TOKEN 未设置")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("list", list_accounts))
    app.add_handler(CommandHandler("delete", delete_account))
    app.add_handler(CommandHandler("last", last))
    app.add_handler(CommandHandler("check", check_accounts))
    app.add_handler(CommandHandler("force", force_signin))
    app.add_handler(CommandHandler("retry", retry_account))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("push", push))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_pending_push_message))

    app.post_init = on_startup

    print("✅ Telegram Bot 启动成功，监听中...")
    app.run_polling()

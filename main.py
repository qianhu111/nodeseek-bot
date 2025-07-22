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
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

ACCOUNTS_FILE = "data/accounts.json"
CHINA_TZ = pytz.timezone("Asia/Shanghai")

last_signin_result = ""
last_signin_time = None

def get_now():
    return datetime.now(CHINA_TZ)

def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_accounts(accounts):
    os.makedirs(os.path.dirname(ACCOUNTS_FILE), exist_ok=True)
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)

accounts = load_accounts()

async def send_long_message(chat_id, text, context):
    MAX_LEN = 4000
    for i in range(0, len(text), MAX_LEN):
        await context.bot.send_message(chat_id=chat_id, text=text[i:i+MAX_LEN])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ 欢迎使用 NodeSeek 签到 Bot！\n"
        "📌 指令说明:\n"
        "/add <账号名称> <cookie> 添加新账号\n"
        "/last 查看最近一次签到记录"
    )

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) < 2:
            await update.message.reply_text("❌ 格式错误，请使用: /add <账号名称> <cookie>")
            return

        name = context.args[0]
        cookie = " ".join(context.args[1:]).strip()

        accounts.append({"name": name, "cookie": cookie})
        save_accounts(accounts)

        await update.message.reply_text(f"✅ 已添加账号: {name}\n正在为该账号签到，请稍候...")

        # 后台执行签到，避免阻塞
        asyncio.create_task(sign_in_and_report(update, context, name, cookie))

    except Exception as e:
        await update.message.reply_text(f"⚠️ 添加账号时出错: {e}")

async def sign_in_and_report(update, context, name, cookie):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, sign_in_single_account, name, cookie)
    await update.message.reply_text(result)

async def last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_signin_result, last_signin_time
    if last_signin_result:
        reply = f"📅 最近签到时间: {last_signin_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n{last_signin_result}"
        await send_long_message(update.effective_chat.id, reply, context)
    else:
        await update.message.reply_text("⚠️ 还没有执行过签到。")

def check_signin_status(scraper, cookie_dict):
    url = "https://www.nodeseek.com/api/user"
    try:
        response = scraper.get(url, cookies=cookie_dict, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get("attendance", {}).get("attendedToday", False)
    except Exception as e:
        print(f"检查签到状态出错: {e}")
    return False

def sign_in_single_account(account_name, cookie):
    url = 'https://www.nodeseek.com/api/attendance?random=false'
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    cookie_dict = {}
    for item in cookie.strip().split(';'):
        if '=' in item:
            k, v = item.split('=', 1)
            cookie_dict[k.strip()] = v.strip()

    if check_signin_status(scraper, cookie_dict):
        msg = f"✅ 账号 {account_name} 今天已签到，跳过。"
        print(msg)
        return msg

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Content-Length': '0',
        'Origin': 'https://www.nodeseek.com',
        'Referer': 'https://www.nodeseek.com/board',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
    }

    try:
        response = scraper.post(url, headers=headers, cookies=cookie_dict, timeout=30)
        if response.status_code == 200:
            msg = f"✅ 账号 {account_name} 签到成功"
        else:
            msg = f"❌ 账号 {account_name} 签到失败，响应：{response.text[:100]}"
        print(msg)
        return msg
    except Exception as e:
        msg = f"❌ 账号 {account_name} 签到异常: {e}"
        print(msg)
        return msg

def send_tg_notification(message):
    TELEGRAM_TOKEN = os.getenv('TG_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TG_USER_ID')

    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            params = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
            response = requests.get(url, params=params)
            if response.status_code == 200:
                print("Telegram通知发送成功")
            else:
                print(f"通知发送失败: {response.status_code} {response.text}")
        except Exception as e:
            print(f"通知发送异常: {e}")
    else:
        print("Telegram配置不完整，无法发送通知")

def sign_in_all_accounts():
    global last_signin_result, last_signin_time

    if not accounts:
        print("无账号可签到")
        return

    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )

    summary = []

    for account in accounts:
        name = account["name"]
        cookie = account["cookie"]

        delay_sec = random.randint(120, 300)
        delay_msg = f"⏳ 账号 {name} 延迟 {delay_sec // 60} 分 {delay_sec % 60} 秒后签到..."
        print(delay_msg)
        summary.append(delay_msg)

        time.sleep(delay_sec)

        msg = sign_in_single_account(name, cookie)
        summary.append(msg)

    last_signin_time = get_now()
    last_signin_result = "\n".join(summary)
    send_tg_notification(f"NodeSeek 签到完成:\n\n{last_signin_result}")

async def signin_loop(app):
    while True:
        now = get_now()
        next_hour = random.randint(7, 8)
        next_minute = random.randint(0, 59)
        next_run = now.replace(hour=next_hour, minute=next_minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)

        wait_sec = (next_run - now).total_seconds()
        print(f"距离下次签到还有 {int(wait_sec//3600)}小时 {int((wait_sec%3600)//60)}分")
        await asyncio.sleep(wait_sec)

        try:
            await asyncio.to_thread(sign_in_all_accounts)
        except Exception as e:
            err_msg = f"签到异常: {e}"
            print(err_msg)
            send_tg_notification(err_msg)

async def main():
    TELEGRAM_TOKEN = os.getenv('TG_BOT_TOKEN')
    if not TELEGRAM_TOKEN:
        raise RuntimeError("环境变量 TG_BOT_TOKEN 未设置")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("last", last))

    commands = [
        BotCommand("start", "启动Bot"),
        BotCommand("add", "添加账号"),
        BotCommand("last", "查看最近签到记录"),
    ]

    await app.bot.set_my_commands(commands)

    print("Telegram Bot启动成功，监听命令中...")

    # 注册一个应用启动后调用的回调，在里面创建后台任务
    async def on_startup(app):
        app.create_task(signin_loop(app))

    app.post_init = on_startup

    await app.run_polling()

if __name__ == "__main__":
    import asyncio

    # 不用 asyncio.run 了，直接调用 run_polling 入口
    from telegram.ext import ApplicationBuilder

    TELEGRAM_TOKEN = os.getenv('TG_BOT_TOKEN')
    if not TELEGRAM_TOKEN:
        raise RuntimeError("环境变量 TG_BOT_TOKEN 未设置")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("last", last))

    async def on_startup(app):
        app.create_task(signin_loop(app))

    app.post_init = on_startup

    # 直接同步调用 run_polling，run_polling内部会管理事件循环
    app.run_polling()

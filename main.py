print(">>> DEBUG: SCRIPT STARTED FROM TOP", flush=True)
import os
import sqlite3
from threading import Thread
import time
import uuid
import math
from html import escape
import requests
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
import telebot.types as types
from flask import Flask
from datetime import datetime

app = Flask('')

@app.route('/')
def home():
  return "Bot is alive!"

def run():
  port = int(os.environ.get('PORT', 5000))
  app.run(host='0.0.0.0', port=port)

def keep_alive():
  t = Thread(target=run)
  t.start()

# --- CONFIGURATION ---
TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
bot = telebot.TeleBot(TOKEN)
ADMIN_WALLET = "BY3Tzt5cA8FwoPRw3B265jwb8NDU5dupf76SXwKqjnRZ"
ADMIN_ID = 5939907983
SUPPORT_ADMIN = "@Farming_Master"
ADMIN_PENDING_TOPUPS = {}
ADMIN_BROADCAST_STATE = {}

PROJECT_NAME = "SOLANA FARMING TELEBOT"

# --- PACKAGES ---
PACKAGES = {
    "starter": {"name": "STARTER", "roi": 0.005, "min": 0.10, "max": 2.00, "cap": 2.5},
    "advance": {"name": "ADVANCE", "roi": 0.01, "min": 2.10, "max": 10.00, "cap": 2.5},
    "premium": {"name": "PREMIUM", "roi": 0.015, "min": 10.10, "max": 25.00, "cap": 2.5},
    "galaxy": {"name": "GALAXY", "roi": 0.02, "min": 25.10, "max": 1000.00, "cap": 2.5}
}

REF_LEVELS = [0.05, 0.04, 0.03, 0.02, 0.01]

OVERRIDE_LEVELS = [
    0.15, 0.10, 0.05, 0.03, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02,
    0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02,
    0.02, 0.03, 0.05, 0.10, 0.15
]

RANKS = [
    {"level": 1, "name": "Star", "target": 30, "strongest_leg_min": 12, "other_legs_min": 18, "daily_royalty": 0.03},
    {"level": 2, "name": "Orbit", "target": 100, "strongest_leg_min": 40, "other_legs_min": 60, "daily_royalty": 0.10},
    {"level": 3, "name": "Solar", "target": 500, "strongest_leg_min": 200, "other_legs_min": 300, "daily_royalty": 0.50},
    {"level": 4, "name": "SuperNova", "target": 1500, "strongest_leg_min": 600, "other_legs_min": 900, "daily_royalty": 1.50},
    {"level": 5, "name": "Galaxy", "target": 5000, "strongest_leg_min": 2000, "other_legs_min": 3000, "daily_royalty": 5.00},
    {"level": 6, "name": "Super Galaxy", "target": 10000, "strongest_leg_min": 4000, "other_legs_min": 6000, "daily_royalty": 10.00},
    {"level": 7, "name": "Crown", "target": 20000, "strongest_leg_min": 8000, "other_legs_min": 12000, "daily_royalty": 20.00},
    {"level": 8, "name": "Grand Crown", "target": 100000, "strongest_leg_min": 40000, "other_legs_min": 60000, "daily_royalty": 100.00},
    {"level": 9, "name": "Universe", "target": 500000, "strongest_leg_min": 200000, "other_legs_min": 300000, "daily_royalty": 500.00},
    {"level": 10, "name": "Supreme Universe", "target": 1000000, "strongest_leg_min": 400000, "other_legs_min": 600000, "daily_royalty": 1000.00},
]

# --- DATABASE SETUP ---
def get_db():
    conn = sqlite3.connect(
        "solana_farming.db",
        check_same_thread=False,
        timeout=30
    )
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        referrer_id INTEGER,
        balance REAL DEFAULT 0,
        total_investment REAL DEFAULT 0,
        total_earned REAL DEFAULT 0,
        total_withdrawn REAL DEFAULT 0,
        plan_id TEXT,
        rank TEXT DEFAULT 'None',
        status TEXT DEFAULT 'inactive',
        username TEXT,
        self_farming REAL DEFAULT 0,
        self_farming_earned REAL DEFAULT 0,
        self_farming_bonus REAL DEFAULT 0,
        direct_referral_earned REAL DEFAULT 0,
        direct_referral_bonus REAL DEFAULT 0,
        team_referral_bonus REAL DEFAULT 0,
        team_override_earned REAL DEFAULT 0,
        team_farming_override_bonus REAL DEFAULT 0,
        rank_royalty_earned REAL DEFAULT 0,
        rank_royalty_bonus REAL DEFAULT 0,
        max_cap REAL DEFAULT 0,
        plan_name TEXT,
        total_team_business REAL DEFAULT 0
    )""")
    try:
        c.execute("ALTER TABLE users ADD COLUMN last_withdrawal_date TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'en'")
    except sqlite3.OperationalError:
        pass

    c.execute("""CREATE TABLE IF NOT EXISTS transactions (txid TEXT PRIMARY KEY)""")
    c.execute("""CREATE TABLE IF NOT EXISTS admin_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        target_user_id INTEGER,
        amount REAL,
        note TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        wallet_address TEXT NOT NULL,
        txid TEXT DEFAULT 'Pending',
        status TEXT DEFAULT 'Paid',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()

init_db()

# --- 10 GLOBAL LANGUAGES TRANSLATIONS (INCLUDING MENU BUTTONS) ---
translations = {
    "en": {
        "select_lang": "🌐 Please select your language:",
        "lang_changed": "✅ Language updated to English!",
        "welcome": "🚜 <b>Welcome to {PROJECT_NAME}</b>\n\nUse the buttons below to start your farming journey.",
        "btn_plans": "💎 Farming Plans",
        "btn_deposit": "💰 Deposit SOL",
        "btn_dashboard": "📊 Dashboard",
        "btn_withdraw": "🎁 Withdraw",
        "btn_ref": "🔗 Referral Link",
        "btn_team": "👥 Team Members",
        "btn_ranks": "🏆 Ranks & Royalty",
        "btn_history": "📜 Withdrawal History",
        "btn_lang": "🌐 Change Language",
        "farming_packages": (
            "<b>💎 Farming Packages (Max Cap: 250% for Self, 500% with Team):</b>\n\n"
            "1️⃣ <b>STARTER</b>\n• Limit: 0.10 - 2.0 SOL\n• Reward: 0.5% Daily\n\n"
            "2️⃣ <b>ADVANCE</b>\n• Limit: 2.10 - 10.0 SOL\n• Reward: 1.0% Daily\n\n"
            "3️⃣ <b>PREMIUM</b>\n• Limit: 10.10 - 25.0 SOL\n• Reward: 1.5% Daily\n\n"
            "4️⃣ <b>GALAXY</b>\n• Limit: 25.10 - 1000 SOL\n• Reward: 2.0% Daily\n\n"
            "⚠️ <i>Note: Base cap is 250%. Referring at least one active user upgrades max cap to 500%.</i>"
        ),
        "deposit_prompt": "💰 <b>Deposit SOL</b>\n\nPlease scan the QR code above or copy the address below to deposit SOL:\n\n<code>{wallet_address}</code>\n\n⚠ <i>Send only SOL to this address.</i>\n\n📝 <i>After sending, please send your Transaction Hash (TxID) here to activate your ID!</i>",
        "no_history": "📜 <b>Withdrawal History</b>\n\nYou have no past withdrawals.",
        "history_title": "📜 <b>Your Recent Withdrawals:</b>\n\n",
        "min_withdraw": "❌ <b>Minimum withdrawal limit is</b> <code>0.01 SOL</code>.",
        "withdraw_prompt": "💰 <b>Available Balance:</b> <code>{bal:.4f} SOL</code>\n\nEnter amount:",
        "team_empty": "👥 You don't have any team members yet.",
        "ref_text": "<b>🔗 Your Referral Link</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>",
        "dashboard_text": (
            "👤 <b>User Dashboard</b>\n\n"
            "💰 <b>Available Balance:</b> <code>{balance:.4f} SOL</code>\n"
            "🌾 <b>Total Self Farming:</b> <code>{self_farming:.4f} SOL</code>\n"
            "🌾 <b>Self Farming Bonus:</b> <code>{self_bonus:.4f} SOL</code>\n"
            "👥 <b>Direct Referral Bonus:</b> <code>{direct_ref:.4f} SOL</code>\n"
            "🤝 <b>Team Referral Bonus:</b> <code>{team_ref:.4f} SOL</code>\n"
            "🤝 <b>Team Farming Override Bonus:</b> <code>{team_override:.4f} SOL</code>\n"
            "🏆 <b>Rank & Royalty Bonus:</b> <code>{royalty:.4f} SOL</code>\n"
            "📈 <b>Total Earned:</b> <code>{earned:.4f} SOL</code> (Max Cap: <code>{max_cap:.2f} SOL</code>)\n\n"
            "🧁 <b>Total Withdrawals:</b> <code>{withdrawn:.4f} SOL</code>\n"
            "🎯 <b>Available Withdrawal Limit:</b> <code>{available_limit:.4f} SOL</code>\n\n"
            "📦 <b>Active Plan:</b> {active_plan}\n"
            "🏆 <b>Current Rank:</b> {current_rank}"
        ),
        "ranks_text": (
            "🏆 <b>Ranks & Royalty Status</b>\n\n"
            "<b>• Total Directs:</b> <code>{directs_count}</code> (Active: <code>{active_directs}</code>)\n"
            "<b>• Direct Business:</b> <code>{direct_biz:.2f} SOL</code>\n"
            "<b>• Total Team Business:</b> <code>{team_biz:.2f} SOL</code>\n"
            "<b>• Current Rank:</b> <code>{current_rank_name}</code>\n"
            "<b>• Next Rank:</b> <code>{next_rank_name}</code>\n\n"
            "<b>🎯 Progress for Next Rank:</b>\n"
            "<b>• Total Target ({target} SOL):</b> {total_icon} (Current: {total_volume:.2f})\n\n"
            "<b>• Leg Requirements Check:</b>\n"
            "<b> - Strongest Leg (Min {req_strongest} SOL):</b> {strongest_icon} (Current: <code>{highest_leg:.2f}</code>)\n"
            "<b> - Other Legs Combined (Min {req_other} SOL):</b> {other_icon} (Current: <code>{other_legs_total:.2f}</code>)\n"
        )
    },
    "ru": {
        "select_lang": "🌐 Пожалуйста, выберите язык:",
        "lang_changed": "✅ Язык успешно изменен на русский!",
        "welcome": "🚜 <b>Добро пожаловать в {PROJECT_NAME}</b>\n\nИспользуйте кнопки ниже, чтобы начать путь фарминга.",
        "btn_plans": "💎 Пакеты фарминга",
        "btn_deposit": "💰 Депозит SOL",
        "btn_dashboard": "📊 Панель",
        "btn_withdraw": "🎁 Вывод",
        "btn_ref": "🔗 Реферальная ссылка",
        "btn_team": "👥 Команда",
        "btn_ranks": "🏆 Ранги и роялти",
        "btn_history": "📜 История выводов",
        "btn_lang": "🌐 Изменить язык",
        "farming_packages": (
            "<b>💎 Пакеты фарминга (Макс. лимит: 250% для себя, 500% с командой):</b>\n\n"
            "1️⃣ <b>STARTER</b>\n• Лимит: 0.10 - 2.0 SOL\n• Награда: 0.5% в день\n\n"
            "2️⃣ <b>ADVANCE</b>\n• Лимит: 2.10 - 10.0 SOL\n• Награда: 1.0% в день\n\n"
            "3️⃣ <b>PREMIUM</b>\n• Лимит: 10.10 - 25.0 SOL\n• Награда: 1.5% в день\n\n"
            "4️⃣ <b>GALAXY</b>\n• Лимит: 25.10 - 1000 SOL\n• Награда: 2.0% в день\n\n"
            "⚠️ <i>Примечание: Базовый лимит 250%. Приглашение активного пользователя увеличивает лимит до 500%.</i>"
        ),
        "deposit_prompt": "💰 <b>Депозит SOL</b>\n\nОтсканируйте QR-код или скопируйте адрес для депозита:\n\n<code>{wallet_address}</code>\n\n⚠ <i>Отправляйте только SOL.</i>\n\n📝 <i>После отправки отправьте TxID сюда!</i>",
        "no_history": "📜 <b>История выводов</b>\n\nУ вас нет прошлых выводов.",
        "history_title": "📜 <b>Ваши недавние выводы:</b>\n\n",
        "min_withdraw": "❌ <b>Минимальный лимит вывода:</b> <code>0.01 SOL</code>.",
        "withdraw_prompt": "💰 <b>Доступный баланс:</b> <code>{bal:.4f} SOL</code>\n\nВведите сумму:",
        "team_empty": "👥 У вас пока нет участников команды.",
        "ref_text": "<b>🔗 Ваша реферальная ссылка</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>",
        "dashboard_text": (
            "👤 <b>Панель пользователя</b>\n\n"
            "💰 <b>Доступный баланс:</b> <code>{balance:.4f} SOL</code>\n"
            "🌾 <b>Собственный фарминг:</b> <code>{self_farming:.4f} SOL</code>\n"
            "🌾 <b>Бонус фарминга:</b> <code>{self_bonus:.4f} SOL</code>\n"
            "👥 <b>Бонус прямых рефералов:</b> <code>{direct_ref:.4f} SOL</code>\n"
            "🤝 <b>Командный реферальный бонус:</b> <code>{team_ref:.4f} SOL</code>\n"
            "🤝 <b>Бонус оверрайда команды:</b> <code>{team_override:.4f} SOL</code>\n"
            "🏆 <b>Бонус ранга и роялти:</b> <code>{royalty:.4f} SOL</code>\n"
            "📈 <b>Всего заработано:</b> <code>{earned:.4f} SOL</code> (Макс. лимит: <code>{max_cap:.2f} SOL</code>)\n\n"
            "🧁 <b>Всего выводов:</b> <code>{withdrawn:.4f} SOL</code>\n"
            "🎯 <b>Доступный лимит вывода:</b> <code>{available_limit:.4f} SOL</code>\n\n"
            "📦 <b>Активный план:</b> {active_plan}\n"
            "🏆 <b>Текущий ранг:</b> {current_rank}"
        ),
        "ranks_text": (
            "🏆 <b>Статус рангов и роялти</b>\n\n"
            "<b>• Всего прямых:</b> <code>{directs_count}</code> (Активных: <code>{active_directs}</code>)\n"
            "<b>• Прямой оборот:</b> <code>{direct_biz:.2f} SOL</code>\n"
            "<b>• Общий оборот команды:</b> <code>{team_biz:.2f} SOL</code>\n"
            "<b>• Текущий ранг:</b> <code>{current_rank_name}</code>\n"
            "<b>• Следующий ранг:</b> <code>{next_rank_name}</code>\n\n"
            "<b>🎯 Прогресс до следующего ранга:</b>\n"
            "<b>• Общая цель ({target} SOL):</b> {total_icon} (Текущий: {total_volume:.2f})\n\n"
            "<b>• Проверка веток:</b>\n"
            "<b> - Сильнейшая ветка (мин. {req_strongest} SOL):</b> {strongest_icon} (Текущий: <code>{highest_leg:.2f}</code>)\n"
            "<b> - Остальные ветки (мин. {req_other} SOL):</b> {other_icon} (Текущий: <code>{other_legs_total:.2f}</code>)\n"
        )
    },
    "zh": {
        "select_lang": "🌐 请选择您的语言：",
        "lang_changed": "✅ 语言已更新为中文！",
        "welcome": "🚜 <b>欢迎来到 {PROJECT_NAME}</b>\n\n使用下方的按钮开始您的耕作之旅。",
        "btn_plans": "💎 挖矿套餐",
        "btn_deposit": "💰 存款 SOL",
        "btn_dashboard": "📊 面板",
        "btn_withdraw": "🎁 提现",
        "btn_ref": "🔗 推荐链接",
        "btn_team": "👥 团队成员",
        "btn_ranks": "🏆 等级与版税",
        "btn_history": "📜 提现记录",
        "btn_lang": "🌐 更改语言",
        "farming_packages": (
            "<b>💎 挖矿套餐（个人上限 250%，团队上限 500%）：</b>\n\n"
            "1️⃣ <b>STARTER</b>\n• 限制：0.10 - 2.0 SOL\n• 每日奖励：0.5%\n\n"
            "2️⃣ <b>ADVANCE</b>\n• 限制：2.10 - 10.0 SOL\n• 每日奖励：1.0%\n\n"
            "3️⃣ <b>PREMIUM</b>\n• 限制：10.10 - 25.0 SOL\n• 每日奖励：1.5%\n\n"
            "4️⃣ <b>GALAXY</b>\n• 限制：25.10 - 1000 SOL\n• 每日奖励：2.0%\n\n"
            "⚠️ <i>注意：基础上限为 250%，推荐至少一名活跃用户可提升至 500%。</i>"
        ),
        "deposit_prompt": "💰 <b>存款 SOL</b>\n\n请扫描上方二维码或复制地址进行存款：\n\n<code>{wallet_address}</code>\n\n⚠ <i>仅限发送 SOL。</i>\n\n📝 <i>发送后请将交易哈希 (TxID) 发送至此处！</i>",
        "no_history": "📜 <b>提现记录</b>\n\n您没有历史提现记录。",
        "history_title": "📜 <b>您最近的提现：</b>\n\n",
        "min_withdraw": "❌ <b>最低提现额度为</b> <code>0.01 SOL</code>。",
        "withdraw_prompt": "💰 <b>可用余额：</b> <code>{bal:.4f} SOL</code>\n\n请输入金额：",
        "team_empty": "👥 您还没有团队成员。",
        "ref_text": "<b>🔗 您的推荐链接</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>",
        "dashboard_text": (
            "👤 <b>用户面板</b>\n\n"
            "💰 <b>可用余额：</b> <code>{balance:.4f} SOL</code>\n"
            "🌾 <b>总个人耕作：</b> <code>{self_farming:.4f} SOL</code>\n"
            "🌾 <b>个人耕作奖励：</b> <code>{self_bonus:.4f} SOL</code>\n"
            "👥 <b>直接推荐奖励：</b> <code>{direct_ref:.4f} SOL</code>\n"
            "🤝 <b>团队推荐奖励：</b> <code>{team_ref:.4f} SOL</code>\n"
            "🤝 <b>团队耕作覆盖奖励：</b> <code>{team_override:.4f} SOL</code>\n"
            "🏆 <b>等级与版税奖励：</b> <code>{royalty:.4f} SOL</code>\n"
            "📈 <b>总收益：</b> <code>{earned:.4f} SOL</code> (上限: <code>{max_cap:.2f} SOL</code>)\n\n"
            "🧁 <b>总提现：</b> <code>{withdrawn:.4f} SOL</code>\n"
            "🎯 <b>可用提现额度：</b> <code>{available_limit:.4f} SOL</code>\n\n"
            "📦 <b>当前套餐：</b> {active_plan}\n"
            "🏆 <b>当前等级：</b> {current_rank}"
        ),
        "ranks_text": (
            "🏆 <b>等级与版税状态</b>\n\n"
            "<b>• 直接推荐总数：</b> <code>{directs_count}</code> (活跃：<code>{active_directs}</code>)\n"
            "<b>• 直接业绩：</b> <code>{direct_biz:.2f} SOL</code>\n"
            "<b>• 团队总业绩：</b> <code>{team_biz:.2f} SOL</code>\n"
            "<b>• 当前等级：</b> <code>{current_rank_name}</code>\n"
            "<b>• 下一等级：</b> <code>{next_rank_name}</code>\n\n"
            "<b>🎯 下一等级进度：</b>\n"
            "<b>• 总目标 ({target} SOL)：</b> {total_icon} (当前：{total_volume:.2f})\n\n"
            "<b>• 腿部要求检查：</b>\n"
            "<b> - 最强腿 (最小 {req_strongest} SOL)：</b> {strongest_icon} (当前：<code>{highest_leg:.2f}</code>)\n"
            "<b> - 其他腿组合 (最小 {req_other} SOL)：</b> {other_icon} (当前：<code>{other_legs_total:.2f}</code>)\n"
        )
    },
    "vi": {
        "select_lang": "🌐 Vui lòng chọn ngôn ngữ của bạn:",
        "lang_changed": "✅ Đã cập nhật ngôn ngữ thành Tiếng Việt!",
        "welcome": "🚜 <b>Chào mừng đến với {PROJECT_NAME}</b>\n\nSử dụng các nút bên dưới để bắt đầu hành trình canh tác của bạn.",
        "btn_plans": "💎 Gói Khai Thác",
        "btn_deposit": "💰 Nạp SOL",
        "btn_dashboard": "📊 Bảng điều khiển",
        "btn_withdraw": "🎁 Rút tiền",
        "btn_ref": "🔗 Liên kết giới thiệu",
        "btn_team": "👥 Thành viên nhóm",
        "btn_ranks": "🏆 Cấp bậc & Bản quyền",
        "btn_history": "📜 Lịch sử rút tiền",
        "btn_lang": "🌐 Đổi ngôn ngữ",
        "farming_packages": (
            "<b>💎 Gói Khai Thác (Giới hạn tối đa: 250% cá nhân, 500% với đội ngũ):</b>\n\n"
            "1️⃣ <b>STARTER</b>\n• Giới hạn: 0.10 - 2.0 SOL\n• Thưởng: 0.5% Mỗi ngày\n\n"
            "2️⃣ <b>ADVANCE</b>\n• Giới hạn: 2.10 - 10.0 SOL\n• Thưởng: 1.0% Mỗi ngày\n\n"
            "3️⃣ <b>PREMIUM</b>\n• Giới hạn: 10.10 - 25.0 SOL\n• Thưởng: 1.5% Mỗi ngày\n\n"
            "4️⃣ <b>GALAXY</b>\n• Giới hạn: 25.10 - 1000 SOL\n• Thưởng: 2.0% Mỗi ngày\n\n"
            "⚠️ <i>Lưu ý: Giới hạn gốc là 250%. Giới thiệu 1 người dùng hoạt động nâng cấp lên 500%.</i>"
        ),
        "deposit_prompt": "💰 <b>Nạp SOL</b>\n\nVui lòng quét mã QR hoặc sao chép địa chỉ để nạp:\n\n<code>{wallet_address}</code>\n\n⚠ <i>Chỉ gửi SOL.</i>\n\n📝 <i>Sau khi gửi, hãy gửi Mã giao dịch (TxID) vào đây!</i>",
        "no_history": "📜 <b>Lịch sử rút tiền</b>\n\nBạn chưa có lịch sử rút tiền.",
        "history_title": "📜 <b>Các lần rút gần đây:</b>\n\n",
        "min_withdraw": "❌ <b>Hạn mức rút tối thiểu là</b> <code>0.01 SOL</code>.",
        "withdraw_prompt": "💰 <b>Số dư khả dụng:</b> <code>{bal:.4f} SOL</code>\n\nNhập số tiền:",
        "team_empty": "👥 Bạn chưa có thành viên nhóm nào.",
        "ref_text": "<b>🔗 Liên kết giới thiệu của bạn</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>",
        "dashboard_text": (
            "👤 <b>Bảng điều khiển</b>\n\n"
            "💰 <b>Số dư khả dụng:</b> <code>{balance:.4f} SOL</code>\n"
            "🌾 <b>Tổng tự canh tác:</b> <code>{self_farming:.4f} SOL</code>\n"
            "🌾 <b>Thưởng tự canh tác:</b> <code>{self_bonus:.4f} SOL</code>\n"
            "👥 <b>Thưởng giới thiệu trực tiếp:</b> <code>{direct_ref:.4f} SOL</code>\n"
            "🤝 <b>Thưởng giới thiệu nhóm:</b> <code>{team_ref:.4f} SOL</code>\n"
            "🤝 <b>Thưởng ghi đè nhóm:</b> <code>{team_override:.4f} SOL</code>\n"
            "🏆 <b>Thưởng cấp bậc & bản quyền:</b> <code>{royalty:.4f} SOL</code>\n"
            "📈 <b>Tổng thu nhập:</b> <code>{earned:.4f} SOL</code> (Giới hạn: <code>{max_cap:.2f} SOL</code>)\n\n"
            "🧁 <b>Tổng rút tiền:</b> <code>{withdrawn:.4f} SOL</code>\n"
            "🎯 <b>Hạn mức rút khả dụng:</b> <code>{available_limit:.4f} SOL</code>\n\n"
            "📦 <b>Gói hiện tại:</b> {active_plan}\n"
            "🏆 <b>Cấp bậc hiện tại:</b> {current_rank}"
        ),
        "ranks_text": (
            "🏆 <b>Trạng thái cấp bậc & bản quyền</b>\n\n"
            "<b>• Tổng trực tiếp:</b> <code>{directs_count}</code> (Hoạt động: <code>{active_directs}</code>)\n"
            "<b>• Doanh số trực tiếp:</b> <code>{direct_biz:.2f} SOL</code>\n"
            "<b>• Tổng doanh số nhóm:</b> <code>{team_biz:.2f} SOL</code>\n"
            "<b>• Cấp bậc hiện tại:</b> <code>{current_rank_name}</code>\n"
            "<b>• Cấp bậc tiếp theo:</b> <code>{next_rank_name}</code>\n\n"
            "<b>🎯 Tiến độ cấp tiếp theo:</b>\n"
            "<b>• Mục tiêu tổng ({target} SOL):</b> {total_icon} (Hiện tại: {total_volume:.2f})\n\n"
            "<b>• Kiểm tra chân:</b>\n"
            "<b> - Chân mạnh nhất (Tối thiểu {req_strongest} SOL):</b> {strongest_icon} (Hiện tại: <code>{highest_leg:.2f}</code>)\n"
            "<b> - Các chân khác (Tối thiểu {req_other} SOL):</b> {other_icon} (Hiện tại: <code>{other_legs_total:.2f}</code>)\n"
        )
    },
    "id": {
        "select_lang": "🌐 Silakan pilih bahasa Anda:",
        "lang_changed": "✅ Bahasa berhasil diubah ke Bahasa Indonesia!",
        "welcome": "🚜 <b>Selamat datang di {PROJECT_NAME}</b>\n\nGunakan tombol di bawah untuk memulai perjalanan farming Anda.",
        "btn_plans": "💎 Paket Farming",
        "btn_deposit": "💰 Deposit SOL",
        "btn_dashboard": "📊 Dasbor",
        "btn_withdraw": "🎁 Penarikan",
        "btn_ref": "🔗 Tautan Referensi",
        "btn_team": "👥 Anggota Tim",
        "btn_ranks": "🏆 Peringkat & Royalti",
        "btn_history": "📜 Riwayat Penarikan",
        "btn_lang": "🌐 Ubah Bahasa",
        "farming_packages": (
            "<b>💎 Paket Farming (Batas Maks: 250% Mandiri, 500% dengan Tim):</b>\n\n"
            "1️⃣ <b>STARTER</b>\n• Batas: 0.10 - 2.0 SOL\n• Hadiah: 0.5% per Hari\n\n"
            "2️⃣ <b>ADVANCE</b>\n• Batas: 2.10 - 10.0 SOL\n• Hadiah: 1.0% per Hari\n\n"
            "3️⃣ <b>PREMIUM</b>\n• Batas: 10.10 - 25.0 SOL\n• Hadiah: 1.5% per Hari\n\n"
            "4️⃣ <b>GALAXY</b>\n• Batas: 25.10 - 1000 SOL\n• Hadiah: 2.0% per Hari\n\n"
            "⚠️ <i>Catatan: Batas dasar 250%. Referensikan 1 pengguna aktif untuk meningkatkan ke 500%.</i>"
        ),
        "deposit_prompt": "💰 <b>Deposit SOL</b>\n\nSilakan pindai QR code atau salin alamat untuk deposit:\n\n<code>{wallet_address}</code>\n\n⚠ <i>Kirim hanya SOL.</i>\n\n📝 <i>Setelah mengirim, kirimkan TxID Anda ke sini!</i>",
        "no_history": "📜 <b>Riwayat Penarikan</b>\n\nAnda tidak memiliki riwayat penarikan.",
        "history_title": "📜 <b>Penarikan Terbaru Anda:</b>\n\n",
        "min_withdraw": "❌ <b>Batas penarikan minimum adalah</b> <code>0.01 SOL</code>.",
        "withdraw_prompt": "💰 <b>Saldo Tersedia:</b> <code>{bal:.4f} SOL</code>\n\nMasukkan jumlah:",
        "team_empty": "👥 Anda belum memiliki anggota tim.",
        "ref_text": "<b>🔗 Tautan Referensi Anda</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>",
        "dashboard_text": (
            "👤 <b>Dasbor Pengguna</b>\n\n"
            "💰 <b>Saldo Tersedia:</b> <code>{balance:.4f} SOL</code>\n"
            "🌾 <b>Total Self Farming:</b> <code>{self_farming:.4f} SOL</code>\n"
            "🌾 <b>Bonus Self Farming:</b> <code>{self_bonus:.4f} SOL</code>\n"
            "👥 <b>Bonus Referral Langsung:</b> <code>{direct_ref:.4f} SOL</code>\n"
            "🤝 <b>Bonus Referral Tim:</b> <code>{team_ref:.4f} SOL</code>\n"
            "🤝 <b>Bonus Override Tim:</b> <code>{team_override:.4f} SOL</code>\n"
            "🏆 <b>Bonus Peringkat & Royalti:</b> <code>{royalty:.4f} SOL</code>\n"
            "📈 <b>Total Pendapatan:</b> <code>{earned:.4f} SOL</code> (Batas: <code>{max_cap:.2f} SOL</code>)\n\n"
            "🧁 <b>Total Penarikan:</b> <code>{withdrawn:.4f} SOL</code>\n"
            "🎯 <b>Batas Penarikan Tersedia:</b> <code>{available_limit:.4f} SOL</code>\n\n"
            "📦 <b>Paket Aktif:</b> {active_plan}\n"
            "🏆 <b>Peringkat Saat Ini:</b> {current_rank}"
        ),
        "ranks_text": (
            "🏆 <b>Status Peringkat & Royalti</b>\n\n"
            "<b>• Total Direct:</b> <code>{directs_count}</code> (Aktif: <code>{active_directs}</code>)\n"
            "<b>• Bisnis Langsung:</b> <code>{direct_biz:.2f} SOL</code>\n"
            "<b>• Total Bisnis Tim:</b> <code>{team_biz:.2f} SOL</code>\n"
            "<b>• Peringkat Saat Ini:</b> <code>{current_rank_name}</code>\n"
            "<b>• Peringkat Berikutnya:</b> <code>{next_rank_name}</code>\n\n"
            "<b>🎯 Progres Peringkat Berikutnya:</b>\n"
            "<b>• Target Total ({target} SOL):</b> {total_icon} (Saat Ini: {total_volume:.2f})\n\n"
            "<b>• Pemeriksaan Kaki:</b>\n"
            "<b> - Kaki Terkuat (Min {req_strongest} SOL):</b> {strongest_icon} (Saat Ini: <code>{highest_leg:.2f}</code>)\n"
            "<b> - Kaki Lainnya (Min {req_other} SOL):</b> {other_icon} (Saat Ini: <code>{other_legs_total:.2f}</code>)\n"
        )
    },
    "th": {
        "select_lang": "🌐 กรุณาเลือกภาษาของคุณ:",
        "lang_changed": "✅ เปลี่ยนภาษาเป็นภาษาไทยเรียบร้อยแล้ว!",
        "welcome": "🚜 <b>ยินดีต้อนรับสู่ {PROJECT_NAME}</b>\n\nใช้ปุ่มด้านล่างเพื่อเริ่มต้นการทำฟาร์มของคุณ",
        "btn_plans": "💎 แพ็คเกจฟาร์ม",
        "btn_deposit": "💰 ฝาก SOL",
        "btn_dashboard": "📊 แดชบอร์ด",
        "btn_withdraw": "🎁 ถอนเงิน",
        "btn_ref": "🔗 ลิงก์แนะนำ",
        "btn_team": "👥 สมาชิกในทีม",
        "btn_ranks": "🏆 ตำแหน่ง & ค่าลิขสิทธิ์",
        "btn_history": "📜 ประวัติการถอน",
        "btn_lang": "🌐 เปลี่ยนภาษา",
        "farming_packages": (
            "<b>💎 แพ็คเกจฟาร์ม (ขีดจำกัดสูงสุด: 250% สำหรับส่วนตัว, 500% กับทีม):</b>\n\n"
            "1️⃣ <b>STARTER</b>\n• ขีดจำกัด: 0.10 - 2.0 SOL\n• รางวัล: 0.5% ต่อวัน\n\n"
            "2️⃣ <b>ADVANCE</b>\n• ขีดจำกัด: 2.10 - 10.0 SOL\n• รางวัล: 1.0% ต่อวัน\n\n"
            "3️⃣ <b>PREMIUM</b>\n• ขีดจำกัด: 10.10 - 25.0 SOL\n• รางวัล: 1.5% ต่อวัน\n\n"
            "4️⃣ <b>GALAXY</b>\n• ขีดจำกัด: 25.10 - 1000 SOL\n• รางวัล: 2.0% ต่อวัน\n\n"
            "⚠️ <i>หมายเหตุ: ขีดจำกัดพื้นฐานคือ 250% แนะนำผู้ใช้งานที่ใช้งานอยู่ 1 คนเพื่อเพิ่มเป็น 500%</i>"
        ),
        "deposit_prompt": "💰 <b>ฝาก SOL</b>\n\nกรุณาสแกน QR โค้ดหรือคัดลอกที่อยู่เพื่อฝาก SOL:\n\n<code>{wallet_address}</code>\n\n⚠ <i>ส่งเฉพาะ SOL เท่านั้น</i>\n\n📝 <i>หลังจากส่งแล้ว โปรดส่งรหัสธุรกรรม (TxID) ที่นี่!</i>",
        "no_history": "📜 <b>ประวัติการถอน</b>\n\nคุณไม่มีประวัติการถอนเงิน",
        "history_title": "📜 <b>การถอนเงินล่าสุดของคุณ:</b>\n\n",
        "min_withdraw": "❌ <b>ขีดจำกัดการถอนขั้นต่ำคือ</b> <code>0.01 SOL</code>",
        "withdraw_prompt": "💰 <b>ยอดเงินคงเหลือ:</b> <code>{bal:.4f} SOL</code>\n\nป้อนจำนวนเงิน:",
        "team_empty": "👥 คุณยังไม่มีสมาชิกในทีม",
        "ref_text": "<b>🔗 ลิงก์แนะนำของคุณ</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>",
        "dashboard_text": (
            "👤 <b>แดชบอร์ดผู้ใช้</b>\n\n"
            "💰 <b>ยอดเงินคงเหลือ:</b> <code>{balance:.4f} SOL</code>\n"
            "🌾 <b>การทำฟาร์มส่วนตัวทั้งหมด:</b> <code>{self_farming:.4f} SOL</code>\n"
            "🌾 <b>โบนัสการทำฟาร์ม:</b> <code>{self_bonus:.4f} SOL</code>\n"
            "👥 <b>โบนัสแนะนำโดยตรง:</b> <code>{direct_ref:.4f} SOL</code>\n"
            "🤝 <b>โบนัสแนะนำทีม:</b> <code>{team_ref:.4f} SOL</code>\n"
            "🤝 <b>โบนัสโอเวอร์ライドทีม:</b> <code>{team_override:.4f} SOL</code>\n"
            "🏆 <b>โบนัสตำแหน่ง & ค่าลิขสิทธิ์:</b> <code>{royalty:.4f} SOL</code>\n"
            "📈 <b>รายได้รวม:</b> <code>{earned:.4f} SOL</code> (ขีดจำกัด: <code>{max_cap:.2f} SOL</code>)\n\n"
            "🧁 <b>การถอนเงินทั้งหมด:</b> <code>{withdrawn:.4f} SOL</code>\n"
            "🎯 <b>ขีดจำกัดการถอนที่ใช้ได้:</b> <code>{available_limit:.4f} SOL</code>\n\n"
            "📦 <b>แพ็คเกจที่ใช้งาน:</b> {active_plan}\n"
            "🏆 <b>ตำแหน่งปัจจุบัน:</b> {current_rank}"
        ),
        "ranks_text": (
            "🏆 <b>สถานะตำแหน่ง & ค่าลิขสิทธิ์</b>\n\n"
            "<b>• แนะนำตรงทั้งหมด:</b> <code>{directs_count}</code> (ใช้งาน: <code>{active_directs}</code>)\n"
            "<b>• ยอดธุรกิจตรง:</b> <code>{direct_biz:.2f} SOL</code>\n"
            "<b>• ยอดธุรกิจทีมรวม:</b> <code>{team_biz:.2f} SOL</code>\n"
            "<b>• ตำแหน่งปัจจุบัน:</b> <code>{current_rank_name}</code>\n"
            "<b>• ตำแหน่งถัดไป:</b> <code>{next_rank_name}</code>\n\n"
            "<b>🎯 ความคืบหน้าสำหรับตำแหน่งถัดไป:</b>\n"
            "<b>• เป้าหมายรวม ({target} SOL):</b> {total_icon} (ปัจจุบัน: {total_volume:.2f})\n\n"
            "<b>• ตรวจสอบขา:</b>\n"
            "<b> - ขาที่แข็งแกร่งที่สุด (ขั้นต่ำ {req_strongest} SOL):</b> {strongest_icon} (ปัจจุบัน: <code>{highest_leg:.2f}</code>)\n"
            "<b> - ขาอื่นๆ รวมกัน (ขั้นต่ำ {req_other} SOL):</b> {other_icon} (ปัจจุบัน: <code>{other_legs_total:.2f}</code>)\n"
        )
    },
    "ar": {
        "select_lang": "🌐 الرجاء اختيار لغتك:",
        "lang_changed": "✅ تم تحديث اللغة إلى العربية!",
        "welcome": "🚜 <b>مرحباً بك في {PROJECT_NAME}</b>\n\nاستخدم الأزرار أدناه لبدء رحلة الزراعة الخاصة بك.",
        "btn_plans": "💎 باقات الزراعة",
        "btn_deposit": "💰 إيداع SOL",
        "btn_dashboard": "📊 لوحة التحكم",
        "btn_withdraw": "🎁 سحب",
        "btn_ref": "🔗 رابط الإحالة",
        "btn_team": "👥 أعضاء الفريق",
        "btn_ranks": "🏆 الرتب والعائدات",
        "btn_history": "📜 سجل السحب",
        "btn_lang": "🌐 تغير اللغة",
        "farming_packages": (
            "<b>💎 باقات الزراعة (الحد الأقصى: 250% للشخصي، 500% مع الفريق):</b>\n\n"
            "1️⃣ <b>STARTER</b>\n• الحد: 0.10 - 2.0 SOL\n• المكافأة: 0.5% يومياً\n\n"
            "2️⃣ <b>ADVANCE</b>\n• الحد: 2.10 - 10.0 SOL\n• المكافأة: 1.0% يومياً\n\n"
            "3️⃣ <b>PREMIUM</b>\n• الحد: 10.10 - 25.0 SOL\n• المكافأة: 1.5% يومياً\n\n"
            "4️⃣ <b>GALAXY</b>\n• الحد: 25.10 - 1000 SOL\n• المكافأة: 2.0% يومياً\n\n"
            "⚠️ <i>ملاحظة: الحد الأساسي هو 250%. إحالة مستخدم نشط واحد ترفع الحد إلى 500%.</i>"
        ),
        "deposit_prompt": "💰 <b>إيداع SOL</b>\n\nيرجى مسح رمز الاستجابة السريعة أو نسخ العنوان للإيداع:\n\n<code>{wallet_address}</code>\n\n⚠ <i>أرسل SOL فقط.</i>\n\n📝 <i>بعد الإرسال، أرسل رقم المعاملة (TxID) هنا!</i>",
        "no_history": "📜 <b>سجل السحب</b>\n\nليس لديك عمليات سحب سابقة.",
        "history_title": "📜 <b>عمليات السحب الأخيرة:</b>\n\n",
        "min_withdraw": "❌ <b>الحد الأدنى للسحب هو</b> <code>0.01 SOL</code>.",
        "withdraw_prompt": "💰 <b>الرصيد المتاح:</b> <code>{bal:.4f} SOL</code>\n\nأدخل المبلغ:",
        "team_empty": "👥 ليس لديك أي أعضاء في الفريق حتى الآن.",
        "ref_text": "<b>🔗 رابط الإحالة الخاص بك</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>",
        "dashboard_text": (
            "👤 <b>لوحة تحكم المستخدم</b>\n\n"
            "💰 <b>الرصيد المتاح:</b> <code>{balance:.4f} SOL</code>\n"
            "🌾 <b>إجمالي الزراعة الذاتية:</b> <code>{self_farming:.4f} SOL</code>\n"
            "🌾 <b>مكافأة الزراعة الذاتية:</b> <code>{self_bonus:.4f} SOL</code>\n"
            "👥 <b>مكافأة الإحالة المباشرة:</b> <code>{direct_ref:.4f} SOL</code>\n"
            "🤝 <b>مكافأة إحالة الفريق:</b> <code>{team_ref:.4f} SOL</code>\n"
            "🤝 <b>مكافأة تجاوز زراعة الفريق:</b> <code>{team_override:.4f} SOL</code>\n"
            "🏆 <b>مكافأة الرتبة والعائدات:</b> <code>{royalty:.4f} SOL</code>\n"
            "📈 <b>إجمالي الأرباح:</b> <code>{earned:.4f} SOL</code> (الحد الأقصى: <code>{max_cap:.2f} SOL</code>)\n\n"
            "🧁 <b>إجمالي السحب:</b> <code>{withdrawn:.4f} SOL</code>\n"
            "🎯 <b>حد السحب المتاح:</b> <code>{available_limit:.4f} SOL</code>\n\n"
            "📦 <b>الباقة النشطة:</b> {active_plan}\n"
            "🏆 <b>الرتبة الحالية:</b> {current_rank}"
        ),
        "ranks_text": (
            "🏆 <b>حالة الرتب والعائدات</b>\n\n"
            "<b>• إجمالي الإحالات المباشرة:</b> <code>{directs_count}</code> (النشطة: <code>{active_directs}</code>)\n"
            "<b>• أعمال الإحالات المباشرة:</b> <code>{direct_biz:.2f} SOL</code>\n"
            "<b>• إجمالي أعمال الفريق:</b> <code>{team_biz:.2f} SOL</code>\n"
            "<b>• الرتبة الحالية:</b> <code>{current_rank_name}</code>\n"
            "<b>• الرتبة التالية:</b> <code>{next_rank_name}</code>\n\n"
            "<b>🎯 تقدم الرتبة التالية:</b>\n"
            "<b>• الهدف الإجمالي ({target} SOL):</b> {total_icon} (الحالي: {total_volume:.2f})\n\n"
            "<b>• فحص متطلبات الأرجل:</b>\n"
            "<b> - الرجل الأقوى (الحد الأدنى {req_strongest} SOL):</b> {strongest_icon} (الحالي: <code>{highest_leg:.2f}</code>)\n"
            "<b> - الأرجل الأخرى مجتمعة (الحد الأدنى {req_other} SOL):</b> {other_icon} (الحالي: <code>{other_legs_total:.2f}</code>)\n"
        )
    },
    "hi": {
        "select_lang": "🌐 कृपया अपनी भाषा चुनें:",
        "lang_changed": "✅ भाषा बदलकर हिंदी कर दी गई है!",
        "welcome": "🚜 <b>{PROJECT_NAME} में आपका स्वागत है</b>\n\nअपनी फार्मिंग यात्रा शुरू करने के लिए नीचे दिए गए बटनों का उपयोग करें।",
        "btn_plans": "💎 फार्मिंग प्लान्स",
        "btn_deposit": "💰 SOL जमा करें",
        "btn_dashboard": "📊 डैशबोर्ड",
        "btn_withdraw": "🎁 निकासी",
        "btn_ref": "🔗 रेफरल लिंक",
        "btn_team": "👥 टीम मेंबर",
        "btn_ranks": "🏆 रैंक और रॉयल्टी",
        "btn_history": "📜 निकासी इतिहास",
        "btn_lang": "🌐 भाषा बदलें",
        "farming_packages": (
            "<b>💎 फार्मing पैकेज (अधिकतम कैप: स्वयं के लिए 250%, टीम के साथ 500%):</b>\n\n"
            "1️⃣ <b>STARTER</b>\n• सीमा: 0.10 - 2.0 SOL\n• इनाम: 0.5% प्रतिदिन\n\n"
            "2️⃣ <b>ADVANCE</b>\n• सीमा: 2.10 - 10.0 SOL\n• इनाम: 1.0% प्रतिदिन\n\n"
            "3️⃣ <b>PREMIUM</b>\n• सीमा: 10.10 - 25.0 SOL\n• इनाम: 1.5% प्रतिदिन\n\n"
            "4️⃣ <b>GALAXY</b>\n• सीमा: 25.10 - 1000 SOL\n• इनाम: 2.0% प्रतिदिन\n\n"
            "⚠️ <i>नोट: बेस कैप 250% है। कम से कम एक सक्रिय उपयोगकर्ता को रेफर करने पर कैप 500% हो जाता है।</i>"
        ),
        "deposit_prompt": "💰 <b>SOL जमा करें</b>\n\nकृपया SOL जमा करने के लिए ऊपर दिए गए QR कोड को स्कैन करें या नीचे दिए गए पते को कॉपी करें:\n\n<code>{wallet_address}</code>\n\n⚠ <i>इस पते पर केवल SOL भेजें।</i>\n\n📝 <i>भेजने के बाद, अपनी आईडी सक्रिय करने के लिए यहाँ Transaction Hash (TxID) भेजें!</i>",
        "no_history": "📜 <b>निकासी इतिहास</b>\n\nआपका कोई पिछला निकासी रिकॉर्ड नहीं है।",
        "history_title": "📜 <b>आपकी हालिया निकासी:</b>\n\n",
        "min_withdraw": "❌ <b>न्यूनतम निकासी सीमा</b> <code>0.01 SOL</code> <b>है।</b>",
        "withdraw_prompt": "💰 <b>उपलब्ध शेष राशि:</b> <code>{bal:.4f} SOL</code>\n\nराशि दर्ज करें:",
        "team_empty": "👥 आपका अभी तक कोई टीम मेंबर नहीं है।",
        "ref_text": "<b>🔗 आपका रेफरल लिंक</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>",
        "dashboard_text": (
            "👤 <b>यूज़र डैशबोर्ड</b>\n\n"
            "💰 <b>उपलब्ध शेष राशि:</b> <code>{balance:.4f} SOL</code>\n"
            "🌾 <b>कुल स्वयं की फार्मिंग:</b> <code>{self_farming:.4f} SOL</code>\n"
            "🌾 <b>फार्मिंग बोनस:</b> <code>{self_bonus:.4f} SOL</code>\n"
            "👥 <b>प्रत्यक्ष रेफरल बोनस:</b> <code>{direct_ref:.4f} SOL</code>\n"
            "🤝 <b>टीम रेफरल बोनस:</b> <code>{team_ref:.4f} SOL</code>\n"
            "🤝 <b>टीम फार्मिंग ओवरराइड बोनस:</b> <code>{team_override:.4f} SOL</code>\n"
            "🏆 <b>रैंक और रॉयल्टी बोनस:</b> <code>{royalty:.4f} SOL</code>\n"
            "📈 <b>कुल कमाई:</b> <code>{earned:.4f} SOL</code> (अधिकतम कैप: <code>{max_cap:.2f} SOL</code>)\n\n"
            "🧁 <b>कुल निकासी:</b> <code>{withdrawn:.4f} SOL</code>\n"
            "🎯 <b>उपलब्ध निकासी सीमा:</b> <code>{available_limit:.4f} SOL</code>\n\n"
            "📦 <b>सक्रिय प्लान:</b> {active_plan}\n"
            "🏆 <b>वर्तमान रैंक:</b> {current_rank}"
        ),
        "ranks_text": (
            "🏆 <b>रैंक और रॉयल्टी स्थिति</b>\n\n"
            "<b>• कुल डायरेक्ट्स:</b> <code>{directs_count}</code> (सक्रिय: <code>{active_directs}</code>)\n"
            "<b>• डायरेक्ट बिजनेस:</b> <code>{direct_biz:.2f} SOL</code>\n"
            "<b>• कुल टीम बिजनेस:</b> <code>{team_biz:.2f} SOL</code>\n"
            "<b>• वर्तमान रैंक:</b> <code>{current_rank_name}</code>\n"
            "<b>• अगली रैंक:</b> <code>{next_rank_name}</code>\n\n"
            "<b>🎯 अगली रैंक के लिए प्रगति:</b>\n"
            "<b>• कुल लक्ष्य ({target} SOL):</b> {total_icon} (वर्तमान: {total_volume:.2f})\n\n"
            "<b>• लेग आवश्यकता चेक:</b>\n"
            "<b> - मजबूत लेग (न्यूनतम {req_strongest} SOL):</b> {strongest_icon} (वर्तमान: <code>{highest_leg:.2f}</code>)\n"
            "<b> - अन्य लेग्स संयुक्त (न्यूनतम {req_other} SOL):</b> {other_icon} (वर्तमान: <code>{other_legs_total:.2f}</code>)\n"
        )
    },
    "bn": {
        "select_lang": "🌐 অনুগ্রহ করে আপনার ভাষা নির্বাচন করুন:",
        "lang_changed": "✅ ভাষা সফলভাবে বাংলায় আপডেট করা হয়েছে!",
        "welcome": "🚜 <b>{PROJECT_NAME}-এ আপনাকে স্বাগতম</b>\n\nআপনার ফার্মিং যাত্রা শুরু করতে নিচের বোতামগুলি ব্যবহার করুন।",
        "btn_plans": "💎 ফার্মিং প্ল্যান",
        "btn_deposit": "💰 SOL জমা দিন",
        "btn_dashboard": "📊 ড্যাশবোর্ড",
        "btn_withdraw": "🎁 উত্তোলন",
        "btn_ref": "🔗 রেফারেল লিংক",
        "btn_team": "👥 টিম মেম্বার",
        "btn_ranks": "🏆 র্যাঙ্ক এবং রয়্যালটি",
        "btn_history": "📜 উত্তোলনের ইতিহাস",
        "btn_lang": "🌐 ভাষা পরিবর্তন",
        "farming_packages": (
            "<b>💎 ফার্মিং প্যাকেজ (সর্বোচ্চ ক্যাপ: নিজের জন্য ২৫০%, টিমের সাথে ৫০০%):</b>\n\n"
            "1️⃣ <b>STARTER</b>\n• সীমা: 0.10 - 2.0 SOL\n• পুরস্কার: প্রতিদিন 0.5%\n\n"
            "2️⃣ <b>ADVANCE</b>\n• সীমা: 2.10 - 10.0 SOL\n• পুরস্কার: প্রতিদিন 1.0%\n\n"
            "3️⃣ <b>PREMIUM</b>\n• সীমা: 10.10 - 25.0 SOL\n• পুরস্কার: প্রতিদিন 1.5%\n\n"
            "4️⃣ <b>GALAXY</b>\n• সীমা: 25.10 - 1000 SOL\n• পুরস্কার: প্রতিদিন 2.0%\n\n"
            "⚠️ <i>দ্রষ্টব্য: বেস ক্যাপ ২৫০%। কমপক্ষে একজন সক্রিয় ব্যবহারকারীকে রেফার করলে ৫০০% হয়।</i>"
        ),
        "deposit_prompt": "💰 <b>SOL জমা করুন</b>\n\nদয়া করে SOL জমা করতে QR কোড স্ক্যান করুন বা নিচের ঠিকানাটি কপি করুন:\n\n<code>{wallet_address}</code>\n\n⚠ <i>শুধুমাত্র SOL পাঠান।</i>\n\n📝 <i>পাঠানোর পরে, আপনার আইডি সক্রিয় করতে এখানে TxID পাঠান!</i>",
        "no_history": "📜 <b>উত্তোলনের ইতিহাস</b>\n\nআপনার কোনো পূর্ববর্তী উত্তোলন নেই।",
        "history_title": "📜 <b>আপনার সাম্প্রতিক উত্তোলন:</b>\n\n",
        "min_withdraw": "❌ <b>সর্বনিম্ন উত্তোলনের সীমা হলো</b> <code>0.01 SOL</code>।",
        "withdraw_prompt": "💰 <b>উপলব্ধ ব্যালেন্স:</b> <code>{bal:.4f} SOL</code>\n\nপরিমাণ লিখুন:",
        "team_empty": "👥 আপনার এখনও কোনো টিম মেম্বার নেই।",
        "ref_text": "<b>🔗 আপনার রেফারেল লিংক</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>",
        "dashboard_text": (
            "👤 <b>ব্যবহারকারী ড্যাশবোর্ড</b>\n\n"
            "💰 <b>উপলব্ধ ব্যালেন্স:</b> <code>{balance:.4f} SOL</code>\n"
            "🌾 <b>মোট সেলফ ফার্মিং:</b> <code>{self_farming:.4f} SOL</code>\n"
            "🌾 <b>সেলফ ফার্মিং বোনাস:</b> <code>{self_bonus:.4f} SOL</code>\n"
            "👥 <b>ডাইরেক্ট রেফারেল বোনাস:</b> <code>{direct_ref:.4f} SOL</code>\n"
            "🤝 <b>টিম রেফারেল বোনাস:</b> <code>{team_ref:.4f} SOL</code>\n"
            "🤝 <b>টিম ফার্মিং ওভাররাইড বোনাস:</b> <code>{team_override:.4f} SOL</code>\n"
            "🏆 <b>র্যাঙ্ক এবং রয়্যালটি বোনাস:</b> <code>{royalty:.4f} SOL</code>\n"
            "📈 <b>মোট অর্জিত:</b> <code>{earned:.4f} SOL</code> (সর্বোচ্চ ক্যাপ: <code>{max_cap:.2f} SOL</code>)\n\n"
            "🧁 <b>মোট উত্তোলন:</b> <code>{withdrawn:.4f} SOL</code>\n"
            "🎯 <b>উপলব্ধ উত্তোলনের সীমা:</b> <code>{available_limit:.4f} SOL</code>\n\n"
            "📦 <b>সক্রিয় প্ল্যান:</b> {active_plan}\n"
            "🏆 <b>বর্তমান র্যাঙ্ক:</b> {current_rank}"
        ),
        "ranks_text": (
            "🏆 <b>র্যাঙ্ক এবং রয়্যালটি স্থিতি</b>\n\n"
            "<b>• মোট ডাইরেক্ট:</b> <code>{directs_count}</code> (সক্রিয়: <code>{active_directs}</code>)\n"
            "<b>• ডাইরেক্ট বিজনেস:</b> <code>{direct_biz:.2f} SOL</code>\n"
            "<b>• মোট টিম বিজনেস:</b> <code>{team_biz:.2f} SOL</code>\n"
            "<b>• বর্তমান র্যাঙ্ক:</b> <code>{current_rank_name}</code>\n"
            "<b>• পরবর্তী র্যাঙ্ক:</b> <code>{next_rank_name}</code>\n\n"
            "<b>🎯 পরবর্তী র্যাঙ্কের অগ্রগতি:</b>\n"
            "<b>• মোট লক্ষ্য ({target} SOL):</b> {total_icon} (বর্তমান: {total_volume:.2f})\n\n"
            "<b>• লেগ প্রয়োজনীয়তা চেক:</b>\n"
            "<b> - শক্তিশালী লেগ (ন্যূনতম {req_strongest} SOL):</b> {strongest_icon} (বর্তমান: <code>{highest_leg:.2f}</code>)\n"
            "<b> - অন্যান্য লেগ সংযুক্ত (ন্যূনতম {req_other} SOL):</b> {other_icon} (বর্তমান: <code>{other_legs_total:.2f}</code>)\n"
        )
    },
    "ng": {
        "select_lang": "🌐 Abeg select your language:",
        "lang_changed": "✅ Language don change to Naija Pidgin!",
        "welcome": "🚜 <b>Welcome to {PROJECT_NAME}</b>\n\nUse the buttons below to start your farming journey.",
        "btn_plans": "💎 Farming Plans",
        "btn_deposit": "💰 Deposit SOL",
        "btn_dashboard": "📊 Dashboard",
        "btn_withdraw": "🎁 Withdraw",
        "btn_ref": "🔗 Referral Link",
        "btn_team": "👥 Team Members",
        "btn_ranks": "🏆 Ranks & Royalty",
        "btn_history": "📜 Withdrawal History",
        "btn_lang": "🌐 Change Language",
        "farming_packages": (
            "<b>💎 Farming Packages (Max Cap: 250% for Self, 500% with Team):</b>\n\n"
            "1️⃣ <b>STARTER</b>\n• Limit: 0.10 - 2.0 SOL\n• Reward: 0.5% Daily\n\n"
            "2️⃣ <b>ADVANCE</b>\n• Limit: 2.10 - 10.0 SOL\n• Reward: 1.0% Daily\n\n"
            "3️⃣ <b>PREMIUM</b>\n• Limit: 10.10 - 25.0 SOL\n• Reward: 1.5% Daily\n\n"
            "4️⃣ <b>GALAXY</b>\n• Limit: 25.10 - 1000 SOL\n• Reward: 2.0% Daily\n\n"
            "⚠️ <i>Note: Base cap na 250%. Referring at least one active user go upgrade am to 500%.</i>"
        ),
        "deposit_prompt": "💰 <b>Deposit SOL</b>\n\nScan the QR code above or copy the address to deposit SOL:\n\n<code>{wallet_address}</code>\n\n⚠ <i>Send only SOL to this address.</i>\n\n📝 <i>After sending, send your Transaction Hash (TxID) here to activate your ID!</i>",
        "no_history": "📜 <b>Withdrawal History</b>\n\nYou no get any past withdrawals.",
        "history_title": "📜 <b>Your Recent Withdrawals:</b>\n\n",
        "min_withdraw": "❌ <b>Minimum withdrawal limit na</b> <code>0.01 SOL</code>.",
        "withdraw_prompt": "💰 <b>Available Balance:</b> <code>{bal:.4f} SOL</code>\n\nEnter amount:",
        "team_empty": "👥 You no get any team members yet.",
        "ref_text": "<b>🔗 Your Referral Link</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>",
        "dashboard_text": (
            "👤 <b>User Dashboard</b>\n\n"
            "💰 <b>Available Balance:</b> <code>{balance:.4f} SOL</code>\n"
            "🌾 <b>Total Self Farming:</b> <code>{self_farming:.4f} SOL</code>\n"
            "🌾 <b>Self Farming Bonus:</b> <code>{self_bonus:.4f} SOL</code>\n"
            "👥 <b>Direct Referral Bonus:</b> <code>{direct_ref:.4f} SOL</code>\n"
            "🤝 <b>Team Referral Bonus:</b> <code>{team_ref:.4f} SOL</code>\n"
            "🤝 <b>Team Farming Override Bonus:</b> <code>{team_override:.4f} SOL</code>\n"
            "🏆 <b>Rank & Royalty Bonus:</b> <code>{royalty:.4f} SOL</code>\n"
            "📈 <b>Total Earned:</b> <code>{earned:.4f} SOL</code> (Max Cap: <code>{max_cap:.2f} SOL</code>)\n\n"
            "🧁 <b>Total Withdrawals:</b> <code>{withdrawn:.4f} SOL</code>\n"
            "🎯 <b>Available Withdrawal Limit:</b> <code>{available_limit:.4f} SOL</code>\n\n"
            "📦 <b>Active Plan:</b> {active_plan}\n"
            "🏆 <b>Current Rank:</b> {current_rank}"
        ),
        "ranks_text": (
            "🏆 <b>Ranks & Royalty Status</b>\n\n"
            "<b>• Total Directs:</b> <code>{directs_count}</code> (Active: <code>{active_directs}</code>)\n"
            "<b>• Direct Business:</b> <code>{direct_biz:.2f} SOL</code>\n"
            "<b>• Total Team Business:</b> <code>{team_biz:.2f} SOL</code>\n"
            "<b>• Current Rank:</b> <code>{current_rank_name}</code>\n"
            "<b>• Next Rank:</b> <code>{next_rank_name}</code>\n\n"
            "<b>🎯 Progress for Next Rank:</b>\n"
            "<b>• Total Target ({target} SOL):</b> {total_icon} (Current: {total_volume:.2f})\n\n"
            "<b>• Leg Requirements Check:</b>\n"
            "<b> - Strongest Leg (Min {req_strongest} SOL):</b> {strongest_icon} (Current: <code>{highest_leg:.2f}</code>)\n"
            "<b> - Other Legs Combined (Min {req_other} SOL):</b> {other_icon} (Current: <code>{other_legs_total:.2f}</code>)\n"
        )
    }
}

def get_user_language(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0]:
        return row[0]
    return "en"

def get_main_keyboard(lang):
    t = translations.get(lang, translations["en"])
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(t["btn_plans"], t["btn_deposit"])
    markup.add(t["btn_dashboard"], t["btn_withdraw"])
    markup.add(t["btn_ref"], t["btn_team"])
    markup.add(t["btn_ranks"], t["btn_history"])
    markup.add(t["btn_lang"])
    return markup

# --- SOLANA AUTO-VERIFY LOGIC ---
def verify_solana_tx(tx_id):
  url = "https://api.mainnet-beta.solana.com"
  payload = {
      "jsonrpc": "2.0",
      "id": 1,
      "method": "getTransaction",
      "params": [tx_id, {"encoding": "json", "maxSupportedTransactionVersion": 0}],
  }
  try:
    response = requests.post(url, json=payload, timeout=10).json()
    if "result" in response and response["result"] is not None:
      res = response["result"]
      if res.get("meta") and res["meta"].get("err") is None:
        keys = res["transaction"]["message"]["accountKeys"]
        if ADMIN_WALLET in keys:
          idx = keys.index(ADMIN_WALLET)
          pre = res["meta"]["preBalances"][idx]
          post = res["meta"]["postBalances"][idx]
          return (post - pre) / 10**9
    return None
  except Exception as e:
    print(f"TX Error: {e}")
    return None

def get_user_direct_business(conn, user_id):
  directs = conn.execute("SELECT COALESCE(self_farming, 0) FROM users WHERE referrer_id=?", (user_id,)).fetchall()
  return sum([d[0] for d in directs])

def get_active_directs_count(conn, user_id):
    directs = conn.execute(
        "SELECT COALESCE(self_farming, 0) FROM users WHERE referrer_id=?",
        (user_id,)
    ).fetchall()
    count = 0
    for d in directs:
        if d[0] >= 0.10:
            count += 1
    return count

def get_subtree_business(conn, uid):
  childs = conn.execute("SELECT user_id, COALESCE(self_farming, 0) FROM users WHERE referrer_id=?", (uid,)).fetchall()
  total = 0
  for c_id, c_inv in childs:
      total += c_inv + get_subtree_business(conn, c_id)
  return total

def get_total_team_business(conn, user_id):
  directs = conn.execute("SELECT user_id, COALESCE(self_farming, 0) FROM users WHERE referrer_id=?", (user_id,)).fetchall()
  team_total = 0
  for d_id, d_inv in directs:
      team_total += d_inv + get_subtree_business(conn, d_id)
  return team_total

def has_direct_referral(conn, user_id):
  directs = conn.execute("SELECT COALESCE(self_farming, 0) FROM users WHERE referrer_id=?", (user_id,)).fetchall()
  for d in directs:
      if d[0] >= 0.10:
          return True
  return False

def distribute_commissions(conn, user_id, amount):
    updates = []
    curr = user_id
    try:
        for idx, pct in enumerate(REF_LEVELS):
            res = conn.execute("SELECT referrer_id FROM users WHERE user_id=?", (curr,)).fetchone()
            if not res or not res[0]:
                break
            ref_id = res[0]
            if idx > 0:
                required_active_directs = idx
                actual_active_directs = get_active_directs_count(conn, ref_id)
                if actual_active_directs < required_active_directs:
                    break
            bonus = amount * pct
            updates.append((ref_id, bonus, idx == 0))
            curr = ref_id
    except Exception as e:
        raise e

    if updates:
        try:
            for ref_id, bonus, is_direct in updates:
                if is_direct:
                    conn.execute(
                        "UPDATE users SET balance = balance + ?, total_earned = total_earned + ?, direct_referral_bonus = COALESCE(direct_referral_bonus, 0) + ? WHERE user_id = ?",
                        (bonus, bonus, bonus, ref_id)
                    )
                else:
                    conn.execute(
                        "UPDATE users SET balance = balance + ?, total_earned = total_earned + ?, team_referral_bonus = COALESCE(team_referral_bonus, 0) + ? WHERE user_id = ?",
                        (bonus, bonus, bonus, ref_id)
                    )
        except Exception as e:
            raise e

def update_team_business_recursive(conn, user_id, amount):
  try:
    conn.execute("ALTER TABLE users ADD COLUMN total_team_business REAL DEFAULT 0")
    conn.commit()
  except Exception:
    pass
  curr = user_id
  while True:
      res = conn.execute("SELECT referrer_id FROM users WHERE user_id=?", (curr,)).fetchone()
      if res and res[0]:
          upliner_id = res[0]
          conn.execute(
              "UPDATE users SET total_team_business = COALESCE(total_team_business, 0) + ? WHERE user_id = ?",
              (amount, upliner_id)
          )
          curr = upliner_id
      else:
          break

def check_and_update_rank(user_id):
    conn = get_db()
    curr_data = conn.execute("SELECT rank FROM users WHERE user_id=?", (user_id,)).fetchone()
    old_rank = curr_data[0] if curr_data else "None"

    directs = conn.execute(
        "SELECT user_id, COALESCE(self_farming, 0) FROM users WHERE referrer_id=?",
        (user_id,),
    ).fetchall()
    
    leg_businesses = []
    for d_id, d_inv in directs:
        sub_bus = get_subtree_business(conn, d_id) + d_inv
        leg_businesses.append(sub_bus)

    leg_businesses.sort(reverse=True)
    strongest_leg = leg_businesses[0] if len(leg_businesses) > 0 else 0
    other_legs_total = sum(leg_businesses[1:]) if len(leg_businesses) > 1 else 0
    total_team_bus = sum(leg_businesses)

    achieved_rank = "None"
    for r in RANKS:
        is_total_met = total_team_bus >= r["target"]
        is_strongest_met = strongest_leg >= r["strongest_leg_min"]
        is_other_legs_met = other_legs_total >= r["other_legs_min"]

        if is_total_met and is_strongest_met and is_other_legs_met:
            achieved_rank = r["name"]

    if achieved_rank != old_rank and achieved_rank != "None":
        conn.execute("UPDATE users SET rank = ? WHERE user_id = ?", (achieved_rank, user_id))
        conn.commit()
    else:
        conn.execute("UPDATE users SET rank = ? WHERE user_id = ?", (achieved_rank, user_id))
        conn.commit()
    conn.close()
  
def get_language_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
        types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        types.InlineKeyboardButton("🇨🇳 中文", callback_data="lang_zh"),
        types.InlineKeyboardButton("🇻🇳 Tiếng Việt", callback_data="lang_vi"),
        types.InlineKeyboardButton("🇮🇩 Bahasa Indonesia", callback_data="lang_id"),
        types.InlineKeyboardButton("🇹🇭 ไทย", callback_data="lang_th"),
        types.InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar"),
        types.InlineKeyboardButton("🇮🇳 हिन्दी", callback_data="lang_hi"),
        types.InlineKeyboardButton("🇧🇩 বাংলা", callback_data="lang_bn"),
        types.InlineKeyboardButton("🇳🇬 Naija (Pidgin)", callback_data="lang_ng")
    )
    return markup

@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_'))
def handle_language_selection(call):
    user_id = call.from_user.id
    selected_lang = call.data.split('_')[1]
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET language = ? WHERE user_id = ?", (selected_lang, user_id))
    conn.commit()
    conn.close()
    
    t = translations.get(selected_lang, translations["en"])
    success_msg = t["lang_changed"]
    bot.answer_callback_query(call.id, success_msg)
    
    # Send confirmation message with updated keyboard
    bot.send_message(
        call.message.chat.id,
        success_msg,
        reply_markup=get_main_keyboard(selected_lang)
    )

@bot.message_handler(func=lambda message: message.text in [translations[l]["btn_lang"] for l in translations])
def language_text_handler(message):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    select_text = translations.get(lang, translations.get("en", {})).get("select_lang", "🌐 Please select your language:")
    bot.send_message(
        message.chat.id,
        select_text,
        reply_markup=get_language_keyboard()
    )

@bot.message_handler(commands=['language', 'lang'])
def change_language_command(message):
    bot.send_message(
        message.chat.id,
        "🌐 Please select your language / कृपया अपनी भाषा चुनें:",
        reply_markup=get_language_keyboard()
    )

@bot.message_handler(commands=["start"])
def start(message):
    args = message.text.split()
    ref_id = args[1] if len(args) > 1 else None

    if ref_id and int(ref_id) == message.from_user.id:
        ref_id = None

    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, referrer_id) VALUES (?, ?)",
        (message.from_user.id, ref_id),
    )

    if ref_id:
        conn.execute(
            "UPDATE users SET referrer_id = ? WHERE user_id = ? AND (referrer_id IS NULL OR referrer_id = '')",
            (ref_id, message.from_user.id),
        )

    conn.execute(
        "UPDATE users SET username=? WHERE user_id=?",
        (message.from_user.username, message.from_user.id),
    )
    conn.commit()
    conn.close()

    user_id = message.from_user.id
    lang = get_user_language(user_id)
    welcome_template = translations.get(lang, translations["en"]).get("welcome", translations["en"]["welcome"])
    welcome_text = welcome_template.format(PROJECT_NAME=PROJECT_NAME)

    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_keyboard(lang),
    )

@bot.message_handler(func=lambda m: m.text in [translations[l]["btn_plans"] for l in translations])
def farming_plans(message):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    text = translations.get(lang, translations.get("en", {})).get("farming_packages", translations["en"]["farming_packages"])
    bot.send_message(message.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text in [translations[l]["btn_deposit"] for l in translations])
def deposit_sol(message):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    wallet_address = ADMIN_WALLET  
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={wallet_address}"
    
    template = translations.get(lang, translations["en"]).get("deposit_prompt", translations["en"]["deposit_prompt"])
    caption = template.format(wallet_address=wallet_address)
    
    sent = bot.send_photo(message.chat.id, photo=qr_url, caption=caption, parse_mode="HTML")
    bot.register_next_step_handler(sent, process_deposit)

def process_deposit(message):
  if not message.text:
      bot.send_message(message.chat.id, "❌ Please enter a valid Transaction ID.")
      return
  txid = message.text.strip()
  bot.send_message(message.chat.id, "🔍 <b>Verifying transaction...</b>", parse_mode="HTML")

  conn = get_db()
  if conn.execute("SELECT txid FROM transactions WHERE txid=?", (txid,)).fetchone():
    bot.send_message(message.chat.id, "❌ <b>This Transaction ID has already been used.</b>", parse_mode="HTML")
    conn.close()
    return

  amount = verify_solana_tx(txid)
  if amount and amount >= 0.10:
    if amount <= 2.0:
      plan = "starter"
    elif amount <= 10.0:
      plan = "advance"
    elif amount <= 25.0:
      plan = "premium"
    else:
      plan = "galaxy"

    conn.execute(
          "UPDATE users SET self_farming = self_farming + ?, total_investment = total_investment + ?, plan_name = ? WHERE user_id = ?",
          (amount, amount, plan, message.from_user.id),
      )
    conn.execute("INSERT INTO transactions (txid) VALUES (?)", (txid,))
    conn.commit()

    distribute_commissions(conn, message.from_user.id, amount)
    update_team_business_recursive(conn, message.from_user.id, amount)

    res = conn.execute("SELECT referrer_id FROM users WHERE user_id=?", (message.from_user.id,)).fetchone()
    if res and res[0]:
      check_and_update_rank(res[0])
    check_and_update_rank(message.from_user.id)

    bot.send_message(
        message.chat.id,
        f"✅ <b>Success!</b> <code>{amount} SOL</code> deposit confirmed. Plan: <b>{PACKAGES[plan]['name']}</b>",
        parse_mode="HTML",
    )
  else:
    bot.send_message(message.chat.id, "❌ <b>Verification Failed!</b> Invalid transaction or amount less than minimum <code>0.10 SOL</code>.", parse_mode="HTML")
  conn.close()

@bot.message_handler(commands=['dashboard'])
@bot.message_handler(func=lambda m: m.text and any(translations[l]["btn_dashboard"] in m.text for l in translations))
def dashboard_handler(message):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    try:
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT balance, self_farming, self_farming_bonus, 
                   direct_referral_bonus, team_referral_bonus, 
                   team_farming_override_bonus, rank_royalty_bonus, 
                   total_earned, total_withdrawn, plan_name, rank 
            FROM users WHERE user_id = ?
        """, (user_id,))
        u = cursor.fetchone()
        has_ref = has_direct_referral(conn, user_id)
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")
        u = None

    if not u:
        bot.send_message(message.chat.id, "Please start the bot first using /start", parse_mode="HTML")
        return

    balance = u["balance"] if u["balance"] is not None else 0.0
    self_farming = u["self_farming"] if u["self_farming"] is not None else 0.0
    self_bonus = u["self_farming_bonus"] if u["self_farming_bonus"] is not None else 0.0
    direct_ref = u["direct_referral_bonus"] if u["direct_referral_bonus"] is not None else 0.0
    team_ref = u["team_referral_bonus"] if u["team_referral_bonus"] is not None else 0.0
    team_override = u["team_farming_override_bonus"] if u["team_farming_override_bonus"] is not None else 0.0
    royalty = u["rank_royalty_bonus"] if u["rank_royalty_bonus"] is not None else 0.0
    earned = u["total_earned"] if u["total_earned"] is not None else 0.0
    withdrawn = u["total_withdrawn"] if u["total_withdrawn"] is not None else 0.0
    active_plan = u["plan_name"] if u["plan_name"] else "None"
    current_rank = u["rank"] if u["rank"] else "None"

    multiplier = 5.0 if has_ref else 2.5
    max_cap = self_farming * multiplier
    available_limit = max_cap - withdrawn

    template = translations.get(lang, translations["en"]).get("dashboard_text", translations["en"]["dashboard_text"])
    text = template.format(
        balance=balance,
        self_farming=self_farming,
        self_bonus=self_bonus,
        direct_ref=direct_ref,
        team_ref=team_ref,
        team_override=team_override,
        royalty=royalty,
        earned=earned,
        max_cap=max_cap,
        withdrawn=withdrawn,
        available_limit=available_limit,
        active_plan=active_plan,
        current_rank=current_rank
    )
    bot.send_message(message.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text in [translations[l]["btn_ranks"] for l in translations])
def team_ranks(message):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    try:
        check_and_update_rank(user_id)
    except Exception as e:
        print(f"Rank update error: {e}")

    conn = get_db()
    u = conn.execute("SELECT rank FROM users WHERE user_id=?", (user_id,)).fetchone()
    directs_cursor = conn.execute(
        "SELECT user_id, COALESCE(self_farming, 0) FROM users WHERE referrer_id=?",
        (user_id,)
    ).fetchall()

    directs_count = len(directs_cursor)
    active_directs = get_active_directs_count(conn, user_id)
    direct_biz = sum([d[1] for d in directs_cursor])
    team_biz = get_total_team_business(conn, user_id)

    leg_businesses = []
    for d_id, d_inv in directs_cursor:
        sub_bus = get_subtree_business(conn, d_id) + d_inv
        leg_businesses.append(sub_bus)

    leg_businesses.sort(reverse=True)
    highest_leg = leg_businesses[0] if len(leg_businesses) > 0 else 0
    other_legs_total = sum(leg_businesses[1:]) if len(leg_businesses) > 1 else 0

    current_rank_name = u[0] if u and u[0] else "None"
    
    next_rank = None
    if current_rank_name == "None":
        next_rank = RANKS[0]
    else:
        for idx, r in enumerate(RANKS):
            if r["name"] == current_rank_name:
                if idx + 1 < len(RANKS):
                    next_rank = RANKS[idx + 1]
                break

    conn.close()

    if next_rank:
        next_rank_name = next_rank["name"]
        target = next_rank["target"]
        req_strongest = next_rank["strongest_leg_min"]
        req_other = next_rank["other_legs_min"]

        is_strongest_met = highest_leg >= req_strongest
        strongest_rem = 0 if is_strongest_met else max(0, req_strongest - highest_leg)
        strongest_icon = f"✅" if is_strongest_met else f"❌ (Need {strongest_rem:.2f} SOL more)"

        is_other_met = other_legs_total >= req_other
        other_rem = 0 if is_other_met else max(0, req_other - other_legs_total)
        other_icon = f"✅" if is_other_met else f"❌ (Need {other_rem:.2f} SOL more)"

        total_volume = highest_leg + other_legs_total
        is_total_met = total_volume >= target
        total_rem = 0 if is_total_met else max(0, target - total_volume)
        total_icon = f"✅" if is_total_met else f"❌ (Need {total_rem:.2f} SOL more)"
    else:
        next_rank_name = "Max Rank Achieved 🎉"
        strongest_icon = "✅"
        other_icon = "✅"
        total_icon = "✅"
        req_strongest = 0
        req_other = 0
        target = 0
        total_volume = highest_leg + other_legs_total

    template = translations.get(lang, translations["en"]).get("ranks_text", translations["en"]["ranks_text"])
    text = template.format(
        directs_count=directs_count,
        active_directs=active_directs,
        direct_biz=direct_biz,
        team_biz=team_biz,
        current_rank_name=current_rank_name,
        next_rank_name=next_rank_name,
        target=target,
        total_icon=total_icon,
        total_volume=total_volume,
        req_strongest=req_strongest,
        strongest_icon=strongest_icon,
        highest_leg=highest_leg,
        req_other=req_other,
        other_icon=other_icon,
        other_legs_total=other_legs_total
    )
    bot.send_message(message.chat.id, text, parse_mode="HTML")

# --- ADMIN PANEL ---
def admin_panel_markup():
  markup = InlineKeyboardMarkup(row_width=2)
  markup.add(
      InlineKeyboardButton("📊 View Stats", callback_data="admin:stats"),
      InlineKeyboardButton("👤 Manage User", callback_data="admin:manage_user"),
  )
  markup.add(InlineKeyboardButton("📋 List All Users", callback_data="admin:list_users"))
  markup.add(
    InlineKeyboardButton("➕ Top-up Free ID", callback_data="admin:topup_free"),
    InlineKeyboardButton("➕ Top-up Paid ID", callback_data="admin:topup_paid"),
  )
  markup.add(InlineKeyboardButton("📢 Broadcast Message", callback_data="admin:broadcast"))
  markup.add(InlineKeyboardButton("❌ Close", callback_data="admin:close"))
  return markup

def admin_user_markup(user_id):
  markup = InlineKeyboardMarkup(row_width=2)
  markup.add(
      InlineKeyboardButton("➕ Manual Top-up", callback_data=f"admin:user_topup:{user_id}"),
      InlineKeyboardButton("🔄 Refresh", callback_data=f"admin:user:{user_id}"),
  )
  markup.add(InlineKeyboardButton("⬅ Admin Panel", callback_data="admin:panel"))
  return markup

def admin_stats_text():
  conn = get_db()
  totals = conn.execute(
      """SELECT
           COUNT(*),
           SUM(CASE WHEN total_investment >= 0.10 THEN 1 ELSE 0 END),
           SUM(CASE WHEN total_investment < 0.10 THEN 1 ELSE 0 END),
           COALESCE(SUM(total_investment), 0),
           COALESCE(SUM(balance), 0),
           COALESCE(SUM(total_earned), 0),
           COALESCE(SUM(total_withdrawn), 0)
         FROM users"""
  ).fetchone()
  tx_count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
  action_count = conn.execute("SELECT COUNT(*) FROM admin_actions").fetchone()[0]
  conn.close()

  return (
      "<b>📊 ADMIN STATS</b>\n\n"
      f"<b>Total users:</b> <code>{totals[0] or 0}</code>\n"
      f"<b>Active users (≥ 0.10 SOL):</b> <code>{totals[1] or 0}</code>\n"
      f"<b>Free IDs (&lt; 0.10 SOL):</b> <code>{totals[2] or 0}</code>\n"
      f"<b>Total investment:</b> <code>{totals[3] or 0:.4f} SOL</code>\n"
      f"<b>User balances:</b> <code>{totals[4] or 0:.4f} SOL</code>\n"
      f"<b>Total earned:</b> <code>{totals[5] or 0:.4f} SOL</code>\n"
      f"<b>Total withdrawn:</b> <code>{totals[6] or 0:.4f} SOL</code>\n"
      f"<b>Verified transactions:</b> <code>{tx_count}</code>\n"
      f"<b>Manual admin actions:</b> <code>{action_count}</code>"
  )

def admin_user_list_messages():
  conn = get_db()
  users = conn.execute("SELECT user_id, username, balance FROM users ORDER BY user_id").fetchall()
  conn.close()

  if not users:
    return ["<b>📋 ALL USERS</b>\n\nNo registered users found."]

  lines = [f"<b>📋 ALL USERS</b> <code>({len(users)} total)</code>\n", "<b>Telegram ID | Username | Balance</b>"]
  for user_id, username, balance in users:
    display_username = f"@{username}" if username else "Not available"
    lines.append(f"<code>{user_id}</code> | <code>{escape(display_username)}</code> | <code>{balance:.4f} SOL</code>")

  messages = []
  current = ""
  for line in lines:
    candidate = f"{current}\n{line}" if current else line
    if current and len(candidate) > 3800:
      messages.append(current)
      current = line
    else:
      current = candidate
  if current:
    messages.append(current)
  return messages

def admin_user_text(user_id):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    user = conn.execute(
        "SELECT user_id, referrer_id, balance, total_investment, total_earned, total_withdrawn, plan_name, rank, status FROM users WHERE user_id=?",
        (user_id,),
    ).fetchone()

    if user:
        active_directs = get_active_directs_count(conn, user_id)
        direct_business = get_user_direct_business(conn, user_id)
        conn.close()
    else:
        conn.close()
        return None

    return (
        f"<b>👤 USER DETAILS</b>\n\n"
        f"<b>User ID:</b> <code>{user['user_id']}</code>\n"
        f"<b>Referrer ID:</b> <code>{user['referrer_id'] or 'None'}</code>\n"
        f"<b>Balance:</b> <code>{user['balance']:.4f} SOL</code>\n"
        f"<b>Investment:</b> <code>{user['total_investment']:.4f} SOL</code>\n"
        f"<b>Total earned:</b> <code>{user['total_earned']:.4f} SOL</code>\n"
        f"<b>Total withdrawn:</b> <code>{user['total_withdrawn']:.4f} SOL</code>\n"
        f"<b>Plan:</b> <code>{user['plan_name'] or 'None'}</code>\n"
        f"<b>Rank:</b> <code>{user['rank'] or 'None'}</code>\n"
        f"<b>Status:</b> <code>{user['status'] or 'inactive'}</code>\n"
        f"<b>Active directs:</b> <code>{active_directs}</code>\n"
        f"<b>Direct business:</b> <code>{direct_business:.4f} SOL</code>"
    )

def record_admin_topup(admin_id, user_id, amount, note, is_paid=False):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    try:
        existed = conn.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,)).fetchone() is not None
        conn.execute("INSERT OR IGNORE INTO users (user_id, referrer_id, status) VALUES (?, NULL, 'inactive')", (user_id,))

        amount = float(amount)
        if amount <= 2.0:
            plan_name = "starter"
        elif amount <= 10.0:
            plan_name = "advance"
        elif amount <= 25.0:
            plan_name = "premium"
        else:
            plan_name = "galaxy"

        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_topups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                amount REAL,
                plan_name TEXT,
                timestamp DATETIME
            )
        ''')
        cursor.execute('INSERT INTO admin_topups (user_id, amount, plan_name, timestamp) VALUES (?, ?, ?, datetime("now"))', (user_id, amount, plan_name))

        if is_paid:
            max_cap = amount * 2.5 
            cursor.execute(
                "UPDATE users SET self_farming = COALESCE(self_farming, 0) + ?, max_cap = ?, status = 'active', plan_name = ? WHERE user_id = ?",
                (amount, max_cap, plan_name, user_id),
            )
            distribute_commissions(conn, user_id, amount)
            update_team_business_recursive(conn, user_id, amount)
        else:
            cursor.execute(
                "UPDATE users SET self_farming = COALESCE(self_farming, 0) + ?, total_earned = COALESCE(total_earned, 0) + ? WHERE user_id = ?",
                (amount, amount, user_id),
            )

        cursor.execute(
            "INSERT INTO admin_actions (admin_id, action, target_user_id, amount, note) VALUES (?, ?, ?, ?, ?)",
            (admin_id, "manual_topup_paid" if is_paid else "manual_topup_free", user_id, amount, note),
        )
        conn.commit()
        return existed
    finally:
        conn.close()

def queue_admin_topup(admin_id, user_id, amount, note, is_paid=False):
   token = uuid.uuid4().hex
   ADMIN_PENDING_TOPUPS[token] = {
       "admin_id": admin_id,
       "user_id": user_id,
       "amount": amount,
       "note": note,
       "is_paid": is_paid,
   }
   markup = InlineKeyboardMarkup(row_width=2)
   markup.add(
       InlineKeyboardButton("✅ Confirm top-up", callback_data=f"admin:confirm_topup:{token}"),
       InlineKeyboardButton("❌ Cancel", callback_data=f"admin:cancel_topup:{token}")
   )
   bot.send_message(
       admin_id,
       f"<b>⚠️ Confirm manual top-up</b>\n\n<b>User ID:</b> <code>{user_id}</code>\n<b>Amount:</b> <code>{amount:.8f} SOL</code>\n",
       reply_markup=markup,
       parse_mode="HTML"
   )

def admin_lookup_user(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        user_id = int(message.text.strip().split()[0])
    except (ValueError, IndexError, AttributeError):
        bot.send_message(message.chat.id, "❌ <b>Invalid user ID.</b>", parse_mode="HTML")
        return

    text = admin_user_text(user_id)
    if text is None:
        bot.send_message(message.chat.id, f"<b>User ID {user_id} does not exist yet.</b>", reply_markup=admin_panel_markup(), parse_mode="HTML")
        return
    bot.send_message(message.chat.id, text, reply_markup=admin_user_markup(user_id), parse_mode="HTML")

def admin_topup_amount(message, user_id):
  if message.from_user.id != ADMIN_ID:
    return
  try:
    amount = float(message.text.strip().split()[0])
    if amount <= 0:
      raise ValueError
  except (ValueError, IndexError):
    bot.send_message(ADMIN_ID, "❌ <b>Invalid amount.</b>", parse_mode="HTML")
    return
  queue_admin_topup(ADMIN_ID, user_id, amount, "Manual user top-up", is_paid=True)

def admin_free_topup(message):
  if message.from_user.id != ADMIN_ID:
      return
  parts = message.text.strip().split()
  try:
      user_id, amount = int(parts[0]), float(parts[1])
  except (ValueError, IndexError):
      sent = bot.send_message(ADMIN_ID, "<b>❌ Invalid format. Use:</b> <code>UserID Amount</code>", parse_mode="HTML")
      bot.register_next_step_handler(sent, admin_free_topup)
      return
  queue_admin_topup(ADMIN_ID, user_id, amount, "Manual top-up from free ID panel")

def admin_paid_topup(message):
  if message.from_user.id != ADMIN_ID:
      return
  parts = message.text.strip().split()
  try:
      user_id, amount = int(parts[0]), float(parts[1])
  except (ValueError, IndexError):
      sent = bot.send_message(ADMIN_ID, "<b>❌ Invalid format. Use:</b> <code>user_id amount</code>", parse_mode="HTML")
      bot.register_next_step_handler(sent, admin_paid_topup)
      return
  queue_admin_topup(ADMIN_ID, user_id, amount, "Manual top-up from paid ID panel", is_paid=True)

@bot.message_handler(commands=["admin"])
def admin_command(message):
  if message.from_user.id != ADMIN_ID:
    return
  bot.send_message(message.chat.id, "<b>🛠 ADMIN PANEL</b>\nChoose an action:", reply_markup=admin_panel_markup(), parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("admin:"))
def admin_callback(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    if call.from_user.id != ADMIN_ID:
        return

    parts = call.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "panel":
        bot.send_message(call.message.chat.id, "<b>🛠️ ADMIN PANEL</b>", reply_markup=admin_panel_markup(), parse_mode="HTML")
    elif action == "stats":
        bot.send_message(call.message.chat.id, admin_stats_text(), reply_markup=admin_panel_markup(), parse_mode="HTML")
    elif action == "list_users":
        for index, text in enumerate(admin_user_list_messages()):
            bot.send_message(call.message.chat.id, text, reply_markup=admin_panel_markup() if index == 0 else None, parse_mode="HTML")
    elif action == "manage_user":
        sent = bot.send_message(call.message.chat.id, "<b>Send the user ID to inspect:</b>", parse_mode="HTML")
        bot.register_next_step_handler(sent, admin_lookup_user)
    elif action == "topup_free":
        sent = bot.send_message(call.message.chat.id, "<b>Send Free ID and Amount (e.g., 12345 0.5):</b>", parse_mode="HTML")
        bot.register_next_step_handler(sent, admin_free_topup)
    elif action == "topup_paid":
        sent = bot.send_message(call.message.chat.id, "<b>Send Paid ID and Amount (e.g., 12345 0.5):</b>", parse_mode="HTML")
        bot.register_next_step_handler(sent, admin_paid_topup)
    elif action == "broadcast":
        ADMIN_BROADCAST_STATE[call.from_user.id] = "WAITING_FOR_BROADCAST"
        bot.send_message(call.message.chat.id, "📢 <b>Broadcast Mode Activated</b>\n\nPlease send the message you want to broadcast:", parse_mode="HTML")
    elif action == "user":
        try:
            user_id = int(parts[2])
        except (ValueError, IndexError):
            return
        text = admin_user_text(user_id)
        if text:
            bot.send_message(call.message.chat.id, text, reply_markup=admin_user_markup(user_id), parse_mode="HTML")
    elif action == "user_topup":
        try:
            user_id = int(parts[2])
        except (ValueError, IndexError):
            return
        sent = bot.send_message(call.message.chat.id, f"<b>Enter SOL amount for user {user_id}:</b>", parse_mode="HTML")
        bot.register_next_step_handler(sent, admin_topup_amount, user_id)
    elif action == "confirm_topup":
        token = parts[2] if len(parts) > 2 else ""
        pending = ADMIN_PENDING_TOPUPS.pop(token, None)
        if not pending:
            bot.send_message(call.message.chat.id, "⚠️ <b>Expired request.</b>", reply_markup=admin_panel_markup(), parse_mode="HTML")
            return
        record_admin_topup(call.from_user.id, pending["user_id"], pending["amount"], "Confirmed top-up", pending.get("is_paid", False))
        bot.send_message(call.message.chat.id, f"✅ <b>Top-up complete for user {pending['user_id']}</b>", parse_mode="HTML")
    elif action == "cancel_topup":
        ADMIN_PENDING_TOPUPS.pop(parts[2] if len(parts) > 2 else "", None)
        bot.send_message(call.message.chat.id, "❌ <b>Cancelled.</b>", reply_markup=admin_panel_markup(), parse_mode="HTML")
    elif action == "close":
        bot.edit_message_text("<b>Admin panel closed.</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML")

@bot.message_handler(content_types=["text", "photo"], func=lambda message: ADMIN_BROADCAST_STATE.get(message.from_user.id) == "WAITING_FOR_BROADCAST")
def execute_broadcast(message):
    admin_id = message.from_user.id
    if admin_id != ADMIN_ID:
        return
    ADMIN_BROADCAST_STATE.pop(admin_id, None)

    conn = get_db()
    users = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()

    total_users = len(users)
    success_count, fail_count = 0, 0
    status_msg = bot.send_message(message.chat.id, f"🚀 <b>Broadcast started...</b>\nTotal users: {total_users}", parse_mode="HTML")

    for u in users:
        u_id = u[0]
        try:
            if message.photo:
                photo_id = message.photo[-1].file_id
                caption = message.caption or ""
                bot.send_photo(u_id, photo_id, caption=caption, parse_mode="HTML")
            else:
                bot.send_message(u_id, message.text, parse_mode="HTML")
            success_count += 1
        except Exception:
            fail_count += 1

    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=status_msg.message_id,
        text=(
            "✅ <b>Broadcast Completed!</b>\n\n"
            f"• Total Users: <code>{total_users}</code>\n"
            f"• Successfully Sent: <code>{success_count}</code>\n"
            f"• Failed / Blocked: <code>{fail_count}</code>"
        ),
        parse_mode="HTML"
    )

@bot.message_handler(func=lambda m: m.text in [translations[l]["btn_history"] for l in translations])
def withdrawal_history(message):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    
    conn = get_db()
    rows = conn.execute("SELECT amount, status, txid, created_at FROM withdrawals WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,)).fetchall()
    conn.close()
    
    if not rows:
        no_hist_text = translations.get(lang, translations["en"]).get("no_history", translations["en"]["no_history"])
        bot.send_message(message.chat.id, no_hist_text, parse_mode="HTML")
        return
    
    title_text = translations.get(lang, translations["en"]).get("history_title", translations["en"]["history_title"])
    text = title_text
    for amt, status, txid, date in rows:
        text += f"• <code>{amt:.4f} SOL</code> | Status: <b>{status}</b>\n  🔗 <b>TxID:</b> <code>{escape(txid)}</code>\n  🕒 <code>{date}</code>\n\n"
    bot.send_message(message.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and any(translations[l]["btn_withdraw"] in m.text for l in translations))
def withdraw_start(message):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    conn = get_db()
    user_row = conn.execute("SELECT last_withdrawal_date FROM users WHERE user_id=?", (user_id,)).fetchone()
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    if user_row and user_row[0] == today_date:
        conn.close()
        bot.send_message(message.chat.id, "❌ <b>You can only withdraw once per day! Please try again tomorrow.</b>", parse_mode="HTML")
        return

    u = conn.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    
    bal = u[0] if u else 0
    if bal < 0.01:
        min_text = translations.get(lang, translations["en"]).get("min_withdraw", translations["en"]["min_withdraw"])
        bot.send_message(message.chat.id, min_text, parse_mode="HTML")
        return
        
    prompt_template = translations.get(lang, translations["en"]).get("withdraw_prompt", translations["en"]["withdraw_prompt"])
    msg = bot.send_message(message.chat.id, prompt_template.format(bal=bal), parse_mode="HTML")
    bot.register_next_step_handler(msg, process_withdrawal_amount)

def process_withdrawal_amount(message):
    try:
        amount = float(message.text)
    except ValueError:
        bot.send_message(message.chat.id, "❌ Enter a valid number.")
        return

    conn = get_db()
    u = conn.execute("SELECT balance FROM users WHERE user_id=?", (message.from_user.id,)).fetchone()
    conn.close()
    bal = u[0] if u else 0

    if amount < 0.01 or amount > bal:
        bot.send_message(message.chat.id, "❌ Invalid amount or insufficient balance.")
        return

    msg = bot.send_message(message.chat.id, "Enter your Solana <b>Wallet Address</b>:", parse_mode="HTML")
    bot.register_next_step_handler(msg, process_withdrawal_address, amount)

def process_withdrawal_address(message, amount):
    wallet_address = message.text.strip()
    user_id = message.from_user.id
    fee = amount * 0.10
    net_amount = amount - fee

    bot.send_message(message.chat.id, f"✅ Withdrawal request submitted!\n• Requested: <code>{amount:.4f} SOL</code>\n• Fee (10%): <code>{fee:.4f} SOL</code>\n• You Will Get: <code>{net_amount:.4f} SOL</code>", parse_mode="HTML")
    
    today_date = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    conn.execute("UPDATE users SET last_withdrawal_date = ? WHERE user_id = ?", (today_date, user_id))
    conn.commit()
    conn.close()

    admin_msg = (
        f"🚨 <b>Withdrawal Request</b>\n"
        f"User: <code>{user_id}</code>\n"
        f"Requested Amt: <code>{amount:.4f} SOL</code>\n"
        f"Fee (10%): <code>{fee:.4f} SOL</code>\n"
        f"👉 <b>Net Send to User:</b> <code>{net_amount:.4f} SOL</code>\n"
        f"Wallet: <code>{wallet_address}</code>\n\n"
        f"Command to Pay:\n<code>/pay {user_id} {amount} [TxID]</code>"
    )
    bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")

@bot.message_handler(commands=["pay"])
def admin_pay(message):
  if message.from_user.id == ADMIN_ID:
    try:
      args = message.text.split()
      uid, amt = int(args[1]), float(args[2])
      txid = args[3] if len(args) > 3 else "Paid by Admin"
      net_amt = amt * 0.9
      
      conn = get_db()
      conn.execute("UPDATE users SET balance = balance - ?, total_withdrawn = total_withdrawn + ? WHERE user_id = ?", (amt, amt, uid))
      conn.execute("INSERT INTO withdrawals (user_id, amount, wallet_address, txid) VALUES (?, ?, ?, ?)", (uid, amt, "Admin Paid", txid))
      conn.commit()
      conn.close()
      
      bot.send_message(uid, f"📤 <b>Paid:</b> <code>{net_amt:.4f} SOL</code> sent!\n🔗 <b>TxID:</b> <code>{txid}</code>", parse_mode="HTML")
      bot.send_message(ADMIN_ID, "✅ <b>Done & Saved TxID!</b>", parse_mode="HTML")
    except Exception as e:
      bot.send_message(ADMIN_ID, f"Error: {e}", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text in [translations[l]["btn_team"] for l in translations])
def my_team_handler(message):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    
    conn = get_db()
    query = """
    WITH RECURSIVE downline(user_id, self_farming, level) AS (
        SELECT user_id, COALESCE(self_farming, 0), 1 AS level FROM users WHERE referrer_id = ?
        UNION ALL
        SELECT u.user_id, COALESCE(u.self_farming, 0), d.level + 1 FROM users u
        JOIN downline d ON u.referrer_id = d.user_id WHERE d.level < 25
    )
    SELECT user_id, self_farming, level FROM downline;
    """
    team_data = conn.execute(query, (user_id,)).fetchall()
    conn.close()

    if not team_data:
        empty_text = translations.get(lang, translations["en"]).get("team_empty", translations["en"]["team_empty"])
        bot.send_message(message.chat.id, empty_text, parse_mode="HTML")
        return

    total_members = len(team_data)
    level_counts = {}
    for uid, sf, lvl in team_data:
        level_counts[lvl] = level_counts.get(lvl, 0) + 1

    team_text = f"<b>👥 Your 25-Level Team Overview</b>\n\n• <b>Total Members:</b> {total_members}\n\nSelect a level below for members & business breakdown:"
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = [types.InlineKeyboardButton(f"Lvl {lvl} ({level_counts[lvl]})", callback_data=f"view_lvl_{lvl}") for lvl in sorted(level_counts.keys()) if lvl <= 25]
    markup.add(*buttons)

    bot.send_message(message.chat.id, team_text, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("view_lvl_"))
def callback_view_level(call):
    target_level = int(call.data.split("_")[2])
    user_id = call.from_user.id

    conn = get_db()
    query = """
    WITH RECURSIVE downline(user_id, self_farming, level) AS (
        SELECT user_id, COALESCE(self_farming, 0), 1 AS level FROM users WHERE referrer_id = ?
        UNION ALL
        SELECT u.user_id, COALESCE(u.self_farming, 0), d.level + 1 FROM users u
        JOIN downline d ON u.referrer_id = d.user_id WHERE d.level < 25
    )
    SELECT user_id, self_farming FROM downline WHERE level = ?;
    """
    members = conn.execute(query, (user_id, target_level)).fetchall()
    conn.close()

    if not members:
        bot.answer_callback_query(call.id, f"No members at Level {target_level}.", show_alert=True)
        return

    total_lvl_bus = sum([sf for uid, sf in members])
    text = f"<b>👥 Level {target_level} Details:</b>\n• Total Business: <code>{total_lvl_bus:.2f} SOL</code>\n\n"
    for idx, (uid, sf) in enumerate(members, 1):
        text += f"{idx}. ID: <code>{uid}</code> | Farming: <code>{sf:.2f} SOL</code>\n"

    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text[:4000], parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text in [translations[l]["btn_ref"] for l in translations])
def referral_link_handler(message):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    bot_username = bot.get_me().username
    
    template = translations.get(lang, translations["en"]).get("ref_text", translations["en"]["ref_text"])
    text = template.format(bot_username=bot_username, user_id=user_id)
    bot.send_message(message.chat.id, text, parse_mode="HTML")

def roi_worker():
    while True:
        try:
            conn = get_db()
            users = conn.execute("SELECT user_id, self_farming, plan_name, total_earned, rank FROM users WHERE self_farming > 0 AND plan_name IS NOT NULL").fetchall()

            for uid, self_farm, p_id, earned, rank in users:
                if not p_id:
                    continue
                plan_key = str(p_id).strip().lower()
                if plan_key in PACKAGES:
                    has_ref = has_direct_referral(conn, uid)
                    multiplier = 5.0 if has_ref else 2.5
                    max_allowed_earn = self_farm * multiplier

                    if earned < max_allowed_earn:
                        roi = self_farm * PACKAGES[plan_key]["roi"]
                        royalty = 0
                        for r in RANKS:
                            if r["name"] == rank:
                                royalty = r["daily_royalty"]
                                break

                        total_payout = roi + royalty
                        conn.execute(
                            "UPDATE users SET balance = balance + ?, total_earned = total_earned + ?, self_farming_bonus = self_farming_bonus + ?, rank_royalty_bonus = rank_royalty_bonus + ? WHERE user_id=?",
                            (total_payout, total_payout, roi, royalty, uid),
                        )
                        conn.commit()

                        curr = uid
                        for level_idx, pct in enumerate(OVERRIDE_LEVELS):
                            res = conn.execute("SELECT referrer_id FROM users WHERE user_id=?", (curr,)).fetchone()
                            if res and res[0]:
                                ref_id = res[0]
                                required_direct_biz = 0.0 if level_idx == 0 else float(level_idx + 1)
                                if get_user_direct_business(conn, ref_id) >= required_direct_biz:
                                    override_bonus = roi * pct
                                    conn.execute(
                                        "UPDATE users SET balance = balance + ?, total_earned = total_earned + ?, team_farming_override_bonus = COALESCE(team_farming_override_bonus, 0) + ? WHERE user_id = ?",
                                        (override_bonus, override_bonus, override_bonus, ref_id)
                                    )
                                    conn.commit()
                                curr = ref_id
                            else:
                                break

            conn.close()
        except Exception as e:
            print(f">>> DEBUG: ROI Worker Error -> {e}")

        time.sleep(300)

if __name__ == "__main__":
    Thread(target=roi_worker, daemon=True).start()
    print("Solana Farming Bot is running successfully...")
    keep_alive()

    while True:
        try:
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            print(f"Polling error: {e}. Retrying in 5 seconds...")
            time.sleep(5)

print(">>> DEBUG: SCRIPT STARTED FROM TOP", flush=True)
from flask import Flask
import os
import sqlite3
import requests
import time
from threading import Thread
from datetime import datetime
from html import escape
import base58
import telebot
import telebot.types as types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.transaction import Transaction
from solana.rpc.api import Client

app = Flask("")

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

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

# --- SOLANA RPC & PAYOUT CONFIG ---
WALLET_PRIVATE_KEY_STR = os.environ.get("WALLET_PRIVATE_KEY")
SOLANA_RPC_URL = os.environ.get("RPC_URL", "https://api.mainnet-beta.solana.com")
solana_client = Client(SOLANA_RPC_URL)

def get_admin_keypair():
    if not WALLET_PRIVATE_KEY_STR:
        return None
    secret_bytes = base58.b58decode(WALLET_PRIVATE_KEY_STR)
    return Keypair.from_bytes(secret_bytes)

def send_sol_payout(to_pubkey_str, amount_in_sol):
    try:
        payer = get_admin_keypair()
        if not payer:
            return False, "WALLET_ERROR"

        # --- CHECK PAYER WALLET BALANCE ---
        balance_response = solana_client.get_balance(payer.pubkey())
        lamports_balance = balance_response.value
        sol_balance = lamports_balance / 1_000_000_000

        if sol_balance < amount_in_sol:
            try:
                bot.send_message(
                    ADMIN_ID,
                    f"🚨 <b>WARNING: Low Admin Wallet Balance!</b>\n\n"
                    f"• Required Payout: {amount_in_sol} SOL\n"
                    f"• Available Balance: {sol_balance} SOL\n\n"
                    f"⚠️ Please top up the payout wallet immediately.",
                    parse_mode="HTML"
                )
            except Exception:
                pass
            return False, f"Insufficient wallet balance. Available: {sol_balance} SOL"

        to_pubkey = Pubkey.from_string(to_pubkey_str)
        lamports = int(amount_in_sol * 1_000_000_000)
        instruction = transfer(
            TransferParams(
                from_pubkey=payer.pubkey(),
                to_pubkey=to_pubkey,
                lamports=lamports
            )
        )
        res = solana_client.get_latest_blockhash()
        recent_blockhash = res.value.blockhash

        # --- BULLETPROOF SOLDERS TRANSACTION BUILD & SIGN ---
        txn = Transaction.new_with_payer(
            [instruction],
            payer.pubkey()
        )
        txn.sign([payer], recent_blockhash)
        
        result = solana_client.send_transaction(txn)
        return True, str(result.value)

    except Exception as e:
        return False, str(e)

# --- PACKAGES ---
PACKAGES = {
    "starter": {"name": "STARTER", "roi": 0.005, "min": 0.10, "max": 2.00, "cap": 2.5},
    "advance": {"name": "ADVANCE", "roi": 0.01, "min": 2.10, "max": 10.00, "cap": 2.5},
    "premium": {"name": "PREMIUM", "roi": 0.015, "min": 10.10, "max": 25.00, "cap": 2.5},
    "galaxy": {"name": "GALAXY", "roi": 0.02, "min": 25.10, "max": 100.00, "cap": 2.5}
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
    {"level": 10, "name": "Supreme Universe", "target": 1000000, "strongest_leg_min": 400000, "other_legs_min": 600000, "daily_royalty": 1000.00}
]

# --- DATABASE SETUP ---
def get_db():
    conn = sqlite3.connect("solana_farming.db", check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
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
    )''')
    try:
        c.execute("ALTER TABLE users ADD COLUMN last_withdrawal_date TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'en'")
    except sqlite3.OperationalError:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS transactions (txid TEXT PRIMARY KEY)''')
    c.execute('''CREATE TABLE IF NOT EXISTS admin_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        target_user_id INTEGER,
        amount REAL,
        note TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        wallet_address TEXT NOT NULL,
        txid TEXT DEFAULT 'Pending',
        status TEXT DEFAULT 'Pending',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

init_db()

# --- 10 GLOBAL LANGUAGES TRANSLATIONS (100% COMPLETE) ---
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
        "farming_packages": "<b>💎 Farming Packages (Max Cap: 250% for Self, 500% with Team):</b>\n\n1️⃣ <b>STARTER</b>\n• Limit: 0.10 - 2.0 SOL\n• Reward: 0.5% Daily\n\n2️⃣ <b>ADVANCE</b>\n• Limit: 2.10 - 10.0 SOL\n• Reward: 1.0% Daily\n\n3️⃣ <b>PREMIUM</b>\n• Limit: 10.10 - 25.0 SOL\n• Reward: 1.5% Daily\n\n4️⃣ <b>GALAXY</b>\n• Limit: 25.10 - 100 SOL\n• Reward: 2.0% Daily\n\n⚠️ <i>Note: Base cap is 250%. Referring at least one active user upgrades max cap to 500%.</i>",
        "deposit_prompt": "💰 <b>Deposit SOL</b>\n\nPlease scan the QR code above or copy the address below to deposit SOL:\n\n<code>{wallet_address}</code>\n\n⚠ <i>Send only SOL to this address.</i>\n\n📝 <i>After sending, please send your Transaction Hash (TxID) here to activate your ID!</i>",
        "no_history": "📜 <b>Withdrawal History</b>\n\nYou have no past withdrawals.",
        "history_title": "📜 <b>Your Recent Withdrawals:</b>\n\n",
        "min_withdraw": "❌ <b>Minimum withdrawal limit is</b> <code>0.01 SOL</code>.",
        "max_daily_withdraw_err": "❌ <b>Daily withdrawal limit reached!</b> Maximum limit is <code>10.0 SOL</code> per day.",
        "withdraw_prompt": "💰 <b>Available Balance:</b> <code>{bal:.4f} SOL</code>\n\nEnter amount (Max 10 SOL/day):",
        "team_empty": "👥 You don't have any team members yet.",
        "ref_text": "<b>🔗 Your Referral Link</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>",
        "withdraw_processing": "⏳ <b>Withdrawal is Processing!</b>\n\nYour request for <code>{amount:.4f} SOL</code> has been submitted for review. Once approved, the SOL will be transferred to your wallet.",
        "withdraw_success_user": "✅ <b>Withdrawal Successful!</b>\n\nYour <code>{amount:.4f} SOL</code> request has been approved and sent to your wallet.\n🔗 <b>TxID:</b> <code>{txid}</code>",
        "dashboard_text": "👤 <b>User Dashboard</b>\n\n💰 <b>Available Balance:</b> <code>{balance:.4f} SOL</code>\n🌾 <b>Total Self Farming:</b> <code>{self_farming:.4f} SOL</code>\n🌾 <b>Self Farming Bonus:</b> <code>{self_bonus:.4f} SOL</code>\n👥 <b>Direct Referral Bonus:</b> <code>{direct_ref:.4f} SOL</code>\n🤝 <b>Team Referral Bonus:</b> <code>{team_ref:.4f} SOL</code>\n🤝 <b>Team Farming Override Bonus:</b> <code>{team_override:.4f} SOL</code>\n🏆 <b>Rank & Royalty Bonus:</b> <code>{royalty:.4f} SOL</code>\n📈 <b>Total Earned:</b> <code>{earned:.4f} SOL</code> (Max Cap: <code>{max_cap:.2f} SOL</code>)\n\n🧁 <b>Total Withdrawals:</b> <code>{withdrawn:.4f} SOL</code>\n🎯 <b>Available Withdrawal Limit:</b> <code>{available_limit:.4f} SOL</code>\n\n📦 <b>Active Plan:</b> {active_plan}\n🏆 <b>Current Rank:</b> {current_rank}",
        "ranks_text": "🏆 <b>Ranks & Royalty Status</b>\n\n<b>• Total Directs:</b> <code>{directs_count}</code> (Active: <code>{active_directs}</code>)\n<b>• Direct Business:</b> <code>{direct_biz:.2f} SOL</code>\n<b>• Total Team Business:</b> <code>{team_biz:.2f} SOL</code>\n<b>• Current Rank:</b> <code>{current_rank_name}</code>\n<b>• Next Rank:</b> <code>{next_rank_name}</code>\n\n<b>🎯 Progress for Next Rank:</b>\n<b>• Total Target ({target} SOL):</b> {total_icon} (Current: {total_volume:.2f})\n\n<b>• Leg Requirements Check:</b>\n<b> - Strongest Leg (Min {req_strongest} SOL):</b> {strongest_icon} (Current: <code>{highest_leg:.2f}</code>)\n<b> - Other Legs Combined (Min {req_other} SOL):</b> {other_icon} (Current: <code>{other_legs_total:.2f}</code>)\n"
    },
    "zh": {
        "select_lang": "🌐 请选择您的语言：",
        "lang_changed": "✅ 语言已更新为中文！",
        "welcome": "🚜 <b>欢迎来到 {PROJECT_NAME}</b>\n\n点击下方按钮开始您的挖矿之旅。",
        "btn_plans": "💎 挖矿套餐",
        "btn_deposit": "💰 存款 SOL",
        "btn_dashboard": "📊 面板",
        "btn_withdraw": "🎁 提现",
        "btn_ref": "🔗 推荐链接",
        "btn_team": "👥 团队成员",
        "btn_ranks": "🏆 等级与版税",
        "btn_history": "📜 提现记录",
        "btn_lang": "🌐 更改语言",
        "farming_packages": "<b>💎 挖矿套餐（个人上限 250%，团队上限 500%）：</b>\n\n1️⃣ <b>STARTER</b>\n• 限额：0.10 - 2.0 SOL\n• 每日收益：0.5%\n\n2️⃣ <b>ADVANCE</b>\n• 限额：2.10 - 10.0 SOL\n• 每日收益：1.0%\n\n3️⃣ <b>PREMIUM</b>\n• 限额：10.10 - 25.0 SOL\n• 每日收益：1.5%\n\n4️⃣ <b>GALAXY</b>\n• 限额：25.10 - 100 SOL\n• 每日收益：2.0%\n\n⚠️ <i>注意：基础收益上限为 250%。推荐至少一名活跃用户可升级至 500%。</i>",
        "deposit_prompt": "💰 <b>存款 SOL</b>\n\n请扫描上方二维码或复制下方地址充值 SOL：\n\n<code>{wallet_address}</code>\n\n⚠ <i>请仅向此地址发送 SOL。</i>\n\n📝 <i>发送完成后，请在此发送交易 Hash (TxID) 以激活您的账号！</i>",
        "no_history": "📜 <b>提现记录</b>\n\n您暂无历史提现记录。",
        "history_title": "📜 <b>您最近的提现记录：</b>\n\n",
        "min_withdraw": "❌ <b>最低提现额度为</b> <code>0.01 SOL</code>。",
        "max_daily_withdraw_err": "❌ <b>已达每日提现上限！</b> 每天最多提现 <code>10.0 SOL</code>。",
        "withdraw_prompt": "💰 <b>可用余额：</b> <code>{bal:.4f} SOL</code>\n\n请输入提现金额（每日上限 10 SOL）：",
        "team_empty": "👥 您目前还没有团队成员。",
        "ref_text": "<b>🔗 您的专属推荐链接</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>",
        "withdraw_processing": "⏳ <b>提现处理中！</b>\n\n您的 <code>{amount:.4f} SOL</code> 提现申请已提交审核。",
        "withdraw_success_user": "✅ <b>提现成功！</b>\n\n您的 <code>{amount:.4f} SOL</code> 已成功转入您的钱包。\n🔗 <b>TxID:</b> <code>{txid}</code>",
        "dashboard_text": "👤 <b>用户仪表板</b>\n\n💰 <b>可用余额：</b> <code>{balance:.4f} SOL</code>\n🌾 <b>个人总挖矿：</b> <code>{self_farming:.4f} SOL</code>\n🌾 <b>个人挖矿奖励：</b> <code>{self_bonus:.4f} SOL</code>\n👥 <b>直推奖励：</b> <code>{direct_ref:.4f} SOL</code>\n🤝 <b>团队推荐奖励：</b> <code>{team_ref:.4f} SOL</code>\n🤝 <b>团队管理奖励：</b> <code>{team_override:.4f} SOL</code>\n🏆 <b>等级分红奖励：</b> <code>{royalty:.4f} SOL</code>\n📈 <b>累计总收益：</b> <code>{earned:.4f} SOL</code>（最高上限：<code>{max_cap:.2f} SOL</code>）\n\n🧁 <b>累计已提现：</b> <code>{withdrawn:.4f} SOL</code>\n🎯 <b>剩余可提现额度：</b> <code>{available_limit:.4f} SOL</code>\n\n📦 <b>当前套餐：</b> {active_plan}\n🏆 <b>当前等级：</b> {current_rank}",
        "ranks_text": "🏆 <b>等级与版税状态</b>\n\n<b>• 直推总人数：</b> <code>{directs_count}</code>（活跃：<code>{active_directs}</code>）\n<b>• 直推业绩：</b> <code>{direct_biz:.2f} SOL</code>\n<b>• 团队总业绩：</b> <code>{team_biz:.2f} SOL</code>\n<b>• 当前等级：</b> <code>{current_rank_name}</code>\n<b>• 下一等级：</b> <code>{next_rank_name}</code>\n\n<b>🎯 升级进度：</b>\n<b>• 目标总业绩 ({target} SOL)：</b> {total_icon}（当前：{total_volume:.2f}）\n\n<b>• 区域业绩要求：</b>\n<b> - 最强大区（至少 {req_strongest} SOL）：</b> {strongest_icon}（当前：<code>{highest_leg:.2f}</code>）\n<b> - 其他小区组合（至少 {req_other} SOL）：</b> {other_icon}（当前：<code>{other_legs_total:.2f}</code>）\n"
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
        "farming_packages": "<b>💎 फार्मिंग पैकेज (मैक्स कैप: खुद के लिए 250%, टीम के साथ 500%):</b>\n\n1️⃣ <b>STARTER</b>\n• सीमा: 0.10 - 2.0 SOL\n• रिवॉर्ड: 0.5% डेली\n\n2️⃣ <b>ADVANCE</b>\n• सीमा: 2.10 - 10.0 SOL\n• रिवॉर्ड: 1.0% डेली\n\n3️⃣ <b>PREMIUM</b>\n• सीमा: 10.10 - 25.0 SOL\n• रिवॉर्ड: 1.5% डेली\n\n4️⃣ <b>GALAXY</b>\n• सीमा: 25.10 - 100 SOL\n• रिवॉर्ड: 2.0% डेली\n\n⚠️ <i>नोट: बेस कैप 250% है। कम से कम 1 एक्टिव यूजर रेफर करने पर कैप 500% हो जाता है।</i>",
        "deposit_prompt": "💰 <b>SOL जमा करें</b>\n\nSOL जमा करने के लिए ऊपर QR कोड स्कैन करें या नीचे दिए गए पते को कॉपी करें:\n\n<code>{wallet_address}</code>\n\n⚠ <i>केवल SOL ही इस पते पर भेजें।</i>\n\n📝 <i>भेजने के बाद, अपनी आईडी एक्टिव करने के लिए ट्रांजेक्शन हैश (TxID) यहाँ भेजें!</i>",
        "no_history": "📜 <b>निकासी इतिहास</b>\n\nआपका कोई पिछला निकासी रिकॉर्ड नहीं है।",
        "history_title": "📜 <b>आपकी हालिया निकासी:</b>\n\n",
        "min_withdraw": "❌ <b>न्यूनतम निकासी सीमा</b> <code>0.01 SOL</code> है।",
        "max_daily_withdraw_err": "❌ <b>डेली निकासी सीमा समाप्त!</b> आप एक दिन में अधिकतम <code>10.0 SOL</code> ही निकाल सकते हैं।",
        "withdraw_prompt": "💰 <b>उपलब्ध शेष राशि:</b> <code>{bal:.4f} SOL</code>\n\nराशि दर्ज करें (Max 10 SOL/day):",
        "team_empty": "👥 आपका अभी तक कोई टीम मेंबर नहीं है।",
        "ref_text": "<b>🔗 आपका रेफरल लिंक</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>",
        "withdraw_processing": "⏳ <b>निकासी प्रक्रिया में है!</b>\n\nआपकी <code>{amount:.4f} SOL</code> की निकासी का अनुरोध समीक्षा के लिए भेज दिया गया है।",
        "withdraw_success_user": "✅ <b>निकासी सफल रही!</b>\n\nआपका <code>{amount:.4f} SOL</code> का अनुरोध स्वीकृत कर आपके वॉलेट में भेज दिया गया है।\n🔗 <b>TxID:</b> <code>{txid}</code>",
        "dashboard_text": "👤 <b>यूज़र डैशबोर्ड</b>\n\n💰 <b>उपलब्ध शेष राशि:</b> <code>{balance:.4f} SOL</code>\n🌾 <b>कुल सेल्फ फार्मिंग:</b> <code>{self_farming:.4f} SOL</code>\n🌾 <b>सेल्फ फार्मिंग बोनस:</b> <code>{self_bonus:.4f} SOL</code>\n👥 <b>डायरेक्ट रेफरल बोनस:</b> <code>{direct_ref:.4f} SOL</code>\n🤝 <b>टीम रेफरल बोनस:</b> <code>{team_ref:.4f} SOL</code>\n🤝 <b>टीम फार्मिंग ओवरराइड बोनस:</b> <code>{team_override:.4f} SOL</code>\n🏆 <b>रैंक और रॉयल्टी बोनस:</b> <code>{royalty:.4f} SOL</code>\n📈 <b>कुल कमाई:</b> <code>{earned:.4f} SOL</code> (मैक्स कैप: <code>{max_cap:.2f} SOL</code>)\n\n🧁 <b>कुल निकासी:</b> <code>{withdrawn:.4f} SOL</code>\n🎯 <b>उपलब्ध निकासी सीमा:</b> <code>{available_limit:.4f} SOL</code>\n\n📦 <b>एक्टिव प्लान:</b> {active_plan}\n🏆 <b>वर्तमान रैंक:</b> {current_rank}",
        "ranks_text": "🏆 <b>रैंक और रॉयल्टी स्थिति</b>\n\n<b>• कुल डायरेक्ट्स:</b> <code>{directs_count}</code> (एक्टिव: <code>{active_directs}</code>)\n<b>• डायरेक्ट बिज़नेस:</b> <code>{direct_biz:.2f} SOL</code>\n<b>• कुल टीम बिज़नेस:</b> <code>{team_biz:.2f} SOL</code>\n<b>• वर्तमान रैंक:</b> <code>{current_rank_name}</code>\n<b>• अगली रैंक:</b> <code>{next_rank_name}</code>\n\n<b>🎯 अगली रैंक के लिए प्रगति:</b>\n<b>• कुल टारगेट ({target} SOL):</b> {total_icon} (वर्तमान: {total_volume:.2f})\n\n<b>• लेग शर्तें:</b>\n<b> - सबसे मजबूत लेग (कम से कम {req_strongest} SOL):</b> {strongest_icon} (वर्तमान: <code>{highest_leg:.2f}</code>)\n<b> - अन्य लेग मिलाकर (कम से कम {req_other} SOL):</b> {other_icon} (वर्तमान: <code>{other_legs_total:.2f}</code>)\n"
    },
    "ru": {
        "select_lang": "🌐 Пожалуйста, выберите язык:",
        "lang_changed": "✅ Язык успешно изменен на русский!",
        "welcome": "🚜 <b>Добро пожаловать в {PROJECT_NAME}</b>\n\nИспользуйте кнопки ниже, чтобы начать фарминг.",
        "btn_plans": "💎 Пакеты фарминга",
        "btn_deposit": "💰 Депозит SOL",
        "btn_dashboard": "📊 Панель",
        "btn_withdraw": "🎁 Вывод",
        "btn_ref": "🔗 Реферальная ссылка",
        "btn_team": "👥 Команда",
        "btn_ranks": "🏆 Ранги и роялти",
        "btn_history": "📜 История выводов",
        "btn_lang": "🌐 Изменить язык",
        "farming_packages": "<b>💎 Пакеты фарминга (Макс. лимит: 250% соло, 500% с командой):</b>\n\n1️⃣ <b>STARTER</b>\n• Лимит: 0.10 - 2.0 SOL\n• Доход: 0.5% в день\n\n2️⃣ <b>ADVANCE</b>\n• Лимит: 2.10 - 10.0 SOL\n• Доход: 1.0% в день\n\n3️⃣ <b>PREMIUM</b>\n• Лимит: 10.10 - 25.0 SOL\n• Доход: 1.5% в день\n\n4️⃣ <b>GALAXY</b>\n• Лимит: 25.10 - 100 SOL\n• Доход: 2.0% в день",
        "deposit_prompt": "💰 <b>Депозит SOL</b>\n\nОтсканируйте QR-код выше или скопируйте адрес ниже для депозита SOL:\n\n<code>{wallet_address}</code>\n\n📝 <i>Отправьте хэш транзакции (TxID) сюда после отправки!</i>",
        "no_history": "📜 <b>История выводов</b>\n\nУ вас нет прошлых выводов.",
        "history_title": "📜 <b>Ваши недавние выводы:</b>\n\n",
        "min_withdraw": "❌ <b>Минимальный лимит вывода:</b> <code>0.01 SOL</code>.",
        "max_daily_withdraw_err": "❌ <b>Дневной лимит превышен!</b> Максимум <code>10.0 SOL</code> в день.",
        "withdraw_prompt": "💰 <b>Доступный баланс:</b> <code>{bal:.4f} SOL</code>\n\nВведите сумму (Макс 10 SOL/день):",
        "team_empty": "👥 У вас пока нет участников команды.",
        "ref_text": "<b>🔗 Ваша реферальная ссылка</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>",
        "withdraw_processing": "⏳ <b>Вывод средств в обработке!</b>\n\nЗапрос на <code>{amount:.4f} SOL</code> отправлен на проверку.",
        "withdraw_success_user": "✅ <b>Вывод успешно завершен!</b>\n\n<code>{amount:.4f} SOL</code> отправлено на ваш кошелек.\n🔗 <b>TxID:</b> <code>{txid}</code>",
        "dashboard_text": "👤 <b>Панель пользователя</b>\n\n💰 <b>Доступный баланс:</b> <code>{balance:.4f} SOL</code>\n🌾 <b>Личный фарминг:</b> <code>{self_farming:.4f} SOL</code>\n🌾 <b>Бонус фарминга:</b> <code>{self_bonus:.4f} SOL</code>\n👥 <b>Прямой бонус:</b> <code>{direct_ref:.4f} SOL</code>\n🤝 <b>Командный бонус:</b> <code>{team_ref:.4f} SOL</code>\n🤝 <b>Бонус управления:</b> <code>{team_override:.4f} SOL</code>\n🏆 <b>Бонус ранга и роялти:</b> <code>{royalty:.4f} SOL</code>\n📈 <b>Всего заработано:</b> <code>{earned:.4f} SOL</code> (Лимит: <code>{max_cap:.2f} SOL</code>)\n\n🧁 <b>Всего выведено:</b> <code>{withdrawn:.4f} SOL</code>\n🎯 <b>Доступный лимит вывода:</b> <code>{available_limit:.4f} SOL</code>\n\n📦 <b>Активный план:</b> {active_plan}\n🏆 <b>Текущий ранг:</b> {current_rank}",
        "ranks_text": "🏆 <b>Ранги и Роялти</b>\n\n<b>• Прямые рефералы:</b> <code>{directs_count}</code> (Активно: <code>{active_directs}</code>)\n<b>• Прямой оборот:</b> <code>{direct_biz:.2f} SOL</code>\n<b>• Оборот команды:</b> <code>{team_biz:.2f} SOL</code>\n<b>• Текущий ранг:</b> <code>{current_rank_name}</code>\n<b>• Следующий ранг:</b> <code>{next_rank_name}</code>\n\n<b>🎯 Прогресс до следующего ранга:</b>\n<b>• Общая цель ({target} SOL):</b> {total_icon} (Текущий: {total_volume:.2f})\n\n<b>• Проверка веток:</b>\n<b> - Сильная ветка (Мин {req_strongest} SOL):</b> {strongest_icon} (Текущий: <code>{highest_leg:.2f}</code>)\n<b> - Другие ветки (Мин {req_other} SOL):</b> {other_icon} (Текущий: <code>{other_legs_total:.2f}</code>)\n"
    },
    "vi": {
        "select_lang": "🌐 Vui lòng chọn ngôn ngữ của bạn:",
        "lang_changed": "✅ Đã cập nhật ngôn ngữ thành Tiếng Việt!",
        "welcome": "🚜 <b>Chào mừng đến với {PROJECT_NAME}</b>\n\nSử dụng các nút bên dưới để bắt đầu khai thác.",
        "btn_plans": "💎 Gói Khai Thác",
        "btn_deposit": "💰 Nạp SOL",
        "btn_dashboard": "📊 Bảng điều khiển",
        "btn_withdraw": "🎁 Rút tiền",
        "btn_ref": "🔗 Liên kết giới thiệu",
        "btn_team": "👥 Thành viên nhóm",
        "btn_ranks": "🏆 Cấp bậc & Bản quyền",
        "btn_history": "📜 Lịch sử rút tiền",
        "btn_lang": "🌐 Đổi ngôn ngữ",
        "farming_packages": "<b>💎 Gói Khai Thác (Tối đa: 250% Cá nhân, 500% Đội nhóm):</b>\n\n1️⃣ <b>STARTER</b>\n• Hạn mức: 0.10 - 2.0 SOL\n• Lợi nhuận: 0.5%/ngày\n\n2️⃣ <b>ADVANCE</b>\n• Hạn mức: 2.10 - 10.0 SOL\n• Lợi nhuận: 1.0%/ngày\n\n3️⃣ <b>PREMIUM</b>\n• Hạn mức: 10.10 - 25.0 SOL\n• Lợi nhuận: 1.5%/ngày\n\n4️⃣ <b>GALAXY</b>\n• Hạn mức: 25.10 - 100 SOL\n• Lợi nhuận: 2.0%/ngày",
        "deposit_prompt": "💰 <b>Nạp SOL</b>\n\nQuét mã QR hoặc sao chép địa chỉ bên dưới để nạp SOL:\n\n<code>{wallet_address}</code>\n\n📝 <i>Sau khi gửi, hãy gửi Mã giao dịch (TxID) vào đây!</i>",
        "no_history": "📜 <b>Lịch sử rút tiền</b>\n\nBạn chưa có lịch sử rút tiền.",
        "history_title": "📜 <b>Lịch sử rút tiền gần đây:</b>\n\n",
        "min_withdraw": "❌ <b>Hạn mức rút tối thiểu:</b> <code>0.01 SOL</code>.",
        "max_daily_withdraw_err": "❌ <b>Đã đạt hạn mức ngày!</b> Tối đa <code>10.0 SOL</code>/ngày.",
        "withdraw_prompt": "💰 <b>Số dư khả dụng:</b> <code>{bal:.4f} SOL</code>\n\nNhập số tiền (Tối đa 10 SOL/ngày):",
        "team_empty": "👥 Bạn chưa có thành viên nhóm nào.",
        "ref_text": "<b>🔗 Liên kết giới thiệu của bạn</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>",
        "withdraw_processing": "⏳ <b>Đang xử lý rút tiền!</b>\n\nYêu cầu <code>{amount:.4f} SOL</code> đã được gửi đi.",
        "withdraw_success_user": "✅ <b>Rút tiền thành công!</b>\n\n<code>{amount:.4f} SOL</code> đã gửi về ví của bạn.\n🔗 <b>TxID:</b> <code>{txid}</code>",
        "dashboard_text": "👤 <b>Bảng Điều Khiển User</b>\n\n💰 <b>Số dư khả dụng:</b> <code>{balance:.4f} SOL</code>\n🌾 <b>Tổng khai thác cá nhân:</b> <code>{self_farming:.4f} SOL</code>\n🌾 <b>Thưởng khai thác:</b> <code>{self_bonus:.4f} SOL</code>\n👥 <b>Thưởng giới thiệu trực tiếp:</b> <code>{direct_ref:.4f} SOL</code>\n🤝 <b>Thưởng đội nhóm:</b> <code>{team_ref:.4f} SOL</code>\n🤝 <b>Thưởng quản lý:</b> <code>{team_override:.4f} SOL</code>\n🏆 <b>Thưởng cấp bậc & bản quyền:</b> <code>{royalty:.4f} SOL</code>\n📈 <b>Tổng thu nhập:</b> <code>{earned:.4f} SOL</code> (Hạn mức: <code>{max_cap:.2f} SOL</code>)\n\n🧁 <b>Tổng đã rút:</b> <code>{withdrawn:.4f} SOL</code>\n🎯 <b>Hạn mức còn lại:</b> <code>{available_limit:.4f} SOL</code>\n\n📦 <b>Gói hiện tại:</b> {active_plan}\n🏆 <b>Cấp bậc hiện tại:</b> {current_rank}",
        "ranks_text": "🏆 <b>Cấp Bậc & Thưởng Bản Quyền</b>\n\n<b>• Trực tiếp:</b> <code>{directs_count}</code> (Hoạt động: <code>{active_directs}</code>)\n<b>• Doanh số trực tiếp:</b> <code>{direct_biz:.2f} SOL</code>\n<b>• Doanh số nhóm:</b> <code>{team_biz:.2f} SOL</code>\n<b>• Cấp bậc hiện tại:</b> <code>{current_rank_name}</code>\n<b>• Cấp bậc tiếp theo:</b> <code>{next_rank_name}</code>\n\n<b>🎯 Tiến độ lên cấp:</b>\n<b>• Mục tiêu ({target} SOL):</b> {total_icon} (Hiện tại: {total_volume:.2f})\n\n<b>• Kiểm tra nhánh:</b>\n<b> - Nhánh mạnh nhất (Tối thiểu {req_strongest} SOL):</b> {strongest_icon} (Hiện tại: <code>{highest_leg:.2f}</code>)\n<b> - Các nhánh khác (Tối thiểu {req_other} SOL):</b> {other_icon} (Hiện tại: <code>{other_legs_total:.2f}</code>)\n"
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
        "farming_packages": "<b>💎 Paket Farming (Batas Maks: 250% Sendiri, 500% dengan Tim):</b>\n\n1️⃣ <b>STARTER</b>\n• Batas: 0.10 - 2.0 SOL\n• Profit: 0.5% Harian\n\n2️⃣ <b>ADVANCE</b>\n• Batas: 2.10 - 10.0 SOL\n• Profit: 1.0% Harian\n\n3️⃣ <b>PREMIUM</b>\n• Batas: 10.10 - 25.0 SOL\n• Profit: 1.5% Harian\n\n4️⃣ <b>GALAXY</b>\n• Batas: 25.10 - 100 SOL\n• Profit: 2.0% Harian",
        "deposit_prompt": "💰 <b>Deposit SOL</b>\n\nPindai kode QR atau salin alamat di bawah untuk deposit SOL:\n\n<code>{wallet_address}</code>\n\n📝 <i>Kirim Hash Transaksi (TxID) ke sini setelah melakukan transfer!</i>",
        "no_history": "📜 <b>Riwayat Penarikan</b>\n\nAnda tidak memiliki riwayat penarikan.",
        "history_title": "📜 <b>Penarikan Terbaru Anda:</b>\n\n",
        "min_withdraw": "❌ <b>Batas penarikan minimum:</b> <code>0.01 SOL</code>.",
        "max_daily_withdraw_err": "❌ <b>Batas harian tercapai!</b> Maksimal <code>10.0 SOL</code> per hari.",
        "withdraw_prompt": "💰 <b>Saldo Tersedia:</b> <code>{bal:.4f} SOL</code>\n\nMasukkan jumlah (Maks 10 SOL/hari):",
        "team_empty": "👥 Anda belum memiliki anggota tim.",
        "ref_text": "<b>🔗 Tautan Referensi Anda</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>",
        "withdraw_processing": "⏳ <b>Penarikan Sedang Diproses!</b>\n\nPermintaan <code>{amount:.4f} SOL</code> telah dikirim.",
        "withdraw_success_user": "✅ <b>Penarikan Berhasil!</b>\n\n<code>{amount:.4f} SOL</code> telah dikirim ke dompet Anda.\n🔗 <b>TxID:</b> <code>{txid}</code>",
        "dashboard_text": "👤 <b>Dasbor Pengguna</b>\n\n💰 <b>Saldo Tersedia:</b> <code>{balance:.4f} SOL</code>\n🌾 <b>Total Farming Sendiri:</b> <code>{self_farming:.4f} SOL</code>\n🌾 <b>Bonus Farming:</b> <code>{self_bonus:.4f} SOL</code>\n👥 <b>Bonus Referal Langsung:</b> <code>{direct_ref:.4f} SOL</code>\n🤝 <b>Bonus Tim:</b> <code>{team_ref:.4f} SOL</code>\n🤝 <b>Bonus Manajemen Tim:</b> <code>{team_override:.4f} SOL</code>\n🏆 <b>Bonus Peringkat & Royalti:</b> <code>{royalty:.4f} SOL</code>\n📈 <b>Total Pendapatan:</b> <code>{earned:.4f} SOL</code> (Batas: <code>{max_cap:.2f} SOL</code>)\n\n🧁 <b>Total Penarikan:</b> <code>{withdrawn:.4f} SOL</code>\n🎯 <b>Sisa Batas Penarikan:</b> <code>{available_limit:.4f} SOL</code>\n\n📦 <b>Paket Aktif:</b> {active_plan}\n🏆 <b>Peringkat Saat Ini:</b> {current_rank}",
        "ranks_text": "🏆 <b>Status Peringkat & Royalti</b>\n\n<b>• Total Referal Langsung:</b> <code>{directs_count}</code> (Aktif: <code>{active_directs}</code>)\n<b>• Omset Langsung:</b> <code>{direct_biz:.2f} SOL</code>\n<b>• Total Omset Tim:</b> <code>{team_biz:.2f} SOL</code>\n<b>• Peringkat Saat Ini:</b> <code>{current_rank_name}</code>\n<b>• Peringkat Berikutnya:</b> <code>{next_rank_name}</code>\n\n<b>🎯 Kemajuan Peringkat:</b>\n<b>• Target Total ({target} SOL):</b> {total_icon} (Saat Ini: {total_volume:.2f})\n\n<b>• Syarat Kaki Omset:</b>\n<b> - Kaki Terkuat (Min {req_strongest} SOL):</b> {strongest_icon} (Saat Ini: <code>{highest_leg:.2f}</code>)\n<b> - Kaki Lainnya (Min {req_other} SOL):</b> {other_icon} (Saat Ini: <code>{other_legs_total:.2f}</code>)\n"
    },
    "th": {
        "select_lang": "🌐 กรุณาเลือกภาษาของคุณ:",
        "lang_changed": "✅ เปลี่ยนภาษาเป็นภาษาไทยเรียบร้อยแล้ว!",
        "welcome": "🚜 <b>ยินดีต้อนรับสู่ {PROJECT_NAME}</b>\n\nกดปุ่มด้านล่างเพื่อเริ่มทำฟาร์ม",
        "btn_plans": "💎 แพ็คเกจฟาร์ม",
        "btn_deposit": "💰 ฝาก SOL",
        "btn_dashboard": "📊 แดชบอร์ด",
        "btn_withdraw": "🎁 ถอนเงิน",
        "btn_ref": "🔗 ลิงก์แนะนำ",
        "btn_team": "👥 สมาชิกในทีม",
        "btn_ranks": "🏆 ตำแหน่ง & ค่าลิขสิทธิ์",
        "btn_history": "📜 ประวัติการถอน",
        "btn_lang": "🌐 เปลี่ยนภาษา",
        "farming_packages": "<b>💎 แพ็คเกจฟาร์ม (รับสูงสุด: 250% ทำเอง, 500% มีทีม):</b>\n\n1️⃣ <b>STARTER</b>\n• ขีดจำกัด: 0.10 - 2.0 SOL\n• ผลตอบแทน: 0.5% ต่อวัน\n\n2️⃣ <b>ADVANCE</b>\n• ขีดจำกัด: 2.10 - 10.0 SOL\n• ผลตอบแทน: 1.0% ต่อวัน\n\n3️⃣ <b>PREMIUM</b>\n• ขีดจำกัด: 10.10 - 25.0 SOL\n• ผลตอบแทน: 1.5% ต่อวัน\n\n4️⃣ <b>GALAXY</b>\n• ขีดจำกัด: 25.10 - 100 SOL\n• ผลตอบแทน: 2.0% ต่อวัน",
        "deposit_prompt": "💰 <b>ฝาก SOL</b>\n\nสแกน QR code หรือคัดลอกที่อยู่นี้เพื่อฝาก SOL:\n\n<code>{wallet_address}</code>\n\n📝 <i>กรุณาส่ง TxID มาที่นี่หลังจากฝากเงินเสร็จสิ้น!</i>",
        "no_history": "📜 <b>ประวัติการถอน</b>\n\nคุณไม่มีประวัติการถอนเงิน",
        "history_title": "📜 <b>ประวัติการถอนเงินล่าสุด:</b>\n\n",
        "min_withdraw": "❌ <b>ถอนขั้นต่ำ:</b> <code>0.01 SOL</code>",
        "max_daily_withdraw_err": "❌ <b>เกินขีดจำกัดรายวัน!</b> สูงสุด <code>10.0 SOL</code> ต่อวัน",
        "withdraw_prompt": "💰 <b>ยอดเงินคงเหลือ:</b> <code>{bal:.4f} SOL</code>\n\nป้อนจำนวนเงิน (สูงสุด 10 SOL/วัน):",
        "team_empty": "👥 คุณยังไม่มีสมาชิกในทีม",
        "ref_text": "<b>🔗 ลิงก์แนะนำของคุณ</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>",
        "withdraw_processing": "⏳ <b>กำลังดำเนินการถอนเงิน!</b>\n\nคำขอถอน <code>{amount:.4f} SOL</code> อยู่ระหว่างตรวจสอบ",
        "withdraw_success_user": "✅ <b>ถอนเงินสำเร็จ!</b>\n\nส่ง <code>{amount:.4f} SOL</code> ไปยังกระเป๋าของคุณแล้ว\n🔗 <b>TxID:</b> <code>{txid}</code>",
        "dashboard_text": "👤 <b>แดชบอร์ดผู้ใช้</b>\n\n💰 <b>ยอดเงินคงเหลือ:</b> <code>{balance:.4f} SOL</code>\n🌾 <b>ฟาร์มเองทั้งหมด:</b> <code>{self_farming:.4f} SOL</code>\n🌾 <b>โบนัสทำฟาร์ม:</b> <code>{self_bonus:.4f} SOL</code>\n👥 <b>โบนัสแนะนำตรง:</b> <code>{direct_ref:.4f} SOL</code>\n🤝 <b>โบนัสทีม:</b> <code>{team_ref:.4f} SOL</code>\n🤝 <b>โบนัสบริหารทีม:</b> <code>{team_override:.4f} SOL</code>\n🏆 <b>โบนัสตำแหน่ง:</b> <code>{royalty:.4f} SOL</code>\n📈 <b>รายได้รวม:</b> <code>{earned:.4f} SOL</code> (สูงสุด: <code>{max_cap:.2f} SOL</code>)\n\n🧁 <b>ยอดถอนรวม:</b> <code>{withdrawn:.4f} SOL</code>\n🎯 <b>ลิมิตถอนคงเหลือ:</b> <code>{available_limit:.4f} SOL</code>\n\n📦 <b>แพ็คเกจปัจจุบัน:</b> {active_plan}\n🏆 <b>ตำแหน่งปัจจุบัน:</b> {current_rank}",
        "ranks_text": "🏆 <b>สถานะตำแหน่ง & ค่าลิขสิทธิ์</b>\n\n<b>• แนะนำตรงทั้งหมด:</b> <code>{directs_count}</code> (แอคทีฟ: <code>{active_directs}</code>)\n<b>• ยอดขายแนะนำตรง:</b> <code>{direct_biz:.2f} SOL</code>\n<b>• ยอดขายทีมรวม:</b> <code>{team_biz:.2f} SOL</code>\n<b>• ตำแหน่งปัจจุบัน:</b> <code>{current_rank_name}</code>\n<b>• ตำแหน่งถัดไป:</b> <code>{next_rank_name}</code>\n\n<b>🎯 ความคืบหน้าตำแหน่งถัดไป:</b>\n<b>• เป้าหมายรวม ({target} SOL):</b> {total_icon} (ปัจจุบัน: {total_volume:.2f})\n\n<b>• ตรวจสอบสายงาน:</b>\n<b> - สายงานใหญ่สุด (อย่างน้อย {req_strongest} SOL):</b> {strongest_icon} (ปัจจุบัน: <code>{highest_leg:.2f}</code>)\n<b> - สายงานอื่นรวม (อย่างน้อย {req_other} SOL):</b> {other_icon} (ปัจจุบัน: <code>{other_legs_total:.2f}</code>)\n"
    },
    "ar": {
        "select_lang": "🌐 الرجاء اختيار لغتك:",
        "lang_changed": "✅ تم تحديث اللغة إلى العربية!",
        "welcome": "🚜 <b>مرحباً بك في {PROJECT_NAME}</b>\n\nاستخدم الأزرار أدناه لبدء رحلة التعدين.",
        "btn_plans": "💎 باقات الزراعة",
        "btn_deposit": "💰 إيداع SOL",
        "btn_dashboard": "📊 لوحة التحكم",
        "btn_withdraw": "🎁 سحب",
        "btn_ref": "🔗 رابط الإحالة",
        "btn_team": "👥 أعضاء الفريق",
        "btn_ranks": "🏆 الرتب والعائدات",
        "btn_history": "📜 سجل السحب",
        "btn_lang": "🌐 تغير اللغة",
        "farming_packages": "<b>💎 باقات الزراعة (الحد الأقصى: 250% شخصي، 500% مع الفريق):</b>\n\n1️⃣ <b>STARTER</b>\n• الحد: 0.10 - 2.0 SOL\n• العائد: 0.5% يومياً\n\n2️⃣ <b>ADVANCE</b>\n• الحد: 2.10 - 10.0 SOL\n• العائد: 1.0% يومياً\n\n3️⃣ <b>PREMIUM</b>\n• الحد: 10.10 - 25.0 SOL\n• العائد: 1.5% يومياً\n\n4️⃣ <b>GALAXY</b>\n• الحد: 25.10 - 100 SOL\n• العائد: 2.0% يومياً",
        "deposit_prompt": "💰 <b>إيداع SOL</b>\n\nامسح رمز QR أو انسخ العنوان للإيداع:\n\n<code>{wallet_address}</code>\n\n📝 <i>أرسل معرف المعاملة (TxID) هنا بعد الإرسال!</i>",
        "no_history": "📜 <b>سجل السحب</b>\n\nليس لديك عمليات سحب سابقة.",
        "history_title": "📜 <b>عمليات السحب الأخيرة:</b>\n\n",
        "min_withdraw": "❌ <b>الحد الأدنى للسحب:</b> <code>0.01 SOL</code>.",
        "max_daily_withdraw_err": "❌ <b>تم الوصول للحد اليومي!</b> الحد الأقصى <code>10.0 SOL</code> يومياً.",
        "withdraw_prompt": "💰 <b>الرصيد المتاح:</b> <code>{bal:.4f} SOL</code>\n\nأدخل المبلغ (الحد الأقصى 10 SOL/يوم):",
        "team_empty": "👥 ليس لديك أي أعضاء في الفريق حتى الآن.",
        "ref_text": "<b>🔗 رابط الإحالة الخاص بك</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>",
        "withdraw_processing": "⏳ <b>طلب السحب قيد المعالجة!</b>\n\nتم تقديم طلب السحب بمبلغ <code>{amount:.4f} SOL</code>.",
        "withdraw_success_user": "✅ <b>تم السحب بنجاح!</b>\n\nتم إرسال <code>{amount:.4f} SOL</code> إلى محفظتك.\n🔗 <b>TxID:</b> <code>{txid}</code>",
        "dashboard_text": "👤 <b>لوحة تحكم المستخدم</b>\n\n💰 <b>الرصيد المتاح:</b> <code>{balance:.4f} SOL</code>\n🌾 <b>إجمالي التعدين الشخصي:</b> <code>{self_farming:.4f} SOL</code>\n🌾 <b>مكافأة التعدين:</b> <code>{self_bonus:.4f} SOL</code>\n👥 <b>مكافأة الإحالة المباشرة:</b> <code>{direct_ref:.4f} SOL</code>\n🤝 <b>مكافأة الفريق:</b> <code>{team_ref:.4f} SOL</code>\n🤝 <b>مكافأة إدارة الفريق:</b> <code>{team_override:.4f} SOL</code>\n🏆 <b>مكافأة الرتبة والعائدات:</b> <code>{royalty:.4f} SOL</code>\n📈 <b>إجمالي الأرباح:</b> <code>{earned:.4f} SOL</code> (الحد الأقصى: <code>{max_cap:.2f} SOL</code>)\n\n🧁 <b>إجمالي السحوبات:</b> <code>{withdrawn:.4f} SOL</code>\n🎯 <b>حد السحب المتاح:</b> <code>{available_limit:.4f} SOL</code>\n\n📦 <b>الباقة الحالية:</b> {active_plan}\n🏆 <b>الرتبة الحالية:</b> {current_rank}",
        "ranks_text": "🏆 <b>حالة الرتبة والعائدات</b>\n\n<b>• إجمالي المباشرين:</b> <code>{directs_count}</code> (نشط: <code>{active_directs}</code>)\n<b>• مبيعات المباشرين:</b> <code>{direct_biz:.2f} SOL</code>\n<b>• إجمالي مبيعات الفريق:</b> <code>{team_biz:.2f} SOL</code>\n<b>• الرتبة الحالية:</b> <code>{current_rank_name}</code>\n<b>• الرتبة القادمة:</b> <code>{next_rank_name}</code>\n\n<b>🎯 التقدم للرتبة القادمة:</b>\n<b>• الهدف الإجمالي ({target} SOL):</b> {total_icon} (الحالي: {total_volume:.2f})\n\n<b>• متطلبات الفروع:</b>\n<b> - أفرع قوي (على الأقل {req_strongest} SOL):</b> {strongest_icon} (الحالي: <code>{highest_leg:.2f}</code>)\n<b> - باقي الأفرع (على الأقل {req_other} SOL):</b> {other_icon} (الحالي: <code>{other_legs_total:.2f}</code>)\n"
    },
    "bn": {
        "select_lang": "🌐 অনুগ্রহ করে আপনার ভাষা নির্বাচন করুন:",
        "lang_changed": "✅ ভাষা সফলভাবে বাংলায় আপডেট করা হয়েছে!",
        "welcome": "🚜 <b>{PROJECT_NAME}-এ আপনাকে স্বাগতম</b>\n\nফার্মিং শুরু করতে নিচের বাটনগুলো ব্যবহার করুন।",
        "btn_plans": "💎 ফার্মিং প্ল্যান",
        "btn_deposit": "💰 SOL জমা দিন",
        "btn_dashboard": "📊 ড্যাশবোর্ড",
        "btn_withdraw": "🎁 উত্তোলন",
        "btn_ref": "🔗 রেফারেল লিংক",
        "btn_team": "👥 টিম মেম্বার",
        "btn_ranks": "🏆 র্যাঙ্ক এবং রয়্যালটি",
        "btn_history": "📜 উত্তোলনের ইতিহাস",
        "btn_lang": "🌐 ভাষা পরিবর্তন",
        "farming_packages": "<b>💎 ফার্মিং প্যাকেজ (সর্বোচ্চ ক্যাপ: নিজস্ব ২৫০%, টিমসহ ৫০০%):</b>\n\n1️⃣ <b>STARTER</b>\n• সীমা: 0.10 - 2.0 SOL\n• দৈনিক ইনকাম: 0.5%\n\n2️⃣ <b>ADVANCE</b>\n• সীমা: 2.10 - 10.0 SOL\n• দৈনিক ইনকাম: 1.0%\n\n3️⃣ <b>PREMIUM</b>\n• সীমা: 10.10 - 25.0 SOL\n• দৈনিক ইনকাম: 1.5%\n\n4️⃣ <b>GALAXY</b>\n• সীমা: 25.10 - 100 SOL\n• দৈনিক ইনকাম: 2.0%",
        "deposit_prompt": "💰 <b>SOL জমা দিন</b>\n\nQR কোড স্ক্যান করুন অথবা নিচের ঠিকানাটি কপি করে SOL ডিপোজিট করুন:\n\n<code>{wallet_address}</code>\n\n📝 <i>ডিপোজিট করার পর ট্রানজেকশন হ্যাশ (TxID) এখানে পাঠান!</i>",
        "no_history": "📜 <b>উত্তোলনের ইতিহাস</b>\n\nআপনার কোনো পূর্ববর্তী উত্তোলন নেই।",
        "history_title": "📜 <b>আপনার সাম্প্রতিক উত্তোলন:</b>\n\n",
        "min_withdraw": "❌ <b>সর্বনিম্ন উত্তোলনের সীমা:</b> <code>0.01 SOL</code>।",
        "max_daily_withdraw_err": "❌ <b>দৈনিক সীমা পূর্ণ!</b> সর্বোচ্চ <code>10.0 SOL</code>/দিন।",
        "withdraw_prompt": "💰 <b>উপলব্ধ ব্যালেন্স:</b> <code>{bal:.4f} SOL</code>\n\nপরিমাণ লিখুন (সর্বোচ্চ 10 SOL/দিন):",
        "team_empty": "👥 আপনার এখনও কোনো টিম মেম্বার নেই।",
        "ref_text": "<b>🔗 আপনার রেফারেল লিংক</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>",
        "withdraw_processing": "⏳ <b>উত্তোলন প্রক্রিয়াধীন রয়েছে!</b>\n\nআপনার <code>{amount:.4f} SOL</code> উত্তোলনের অনুরোধ জমা হয়েছে।",
        "withdraw_success_user": "✅ <b>উত্তোলন সফল হয়েছে!</b>\n\n<code>{amount:.4f} SOL</code> আপনার ওয়ালেটে পাঠানো হয়েছে।\n🔗 <b>TxID:</b> <code>{txid}</code>",
        "dashboard_text": "👤 <b>ইউজার ড্যাশবোর্ড</b>\n\n💰 <b>উপলব্ধ ব্যালেন্স:</b> <code>{balance:.4f} SOL</code>\n🌾 <b>মোট নিজস্ব ফার্মিং:</b> <code>{self_farming:.4f} SOL</code>\n🌾 <b>ফার্মিং বোনাস:</b> <code>{self_bonus:.4f} SOL</code>\n👥 <b>ডাইরেক্ট রেফারেল বোনাস:</b> <code>{direct_ref:.4f} SOL</code>\n🤝 <b>টিম রেফারেল বোনাস:</b> <code>{team_ref:.4f} SOL</code>\n🤝 <b>টিম ওভাররাইড বোনাস:</b> <code>{team_override:.4f} SOL</code>\n🏆 <b>র্যাঙ্ক ও রয়্যালটি বোনাস:</b> <code>{royalty:.4f} SOL</code>\n📈 <b>মোট আয়:</b> <code>{earned:.4f} SOL</code> (ক্যাপ: <code>{max_cap:.2f} SOL</code>)\n\n🧁 <b>মোট উত্তোলন:</b> <code>{withdrawn:.4f} SOL</code>\n🎯 <b>অবশিষ্ট উত্তোলন সীমা:</b> <code>{available_limit:.4f} SOL</code>\n\n📦 <b>বর্তমান প্ল্যান:</b> {active_plan}\n🏆 <b>বর্তমান র্যাঙ্ক:</b> {current_rank}",
        "ranks_text": "🏆 <b>র্যাঙ্ক ও রয়্যালটি স্ট্যাটাস</b>\n\n<b>• মোট ডাইরেক্ট:</b> <code>{directs_count}</code> (সক্রিয়: <code>{active_directs}</code>)\n<b>• ডাইরেক্ট সেলস:</b> <code>{direct_biz:.2f} SOL</code>\n<b>• মোট টিম সেলস:</b> <code>{team_biz:.2f} SOL</code>\n<b>• বর্তমান র্যাঙ্ক:</b> <code>{current_rank_name}</code>\n<b>• পরবর্তী র্যাঙ্ক:</b> <code>{next_rank_name}</code>\n\n<b>🎯 পরবর্তী র্যাঙ্কের অগ্রগতি:</b>\n<b>• মোট টার্গেট ({target} SOL):</b> {total_icon} (বর্তমান: {total_volume:.2f})\n\n<b>• লেগ শর্তাবলী:</b>\n<b> - স্ট্রং লেগ (সর্বনিম্ন {req_strongest} SOL):</b> {strongest_icon} (বর্তমান: <code>{highest_leg:.2f}</code>)\n<b> - অন্যান্য লেগ (সর্বনিম্ন {req_other} SOL):</b> {other_icon} (বর্তমান: <code>{other_legs_total:.2f}</code>)\n"
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
        "farming_packages": "<b>💎 Farming Packages (Max Cap: 250% Self, 500% with Team):</b>\n\n1️⃣ <b>STARTER</b>\n• Limit: 0.10 - 2.0 SOL\n• Reward: 0.5% Daily\n\n2️⃣ <b>ADVANCE</b>\n• Limit: 2.10 - 10.0 SOL\n• Reward: 1.0% Daily\n\n3️⃣ <b>PREMIUM</b>\n• Limit: 10.10 - 25.0 SOL\n• Reward: 1.5% Daily\n\n4️⃣ <b>GALAXY</b>\n• Limit: 25.10 - 100 SOL\n• Reward: 2.0% Daily",
        "deposit_prompt": "💰 <b>Deposit SOL</b>\n\nScan the QR code or copy address below to send SOL:\n\n<code>{wallet_address}</code>\n\n📝 <i>After sending, abeg paste your TxID here to activate!</i>",
        "no_history": "📜 <b>Withdrawal History</b>\n\nYou no get any past withdrawals.",
        "history_title": "📜 <b>Your Recent Withdrawals:</b>\n\n",
        "min_withdraw": "❌ <b>Minimum withdrawal limit na</b> <code>0.01 SOL</code>.",
        "max_daily_withdraw_err": "❌ <b>Daily limit reached!</b> Maximum na <code>10.0 SOL</code> per day.",
        "withdraw_prompt": "💰 <b>Available Balance:</b> <code>{bal:.4f} SOL</code>\n\nEnter amount (Max 10 SOL/day):",
        "team_empty": "👥 You no get any team members yet.",
        "ref_text": "<b>🔗 Your Referral Link</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>",
        "withdraw_processing": "⏳ <b>Withdrawal dey process!</b>\n\nYour request for <code>{amount:.4f} SOL</code> don go for review.",
        "withdraw_success_user": "✅ <b>Withdrawal Successful!</b>\n\nDem don send <code>{amount:.4f} SOL</code> to your wallet.\n🔗 <b>TxID:</b> <code>{txid}</code>",
        "dashboard_text": "👤 <b>User Dashboard</b>\n\n💰 <b>Available Balance:</b> <code>{balance:.4f} SOL</code>\n🌾 <b>Total Self Farming:</b> <code>{self_farming:.4f} SOL</code>\n🌾 <b>Self Farming Bonus:</b> <code>{self_bonus:.4f} SOL</code>\n👥 <b>Direct Referral Bonus:</b> <code>{direct_ref:.4f} SOL</code>\n🤝 <b>Team Referral Bonus:</b> <code>{team_ref:.4f} SOL</code>\n🤝 <b>Team Management Bonus:</b> <code>{team_override:.4f} SOL</code>\n🏆 <b>Rank & Royalty Bonus:</b> <code>{royalty:.4f} SOL</code>\n📈 <b>Total Earned:</b> <code>{earned:.4f} SOL</code> (Max Cap: <code>{max_cap:.2f} SOL</code>)\n\n🧁 <b>Total Withdrawals:</b> <code>{withdrawn:.4f} SOL</code>\n🎯 <b>Available Limit:</b> <code>{available_limit:.4f} SOL</code>\n\n📦 <b>Active Plan:</b> {active_plan}\n🏆 <b>Current Rank:</b> {current_rank}",
        "ranks_text": "🏆 <b>Ranks & Royalty Status</b>\n\n<b>• Total Directs:</b> <code>{directs_count}</code> (Active: <code>{active_directs}</code>)\n<b>• Direct Business:</b> <code>{direct_biz:.2f} SOL</code>\n<b>• Total Team Business:</b> <code>{team_biz:.2f} SOL</code>\n<b>• Current Rank:</b> <code>{current_rank_name}</code>\n<b>• Next Rank:</b> <code>{next_rank_name}</code>\n\n<b>🎯 Progress for Next Rank:</b>\n<b>• Total Target ({target} SOL):</b> {total_icon} (Current: {total_volume:.2f})\n\n<b>• Leg Check:</b>\n<b> - Strongest Leg (Min {req_strongest} SOL):</b> {strongest_icon} (Current: <code>{highest_leg:.2f}</code>)\n<b> - Other Legs (Min {req_other} SOL):</b> {other_icon} (Current: <code>{other_legs_total:.2f}</code>)\n"
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

def get_translated_text(user_id, key, **kwargs):
    lang = get_user_language(user_id)
    user_trans = translations.get(lang, translations["en"])
    template = user_trans.get(key, translations["en"].get(key, ""))
    return template.format(**kwargs)

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
        "params": [tx_id, {"encoding": "json", "maxSupportedTransactionVersion": 0}]
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
    directs = conn.execute("SELECT COALESCE(self_farming, 0) FROM users WHERE referrer_id=?", (user_id,)).fetchall()
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
                    conn.execute("UPDATE users SET balance = balance + ?, total_earned = total_earned + ?, direct_referral_bonus = COALESCE(direct_referral_bonus, 0) + ? WHERE user_id = ?", (bonus, bonus, bonus, ref_id))
                else:
                    conn.execute("UPDATE users SET balance = balance + ?, total_earned = total_earned + ?, team_referral_bonus = COALESCE(team_referral_bonus, 0) + ? WHERE user_id = ?", (bonus, bonus, bonus, ref_id))
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
            conn.execute("UPDATE users SET total_team_business = COALESCE(total_team_business, 0) + ? WHERE user_id = ?", (amount, upliner_id))
            curr = upliner_id
        else:
            break

def check_and_update_rank(user_id):
    conn = get_db()
    curr_data = conn.execute("SELECT rank FROM users WHERE user_id=?", (user_id,)).fetchone()
    old_rank = curr_data[0] if curr_data else "None"

    directs = conn.execute("SELECT user_id, COALESCE(self_farming, 0) FROM users WHERE referrer_id=?", (user_id,)).fetchall()
    
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

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def handle_language_selection(call):
    user_id = call.from_user.id
    selected_lang = call.data.split("_")[1]

    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET language = ? WHERE user_id = ?", (selected_lang, user_id))
    conn.commit()
    conn.close()

    t = translations.get(selected_lang, translations["en"])
    success_msg = t["lang_changed"]
    bot.answer_callback_query(call.id, success_msg)

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
    bot.send_message(message.chat.id, select_text, reply_markup=get_language_keyboard())

@bot.message_handler(commands=["language", "lang"])
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
    conn.execute("INSERT OR IGNORE INTO users (user_id, referrer_id) VALUES (?, ?)", (message.from_user.id, ref_id))
    
    if ref_id:
        conn.execute("UPDATE users SET referrer_id = ? WHERE user_id = ? AND (referrer_id IS NULL OR referrer_id = '')", (ref_id, message.from_user.id))

    conn.execute("UPDATE users SET username=? WHERE user_id=?", (message.from_user.username, message.from_user.id))
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
        reply_markup=get_main_keyboard(lang)
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

    if amount and amount > 100.0:
        bot.send_message(message.chat.id, "❌ <b>Deposit Failed!</b> Maximum deposit limit per transaction is <code>100.0 SOL</code>.", parse_mode="HTML")
        conn.close()
        return

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
            (amount, amount, plan, message.from_user.id)
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
            parse_mode="HTML"
        )
    else:
        bot.send_message(message.chat.id, "❌ <b>Verification Failed!</b> Invalid transaction or amount less than minimum <code>0.10 SOL</code>.", parse_mode="HTML")
    conn.close()

@bot.message_handler(commands=["dashboard"])
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
    directs_cursor = conn.execute("SELECT user_id, COALESCE(self_farming, 0) FROM users WHERE referrer_id=?", (user_id,)).fetchall()

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
        InlineKeyboardButton("👤 Manage User", callback_data="admin:manage_user")
    )
    markup.add(
        InlineKeyboardButton("📋 List All Users", callback_data="admin:list_users"),
        InlineKeyboardButton("🔍 User Withdrawal Log", callback_data="admin:user_withdrawals")
    )
    markup.add(
        InlineKeyboardButton("➕ Top-up Free ID", callback_data="admin:topup_free"),
        InlineKeyboardButton("➕ Top-up Paid ID", callback_data="admin:topup_paid")
    )
    markup.add(
        InlineKeyboardButton("📢 Broadcast Message", callback_data="admin:broadcast")
    )
    markup.add(InlineKeyboardButton("❌ Close", callback_data="admin:close"))
    return markup

def admin_user_markup(user_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("➕ Manual Top-up", callback_data=f"admin:user_topup:{user_id}"),
        InlineKeyboardButton("🔄 Refresh", callback_data=f"admin:user:{user_id}")
    )
    markup.add(
        InlineKeyboardButton("📜 Withdraw Log", callback_data=f"admin:view_w_log:{user_id}")
    )
    markup.add(
        InlineKeyboardButton("⬅ Admin Panel", callback_data="admin:panel")
    )
    return markup

def admin_stats_text():
    conn = get_db()
    totals = conn.execute("""SELECT
           COUNT(*),
           SUM(CASE WHEN total_investment >= 0.10 THEN 1 ELSE 0 END),
           SUM(CASE WHEN total_investment < 0.10 THEN 1 ELSE 0 END),
           COALESCE(SUM(total_investment), 0),
           COALESCE(SUM(balance), 0),
           COALESCE(SUM(total_earned), 0),
           COALESCE(SUM(total_withdrawn), 0)
         FROM users""").fetchone()
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

    lines = [
        f"<b>📋 ALL USERS</b> <code>({len(users)} total)</code>\n",
        "<b>Telegram ID | Username | Balance</b>"
    ]
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
    user = conn.execute("SELECT user_id, referrer_id, balance, total_investment, total_earned, total_withdrawn, plan_name, rank, status FROM users WHERE user_id=?", (user_id,)).fetchone()

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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_topups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                amount REAL,
                plan_name TEXT,
                timestamp DATETIME
            )
        """)
        cursor.execute("INSERT INTO admin_topups (user_id, amount, plan_name, timestamp) VALUES (?, ?, ?, datetime('now'))", (user_id, amount, plan_name))

        if is_paid:
            max_cap = amount * 2.5
            cursor.execute(
                "UPDATE users SET self_farming = COALESCE(self_farming, 0) + ?, max_cap = ?, status = 'active', plan_name = ? WHERE user_id = ?",
                (amount, max_cap, plan_name, user_id)
            )
            distribute_commissions(conn, user_id, amount)
            update_team_business_recursive(conn, user_id, amount)
        else:
            max_cap = amount * 2.5
            cursor.execute(
                "UPDATE users SET self_farming = COALESCE(self_farming, 0) + ?, max_cap = COALESCE(max_cap, 0) + ?, status = 'active', plan_name = ? WHERE user_id = ?",
                (amount, max_cap, plan_name, user_id)
            )

        cursor.execute("INSERT INTO admin_actions (admin_id, action, target_user_id, amount, note) VALUES (?, ?, ?, ?, ?)", (admin_id, "manual_topup_paid" if is_paid else "manual_topup_free", user_id, amount, note))
        conn.commit()
        return existed
    finally:
        conn.close()

def queue_admin_topup(admin_id, user_id, amount, note, is_paid=False):
    token = uuid.uuid4().hex if 'uuid' in globals() else str(time.time())
    ADMIN_PENDING_TOPUPS[token] = {
        "admin_id": admin_id,
        "user_id": user_id,
        "amount": amount,
        "note": note,
        "is_paid": is_paid
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

def admin_view_user_withdrawals(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        target_id = int(message.text.strip().split()[0])
    except Exception:
        bot.send_message(ADMIN_ID, "❌ Invalid User ID.", parse_mode="HTML")
        return

    conn = get_db()
    rows = conn.execute("SELECT id, amount, wallet_address, status, txid, created_at FROM withdrawals WHERE user_id = ? ORDER BY id DESC", (target_id,)).fetchall()
    conn.close()

    if not rows:
        bot.send_message(ADMIN_ID, f"<b>📜 User {target_id} has no withdrawal records.</b>", parse_mode="HTML")
        return

    total_w = sum([r[1] for r in rows if r[3] in ["Paid", "APPROVED"]])
    text = f"<b>📜 Withdrawal Log for User:</b> <code>{target_id}</code>\n<b>💰 Total Approved/Paid:</b> <code>{total_w:.4f} SOL</code>\n\n"
    for w_id, amt, wallet, status, txid, date in rows:
        text += f"• <b>Req ID #{w_id}:</b> <code>{amt:.4f} SOL</code> | Status: <b>{status}</b>\n  🏦 Wallet: <code>{wallet}</code>\n  🔗 TxID: <code>{escape(txid)}</code>\n  🕒 {date}\n\n"

    bot.send_message(ADMIN_ID, text[:4000], parse_mode="HTML")

@bot.message_handler(commands=["admin"])
def admin_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    bot.send_message(
        message.chat.id,
        "<b>🛠 ADMIN PANEL</b>\nChoose an action:",
        reply_markup=admin_panel_markup(),
        parse_mode="HTML"
    )

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
    elif action == "user_withdrawals":
        sent = bot.send_message(call.message.chat.id, "<b>Enter User ID to check withdrawal history:</b>", parse_mode="HTML")
        bot.register_next_step_handler(sent, admin_view_user_withdrawals)
    elif action == "view_w_log":
        try:
            target_id = int(parts[2])
            conn = get_db()
            rows = conn.execute("SELECT id, amount, wallet_address, status, txid, created_at FROM withdrawals WHERE user_id = ? ORDER BY id DESC", (target_id,)).fetchall()
            conn.close()
            if not rows:
                bot.send_message(call.message.chat.id, f"<b>No withdrawals for user {target_id}</b>", parse_mode="HTML")
                return
            total_w = sum([r[1] for r in rows if r[3] in ["Paid", "APPROVED"]])
            text = f"<b>📜 Withdrawal Log for User:</b> <code>{target_id}</code>\n<b>💰 Total Approved/Paid:</b> <code>{total_w:.4f} SOL</code>\n\n"
            for w_id, amt, wallet, status, txid, date in rows:
                text += f"• <b>Req #{w_id}:</b> <code>{amt:.4f} SOL</code> | Status: <b>{status}</b>\n  🏦 <code>{wallet}</code>\n  🔗 <code>{escape(txid)}</code>\n  🕒 {date}\n\n"
            bot.send_message(call.message.chat.id, text[:4000], parse_mode="HTML")
        except Exception as e:
            print(f"Error: {e}")
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

@bot.message_handler(commands=["withdrawals"])
def admin_withdrawals_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 2:
        bot.send_message(ADMIN_ID, "<b>Usage:</b> <code>/withdrawals <UserID></code>", parse_mode="HTML")
        return

    try:
        target_id = int(args[1])
        conn = get_db()
        rows = conn.execute("SELECT id, amount, wallet_address, status, txid, created_at FROM withdrawals WHERE user_id = ? ORDER BY id DESC", (target_id,)).fetchall()
        conn.close()

        if not rows:
            bot.send_message(ADMIN_ID, f"<b>📜 No withdrawals found for user {target_id}.</b>", parse_mode="HTML")
            return

        total_w = sum([r[1] for r in rows if r[3] in ["Paid", "APPROVED"]])
        text = f"<b>📜 Withdrawal Log for User:</b> <code>{target_id}</code>\n<b>💰 Total Approved/Paid:</b> <code>{total_w:.4f} SOL</code>\n\n"
        for w_id, amt, wallet, status, txid, date in rows:
            text += f"• <b>Req ID #{w_id}:</b> <code>{amt:.4f} SOL</code> | Status: <b>{status}</b>\n  🏦 Wallet: <code>{wallet}</code>\n  🔗 TxID: <code>{escape(txid)}</code>\n  🕒 {date}\n\n"

        bot.send_message(ADMIN_ID, text[:4000], parse_mode="HTML")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"Error: {e}", parse_mode="HTML")

@bot.message_handler(content_types=['text', 'photo'], func=lambda message: ADMIN_BROADCAST_STATE.get(message.from_user.id) == "WAITING_FOR_BROADCAST")
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

    today_date = datetime.now().strftime("%Y-%m-%d")
    user_row = conn.execute("SELECT last_withdrawal_date FROM users WHERE user_id=?", (user_id,)).fetchone()

    if user_row and user_row[0] == today_date:
        conn.close()
        bot.send_message(message.chat.id, "❌ <b>Daily Withdrawal Limit Reached!</b>\n\nYou can only request 1 withdrawal per day. Please try again tomorrow.", parse_mode="HTML")
        return

    sum_row = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM withdrawals WHERE user_id = ? AND created_at LIKE ? AND status IN ('Paid', 'Pending', 'APPROVED')", (user_id, f"{today_date}%")).fetchone()
    today_withdrawn_so_far = sum_row[0] if sum_row else 0.0

    if today_withdrawn_so_far >= 10.0:
        conn.close()
        err_txt = get_translated_text(user_id, "max_daily_withdraw_err")
        bot.send_message(message.chat.id, err_txt, parse_mode="HTML")
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

    user_id = message.from_user.id
    conn = get_db()

    today_date = datetime.now().strftime("%Y-%m-%d")
    sum_row = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM withdrawals WHERE user_id = ? AND created_at LIKE ? AND status IN ('Paid', 'Pending', 'APPROVED')", (user_id, f"{today_date}%")).fetchone()
    today_withdrawn_so_far = sum_row[0] if sum_row else 0.0

    if (today_withdrawn_so_far + amount) > 10.0:
        rem_limit = max(0.0, 10.0 - today_withdrawn_so_far)
        conn.close()
        bot.send_message(message.chat.id, f"❌ <b>Daily Withdrawal Limit Error!</b>\n\nYou can only withdraw up to <code>10.0 SOL</code> per day.\n• Today's Withdrawn: <code>{today_withdrawn_so_far:.4f} SOL</code>\n• Remaining Limit: <code>{rem_limit:.4f} SOL</code>", parse_mode="HTML")
        return

    u = conn.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    bal = u[0] if u else 0

    if amount < 0.01 or amount > bal:
        bot.send_message(message.chat.id, "❌ Invalid amount or insufficient balance.")
        return

    msg = bot.send_message(message.chat.id, "Enter your Solana <b>Wallet Address</b>:", parse_mode="HTML")
    bot.register_next_step_handler(msg, process_withdrawal_address, amount)

# --- TIERED WITHDRAWAL & 10% FEE LOGIC ---
def process_withdrawal_address(message, amount):
    wallet_address = message.text.strip()
    user_id = message.from_user.id

    today_date = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    conn.execute("UPDATE users SET last_withdrawal_date = ? WHERE user_id = ?", (today_date, user_id))
    conn.commit()

    payout_amount = round(amount * 0.90, 4)
    fee_amount = round(amount * 0.10, 4)

    if 0.01 <= amount <= 0.10:
        bot.send_message(message.chat.id, f"⏳ Processing instant withdrawal of <code>{amount:.4f} SOL</code> (Net Payout: <code>{payout_amount:.4f} SOL</code>)...", parse_mode="HTML")

        success, tx_hash_or_err = send_sol_payout(wallet_address, payout_amount)

        if success:
            conn.execute(
                "UPDATE users SET balance = balance - ?, total_withdrawn = total_withdrawn + ? WHERE user_id = ?",
                (amount, amount, user_id)
            )
            conn.execute(
                "INSERT INTO withdrawals (user_id, amount, wallet_address, txid, status) VALUES (?, ?, ?, ?, 'Paid')",
                (user_id, amount, wallet_address, tx_hash_or_err)
            )
            conn.commit()
            conn.close()

            succ_msg = get_translated_text(user_id, "withdraw_success_user", amount=amount, txid=tx_hash_or_err)
            bot.send_message(message.chat.id, succ_msg, parse_mode="HTML")
        else:
            conn.close()
            bot.send_message(message.chat.id, f"⚠️ Auto-withdrawal failed! Error: {tx_hash_or_err}", parse_mode="HTML")

    elif amount > 0.10:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO withdrawals (user_id, amount, wallet_address, txid, status) VALUES (?, ?, ?, 'Pending', 'Pending')",
            (user_id, amount, wallet_address),
        )
        request_id = cursor.lastrowid
        conn.commit()
        conn.close()

        proc_msg = get_translated_text(user_id, "withdraw_processing", amount=amount)
        bot.send_message(message.chat.id, proc_msg, parse_mode="HTML")

        admin_msg = (
            f"🚨 <b>Withdrawal Request</b>\n\n"
            f"User: <code>{user_id}</code>\n"
            f"Requested Amt: <code>{amount:.4f} SOL</code>\n"
            f"Fee (10%): <code>{fee_amount:.4f} SOL</code>\n"
            f"👉 <b>Net Send to User:</b> <code>{payout_amount:.4f} SOL</code>\n"
            f"Wallet:\n<code>{wallet_address}</code>\n\n"
            f"Command to Pay:\n"
            f"<code>/pay {user_id} {payout_amount:.4f} [TxID]</code>"
        )
        
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("✅ Approve", callback_data=f"app_wd:{request_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"rej_wd:{request_id}"),
        )
        bot.send_message(ADMIN_ID, admin_msg, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith(("app_wd:", "rej_wd:")))
def handle_withdrawal_approval(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    if call.from_user.id != ADMIN_ID:
        return

    data_parts = call.data.split(":")
    action = data_parts[0]
    request_id = data_parts[1]

    conn = get_db()
    conn.row_factory = sqlite3.Row
    req = conn.execute("SELECT * FROM withdrawals WHERE id = ? AND status = 'Pending'", (request_id,)).fetchone()

    if not req:
        conn.close()
        bot.edit_message_text(
            text=call.message.text + "\n\n⚠️ Request already processed or not found!",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML"
        )
        return

    user_id = req["user_id"]
    amount = req["amount"]
    wallet_address = req["wallet_address"]
    payout_amount = amount * 0.90

    if action == "app_wd":
        bot.edit_message_text(
            text=call.message.text + "\n\n⏳ Processing SOL Transfer...",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML"
        )

        success, tx_hash_or_err = send_sol_payout(wallet_address, payout_amount)

        if success:
            conn.execute(
                "UPDATE users SET balance = balance - ?, total_withdrawn = total_withdrawn + ? WHERE user_id = ?",
                (amount, amount, user_id)
            )
            conn.execute(
                "UPDATE withdrawals SET status = 'Paid', txid = ? WHERE id = ?",
                (tx_hash_or_err, request_id)
            )
            conn.commit()
            conn.close()

            user_succ_text = get_translated_text(user_id, "withdraw_success_user", amount=amount, txid=tx_hash_or_err)
            bot.send_message(user_id, user_succ_text, parse_mode="HTML")

            bot.edit_message_text(
                text=call.message.text + f"\n\n✅ <b>APPROVED & PAID!</b>\nTxID: <code>{escape(tx_hash_or_err)}</code>",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML"
            )
        else:
            conn.close()
            bot.edit_message_text(
                text=call.message.text + f"\n\n❌ <b>Failed to send SOL:</b> {tx_hash_or_err}",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML"
            )

    elif action == "rej_wd":
        conn.execute("UPDATE withdrawals SET status = 'Rejected' WHERE id = ?", (request_id,))
        conn.commit()
        conn.close()

        bot.send_message(user_id, f"❌ Aapka withdrawal request (<code>{amount:.4f} SOL</code>) reject kar diya gaya hai.", parse_mode="HTML")
        bot.edit_message_text(
            text=call.message.text + "\n\n❌ <b>REJECTED BY ADMIN</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML"
        )

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
                            (total_payout, total_payout, roi, royalty, uid)
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

        time.sleep(86400)

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

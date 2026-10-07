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

# --- 5-LEVEL DIRECT REFERRAL INCOME PERCENTAGES ---
REF_LEVELS = [0.05, 0.04, 0.03, 0.02, 0.01]

# --- 25-LEVEL OVERRIDE BONUS PERCENTAGES ---
OVERRIDE_LEVELS = [
    0.15, 0.10, 0.05, 0.03, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02,
    0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02,
    0.02, 0.03, 0.05, 0.10, 0.15
]

# --- RANKS & ROYALTY ---
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

# --- HELPER FUNCTIONS ---
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

# --- DISTRIBUTE 5-LEVEL DIRECT COMMISSIONS ---
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

# --- CALCULATE RANK WITH LEG MINIMUM REQUIREMENTS & CONGRATULATION ALERT ---
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
        conn.execute(
            "UPDATE users SET rank = ? WHERE user_id = ?",
            (achieved_rank, user_id),
        )
        conn.commit()
        
        try:
            dir_biz = get_user_direct_business(conn, user_id)
            congrats_text = (
                "🎉 <b>CONGRATULATIONS!</b> 🎉\n\n"
                "Fantastic news! You have successfully achieved a new rank upgrade!\n\n"
                f"🏆 <b>New Rank:</b> <code>{achieved_rank}</code>\n\n"
                f"• Direct Business: <b>{dir_biz:.2f} SOL</b>\n"
                f"• Team Business: <b>{total_team_bus:.2f} SOL</b>\n\n"
                "Keep up the amazing work and continue growing your team and earnings! 🚀"
            )
            bot.send_message(user_id, congrats_text, parse_mode="HTML")
        except Exception as e:
            print(f"Failed to send rank congratulation to {user_id}: {e}")
    else:
        conn.execute(
            "UPDATE users SET rank = ? WHERE user_id = ?",
            (achieved_rank, user_id),
        )
        conn.commit()

    conn.close()

# --- HANDLERS ---
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

    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("💎 Farming Plans", "💰 Deposit SOL")
    markup.add("📊 Dashboard", "🎁 Withdraw")
    markup.add("🔗 Referral Link", "👥 Team Members")
    markup.add("🏆 Ranks & Royalty", "📜 Withdrawal History")

    bot.send_message(
        message.chat.id,
        f"🚜 <b>Welcome to {PROJECT_NAME}</b>\n\nUse the buttons below to start your investment journey.",
        parse_mode="HTML",
        reply_markup=markup,
    )

@bot.message_handler(func=lambda m: m.text == "💎 Farming Plans")
def farming_plans(message):
  text = (
      "<b>💎 Farming Packages (Max Cap: 250% for Self, 500% with Team):</b>\n\n"
      "1️⃣ <b>STARTER</b>\n<b>• Limit:</b> <code>0.10 - 2.0 SOL</code>\n<b>• Reward:</b> <code>0.5% Daily</code>\n\n"
      "2️⃣ <b>ADVANCE</b>\n<b>• Limit:</b> <code>2.10 - 10.0 SOL</code>\n<b>• Reward:</b> <code>1.0% Daily</code>\n\n"
      "3️⃣ <b>PREMIUM</b>\n<b>• Limit:</b> <code>10.10 - 25.0 SOL</code>\n<b>• Reward:</b> <code>1.5% Daily</code>\n\n"
      "4️⃣ <b>GALAXY</b>\n<b>• Limit:</b> <code>25.10 - 1000 SOL</code>\n<b>• Reward:</b> <code>2.0% Daily</code>\n\n"
      "⚠️ <i>Note: Base cap is 250%. Referring at least one active user upgrades max cap to 500%.</i>"
  )
  bot.send_message(message.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "💰 Deposit SOL")
def deposit_sol(message):
    wallet_address = ADMIN_WALLET  
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={wallet_address}"
    caption = (
        f"💰 <b>Deposit SOL</b>\n\n"
        f"Please scan the QR code above or copy the address below to deposit SOL:\n\n"
        f"<code>{wallet_address}</code>\n\n"
        f"⚠ <i>Send only SOL to this address.</i>\n\n"
        f"📝 <i>After sending, please send your Transaction Hash (TxID) here to activate your ID!</i>"
    )
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
@bot.message_handler(func=lambda m: m.text and "Dashboard" in m.text)
def dashboard_handler(message):
    user_id = message.from_user.id
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

    text = (
        f"👤 <b>User Dashboard</b>\n\n"
        f"💰 <b>Available Balance:</b> <code>{balance:.4f} SOL</code>\n"
        f"🌾 <b>Total Self Farming:</b> <code>{self_farming:.4f} SOL</code>\n"
        f"🌾 <b>Self Farming Bonus:</b> <code>{self_bonus:.4f} SOL</code>\n"
        f"👥 <b>Direct Referral Bonus:</b> <code>{direct_ref:.4f} SOL</code>\n"
        f"🤝 <b>Team Referral Bonus:</b> <code>{team_ref:.4f} SOL</code>\n"
        f"🤝 <b>Team Farming Override Bonus:</b> <code>{team_override:.4f} SOL</code>\n"
        f"🏆 <b>Rank & Royalty Bonus:</b> <code>{royalty:.4f} SOL</code>\n"
        f"📈 <b>Total Earned:</b> <code>{earned:.4f} SOL</code> (Max Cap: <code>{max_cap:.2f} SOL</code>)\n\n"
        f"🧁 <b>Total Withdrawals:</b> <code>{withdrawn:.4f} SOL</code>\n"
        f"🎯 <b>Available Withdrawal Limit:</b> <code>{available_limit:.4f} SOL</code>\n\n"
        f"📦 <b>Active Plan:</b> {active_plan}\n"
        f"🏆 <b>Current Rank:</b> {current_rank}"
    )
    bot.send_message(message.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "🏆 Ranks & Royalty")
def team_ranks(message):
    user_id = message.from_user.id
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
        strongest_icon = "✅" if is_strongest_met else f"❌ (Need {strongest_rem:.2f} SOL more)"

        is_other_met = other_legs_total >= req_other
        other_rem = 0 if is_other_met else max(0, req_other - other_legs_total)
        other_icon = "✅" if is_other_met else f"❌ (Need {other_rem:.2f} SOL more)"

        total_volume = highest_leg + other_legs_total
        is_total_met = total_volume >= target
        total_rem = 0 if is_total_met else max(0, target - total_volume)
        total_icon = "✅" if is_total_met else f"❌ (Need {total_rem:.2f} SOL more)"
    else:
        next_rank_name = "Max Rank Achieved 🎉"
        strongest_icon = "✅"
        other_icon = "✅"
        total_icon = "✅"
        req_strongest = 0
        req_other = 0
        target = 0

    text = (
        f"🏆 <b>Ranks & Royalty Status</b>\n\n"
        f"<b>• Total Directs:</b> <code>{directs_count}</code> (Active: <code>{active_directs}</code>)\n"
        f"<b>• Direct Business:</b> <code>{direct_biz:.2f} SOL</code>\n"
        f"<b>• Total Team Business:</b> <code>{team_biz:.2f} SOL</code>\n"
        f"<b>• Current Rank:</b> <code>{current_rank_name}</code>\n"
        f"<b>• Next Rank:</b> <code>{next_rank_name}</code>\n\n"
        f"<b>🎯 Progress for Next Rank:</b>\n"
        f"<b>• Total Target ({target} SOL):</b> {total_icon} (Current: {highest_leg + other_legs_total:.2f})\n\n"
        f"<b>• Leg Requirements Check:</b>\n"
        f"<b> - Strongest Leg (Min {req_strongest} SOL):</b> {strongest_icon} (Current: <code>{highest_leg:.2f}</code>)\n"
        f"<b> - Other Legs Combined (Min {req_other} SOL):</b> {other_icon} (Current: <code>{other_legs_total:.2f}</code>)\n"
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
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, referrer_id, status) VALUES (?, NULL, 'inactive')",
            (user_id,),
        )

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
        cursor.execute('''
            INSERT INTO admin_topups (user_id, amount, plan_name, timestamp)
            VALUES (?, ?, ?, datetime('now'))
        ''', (user_id, amount, plan_name))

        if is_paid:
            max_cap = amount * 2.5 
            cursor.execute(
                """
                UPDATE users 
                SET self_farming = COALESCE(self_farming, 0) + ?,
                    max_cap = ?,
                    status = 'active', 
                    plan_name = ? 
                WHERE user_id = ?
                """,
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
       f"<b>⚠️ Confirm manual top-up</b>\n\n"
       f"<b>User ID:</b> <code>{user_id}</code>\n"
       f"<b>Amount:</b> <code>{amount:.8f} SOL</code>\n",
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
        bot.send_message(
            call.message.chat.id,
            "📢 <b>Broadcast Mode Activated</b>\n\nPlease send the message you want to broadcast (Text or Photo with Caption):",
            parse_mode="HTML"
        )
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

# --- ADMIN BROADCAST HANDLER ---
@bot.message_handler(
    content_types=["text", "photo"],
    func=lambda message: ADMIN_BROADCAST_STATE.get(message.from_user.id) == "WAITING_FOR_BROADCAST"
)
def execute_broadcast(message):
    admin_id = message.from_user.id
    if admin_id != ADMIN_ID:
        return
    ADMIN_BROADCAST_STATE.pop(admin_id, None)

    conn = get_db()
    users = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()

    total_users = len(users)
    success_count = 0
    fail_count = 0

    status_msg = bot.send_message(
        message.chat.id,
        f"🚀 <b>Broadcast started...</b>\nTotal users: {total_users}",
        parse_mode="HTML"
    )

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

# --- WITHDRAWAL & HISTORY HANDLERS (Updated with Fee Display for Admin) ---
@bot.message_handler(func=lambda m: m.text == "📜 Withdrawal History")
def withdrawal_history(message):
    conn = get_db()
    rows = conn.execute("SELECT amount, status, txid, created_at FROM withdrawals WHERE user_id = ? ORDER BY id DESC LIMIT 10", (message.from_user.id,)).fetchall()
    conn.close()
    if not rows:
        bot.send_message(message.chat.id, "📜 <b>Withdrawal History</b>\n\nYou have no past withdrawals.", parse_mode="HTML")
        return
    
    text = "📜 <b>Your Recent Withdrawals:</b>\n\n"
    for amt, status, txid, date in rows:
        text += f"• <code>{amt:.4f} SOL</code> | Status: <b>{status}</b>\n  🔗 <b>TxID:</b> <code>{escape(txid)}</code>\n  🕒 <code>{date}</code>\n\n"
    bot.send_message(message.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.strip() in ["🎁 Withdraw", "Withdraw"])
def withdraw_start(message):
    conn = get_db()
    u = conn.execute("SELECT balance FROM users WHERE user_id=?", (message.from_user.id,)).fetchone()
    conn.close()
    bal = u[0] if u else 0
    if bal < 0.01:
        bot.send_message(message.chat.id, "❌ <b>Minimum withdrawal limit is</b> <code>0.01 SOL</code>.", parse_mode="HTML")
        return
    msg = bot.send_message(message.chat.id, f"💰 <b>Available Balance:</b> <code>{bal:.4f} SOL</code>\n\nEnter amount:", parse_mode="HTML")
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
    
    # 10% Fee Calculation
    fee = amount * 0.10
    net_amount = amount - fee

    bot.send_message(message.chat.id, f"✅ Withdrawal request submitted!\n• Requested: <code>{amount:.4f} SOL</code>\n• Fee (10%): <code>{fee:.4f} SOL</code>\n• You Will Get: <code>{net_amount:.4f} SOL</code>", parse_mode="HTML")
    
    # Admin notification showing requested amount, 10% fee, and exact net amount to send
    admin_msg = (
        f"🚨 <b>Withdrawal Request</b>\n"
        f"User: <code>{user_id}</code>\n"
        f"Requested Amt: <code>{amount:.4f} SOL</code>\n"
        f"Fee (10%): <code>{fee:.4f} SOL</code>\n"
        f"👉 <b>Net Send to User:</b> <code>{net_amount:.4f} SOL</code>\n"
        f"Wallet: <code>{wallet_address}</code>\n\n"
        f"Command to Pay:\n<code>/pay {user_id} {net_amount} [TxID]</code>"
    )
    bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")

@bot.message_handler(commands=["pay"])
def admin_pay(message):
  if message.from_user.id == ADMIN_ID:
    try:
      args = message.text.split()
      uid, amt = int(args[1]), float(args[2])
      txid = args[3] if len(args) > 3 else "Paid by Admin"
      
      # Calculate net amount after 10% fee for the user notification message
      net_amt = amt * 0.9
      
      conn = get_db()
      # Deducts the full requested amount (amt) from user balance and total withdrawals
      conn.execute("UPDATE users SET balance = balance - ?, total_withdrawn = total_withdrawn + ? WHERE user_id = ?", (amt, amt, uid))
      conn.execute("INSERT INTO withdrawals (user_id, amount, wallet_address, txid) VALUES (?, ?, ?, ?)", (uid, amt, "Admin Paid", txid))
      conn.commit()
      conn.close()
      
      # Sends the net amount (after fee deduction) to the user
      bot.send_message(uid, f"📤 <b>Paid:</b> <code>{net_amt:.4f} SOL</code> sent!\n🔗 <b>TxID:</b> <code>{txid}</code>", parse_mode="HTML")
      bot.send_message(ADMIN_ID, "✅ <b>Done & Saved TxID!</b>", parse_mode="HTML")
    except Exception as e:
      bot.send_message(ADMIN_ID, f"Error: {e}", parse_mode="HTML")

# --- TEAM MEMBERS HANDLERS (WITH LEVEL-WISE BUSINESS BREAKDOWN) ---
@bot.message_handler(func=lambda m: m.text == "👥 Team Members")
def my_team_handler(message):
    conn = get_db()
    user_id = message.from_user.id

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
        bot.send_message(message.chat.id, "👥 You don't have any team members yet.", parse_mode="HTML")
        return

    total_members = len(team_data)
    level_counts = {}
    level_business = {}
    for uid, sf, lvl in team_data:
        level_counts[lvl] = level_counts.get(lvl, 0) + 1
        level_business[lvl] = level_business.get(lvl, 0.0) + sf

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

@bot.message_handler(func=lambda m: m.text == "🔗 Referral Link")
def referral_link_handler(message):
    bot_username = bot.get_me().username
    user_id = message.from_user.id
    text = f"<b>🔗 Your Referral Link</b>\n\n<code>https://t.me/{bot_username}?start={user_id}</code>"
    bot.send_message(message.chat.id, text, parse_mode="HTML")

# --- ROI & BACKGROUND WORKER (5 MIN SLEEP) ---
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
            print("ROI worker cycle completed. Sleeping for 5 minutes...")
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

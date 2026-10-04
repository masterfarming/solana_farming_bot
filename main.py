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

# --- CONFIGURATION ---
TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
bot = telebot.TeleBot(TOKEN)
ADMIN_WALLET = "BY3Tzt5cA8FwoPRw3B265jwb8NDU5dupf76SXwKqjnRZ"
ADMIN_ID = 5939907983
SUPPORT_ADMIN = "@Farming_Master"
ADMIN_PENDING_TOPUPS = {}

PROJECT_NAME = "SOLANA FARMING TELEBOT"

# --- PACKAGES (Default Max Cap 250%, Upgradeable to 500% with 1 Active Direct) ---
PACKAGES = {
    "starter": {"name": "STARTER", "roi": 0.005, "min": 0.10, "max": 2.00, "cap": 2.5},
    "advance": {"name": "ADVANCE", "roi": 0.01, "min": 2.10, "max": 10.00, "cap": 2.5},
    "premium": {"name": "PREMIUM", "roi": 0.015, "min": 10.10, "max": 25.00, "cap": 2.5},
    "galaxy": {"name": "GALAXY", "roi": 0.02, "min": 25.10, "max": 1000.00, "cap": 2.5}
}

# --- 5-LEVEL DIRECT REFERRAL INCOME PERCENTAGES ---
REF_LEVELS = [0.05, 0.04, 0.03, 0.02, 0.01]

# --- 25-LEVEL OVERRIDE BONUS PERCENTAGES (ROI on ROI) ---
OVERRIDE_LEVELS = [
    0.15, 0.10, 0.05, 0.03, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02,
    0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02,
    0.02, 0.03, 0.05, 0.10, 0.15
]

# --- RANKS & ROYALTY (40:60 Ratio Rules) ---
RANKS = [
    {"name": "1 Star Rank", "target": 30, "daily_royalty": 0.03},
    {"name": "2 Silver Rank", "target": 100, "daily_royalty": 0.10},
    {"name": "3 Gold Rank", "target": 500, "daily_royalty": 0.50},
    {"name": "4 Diamond Rank", "target": 1500, "daily_royalty": 1.50},
    {"name": "5 Galaxy Rank", "target": 5000, "daily_royalty": 5.00},
    {"name": "6 Super Galaxy Rank", "target": 10000, "daily_royalty": 10.00},
    {"name": "7 Universe Rank", "target": 20000, "daily_royalty": 20.00},
    {"name": "8 Crown Rank", "target": 100000, "daily_royalty": 100.00},
    {"name": "9 Crown Master Rank", "target": 500000, "daily_royalty": 500.00},
    {"name": "10 Universe Master Rank", "target": 1000000, "daily_royalty": 1000.00},
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
        direct_referral_earned REAL DEFAULT 0,
        team_override_earned REAL DEFAULT 0,
        rank_royalty_earned REAL DEFAULT 0
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
    try:
        c.execute("ALTER TABLE users ADD COLUMN self_farming REAL DEFAULT 0")
    except Exception:
        pass

    try:
        c.execute("ALTER TABLE users ADD COLUMN max_cap REAL DEFAULT 0;")
        try:
            c.execute("ALTER TABLE users ADD COLUMN plan_name TEXT;")
        except Exception:
            pass

    except Exception:
        pass

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


# --- HELPER FUNCTIONS FOR BUSINESS & SUBTREE ---
def get_user_direct_business(conn, user_id):
  directs = conn.execute("SELECT COALESCE(self_farming, 0) FROM users WHERE referrer_id=?", (user_id,)).fetchall()
  return sum([d[0] for d in directs])

def get_active_directs_count(user_id):
    conn = get_db()
    try:
        directs = conn.execute(
            "SELECT COALESCE(self_farming, 0) FROM users WHERE referrer_id=?",
            (user_id,)
        ).fetchall()
        count = 0
        for d in directs:
            if d[0] >= 0.10:
                count += 1
        return count
    finally:
        conn.close()

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
                actual_active_directs = get_active_directs_count(ref_id)
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
                        "UPDATE users "
                        "SET balance = balance + ?, "
                        "total_earned = total_earned + ?, "
                        "direct_referral_bonus = "
                        "COALESCE(direct_referral_bonus, 0) + ? "
                        "WHERE user_id = ?",
                        (bonus, bonus, bonus, ref_id)
                    )
                else:
                    conn.execute(
                        "UPDATE users "
                        "SET balance = balance + ?, "
                        "total_earned = total_earned + ?, "
                        "team_referral_bonus = "
                        "COALESCE(team_referral_bonus, 0) + ? "
                        "WHERE user_id = ?",
                        (bonus, bonus, bonus, ref_id)
                    )
        except Exception as e:
            raise e

def update_team_business_recursive(
  conn, 
  user_id, 
  amount
):
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

# --- CALCULATE RANK WITH 40:60 RATIO ---
def check_and_update_rank(user_id):
    conn = get_db()
    directs = conn.execute(
        "SELECT user_id, total_investment FROM users WHERE referrer_id=?",
        (user_id,),
    ).fetchall()
    if not directs:
        conn.close()
        return

    leg_businesses = []
    for d_id, d_inv in directs:
        sub_bus = get_subtree_business(conn, d_id) + d_inv
        leg_businesses.append(sub_bus)

    leg_businesses.sort(reverse=True)

    if len(leg_businesses) < 2:
        conn.close()
        return

    highest_leg = leg_businesses[0]
    other_legs_total = sum(leg_businesses[1:])
    total_team_bus = sum(leg_businesses)

    achieved_rank = "None"
    for r in RANKS:
        req = r["target"]
        if total_team_bus >= req:
            cond_high = highest_leg <= (total_team_bus * 0.40)
            cond_other = other_legs_total >= (total_team_bus * 0.60)
            if cond_high and cond_other:
                achieved_rank = r["name"]

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

    markup = ReplyKeyboardMarkup(
        resize_keyboard=True, 
        row_width=2
    )
    markup.add("💎 Farming Plans", "💰 Deposit SOL")
    markup.add("📊 Dashboard", "🎁 Withdraw")
    markup.add("🔗 Referral Link", "👥 Team Members")
    markup.add("🏆 Ranks & Royalty")

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


@bot.message_handler(func=lambda m: m.text == "📥 Deposit SOL")
def deposit(message):
  sent = bot.send_message(
      message.chat.id,
      f"<b>📥 Deposit SOL</b>\n\nPlease transfer SOL to this wallet:\n<code>{ADMIN_WALLET}</code>\n\nAfter transferring, please paste your <b>TXID (Transaction Signature)</b> below:",
      parse_mode="HTML",
  )
  bot.register_next_step_handler(sent, process_deposit)


def process_deposit(message):
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
          "UPDATE users SET self_farming = self_farming + ?, total_investment = total_investment + ?, plan_id = ? WHERE user_id = ?",
          (amount, amount, plan, message.from_user.id),
      )
    conn.execute("INSERT INTO transactions (txid) VALUES (?)", (txid,))
    conn.commit()

    distribute_commissions(message.from_user.id, amount)

    res = conn.execute("SELECT referrer_id FROM users WHERE user_id=?", (message.from_user.id,)).fetchone()
    if res and res[0]:
      check_and_update_rank(res[0])

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
    print(">>> DASHBOARD CLICKED OR COMMAND USED! <<<")
    user_id = message.from_user.id

    try:
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Automatically ensure all required columns exist
        columns_to_add = [
            "self_farming REAL DEFAULT 0.0",
            "self_farming_bonus REAL DEFAULT 0.0",
            "direct_referral_bonus REAL DEFAULT 0.0",
            "team_referral_bonus REAL DEFAULT 0.0",
            "team_farming_override_bonus REAL DEFAULT 0.0",
            "rank_royalty_bonus REAL DEFAULT 0.0",
            "total_earned REAL DEFAULT 0.0",
            "total_withdrawn REAL DEFAULT 0.0",
            "current_rank TEXT DEFAULT 'None'",
            "active_plan TEXT DEFAULT 'None'",
            "max_cap REAL DEFAULT 0.0"
        ]
        for col in columns_to_add:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col}")
            except Exception:
                pass
        conn.commit()

        u = cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")
        u = None

    if not u:
        bot.send_message(message.chat.id, "Please start the bot first using /start", parse_mode="HTML")
        return

    balance = u["balance"] if "balance" in u.keys() and u["balance"] is not None else 0.0
    self_farming = u["self_farming"] if "self_farming" in u.keys() and u["self_farming"] is not None else 0.0
    self_bonus = u["self_farming_bonus"] if "self_farming_bonus" in u.keys() and u["self_farming_bonus"] is not None else 0.0
    direct_ref = u["direct_referral_bonus"] if "direct_referral_bonus" in u.keys() and u["direct_referral_bonus"] is not None else 0.0
    team_ref = u["team_referral_bonus"] if "team_referral_bonus" in u.keys() and u["team_referral_bonus"] is not None else 0.0
    team_override = u["team_farming_override_bonus"] if "team_farming_override_bonus" in u.keys() and u["team_farming_override_bonus"] is not None else 0.0
    royalty = u["rank_royalty_bonus"] if "rank_royalty_bonus" in u.keys() and u["rank_royalty_bonus"] is not None else 0.0
    withdrawn = (
        u["total_withdrawn"]
        if "total_withdrawn" in u.keys()
        and u["total_withdrawn"] is not None
        else 0.0
    )
    active_plan = u["plan_name"] if "plan_name" in u.keys() and u["plan_name"] else "None"
    current_rank = u["rank"] if "rank" in u.keys() and u["rank"] else "None"

    # Total Earned calculation across all income types
    earned = self_bonus + direct_ref + team_ref + team_override + royalty

    # Dynamic Max Cap calculation based on investment/self_farming and direct referral status
    conn = get_db()
    has_ref = has_direct_referral(conn, user_id)
    conn.close()

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
    conn = get_db()
    u = conn.execute("SELECT rank FROM users WHERE user_id=?", (message.from_user.id,)).fetchone()

    directs_cursor = conn.execute(
        "SELECT user_id, COALESCE(self_farming, 0) FROM users WHERE referrer_id=?",
        (message.from_user.id,)
    ).fetchall()

    directs_count = len(directs_cursor)
    active_directs = get_active_directs_count(message.from_user.id)
    direct_biz = sum([d[1] for d in directs_cursor])
    team_biz = get_total_team_business(conn, message.from_user.id)
    has_ref = has_direct_referral(conn, message.from_user.id)

    leg_businesses = []
    for d_id, d_inv in directs_cursor:
        sub_bus = get_subtree_business(conn, d_id) + d_inv
        leg_businesses.append(sub_bus)

    leg_businesses.sort(reverse=True)
    highest_leg = leg_businesses[0] if len(leg_businesses) > 0 else 0
    other_legs_total = sum(leg_businesses[1:]) if len(leg_businesses) > 1 else 0

    current_rank_name = u[0] if u else "None"

    next_rank_target = 0
    next_rank_name = "Max Rank Achieved"

    # Agar user ki rank "None" hai, toh seedha pehli rank ko next rank bana do
    if current_rank_name == "None" and RANKS:
        next_rank_target = RANKS[0]["target"]
        next_rank_name = RANKS[0]["name"]
    else:
        found = False
        for idx, r in enumerate(RANKS):
            if r["name"] == current_rank_name:
                if idx + 1 < len(RANKS):
                    next_rank_target = RANKS[idx + 1]["target"]
                    next_rank_name = RANKS[idx + 1]["name"]
                found = True
                break

    req_high_max = next_rank_target * 0.40
    if next_rank_target <= 0:
        req_high_max = 0

    req_other_min = next_rank_target * 0.60
    if next_rank_target <= 0:
        req_other_min = 0

    needed_total_biz = max(0, next_rank_target - team_biz)
    if next_rank_target <= 0:
        needed_total_biz = 0

    text = (
        f"🏆 <b>Ranks & Royalty Status</b>\n\n"
        f"<b>• Total Directs: <code>{directs_count}</code> (Active: <code>{active_directs}</code>)</b>\n"
        f"<b>• Direct Business: <code>{direct_biz:.2f} SOL</code></b>\n"
        f"<b>• Total Team Business: <code>{team_biz:.2f} SOL</code></b>\n"
        f"<b>• Current Rank: <code>{current_rank_name}</code></b>\n"
        f"<b>• Next Rank: <code>{next_rank_name}</code></b>\n\n"
        f"<b>🎯 Progress for Next Rank ({next_rank_target} SOL Target):</b>\n"
        f"<b>• Remaining Total Business: <code>{needed_total_biz:.2f} SOL</code></b>\n\n"
        f"<b>• 40:60 Ratio Check:</b>\n"
        f"<b> - Strongest Leg Max (40%): <code>{req_high_max:.2f}</code> SOL (Current: <code>{highest_leg:.2f}</code>)</b>\n"
        f"<b> - Other Legs Min (60%): <code>{req_other_min:.2f}</code> SOL (Current: <code>{other_legs_total:.2f}</code>)</b>\n\n"
    )
    bot.send_message(message.chat.id, text, parse_mode="HTML")

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
  markup.add(
    InlineKeyboardButton("❌ Close", callback_data="admin:close"),
  )
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
  users = conn.execute(
      "SELECT user_id, username, balance FROM users ORDER BY user_id"
  ).fetchall()
  conn.close()

  if not users:
    return ["<b>📋 ALL USERS</b>\n\nNo registered users found."]

  lines = [
      f"<b>📋 ALL USERS</b> <code>({len(users)} total)</code>\n",
      "<b>Telegram ID | Username | Balance</b>",
  ]
  for user_id, username, balance in users:
    display_username = f"@{username}" if username else "Not available"
    lines.append(
        f"<code>{user_id}</code> | "
        f"<code>{escape(display_username)}</code> | "
        f"<code>{balance:.4f} SOL</code>"
    )

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

    if not user:
        return None

    return (
        f"<b>👤 USER DETAILS</b>\n\n"
        f"<b>User ID:</b> <code>{user[0]}</code>\n"
        f"<b>Referrer ID:</b> <code>{user[1] or 'None'}</code>\n"
        f"<b>Balance:</b> <code>{user[2]:.4f} SOL</code>\n"
        f"<b>Investment:</b> <code>{user[3]:.4f} SOL</code>\n"
        f"<b>Total earned:</b> <code>{user[4]:.4f} SOL</code>\n"
        f"<b>Total withdrawn:</b> <code>{user[5]:.4f} SOL</code>\n"
        f"<b>Plan:</b> <code>{user['plan_name'] or 'None'}</code>\n"
        f"<b>Rank:</b> <code>{user[7] or 'None'}</code>\n"
        f"<b>Status:</b> <code>{user[8] or 'inactive'}</code>\n"
        f"<b>Active directs:</b> <code>{active_directs}</code>\n"
        f"<b>Direct business:</b> <code>{direct_business:.4f} SOL</code>"
    )

def record_admin_topup(admin_id, user_id, amount, note, is_paid=False):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    try:
        try:
            conn.execute('ALTER TABLE users ADD COLUMN plan_name TEXT')
            conn.execute('ALTER TABLE users ADD COLUMN max_cap REAL DEFAULT 0')
            conn.execute('ALTER TABLE users ADD COLUMN self_farming REAL DEFAULT 0')
        except sqlite3.OperationalError:
            pass

        existed = conn.execute(
            "SELECT 1 FROM users WHERE user_id=?", (user_id,)
        ).fetchone() is not None
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
        elif amount <= 1000.0:
            plan_name = "galaxy"
        else:
            plan_name = "starter"

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
        try:
            cursor.execute('ALTER TABLE admin_topups ADD COLUMN plan_name TEXT')
        except sqlite3.OperationalError:
            pass

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

        conn.commit()

        cursor.execute(
            "INSERT INTO admin_actions (admin_id, action, target_user_id, amount, note) VALUES (?, ?, ?, ?, ?)",
            (
                admin_id,
                "manual_topup_paid" if is_paid else "manual_topup_free",
                user_id,
                amount,
                note,
            ),
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
       f"<b>Amount:</b> <code>{amount:.8f} SOL</code>\n\n"
       f"<i>This credits balance and total earned only. It does not create an on-chain deposit, investment, or ROI plan.</i>\n"
       f"<i>A missing user ID will be created as a free ID.</i>",
       reply_markup=markup,
       parse_mode="HTML"
   )

def admin_lookup_user(message):
  if message.from_user.id != ADMIN_ID:
    return
  try:
    user_id = int(message.text.strip().split()[0])
    if user_id <= 0:
      raise ValueError
  except (ValueError, IndexError):
    bot.send_message(ADMIN_ID, "❌ <b>Invalid user ID.</b> Open /admin and try Manage User again.", parse_mode="HTML")
    return

  text = admin_user_text(user_id)
  if text is None:
    bot.send_message(
        ADMIN_ID,
        f"<b>User ID {user_id} does not exist yet.</b> Use <b>Top-up Free ID</b> if you want to create and credit it.",
        reply_markup=admin_panel_markup(),
        parse_mode="HTML",
    )
    return
  bot.send_message(ADMIN_ID, text, reply_markup=admin_user_markup(user_id), parse_mode="HTML")


def admin_topup_amount(message, user_id):
  if message.from_user.id != ADMIN_ID:
    return
  try:
    amount = float(message.text.strip().split()[0])
    if not math.isfinite(amount) or amount <= 0 or amount > 1000000:
      raise ValueError
  except (ValueError, IndexError):
    bot.send_message(ADMIN_ID, "❌ <b>Invalid amount.</b> Enter a positive SOL amount up to <code>1,000,000</code>.", parse_mode="HTML")
    return

def admin_free_topup(message):
  if message.from_user.id != ADMIN_ID:
      return
  parts = message.text.strip().split()
  try:
      user_id = int(parts[0])
      amount = float(parts[1])
      if user_id <= 0 or not math.isfinite(amount) or amount <= 0 or amount > 1000000:
          raise ValueError
  except (ValueError, IndexError):
      sent = bot.send_message(
          ADMIN_ID,
          "<b>❌ Invalid format.</b> Enter: <code>UserID Amount</code>\n<b>Example:</b> <code>123456789 0.50</code>",
          reply_markup=admin_panel_markup(),
          parse_mode="HTML"
      )
      bot.register_next_step_handler(sent, admin_free_topup)
      return
  queue_admin_topup(ADMIN_ID, user_id, amount, "Manual top-up from free ID panel")

def admin_paid_topup(message):
  if message.from_user.id != ADMIN_ID:
      return
  parts = message.text.strip().split()
  try:
      user_id = int(parts[0])
      amount = float(parts[1])
      if (user_id <= 0 or not math.isfinite(amount) 
              or amount <= 0 or amount > 1000000):
          raise ValueError
  except (ValueError, IndexError):
      sent = bot.send_message(
          ADMIN_ID,
          "<b>❌ Invalid format.</b> Use: <code>user_id amount</code> (e.g., <code>123456789 0.50</code>)",
          parse_mode="HTML"
      )
      bot.register_next_step_handler(sent, admin_paid_topup)
      return

  queue_admin_topup(ADMIN_ID, user_id, amount, "Manual top-up from paid ID panel", is_paid=True)

@bot.message_handler(commands=["admin"])
def admin_command(message):
  if message.from_user.id != ADMIN_ID:
    bot.send_message(message.chat.id, "❌ <b>Admin access only.</b>", parse_mode="HTML")
    return
  bot.send_message(
      message.chat.id,
      "<b>🛠 ADMIN PANEL</b>\nChoose an action:",
      reply_markup=admin_panel_markup(),
      parse_mode="HTML",
  )

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("admin:"))
def admin_callback(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Admin access only.", show_alert=True)
        return

    parts = call.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "panel":
        bot.send_message(
            call.message.chat.id,
            "<b>🛠️ ADMIN PANEL</b>\nChoose an action:",
            reply_markup=admin_panel_markup(),
            parse_mode="HTML"
        )
    elif action == "stats":
        bot.send_message(
            call.message.chat.id,
            admin_stats_text(),
            reply_markup=admin_panel_markup(),
            parse_mode="HTML"
        )
    elif action == "list_users":
        messages = admin_user_list_messages()
        for index, text in enumerate(messages):
            bot.send_message(
                call.message.chat.id,
                text,
                reply_markup=admin_panel_markup() if index == len(messages) - 1 else None,
                parse_mode="HTML"
            )
    elif action == "manage_user":
        sent = bot.send_message(
            call.message.chat.id,
            "<b>Send the user ID to inspect:</b>",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(sent, admin_lookup_user)
    elif action == "topup_free":
        sent = bot.send_message(
            call.message.chat.id,
            "<b>Send the free ID and amount separated by a space.</b>\n<b>Example:</b> <code>123456789 0.50</code>",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(sent, admin_free_topup)
    elif action == "topup_paid":
        sent = bot.send_message(
            call.message.chat.id,
            "<b>Send the paid ID and amount separated by a space.</b>\n<b>Example:</b> <code>123456789 0.50</code>",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(sent, admin_paid_topup)
    elif action == "user":
        try:
            user_id = int(parts[2])
        except (ValueError, IndexError):
            bot.send_message(
                call.message.chat.id,
                "❌ <b>Invalid user selection.</b>",
                reply_markup=admin_panel_markup(),
                parse_mode="HTML"
            )
            return

        text = admin_user_text(user_id)
        if text is None:
            bot.send_message(
                call.message.chat.id,
                "❌ <b>User not found.</b>",
                reply_markup=admin_panel_markup(),
                parse_mode="HTML"
            )
        else:
            bot.send_message(
                call.message.chat.id,
                text,
                reply_markup=admin_user_markup(user_id),
                parse_mode="HTML"
            )
    elif action == "user_topup":
        try:
            user_id = int(parts[2])
        except (ValueError, IndexError):
            bot.send_message(
                call.message.chat.id,
                "❌ <b>Invalid user selection.</b>",
                reply_markup=admin_panel_markup(),
                parse_mode="HTML"
            )
            return

        sent = bot.send_message(
            call.message.chat.id,
            f"<b>Enter the SOL amount to top up for user {user_id}:</b>",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(sent, admin_topup_amount, user_id)
    elif action == "confirm_topup":
        token = parts[2] if len(parts) > 2 else ""
        pending = ADMIN_PENDING_TOPUPS.get(token)
        if not pending or pending["admin_id"] != call.from_user.id:
            bot.send_message(
                call.message.chat.id,
                "⚠️ <b>This top-up request is expired or already processed.</b>",
                reply_markup=admin_panel_markup(),
                parse_mode="HTML"
            )
            return

        t_type = pending.get("type", "manual")

        existed = record_admin_topup(call.from_user.id, pending["user_id"], float(pending["amount"]), t_type, pending.get("is_paid", False))
        ADMIN_PENDING_TOPUPS.pop(token, None)
        c_text = "existing user" if existed else "new free ID created"
        bot.send_message(
            call.message.chat.id,
            f"✅ <b>Top-up complete.</b>\n\nUser ID: {pending['user_id']}\nAmount: {pending['amount']:.8f} SOL\nTarget: {c_text}",
            parse_mode="HTML"
        )
        try:
            bot.send_message(
                pending["user_id"],
                f"✅ <b>An admin credited</b> <code>{pending['amount']:.8f} SOL</code> <b>to your self farming.</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass
    elif action == "cancel_topup":
        token = parts[2] if len(parts) > 2 else ""
        ADMIN_PENDING_TOPUPS.pop(token, None)
        bot.send_message(
            call.message.chat.id,
            "❌ <b>Top-up cancelled.</b>",
            reply_markup=admin_panel_markup(),
            parse_mode="HTML"
        )
    elif action == "close":
        try:
            bot.edit_message_text(
                "<b>Admin panel closed.</b>",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML"
            )
        except Exception:
            bot.send_message(
                call.message.chat.id,
                "<b>Admin panel closed.</b>",
                parse_mode="HTML"
            )

@bot.message_handler(commands=['dashboard'])
@bot.message_handler(func=lambda m: m.text and "Dashboard" in m.text)
def dashboard_handler(message):
    print(">>> DASHBOARD CLICKED OR COMMAND USED! <<<")
    user_id = message.from_user.id

    try:
        conn = get_db()
        cursor = conn.cursor()

        # Automatically ensure all income and bonus columns exist to prevent DB errors
        columns_to_add = [
            "self_farming_bonus REAL DEFAULT 0.0",
            "direct_referral_bonus REAL DEFAULT 0.0",
            "team_referral_bonus REAL DEFAULT 0.0",
            "team_farming_override_bonus REAL DEFAULT 0.0",
            "rank_royalty_bonus REAL DEFAULT 0.0",
            "total_withdrawn REAL DEFAULT 0.0",
            "current_rank TEXT DEFAULT 'None'",
            "active_plan TEXT DEFAULT 'None'",

        ]
        for col in columns_to_add:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col}")
            except Exception:
                pass
        conn.commit()

        # Fetch all required fields including team_referral_bonus
        cursor.execute("""
            SELECT balance, self_farming, self_farming_bonus, 
                   direct_referral_bonus, team_referral_bonus, 
                   team_farming_override_bonus, rank_royalty_bonus, 
                   total_earned, total_withdrawn, active_plan, current_rank 
            FROM users WHERE user_id = ?
        """, (user_id,))

        user = cursor.fetchone()
        conn.close()
        print(">>> DEBUG USER DATA FROM DB:", user)
    except Exception as e:
        print(f"DB Error: {e}")
        user = None

    if not user:
        balance = self_farming = self_bonus = direct_ref = team_ref = team_override = royalty = earned = withdrawn = 0.0
        active_plan = "None"
        current_rank = "None"
    else:
        balance = user[0] if len(user) > 0 and user[0] is not None else 0.0
        self_farming = user[1] if len(user) > 1 and user[1] is not None else 0.0
        self_bonus = user[2] if len(user) > 2 and user[2] is not None else 0.0
        direct_ref = user[3] if len(user) > 3 and user[3] is not None else 0.0
        team_ref = user[4] if len(user) > 4 and user[4] is not None else 0.0
        team_override = user[5] if len(user) > 5 and user[5] is not None else 0.0
        royalty = user[6] if len(user) > 6 and user[6] is not None else 0.0
        earned = user[7] if len(user) > 7 and user[7] is not None else 0.0
        withdrawn = user[8] if len(user) > 8 and user[8] is not None else 0.0
        active_plan = user[9] if len(user) > 9 and user[9] is not None else "None"
        current_rank = user[10] if len(user) > 10 and user[10] is not None else "None"

    # Calculate available withdrawal limit
    has_ref = has_direct_referral(conn, user_id) if 'conn' in locals() else False
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
        f"📈 <b>Total Earned:</b> <code>{earned:.4f} SOL</code> (Max Cap: {max_cap:.2f} SOL)\n\n"
        f"🧁 <b>Total Withdrawals:</b> <code>{withdrawn:.4f} SOL</code>\n"
        f"🎯 <b>Available Withdrawal Limit:</b> <code>{available_limit:.4f} SOL</code>\n\n"
        f"📦 <b>Active Plan:</b> {active_plan}\n"
        f"🏆 <b>Current Rank:</b> {current_rank}"
    )

    bot.send_message(message.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and "Withdraw" in m.text)
def withdraw_request_start(message):
    conn = get_db()
    u = conn.execute("SELECT balance FROM users WHERE user_id=?", (message.from_user.id,)).fetchone()
    conn.close()

    bal = u[0] if u else 0
    if bal < 0.01:
        bot.send_message(message.chat.id, "❌ <b>Minimum withdrawal limit is</b> <code>0.01 SOL</code>.", parse_mode="HTML")
        return

    msg = bot.send_message(message.chat.id, f"💰 <b>Available Balance:</b> <code>{bal:.4f} SOL</code>\n\nPlease enter your withdrawal amount:", parse_mode="HTML")
    bot.register_next_step_handler(msg, process_withdrawal_amount)

def process_withdrawal_amount(message):
    try:
        amount = float(message.text)
    except ValueError:
        bot.send_message(message.chat.id, "❌ Please enter a valid number. Click 'Withdraw' again.")
        return

    user_id = message.from_user.id
    conn = get_db()
    u = conn.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()

    bal = u[0] if u else 0
    if amount < 0.01:
        bot.send_message(message.chat.id, "❌ Minimum withdrawal is 0.01 SOL.")
        return
    if amount > bal:
        bot.send_message(message.chat.id, "❌ Entered amount exceeds your available balance.")
        return

    msg = bot.send_message(message.chat.id, f"You have entered <b>{amount} SOL</b>.\n\nPlease enter your Solana <b>Wallet Address</b>:", parse_mode="HTML")
    bot.register_next_step_handler(msg, process_withdrawal_address, amount)

def process_withdrawal_address(message, amount):
    wallet_address = message.text.strip()
    user_id = message.from_user.id

    conn = get_db()
    u = conn.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
    bal = u[0] if u else 0

    if amount > bal:
        conn.close()
        bot.send_message(message.chat.id, "❌ Insufficient balance.")
        return

    conn.close()

    # 10% fee calculation
    fee = amount * 0.10
    net_amount = amount - fee

    bot.send_message(
        message.chat.id, 
        f"✅ Your withdrawal request for <b>{amount} SOL</b> has been submitted!\n\n• Requested: <code>{amount} SOL</code>\n• Fee (10%): <code>{fee:.4f} SOL</code>\n• Net Payable: <code>{net_amount:.4f} SOL</code>", 
        parse_mode="HTML"
    )

    # Send notification to admin with fee details
    bot.send_message(
        ADMIN_ID,
        f"🚨 <b>Withdrawal Request (10% Fee Applied)</b>\n\n• User ID: <code>{user_id}</code>\n• Requested Amount: <code>{amount} SOL</code>\n• Fee (10%): <code>{fee:.4f} SOL</code>\n• Net Pay to User: <code>{net_amount:.4f} SOL</code>\n• Wallet: <code>{wallet_address}</code>\n\nTo approve and pay, use command:\n<code>/pay {user_id} {amount}</code>",
        parse_mode="HTML"
    )

@bot.message_handler(commands=["pay"])
def admin_pay(message):
  if message.from_user.id == ADMIN_ID:
    try:
      args = message.text.split()
      uid, amt = int(args[1]), float(args[2])
      conn = get_db()
      conn.execute("UPDATE users SET balance = balance - ?, total_withdrawn = total_withdrawn + ? WHERE user_id = ?", (amt, amt, uid))
      conn.commit()
      conn.close()
      bot.send_message(uid, f"📤 <b>Withdrawal Processed:</b> <code>{amt} SOL</code> has been sent!", parse_mode="HTML")
      bot.send_message(ADMIN_ID, "✅ <b>Paid and database updated.</b>", parse_mode="HTML")
    except Exception as e:
      bot.send_message(
          ADMIN_ID,
          f"<b>Format:</b> <code>/pay UserID Amount</code>\n<b>Error:</b> <code>{escape(str(e))}</code>",
          parse_mode="HTML",
      )


# --- ROI & 25-LEVEL OVERRIDE BACKGROUND WORKER ---
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
                            "UPDATE users SET balance = balance + ?, total_earned = total_earned + ?, self_farming_bonus = self_farming_bonus + ? WHERE user_id=?",
                            (total_payout, total_payout, roi, uid),
                        )
                        conn.commit()

                        # --- 25-LEVEL OVERRIDE BONUS ---
                        curr = uid
                        for level_idx, pct in enumerate(OVERRIDE_LEVELS):
                            res = conn.execute("SELECT referrer_id FROM users WHERE user_id=?", (curr,)).fetchone()
                            if res and res[0]:
                                ref_id = res[0]
                                if level_idx == 0:
                                    required_direct_biz = 0.0
                                else:
                                    required_direct_biz = float(level_idx + 1)

                                actual_direct_biz = get_user_direct_business(conn, ref_id)
                                if actual_direct_biz >= required_direct_biz:
                                    override_bonus = roi * pct
                                    conn.execute(
                                        "UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ?",
                                        (override_bonus, override_bonus, ref_id)
                                    )
                                    conn.commit()
                                curr = ref_id
                            else:
                                break

                        # Check if max cap reached after payout
                        if (earned + total_payout) >= max_allowed_earn:
                            conn.execute(
                                "UPDATE users SET status='retopup_required', plan_name=NULL WHERE user_id=?",
                                (uid,)
                            )
                            conn.commit()

            conn.close()
            print("ROI worker cycle completed. Sleeping now...")
        except Exception as e:
            print(f">>> DEBUG: ROI Worker Error -> {e}")

        time.sleep(86400)

@bot.message_handler(func=lambda m: m.text == "🔗 Referral Link")
def referral_link_handler(message):
    bot_username = bot.get_me().username
    user_id = message.from_user.id

    text = (
        f"<b>🔗 Your Referral Link</b>\n\n"
        f"Share this link with your friends to invite them to the bot:\n"
        f"<code>https://t.me/{bot_username}?start={user_id}</code>"
    )
    bot.send_message(message.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "👥 Team Members")
def my_team_handler(message):
    conn = get_db()
    user_id = message.from_user.id

    # Recursive query to fetch downline members up to 25 levels
    query = """
    WITH RECURSIVE downline(user_id, self_farming, level) AS (
        SELECT user_id, COALESCE(self_farming, 0), 1 AS level
        FROM users
        WHERE referrer_id = ?

        UNION ALL

        SELECT u.user_id, COALESCE(u.self_farming, 0), d.level + 1
        FROM users u
        JOIN downline d ON u.referrer_id = d.user_id
        WHERE d.level < 25
    )
    SELECT user_id, self_farming, level FROM downline;
    """

    team_data = conn.execute(query, (user_id,)).fetchall()
    conn.close()

    if not team_data:
        bot.send_message(message.chat.id, "👥 You don't have any team members yet.", parse_mode="HTML")
        return

    total_members = len(team_data)

    # Level-wise count and business calculation
    level_counts = {}
    level_business = {}
    for uid, sf, lvl in team_data:
        level_counts[lvl] = level_counts.get(lvl, 0) + 1
        level_business[lvl] = level_business.get(lvl, 0.0) + sf

        team_text = f"<b>👥 Your 25-Level Team Overview</b>\n\n"
        team_text += f"<b>• Total Team Members:</b> <code>{total_members}</code>\n\n"
        team_text += "<b>Click on the levels below to view member details:</b>"

        # Inline buttons banayein
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = []

        for lvl in sorted(level_counts.keys()):
            if lvl <= 25:
                count = level_counts[lvl]
                buttons.append(types.InlineKeyboardButton(f"Lvl {lvl} ({count})", callback_data=f"view_lvl_{lvl}"))

        for i in range(0, len(buttons), 3):
            markup.add(*buttons[i:i+3])

        bot.send_message(message.chat.id, team_text, reply_markup=markup, parse_mode="HTML")


    # Callback Handler jab user kisi level ke button par click karega
    @bot.callback_query_handler(func=lambda call: call.data.startswith("view_lvl_"))
    def callback_view_level(call):
        target_level = int(call.data.split("_")[2])
        user_id = call.from_user.id

        conn = get_db()
        query = """
        WITH RECURSIVE downline(user_id, self_farming, level) AS (
            SELECT user_id, COALESCE(self_farming, 0), 1 AS level
            FROM users
            WHERE referrer_id = ?

            UNION ALL

            SELECT u.user_id, COALESCE(u.self_farming, 0), d.level + 1
            FROM users u
            JOIN downline d ON u.referrer_id = d.user_id
            WHERE d.level < 25
        )
        SELECT user_id, self_farming FROM downline WHERE level = ?;
        """

        members = conn.execute(query, (user_id, target_level)).fetchall()
        conn.close()

        if not members:
            bot.answer_callback_query(call.id, f"No members found at Level {target_level}.", show_alert=True)
            return

        text = f"<b>👥 Level {target_level} Members List:</b>\n\n"
        for idx, (uid, sf) in enumerate(members, 1):
            text += f"{idx}. ID: <code>{uid}</code> | Farming: <code>{sf:.2f} SOL</code>\n"

        if len(text) > 4096:
            text = text[:4000] + "\n\n<i>(List is too long...)</i>"

        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, text, parse_mode="HTML")
@bot.message_handler(func=lambda m: m.text == "💰 Deposit SOL")
def deposit_sol(message):
    wallet_address = ADMIN_WALLET  

    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={wallet_address}"

    caption = (
        f"💰 <b>Deposit SOL</b>\n\n"
        f"Please scan the QR code above or copy the address below to deposit SOL:\n\n"
        f"<code>{wallet_address}</code>\n\n"
        f"⚠️ <i>Send only SOL to this address.</i>\n\n"
        f"📝 <i>After sending, please send your Transaction Hash (TxID) here to activate your ID!</i>"
    )

    bot.send_photo(
        message.chat.id,
        photo=qr_url,
        caption=caption,
        parse_mode="HTML"
    )
if __name__ == "__main__":
    # Force fix: Drop and recreate or ensure columns in admin_topups
    try:
        conn = sqlite3.connect('Solana_farming.db')
        cursor = conn.cursor()

        # Check if table exists, if so check columns, or safely recreate if structure mismatch
        cursor.execute("PRAGMA table_info(admin_topups);")
        columns = [info[1] for info in cursor.fetchall()]

        if not columns:
            cursor.execute('''
                CREATE TABLE admin_topups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    amount REAL,
                    plan_name TEXT,
                    timestamp DATETIME
                )
            ''')
        else:
            if 'plan_name' not in columns:
                cursor.execute('ALTER TABLE admin_topups ADD COLUMN plan_name TEXT')

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database setup error: {e}")

    Thread(target=roi_worker, daemon=True).start()
    print("Solana Farming Bot is running with Condition-Free Level 1 Override...")

    while True:
        try:
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            print(f"Polling error encountered: {e}. Retrying in 5 seconds...")
            time.sleep(5)

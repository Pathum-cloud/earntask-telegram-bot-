import os, asyncio, logging
from decimal import Decimal
from dotenv import load_dotenv
import asyncpg
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
                           ReplyKeyboardMarkup, KeyboardButton, WebAppInfo)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import FastAPI
import uvicorn

load_dotenv()
logging.basicConfig(level=logging.INFO)
BOT_TOKEN=os.environ["BOT_TOKEN"]
ADMIN_ID=int(os.environ["ADMIN_ID"])
DATABASE_URL=os.environ["DATABASE_URL"]
CHANNELS=[os.getenv("CHANNEL_1",""), os.getenv("CHANNEL_2","")]
BASE=os.getenv("PUBLIC_BASE_URL","").rstrip("/")
PAY_ADDR=os.getenv("USDT_BEP20_ADDRESS","0x52824938de138886fdf6f7a80262e5c0a173d92c")
PRICE_LOW=Decimal(os.getenv("TASK_PRICE_UNDER_2000","4.00"))
PRICE_HIGH=Decimal(os.getenv("TASK_PRICE_OVER_2000","6.00"))
REF_REWARD=Decimal(os.getenv("REFERRAL_REWARD","0.02"))
AD_REWARD=Decimal(os.getenv("AD_REWARD","0.05"))
DAILY_AD_LIMIT=int(os.getenv("DAILY_AD_LIMIT","30"))
JOIN_TOTAL=Decimal(os.getenv("JOIN_TASK_TOTAL","0.01"))
USER_SHARE=Decimal(os.getenv("USER_SHARE","0.30"))

bot=Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp=Dispatcher()
db=None
app=FastAPI()

MENU=ReplyKeyboardMarkup(keyboard=[
 [KeyboardButton(text="👥 Referrals"),KeyboardButton(text="📋 Tasks")],
 [KeyboardButton(text="📺 Watch Ads & Earn"),KeyboardButton(text="👤 Profile")],
 [KeyboardButton(text="➕ Add Your Task")]
], resize_keyboard=True)

async def init_db():
 global db
 db=await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
 async with db.acquire() as c:
  await c.execute("""
  CREATE TABLE IF NOT EXISTS users(
   id BIGINT PRIMARY KEY, username TEXT, referred_by BIGINT, referrals INTEGER NOT NULL DEFAULT 0,
   balance NUMERIC(14,6) NOT NULL DEFAULT 0, joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
   blocked BOOLEAN NOT NULL DEFAULT false);
  CREATE TABLE IF NOT EXISTS task_requests(
   id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, title TEXT NOT NULL, target_url TEXT NOT NULL,
   members INTEGER NOT NULL, txid TEXT, amount NUMERIC(12,2) NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
   created_at TIMESTAMPTZ NOT NULL DEFAULT now());
  CREATE TABLE IF NOT EXISTS tasks(
   id BIGSERIAL PRIMARY KEY, title TEXT NOT NULL, target_url TEXT NOT NULL, reward NUMERIC(12,6) NOT NULL,
   kind TEXT NOT NULL DEFAULT 'join', active BOOLEAN NOT NULL DEFAULT true);
  CREATE TABLE IF NOT EXISTS task_completions(
   user_id BIGINT NOT NULL, task_id BIGINT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
   PRIMARY KEY(user_id,task_id));
  CREATE TABLE IF NOT EXISTS withdrawals(
   id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, amount NUMERIC(14,6) NOT NULL, wallet TEXT NOT NULL,
   status TEXT NOT NULL DEFAULT 'pending', created_at TIMESTAMPTZ NOT NULL DEFAULT now());
  CREATE TABLE IF NOT EXISTS ad_views(
   user_id BIGINT NOT NULL, day DATE NOT NULL DEFAULT CURRENT_DATE, count INTEGER NOT NULL DEFAULT 0,
   PRIMARY KEY(user_id,day));
  CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
  """)

async def is_member(uid:int, chat:str)->bool:
 if not chat: return False
 try:
  m=await bot.get_chat_member(chat,uid)
  return m.status in ("creator","administrator","member")
 except Exception:
  return False

async def gate(uid:int)->bool:
 return all([await is_member(uid,c) for c in CHANNELS])

def gate_kb():
 b=InlineKeyboardBuilder()
 for i,ch in enumerate(CHANNELS,1):
  if ch: b.button(text=f"Join Channel {i}", url=f"https://t.me/{ch.lstrip('@')}")
 b.button(text="✅ I Joined — Check", callback_data="check_join")
 b.adjust(1)
 return b.as_markup()

async def ensure_user(m:Message, refid:int|None=None):
 async with db.acquire() as c:
  old=await c.fetchrow("SELECT id FROM users WHERE id=$1",m.from_user.id)
  if old: 
   await c.execute("UPDATE users SET username=$2 WHERE id=$1",m.from_user.id,m.from_user.username)
   return
  valid_ref=None
  if refid and refid != m.from_user.id:
   exists=await c.fetchrow("SELECT id FROM users WHERE id=$1 AND blocked=false",refid)
   if exists: valid_ref=refid
  await c.execute("INSERT INTO users(id,username,referred_by) VALUES($1,$2,$3)",m.from_user.id,m.from_user.username,valid_ref)
  if valid_ref:
   await c.execute("UPDATE users SET referrals=referrals+1,balance=balance+$2 WHERE id=$1",valid_ref,REF_REWARD)

@dp.message(Command("id"))
async def myid(m:Message): await m.answer(f"Your Telegram ID: <code>{m.from_user.id}</code>")

@dp.message(CommandStart())
async def start(m:Message):
 ref=None
 parts=(m.text or "").split(maxsplit=1)
 if len(parts)>1 and parts[1].startswith("ref_"):
  try: ref=int(parts[1][4:])
  except ValueError: pass
 await ensure_user(m,ref)
 if not await gate(m.from_user.id):
  await m.answer("Please join both required channels before using the bot.",reply_markup=gate_kb())
 else:
  await m.answer("👋 Welcome! Earn tasks, referrals and verified ads rewards.",reply_markup=MENU)

@dp.callback_query(F.data=="check_join")
async def check_join(q:CallbackQuery):
 if await gate(q.from_user.id):
  await q.message.edit_text("✅ Membership verified. You can now use the bot.")
  await q.message.answer("Main menu:",reply_markup=MENU)
 else: await q.answer("You have not joined both channels yet. Please join them and check again.",show_alert=True)

@dp.message(F.text=="👥 Referrals")
async def referrals(m:Message):
 if not await gate(m.from_user.id): return await m.answer("Please join both required channels first.",reply_markup=gate_kb())
 me=await bot.get_me()
 async with db.acquire() as c:
  r=await c.fetchrow("SELECT referrals,balance FROM users WHERE id=$1",m.from_user.id)
 await m.answer(f"👥 Qualified referrals: <b>{r['referrals']}</b>\\nReward per referral: <b>${REF_REWARD}</b>\\nYour invite link:\\n<code>https://t.me/{me.username}?start=ref_{m.from_user.id}</code>")

@dp.message(F.text=="➕ Add Your Task")
async def add_task(m:Message):
 if not await gate(m.from_user.id): return await m.answer("Please join both required channels first.",reply_markup=gate_kb())
 await m.answer(f"➕ <b>Add Your Task</b>\\n\\nSubmit your task using this format:\\n<code>/task Title | https://example.com | members</code>\\n\\n≤ 2,000 members: <b>${PRICE_LOW}</b>\\nMore than 2,000 members: <b>${PRICE_HIGH}</b> (unlimited targeting)\\n\\nPayment method: USDT BEP20\\n<code>{PAY_ADDR}</code>\\n\\nAfter submitting, send the transaction ID (TxID). An admin will manually verify the blockchain transfer. A TxID alone is not proof of payment.")

@dp.message(Command("task"))
async def task_cmd(m:Message):
 await ensure_user(m)
 raw=(m.text or "").partition(" ")[2]
 bits=[x.strip() for x in raw.split("|")]
 if len(bits)!=3:
  return await m.answer("Format: <code>/task Title | https://example.com | members</code>")
 title,url,n=bits
 if not url.startswith(("https://","http://")): return await m.answer("Please provide a valid HTTP or HTTPS URL.")
 try: members=int(n)
 except ValueError: return await m.answer("The member count must be a number.")
 if members<1: return await m.answer("The member count must be at least 1.")
 amount=PRICE_LOW if members<=2000 else PRICE_HIGH
 async with db.acquire() as c:
  row=await c.fetchrow("INSERT INTO task_requests(user_id,title,target_url,members,amount) VALUES($1,$2,$3,$4,$5) RETURNING id",m.from_user.id,title,url,members,amount)
 await m.answer(f"Request #{row['id']} created. Pay <b>${amount} USDT</b> to\\n<code>{PAY_ADDR}</code>\\nThen send <code>/tx {row['id']} YOUR_TXID</code>. The task will not go live until an admin verifies the payment.")

@dp.message(Command("tx"))
async def tx_cmd(m:Message):
 parts=(m.text or "").split(maxsplit=2)
 if len(parts)!=3: return await m.answer("Format: /tx REQUEST_ID TXID")
 try: rid=int(parts[1])
 except ValueError: return await m.answer("Invalid request ID.")
 async with db.acquire() as c:
  r=await c.fetchrow("UPDATE task_requests SET txid=$3 WHERE id=$1 AND user_id=$2 AND status='pending' RETURNING *",rid,m.from_user.id,parts[2])
 if not r: return await m.answer("Pending request not found.")
 kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Approve",callback_data=f"taskok:{rid}"),InlineKeyboardButton(text="❌ Reject",callback_data=f"taskno:{rid}")]])
 await bot.send_message(ADMIN_ID,f"🧾 <b>Task payment review #{rid}</b>\\nUser: <code>{r['user_id']}</code>\\nTitle: {r['title']}\\nMembers: {r['members']}\\nAmount: ${r['amount']}\\nTxID: <code>{r['txid']}</code>\\nURL: {r['target_url']}\\nVerify on BscScan before approve.",reply_markup=kb)
 await m.answer("Your TxID was sent to the admin. Please wait while the payment is verified on the blockchain.")

@dp.callback_query(F.data.startswith("taskok:"))
async def task_approve(q:CallbackQuery):
 if q.from_user.id!=ADMIN_ID: return await q.answer("Admin only",show_alert=True)
 rid=int(q.data.split(":")[1])
 async with db.acquire() as c:
  r=await c.fetchrow("UPDATE task_requests SET status='approved' WHERE id=$1 AND status='pending' RETURNING *",rid)
  if r: await c.execute("INSERT INTO tasks(title,target_url,reward,kind) VALUES($1,$2,$3,'join')",r['title'],r['target_url'],JOIN_TOTAL*USER_SHARE)
 if r:
  await bot.send_message(r['user_id'],f"✅ Task request #{rid} approved and published.")
  await q.message.edit_reply_markup(reply_markup=None); await q.answer("Approved")
 else: await q.answer("Already handled or not found",show_alert=True)

@dp.callback_query(F.data.startswith("taskno:"))
async def task_reject(q:CallbackQuery):
 if q.from_user.id!=ADMIN_ID: return await q.answer("Admin only",show_alert=True)
 rid=int(q.data.split(":")[1])
 async with db.acquire() as c:
  r=await c.fetchrow("UPDATE task_requests SET status='rejected' WHERE id=$1 AND status='pending' RETURNING *",rid)
 if r: await bot.send_message(r['user_id'],f"❌ Task request #{rid} was rejected. Contact admin about refunds."); await q.message.edit_reply_markup(reply_markup=None)
 await q.answer("Rejected")

@dp.message(F.text=="📋 Tasks")
async def tasks_menu(m:Message):
 await list_tasks(m)

@dp.message(F.text=="📺 Watch Ads & Earn")
async def ads(m:Message):
 if not await gate(m.from_user.id): return await m.answer("Please join both required channels first.",reply_markup=gate_kb())
 if not BASE: return await m.answer("The admin has not configured the Web App URL yet.")
 await m.answer(f"📺 Watch Ads & Earn\\nReward: ${AD_REWARD} per verified ad; max {DAILY_AD_LIMIT}/day.\\nYour balance will not be credited until the ad provider verifies completion on the server.",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Open Ad Page",web_app=WebAppInfo(url=f"{BASE}/ad?uid={m.from_user.id}"))]]))

@dp.message(F.text=="👤 Profile")
async def profile(m:Message):
 if not await gate(m.from_user.id): return await m.answer("Please join both required channels first.",reply_markup=gate_kb())
 async with db.acquire() as c:
  u=await c.fetchrow("SELECT balance,referrals FROM users WHERE id=$1",m.from_user.id)
 await m.answer(f"👤 <b>Profile</b>\\nBalance: <b>${u['balance']:.6f}</b>\\nQualified referrals: <b>{u['referrals']}</b>\\n\\nWithdraw: <code>/withdraw amount | YOUR_USDT_BEP20_ADDRESS</code>\\nMinimum $1 + at least 5 qualified referrals.")

@dp.message(Command("withdraw"))
async def withdraw(m:Message):
 parts=(m.text or "").partition(" ")[2].split("|",1)
 if len(parts)!=2: return await m.answer("Format: <code>/withdraw 1.00 | 0xYourBEP20Address</code>")
 try: amount=Decimal(parts[0].strip())
 except Exception: return await m.answer("Invalid amount.")
 wallet=parts[1].strip()
 if amount<Decimal("1"): return await m.answer("Minimum withdraw is $1.")
 if not wallet.startswith("0x") or len(wallet)!=42: return await m.answer("Enter a valid USDT BEP20 wallet address: 0x followed by 40 hexadecimal characters.")
 async with db.acquire() as c:
  async with c.transaction():
   u=await c.fetchrow("SELECT balance,referrals FROM users WHERE id=$1 FOR UPDATE",m.from_user.id)
   if not u or u['referrals']<5: return await m.answer("You need at least 5 qualified referrals to withdraw.")
   if Decimal(u['balance'])<amount: return await m.answer("Insufficient balance.")
   await c.execute("UPDATE users SET balance=balance-$2 WHERE id=$1",m.from_user.id,amount)
   w=await c.fetchrow("INSERT INTO withdrawals(user_id,amount,wallet) VALUES($1,$2,$3) RETURNING id",m.from_user.id,amount,wallet)
 kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Accept",callback_data=f"wdok:{w['id']}"),InlineKeyboardButton(text="❌ Reject",callback_data=f"wdno:{w['id']}")]])
 await bot.send_message(ADMIN_ID,f"💸 <b>Withdrawal #{w['id']}</b>\\nUser: <code>{m.from_user.id}</code>\\nAmount: ${amount}\\nQualified referrals: {u['referrals']}\\nWallet: <code>{wallet}</code>",reply_markup=kb)
 await m.answer(f"Withdrawal #{w['id']} pending admin review.")

@dp.callback_query(F.data.startswith("wdok:"))
async def wd_accept(q:CallbackQuery):
 if q.from_user.id!=ADMIN_ID: return await q.answer("Admin only",show_alert=True)
 wid=int(q.data.split(":")[1])
 async with db.acquire() as c: r=await c.fetchrow("UPDATE withdrawals SET status='accepted' WHERE id=$1 AND status='pending' RETURNING *",wid)
 if r:
  await bot.send_message(r['user_id'],f"Withdrawal #{wid} accepted. Admin will send USDT manually.")
  await q.message.edit_reply_markup(reply_markup=None)
 await q.answer("Accepted")

@dp.callback_query(F.data.startswith("wdno:"))
async def wd_reject(q:CallbackQuery):
 if q.from_user.id!=ADMIN_ID: return await q.answer("Admin only",show_alert=True)
 wid=int(q.data.split(":")[1])
 async with db.acquire() as c:
  r=await c.fetchrow("UPDATE withdrawals SET status='rejected' WHERE id=$1 AND status='pending' RETURNING *",wid)
  if r: await c.execute("UPDATE users SET balance=balance+$2 WHERE id=$1",r['user_id'],r['amount'])
 if r:
  await bot.send_message(r['user_id'],f"Withdrawal #{wid} rejected; amount returned to balance.")
  await q.message.edit_reply_markup(reply_markup=None)
 await q.answer("Rejected")

@dp.message(Command("addtask"))
async def admin_add_task(m:Message):
 if m.from_user.id!=ADMIN_ID: return await m.answer("Not allowed.")
 bits=(m.text or "").partition(" ")[2].split("|")
 bits=[x.strip() for x in bits]
 if len(bits)!=3: return await m.answer("Format: /addtask Title | https://t.me/group | 0.01")
 try: reward=Decimal(bits[2])
 except Exception: return await m.answer("Reward must be a number.")
 if not bits[1].startswith("https://"): return await m.answer("URL must use https.")
 async with db.acquire() as c: r=await c.fetchrow("INSERT INTO tasks(title,target_url,reward,kind) VALUES($1,$2,$3,'join') RETURNING id",bits[0],bits[1],reward)
 await m.answer(f"Free task #{r['id']} added (admin-only command).")

@dp.message(Command("tasks"))
async def list_tasks(m:Message):
 if not await gate(m.from_user.id): return await m.answer("Join channels first.",reply_markup=gate_kb())
 async with db.acquire() as c: rows=await c.fetch("SELECT * FROM tasks WHERE active=true ORDER BY id DESC LIMIT 15")
 if not rows: return await m.answer("There are no tasks available right now.")
 b=InlineKeyboardBuilder()
 for t in rows: b.button(text=f"#{t['id']} {t['title']} — ${t['reward']}",callback_data=f"do:{t['id']}")
 b.adjust(1)
 await m.answer("Available join tasks:",reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("do:"))
async def do_task(q:CallbackQuery):
 if not await gate(q.from_user.id): return await q.answer("Join channels first",show_alert=True)
 tid=int(q.data.split(":")[1])
 async with db.acquire() as c: t=await c.fetchrow("SELECT * FROM tasks WHERE id=$1 AND active=true",tid)
 if not t: return await q.answer("Task unavailable",show_alert=True)
 await q.message.answer(f"Task: <b>{t['title']}</b>\\nJoin: {t['target_url']}\\nAfter joining, tap the Verify button.",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔎 Verify join",callback_data=f"verify:{tid}")]]))
 await q.answer()

@dp.callback_query(F.data.startswith("verify:"))
async def verify_task(q:CallbackQuery):
 tid=int(q.data.split(":")[1])
 async with db.acquire() as c:
  t=await c.fetchrow("SELECT * FROM tasks WHERE id=$1 AND active=true",tid)
  if not t: return await q.answer("Task unavailable",show_alert=True)
  # The bot must be a member/admin of the target chat to reliably verify membership.
  target=t['target_url'].rstrip('/').split('/')[-1]
  chat="@"+target
  try:
   member=await bot.get_chat_member(chat,q.from_user.id)
   ok=member.status in ("creator","administrator","member")
  except Exception: ok=False
  if not ok: return await q.answer("Could not verify membership. Join the group and try again.",show_alert=True)
  try: await c.execute("INSERT INTO task_completions(user_id,task_id) VALUES($1,$2)",q.from_user.id,tid)
  except asyncpg.UniqueViolationError: return await q.answer("You have already received a reward for this task.",show_alert=True)
  await c.execute("UPDATE users SET balance=balance+$2 WHERE id=$1",q.from_user.id,t['reward'])
 await q.answer("Verified! Reward credited.",show_alert=True)
 await q.message.answer(f"✅ Membership verified. ${t['reward']} credited.")

@dp.message()
async def fallback(m:Message):
 if m.text and m.text.startswith("/"): return await m.answer("Unknown command. Use /start.")
 await m.answer("Please choose an option from the menu.",reply_markup=MENU)

@app.get("/")
async def health(): return {"ok":True,"service":"EarnTask bot"}

async def run_bot():
 await init_db()
 await dp.start_polling(bot)

async def run_web():
 config=uvicorn.Config(app,host="0.0.0.0",port=int(os.getenv("PORT","8080")),log_level="info")
 server=uvicorn.Server(config)
 await server.serve()

async def main():
 await asyncio.gather(run_bot(),run_web())

if __name__=="__main__": asyncio.run(main())

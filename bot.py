import discord
import os
import requests
import asyncio
from openai import OpenAI
from datetime import datetime, timezone

print("📦 Kalle Bot wird gestartet...")

# Discord Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)

# ENV Variablen laden
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
WEB_SERVICE_URL = os.getenv("WEB_SERVICE_URL")

# OpenAI Client
client_openai = OpenAI(api_key=OPENAI_API_KEY)

# Begrüßte User
user_greeted = set()

# Pro-User-Tageslimit
user_limits = {}
MAX_REQUESTS_PER_USER_PER_DAY = 5

# Prüft, ob ein User noch GPT verwenden darf
def can_user_call_openai(user_id):
    today = datetime.now(timezone.utc).date()
    if user_id not in user_limits or user_limits[user_id]["date"] != today:
        user_limits[user_id] = {"count": 0, "date": today}
    return user_limits[user_id]["count"] < MAX_REQUESTS_PER_USER_PER_DAY

def increment_user_call(user_id):
    user_limits[user_id]["count"] += 1

# Löscht alle Nachrichten eines Users (außer im Log-Channel)
async def delete_user_messages(channel, user_id, limit=100):
    if channel.id == LOG_CHANNEL_ID:
        return
    async for msg in channel.history(limit=limit):
        if msg.author.id == user_id:
            try:
                await msg.delete()
            except:
                pass

# Löscht alle Nachrichten im Log-Channel (Admin-Befehl)
async def clear_log_channel(channel):
    async for msg in channel.history(limit=1000):
        try:
            await msg.delete()
        except:
            pass

@client.event
async def on_ready():
    print(f"✅ Kalle ist online als {client.user}")
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        msg = await channel.send("👋 Kalle ist bereit für deine Trading-Fragen!")
        await asyncio.sleep(300)
        await msg.delete()

@client.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = message.author.id
    user_input = message.content.strip()

    # 🔒 Admin-Befehl im Log-Channel: "!clearlogs"
    if message.channel.id == LOG_CHANNEL_ID and user_input.lower() == "!clearlogs":
        if message.author.guild_permissions.administrator:
            confirm = await message.channel.send("🧹 Lösche alle Log-Nachrichten...")
            await clear_log_channel(message.channel)
        else:
            await message.channel.send("⛔ Du hast keine Berechtigung.")
        return

    if message.channel.id != CHANNEL_ID:
        return

    # Begrüßung
    if user_id not in user_greeted:
        user_greeted.add(user_id)
        greeting = await message.channel.send(
            f"👋 Willkommen {message.author.mention}!\n\n"
            "Ich bin **Kalle**, dein persönlicher **Trading-Coach**. 📈💬\n"
            "Frag mich alles rund um:\n"
            "• Indikatoren (MACD, RSI, etc.)\n"
            "• Strategien (TP, SL, Breakouts)\n"
            "• Marktpsychologie, Sessions, Gann, usw.\n\n"
            "Wie kann ich dir helfen?"
        )
        await asyncio.sleep(300)
        await greeting.delete()
        return

    # Limit-Prüfung
    if not can_user_call_openai(user_id):
        log_channel = client.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(
                f"🚫 **Anfrage blockiert** von {message.author} (Limit erreicht)\n"
                f"🧠 Inhalt: `{user_input}`\n"
                f"📆 Heute gesendet: {user_limits[user_id]['count']}/{MAX_REQUESTS_PER_USER_PER_DAY}"
            )
        await message.delete()
        return

    try:
        # GPT-Antwort abrufen
        res = client_openai.chat.completions.create(
            model="gpt-3.5-turbo",
            max_tokens=200,
            messages=[
                {"role": "system", "content": "Du bist Kalle, ein professioneller Trading-Coach."},
                {"role": "user", "content": user_input}
            ]
        )
        reply = res.choices[0].message.content.strip()

        # Fallback bei unklarer GPT-Antwort
        if "ich bin mir nicht sicher" in reply.lower() or len(reply) < 20:
            ws = requests.post(f"{WEB_SERVICE_URL}/learn", json={"question": user_input})
            if ws.status_code == 200:
                reply = ws.json().get("answer", "Ich konnte nichts finden.")

        # Antwort senden
        formatted = (
            f"📊 **Kalles Antwort**\n\n"
            f"{reply}\n\n"
            f"---\n"
            f"🤖 *Möchtest du noch etwas wissen? Frag mich einfach weiter!*"
        )
        antwort = await message.channel.send(formatted)

        # Tokenverbrauch schätzen
        estimated_tokens = len(user_input) // 4 + 200
        increment_user_call(user_id)

        # Logging
        log_channel = client.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(
                f"📋 **Anfrage von {message.author}**\n"
                f"🧠 Inhalt: `{user_input}`\n"
                f"📤 Tokens geschätzt: {estimated_tokens}\n"
                f"📆 Heute gesendet: {user_limits[user_id]['count']}/{MAX_REQUESTS_PER_USER_PER_DAY}"
            )

        # Nachrichten löschen nach 5 Minuten
        await asyncio.sleep(300)
        await delete_user_messages(message.channel, user_id)

    except Exception as e:
        print("❌ Fehler im Bot:", e)
        try:
            if "insufficient_quota" in str(e).lower():
                log_channel = client.get_channel(LOG_CHANNEL_ID)
                if log_channel:
                    await log_channel.send("🚨 GPT-Anfrage blockiert: Quota überschritten. Bitte Guthaben prüfen.")
                return
            elif "rate_limit" in str(e).lower():
                log_channel = client.get_channel(LOG_CHANNEL_ID)
                if log_channel:
                    await log_channel.send("⚠️ GPT-Anfrage blockiert: Rate-Limit erreicht.")
                await asyncio.sleep(5)
                return

            fehler = await message.channel.send("⚠️ Ein Fehler ist aufgetreten. Versuch es bitte später nochmal.")
            await asyncio.sleep(300)
            await fehler.delete()
        except:
            pass

# Start
try:
    client.run(DISCORD_TOKEN)
except Exception as e:
    print("❌ Fehler beim Starten des Bots:", e)

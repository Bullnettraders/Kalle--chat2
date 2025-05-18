import discord
import os
import requests
import asyncio
from openai import OpenAI

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
WEB_SERVICE_URL = os.getenv("WEB_SERVICE_URL")

# OpenAI Client
client_openai = OpenAI(api_key=OPENAI_API_KEY)
user_greeted = set()

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
    if message.channel.id != CHANNEL_ID or message.author.bot:
        return

    user_id = message.author.id
    user_input = message.content.strip()

    # Begrüßung (nur einmal pro User)
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

    try:
        # GPT-Antwort abrufen
        res = client_openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Du bist Kalle, ein professioneller Trading-Coach."},
                {"role": "user", "content": user_input}
            ]
        )
        reply = res.choices[0].message.content.strip()

        # Wenn GPT unsicher ist → Webservice fragen
        if "ich bin mir nicht sicher" in reply.lower() or len(reply) < 20:
            ws = requests.post(f"{WEB_SERVICE_URL}/learn", json={"question": user_input})
            if ws.status_code == 200:
                reply = ws.json().get("answer", "Ich konnte nichts finden.")

        # Antwort senden & speichern
        formatted = (
            f"📊 **Kalles Antwort**\n\n"
            f"{reply}\n\n"
            f"---\n"
            f"🤖 *Möchtest du noch etwas wissen? Frag mich einfach weiter!*"
        )
        antwort = await message.channel.send(formatted)

        # Warte 5 Minuten → lösche Antwort und Frage
        await asyncio.sleep(300)
        await antwort.delete()
        await message.delete()

    except Exception as e:
        print("❌ Fehler im Bot:", e)
        try:
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

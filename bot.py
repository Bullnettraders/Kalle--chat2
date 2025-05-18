import discord
import os
import requests
from openai import OpenAI

print("📦 Kalle Bot wird gestartet...")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)

# Lade Umgebungsvariablen
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
WEB_SERVICE_URL = os.getenv("WEB_SERVICE_URL")

client_openai = OpenAI(api_key=OPENAI_API_KEY)

@client.event
async def on_ready():
    print(f"✅ Kalle ist online als {client.user}")
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("👋 Ich bin **Kalle**, dein Trading-Bot! Frag mich alles.")

@client.event
async def on_message(message):
    if message.channel.id != CHANNEL_ID or message.author.bot:
        return

    user_input = message.content.strip()
    try:
        # GPT-Abfrage
        res = client_openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Du bist Kalle, ein erfahrener Trading-Coach."},
                {"role": "user", "content": user_input}
            ]
        )
        reply = res.choices[0].message.content.strip()

        # Wenn GPT keine richtige Antwort liefert → Webservice fragen
        if "ich bin mir nicht sicher" in reply.lower() or len(reply) < 20:
            ws = requests.post(f"{WEB_SERVICE_URL}/learn", json={"question": user_input})
            if ws.status_code == 200:
                reply = ws.json().get("answer", "Ich konnte nichts finden.")

        await message.channel.send(f"📊 **Kalles Antwort**\n\n{reply}")

    except Exception as e:
        print("❌ Fehler im Bot:", e)
        await message.channel.send("⚠️ Ein Fehler ist aufgetreten.")

client.run(DISCORD_TOKEN)

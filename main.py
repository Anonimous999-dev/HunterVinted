import asyncio
import requests
from bs4 import BeautifulSoup
import discord

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# --- CONFIG DES RECHERCHES ---
SEARCHES = [
    {"name": "Jean Levi's 501", "query": "levis 501", "max_price": 30},
    {"name": "Nike Tech", "query": "nike tech fleece", "max_price": 50},
    {"name": "Hoodie Lacoste", "query": "lacoste hoodie", "max_price": 40},
]

CHANNEL_ID = 123456789012345678  # Remplace par ton channel Discord

# --- SCRAPER ---
def search_vinted(query, max_price):
    url = f"https://www.vinted.fr/catalog?search_text={query.replace(' ', '%20')}"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "lxml")

    items = []
    for item in soup.select("div.ItemBox_box__Vhjqu")[:10]:
        title = item.select_one("img")["alt"]
        price = item.select_one("span").text.replace("€", "").strip()

        try:
            price = float(price)
        except:
            continue

        if price <= max_price:
            link = "https://www.vinted.fr" + item.parent["href"]
            items.append((title, price, link))

    return items


# --- TASK PRINCIPALE ---
async def vinted_loop():
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    sent_items = set()

    while True:
        for s in SEARCHES:
            results = search_vinted(s["query"], s["max_price"])

            for title, price, link in results:
                uid = title + str(price)

                if uid not in sent_items:
                    await channel.send(
                        f"🔍 **Trouvé : {s['name']}**\n"
                        f"💸 Prix : {price}€\n"
                        f"📌 {title}\n"
                        f"🔗 {link}"
                    )
                    sent_items.add(uid)

        await asyncio.sleep(45)  # Pause pour économiser la batterie/render


@client.event
async def on_ready():
    print(f"Bot connecté en tant que {client.user}")
    client.loop.create_task(vinted_loop())


client.run("DISCORD_BOT_TOKEN")

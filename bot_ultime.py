import os
import discord
from discord.ext import commands, tasks
import requests
import asyncio
import random
import time
from datetime import datetime

print("🚀 Démarrage du bot Vinted...")

# Récupère le token depuis Render
TON_TOKEN = os.environ.get('DISCORD_TOKEN')

if not TON_TOKEN:
    print("❌ ERREUR: Token Discord non trouvé!")
    print("💡 Configure DISCORD_TOKEN sur Render.com")
    exit(1)

print("✅ Token Discord trouvé!")

# Configuration
CONFIG = {
    'scan_interval': 300,
    'request_delay': (3, 7),
    'max_requests_per_scan': 6
}

user_searches = {}

class VintedBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        
        self.seen_items = set()
        self.scan_count = 0
        
    async def setup_hook(self):
        print("🔄 Synchronisation des commandes...")
        try:
            await self.tree.sync()
            print("✅ Commandes synchronisées!")
        except Exception as e:
            print(f"❌ Erreur synchronisation: {e}")
    
    async def on_ready(self):
        print(f'✅ {self.user.name} connecté et actif!')
        await self.send_startup_message()
        self.vinted_scanner.start()
    
    async def send_startup_message(self):
        try:
            embed = discord.Embed(
                title="🤖 VINTED BOT ACTIVÉ",
                description="**Je scanne Vinted 24h/24!**\nUtilise `/add` pour commencer",
                color=0x00ff00
            )
            embed.add_field(
                name="🔧 Commandes", 
                value="`/add` - Ajouter recherche\n`/list` - Lister recherches\n`/remove` - Supprimer\n`/stats` - Statistiques", 
                inline=False
            )
            
            for channel in self.get_all_channels():
                if isinstance(channel, discord.TextChannel):
                    await channel.send(embed=embed)
                    print("✅ Message de démarrage envoyé!")
                    break
        except Exception as e:
            print(f"❌ Erreur message démarrage: {e}")

    def random_delay(self):
        return random.uniform(*CONFIG['request_delay'])
    
    def random_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_2 like Mac OS X) AppleWebKit/605.1.15',
            'Accept': 'application/json'
        }
    
    async def scan_vinted(self, search_config):
        try:
            await asyncio.sleep(self.random_delay())
            
            params = {
                'search_text': search_config['keywords'],
                'price_to': search_config['max_price'],
                'order': 'newest_first',
                'per_page': 10
            }
            
            url = "https://www.vinted.fr/api/v2/catalog/items"
            response = requests.get(url, params=params, headers=self.random_headers(), timeout=10)
            
            if response.status_code == 200:
                items = response.json().get('items', [])
                print(f"🔍 {len(items)} articles trouvés pour {search_config['name']}")
                return items
            return []
                
        except Exception as e:
            print(f"❌ Erreur scan {search_config['name']}: {e}")
            return []
    
    async def check_profit(self, item, search_config):
        try:
            item_id = item.get('id')
            price = float(item.get('price', 0))
            title = item.get('title', '')[:80]
            
            if item_id in self.seen_items:
                return None
            
            if price <= search_config['max_price']:
                profit = (price * search_config['profit_margin'] * 0.87) - price - 2
                
                if profit >= search_config['min_profit']:
                    print(f"💰 Bonne affaire trouvée: {title} - {price}€")
                    return {
                        'id': item_id,
                        'title': title,
                        'price': price,
                        'profit': profit,
                        'url': f"https://www.vinted.fr/item/{item_id}",
                        'search_name': search_config['name']
                    }
            return None
        except Exception as e:
            return None
    
    async def send_notification(self, deal, user_id):
        try:
            embed = discord.Embed(
                title="🚨 BONNE AFFAIRE!",
                description=f"**{deal['title']}**",
                color=0xff6b6b,
                url=deal['url']
            )
            
            embed.add_field(name="💰 Prix", value=f"{deal['price']}€", inline=True)
            embed.add_field(name="💵 Profit", value=f"{deal['profit']:.1f}€", inline=True)
            embed.add_field(name="🔍 Recherche", value=deal['search_name'], inline=False)
            
            user = await self.fetch_user(int(user_id))
            if user:
                try:
                    await user.send(embed=embed)
                    print(f"📨 Notification envoyée à {user.name}")
                except:
                    for channel in self.get_all_channels():
                        if isinstance(channel, discord.TextChannel):
                            await channel.send(f"<@{user_id}>", embed=embed)
                            break
            
            self.seen_items.add(deal['id'])
        except Exception as e:
            print(f"❌ Erreur notification: {e}")

    @tasks.loop(minutes=5)
    async def vinted_scanner(self):
        if not user_searches:
            print("ℹ️  Aucune recherche configurée")
            return
        
        print(f"🔍 Scan #{self.scan_count + 1} en cours...")
        new_deals = 0
        
        for user_id, searches in user_searches.items():
            for search_config in searches.values():
                items = await self.scan_vinted(search_config)
                
                for item in items[:3]:
                    deal = await self.check_profit(item, search_config)
                    if deal:
                        await self.send_notification(deal, user_id)
                        new_deals += 1
                        await asyncio.sleep(1)
                
                await asyncio.sleep(2)
        
        self.scan_count += 1
        if new_deals > 0:
            print(f"✅ Scan #{self.scan_count} terminé: {new_deals} nouvelles affaires!")
        else:
            print(f"✅ Scan #{self.scan_count} terminé: aucune nouvelle affaire")
    
    @vinted_scanner.before_loop
    async def before_scanner(self):
        await self.wait_until_ready()

# Commandes Discord
bot = VintedBot()

@bot.tree.command(name="add", description="Ajouter une recherche")
async def add_search(interaction: discord.Interaction, nom: str, mots_cles: str, prix_max: float, marge: float = 1.8):
    try:
        user_id = str(interaction.user.id)
        
        if user_id not in user_searches:
            user_searches[user_id] = {}
        
        search_id = f"{nom}_{int(time.time())}"
        user_searches[user_id][search_id] = {
            'name': nom,
            'keywords': mots_cles,
            'max_price': prix_max,
            'profit_margin': marge,
            'min_profit': 8
        }
        
        embed = discord.Embed(
            title="✅ Recherche ajoutée!",
            description=f"**{nom}**\n`{mots_cles}`\nMax: {prix_max}€ | Marge: {marge}x",
            color=0x00ff00
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        print(f"✅ Recherche ajoutée: {nom}")
    except Exception as e:
        await interaction.response.send_message("❌ Erreur lors de l'ajout!", ephemeral=True)

@bot.tree.command(name="list", description="Lister mes recherches")
async def list_searches(interaction: discord.Interaction):
    try:
        user_id = str(interaction.user.id)
        
        if user_id not in user_searches or not user_searches[user_id]:
            await interaction.response.send_message("❌ Aucune recherche!", ephemeral=True)
            return
        
        embed = discord.Embed(title="📋 Tes recherches", color=0x3498db)
        
        for i, config in enumerate(user_searches[user_id].values(), 1):
            embed.add_field(
                name=f"{i}. {config['name']}",
                value=f"`{config['keywords']}` | Max: {config['max_price']}€",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message("❌ Erreur liste!", ephemeral=True)

@bot.tree.command(name="remove", description="Supprimer une recherche")
async def remove_search(interaction: discord.Interaction, numero: int):
    try:
        user_id = str(interaction.user.id)
        
        if user_id not in user_searches:
            await interaction.response.send_message("❌ Aucune recherche!", ephemeral=True)
            return
        
        searches = list(user_searches[user_id].values())
        if 1 <= numero <= len(searches):
            search_name = searches[numero-1]['name']
            keys = list(user_searches[user_id].keys())
            del user_searches[user_id][keys[numero-1]]
            
            await interaction.response.send_message(f"✅ **{search_name}** supprimée!", ephemeral=True)
            print(f"✅ Recherche supprimée: {search_name}")
        else:
            await interaction.response.send_message("❌ Numéro invalide!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message("❌ Erreur suppression!", ephemeral=True)

@bot.tree.command(name="stats", description="Statistiques du bot")
async def bot_stats(interaction: discord.Interaction):
    try:
        total_searches = sum(len(searches) for searches in user_searches.values())
        
        embed = discord.Embed(title="📊 Stats du Bot", color=0x9b59b6)
        embed.add_field(name="👥 Utilisateurs", value=len(user_searches), inline=True)
        embed.add_field(name="🔍 Recherches", value=total_searches, inline=True)
        embed.add_field(name="🔄 Scans", value=bot.scan_count, inline=True)
        embed.add_field(name="💾 Articles", value=len(bot.seen_items), inline=True)
        
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message("❌ Erreur stats!", ephemeral=True)

# 🚀 LANCEMENT
if __name__ == "__main__":
    print("🚀 Lancement du bot...")
    try:
        bot.run(TON_TOKEN)
    except Exception as e:
        print(f"❌ ERREUR CRITIQUE: {e}")
        import traceback
        traceback.print_exc()

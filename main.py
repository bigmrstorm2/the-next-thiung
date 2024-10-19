import discord
from discord.ext import commands
import random
import requests
import json
import os
import asyncio

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
client = commands.Bot(command_prefix="!", intents=intents)

GELBOORU_API_URL = "https://gelbooru.com/index.php?page=dapi&s=post&q=index"
API_KEY = '6f284874e454ac97a694bb9cffb4a0faa0c19a3862d9855973fdcaf990fcd75f'
USER_ID = '1571336'

used_numbers = set()
user_inventories = {}

def load_inventory():
    if os.path.exists('inventory.json'):
        with open('inventory.json', 'r') as f:
            return json.load(f)
    return {}

def save_inventory():
    with open('inventory.json', 'w') as f:
        json.dump(user_inventories, f)

user_inventories = load_inventory()

def format_number(number):
    return f"{number:03d}"

def generate_unique_number():
    available_numbers = set(range(1000)) - used_numbers
    if not available_numbers:
        return None
    number = random.choice(list(available_numbers))
    used_numbers.add(number)
    return format_number(number)

def fetch_gelbooru_image(tags):
    params = {
        "page": "dapi",
        "s": "post",
        "q": "index",
        "api_key": API_KEY,
        "user_id": USER_ID,
        "tags": tags,
        "limit": 100,
        "json": 1,
    }

    try:
        response = requests.get(GELBOORU_API_URL, params=params)

        if response.status_code == 200:
            data = response.json()
            if data and 'post' in data and len(data['post']) > 0:
                post = random.choice(data['post'])

                if 'file_url' in post:
                    artist_tags = post.get('tag_string_artist', '').split(', ') if post.get('tag_string_artist') else ['Unknown']
                    character_tags = post.get('tag_string_character', '').split(', ') if post.get('tag_string_character') else ['Unknown']
                    copyright_tags = post.get('tag_string_copyright', '').split(', ') if post.get('tag_string_copyright') else ['Unknown']

                    return {
                        "image_url": post['file_url'],
                        "artist": ', '.join(artist_tags),
                        "copyright": ', '.join(copyright_tags),
                        "character": ', '.join(character_tags),
                    }
                else:
                    return None
            else:
                return None
        else:
            return None

    except requests.RequestException as e:
        return None

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

@client.event
async def on_member_join(member):
    number = generate_unique_number()
    if number is None:
        return

    try:
        await member.edit(nick=number)
        print(f'Changed {member.name}\'s name to {number}')
    except discord.Forbidden:
        print(f"Missing permissions to change nickname of {member.name}")
    except discord.HTTPException as e:
        print(f"Failed to change nickname for {member.name}: {e}")

@client.event
async def on_member_remove(member):
    if member.nick and member.nick.isdigit():
        used_numbers.discard(int(member.nick))

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if client.user in message.mentions:
        if "search" in message.content.lower():
            category = message.content.lower().split("search", 1)[1].strip()
            image_data = fetch_gelbooru_image(category)

            if image_data and image_data['image_url']:
                embed = discord.Embed(
                    title="Image Information",
                    color=random.randint(0, 0xFFFFFF)
                )
                embed.add_field(name="Character", value=image_data['character'], inline=False)
                embed.add_field(name="Artist", value=image_data['artist'], inline=False)
                embed.add_field(name="Copyright", value=image_data['copyright'], inline=False)
                embed.set_image(url=image_data['image_url'])

                msg = await message.channel.send(embed=embed, reference=message)

                await msg.add_reaction("💾")

                def check_reaction(reaction, user):
                    return user == message.author and str(reaction.emoji) == "💾" and reaction.message.id == msg.id

                try:
                    reaction, user = await client.wait_for("reaction_add", timeout=60.0, check=check_reaction)

                    if message.author.id not in user_inventories:
                        user_inventories[message.author.id] = []
                    user_inventories[message.author.id].append(image_data)
                    save_inventory()
                    await message.channel.send("Image saved to your inventory!")

                except asyncio.TimeoutError:
                    await message.channel.send("You took too long to react. The image was not saved.")

        elif message.content.strip().endswith("!inventory"):
            await inventory(message)

        elif message.content.strip().endswith("!help"):
            await help_command(message)

    await client.process_commands(message)

async def inventory(message):
    if message.author.id not in user_inventories or not user_inventories[message.author.id]:
        await message.channel.send("Your inventory is empty.")
        return

    inventory = user_inventories[message.author.id]
    index = 0

    async def update_message():
        embed = discord.Embed(
            title="Inventory Image",
            color=random.randint(0, 0xFFFFFF)
        )
        embed.add_field(name="Character", value=inventory[index]['character'], inline=False)
        embed.add_field(name="Artist", value=inventory[index]['artist'], inline=False)
        embed.add_field(name="Copyright", value=inventory[index]['copyright'], inline=False)
        embed.set_image(url=inventory[index]['image_url'])
        embed.set_footer(text=f"Image {index + 1} of {len(inventory)}")
        await msg.edit(embed=embed)

    embed = discord.Embed(
        title="Inventory Image",
        color=random.randint(0, 0xFFFFFF)
    )
    embed.add_field(name="Character", value=inventory[0]['character'], inline=False)
    embed.add_field(name="Artist", value=inventory[0]['artist'], inline=False)
    embed.add_field(name="Copyright", value=inventory[0]['copyright'], inline=False)
    embed.set_image(url=inventory[0]['image_url'])
    embed.set_footer(text=f"Image 1 of {len(inventory)}")
    msg = await message.channel.send(embed=embed)
    await msg.add_reaction("⬅️")
    await msg.add_reaction("➡️")

    def check(reaction, user):
        return user == message.author and str(reaction.emoji) in ["⬅️", "➡️"] and reaction.message.id == msg.id

    while True:
        try:
            reaction, user = await client.wait_for("reaction_add", timeout=60.0, check=check)

            if str(reaction.emoji) == "➡️":
                index = (index + 1) % len(inventory)
            elif str(reaction.emoji) == "⬅️":
                index = (index - 1) % len(inventory)

            await update_message()
            await reaction.remove(user)

        except asyncio.TimeoutError:
            await msg.clear_reactions()
            break

async def help_command(message):
    help_embed = discord.Embed(
        title="Help - Bot Commands",
        description="Here are the commands you can use with this bot:",
        color=random.randint(0, 0xFFFFFF)
    )
    
    help_embed.add_field(name="@bot search <category>", value="Fetch a random image from Gelbooru based on the specified category.", inline=False)
    help_embed.add_field(name="@bot !inventory", value="View all images you have saved in your inventory.", inline=False)
    help_embed.add_field(name="@bot !help", value="Display this help message.", inline=False)

    await message.channel.send(embed=help_embed)

client.run('token')

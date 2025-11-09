import discord
from discord.ext import commands
import logging
import os
import asyncio
from utils.constants import TOKEN, COMMAND_PREFIX

# Setup logging
logging.basicConfig(
    filename='discord.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

class Bot(commands.Bot):
    async def setup_hook(self):
        # Load cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and not filename.startswith('__'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f'Loaded {filename}')
                except Exception as e:
                    print(f'Failed to load {filename}')
                    print(f'Error: {e}')

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')
        await self.change_presence(activity=discord.Game(name=f"{COMMAND_PREFIX}help"))

def main():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True

    bot = Bot(command_prefix=COMMAND_PREFIX, intents=intents)
    
    try:
        bot.run(TOKEN)
    except Exception as e:
        logging.error(f"Error running bot: {e}")

if __name__ == "__main__":
    main()
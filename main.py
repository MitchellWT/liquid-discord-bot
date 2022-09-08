import os
import logging

from dotenv import load_dotenv
from discord.ext import commands

load_dotenv()

# Global variables
bot = commands.Bot(command_prefix=['-', 'liquid '])
token = os.getenv('DISCORD_TOKEN')

# Logging
logging.basicConfig(
    filename='debug.log', 
    level=logging.DEBUG)

@bot.event
async def on_ready():
    print(f'{bot.user.name} is ready!')

bot.load_extension('liquid.player')
bot.run(token)

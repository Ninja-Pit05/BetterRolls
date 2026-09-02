""" BetterRools point of entrance.

Initialises the logging system, loads cogs and starts the bot.

Set the env variable BOT_TOKEN to you bot token from discord's developer portal.

Run the main file from a virtual environment with:
´´´
python main.py
´´´
"""

import os
import importlib
import traceback
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from dotenv import load_dotenv

import discord
import discord
from discord.ext import commands

from db import init_db


load_dotenv()
BOT_TOKEN = os.environ.get('BOT_TOKEN')
PREFIX = os.environ.get('PREFIX')


logger = logging.getLogger(__name__)
logger.setLevel('INFO')
LOG_FORMAT='[%(levelname)s] (%(asctime)s) [%(module)s] - %(message)s'
# Logger's file handler
logger_fh=TimedRotatingFileHandler(
        'logs/log.txt',
        when='midnight',
        backupCount=30)
logger_fh.setFormatter(logging.Formatter(LOG_FORMAT))
# Logger's console (stream) handler
logger_sh=logging.StreamHandler()
logger_sh.setFormatter(logging.Formatter(LOG_FORMAT))
logger.addHandler(logger_fh)
logger.addHandler(logger_sh)


init_db('database.db')


class CustomBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self) -> None:
        for file in os.listdir("cogs"):
            if file.endswith(".py"):
                await bot.load_extension(f'cogs.{file[:-3]}')
        await self.tree.sync()


description = """A simple discord bot that provides stats editing and dice
rolling for rpg sessions.
Made by Ninja. https://github.com/Ninja-Pit05/BetterRolls
"""
intents = discord.Intents.default()
intents.message_content = True

bot = CustomBot(command_prefix=PREFIX,
                description=description,
                intents=intents)


@bot.event
async def on_ready():
    """ Announce succesfull connections. """
    logger.info('Successfully logged in as %s', bot.user)


@bot.tree.command()
async def ping(interaction):
    """ Let's us know the bot is on. """
    logger.info('PING! at %s', datetime.now())
    await interaction.response.send_message("Pong")


bot.run(BOT_TOKEN)

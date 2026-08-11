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

import discord
from discord import app_commands

from db import init_db

init_db('database.db')



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

class Client(discord.Client):
    """ Custom discord Client. """
    user: discord.ClientUser

    def __init__(self, *, intents: discord.Intents): # pylint: disable=W0621
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # load cogs
        for file in os.listdir("cogs"):
            if file.endswith(".py"):
                spec = importlib.util.find_spec(f"cogs.{file[:-3]}")
                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)
                except Exception as e: # pylint: disable=W0718
                    e_text = traceback.format_exception(e)
                    logger.error(
                        'Failed to compile cog "%s": %s\n    %s',
                        file[:-3], e, ''.join(e_text))
                    continue
                try:
                    loader = getattr(module,'load')
                except AttributeError:
                    logger.error('Cog "%s" missing loader.', file[:-3])
                    continue
                try:
                    loader(self)
                except Exception as e: # pylint: disable=W0718
                    e_text = traceback.format_exception(e)
                    logger.error(
                        'Failed to load cog "%s": %s\n    %s',
                        file[:-3], e, ''.join(e_text))
                    continue
                logger.info('Loaded cog "%s" successfully.', file[:-3])
        await self.tree.sync()



intents = discord.Intents.default()
client = Client(intents=intents)



@client.event
async def on_ready():
    """ Announce succesfull connections. """
    logger.info('Successfully logged in as %s', client.user)


@client.tree.command()
async def ping(interaction):
    """ Let's us know the bot is on. """
    logger.info('PING! at %s', datetime.now())
    await interaction.response.send_message("Pong")

client.run(BOT_TOKEN)

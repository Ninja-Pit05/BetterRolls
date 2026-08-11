""" Takes care of every aspect of players stats. From creation and storing to
editing and deletion.
"""
from enum import Enum
from time import time
from re import fullmatch
from typing import Literal
from random import randint
from dataclasses import dataclass

import discord
from discord import ui
from utils import Paginator, NextButton, PreviousButton, ReturnButton, clamp
from db import ConnectionManager, UsersDBInterface


STANDARD_DND_DICES = ['d4','d6','d8','d10','d12','d20','d100']


class InvalidInput(Exception):
    """ Raised when input has an invalid type on validate_input() """
    pass

class OutOfLimits(Exception):
    """ Raised when input has an invalid size. """
    pass

class RollTypes(Enum):
    """ Enumeration of stat types. Equivalent to the Types lookup table."""
    Single = 0
    Advantage = 1
    Disadvantage = 2
    Grouped = 3

    def __getitem__(self, subscript: int):
        """ Allows subscription of RollTypes by their values. """
        return [self.Single, self.Advantage,
                self.Disadvantage, self.Grouped][subscript]


@dataclass
class Dice():
    """ A dice that was rolled trough one of the rolling commands.
    Type is the dice highest number. (6, 12, 20 etc.) And value
    is the actual value the dice rolled. When initiated without a set
    value, it will automatically roll its type.
    """
    def __init__(self, type: int, value: int = None, roll_id: int = None):
        self.roll_id = roll_id
        self.type = type
        if value is None:
            self.value = randint(1, type)
        else:
            self.value = value

@dataclass
class Roll():
    """ A roll is one call of any rolling command stored in the db for
    roll history tracking purposes. One roll can have many dices with
    different types involved. The rolltype of the roll defines how the
    dices values will be interpreted.
    """
    def __init__(self, id: int, user_id: int, type_id: int,
                 timestamp: int, dices: list[dice]):
        self.id = id
        self.user_id = user_id
        self.type = RollTypes(type_id)
        self.timestamp = timestamp
        self.dices = dices



class RollsDBInterface:
    """ Bridge to the relational database.
    Acts on tables relates to rolls such as users, rolls, dices and
    rolltypes.
    """
    def __init__(self, file: str):
        self.file = file
        self.users_if = UsersDBInterface(self.file)

    def fetchall_from(self, user_id: int) -> list[Roll]|list:
        _id = self.users_if.get_surrogate(user_id)
        with ConnectionManager(self.file) as db:
            raw_rolls = db.cursor.execute(
                'SELECT * FROM rolls WHERE user_id = ?',
                [_id]).fetchall()
            rolls = [
                        Roll(
                            *raw_roll,
                            [
                                Dice(raw_dice[1], raw_dice[2], raw_dice[0])
                                for raw_dice in db.cursor.execute(
                                    'SELECT * FROM dices WHERE roll_id = ?',
                                    [raw_roll[0]]).fetchall()
                            ])
                        for raw_roll in raw_rolls
                    ]
        return rolls

    def new(self, user_id: int, rolltype_id: int, timestamp: int,
            dices: list[tuple[int,int]]) -> None:
        _id = self.users_if.get_surrogate(user_id)
        if _id is None:
            self.users_if.add_user(user_id)
            _id = self.users_if.get_surrogate(user_id)

        with ConnectionManager(self.file) as db:
            roll_id = db.cursor.execute(
                'INSERT INTO rolls VALUES(NULL, ?, ?, ?) RETURNING id',
                [_id, rolltype_id, timestamp]).fetchone()
            roll_id = roll_id[0]
            for dice in dices:
                db.cursor.execute(
                'INSERT INTO dices VALUES(?, ?, ?)',
                [roll_id, dice[0], dice[1]])
            db.connection.commit()

database = RollsDBInterface('database.db')



class HistoryView(ui.LayoutView):
    """ Display an user roll history trough a paginated list on conatiners.

    Args:
        user: Discord.User being viwed.
    """
    def __init__(self, user: discord.User, paginator: Paginator = None):
        super().__init__()
        self.add_item(ui.TextDisplay(f'Roll history for {user.mention}.'))
        if paginator is None:
            paginator = Paginator(database.fetchall_from(user.id),6)
        for roll in paginator.current:
            if roll.type == RollTypes.Grouped:
                values = {}
                for dice in roll.dices:
                    try:
                        values[dice.type].append(dice)
                    except KeyError:
                        values[dice.type] = [dice]
                dice_values = '\n'.join(
                    [f'> {len(values[key])}d{values[key][0].type}: '
                        + ', '.join([str(dice.value) for dice in dices])
                     for key, dices in values.items()])
            else:
                dice_values = ', '.join([str(dice.value) for dice in roll.dices])
            match roll.type:
                case RollTypes.Single:
                    title = f'### Standard Roll d{roll.dices[0].type}\n'
                    body = 'Rolled 🎲' + dice_values
                case RollTypes.Advantage:
                    title = (f'### Advantage Roll {len(roll.dices)}'
                             f'd{roll.dices[0].type}\n')
                    body = (f'-# Rolled {dice_values}\nHighest '
                            f'🎲{max([dice.value for dice in roll.dices])}')
                case RollTypes.Disadvantage:
                    title = (f'### Advantage Roll {len(roll.dices)}'
                             f'd{roll.dices[0].type}\n')
                    body = (f'-# Rolled {dice_values}\nLowest '
                            f'🎲{min([dice.value for dice in roll.dices])}')
                case RollTypes.Grouped:
                    title = '### Grouped Roll\n'
                    body = (f'{dice_values}\nTotal '
                            f'🎲{sum([dice.value for dice in roll.dices])}')
            self.add_item(ui.Container(
                ui.TextDisplay(title + body + f'\n-# <t:{roll.timestamp}>')))
        self.add_item(ui.ActionRow(
            PreviousButton(user, paginator, HistoryView),
            NextButton(user, paginator, HistoryView),
            ))



def load(client: discord.Client):
    """Cog loader. Loads this cog to a discord.Client instance.

    Args:
        client(discord.Cient) - Client instance to bind this cog to.
    """

    @client.tree.command()
    async def roll(interaction,
            dice: Literal[*STANDARD_DND_DICES]):
        """ Roll a standard DND dice once.

        Args:
            dice: Select which standard dice to roll.
        """

        roll = Dice(type=int(dice[1:]))
        await interaction.response.send_message(
            f'## {interaction.user.display_name} is rolling a {dice}.'
            f'\n### Rolled 🎲{roll.value}')
        database.new(interaction.user.id, RollTypes.Single.value,
                     int(time()), [(roll.type, roll.value)])

    @client.tree.command()
    async def advantage_roll(interaction,
            dice: Literal[*STANDARD_DND_DICES],
            amount: int = 2):
        """ Roll n dices with advantage.

        Args:
            dice: Select which standard dice to roll.
            amount: How many dices to trow. Defaults to 2, min 2 and max 20.
        """
        amount = clamp(2, amount, 20)
        rolls = [Dice(type=int(dice[1:])) for _ in range(amount)]
        await interaction.response.send_message(
            f'## {interaction.user.display_name} is rolling {amount}{dice} '
            f'with advantage.'
            f'\n-# Rolled {', '.join(str(roll.value) for roll in rolls)}'
            f'\n### Higher dice 🎲{max([roll.value for roll in rolls])}')
        database.new(interaction.user.id, RollTypes.Advantage.value,
                     int(time()), [(roll.type, roll.value) for roll in rolls])

    @client.tree.command()
    async def disadvantage_roll(interaction,
            dice: Literal[*STANDARD_DND_DICES],
            amount: int = 2):
        """ Roll n dices with disadvantage.

        Args:
            dice: Select which standard dice to roll.
            amount: How many dices to trow. Defaults to 2, min 2 and max 20.
        """
        amount = clamp(2, amount, 20)
        rolls = [Dice(type=int(dice[1:])) for _ in range(amount)]
        await interaction.response.send_message(
            f'## {interaction.user.display_name} is rolling {amount}{dice} '
            f'with disadvantage.'
            f'\n-# Rolled {', '.join(str(roll.value) for roll in rolls)}'
            f'\n### Lower dice 🎲{max([roll.value for roll in rolls])}')
        database.new(interaction.user.id, RollTypes.Disadvantage.value,
                     int(time()), [(roll.type, roll.value) for roll in rolls])

    @client.tree.command()
    async def grouped_roll(interaction,
            dice_pool1: Literal[*STANDARD_DND_DICES],
            amount_pool1: int,
            dice_pool2: Literal[*STANDARD_DND_DICES] = None,
            amount_pool2: int = 1,
            dice_pool3: Literal[*STANDARD_DND_DICES] = None,
            amount_pool3: int = 1,
            dice_pool4: Literal[*STANDARD_DND_DICES] = None,
            amount_pool4: int = 1):
        """ Roll at most 4 dice pools at once and sum their values. Max of 10
        dices per pool.

        Args:
            dice_pool1: Select which standard dice to roll on pool 1.
            amount_pool1: How many dices to trow on pool 1.
            dice_pool2: Select which standard dice to roll on pool 2.
            amount_pool2: How many dices to trow on pool 2.
            dice_pool3: Select which standard dice to roll on pool 3.
            amount_pool3: How many dices to trow on pool 3.
            dice_pool4: Select which standard dice to roll on pool 4.
            amount_pool4: How many dices to trow on pool 4.
        """
        pools = [(int(pool[1:]), clamp(2, amount, 10)) for pool, amount in
                  [
                    (dice_pool1, amount_pool1), (dice_pool2, amount_pool2),
                    (dice_pool3, amount_pool3), (dice_pool4, amount_pool4)
                  ] if pool is not None]
        group_rolls = [[Dice(type) for _ in range(amount)]
                            for type, amount in pools]
        pools_str = [f'{a}d{t}' for t, a in pools]
        await interaction.response.send_message(
            f'## {interaction.user.display_name} is rolling '
            +f'{ ', '.join(pools_str)}.\n'
            +'\n'.join([f'-# {pool_str} rolled '
                      f'{', '.join(str(roll.value) for roll in rolls)}'
                      f'\n-# **Totalling 🎲{sum([roll.value for roll in rolls])}**'
                      for pool_str, rolls in zip(pools_str,group_rolls)])
            +f'\n### Grouped roll 🎲{sum([roll.value for rolls in group_rolls
                                                      for roll in rolls])}')
        database.new(interaction.user.id, RollTypes.Grouped.value, int(time()),
                     [(roll.type, roll.value) for rolls in group_rolls
                                        for roll in rolls])

    @client.tree.command()
    async def custom_roll(interaction, expression: str):
        """ Roll a custom set of dices with the usual dnd notation. The total
        amount of dices can't be higher than 30.

        Args:
            expression: String containing the dices to roll. Ex: "2d6 3d4 d20"    
        """
        raw = expression.split(' ')
        while ' ' in raw:
            raw.remove(' ')
        for pool in raw:
            if pool[0] == 'd':
                pool = '1'+pool
            if (fullmatch('[\\d]*d[\\d]+', pool) is None
                    or any([int(v)<1 for v in pool.split('d')])
                    or any([int(v)>1000 for v in pool.split('d')])):
                await interaction.response.send_message(
                    f'Invalid code ***{pool}***.')
                return
        if sum([int(pool.split('d')[0] if pool[0] != 'd' else 1)
                for pool in raw]) > 30:
            await interaction.response.send_message(
                'Way too many dices. Capped at 30 for custom rolls.')
            return
        group_rolls = []
        for pool in raw:
            amount = pool[:pool.find('d')]
            if amount == '':
                amount = 1
            else:
                amount = int(amount)
            group_rolls.append(
                [Dice(type=int(pool[pool.find('d')+1:]))
                for _ in range(amount)]
                )
        await interaction.response.send_message(
            f'## {interaction.user.display_name} is rolling '
            +f'{ ', '.join(raw)}.\n'
            +'\n'.join([f'-# {pool} rolled '
                        f'{', '.join(str(roll.value) for roll in rolls)}'
                        f'\n-# **Totalling 🎲{sum([roll.value
                                                    for roll in rolls])}**'
                        for rolls, pool in zip(group_rolls, raw)])
            +f'\n### Total roll 🎲{sum([roll.value
                                            for rolls in group_rolls
                                            for roll in rolls])}')
        database.new(interaction.user.id, RollTypes.Grouped.value, int(time()),
                     [(roll.type, roll.value) for rolls in group_rolls
                                              for roll in rolls])


    @client.tree.command()
    async def history(interaction, user: discord.User = None):
        """ See an user's roll history.

        Args:
            user: Leave it empty to see own roll history.
        """
        if user is None:
            user = interaction.user
        await interaction.response.send_message(view=HistoryView(user))

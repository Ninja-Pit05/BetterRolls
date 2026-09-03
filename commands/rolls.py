""" Takes care of every aspect of players stats. From creation and storing to
editing and deletion.
"""
from enum import Enum
from time import time
from re import fullmatch
import re
from typing import Literal, Union
from random import randint
from dataclasses import dataclass

import discord
from discord import ui
from discord.ext import commands
from numpy import isin

from utils import Paginator, NextButton, PreviousButton, ReturnButton, clamp
from db import ConnectionManager, UsersDBInterface


STANDARD_DND_DICES = Literal['d4','d6','d8','d10','d12','d20','d100']


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
    type: int
    value: int
    roll_id: int|None
    def __init__(self, type: int, value: int|None = None,
                roll_id: int|None = None):
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
    id: int
    user_id: int
    type: RollTypes
    timestamp: int
    dices: list

    def __init__(self, id: int, user_id: int, type_id: int,
                 timestamp: int, dices: list[Dice]):
        self.id = id
        self.user_id = user_id
        self.type = RollTypes(type_id)
        self.timestamp = timestamp
        self.dices = dices


def result_string_from_groupedroll(roll: Roll) -> str:
    values = {}
    for dice in roll.dices:
        try:
            values[dice.type].append(dice)
        except KeyError:
            values[dice.type] = [dice]
    dice_values = '\n'.join([
        f'> {len(values[key])}d{values[key][0].type}: '
        + ', '.join([str(dice.value) for dice in dices])
        for key, dices in values.items()])
    return dice_values


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
                '''SELECT * FROM rolls WHERE user_id = ?
                    ORDER BY timestamp DESC''',
                [_id]).fetchall()
            rolls = [
                        Roll(
                            *raw_roll,
                            dices = [
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
    def __init__(self, user: discord.User|discord.Member,
                paginator: Paginator|None = None):
        super().__init__()
        self.add_item(ui.TextDisplay(f'Roll history for {user.mention}.'))
        if paginator is None:
            paginator = Paginator(database.fetchall_from(user.id),6)
        for roll in paginator.current:
            if roll.type == RollTypes.Grouped:
                dice_values = result_string_from_groupedroll(roll)
            else:
                dice_values = ', '.join([str(dice.value)
                                        for dice in roll.dices])
            match roll.type:
                case RollTypes.Single:
                    _amount = len(roll.dices) if len(roll.dices) > 1 else ''
                    title = f'### Standard Roll {_amount}d{roll.dices[0].type}\n'
                    body = (f'Rolled 🎲{dice_values}' if
                            len(roll.dices) == 1 else
                            f'\n-# Rolled {dice_values}'
                            +f'\n**Total 🎲{sum([dice.value
                                for dice in roll.dices])}**')
                case RollTypes.Advantage:
                    title = (f'### Advantage Roll {len(roll.dices)}'
                             f'd{roll.dices[0].type}\n')
                    body = (f'-# Rolled {dice_values}\nHighest '
                            f'🎲{max([dice.value for dice in roll.dices])}')
                case RollTypes.Disadvantage:
                    title = (f'### Disadvantage Roll {len(roll.dices)}'
                             f'd{roll.dices[0].type}\n')
                    body = (f'-# Rolled {dice_values}\nLowest '
                            f'🎲{min([dice.value for dice in roll.dices])}')
                case _:
                    title = '### Grouped Roll\n'
                    body = (f'{dice_values[:200]}\nTotal '
                            f'🎲{sum([dice.value for dice in roll.dices])}')
            self.add_item(ui.Container(
                ui.TextDisplay(title + body + f'\n-# <t:{roll.timestamp}>')))
        self.add_item(ui.ActionRow(
            PreviousButton(user, paginator, HistoryView),
            NextButton(user, paginator, HistoryView),
            ))



def parse_roll(text: str) -> list[str|list[str]]:
    """ Parses a string into smaller string of (hopefully) dnd dice
    rolling codes.

    Args:
        text: The full text input to parse.

    Returns:
        List of parsed values strings. Can contain strings for simple
        rolls or a list a strings for grouped rolls."""

    def validate_dices(dices: list[str], group_mode: bool = False) -> None:
        """ Validates dice notation. Raises InvalidInput if not valid.

        Args:
            dices: A list of strings. Each string will be tested for vality.
            group_mode: If the validation should allow 'ad' or 'di' flags for
                advantage and disadvantage rolls. Defaults to False.
        Returns:
            None
        Raises:
            InvalidInput: If any dice string was invalid.
        """
        errors = []
        if len(dices) == 0:
            errors.append('{}')
        for text in dices:
            if group_mode:
                reg = re.fullmatch('\\d*d\\d+', text)
            else:
                reg = re.fullmatch('\\d*d\\d+(?:ad|di)?', text)
            if reg is None:
                errors.append(text)
        if len(errors) > 0:
            if group_mode:
                raise InvalidInput(f'{{{", ".join(errors)}}}')
            else:
                raise InvalidInput(f'{", ".join(errors)}')

    def clear_empty_strings(list: list[str]) -> list:
        """ Iterates over a list removing empty '' strings or
        spaces-only strings."""
        while '' in list:
            list.remove('')
        for item in list:
            if item.isspace():
                list.remove(item)
        return list

    parsing = clear_empty_strings(re.split('({[^{}]*})', text))
    output=[]
    errors = []
    for substring in parsing:
        sublist = substring.strip('{').strip('}').split(' ')
        sublist = clear_empty_strings(sublist)
        try:
            if substring.startswith('{'):
                validate_dices(sublist, True)
            else:
                validate_dices(sublist)
        except InvalidInput as e:
            errors += [e.args[0]]
        if not errors and substring.startswith('{'):
            output.append(sublist)
        elif not errors:
            output += [*sublist]
    if errors:
        raise InvalidInput(', '.join(errors))
    return output

def roll_expression(expression: str|list[str]) -> Roll:
    """ Rolls a valid dnd dice expression.

    Args:
        expression: A valid dnd dice expression  or list of expressions
            in the form of NdMF. Where N and M is an int higher than 0
            and F is one of the two flags: 'ad' for advantage and 'di'
            for disadvantage. If N is missing in the expression it is
            interpreted as an implicit 1. If expression is a list intead
            of a string it is implicit known that it's grouped rool and
            flags aren't accepted.

    Returns:
        A full Roll object with the interpreted rolling results, roll
        type and roll timestamp.
    """
    if isinstance(expression, list):
        pattern = '(?P<amount>\\d*)d(?P<type>\\d+)'
        flag = 'group'
    else:
        pattern = '(?P<amount>\\d*)d(?P<type>\\d+)(?P<flag>ad|di)?'
        flag = None
        expression = [expression]
    assert isinstance(expression, list)
    dices = []
    for exp in expression:
        # get relevant values from groups.
        match = re.fullmatch(pattern, exp)
        assert isinstance(match, re.Match)
        amount = match.group('amount')
        if amount == '':
            amount = 1
        else:
            amount = clamp(1,int(amount),30)
        type = clamp(1,int(match.group('type')),1000)
        if flag is None:
            flag = match.group('flag')
        # roll values, add to dice result pool.
        dices += [Dice(type) for i in range(amount)]
    match flag:
        case 'group':
            roll_type = RollTypes.Grouped
        case 'ad':
            roll_type = RollTypes.Advantage
        case 'di':
            roll_type = RollTypes.Disadvantage
        case _:
            roll_type = RollTypes.Single
    return Roll(-1, -1, roll_type.value, -1, dices)



async def setup(bot):
    """Cog loader. Loads this cog to a discord.Client instance.

    Args:
        client(discord.Cient) - Client instance to bind this cog to.
    """

    @bot.hybrid_command()
    async def roll(ctx: commands.Context, dice: STANDARD_DND_DICES):
        """ Roll a single standard DND dice once.

        Args:
            dice: Select which standard dice to roll.
        """
        try:
            parsed_exp = parse_roll(dice)
        except InvalidInput as e:
            try:
                assert isinstance(ctx.interaction, discord.Interaction)
                await ctx.interaction.response.send_message(
                    f'Invalid input(s): {e.args[0]}')
            except:
                await ctx.channel.send(f'Invalid input(s): {e.args[0]}')
            return
        roll = roll_expression(parsed_exp[0])
        txt = (f'## {ctx.author.display_name} is rolling a {dice}.'
                f'\n### Rolled 🎲{roll.dices[0].value}')
        try:
            assert isinstance(ctx.interaction, discord.Interaction)
            await ctx.interaction.response.send_message(txt)
        except:
            await ctx.channel.send(txt)
        database.new(ctx.author.id, RollTypes.Single.value, int(time()),
            [(dice.type, dice.value) for dice in roll.dices])

    @bot.hybrid_command()
    async def advantage_roll(ctx: commands.Context,
            dice: STANDARD_DND_DICES,
            amount: int = 2):
        """ Roll n dices with advantage.

        Args:
            dice: Select which standard dice to roll.
            amount: How many dices to trow. Defaults to 2, min 2 and max 30.
        """
        expression = f'{amount}{dice}'
        try:
            parsed_exp = parse_roll(expression)
        except InvalidInput as e:
            try:
                assert isinstance(ctx.interaction, discord.Interaction)
                await ctx.interaction.response.send_message(
                    f'Invalid input(s): {e.args[0]}')
            except:
                await ctx.channel.send(f'Invalid input(s): {e.args[0]}')
            return
        roll = roll_expression(parsed_exp[0])
        txt = (f'## {ctx.author.display_name} is rolling a {expression} '
            f'with advantage.'
            f'\n-# Rolled {', '.join([str(dice.value)
                for dice in roll.dices])}'
            f'\n### Higher dice 🎲{max([dice.value
                for dice in roll.dices])}')
        try:
            assert isinstance(ctx.interaction, discord.Interaction)
            await ctx.interaction.response.send_message(txt)
        except:
            await ctx.channel.send(txt)
        database.new(ctx.author.id, RollTypes.Advantage.value, int(time()),
            [(dice.type, dice.value) for dice in roll.dices])

    @bot.hybrid_command()
    async def disadvantage_roll(ctx: commands.Context,
            dice: STANDARD_DND_DICES,
            amount: int = 2):
        """ Roll n dices with disadvantage.

        Args:
            dice: Select which standard dice to roll.
            amount: How many dices to trow. Defaults to 2, min 2 and max 30.
        """
        expression = f'{amount}{dice}'
        try:
            parsed_exp = parse_roll(expression)
        except InvalidInput as e:
            try:
                assert isinstance(ctx.interaction, discord.Interaction)
                await ctx.interaction.response.send_message(
                    f'Invalid input(s): {e.args[0]}')
            except:
                await ctx.channel.send(f'Invalid input(s): {e.args[0]}')
            return
        roll = roll_expression(parsed_exp[0])
        txt = (f'## {ctx.author.display_name} is rolling a {expression} '
            f'with disadvantage.'
            f'\n-# Rolled {', '.join([str(dice.value) for dice in roll.dices])}'
            f'\n### Lowest dice 🎲{min([dice.value for dice in roll.dices])}')
        try:
            assert isinstance(ctx.interaction, discord.Interaction)
            await ctx.interaction.response.send_message(txt)
        except:
            await ctx.channel.send(txt)
        database.new(ctx.author.id, RollTypes.Disadvantage.value, int(time()),
            [(dice.type, dice.value) for dice in roll.dices])

    @bot.hybrid_command()
    async def grouped_roll(ctx: commands.Context,
            dice_pool1: STANDARD_DND_DICES,
            amount_pool1: int,
            dice_pool2: STANDARD_DND_DICES = '',
            amount_pool2: int = 1,
            dice_pool3: STANDARD_DND_DICES = '',
            amount_pool3: int = 1,
            dice_pool4: STANDARD_DND_DICES = '',
            amount_pool4: int = 1):
        """ Roll at most 4 dice pools at once and sum their values.

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
        expression = f'{str(amount_pool1)}{str(dice_pool1)}'
        for dice, amount in [
                                (dice_pool2, amount_pool2),
                                (dice_pool3, amount_pool3),
                                (dice_pool4, amount_pool4),
                            ]:
            if dice != '':
                expression += f' {amount}{dice}'
        try:
            parsed_exp = parse_roll(f'{{{expression}}}')
        except InvalidInput as e:
            try:
                assert isinstance(ctx.interaction, discord.Interaction)
                await ctx.interaction.response.send_message(
                    f'Invalid input(s): {e.args[0]}')
            except:
                await ctx.channel.send(f'Invalid input(s): {e.args[0]}')
            return
        roll = roll_expression(parsed_exp[0])
        dice_values = result_string_from_groupedroll(roll)
        txt = (
            f'## {ctx.author.display_name} is doing a grouped roll:'
            f'\n{dice_values}\n **Totalling '
            f'🎲{sum([dice.value for dice in roll.dices])}'
            '**')
        try:
            assert isinstance(ctx.interaction, discord.Interaction)
            await ctx.interaction.response.send_message(txt)
        except:
            await ctx.channel.send(txt)
        database.new(ctx.author.id, RollTypes.Grouped.value, int(time()),
                     [(dice.type, dice.value) for dice in roll.dices])

    @bot.hybrid_command(aliases=['r'])
    async def custom_roll(ctx: commands.Context, *, expression: str):
        """ Execute one or many rolls of dices with a special dnd
        notation.
        The dices must be in NdNF form and divided by a space. N is an
        integer higher than 0 and F is either 'ad' or 'di' flag to
        signal an advantage or disadvantage roll, respectively, or
        ommited. If the first N is ommited it's implicitly understood
        as 1. For grouped rolls surroud the dices in curly braces {},
        grouped rolls can't contain dices with flags.

        Ex:
            'd8': One d8 roll.
            '2d10ad': One 2d10 roll with advantage.
            '{d8 2d4 2d2}': One grouped roll with d8, 2d4 and 2d2
                            summed up.
            '2d4 2d20di {2d2 3d6}': Multiple rolls in one expression. A
                                    'mixed' expression.

        Args:
            expression: Roll expression. EX: '2d6ad', '{2d8 2d12}'
        """
        try:
            parsed_exp = parse_roll(expression)
        except InvalidInput as e:
            try:
                assert isinstance(ctx.interaction, discord.Interaction)
                await ctx.interaction.response.send_message(
                    f'Invalid input(s): {e.args[0]}')
            except:
                await ctx.channel.send(f'Invalid input(s): {e.args[0]}')
            return
        rolls = [roll_expression(child_exp) for child_exp in parsed_exp]

        for roll in rolls:
            match roll.type:
                case RollTypes.Single:
                    txt = (
                        f'## {ctx.author.display_name} is rolling a '
                        f'{len(roll.dices) if len(roll.dices) > 1 else ''}'
                        f'd{roll.dices[0].type}.'
                        +(f'\n### Rolled 🎲{roll.dices[0].value}' if
                            len(roll.dices) == 0 else
                            f'\n-# Rolled {', '.join([str(dice.value)
                                for dice in roll.dices])}'
                            +f'\n**Totalling 🎲{sum([dice.value
                                for dice in roll.dices])}**'))
                case RollTypes.Advantage:
                    txt = (
                        f'## {ctx.author.display_name} is rolling a '
                        f'{len(roll.dices) if len(roll.dices) > 1 else ''}'
                        f'd{roll.dices[0].type} with advantage.'
                        f'\n-# Rolled {', '.join(str(dice.value)
                            for dice in roll.dices)}'
                        f'\n### Higher dice 🎲{max([dice.value
                            for dice in roll.dices])}')
                case RollTypes.Disadvantage:
                    txt = (
                        f'## {ctx.author.display_name} is rolling a '
                        f'{len(roll.dices) if len(roll.dices) > 1 else ''}'
                        f'd{roll.dices[0].type} with disadvantage.'
                        f'\n-# Rolled {', '.join(str(dice.value)
                            for dice in roll.dices)}'
                        f'\n### Lowest dice 🎲{min([dice.value
                            for dice in roll.dices])}')
                case _:
                    dice_values = result_string_from_groupedroll(roll)
                    txt = (
                        f'## {ctx.author.display_name} is doing a '
                        f'grouped roll:\n{dice_values[:200]}\n **Totalling '
                        f'🎲{sum([dice.value for dice in roll.dices])}'
                        '**')
            try:
                assert isinstance(ctx.interaction, discord.Interaction)
                await ctx.interaction.response.send_message(txt)
            except:
                await ctx.channel.send(txt)
            database.new(ctx.author.id, roll.type.value, int(time()),
                     [(dice.type, dice.value) for dice in roll.dices])

    @bot.hybrid_command()
    async def history(
            ctx: commands.Context,
            user: discord.User | discord.Member | None = None):
        """ See an user's roll history.

        Args:
            user: Leave it empty to see own roll history.
        """
        if user is None:
            user = ctx.author
        assert isinstance(user, discord.User|discord.Member)
        try:
            assert isinstance(ctx.interaction, discord.Interaction)
            await ctx.interaction.response.send_message(view=HistoryView(user))
        except:
            await ctx.channel.send(view=HistoryView(user))

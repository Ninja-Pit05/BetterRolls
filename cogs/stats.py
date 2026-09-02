""" Takes care of every aspect of players stats. From creation and storing to
editing and deletion.
"""
from enum import Enum
from dataclasses import dataclass

import discord
from discord import ui

from utils import Paginator, NextButton, PreviousButton, ReturnButton
from db import ConnectionManager, UsersDBInterface



class InvalidInput(Exception):
    """ Raised when input has an invalid type on validate_input() """
    pass

class OutOfLimits(Exception):
    """ Raised when input has an invalid size. """
    pass

class StatTypes(Enum):
    """ Enumeration of stat types. Equivalent to the Types lookup table."""
    Integer = 0
    Float = 1
    RangeInteger = 2
    RangeFloat = 3
    Text = 4
    LimitedText = 5

    def __getitem__(self, subscript: int):
        """ Allows subscription of StatTypes by their values. """
        return [self.Integer, self.Float, self.RangeInteger,
                self.RangeFloat, self.Text, self.LimitedText][subscript]


@dataclass
class Stat():
    """ Represents a stat object. """
    def __init__(self, id: int, label: str, user_id: int, type_id: int,
                value: str, min: int, max: int):
        self.id = id
        self.label = label
        self.user_id = user_id
        self.type = StatTypes(type_id)
        self.value = value
        self.min = min
        self.max = max
    
    def to_display(self):
        """ Returns the stat as a str ready to be displayed on discord. """
        match self.type:
            case StatTypes.RangeInteger | StatTypes.RangeFloat:
                if self.min == 0:
                    return f'{self.label}: {self.value}/{self.max}'
                return f'{self.label}: {self.min}/{self.value}/{self.max}'
            case _:
                return f'{self.label}: {self.value}'

    def validate(self, value: str):
        """ validates input and returns the transformed value. """
        if self.type in [StatTypes.Integer, StatTypes.RangeInteger]:
            try:
                _value = int(value)
            except:
                raise InvalidInput(f'Expected Integer, received {value}')
            if self.type == StatTypes.RangeInteger:
                if int(_value) < self.min or int(_value) > self.max:
                    raise OutOfLimits(f'Value range from {self.min} to'
                                      f' {self.max}. Received: {_value}')
            return _value
        if self.type in [StatTypes.Float, StatTypes.RangeFloat]:
            try:
                _value = float(value)
            except:
                raise InvalidInput(f'Expected Float, received {value}')
            if self.type == StatTypes.RangeFloat:
                if float(_value) < self.min or float(_value) > self.max:
                    raise OutOfLimits(f'Value range from {self.min} to'
                                      f' {self.max}. Received: {_value}')
            return _value
        if self.type == StatTypes.LimitedText:
            if len(value) < self.min or len(value) > self.max:
                raise OutOfLimits(f"Text size should be from {self.min} "
                                  f" to {self.max}. Received: {value}"
                                  f" ({len(value)} characters long.)")
        return value



class StatsDBInterface:
    """ Bridge to the relational database.
    Deals with tables related to stats: stat, and stattypes.
    """
    def __init__(self, file: str):
        self.file = file
        self.users_if = UsersDBInterface(self.file)

    def fetchall_from(self, user_id: int) -> list[Stat]:
        _id = self.users_if.get_surrogate(user_id)
        with ConnectionManager(self.file) as db:
            raw_stats = db.cursor.execute(
                'SELECT * FROM stats WHERE user_id = ?',
                [_id]).fetchall()
        return [Stat(*raw_stat) for raw_stat in raw_stats]

    def rem(self, stat_id: int) -> None:
        with ConnectionManager(self.file) as db:
            db.cursor.execute('DELETE FROM stats WHERE id = ?', [stat_id])
            db.connection.commit()

    def new(self, label: str, user_id: int, type_id: int,
            min: int|float, max: int|float) -> None:
        _id = self.users_if.get_surrogate(user_id)
        if _id is None:
            self.users_if.add_user(user_id)
            _id = self.users_if.get_surrogate(user_id)

        with ConnectionManager(self.file) as db:
            db.cursor.execute(
                'INSERT INTO stats VALUES(NULL, ?, ?, ?, ?, ?, ?)',
                [label, _id, type_id, 0, min, max])
            db.connection.commit()

    def set_value(self, stat_id: int, value: int|str|float) -> None:
        with ConnectionManager(self.file) as db:
            db.cursor.execute(
                'UPDATE stats SET value = ? WHERE id = ?',
                [value, stat_id])
            db.connection.commit()

    def edit(self, stat_id: int, label: str, type_id: int,
            min: int|float, max: int|float) -> None:
        with ConnectionManager(self.file) as db:
            db.cursor.execute(
                '''UPDATE stats 
                        SET label = ?
                            ,type_id = ?
                            ,min = ?
                            ,max = ?
                    WHERE id = ?''',
                [label, type_id, min, max, stat_id])
            db.connection.commit()


database = StatsDBInterface('database.db')


class DeepEditWindow(ui.LayoutView):
    """ To DEEP edit user's stats. """
    def __init__(self, user: discord.User, paginator: Paginator):
        super().__init__()

        container = ui.Container()
    
        class DeepEditModal(ui.Modal, title='Change stat'):
            """ Allows one to edit or add a stat. """
            def __init__(self, stat: Stat, user=None):
                super().__init__()
                self.stat = stat
                self.user = user
                self.label = ui.TextInput(default=stat.label)
                self.add_item(ui.Label(text='Label',
                                       component=self.label))
                self.type = ui.Select(options=
                    [discord.SelectOption(label=type.name,
                                          value=str(type.value))
                    for type in StatTypes])
                self.add_item(ui.Label(text='Type', component=self.type))
                self.min = ui.TextInput(default=str(stat.min))
                self.add_item(ui.Label(text='Min value', component=self.min))
                self.max = ui.TextInput(default=str(stat.max))
                self.add_item(ui.Label(text='Max value', component=self.max))
                if user is None:
                    self.delete = ui.Checkbox()
                    self.add_item(ui.Label(text='Delete Stat',
                                           component=self.delete))

            async def on_submit(self, interaction):
                # Error handling
                if self.type in [1,3]:
                    try:
                        float(self.min.value)
                        float(self.max.value)
                    except ValueError:
                        await interaction.response.send_message(
                            'Invalid min or max value. Expected Float',
                            f'received ({self.min}, {self.max})',
                            delete_after=5)
                        return
                elif self.type in [0,2]:
                    try:
                        int(self.min.value)
                        int(self.max.value)
                    except ValueError:
                        await interaction.response.send_message(
                            'Invalid min or max value. Expected Integer',
                            f'received ({self.min}, {self.max})',
                            delete_after=5)
                        return
                await interaction.response.defer()
                #DB updating.
                if self.user is None:
                    if self.delete.value is True:
                        database.rem(self.stat.id)
                        self.stop()
                        return
                    database.edit(self.stat.id, self.label.value,
                                  int(self.type.values[0]), int(self.min.value),
                                  int(self.max.value))
                    self.stop()
                    return
                database.new(self.label.value, self.user.id,
                             int(self.type.values[0]), int(self.min.value),
                             int(self.max.value))
                self.stop()
                return

        class EditStat(ui.Button):
            """ Opens the EditingModal. """
            def __init__(self, stat: Stat):
                super().__init__(label='✏️',
                                 style=discord.ButtonStyle.green)
                self.stat = stat
            async def callback(self, interaction):
                modal = DeepEditModal(self.stat)
                await interaction.response.send_modal(modal)
                await modal.wait()
                stats = database.fetchall_from(user.id)
                paginator = Paginator(stats,8)
                await interaction.edit_original_response(
                    view=DeepEditWindow(user, paginator))

        class AddStat(ui.Button):
            """ Opens the EditingModal. """
            def __init__(self, user: discord.User):
                self.user = user
                super().__init__(label='New Stat')
            async def callback(self, interaction):
                modal = DeepEditModal(Stat(0,'Stat label',0,0,'10',0,0),
                                      self.user)
                await interaction.response.send_modal(modal)
                await modal.wait()
                stats = database.fetchall_from(user.id)
                paginator = Paginator(stats,8)
                await interaction.edit_original_response(
                    view=DeepEditWindow(user, paginator))

        for item in paginator.current:
            container.add_item(ui.Section(
                item.to_display(), accessory=EditStat(item)))

        container.add_item(ui.ActionRow(
            AddStat(user), PreviousButton(user, paginator, DeepEditWindow),
            NextButton(user, paginator, DeepEditWindow),
            ReturnButton(user, paginator, EditStatsWindow)))
        self.add_item(container)


class EditStatsWindow(ui.LayoutView):
    """ Displays user's stats in a way that makes them easily editable.
    """
    def __init__(self, user: discord.User, paginator: Paginator):
        super().__init__()

        container = ui.Container()

        class EditStat(ui.Button):
            """ Opens the EditingModal. """
            def __init__(self, stat: Stat):
                super().__init__(label='✏️',
                                 style=discord.ButtonStyle.green)
                self.stat = stat
            async def callback(self, interaction):
                await interaction.response.send_modal(EditStatModal(self.stat))

        for item in paginator.current:
            container.add_item(ui.Section(
                item.to_display(), accessory=EditStat(item)))

        class EditStatModal(ui.Modal, title='Edit stat'):
            """ Allows one to edit a stat. """
            def __init__(self, stat: Stat):
                super().__init__()
                self.stat = stat
                self.input = ui.TextInput(default=stat.value)
                rang=''
                if stat.type in [StatTypes.RangeInteger, StatTypes.RangeFloat,
                                 StatTypes.LimitedText]:
                    rang = f'min {stat.min}, max {stat.min}'
                if stat.type in [StatTypes.Integer, StatTypes.RangeInteger]:
                    type_lb = 'Int'
                elif stat.type in [StatTypes.Float, StatTypes.RangeFloat]:
                    type_lb = 'Float'
                else: #stat.type in [StatTypes.Text, StatTypes.LimitedText]
                    type_lb = 'Text'
                self.add_item(ui.Label(text=f'Value {type_lb}. {rang}',
                    component=self.input))
            async def on_submit(self, interaction):
                try:
                    value = self.stat.validate(self.input.value)
                except (InvalidInput, OutOfLimits) as ex:
                    await interaction.response.send_message(
                        f'{ex}', delete_after=5)
                    return
                database.set_value(self.stat.id, value)
                stats = database.fetchall_from(user.id)
                paginator = Paginator(stats,8)
                await interaction.response.edit_message(
                    view=EditStatsWindow(user, paginator))


        class DeepEdit(ui.Button):
            """ Routes to EditStatsWindow. """
            def __init__(self):
                super().__init__(label='Deep Edit')
            async def callback(self, interaction):
                await interaction.response.edit_message(
                    view=DeepEditWindow(user, paginator))

        container.add_item(ui.ActionRow(
            DeepEdit(), PreviousButton(user, paginator, EditStatsWindow),
            NextButton(user, paginator, EditStatsWindow),
            ReturnButton(user, paginator, StatsWindow)))
        self.add_item(container)


class StatsWindow(ui.LayoutView):
    """ Displays user's stats. Disposes of buttons for pagination
    and navigation to editiding view."""
    def __init__(self, user: discord.User, paginator: Paginator):
        super().__init__()

        container = ui.Container()

        for item in paginator.current:
            container.add_item(ui.TextDisplay(item.to_display()))

        class Edit(ui.Button):
            """ Routes to EditStatsWindow. """
            def __init__(self):
                super().__init__(label='Edit')
            async def callback(self, interaction):
                await interaction.response.edit_message(
                    view=EditStatsWindow(user, paginator))

        container.add_item(ui.ActionRow(
            Edit(), PreviousButton(user, paginator, StatsWindow),
            NextButton(user, paginator, StatsWindow)))
        self.add_item(container)



async def setup(bot):
    """Loads this command into the given bot instance."""
    @bot.tree.command()
    async def stats(interaction, user: discord.User|None):
        """ Opens the stats window of a player.

        Args:
            user: Leave empty to see own stats windows.
        """
        if user is None:
            user = interaction.user
        assert user is not None #pyright happy
        stats = database.fetchall_from(user.id)
        paginator = Paginator(stats,8)
        await interaction.response.send_message(view=StatsWindow(
            user, paginator))

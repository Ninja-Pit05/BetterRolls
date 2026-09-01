""" Utilitary code used in multiple files. """
import discord
from discord import ui
from typing import Callable, Type


class Paginator():
    """ Automates paginating over a list of objects.
    
    Args:
        objects(list): Lit of objects to paginate over
        pg_size(int): Amount of objects in a single page.
    Methods:
        current(): Returns the current page.
        is_on_last(): Returns a boolean indicating if the paginator is
            on the last page.
        is_on_first(): Returns a boolean indicating if the paginator is
            on the first page.
        next(): Paginates to the next page (if possible) then returns
            self.current(), even if the pagination failed.
        previous(): Paginates to the previous page (if possible) then
            returns self.current(), even if the pagination failed.
    """
    def __init__(self, objects: list, pg_size: int = 10):
        self.objects = objects
        self.pg = 0
        self.pg_size = pg_size
    
    @property
    def current(self) -> list:
        """ List of object in the current page. """
        return self.objects[self.pg*self.pg_size:(self.pg+1)*self.pg_size]

    @property
    def is_on_last(self) -> bool:
        """ BOOL to indicate if it's in the last page. """
        return self.pg >= ((int(len(self.objects)/self.pg_size) - (
            0 if len(self.objects)%self.pg_size > 0 else 1)))

    @property
    def is_on_first(self) -> bool:
        """ BOOL to indicate if it's in the first page. """
        return self.pg == 0
    
    def next(self) -> list:
        """ Paginates to the next page and returns it. """
        if not self.is_on_last:
            self.pg += 1
        return self.current

    def previous(self) -> list:
        """ Paginates to the previous page and returns it. """
        if not self.is_on_first:
            self.pg -= 1
        return self.current


# -- Pagination buttons.
class NextButton(ui.Button):
    """ Paginates to next pg. """
    def __init__(self, user: discord.User, paginator: Paginator,
                 view: Type[ui.LayoutView]):
        self.user = user
        self.paginator = paginator
        self.target_view = view
        super().__init__(label='Next',
                         style=discord.ButtonStyle.blurple,
                         disabled=paginator.is_on_last)
    async def callback(self, interaction):
        self.paginator.next()
        await interaction.response.edit_message(
            view=self.target_view(self.user, self.paginator))


class PreviousButton(ui.Button):
    """ Paginates to previous pg. """
    def __init__(self, user: discord.User, paginator: Paginator,
                 view: Type[ui.LayoutView]):
        self.user = user
        self.paginator = paginator
        self.target_view = view
        super().__init__(label='Previous',
                         style=discord.ButtonStyle.blurple,
                         disabled=paginator.is_on_first)
    async def callback(self, interaction):
        self.paginator.previous()
        await interaction.response.edit_message(
            view=self.target_view(self.user, self.paginator))


class ReturnButton(ui.Button):
    """ Routes to previous view. """
    def __init__(self, user: discord.User, paginator: Paginator,
                 view: Type[ui.LayoutView]):
        self.user = user
        self.paginator = paginator
        self.target_view = view
        super().__init__(label='Return')
    async def callback(self, interaction):
        await interaction.response.edit_message(
            view=self.target_view(self.user, self.paginator))

def clamp(minimun: int, value: int, maximun: int):
    """ Clamps a value between a minimun and maximun value. """
    return max(minimun, min(maximun, value))

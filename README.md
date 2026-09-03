# BetterRolls
A simple discord bot that provides stats editing and dice rolling for rpg sessions. With standard, advantage, disadvantage and grouped rolls, rolling history and stats windows.

### This bot may be perfect for you if you need:
- The usual dice rolling mechanics with simple notation.
- A rolling tool that makes rolling easy and fast.
- Rolling that shows the individual value of each dice and the resulting roll.
- Full users rolling history.
- Simplified stat window with editable stats that can be altered by any of your players.
- Shared state (history and stats) trough multiple guilds.
- You want a base to build something on top of.

### This bot may not fit you if:
- You need even more dice rolling options and/or a more complex system.
- You need a stats winows with a more complex style.
- Local state (history and stats) down to individual guilds or channels.
- You need the stats window to be editable by a limited amount of whitelisted users.

# Getting started
Here we assume that you have python installed and that you've set a virtual environment to run the project.
### Creating your bot
First you must create an application in [Discord's Developer Portal](https://discord.com/developers/home). In your application got to Bot, reset your token, copy it and store it in a secure place.

If you want to allow prefix commands aside from application commands, turn the 'Message Content Intent' on at Bot > Privileged Gateway Intents. Be aware that discord is moving away from prefix commands and you may need pass trough a discord review if your bot has access to 10k+ users in total, so prefix commands are disencouraged.

Then go over to Installation, in Installation Contexts 'Guild Install' must be enabled. Down at Default Install Settings > Guild Install > Scopes add the application.commands and bot scopes.

Yet in Installation copy your bot install discord provided link at Install Link. Use this link to add bot to your bot to the guilds desired.
### Configuring the bot.
Download or clone the repo into your machine.
Copy or rename the ´.env.example´ file to ´.env´, and replace the dummy text at ´BOT_TOKEN´ with your bot token. Your file should look similar to this:
´´´
PREFIX=?
BOT_TOKEN='MTNgTXcnskCKSNAShsbc.SKCnjsd283.NsjghTFRSTT'
´´´
Alternatively, you can set those variables in your virtual environment.
Start the bot with 'python main.py'

If no errors were raised, you can test the bot with '?r d8'.
### Done
If you've followed all the steps correctly you should have a functional tool to make dice rolls with.

# Commands
Now that you got the bot running, what can you do?
## Dice rolling
The bot allows prefix commands and app commands to trigger commands. The bot's prefix is ´?´ unless you changed the PREFIX variable.
### Rolling with prefix commands.
For prefix commands you can simply add the dice you need after the bot's prefix + r. So to roll a d6:

´?r d6´

Would look like:

> **MangoDestroyer56 is rolling a d6.**

> Rolled 🎲2

You can roll multiple dices of the same type:

´?r 3d8´


The dice notation used here is pretty similar to the standard dice notation used.

The notation followed is ´NdNF´, where N is an integer higher than 0 and F is a flag.


The first N, when ommitted, is implicitly interpreted as a 1, and both N's are capped.

F is an optional flag to indicate rolls with advantage or disadvantage, 'ad' and 'di', respectively.

So an advantage roll would look like ´3d6ad´ for 3 dices 6 rollled with advantage. And an disadvantage roll ´2d12di´ for 2 dices 12 disadvantage rolls.

You can also make grouped rolls with different dice type by surrounding them in curly braces ´{}´ and spacing them with a space ´ ´.

So ´{d20 2d6 d8}´ would roll a dice 20, 2 dice 6, a dice 8 and sum their results. Grouped rolls do not accept flags and will trow an error if a flag is present in it.

### Rolling with application commands.
We tried to make rolling with application commands as simple and straight forward as possible. The app commands only accept standard dnd dices (d2, d4, d6, d8, d10, d12, d20, d100) and has the following app commands: 


#### /roll 'dice'
For single rolls with standard dnd dices. Ex: ´/roll d6´, ´/roll d20´.


#### /advantage_roll 'dice' 'amount'
For advantage rolls. An 'amount' of dices of type <dice> are rolled, their values displayed and the higher value one picked. If 'amount' is ommited, it is interpreted as 2.

EXx: ´/advantage_roll d6´, ´/advantage_roll d8 3´.


#### /disadvantage_roll 'dice' 'amount'
For disadvantage or advantage rolls. An 'amount' of dices of type 'dice' are rolled, their values displayed and the lower value one picked. If 'amount' is ommited, it is interpreted as 2.

EXx: ´/advantage_roll d6´, ´/advantage_roll d8 3´.


#### /grouped_roll 'dice_pool1' 'amount_pool1' 'dice_pool2' 'amount_pool2' 'dice_pool3' 'amount_pool3' 'dice_pool4' 'amount_pool4'
For grouped rolls. the 'dice_poolN's from 2 to 4 are optional and ignored if ommited. 'amount_poolN' from 2 to 4 have the default value of 1, so if 'dice_pool2' is set but 'amount_pool2' is not, a single dice of type 'dice_pool2' will be rolled.

Ex: ´/grouped_roll d6 5 d10´, ´/grouped_roll d2 3 d4 2 d6 1 d10´, ´/grouped_roll d20 2´


#### /custom_roll 'expression'
The other commands were thought to make a specific roll as fast as possible, this command can be as fast as them and allows to do dice rolling as if you were using the prefix '?r' method with all the options that it disposes of. So, if with prefix commands you would do ´?r 5d12ad´ or ´?r {2d4 d20}´, with application commands you would write ´/custom_roll 5d12ad´ or ´custom_roll {2d4 d20}´


### Dice history
You can also see al past rolls of any user with ´?history <user>´ or ´/history <user>´. The roll history displays the each dice roll, the final rolling results and the timestamp at which the rolling as made. Anyone can see eachothers rolling history.


## Stats
Sometimes you need something simple to keep your session stats and track player info. The bot has a simple, although really simplified, way of doing that. 

Use ´/stats´ to access your own list of stats, or, ´/stats <user>´ to access another use's list of stats.

The stat window have 3 modes: View, Edit and DeepEdit. When viewing, you can only see each stat value, but cannot edit them. By clicking in the button 'Edit' you will enter the Editing mode. You can now alter each stats value but not the stat's itselves. By clicking the 'Deep Edit' button you can now alter the stats itselves. You can add new stats, edit their types, their min and max values (if applicable) and can also remove a stat from the stat window.

All players can edit eachothers stats at any time, which is good if you have player who help each other to fill and edit stats. Not so good if you have some troller in you team.

The stats can have the following types: Integer, RangeInteger, Float, RangeFloat, Text and RangedText. Each type can only accept their respectfully data type when 'shallow' editing. Aside from that RangeInteger and RangeFloat will trown an error if the value inputed is higher or lower than their defined max and min values. RangedText takes the min and max value to define the minimal and maximun text lenght. For the other data types the min and max properties are ignored.


___
The bot is indeed a simple project, but i'm willing to improve it whenever i get some free time. So feel free to add to it and suggest improvements.

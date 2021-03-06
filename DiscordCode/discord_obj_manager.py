from post_to_discord_manager import ManageManager

ex = ManageManager('Discord Values .txt', 'Asynchronous Code File .py')

# The Discord Values file (txt) must be like shown below (More info for keys can be found on the Discord Bots area.
# you must create an app and add a bot. https://discord.com/developers/applications):

# To separate collections, use the '|' character

# put discord bot token here
# put the channel ids here. for now, sales listings or sales
# collection name here. can be found in the URL of the homepage of a collection.
# Discord embed icon URL or None
# RGB values r g b or None
# OS API Key
# EtherScan API Key
# Bot prefix or None
# Command Command Description (surrounded with double quotes). Command Description MUST end with 'To use, type: [usage]'
# where [usage] is showing how to use the command

# for example:
# -----discord_values.txt-----
# bot token
# sales_channel_id listings_channel_id | sales_channel_id
# the-nft | the-nft-2
# image.jpg | image2.jpg
# 0 0 0 | 255 255 255
# OS API key
# EtherScan API Key
# ! or ? or >> or... etc.
# example "this is an example command. To use, type: !command"

# Following the file, there is a necessary argument which is the name of the asynchronous code file that will be
# generated when the program is ran. This is a .py file which executes all the code and keeps the program running.

# example instantiator:
mm = ManageManager('discord_values_yachts.txt', 'asynchronous_discord_code_yachts.py')

import os
import re
import discord
# from discord.ext import commands
from discord.utils import get
from discord_slash import SlashCommand, SlashContext
from discord_slash.utils.manage_commands import create_choice, create_option
from dotenv import load_dotenv
from asyncio_mqtt import Client, Will
import asyncio

from time import sleep
import pdb

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = int(os.getenv('DISCORD_GUILD'))
CURRENT_ID = int(os.getenv('CURRENT_ID'))
ALL_ID = int(os.getenv('ALL_ID'))
CONTROL_ID = int(os.getenv('CONTROL_ID'))
TEST_ID = int(os.getenv('TEST_ID'))
MQTT_HOST = os.getenv('MQTT_HOST')
MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASS = os.getenv('MQTT_PASS')
MQTT_PORT = os.getenv('MQTT_PORT') or 1883
bind_ids = []

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

intents = discord.Intents.default()
intents.members = True
loop = asyncio.get_event_loop()
client = discord.Client(loop=loop, intents=intents)
slash = SlashCommand(client, sync_commands=True)

async def setup_mqtt():
  async with Client(
    MQTT_HOST,
    username=MQTT_USER,
    password=MQTT_PASS,
    will=Will('discord/status', 'off')
  ) as mqtt_client:
    async with mqtt_client.filtered_messages('discord/#') as messages:
      await mqtt_client.subscribe("discord/av")
      await mqtt_client.subscribe("discord/av-current")
      await mqtt_client.subscribe("discord/command")
      await mqtt_client.subscribe("discord/test")
      await mqtt_client.publish('discord/status', 'on')
      print('MQTT ready')
      async for message in messages:
        txt = message.payload.decode()
        print(f'MQTT ({message.topic}): {txt}')
        guild = next(g for g in client.guilds if g.id == GUILD)
        if message.topic == 'discord/av':
          channel = guild.get_channel(ALL_ID)
        elif message.topic == 'discord/av-current':
          channel = guild.get_channel(CURRENT_ID)
        elif message.topic == 'discord/control':
          channel = guild.get_channel(CONTROL_ID)
        elif message.topic == 'discord/test':
          channel = guild.get_channel(TEST_ID)
        await channel.send(content=f'MQTT: {txt}', delete_after=10)


@client.event
async def on_ready():
  for guild in client.guilds:
    if guild.name == GUILD:
      break
  print(f'{client.user} has connected to Discord at {guild.name}!')

@client.event
async def on_member_join(member):
  await member.create_dm()
  await member.dm_channel.send(
    f'Hi {member.name}, welcome to the Discord server!'
  )

@client.event
async def on_typing(channel, user, when):
  print(f'[{when}] {user.name} typing in {channel.name}')

@client.event
async def on_raw_reaction_add(payload):
  if payload.member == client.user:
    return

  guild = next(g for g in client.guilds if g.id == payload.guild_id)
  user = guild.get_member(payload.user_id)
  channel = guild.get_channel(payload.channel_id)
  msg = await channel.fetch_message(payload.message_id)
  msg = re.sub(r'\n*.^>>>.*', '', msg.content, flags=re.S|re.M)
  print(f'{user.name} added reaction {payload.emoji.name} (in {channel.name}) to {msg}')

  if payload.message_id in bind_ids:
    print('Binding')

    role = get(guild.roles, name='Current')
    channel = client.get_channel(CURRENT_ID)

    if payload.emoji.name == '👍':
      print(f'Add {payload.member.name} to current')
      await payload.member.add_roles(role)
      await channel.send(content=f'{payload.member.name} on current.', delete_after=30)
      print(f'Added {payload.member.name} to current')
    elif payload.emoji.name == '⛔':
      print(f'Remove {payload.member.name} from current')
      await payload.member.remove_roles(role)
      await channel.send(content=f'{payload.member.name} left current.', delete_after=30)
      print(f'Removed {payload.member.name} from current')

@client.event
async def on_raw_reaction_remove(payload):
  guild = next(g for g in client.guilds if g.id == payload.guild_id)
  user = guild.get_member(payload.user_id)
  channel = guild.get_channel(payload.channel_id)
  msg = await channel.fetch_message(payload.message_id)
  msg = re.sub(r'\n*^>>>.*', '', msg.content, flags=re.S|re.M)
  print(f'{user.name} removed reaction {payload.emoji.name} (in {channel.name}) from {msg}')

@client.event
async def on_message(message):
  if message.author == client.user:
    return

  if message.content == '!a':
    msg = await message.channel.send(f'Adding {message.author.name}')
    print(f'Add {message.author.name} to current')
    role = get(message.guild.roles, name='Current')
    await message.author.add_roles(role)
    await msg.edit(content=f'Added {message.author.name} to Current')
    await message.delete()

  elif message.content == '!r':
    msg = await message.channel.send(f'Removing {message.author.name}')
    print(f'Remove {message.author.name} from current')
    role = get(message.guild.roles, name='Current')
    await message.author.remove_roles(role)
    await msg.edit(content=f'Removed {message.author.name} from Current')
    await message.delete()
  
  elif message.content.startswith('!t'):
    # publish.single('discord/test', message.content.replace('!t', ''), hostname=MQTT_HOST)
    # mqtt_client.publish('discord/test', message.content.replace('!t ', ''))
    async with Client(MQTT_HOST,
      username=MQTT_USER,
      password=MQTT_PASS) as mqtt_client:
      await mqtt_client.publish(
        'discord/test',
        payload=message.content.replace('!t ', '').encode()
      )

  if type(message.channel) == discord.channel.TextChannel:
    if message.channel.id == TEST_ID:
      print(f'Mesasge in {message.channel.name} (from {message.author.name}): {message.content}')
    elif message.channel.id == CONTROL_ID:
      print(f'Control Mesasge (from {message.author.name}): {message.content}')
      # if message.content == 'start':
      # elif message.content == 'shutdown':
  elif type(message.channel) == discord.channel.DMChannel:
    if message.author.id == 488739970979463173:
      channel = client.get_channel(ALL_ID)
      if message.content.startswith('!say '):
        msg = await channel.send(message.content.replace('!say ',''))
        print(f'Said {msg}')
      elif message.content.startswith('!ask '):
        msg = message.content.replace('!ask ','')
        msg = await channel.send(content=f'{msg}\n\n>>> 👍 Yes\n⛔ No')
        await msg.add_reaction('👍')
        await msg.add_reaction('⛔')
        print(f'Asked {msg}')
        bind_ids.append(msg.id)
      return
    print(f'Direct Mesasge from {message.author.name}: {message.content}')

@slash.slash(
  name="start",
  description="[control channel] Start the AV System",
  guild_ids=[GUILD]
)
async def _start(ctx:SlashContext):
  if ctx.channel.id == CONTROL_ID:
    await ctx.send(f'Starting AV for {ctx.author.name}')
  else:
    await ctx.send('You must be in the `control` channel to use this.')

@slash.slash(
  name="shutdown",
  description="[control channel] Shutdown the AV System",
  guild_ids=[GUILD]
)
async def _start(ctx:SlashContext):
  if ctx.channel.id == CONTROL_ID:
    await ctx.send(f'Shutting down AV for {ctx.author.name}')
  else:
    await ctx.send('You must be in the `control` channel to use this.')

@slash.slash(
  name="prepare",
  description="[control channel] Prepares ProPresenter",
  guild_ids=[GUILD],
  options=[
    create_option(
      name="praise",
      description="Song of Praise #",
      required=False,
      option_type=4 # see https://discord.com/developers/docs/interactions/application-commands#application-command-object-application-command-option-type
    ),
    create_option(
      name="opening",
      description="Opening Hymn #",
      required=False,
      option_type=4 # see https://discord.com/developers/docs/interactions/application-commands#application-command-object-application-command-option-type
    ),
    create_option(
      name="closing",
      description="Closing Hymn #",
      required=False,
      option_type=4 # see https://discord.com/developers/docs/interactions/application-commands#application-command-object-application-command-option-type
    ),
    create_option(
      name="scripture",
      description="Scripture Verse (reference)",
      required=False,
      option_type=3 # see https://discord.com/developers/docs/interactions/application-commands#application-command-object-application-command-option-type
    )
  ]
)
async def _prep(ctx:SlashContext, praise:int=-1, opening:int=-1, closing:int=-1, scripture:str=''):
  if ctx.channel.id == CONTROL_ID:
    await ctx.send(f'Prepare ProPresenter for {ctx.author.name} with:\n#{praise} for Song of Praise\n#{opening} for Opening Hymn\n#{closing} for Closing Hymn\n{scripture} for Scripture')
    await ctx.send(f'Don\'t forget to get the offering slide - I can\'t do that myself yet.')
  else:
    await ctx.send('You must be in the `control` channel to use this.')

loop.create_task(setup_mqtt())
try:
  loop.run_until_complete(client.start(TOKEN))
except KeyboardInterrupt:
  print('Quitting')
  quit()

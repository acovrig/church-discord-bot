import os
from time import sleep
import re
import discord
from discord.ext import commands
from discord.utils import get
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
from threading import Thread
import asyncio

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

intents = discord.Intents.default()
intents.members = True

# client = commands.Bot(command_prefix=',', intents=intents)
client = discord.Client(intents=intents)
bot = commands.Bot(command_prefix='!')


async def final_send(channel, msg):
  print(f'sending {msg} to {channel}')
  await channel.send(content=msg, delete_after=10)

def send_discord_message(channel, msg):
  print(f'que {msg}')
  asyncio.new_event_loop().create_task(final_send(channel, msg))


def on_mqtt_connect(client, userdata, flags, rc):
  print(f'Connected to MQTT: {str(rc)}')
  client.subscribe('discord/av')
  client.subscribe('discord/av-current')
  client.subscribe('discord/command')
  client.subscribe('discord/test')
  client.publish('discord/status', 'on')

def on_mqtt_message(mqtt_client, userdata, msg):
  txt = msg.payload.decode('utf-8')
  # txt = str(txt)
  print(f'Got MQTT {msg.topic}: {txt}')
  guild = next(g for g in client.guilds if g.id == GUILD)
  if msg.topic == 'discord/av':
    channel = guild.get_channel(ALL_ID)
  elif msg.topic == 'discord/av-current':
    channel = guild.get_channel(CURRENT_ID)
  elif msg.topic == 'discord/control':
    channel = guild.get_channel(CONTROL_ID)
  elif msg.topic == 'discord/test':
    channel = guild.get_channel(TEST_ID)

  # msg_thread = Thread(target=channel.send, args={'content': f'MQTT: {txt}', 'delete_after': 10})
  msg_thread = Thread(target=send_discord_message, args=(channel, f'MQTT: {txt}'))
  msg_thread.daemon = True
  msg_thread.start()
  # asyncio.run(channel.send(content=f'MQTT: {txt}', delete_after=10))
  # loop = asyncio.new_event_loop()
  # loop.run_until_complete(channel.send(content=f'MQTT: {txt}', delete_after=10))
  # loop = asyncio.new_event_loop()
  # asyncio.set_event_loop(loop)
  # loop.run_until_complete(send_discord_message(channel, f'MQTT: {txt}'))


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
    mqtt_client.publish('discord/test', message.content.replace('!t ', ''))

  if type(message.channel) == discord.channel.TextChannel:
    if message.channel.name == 'testing':
      print(f'Mesasge in {message.channel.name} (from {message.author.name}): {message.content}')
    elif message.channel.name == 'current-av':
      print(f'Mesasge in {message.channel.name} (from {message.author.name}): {message.content}')
    elif message.channel.name == 'av':
      print(f'Mesasge in {message.channel.name} (from {message.author.name}): {message.content}')
    else:
      print(f'Mesasge in {message.channel.name} (from {message.author.name}): {message.content}')
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

def run_discord():
  client.run(TOKEN)


mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(MQTT_USER, password=MQTT_PASS)
mqtt_client.on_connect = on_mqtt_connect
mqtt_client.on_message = on_mqtt_message
mqtt_client.will_set('discord/status', 'off')
mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)

mqtt_thread = Thread(target=mqtt_client.loop_forever)
discord_thread = Thread(target=run_discord)

mqtt_thread.daemon = True
discord_thread.daemon = True
mqtt_thread.start()
discord_thread.start()

try:
  while True:
    sleep(1)
except KeyboardInterrupt:
  print('Quitting')
  quit()

# mqtt_thread.join()
# print('mqtt exited')
# discord_thread.join()
# print('full exit')
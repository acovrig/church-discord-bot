import os
from tempfile import NamedTemporaryFile
import re
import json
import discord
from discord.utils import get
from discord_slash import SlashCommand, SlashContext
from discord_slash.utils.manage_commands import create_choice, create_option
from dotenv import load_dotenv
from asyncio_mqtt import Client, Will
import asyncio
import lxml.html
import requests
import PyPDF2
from tika import parser
from datetime import datetime

from cal import run_cal, get_creds as refresh_cal
from yt_desc import run_yt, get_creds as refresh_yt
from people import People

from time import sleep
import pdb

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('DISCORD_GUILD_ID'))
CURRENT_ID = int(os.getenv('CURRENT_ID'))
ALL_ID = int(os.getenv('ALL_ID'))
CONTROL_ID = int(os.getenv('CONTROL_ID'))
TEST_ID = int(os.getenv('TEST_ID'))
MQTT_HOST = os.getenv('MQTT_HOST')
MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASS = os.getenv('MQTT_PASS')
MQTT_PORT = os.getenv('MQTT_PORT') or 1883
GUILD = None
bind_ids = []

if os.name == 'nt':
  asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

intents = discord.Intents.default()
intents.members = True
# loop = asyncio.get_event_loop()
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
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
      await mqtt_client.subscribe("discord/control")
      await mqtt_client.subscribe("discord/test")
      await mqtt_client.publish('discord/status', 'on')
      print('MQTT ready')
      async for message in messages:
        channel = None
        txt = message.payload.decode()
        print(f'MQTT ({message.topic}): {txt}')
        if message.topic == 'discord/av':
          channel = GUILD.get_channel(ALL_ID)
        elif message.topic == 'discord/av-current':
          channel = GUILD.get_channel(CURRENT_ID)
        elif message.topic == 'discord/control':
          channel = GUILD.get_channel(CONTROL_ID)
        elif message.topic == 'discord/test':
          channel = GUILD.get_channel(TEST_ID)
        elif message.topic == 'discord/command':
          if txt == 'update_youtube':
            print('Updating YouTube')
            msg = await GUILD.get_channel(CURRENT_ID).send(content=f'Updating YouTube Description')
            await run_yt(msg)
          elif txt == 'parse':
            url = get_url()
            print(f'Parsing {url}')
            if url != None:
              bulletin = parse_pdf(url)
              print(bulletin)
              await mqtt_bulletin(bulletin)
          elif txt == 'schedule':
            await parse_schedule(True)
        if channel != None:
          await channel.send(content=f'MQTT: {txt}', delete_after=10)


@client.event
async def on_ready():
  global GUILD
  for guild in client.guilds:
    if guild.id == GUILD_ID:
      GUILD = guild
      break
  print(f'{client.user} has connected to Discord at {guild.name}!')

@client.event
async def on_member_join(member):
  await member.create_dm()
  await member.dm_channel.send(
    f'Hi {member.display_name}, welcome to the Discord server!'
  )

@client.event
async def on_raw_reaction_add(payload):
  if payload.member == client.user:
    return

  guild = next(g for g in client.guilds if g.id == payload.guild_id)
  user = guild.get_member(payload.user_id)
  channel = guild.get_channel(payload.channel_id)
  msg = await channel.fetch_message(payload.message_id)
  msg = re.sub(r'\n*.^>>>.*', '', msg.content, flags=re.S|re.M)
  print(f'{user.display_name} added reaction {payload.emoji.name} (in {channel.name}) to {msg}')

  if payload.message_id in bind_ids:
    print('Binding')

    role = get(guild.roles, name='Current')
    channel = client.get_channel(CURRENT_ID)

    if payload.emoji.name == '👍':
      print(f'Add {payload.member.display_name} to current')
      await payload.member.add_roles(role)
      await channel.send(content=f'{payload.member.display_name} on current.', delete_after=30)
      print(f'Added {payload.member.display_name} to current')
    elif payload.emoji.name == '⛔':
      print(f'Remove {payload.member.display_name} from current')
      await payload.member.remove_roles(role)
      await channel.send(content=f'{payload.member.display_name} left current.', delete_after=30)
      print(f'Removed {payload.member.display_name} from current')

@client.event
async def on_raw_reaction_remove(payload):
  guild = next(g for g in client.guilds if g.id == payload.guild_id)
  user = guild.get_member(payload.user_id)
  channel = guild.get_channel(payload.channel_id)
  msg = await channel.fetch_message(payload.message_id)
  msg = re.sub(r'\n*^>>>.*', '', msg.content, flags=re.S|re.M)
  print(f'{user.display_name} removed reaction {payload.emoji.name} (in {channel.name}) from {msg}')

@client.event
async def on_message(message):
  if message.author == client.user:
    return

  if message.content == '!a':
    msg = await message.channel.send(f'Adding {message.author.display_name}')
    print(f'Add {message.author.display_name} to current')
    role = get(message.guild.roles, name='Current')
    await message.author.add_roles(role)
    await msg.edit(content=f'Added {message.author.display_name} to Current')
    await message.delete()

  elif message.content == '!r':
    msg = await message.channel.send(f'Removing {message.author.display_name}')
    print(f'Remove {message.author.display_name} from current')
    role = get(message.guild.roles, name='Current')
    await message.author.remove_roles(role)
    await msg.edit(content=f'Removed {message.author.display_name} from Current')
    await message.delete()

  if type(message.channel) == discord.channel.TextChannel:
    if message.channel.id == TEST_ID:
      print(f'Mesasge in {message.channel.name} (from {message.author.display_name}): {message.content}')
    elif message.channel.id == CONTROL_ID:
      print(f'Control Mesasge (from {message.author.display_name}): {message.content}')
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
      elif message.content == '!clear control':
        chan = client.get_channel(CONTROL_ID)
        his = await chan.history().flatten()
        for m in his:
          await m.delete()
        await message.channel.send(content=f'Cleared {len(his)} messges.')
      return
    print(f'Direct Mesasge from {message.author.display_name}: {message.content}')

@slash.slash(
  name="start",
  description="[control channel] Start the AV System",
  guild_ids=[GUILD_ID]
)
async def _start(ctx:SlashContext):
  if ctx.channel.id == CONTROL_ID:
    async with Client(MQTT_HOST,
      username=MQTT_USER,
      password=MQTT_PASS) as mqtt_client:
      await mqtt_client.publish(
        'av',
        payload='start AV'
      )
    await ctx.send(f'Starting AV', delete_after=10)
  else:
    await ctx.send('You must be in the `control` channel to use this.', delete_after=30)

@slash.slash(
  name="shutdown",
  description="[control channel] Shutdown the AV System",
  guild_ids=[GUILD_ID]
)
async def _stop(ctx:SlashContext):
  if ctx.channel.id == CONTROL_ID:
    await ctx.send(f'Shutting down AV', delete_after=10)
    async with Client(MQTT_HOST,
      username=MQTT_USER,
      password=MQTT_PASS) as mqtt_client:
      await mqtt_client.publish( 'av', payload='stop AV' )
  else:
    await ctx.send('You must be in the `control` channel to use this.', delete_after=30)

@slash.slash(
  name="parse",
  description="[control channel] Parses the PDF for ProPresenter",
  guild_ids=[GUILD_ID],
  options=[
    create_option(
      name="url",
      description="URL of the PDF to parse",
      required=False,
      option_type=3
    )
  ]
)
async def _parse(ctx:SlashContext, url:str=''):
  if ctx.channel.id == CONTROL_ID:
    if url == '':
      msg = await ctx.send(f'🤔 Getting URL (should be quick)')
      url = get_url()
      if url == None:
        await msg.edit(content=f'😞 Unable to find PDF URL', delete_after=30)
        return
      await msg.edit(content=f'🧐 Parsing {url} (takes ~30 seconds)')
    else:
      msg = await ctx.send(f'🧐 Parsing {url} (takes ~30 seconds)')

    bulletin = parse_pdf(url)
    print(bulletin)

    list_msg = format_bulletin(bulletin)

    await mqtt_bulletin(bulletin)

    await msg.edit(content=list_msg)
  else:
    await ctx.send('😱 You must be in the `control` channel to use this.', delete_after=30)

@slash.slash(
  name="schedule",
  description="[control channel] Parses the calendar and bulletin, adjusts permissions.",
  guild_ids=[GUILD_ID],
  options=[]
)
async def _schedule(ctx:SlashContext):
  if ctx.channel.id == CONTROL_ID:
    msg = await ctx.send(f'🧐 Reading calendar and PDF', delete_after=30)
    list_msg = await parse_schedule(True)
    await msg.edit(content=f'👍 Schedule [parsed and sent]({list_msg.jump_url}) to the [current-av](https://discord.com/channels/947230453742600222/947230847474475008) channel.', delete_after=30)
  else:
    await ctx.send('😱 You must be in the `control` channel to use this.', delete_after=30)

@slash.slash(
  name="cam",
  description="[control channel] Move the camera",
  guild_ids=[GUILD_ID],
  options=[
    create_option(
      name="position",
      description="Position to move to",
      required=True,
      option_type=3,
      choices=[
        {"name": "Pulpit", "value": "pulpit"},
        {"name": "Pulpit Close", "value": "pulpit_zoom"},
        {"name": "Choir", "value": "choir"},
        {"name": "Stage", "value": "stage"},
        {"name": "Wide", "value": "wide"},
        {"name": "Children's Story", "value": "childrens_story"}
      ]
    )
  ]
)
async def _cam(ctx:SlashContext, position):
  if ctx.channel.id == CONTROL_ID:
    await ctx.send(f'Moving Cam to {position}', delete_after=10)
    async with Client(MQTT_HOST,
      username=MQTT_USER,
      password=MQTT_PASS) as mqtt_client:
      await mqtt_client.publish( 'av', payload=f'cam {position}')
  else:
    await ctx.send('You must be in the `control` channel to use this.', delete_after=30)


def get_url():
  try:
    html = requests.get('https://sgsda.org/document_groups/2346').text
    page = lxml.html.document_fromstring(html)
    href = page.xpath('//*[@id="document_group"]/div/table//td//a')[0].attrib['href']
    href = f'https://sgsda.org{href}'
  except:
    print('Failed to get URL')
    href = None
  return href

def parse_pdf(file):
  del_file = True
  if isinstance(file, str):
    if file.startswith('http'):
      r = requests.get(file, headers={'User-Agent': 'Mozilla/5.0'})
      fdst = NamedTemporaryFile(delete=False)
      fdst.write(r.content)
      fdst.close()
      file = fdst.name
    elif os.path.exists(file):
      del_file = False
  else:
    file = file.name
  print(f'Parse PDF {file}')
  raw = parser.from_file(file)
  if del_file:
    os.unlink(file)
  txt = raw['content']
  chapters = []
  parse_date = None
  iso_date = None
  i = 0
  for line in txt.split('\n'):
    # print(f'i: {i}, len: {len(chapters)}, line: "{line.strip()}"')
    m = re.search(r'^(.+?)(?:\.|…|\s){5,}(.+$)', line.strip())
    date_re = re.search(r'^[a-zA-Z]+? [0-9]+, [0-9]{4} [0-9]+:[0-9]+ ', line.strip())
    stripped_line = re.sub(r'[\u2018\u2019]', "'", re.sub(r'[\u201C\u201D]', '"', line)).strip()
    if m != None and (len(chapters) == 0 or i < 7):
      i = 1
      if re.sub(r'[\u2018\u2019]', "'", re.sub(r'[\u201C\u201D]', '"', m.group(1))).strip() != 'Prelude':
        chapters.append({
          'name': re.sub(r'[\u2018\u2019]', "'", re.sub(r'[\u201C\u201D]', '"', m.group(1))).strip(),
          'who': re.sub(r'[\u2018\u2019]', "'", re.sub(r'[\u201C\u201D]', '"', m.group(2))).strip(),
          'info': '',
          'start': '10:00'
        })
        # print(chapters[-1])
    elif date_re != None:
      parse_date = datetime.strptime(date_re.group(0).strip(), r'%B %d, %Y %H:%M')
      iso_date = datetime.strftime(parse_date, r'%Y-%m-%d')
      parse_date = datetime.strftime(parse_date, r'%B %d, %Y')
    elif len(chapters) > 0:
      e = chapters.pop()

      if e['info'] != '':
        chapters.append(e)
      elif i < 4 and not stripped_line.startswith("Welcome! We're so glad you're here.") and not stripped_line.startswith('Piano: ') and not stripped_line.startswith('Organ: '):
        e = e | {'info': stripped_line}
        chapters.append(e)
        # print(f'info: "' + chapters[-1]['info'] + '"')
    i += 1
  if parse_date == None or iso_date == None:
    iso_date = os.path.basename(file).replace('.pdf', '')
    parse_date = datetime.strptime(iso_date, r'%Y-%m-%d').strftime(r'%B %d, %Y')
  return {"chapters": chapters, "date": parse_date, "iso_date": iso_date}

def format_bulletin(bulletin):
  datestr = bulletin['date']
  try:
    sop = next(e for e in bulletin['chapters'] if e['name'] == 'Song of Praise')
    sop = re.search(r'^#(\d+) ', sop['info'])
    if sop != None:
      sop = sop.group(1)
  except StopIteration:
    sop = None

  try:
    oh = next(e for e in bulletin['chapters'] if e['name'] == 'Opening Hymn')
    oh = re.search(r'^#(\d+) ', oh['info'])
    if oh != None:
      oh = oh.group(1)
  except StopIteration:
    oh = None

  try:
    ch = next(e for e in bulletin['chapters'] if e['name'] == 'Closing Hymn')
    ch = re.search(r'^#(\d+) ', ch['info'])
    if ch != None:
      ch = ch.group(1)
  except StopIteration:
    ch = None

  try:
    script = next(e for e in bulletin['chapters'] if e['name'] == 'Scripture')
    script = script['info']
  except StopIteration:
    script = None

  try:
    offer = next(e for e in bulletin['chapters'] if e['name'] == 'Offering Appeal')
    offer = offer['info']
  except StopIteration:
    offer = None

  return f'👀 Bulletin as I read it (for {datestr}):\n{sop} - Song of Praise\n{oh} - Opening Hymn\n{offer} - Offering\n{script} - Scripture\n{ch} - Closing Hymn'

async def parse_schedule(force=False):
  if not force:
    await asyncio.sleep(10)
  while True:
    nowstr = datetime.now().strftime('%A %H %M')
    if nowstr == 'Friday 19 00' or force:
      techs = []
      for tech in run_cal():
        try:
          techs.append({'name': tech, 'id': People[tech].value})
        except:
          print(f'Skipping unknown tech"{tech}"')
      techs = list({v['id']:v for v in techs}.values())

      role = get(GUILD.roles, name='Current')
      for member in role.members:
        if member.id not in list(map(lambda x: x['id'], techs)):
          print(f'Remove {member.display_name} from current')
          await member.remove_roles(role)
      for tech in techs:
        if tech['id'] not in list(map(lambda x: x.id, role.members)):
          print(f"Add {tech['name']} ({tech['id']}) to current")
          member = GUILD.get_member(tech['id'])
          if member == None:
            print(f"Member {tech['name']} ({tech['id']}) not found in {GUILD.name} ({GUILD.id}).")
          else:
            await member.add_roles(role)
        else:
          print(f"{tech['name']} ({tech['id']}) already in current.")

      print('Parsing bulletin per schedule')
      bulletin = parse_pdf(get_url())
      await mqtt_bulletin(bulletin)
      msg = await client.get_channel(CURRENT_ID).send(content=format_bulletin(bulletin))
      print(bulletin)

      if force:
        print(f'Parse forced, exiting loop')
        return msg
      await asyncio.sleep(500)
    else:
      await asyncio.sleep(30)

async def mqtt_bulletin(bulletin):
  bulletin['chapters'].insert(0, {'name': 'start', 'start': '10:00'})
  bulletin['chapters'].append({'name': 'end', 'start': '12:00'})
  async with Client(MQTT_HOST,
    username=MQTT_USER,
    password=MQTT_PASS) as mqtt_client:
    await mqtt_client.publish( 'bulletin_json', payload=json.dumps(bulletin))

async def refresh_tokens():
  while True:
    refresh_cal(True)
    refresh_yt(True)
    await asyncio.sleep(60*30) # run every 30min

async def initTika():
  fdst = NamedTemporaryFile(delete=False)
  fdst.close()
  parser.from_file(fdst.name)
  os.unlink(fdst.name)


async def testfunc():
  await asyncio.sleep(5)
  # for fn in sorted(os.listdir(os.path.join('z:',os.sep,'projects','church','toArchive','pdf'))):
  #   if datetime.strptime(fn.replace('.pdf', ''), r'%Y-%m-%d') < datetime.strptime('2018-09-15', r'%Y-%m-%d'):
  #     continue
  #   bulletin = parse_pdf(os.path.join('z:',os.sep,'projects','church','toArchive','pdf',fn))
  #   print(bulletin)
  #   await mqtt_bulletin(bulletin)
  #   await asyncio.sleep(0.1)


def startup():
  loop.create_task(setup_mqtt())
  loop.create_task(parse_schedule())
  loop.create_task(refresh_tokens())
  loop.create_task(initTika())
  try:
    loop.run_until_complete(client.start(TOKEN))
  except KeyboardInterrupt:
    print('Quitting')
    # for guild in client.guilds:
    #   guild.get_channel(947230453742600227).disconnect()
    quit()

if __name__ == '__main__':
  startup()
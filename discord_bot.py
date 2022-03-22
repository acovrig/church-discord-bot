from datetime import datetime, timedelta
from main import startup
from cal import run_cal
from people import People
from bulletin_db import BulletinDB

class mockHass:
  def Hass(self):
    print('Mocked Hass')

  def log(self, l):
    print(l)

try:
  import appdaemon.plugins.hass.hassapi as hass
except:
  hass = mockHass

# class DiscordBot(hass.Hass):
class DiscordBot:
  def __init__(self):
    self.log('Starting main')
    startup(self)

    # techs = run_cal(self)
    # ids = list(map(lambda x: People[x].value, techs))
    # ids = list(set(ids))
    # print(ids)

    # sab = 5 - datetime.now().weekday()
    # sab = 7 - sab
    # sab = datetime.now() - timedelta(sab)
    # sab = sab.date()
    # bdb = BulletinDB(self)
    # lst = bdb.get_date(sab)
    # print(lst)
    self.log('Main done')

  def log(self, s):
    print(s)

db = DiscordBot()
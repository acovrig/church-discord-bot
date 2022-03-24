import os
from dotenv import load_dotenv
from datetime import timedelta
import mysql.connector

class BulletinDB:
  def __init__(self):
    print('Init DB')
    load_dotenv()
    self.db = mysql.connector.connect(
      host=os.getenv('MYSQL_HOST'),
      user=os.getenv('MYSQL_USER'),
      password=os.getenv('MYSQL_PASS'),
      database=os.getenv('MYSQL_DB')
    )
    self.cursor = self.db.cursor(dictionary=True)
  
  def get_date(self, date):
    self.cursor.execute('SELECT name,who,info,start FROM bulletin WHERE date=%s AND name != %s;', (date,'end'))
    res = self.cursor.fetchall()
    ss = res[0]['start']
    del res[0]
    for x in res:
      d = str(x['start'] - ss)
      x['ss'] = d
    
    return res
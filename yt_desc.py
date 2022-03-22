from __future__ import print_function

import datetime
import os.path
from re import sub

from bulletin_db import BulletinDB
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from discord import Embed

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']


async def run_yt(hass, msg=None):
  """Shows basic usage of the Google Calendar API.
  prints the start and name of the next 10 events on the user's calendar.
  """
  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists('token-yt.json'):
    creds = Credentials.from_authorized_user_file('token-yt.json', SCOPES)
  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
      creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open('token-yt.json', 'w') as token:
      token.write(creds.to_json())

  try:
    service = build('youtube', 'v3', credentials=creds)
    
    fri = 4 - datetime.now().weekday()
    if fri <= 0:
      fri += 7
    fri = 7 - fri
    fri = datetime.now() - timedelta(fri)
    fri = fri.isoformat() + 'Z'
    
    vids = service.search().list(
      part='snippet',
      channelId="UCnJGTc0XKdRMvuzNF5odxyg",
      publishedAfter=fri
    ).execute()
    vids = vids.get('items', [])

    if not vids:
      hass.log('No videos found.')
      if msg != None:
        await msg.edit(content=f'🛑 No videos found to update.')
      return

    vid = vids[0].get('id', {}).get('videoId')
    hass.log(f"Found YT VID: {vid}")
    if msg != None:
      await msg.edit(content=f'🎥 Found https://youtu.be/{vid}:')

    video = service.videos().list(
      part='snippet,contentDetails,statistics',
      id=vid
    ).execute()
    video = video.get('items', [])
    if not video:
      hass.log(f'Unable to get vid {vid}.')
      if msg != None:
        await msg.edit(content=f'🛑 Unable to get vid {vid}.')
      return

    video = video[0]
    # hass.log(video)

    title = video.get('snippet', {}).get('title', 'Church Service')
    catId = video.get('snippet', {}).get('categoryId', '19')
    desc = video.get('snippet', {}).get('description', 'Standifer Gap SDA Church')
    
    sab = 7 - (5 - datetime.now().weekday()) # TODO: test this, it feels wrong
    sab = (datetime.now() - timedelta(sab)).date()

    times = '0:00:00 Happy Sabbath'
    if times not in desc:
      bulletin = BulletinDB(hass)
      bulletin = bulletin.get_date(sab)
      for e in bulletin:
        who = e['who']
        info = e['info']
        if who != '':
          who=f' - {who}'
        if info != '':
          info=f" - {info.replace('#', '')}"
        times = f"{times}\n{e['ss']} - {e['name']}{who}{info}"
      desc = f'{desc}\n\nChapters:\n{times}'

      updated_video = service.videos().update(
        part='snippet',
        body={
          'id': vid,
          'snippet': {
            'title': title,
            'categoryId': catId,
            'description': desc
          }
        }
      ).execute()

      if msg != None:
        await msg.edit(content=f"✅ Updated the description of https://youtu.be/{vid}:\n\n{times}")
    else:
      if msg != None:
        await msg.edit(content=f"✅ Video already has times: https://youtu.be/{vid}:\n\n{desc}")

  except HttpError as error:
    hass.log('An error occurred: %s' % error)
    if msg != None:
      await msg.edit(content=f"🛑 Something went wrong with the YT API: {error}")

class Logger():
  def log(l):
    print(l)

if __name__ == '__main__':
  run_yt(Logger)
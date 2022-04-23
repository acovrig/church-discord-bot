from __future__ import print_function

from datetime import datetime, timedelta
import os
from re import sub

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import RefreshError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def get_creds(auto = False):
  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  token_file = os.path.join('creds', 'token-cal.json')
  if os.path.exists(os.path.join(os.path.sep, 'creds', 'token-cal.json')):
    token_file = os.path.join(os.path.sep, 'creds', 'token-cal.json')
  elif os.path.exists('token-cal.json'):
    token_file = 'token-cal.json'
  if os.path.exists(token_file):
    creds = Credentials.from_authorized_user_file(token_file, SCOPES)
  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      try:
        print('Refreshing cal token')
        creds.refresh(Request())
      except RefreshError:
        os.remove(token_file)
        if not auto:
          creds = get_creds()
    elif not auto:
      creds_file = os.path.join('creds', 'credentials.json')
      if os.path.exists(os.path.join(os.path.sep, 'creds', 'credentials.json')):
        creds_file = os.path.join(os.path.sep, 'creds', 'credentials.json')
      elif os.path.exists('credentials.json'):
        creds_file = 'credentials.json'
      flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
      creds = flow.run_local_server(port=0)
    else:
      print('Unable to refresh token (auto)')
      return None
  else:
    print('Cal Token Valid')

  # Save the credentials for the next run
  # print(f'Saving creds to {token_file}')
  with open(token_file, 'w') as token:
    token.write(creds.to_json())
  return creds

def run_cal():
  """Shows basic usage of the Google Calendar API.
  prints the start and name of the next 10 events on the user's calendar.
  """

  creds = get_creds()

  try:
    service = build('calendar', 'v3', credentials=creds)

    # Call the Calendar API
    now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
    print('Getting the upcoming 10 events')
    sab = 6 - datetime.now().weekday()
    if sab <= 0:
      sab += 7
    sab = datetime.now() + timedelta(sab)
    sab = sab.isoformat() + 'Z'
    events_result = service.events().list(
      calendarId='bbulvedkouijjattqv7pu4jfk4@group.calendar.google.com',
      timeMin=now,
      maxResults=10,
      singleEvents=True,
      timeMax=sab,
      orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])

    if not events:
      print('No upcoming events found.')
      return

    for event in events:
      start = event['start'].get('dateTime', event['start'].get('date'))
      print(f"{start} {event['summary']}")

    people = list(map(lambda x: sub(r'[^a-zA-Z]', '', x['summary']).upper(), events))
    people.append('AUSTIN')
    people.append('STREAMING_PC')
    return people

  except HttpError as error:
    print('An error occurred: %s' % error)

if __name__ == '__main__':
  run_cal()
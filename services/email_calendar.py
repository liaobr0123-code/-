import os
import datetime
import asyncio
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import base64
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar.events'
]

class EmailCalendarService:
    def __init__(self):
        self.creds = None
        self._authenticate()

    def _authenticate(self):
        import json
        if os.getenv('GOOGLE_TOKEN_JSON'):
            info = json.loads(os.getenv('GOOGLE_TOKEN_JSON'))
            self.creds = Credentials.from_authorized_user_info(info, SCOPES)
        elif os.path.exists('token.json'):
            self.creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    self.creds = None
            elif os.path.exists('credentials.json'):
                print("=========================================================================")
                print("請在終端機執行 `python services/email_calendar.py` 來進行 Google 帳號授權")
                print("=========================================================================")
            else:
                print("警告: 找不到 credentials.json，Gmail 與 Calendar 功能將被停用。")

    async def send_email(self, to_email: str, subject: str, content: str):
        if not self.creds or not to_email:
            print(f"Skipping email to {to_email} (no credentials or email address)")
            return
            
        def _send():
            try:
                service = build('gmail', 'v1', credentials=self.creds)
                message = EmailMessage()
                message.set_content(content)
                message['To'] = to_email
                message['From'] = 'me'
                message['Subject'] = subject

                encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
                create_message = {'raw': encoded_message}
                service.users().messages().send(userId="me", body=create_message).execute()
            except Exception as e:
                print(f"Failed to send email: {e}")
                
        await asyncio.to_thread(_send)

    async def add_calendar_event(self, to_email: str, summary: str, description: str = ""):
        if not self.creds or not to_email:
            print(f"Skipping calendar event (no credentials or email address)")
            return
            
        def _add():
            try:
                service = build('calendar', 'v3', credentials=self.creds)
                # 設定為全天事件 (明天)
                tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
                event = {
                  'summary': summary,
                  'description': description,
                  'start': {
                    'date': tomorrow,
                    'timeZone': 'Asia/Taipei',
                  },
                  'end': {
                    'date': tomorrow,
                    'timeZone': 'Asia/Taipei',
                  },
                  'attendees': [
                    {'email': to_email},
                  ],
                }
                service.events().insert(calendarId='primary', body=event).execute()
            except Exception as e:
                print(f"Failed to add calendar event: {e}")
                
        await asyncio.to_thread(_add)

email_calendar_service = EmailCalendarService()

if __name__ == '__main__':
    # 用於獨立執行此檔案以產生 token.json
    if os.path.exists('credentials.json') and not os.path.exists('token.json'):
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
        print("授權成功！已產生 token.json")
    elif os.path.exists('token.json'):
         print("已經擁有 token.json，無需重新授權。")
    else:
         print("請先在根目錄放置從 GCP 下載的 credentials.json，然後在根目錄執行 `python -m services.email_calendar`")


import requests
from datetime import date
import os
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import RefreshError

load_dotenv()
API_KEY = os.getenv('API_KEY')




def print_toFile(filename, data,date=None):
    with open(filename+"_"+date+".json", 'w') as f:
        data=str(data.encode("UTF-8"))
        f.write(data)
        

creds = None
# The file token.json stores the user's access and refresh tokens, and is
# created automatically when the authorization flow completes for the first
# time.

# creds = Credentials.from_authorized_user_file('./client_secrets_desktop.json', ['https://www.googleapis.com/auth/youtube'])

if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:   
            print("Failed to refresh token, re-authenticating...")
        flow = InstalledAppFlow.from_client_secrets_desktop_file(
                './client_secrets_desktop_desktop.json', ['https://www.googleapis.com/auth/youtube']
            )
        creds = flow.run_local_server(port=8080)    
else:
    flow = InstalledAppFlow.from_client_secrets_file(
        './client_secrets_desktop.json', ['https://www.googleapis.com/auth/youtube']
    )
    creds = flow.run_local_server(port=8080)
    
    
# Save the credentials for the next run
with open('token.js', "w") as token:
    token.write(creds.to_json())




#call grab subscriptions
try:
    req = requests.get("https://www.googleapis.com/youtube/v3/subscriptions?", params={
        'part': 'id',
        'mine': 'true',
        'maxResult':100,
        'key':{API_KEY}
    },
                    headers = {"Authorization": f"Bearer {creds.token}"}
                    )
    
    data = req.json()
    pagetoken = data.get("nextPageToken", None)
except HttpError as e:
    print(f"An HTTP error {e.resp.status} occurred: {e.content}")

#pass along next page token if exists, new tree of data

while pagetoken:
    req = requests.get("https://www.googleapis.com/youtube/v3/subscriptions?key={API_KEY}", params={
        'part': 'id',
        'mine': 'true',
        'pageToken': pagetoken,
        'maxResult':100,
        'key':{API_KEY}
    },
                       headers = {"Authorization": f"Bearer {creds.token}"}
                       )
    moredata = req.json()
    data["items"].extend(moredata["items"])
    pagetoken = moredata.get("nextPageToken", None)

date = date.today().strftime("_%m_%d_%Y") 
print_toFile(f"youTubeChannelInfo", str(data),date)

#delete subscriptions
for item in data["items"]:
    sub_id = item["id"]
    delreq = requests.delete(f"https://www.googleapis.com/youtube/v3/subscriptions?id={sub_id}&key={API_KEY}",
                             headers = {"Authorization": f"Bearer {creds.token}"}
                             )
    if delreq.status_code == 204:
        print(f"Successfully deleted subscription: {sub_id}")
    else:
        print(f"Failed to delete subscription: {sub_id}, Status Code: {delreq.status_code}, Response: {delreq.text}")


    
    
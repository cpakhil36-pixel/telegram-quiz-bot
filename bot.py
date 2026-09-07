import os
import json
import urllib.request

TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

url = f"https://api.telegram.org/bot{TOKEN}/sendPoll"

data = {
    "chat_id": CHAT_ID,
    "question": "Capital of India is?",
    "options": [
        "Mumbai",
        "New Delhi",
        "Chennai",
        "Kolkata"
    ],
    "type": "quiz",
    "correct_option_id": 1,
    "is_anonymous": False
}

request = urllib.request.Request(
    url,
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

response = urllib.request.urlopen(request)

print(response.read().decode())

import os
import json
import urllib.request
import urllib.error

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
   "is_anonymous": True
}

request = urllib.request.Request(
    url,
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST"
)

try:
    response = urllib.request.urlopen(request)
    result = response.read().decode("utf-8")
    print(result)

except urllib.error.HTTPError as e:
    error_message = e.read().decode("utf-8")
    print("Telegram Error:")
    print(error_message)
    raise

import os
import json
import urllib.request

TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

message = """🏆 BANKING QUIZ RANK LIST

Quiz Completed! 🎉

🥇 1. Rank
🥈 2. Rank
🥉 3. Rank

Thank you for participating! ❤️
"""

data = {
    "chat_id": CHAT_ID,
    "text": message
}

request = urllib.request.Request(
    URL,
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST"
)

with urllib.request.urlopen(request) as response:
    print(response.read().decode("utf-8"))

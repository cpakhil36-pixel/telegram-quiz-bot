import os
import csv
import json
import time
import urllib.request
import urllib.error
from datetime import datetime
from zoneinfo import ZoneInfo

# ==========================================
# SETTINGS
# ==========================================

TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

# CSV FILE NAME
FILE_NAME = "SSC_sample_10_questions.csv"

API = f"https://api.telegram.org/bot{TOKEN}"

# RANK LIST TIME
RANK_HOUR = 11
RANK_MINUTE = 0

INDIA = ZoneInfo("Asia/Kolkata")


# ==========================================
# TELEGRAM API
# ==========================================

def telegram(method, data=None):

    if data is None:
        data = {}

    url = f"{API}/{method}"

    request = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as e:
        print("Telegram Error:")
        print(e.read().decode("utf-8"))
        raise


# ==========================================
# 1. READ CSV FILE
# ==========================================

questions = []

with open(
    FILE_NAME,
    "r",
    encoding="utf-8-sig"
) as file:

    reader = csv.DictReader(file)

    for number, row in enumerate(
        reader,
        start=1
    ):

        question = row["question"].strip()

        options = [
            row["option1"].strip(),
            row["option2"].strip(),
            row["option3"].strip(),
            row["option4"].strip()
        ]

        correct_answer = row["answer"].strip()

        if correct_answer not in options:
            raise ValueError(
                f"Correct answer not found "
                f"in Question {number}: "
                f"{question}"
            )

        questions.append({
            "question": question,
            "options": options,
            "correct_option_id": options.index(
                correct_answer
            )
        })


print(
    f"Loaded {len(questions)} questions."
)


# ==========================================
# 2. SEND QUIZZES
# ==========================================

for number, q in enumerate(
    questions,
    start=1
):

    print(
        f"Sending Question {number}..."
    )

    result = telegram(
        "sendPoll",
        {
            "chat_id": CHAT_ID,

            "question": q["question"],

            "options": q["options"],

            "type": "quiz",

            "correct_option_id":
                q["correct_option_id"],

            # CHANNEL = TRUE
            "is_anonymous": True
        }
    )

    if not result.get("ok"):
        raise Exception(
            f"Quiz failed: {result}"
        )

    print(
        f"Question {number} sent successfully."
    )

    time.sleep(5)


print(
    "All questions sent successfully."
)


# ==========================================
# 3. WAIT UNTIL 12:00 PM IST
# ==========================================

print(
    "Waiting for 12:00 PM IST..."
)

while True:

    now = datetime.now(INDIA)

    if (
        now.hour > RANK_HOUR
        or (
            now.hour == RANK_HOUR
            and now.minute >= RANK_MINUTE
        )
    ):
        break

    time.sleep(30)


# ==========================================
# 4. SEND RANK LIST
# ==========================================

rank_message = (
    "🏆 DAILY QUIZ RANK LIST 🏆\n\n"
    "Quiz completed successfully! 🎉\n\n"
    "Thank you for participating."
)


telegram(
    "sendMessage",
    {
        "chat_id": CHAT_ID,
        "text": rank_message
    }
)


print(
    "🏆 Rank List message sent at 12.00 PM IST."
)

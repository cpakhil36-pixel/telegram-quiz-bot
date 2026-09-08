import os
import csv
import json
import time
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

FILE_NAME = os.environ.get(
    "FILE_NAME",
    "SSC_sample_10_questions.csv"
)

API = f"https://api.telegram.org/bot{TOKEN}"


def telegram(method, data=None):
    if data is None:
        data = {}

    url = f"{API}/{method}"

    request = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


# =========================
# 1. READ QUESTIONS
# =========================

questions = []

with open(FILE_NAME, "r", encoding="utf-8-sig") as file:
    reader = csv.DictReader(file)

    for row in reader:

        options = [
            row["option1"].strip(),
            row["option2"].strip(),
            row["option3"].strip(),
            row["option4"].strip()
        ]

        correct_answer = row["answer"].strip()

        if correct_answer not in options:
            raise ValueError(
                f"Correct answer not found: {row['question']}"
            )

        questions.append({
            "question": row["question"].strip(),
            "options": options,
            "correct_option_id": options.index(correct_answer)
        })


# =========================
# 2. SEND ALL QUIZZES
# =========================

polls = {}

for number, q in enumerate(questions, start=1):

    result = telegram(
        "sendPoll",
        {
            "chat_id": CHAT_ID,
            "question": q["question"],
            "options": q["options"],
            "type": "quiz",
            "correct_option_id": q["correct_option_id"],
            "is_anonymous": False
        }
    )

    if result.get("ok"):

        poll_id = result["result"]["poll"]["id"]

        polls[poll_id] = {
            "number": number,
            "correct": q["correct_option_id"]
        }

        print(f"Question {number} sent.")

    else:
        print("Quiz error:", result)

    time.sleep(5)


# =========================
# 3. COLLECT ANSWERS
# =========================

scores = {}

print("Waiting for answers...")

offset = None

# India time
india = ZoneInfo("Asia/Kolkata")

while True:

    now = datetime.now(india)

    # 10:50 AM reached
    if now.hour == 10 and now.minute >= 50:
        break

    params = {
        "timeout": 30
    }

    if offset is not None:
        params["offset"] = offset

    result = telegram("getUpdates", params)

    if not result.get("ok"):
        continue

    for update in result.get("result", []):

        offset = update["update_id"] + 1

        answer = update.get("poll_answer")

        if not answer:
            continue

        poll_id = answer.get("poll_id")

        if poll_id not in polls:
            continue

        user = answer.get("user", {})

        user_id = user.get("id")

        first_name = user.get("first_name", "")
        last_name = user.get("last_name", "")

        name = f"{first_name} {last_name}".strip()

        if user_id not in scores:
            scores[user_id] = {
                "name": name,
                "score": 0
            }

        selected = answer.get("option_ids", [])

        correct_option = polls[poll_id]["correct"]

        if selected and selected[0] == correct_option:
            scores[user_id]["score"] += 1

    time.sleep(1)


# =========================
# 4. CREATE RANK LIST
# =========================

ranking = sorted(
    scores.values(),
    key=lambda x: x["score"],
    reverse=True
)


# =========================
# 5. SEND RANK LIST
# =========================

message = "🏆 DAILY QUIZ RANK LIST 🏆\n\n"

if not ranking:

    message += "No participants."

else:

    for rank, person in enumerate(ranking, start=1):

        if rank == 1:
            medal = "🥇"
        elif rank == 2:
            medal = "🥈"
        elif rank == 3:
            medal = "🥉"
        else:
            medal = f"{rank}."

        message += (
            f"{medal} {person['name']} — "
            f"{person['score']}/{len(questions)}\n"
        )


telegram(
    "sendMessage",
    {
        "chat_id": CHAT_ID,
        "text": message
    }
)

print("🏆 Rank List sent at 10:50 AM.")

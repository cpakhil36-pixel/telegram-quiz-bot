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
CHAT_ID = os.environ["BANKING_CHAT_ID"]

FILE_NAME = "SSC_sample_10_questions.csv"

API = f"https://api.telegram.org/bot{TOKEN}"

RANK_HOUR = 11
RANK_MINUTE = 0

india = ZoneInfo("Asia/Kolkata")


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
# 1. READ CSV
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

polls = {}

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

            "question":
                q["question"],

            "options":
                q["options"],

            "type":
                "quiz",

            "correct_option_id":
                q["correct_option_id"],

            # Participant name required
            "is_anonymous":
                False
        }
    )

    if not result.get("ok"):

        raise Exception(
            f"Quiz failed: {result}"
        )

    poll_id = (
        result["result"]["poll"]["id"]
    )

    polls[poll_id] = {
        "question_number": number,
        "correct_option":
            q["correct_option_id"]
    }

    print(
        f"Question {number} sent successfully."
    )

    time.sleep(5)


print(
    "All questions sent."
)


# ==========================================
# 3. COLLECT ANSWERS
# ==========================================

scores = {}

offset = None

print(
    "Waiting for participants' answers..."
)


while True:

    now = datetime.now(india)

    # Stop at 11:00 AM IST
    if (
        now.hour > RANK_HOUR
        or
        (
            now.hour == RANK_HOUR
            and now.minute >= RANK_MINUTE
        )
    ):
        break

    params = {
        "timeout": 30
    }

    if offset is not None:
        params["offset"] = offset

    result = telegram(
        "getUpdates",
        params
    )

    if not result.get("ok"):
        time.sleep(2)
        continue

    for update in result.get(
        "result",
        []
    ):

        offset = (
            update["update_id"] + 1
        )

        answer = update.get(
            "poll_answer"
        )

        if not answer:
            continue

        poll_id = answer.get(
            "poll_id"
        )

        if poll_id not in polls:
            continue

        user = answer.get(
            "user",
            {}
        )

        user_id = user.get(
            "id"
        )

        first_name = user.get(
            "first_name",
            ""
        )

        last_name = user.get(
            "last_name",
            ""
        )

        name = (
            f"{first_name} {last_name}"
        ).strip()

        if user_id not in scores:

            scores[user_id] = {
                "name": name,
                "score": 0,
                "answered": set()
            }

        # Avoid counting the same question twice
        question_number = polls[
            poll_id
        ]["question_number"]

        if question_number in scores[
            user_id
        ]["answered"]:
            continue

        scores[
            user_id
        ]["answered"].add(
            question_number
        )

        selected = answer.get(
            "option_ids",
            []
        )

        correct_option = polls[
            poll_id
        ]["correct_option"]

        if (
            selected
            and
            selected[0] == correct_option
        ):

            scores[
                user_id
            ]["score"] += 1

    time.sleep(1)


# ==========================================
# 4. CREATE RANKING
# ==========================================

ranking = sorted(
    scores.values(),
    key=lambda x: x["score"],
    reverse=True
)


# ==========================================
# 5. RANK LIST MESSAGE
# ==========================================

message = (
    "🏆 DAILY QUIZ RANK LIST 🏆\n\n"
)

if not ranking:

    message += (
        "No participants found."
    )

else:

    for rank, person in enumerate(
        ranking,
        start=1
    ):

        if rank == 1:
            medal = "🥇"

        elif rank == 2:
            medal = "🥈"

        elif rank == 3:
            medal = "🥉"

        else:
            medal = f"{rank}."

        message += (
            f"{medal} "
            f"{person['name']} — "
            f"{person['score']}/"
            f"{len(questions)}\n"
        )


# ==========================================
# 6. SEND RANK LIST
# ==========================================

telegram(
    "sendMessage",
    {
        "chat_id": CHAT_ID,
        "text": message
    }
)


print(
    "🏆 Rank List sent at 11:00 AM IST."
)

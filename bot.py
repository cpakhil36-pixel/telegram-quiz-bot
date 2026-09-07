import os
import csv
import json
import urllib.request
import urllib.error

TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
FILE_NAME = os.environ.get(
    "FILE_NAME",
    "SSC_sample_10_questions.csv"
)

url = f"https://api.telegram.org/bot{TOKEN}/sendPoll"

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
                f'Correct answer "{correct_answer}" was not found in options for: {row["question"]}'
            )

        correct_option_id = options.index(correct_answer)

        data = {
            "chat_id": CHAT_ID,
            "question": row["question"].strip(),
            "options": options,
            "type": "quiz",
            "correct_option_id": correct_option_id,
            "is_anonymous": True
        }

        request = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(request) as response:
                print(response.read().decode("utf-8"))

        except urllib.error.HTTPError as e:
            print("Telegram Error:")
            print(e.read().decode("utf-8"))
            raise

import os
import csv
import json
import time
import requests
from collections import defaultdict

BOT_TOKEN = os.environ["BOT_TOKEN"]

SSC_CHAT_ID = os.environ["RRB_SSC_CHAT_ID"]
BANKING_CHAT_ID = os.environ["BANKING_CHAT_ID"]

SSC_FILE = "SSC.csv"
BANKING_FILE = "BANKING.csv"

QUESTION_TIME = 60
TOTAL_QUESTIONS = 10

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def telegram(method, data):
    try:
        response = requests.post(
            f"{API_URL}/{method}",
            data=data,
            timeout=30
        )

        result = response.json()

        if not result.get("ok"):
            print("Telegram Error:", result)

        return result

    except Exception as e:
        print("Error:", e)
        return None


def load_questions(filename):
    questions = []

    with open(filename, "r", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for row in reader:
            questions.append({
                "question": row["question"].strip(),
                "options": [
                    row["option1"].strip(),
                    row["option2"].strip(),
                    row["option3"].strip(),
                    row["option4"].strip()
                ],
                "answer": row["answer"].strip()
            })

    if len(questions) < TOTAL_QUESTIONS:
        raise ValueError(
            f"{filename} must contain at least "
            f"{TOTAL_QUESTIONS} questions."
        )

    return questions[:TOTAL_QUESTIONS]


def get_correct_option(question):
    answer = question["answer"].strip()

    answer_map = {
        "A": 0,
        "B": 1,
        "C": 2,
        "D": 3
    }

    if answer.upper() in answer_map:
        return answer_map[answer.upper()]

    for index, option in enumerate(question["options"]):
        if option.lower() == answer.lower():
            return index

    raise ValueError(
        f"Answer not found in options: {answer}"
    )


def send_question(chat_id, number, question):
    correct_option = get_correct_option(question)

    data = {
        "chat_id": chat_id,
        "question": (
            f"Question {number}/{TOTAL_QUESTIONS}\n\n"
            f"{question['question']}"
        ),
        "options": json.dumps(
            question["options"],
            ensure_ascii=False
        ),
        "type": "quiz",
        "correct_option_id": correct_option,
        "open_period": QUESTION_TIME,
        "is_anonymous": False,
        "allows_multiple_answers": False
    }

    result = telegram("sendPoll", data)

    if result and result.get("ok"):
        return result["result"]["poll"]["id"]

    return None


def collect_answers(end_time, poll_answers, scores):
    offset = None

    while time.time() < end_time:
        remaining = end_time - time.time()
        timeout = min(5, max(1, int(remaining)))

        params = {
            "timeout": timeout
        }

        if offset is not None:
            params["offset"] = offset

        try:
            response = requests.get(
                f"{API_URL}/getUpdates",
                params=params,
                timeout=timeout + 10
            )

            result = response.json()

            if not result.get("ok"):
                continue

            for update in result.get("result", []):
                offset = update["update_id"] + 1

                answer = update.get("poll_answer")

                if not answer:
                    continue

                poll_id = answer.get("poll_id")

                if poll_id not in poll_answers:
                    continue

                user = answer.get("user")
                selected = answer.get("option_ids", [])

                if not user or not selected:
                    continue

                user_id = user["id"]

                if user_id not in scores:
                    scores[user_id] = {
                        "name": "",
                        "correct": 0,
                        "wrong": 0,
                        "answered": set()
                    }

                username = user.get("username")
                first_name = user.get(
                    "first_name",
                    "User"
                )
                last_name = user.get(
                    "last_name",
                    ""
                )

                if username:
                    name = f"@{username}"
                else:
                    name = (
                        f"{first_name} {last_name}"
                    ).strip()

                scores[user_id]["name"] = name

                if poll_id in scores[user_id]["answered"]:
                    continue

                scores[user_id]["answered"].add(poll_id)

                if (
                    selected[0]
                    == poll_answers[poll_id]
                ):
                    scores[user_id]["correct"] += 1
                else:
                    scores[user_id]["wrong"] += 1

        except Exception as e:
            print("Answer collection error:", e)
            time.sleep(1)


def send_final_result(chat_id, scores, title):
    if not scores:
        telegram(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    f"🏁 {title} Finished!\n\n"
                    "No participants recorded."
                )
            }
        )
        return

    ranking = sorted(
        scores.values(),
        key=lambda x: x["correct"],
        reverse=True
    )

    text = (
        f"🏁 {title} Finished!\n\n"
        f"📊 Final Result\n\n"
    )

    for rank, user in enumerate(ranking[:20], 1):
        answered = len(user["answered"])
        missed = TOTAL_QUESTIONS - answered

        text += (
            f"{rank}. {user['name']}\n"
            f"   ✅ Correct: {user['correct']}\n"
            f"   ❌ Wrong: {user['wrong']}\n"
            f"   ⏳ Missed: {missed}\n"
            f"   🏆 Score: "
            f"{user['correct']}/{TOTAL_QUESTIONS}\n\n"
        )

    telegram(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text
        }
    )


def run_quiz(chat_id, questions, title):
    print(f"Starting {title}")

    scores = {}
    poll_answers = {}

    for number, question in enumerate(
        questions,
        start=1
    ):
        print(
            f"Sending question {number}/"
            f"{TOTAL_QUESTIONS}"
        )

        poll_id = send_question(
            chat_id,
            number,
            question
        )

        if poll_id is None:
            print(
                f"Question {number} failed."
            )
            continue

        poll_answers[poll_id] = (
            get_correct_option(question)
        )

        end_time = (
            time.time()
            + QUESTION_TIME
            + 3
        )

        collect_answers(
            end_time,
            poll_answers,
            scores
        )

        time.sleep(2)

    send_final_result(
        chat_id,
        scores,
        title
    )

    print(f"{title} completed.")


def main():
    print("🚀 DAILY QUIZ BOT STARTED")

    ssc_questions = load_questions(
        SSC_FILE
    )

    banking_questions = load_questions(
        BANKING_FILE
    )

    print(
        f"SSC/RRB: {len(ssc_questions)} questions"
    )

    print(
        f"Banking: {len(banking_questions)} questions"
    )

    run_quiz(
        SSC_CHAT_ID,
        ssc_questions,
        "SSC + RRB Quiz"
    )

    run_quiz(
        BANKING_CHAT_ID,
        banking_questions,
        "Banking Quiz"
    )

    print("✅ ALL QUIZZES COMPLETED")


if __name__ == "__main__":
    main()

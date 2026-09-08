import os
import csv
import json
import time
import requests

BOT_TOKEN = os.environ["BOT_TOKEN"]

SSC_CHAT_ID = os.environ["SSC_CHAT_ID"]
BANKING_CHAT_ID = os.environ["BANKING_CHAT_ID"]

SSC_FILE = "SSC.csv"
BANKING_FILE = "BANKING.csv"

QUESTION_TIME = 60
TOTAL_QUESTIONS = 10

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Telegram update offset
UPDATE_OFFSET = None


def telegram(method, data=None):
    try:
        response = requests.post(
            f"{API_URL}/{method}",
            data=data or {},
            timeout=30
        )

        result = response.json()

        if not result.get("ok"):
            print("Telegram Error:", result)

        return result

    except Exception as e:
        print("Telegram Request Error:", e)
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

        # New Telegram Bot API format
        "correct_option_ids": json.dumps(
            [correct_option]
        ),

        # 60 second timer
        "open_period": QUESTION_TIME,

        # IMPORTANT:
        # Keep False for name/score/rank tracking
        "is_anonymous": False,

        "allows_multiple_answers": False
    }

    result = telegram("sendPoll", data)

    if result and result.get("ok"):
        poll_id = result["result"]["poll"]["id"]

        print(
            f"Poll sent successfully: "
            f"{number}/{TOTAL_QUESTIONS}"
        )

        return poll_id

    return None


def collect_answers(end_time, poll_answers, scores):
    global UPDATE_OFFSET

    while time.time() < end_time:

        remaining = end_time - time.time()

        timeout = min(
            5,
            max(1, int(remaining))
        )

        params = {
            "timeout": timeout,

            # IMPORTANT:
            # Explicitly request poll answers
            "allowed_updates": json.dumps(
                ["poll_answer"]
            )
        }

        if UPDATE_OFFSET is not None:
            params["offset"] = UPDATE_OFFSET

        try:
            response = requests.get(
                f"{API_URL}/getUpdates",
                params=params,
                timeout=timeout + 10
            )

            result = response.json()

            if not result.get("ok"):
                print(
                    "getUpdates Error:",
                    result
                )
                continue

            updates = result.get(
                "result",
                []
            )

            for update in updates:

                UPDATE_OFFSET = (
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

                # Ignore old/different polls
                if poll_id not in poll_answers:
                    continue

                user = answer.get("user")

                selected = answer.get(
                    "option_ids",
                    []
                )

                if not user:
                    continue

                user_id = user["id"]

                if user_id not in scores:
                    scores[user_id] = {
                        "name": "",
                        "correct": 0,
                        "wrong": 0,
                        "answered": set()
                    }

                username = user.get(
                    "username"
                )

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
                        f"{first_name} "
                        f"{last_name}"
                    ).strip()

                scores[user_id]["name"] = name

                # Prevent duplicate scoring
                if poll_id in scores[user_id]["answered"]:
                    continue

                # Empty option = vote removed
                if not selected:
                    continue

                scores[user_id]["answered"].add(
                    poll_id
                )

                if (
                    selected[0]
                    == poll_answers[poll_id]
                ):
                    scores[user_id]["correct"] += 1
                else:
                    scores[user_id]["wrong"] += 1

                print(
                    f"Answer received: "
                    f"{name} | "
                    f"{'Correct' if selected[0] == poll_answers[poll_id] else 'Wrong'}"
                )

        except Exception as e:
            print(
                "Answer collection error:",
                e
            )

            time.sleep(1)


def send_final_result(
    chat_id,
    scores,
    title
):
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
        f"📊 FINAL RESULT\n\n"
    )

    for rank, user in enumerate(
        ranking[:20],
        start=1
    ):

        answered = len(
            user["answered"]
        )

        missed = (
            TOTAL_QUESTIONS
            - answered
        )

        text += (
            f"🏆 {rank}. {user['name']}\n"
            f"✅ Correct: {user['correct']}\n"
            f"❌ Wrong: {user['wrong']}\n"
            f"⏳ Missed: {missed}\n"
            f"📊 Score: "
            f"{user['correct']}/{TOTAL_QUESTIONS}\n\n"
        )

    telegram(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text
        }
    )


def run_quiz(
    chat_id,
    questions,
    title
):
    print(
        f"\n=============================="
    )

    print(
        f"Starting {title}"
    )

    print(
        f"=============================="
    )

    scores = {}
    poll_answers = {}

    for number, question in enumerate(
        questions,
        start=1
    ):

        print(
            f"Sending question "
            f"{number}/{TOTAL_QUESTIONS}"
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

        correct_option = (
            get_correct_option(question)
        )

        poll_answers[poll_id] = (
            correct_option
        )

        # Wait 60 seconds
        end_time = (
            time.time()
            + QUESTION_TIME
            + 2
        )

        collect_answers(
            end_time,
            poll_answers,
            scores
        )

        # Small gap before next question
        time.sleep(2)

    send_final_result(
        chat_id,
        scores,
        title
    )

    print(
        f"{title} completed."
    )


def main():

    print(
        "🚀 DAILY QUIZ BOT STARTED"
    )

    print(
        "SSC Chat ID:",
        SSC_CHAT_ID
    )

    print(
        "Banking Chat ID:",
        BANKING_CHAT_ID
    )

    ssc_questions = load_questions(
        SSC_FILE
    )

    banking_questions = load_questions(
        BANKING_FILE
    )

    print(
        f"SSC/RRB: "
        f"{len(ssc_questions)} questions"
    )

    print(
        f"Banking: "
        f"{len(banking_questions)} questions"
    )

    # SSC + RRB
    run_quiz(
        SSC_CHAT_ID,
        ssc_questions,
        "SSC + RRB Quiz"
    )

    # Banking
    run_quiz(
        BANKING_CHAT_ID,
        banking_questions,
        "Banking Quiz"
    )

    print(
        "✅ ALL QUIZZES COMPLETED"
    )


if __name__ == "__main__":
    main()

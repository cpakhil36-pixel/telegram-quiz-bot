import os
import csv
import time
import requests
from collections import defaultdict

# =========================
# SETTINGS
# =========================

BOT_TOKEN = os.environ["BOT_TOKEN"]

RRB_SSC_CHAT_ID = os.environ["RRB_SSC_CHAT_ID"]
BANKING_CHAT_ID = os.environ["BANKING_CHAT_ID"]

RRB_SSC_FILE = "RRB_SSC.csv"
BANKING_FILE = "BANKING.csv"

QUESTION_TIME = 60
TOTAL_QUESTIONS = 10

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


# =========================
# TELEGRAM FUNCTIONS
# =========================

def telegram(method, data=None):
    url = f"{API_URL}/{method}"

    try:
        response = requests.post(url, data=data, timeout=30)
        result = response.json()

        if not result.get("ok"):
            print("Telegram Error:", result)

        return result

    except Exception as e:
        print("Request Error:", e)
        return None


# =========================
# READ CSV
# =========================

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

    return questions[:TOTAL_QUESTIONS]


# =========================
# FIND CORRECT ANSWER
# =========================

def get_correct_option(question):

    answer = question["answer"].strip()

    option_map = {
        "A": 0,
        "B": 1,
        "C": 2,
        "D": 3
    }

    # If CSV contains A/B/C/D
    if answer.upper() in option_map:
        return option_map[answer.upper()]

    # If CSV contains complete answer text
    for index, option in enumerate(question["options"]):

        if option.lower() == answer.lower():
            return index

    raise ValueError(
        f"Answer not found in options: {answer}"
    )


# =========================
# SEND QUIZ QUESTION
# =========================

def send_quiz(chat_id, question_number, question):

    correct_option = get_correct_option(question)

    data = {
        "chat_id": chat_id,
        "question": f"Question {question_number}/10\n\n{question['question']}",
        "options": str(question["options"]).replace("'", '"'),
        "type": "quiz",
        "correct_option_id": correct_option,

        # 60 second Telegram timer
        "open_period": QUESTION_TIME,

        # Required for participant tracking/rank
        "is_anonymous": False,

        "allows_multiple_answers": False
    }

    result = telegram("sendPoll", data)

    if result and result.get("ok"):

        poll = result["result"]["poll"]

        print(
            f"Question {question_number} sent "
            f"to {chat_id}"
        )

        return poll["id"]

    print(
        f"Failed to send Question {question_number}"
    )

    return None


# =========================
# GET POLL ANSWERS
# =========================

def collect_answers(
    start_time,
    end_time,
    poll_details,
    scores
):

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

            updates = result.get("result", [])

            for update in updates:

                offset = update["update_id"] + 1

                poll_answer = update.get("poll_answer")

                if not poll_answer:
                    continue

                poll_id = poll_answer.get("poll_id")

                if poll_id not in poll_details:
                    continue

                user = poll_answer.get("user")

                option_ids = poll_answer.get(
                    "option_ids",
                    []
                )

                if not user or not option_ids:
                    continue

                user_id = user["id"]

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

                    display_name = f"@{username}"

                else:

                    display_name = (
                        first_name + " " + last_name
                    ).strip()

                details = poll_details[poll_id]

                correct_option = details[
                    "correct_option"
                ]

                selected_option = option_ids[0]

                # Prevent duplicate scoring
                question_key = (
                    user_id,
                    poll_id
                )

                if question_key in scores["answered"]:
                    continue

                scores["answered"].add(
                    question_key
                )

                if selected_option == correct_option:

                    scores["users"][user_id][
                        "score"
                    ] += 1

                scores["users"][user_id][
                    "name"
                ] = display_name

                scores["users"][user_id][
                    "answered"
                ] += 1

        except Exception as e:

            print(
                "Answer collection error:",
                e
            )

            time.sleep(1)


# =========================
# SEND FINAL RANK
# =========================

def send_rank(chat_id, scores, title):

    users = scores["users"]

    if not users:

        telegram(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    f"🏁 {title}\n\n"
                    "No participants recorded."
                )
            }
        )

        return

    ranking = sorted(
        users.values(),
        key=lambda x: x["score"],
        reverse=True
    )

    text = f"🏆 {title} - Final Result\n\n"

    rank = 1

    for user in ranking[:20]:

        name = user["name"]
        score = user["score"]

        text += (
            f"{rank}. {name} — "
            f"{score}/{TOTAL_QUESTIONS}\n"
        )

        rank += 1

    telegram(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text
        }
    )


# =========================
# RUN ONE QUIZ
# =========================

def run_quiz(
    chat_id,
    questions,
    title,
    shared_scores
):

    print(
        f"\nStarting {title}"
    )

    poll_details = {}

    for index, question in enumerate(
        questions,
        start=1
    ):

        poll_id = send_quiz(
            chat_id,
            index,
            question
        )

        if poll_id:

            poll_details[poll_id] = {
                "correct_option":
                    get_correct_option(question)
            }

        # Collect answers during the
        # 60-second question period
        start_time = time.time()

        end_time = (
            start_time + QUESTION_TIME + 5
        )

        collect_answers(
            start_time,
            end_time,
            poll_details,
            shared_scores
        )

        print(
            f"Question {index} completed."
        )

        # Small gap before next question
        time.sleep(2)

    print(
        f"{title} completed."
    )


# =========================
# MAIN
# =========================

def main():

    print("================================")
    print("      DAILY QUIZ BOT STARTED")
    print("================================")

    # Load RRB + SSC questions
    rrb_ssc_questions = load_questions(
        RRB_SSC_FILE
    )

    # Load Banking questions
    banking_questions = load_questions(
        BANKING_FILE
    )

    print(
        f"RRB + SSC Questions: "
        f"{len(rrb_ssc_questions)}"
    )

    print(
        f"Banking Questions: "
        f"{len(banking_questions)}"
    )

    # Separate scores for each group
    rrb_ssc_scores = {
        "users": defaultdict(
            lambda: {
                "name": "",
                "score": 0,
                "answered": 0
            }
        ),
        "answered": set()
    }

    banking_scores = {
        "users": defaultdict(
            lambda: {
                "name": "",
                "score": 0,
                "answered": 0
            }
        ),
        "answered": set()
    }

    # =========================
    # RRB + SSC QUIZ
    # =========================

    run_quiz(
        RRB_SSC_CHAT_ID,
        rrb_ssc_questions,
        "RRB + SSC Quiz",
        rrb_ssc_scores
    )

    # =========================
    # BANKING QUIZ
    # =========================

    run_quiz(
        BANKING_CHAT_ID,
        banking_questions,
        "Banking Quiz",
        banking_scores
    )

    # =========================
    # FINAL RANKS
    # =========================

    send_rank(
        SSC_CHAT_ID,
        rrb_ssc_scores,
        "RRB + SSC"
    )

    send_rank(
        BANKING_CHAT_ID,
        banking_scores,
        "Banking"
    )

    print(
        "\nALL QUIZZES COMPLETED."
    )


if __name__ == "__main__":
    main()


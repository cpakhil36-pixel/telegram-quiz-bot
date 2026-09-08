import os
import csv
import time
import uuid

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

BOT_TOKEN = os.environ["BOT_TOKEN"]

SSC_FILE = "SSC.csv"
BANKING_FILE = "BANKING.csv"

QUESTION_TIME = 60
TOTAL_QUESTIONS = 10


def load_questions(filename):
    questions = []

    with open(
        filename,
        "r",
        encoding="utf-8-sig"
    ) as file:

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


def correct_answer(question):
    answer = question["answer"].strip().upper()

    if answer in ["A", "B", "C", "D"]:
        return ord(answer) - ord("A")

    for i, option in enumerate(
        question["options"]
    ):
        if option.lower() == question[
            "answer"
        ].strip().lower():
            return i

    return 0


SSC_QUESTIONS = load_questions(
    SSC_FILE
)

BANKING_QUESTIONS = load_questions(
    BANKING_FILE
)

sessions = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [
            InlineKeyboardButton(
                "📝 SSC + RRB Exam",
                callback_data="start_ssc"
            )
        ],
        [
            InlineKeyboardButton(
                "🏦 Banking Exam",
                callback_data="start_banking"
            )
        ]
    ]

    await update.message.reply_text(
        "🎓 DAILY ONLINE EXAM\n\n"
        "Choose your exam:",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )


async def start_exam(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    if query.data == "start_ssc":
        questions = SSC_QUESTIONS
        title = "SSC + RRB"
    else:
        questions = BANKING_QUESTIONS
        title = "Banking"

    session_id = str(uuid.uuid4())

    sessions[user_id] = {
        "session_id": session_id,
        "questions": questions,
        "title": title,
        "current": 0,
        "score": 0,
        "answers": [],
        "start_time": time.time()
    }

    await send_question(
        query,
        context,
        user_id
    )


async def send_question(
    query,
    context,
    user_id
):

    session = sessions.get(user_id)

    if not session:
        return

    number = session["current"]

    if number >= len(
        session["questions"]
    ):
        await finish_exam(
            query,
            user_id
        )
        return

    question = session[
        "questions"
    ][number]

    keyboard = []

    for i, option in enumerate(
        question["options"]
    ):

        keyboard.append([
            InlineKeyboardButton(
                option,
                callback_data=f"answer_{i}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "⏱ 60 Seconds",
            callback_data="timer"
        )
    ])

    await query.edit_message_text(
        f"📝 {session['title']}\n\n"
        f"Question {number + 1}/"
        f"{TOTAL_QUESTIONS}\n\n"
        f"{question['question']}\n\n"
        f"⏱ Time: 60 seconds",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )


async def answer_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    session = sessions.get(user_id)

    if not session:
        await query.edit_message_text(
            "❌ Exam session expired.\n\n"
            "Send /start to begin again."
        )
        return

    selected = int(
        query.data.split("_")[1]
    )

    question = session[
        "questions"
    ][session["current"]]

    correct = correct_answer(
        question
    )

    if selected == correct:
        session["score"] += 1

    session["answers"].append(
        selected
    )

    session["current"] += 1

    await send_question(
        query,
        context,
        user_id
    )


async def finish_exam(
    query,
    user_id
):

    session = sessions.get(user_id)

    if not session:
        return

    score = session["score"]

    total = len(
        session["questions"]
    )

    percentage = (
        score / total
    ) * 100

    await query.edit_message_text(
        f"🏁 EXAM COMPLETED!\n\n"
        f"📚 {session['title']}\n\n"
        f"✅ Correct: {score}\n"
        f"❌ Wrong: {total - score}\n"
        f"📊 Score: {score}/{total}\n"
        f"📈 Percentage: "
        f"{percentage:.0f}%\n\n"
        f"🎉 Thank you for attending!"
    )

    del sessions[user_id]


async def timer_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer(
        "⏱ Timer is 60 seconds.",
        show_alert=True
    )


def main():

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            start_exam,
            pattern="^start_(ssc|banking)$"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            answer_question,
            pattern="^answer_[0-3]$"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            timer_button,
            pattern="^timer$"
        )
    )

    print(
        "🚀 Exam Bot Started"
    )

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()

import os
import csv
import time
import uuid
import asyncio

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

SSC_CHAT_ID = os.environ.get("SSC_CHAT_ID")
BANKING_CHAT_ID = os.environ.get("BANKING_CHAT_ID")

QUESTION_TIME = 60
TOTAL_QUESTIONS = 10

sessions = {}
completed_results = {
    "SSC + RRB": {},
    "Banking": {}
}


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

    for i, option in enumerate(question["options"]):
        if option.lower() == answer.lower():
            return i

    return 0


SSC_QUESTIONS = load_questions(SSC_FILE)
BANKING_QUESTIONS = load_questions(BANKING_FILE)


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

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
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def start_exam(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    old_session = sessions.get(user_id)

    if old_session and old_session.get("timer_task"):
        old_session["timer_task"].cancel()

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
        "timer_task": None,
        "question_token": str(uuid.uuid4())
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

    if number >= len(session["questions"]):
        await finish_exam(query, user_id)
        return

    question = session["questions"][number]

    question_token = str(uuid.uuid4())
    session["question_token"] = question_token

    keyboard = []

    for i, option in enumerate(question["options"]):
        keyboard.append([
            InlineKeyboardButton(
                option,
                callback_data=f"answer_{i}"
            )
        ])

    message = await query.edit_message_text(
        f"📝 {session['title']}\n\n"
        f"Question {number + 1}/{TOTAL_QUESTIONS}\n\n"
        f"{question['question']}\n\n"
        f"⏱️ Time Left: 60 seconds",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    if session.get("timer_task"):
        session["timer_task"].cancel()

    session["timer_task"] = asyncio.create_task(
        countdown_timer(
            context,
            user_id,
            message.chat_id,
            message.message_id,
            number,
            question_token
        )
    )


async def countdown_timer(
    context,
    user_id,
    chat_id,
    message_id,
    question_number,
    question_token
):

    try:

        for remaining in range(
            QUESTION_TIME - 1,
            -1,
            -1
        ):

            await asyncio.sleep(1)

            session = sessions.get(user_id)

            if not session:
                return

            if session["current"] != question_number:
                return

            if session["question_token"] != question_token:
                return

            question = session["questions"][question_number]

            keyboard = []

            for i, option in enumerate(question["options"]):
                keyboard.append([
                    InlineKeyboardButton(
                        option,
                        callback_data=f"answer_{i}"
                    )
                ])

            if remaining > 0:

                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=(
                            f"📝 {session['title']}\n\n"
                            f"Question {question_number + 1}/"
                            f"{TOTAL_QUESTIONS}\n\n"
                            f"{question['question']}\n\n"
                            f"⏱️ Time Left: "
                            f"{remaining} seconds"
                        ),
                        reply_markup=InlineKeyboardMarkup(
                            keyboard
                        )
                    )

                except Exception:
                    pass

            else:

                session["answers"].append(None)
                session["current"] += 1

                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=(
                            f"⏰ TIME UP!\n\n"
                            f"Question "
                            f"{question_number + 1} "
                            f"was not answered."
                        )
                    )
                except Exception:
                    pass

                await asyncio.sleep(1)

                session = sessions.get(user_id)

                if session:
                    await send_next_question(
                        context,
                        user_id
                    )

                return

    except asyncio.CancelledError:
        return


async def send_next_question(
    context,
    user_id
):

    session = sessions.get(user_id)

    if not session:
        return

    number = session["current"]

    if number >= len(session["questions"]):

        await finish_exam_by_bot(
            context,
            user_id
        )

        return

    question = session["questions"][number]

    keyboard = []

    for i, option in enumerate(question["options"]):
        keyboard.append([
            InlineKeyboardButton(
                option,
                callback_data=f"answer_{i}"
            )
        ])

    try:

        message = await context.bot.send_message(
            chat_id=session["chat_id"],
            text=(
                f"📝 {session['title']}\n\n"
                f"Question {number + 1}/"
                f"{TOTAL_QUESTIONS}\n\n"
                f"{question['question']}\n\n"
                f"⏱️ Time Left: 60 seconds"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        session["question_token"] = str(uuid.uuid4())

        session["timer_task"] = asyncio.create_task(
            countdown_timer(
                context,
                user_id,
                message.chat_id,
                message.message_id,
                number,
                session["question_token"]
            )
        )

    except Exception as e:
        print("Next question error:", e)


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

    if session.get("timer_task"):
        session["timer_task"].cancel()

    selected = int(query.data.split("_")[1])

    question = session["questions"][session["current"]]

    correct = correct_answer(question)

    if selected == correct:
        session["score"] += 1

    session["answers"].append(selected)

    session["current"] += 1

    if session["current"] >= len(session["questions"]):

        await finish_exam(
            query,
            user_id
        )

        return

    session["chat_id"] = query.message.chat_id

    await send_next_question(
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
    total = len(session["questions"])

    percentage = (score / total) * 100

    title = session["title"]

    completed_results[title][user_id] = score

    scores = list(completed_results[title].values())

    rank = 1

    for other_score in scores:
        if other_score > score:
            rank += 1

    await query.edit_message_text(
        f"🏁 EXAM COMPLETED!\n\n"
        f"📚 {title}\n\n"
        f"✅ Correct: {score}\n"
        f"❌ Wrong: {total - score}\n"
        f"📊 Score: {score}/{total}\n"
        f"📈 Percentage: {percentage:.0f}%\n"
        f"🏆 Rank: {rank}\n\n"
        f"🎉 Thank you for attending!"
    )

    del sessions[user_id]


async def finish_exam_by_bot(
    context,
    user_id
):

    session = sessions.get(user_id)

    if not session:
        return

    score = session["score"]
    total = len(session["questions"])

    percentage = (score / total) * 100

    title = session["title"]

    completed_results[title][user_id] = score

    scores = list(completed_results[title].values())

    rank = 1

    for other_score in scores:
        if other_score > score:
            rank += 1

    await context.bot.send_message(
        chat_id=session["chat_id"],
        text=(
            f"🏁 EXAM COMPLETED!\n\n"
            f"📚 {title}\n\n"
            f"✅ Correct: {score}\n"
            f"❌ Wrong: {total - score}\n"
            f"📊 Score: {score}/{total}\n"
            f"📈 Percentage: {percentage:.0f}%\n"
            f"🏆 Rank: {rank}\n\n"
            f"🎉 Thank you for attending!"
        )
    )

    del sessions[user_id]


async def send_group_links(
    application
):

    try:

        bot_info = await application.bot.get_me()

        bot_username = bot_info.username

        link = f"https://t.me/{bot_username}"

        text = (
            "🎯 TODAY'S ONLINE EXAM\n\n"
            "📝 SSC + RRB & 🏦 Banking\n\n"
            "👇 Click the button below to enter the exam"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "🚀 START EXAM",
                    url=link
                )
            ]
        ]

        markup = InlineKeyboardMarkup(keyboard)

        if SSC_CHAT_ID:

            try:
                await application.bot.send_message(
                    chat_id=SSC_CHAT_ID,
                    text=text,
                    reply_markup=markup
                )

                print("✅ SSC exam link sent")

            except Exception as e:
                print("❌ SSC group error:", e)

        if BANKING_CHAT_ID:

            try:
                await application.bot.send_message(
                    chat_id=BANKING_CHAT_ID,
                    text=text,
                    reply_markup=markup
                )

                print("✅ Banking exam link sent")

            except Exception as e:
                print("❌ Banking group error:", e)

    except Exception as e:
        print("❌ Group link error:", e)


async def post_init(
    application
):

    await send_group_links(application)


async def start_exam_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await start(update, context)


def main():

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start_exam_handler
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

    print("🚀 Exam Bot Started")

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()


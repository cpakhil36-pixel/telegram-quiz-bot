import os
import csv
import uuid
import asyncio
from datetime import datetime, timezone

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

# Every GitHub Actions run gets a unique RUN_ID.
RUN_ID = os.environ.get("GITHUB_RUN_ID", str(uuid.uuid4()))

# This changes automatically for every workflow run.
EXAM_ID = f"exam_{RUN_ID}"


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
        if option.strip().lower() == answer.strip().lower():
            return i

    return 0


SSC_QUESTIONS = load_questions(SSC_FILE)
BANKING_QUESTIONS = load_questions(BANKING_FILE)


def make_exam_link(bot_username):
    return f"https://t.me/{bot_username}?start={EXAM_ID}"


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    # Read deep-link parameter.
    args = context.args

    requested_exam = None

    if args:
        requested_exam = args[0]

    # If this is a fresh daily/run link.
    if requested_exam == EXAM_ID:

        keyboard = [
            [
                InlineKeyboardButton(
                    "📝 SSC + RRB Exam",
                    callback_data=f"start_ssc|{EXAM_ID}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🏦 Banking Exam",
                    callback_data=f"start_banking|{EXAM_ID}"
                )
            ]
        ]

        await update.message.reply_text(
            "🎓 DAILY ONLINE EXAM\n\n"
            "🆕 New Exam Session\n\n"
            "Choose your exam:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # Normal /start without today's deep link.
    keyboard = [
        [
            InlineKeyboardButton(
                "📝 SSC + RRB Exam",
                callback_data=f"start_ssc|{EXAM_ID}"
            )
        ],
        [
            InlineKeyboardButton(
                "🏦 Banking Exam",
                callback_data=f"start_banking|{EXAM_ID}"
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

    data = query.data.split("|")

    if len(data) != 2:
        await query.edit_message_text(
            "❌ Invalid exam link."
        )
        return

    exam_type = data[0]
    exam_id = data[1]

    # Old link protection.
    if exam_id != EXAM_ID:
        await query.edit_message_text(
            "❌ This exam link has expired.\n\n"
            "Please use the latest exam link."
        )
        return

    user_id = query.from_user.id

    # Delete old session for this user.
    old_session = sessions.pop(user_id, None)

    if old_session:
        old_timer = old_session.get("timer_task")

        if old_timer:
            old_timer.cancel()

    if exam_type == "start_ssc":
        questions = SSC_QUESTIONS
        title = "SSC + RRB"

    elif exam_type == "start_banking":
        questions = BANKING_QUESTIONS
        title = "Banking"

    else:
        await query.edit_message_text(
            "❌ Invalid exam."
        )
        return

    session_id = str(uuid.uuid4())

    sessions[user_id] = {
        "session_id": session_id,
        "exam_id": exam_id,
        "questions": questions,
        "title": title,
        "current": 0,
        "score": 0,
        "answers": [],
        "chat_id": query.message.chat_id,
        "timer_task": None,
        "question_token": None
    }

    # Create a NEW message instead of reusing the old one.
    await query.message.reply_text(
        f"✅ {title} Exam Started\n\n"
        f"📚 Total Questions: {TOTAL_QUESTIONS}\n"
        f"⏱️ Time: {QUESTION_TIME} seconds per question\n\n"
        f"Good luck! 🎯"
    )

    await send_question(
        context,
        user_id
    )


async def send_question(
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
                callback_data=(
                    f"answer|{session['exam_id']}|{i}|{number}"
                )
            )
        ])

    question_token = str(uuid.uuid4())

    session["question_token"] = question_token

    try:

        message = await context.bot.send_message(
            chat_id=session["chat_id"],
            text=(
                f"📝 {session['title']}\n\n"
                f"Question {number + 1}/{TOTAL_QUESTIONS}\n\n"
                f"{question['question']}\n\n"
                f"⏱️ Time Left: 60 seconds"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:

        print("Question send error:", e)
        return

    old_timer = session.get("timer_task")

    if old_timer:
        old_timer.cancel()

    session["timer_task"] = asyncio.create_task(
        countdown_timer(
            context=context,
            user_id=user_id,
            chat_id=message.chat_id,
            message_id=message.message_id,
            question_number=number,
            question_token=question_token
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
                        callback_data=(
                            f"answer|{session['exam_id']}|"
                            f"{i}|{question_number}"
                        )
                    )
                ])

            if remaining > 0:

                try:

                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=(
                            f"📝 {session['title']}\n\n"
                            f"Question "
                            f"{question_number + 1}/"
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

                # Time expired.
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
                    await send_question(
                        context,
                        user_id
                    )

                return

    except asyncio.CancelledError:
        return


async def answer_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    data = query.data.split("|")

    if len(data) != 4:
        await query.answer(
            "Invalid answer.",
            show_alert=True
        )
        return

    _, exam_id, selected_text, question_number_text = data

    if exam_id != EXAM_ID:
        await query.answer(
            "❌ This exam has expired.",
            show_alert=True
        )
        return

    selected = int(selected_text)
    question_number = int(question_number_text)

    user_id = query.from_user.id

    session = sessions.get(user_id)

    if not session:
        await query.message.reply_text(
            "❌ Exam session expired.\n\n"
            "Please open the latest exam link."
        )
        return

    # Ignore old/stale question buttons.
    if session["exam_id"] != exam_id:
        await query.answer(
            "❌ Old exam session.",
            show_alert=True
        )
        return

    if session["current"] != question_number:
        await query.answer(
            "⚠️ This question is no longer active.",
            show_alert=True
        )
        return

    timer_task = session.get("timer_task")

    if timer_task:
        timer_task.cancel()

    question = session["questions"][question_number]

    correct = correct_answer(question)

    if selected == correct:
        session["score"] += 1
        result_text = "✅ Correct!"

    else:
        result_text = "❌ Wrong!"

    session["answers"].append(selected)

    session["current"] += 1

    # Disable old buttons.
    try:

        await query.edit_message_reply_markup(
            reply_markup=None
        )

    except Exception:
        pass

    try:

        await query.message.reply_text(
            result_text
        )

    except Exception:
        pass

    if session["current"] >= len(session["questions"]):

        await finish_exam_by_bot(
            context,
            user_id
        )

        return

    await send_question(
        context,
        user_id
    )


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

    scores = list(
        completed_results[title].values()
    )

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

    old_timer = session.get("timer_task")

    if old_timer:
        old_timer.cancel()

    del sessions[user_id]


async def timer_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer(
        "⏱️ 60 seconds per question.",
        show_alert=True
    )


async def send_group_links(
    application
):

    try:

        bot_info = await application.bot.get_me()

        bot_username = bot_info.username

        exam_link = make_exam_link(
            bot_username
        )

        text = (
            "🎯 TODAY'S ONLINE EXAM\n\n"
            "🆕 NEW EXAM SESSION\n\n"
            "👇 Click below to enter the exam"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "🚀 START EXAM",
                    url=exam_link
                )
            ]
        ]

        markup = InlineKeyboardMarkup(keyboard)

        if SSC_CHAT_ID:

            try:

                await application.bot.send_message(
                    chat_id=SSC_CHAT_ID,
                    text=(
                        "📝 SSC + RRB DAILY EXAM\n\n"
                        "👇 Click below to start today's exam"
                    ),
                    reply_markup=markup
                )

                print(
                    "✅ SSC new exam link sent:"
                )
                print(exam_link)

            except Exception as e:

                print(
                    "❌ SSC group error:",
                    e
                )

        if BANKING_CHAT_ID:

            try:

                await application.bot.send_message(
                    chat_id=BANKING_CHAT_ID,
                    text=(
                        "🏦 BANKING DAILY EXAM\n\n"
                        "👇 Click below to start today's exam"
                    ),
                    reply_markup=markup
                )

                print(
                    "✅ Banking new exam link sent:"
                )
                print(exam_link)

            except Exception as e:

                print(
                    "❌ Banking group error:",
                    e
                )

    except Exception as e:

        print(
            "❌ Group link error:",
            e
        )


async def post_init(
    application
):

    await send_group_links(
        application
    )


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
            start
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            start_exam,
            pattern=r"^start_(ssc|banking)\|"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            answer_question,
            pattern=r"^answer\|"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            timer_button,
            pattern=r"^timer$"
        )
    )

    print(
        "🚀 Exam Bot Started"
    )

    print(
        "🆔 Current Exam ID:",
        EXAM_ID
    )

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()

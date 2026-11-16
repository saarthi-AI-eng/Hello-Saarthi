"""Learning analytics computed from quiz attempts, code submissions and chat activity.

Student view (WBS 4.1 learning trackers): per-topic accuracy, trend, weak topics with
recommended materials, syllabus coverage, class median, streak and badges.
Teacher view (WBS 4.2 student performance): score histogram, at-risk students,
per-topic class accuracy, most-missed questions and a CSV export.

No AI is involved. Everything is derived from rows that already exist.
"""

from __future__ import annotations

import csv
import io
import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.dao.notification_dao import NotificationDAO
from saarthi_backend.model import (
    ChatMessage,
    CodeProblem,
    CodeSubmission,
    Conversation,
    Course,
    CourseModule,
    Enrollment,
    Material,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    User,
)

WEAK_BELOW = 70.0  # a topic below this accuracy is "weak" for a student


def at_risk_threshold() -> float:
    """Average quiz score (%) below which a student is flagged at risk (env AT_RISK_THRESHOLD)."""
    try:
        return float(os.environ.get("AT_RISK_THRESHOLD", "50"))
    except ValueError:
        return 50.0


def _r(v: float | None, n: int = 1) -> float | None:
    return None if v is None else round(float(v), n)


def _day(dt: datetime | None) -> date | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date()


def _answers(attempt: QuizAttempt) -> list[dict]:
    try:
        return json.loads(attempt.answers_json or "[]")
    except (TypeError, ValueError):
        return []


async def _attempts_with_quizzes(db: AsyncSession, course_ids: list[int], user_id: int | None = None):
    """Submitted attempts (with their quiz) for the given courses, oldest first."""
    if not course_ids:
        return []
    stmt = (
        select(QuizAttempt, Quiz)
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .where(Quiz.course_id.in_(course_ids), QuizAttempt.submitted_at.is_not(None), QuizAttempt.score.is_not(None))
        .order_by(QuizAttempt.submitted_at)
    )
    if user_id is not None:
        stmt = stmt.where(QuizAttempt.user_id == user_id)
    return (await db.execute(stmt)).all()


async def _questions(db: AsyncSession, quiz_ids: set[int]) -> dict[str, QuizQuestion]:
    if not quiz_ids:
        return {}
    rows = (await db.execute(select(QuizQuestion).where(QuizQuestion.quiz_id.in_(quiz_ids)))).scalars().all()
    return {str(q.id): q for q in rows}


def _graded_answers(attempt: QuizAttempt, quiz: Quiz, questions: dict[str, QuizQuestion]):
    """(question, topic, is_correct) for each stored answer of an attempt."""
    for a in _answers(attempt):
        q = questions.get(str(a.get("questionId")))
        if q is None:
            continue
        topic = q.topic or quiz.topic or "General"
        yield q, topic, a.get("selectedIndex") == q.correct_index


# ── Streak ──────────────────────────────────────────────────────────────────

async def active_days(db: AsyncSession, user_id: int, since_days: int = 400) -> set[date]:
    """Days (UTC) on which the user submitted a quiz or code, or asked the AI tutor."""
    since = datetime.now(timezone.utc) - timedelta(days=since_days)
    days: set[date] = set()
    for stmt in (
        select(QuizAttempt.submitted_at).where(QuizAttempt.user_id == user_id, QuizAttempt.submitted_at >= since),
        select(CodeSubmission.created_at).where(CodeSubmission.user_id == user_id, CodeSubmission.created_at >= since),
        select(ChatMessage.created_at)
        .join(Conversation, Conversation.id == ChatMessage.conversation_id)
        .where(Conversation.user_id == user_id, ChatMessage.role == "user", ChatMessage.created_at >= since),
    ):
        days.update(d for d in (_day(r[0]) for r in (await db.execute(stmt)).all()) if d)
    return days


def streak_from_days(days: set[date], today: date | None = None) -> int:
    """Consecutive active days ending today (or yesterday, so the streak survives until tonight)."""
    today = today or datetime.now(timezone.utc).date()
    cur = today if today in days else today - timedelta(days=1)
    n = 0
    while cur in days:
        n += 1
        cur -= timedelta(days=1)
    return n


async def streak_days(db: AsyncSession, user_id: int) -> int:
    return streak_from_days(await active_days(db, user_id))


# ── Student analytics ───────────────────────────────────────────────────────

async def _course_topics(db: AsyncSession, course_id: int) -> list[str]:
    """Module titles in order, then topics used by quizzes and materials that have no module row."""
    mods = (await db.execute(
        select(CourseModule.title).where(CourseModule.course_id == course_id)
        .order_by(CourseModule.sort_order, CourseModule.id)
    )).scalars().all()
    seen = {m.lower() for m in mods}
    out = list(mods)
    for stmt in (
        select(Quiz.topic).where(Quiz.course_id == course_id, Quiz.topic.is_not(None)),
        select(Material.topic).where(Material.course_id == course_id, Material.topic.is_not(None)),
    ):
        for t in (await db.execute(stmt)).scalars().all():
            if t and t.strip() and t.lower() not in seen:
                seen.add(t.lower())
                out.append(t)
    return out


async def _materials_for(db: AsyncSession, course_id: int, topic: str, limit: int = 3) -> list[dict]:
    rows = (await db.execute(
        select(Material).where(Material.course_id == course_id)
        .where((Material.topic.ilike(topic)) | (Material.title.ilike(f"%{topic}%")))
        .order_by(Material.created_at.desc()).limit(limit)
    )).scalars().all()
    return [{"id": str(m.id), "title": m.title, "type": m.type, "courseId": str(course_id)} for m in rows]


async def student_analytics(db: AsyncSession, user: User) -> dict:
    courses = (await db.execute(
        select(Course).join(Enrollment, Enrollment.course_id == Course.id).where(Enrollment.user_id == user.id)
    )).scalars().all()
    course_ids = [c.id for c in courses]
    title = {c.id: c.title for c in courses}

    mine = await _attempts_with_quizzes(db, course_ids, user.id)
    questions = await _questions(db, {q.id for _, q in mine})

    # Per topic and per difficulty accuracy.
    topic_stats: dict[tuple[int, str], list[int]] = defaultdict(lambda: [0, 0])
    diff_stats: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for attempt, quiz in mine:
        for q, topic, ok in _graded_answers(attempt, quiz, questions):
            topic_stats[(quiz.course_id, topic)][0] += int(ok)
            topic_stats[(quiz.course_id, topic)][1] += 1
            diff_stats[q.difficulty or "recall"][0] += int(ok)
            diff_stats[q.difficulty or "recall"][1] += 1

    topics = sorted(
        (
            {"topic": t, "courseId": str(cid), "course": title.get(cid, ""), "correct": c, "total": n,
             "accuracy": _r(c * 100 / n)}
            for (cid, t), (c, n) in topic_stats.items() if n
        ),
        key=lambda x: x["accuracy"],
    )

    # Weak topics with notes to read and a quiz to retry.
    quiz_by_topic = {}
    for _, quiz in mine:
        quiz_by_topic.setdefault((quiz.course_id, (quiz.topic or "").lower()), quiz)
    weak = []
    for t in topics:
        if t["accuracy"] >= WEAK_BELOW:
            continue
        cid = int(t["courseId"])
        retry = quiz_by_topic.get((cid, t["topic"].lower()))
        weak.append({
            **t,
            "materials": await _materials_for(db, cid, t["topic"]),
            "retryQuiz": {"id": str(retry.id), "title": retry.title} if retry else None,
        })

    # Trend: one point per day with attempts, last 30 days.
    since = datetime.now(timezone.utc).date() - timedelta(days=29)
    per_day: dict[date, list[float]] = defaultdict(list)
    for attempt, _ in mine:
        d = _day(attempt.submitted_at)
        if d and d >= since:
            per_day[d].append(attempt.score)
    trend = [
        {"date": (since + timedelta(days=i)).isoformat(),
         "avgScore": _r(sum(per_day[since + timedelta(days=i)]) / len(per_day[since + timedelta(days=i)]))
         if per_day.get(since + timedelta(days=i)) else None,
         "attempts": len(per_day.get(since + timedelta(days=i), []))}
        for i in range(30)
    ]

    # Coverage and class comparison per course.
    everyone = await _attempts_with_quizzes(db, course_ids)
    by_course_user: dict[int, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for attempt, quiz in everyone:
        by_course_user[quiz.course_id][attempt.user_id].append(attempt.score)
    covered_topics: dict[int, set[str]] = defaultdict(set)
    for (cid, t) in topic_stats:
        covered_topics[cid].add(t.lower())
    for _, quiz in mine:
        if quiz.topic:
            covered_topics[quiz.course_id].add(quiz.topic.lower())

    course_out = []
    for c in courses:
        mods = await _course_topics(db, c.id)
        modules = [{"title": m, "covered": m.lower() in covered_topics[c.id]} for m in mods]
        avgs = [sum(s) / len(s) for s in by_course_user[c.id].values() if s]
        my_scores = by_course_user[c.id].get(user.id, [])
        course_out.append({
            "id": str(c.id), "title": c.title, "code": c.code,
            "myAvg": _r(sum(my_scores) / len(my_scores)) if my_scores else None,
            "classMedian": _r(median(avgs)) if avgs else None,
            "classmates": len(avgs),
            "attempts": len(my_scores),
            "modules": modules,
            "coverage": _r(sum(m["covered"] for m in modules) * 100 / len(modules)) if modules else None,
        })

    # Code submissions and activity.
    code_rows = (await db.execute(
        select(CodeSubmission, CodeProblem.title)
        .join(CodeProblem, CodeProblem.id == CodeSubmission.problem_id)
        .where(CodeSubmission.user_id == user.id).order_by(CodeSubmission.created_at.desc())
    )).all()
    days = await active_days(db, user.id)
    streak = streak_from_days(days)
    scores = [a.score for a, _ in mine]
    answered = sum(n for _, n in topic_stats.values())
    correct = sum(c for c, _ in topic_stats.values())

    recent = sorted(
        [{"type": "quiz", "title": f"Scored {round(a.score)}% on {q.title}", "at": a.submitted_at.isoformat()}
         for a, q in mine]
        + [{"type": "code",
            "title": f"{'Solved' if s.total and s.passed == s.total else 'Submitted'}: {t} ({s.passed}/{s.total} tests)",
            "at": s.created_at.isoformat()} for s, t in code_rows],
        key=lambda x: x["at"], reverse=True,
    )[:8]

    solved = {t for s, t in code_rows if s.total and s.passed == s.total}
    badges = [
        {"id": "first-quiz", "title": "First Quiz", "description": "Submit your first quiz", "earned": len(scores) >= 1},
        {"id": "perfect", "title": "Perfect Score", "description": "Score 100% on a quiz", "earned": any(s >= 100 for s in scores)},
        {"id": "five-quizzes", "title": "Quiz Regular", "description": "Submit 5 quizzes", "earned": len(scores) >= 5},
        {"id": "topic-master", "title": "Topic Master", "description": "90%+ on a topic with 5+ questions",
         "earned": any(n >= 5 and c / n >= 0.9 for c, n in topic_stats.values())},
        {"id": "coder", "title": "Problem Solver", "description": "Pass every test on a Code Lab problem", "earned": bool(solved)},
        {"id": "streak-3", "title": "3-Day Streak", "description": "Study 3 days in a row", "earned": streak >= 3},
        {"id": "streak-7", "title": "7-Day Streak", "description": "Study 7 days in a row", "earned": streak >= 7},
    ]

    # Next step: weakest topic's notes, else the first module not touched yet.
    next_resource = None
    for w in weak:
        if w["materials"]:
            next_resource = {"reason": f"Your weakest topic is {w['topic']} ({round(w['accuracy'])}%)", **w["materials"][0]}
            break
        if w["retryQuiz"]:
            next_resource = {"reason": f"Your weakest topic is {w['topic']} ({round(w['accuracy'])}%)",
                             "title": f"Retry: {w['retryQuiz']['title']}", "type": "quiz", "id": w["retryQuiz"]["id"],
                             "courseId": w["courseId"]}
            break
    if next_resource is None:
        for c in course_out:
            gap = next((m["title"] for m in c["modules"] if not m["covered"]), None)
            if gap:
                mats = await _materials_for(db, int(c["id"]), gap, 1)
                next_resource = {"reason": f"You have not practised {gap} in {c['title']} yet",
                                 **(mats[0] if mats else {"title": f"{gap} quizzes", "type": "quiz", "id": None,
                                                          "courseId": c["id"]})}
                break

    return {
        "summary": {
            "courses": len(courses),
            "quizzesTaken": len({q.id for _, q in mine}),
            "attempts": len(scores),
            "avgScore": _r(sum(scores) / len(scores)) if scores else None,
            "accuracy": _r(correct * 100 / answered) if answered else None,
            "codeSolved": len(solved),
            "streakDays": streak,
            "activeDays30": sum(1 for d in days if d >= since),
        },
        "topics": topics,
        "difficulty": [
            {"level": lvl, "correct": diff_stats[lvl][0], "total": diff_stats[lvl][1],
             "accuracy": _r(diff_stats[lvl][0] * 100 / diff_stats[lvl][1]) if diff_stats[lvl][1] else None}
            for lvl in ("recall", "application", "analysis")
        ],
        "weakTopics": weak,
        "trend": trend,
        "courses": course_out,
        "badges": badges,
        "recent": recent,
        "nextResource": next_resource,
    }


# ── Teacher: class performance ──────────────────────────────────────────────

async def teacher_courses(db: AsyncSession, user: User) -> list[Course]:
    stmt = select(Course).order_by(Course.created_at.desc())
    if user.role != "admin":
        stmt = stmt.where(Course.owner_id == user.id)
    return list((await db.execute(stmt)).scalars().all())


async def class_performance(db: AsyncSession, course: Course, threshold: float) -> dict:
    students = (await db.execute(
        select(User).join(Enrollment, Enrollment.user_id == User.id).where(Enrollment.course_id == course.id)
        .order_by(User.full_name)
    )).scalars().all()
    rows = await _attempts_with_quizzes(db, [course.id])
    questions = await _questions(db, {q.id for _, q in rows})
    total_quizzes = len((await db.execute(select(Quiz.id).where(Quiz.course_id == course.id))).all())

    per_user: dict[int, list[QuizAttempt]] = defaultdict(list)
    topic_stats: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    q_stats: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for attempt, quiz in rows:
        per_user[attempt.user_id].append((attempt, quiz))
        for q, topic, ok in _graded_answers(attempt, quiz, questions):
            topic_stats[topic][0] += int(ok)
            topic_stats[topic][1] += 1
            q_stats[str(q.id)][0] += int(not ok)
            q_stats[str(q.id)][1] += 1

    student_out = []
    for s in students:
        attempts = per_user.get(s.id, [])
        scores = [a.score for a, _ in attempts]
        avg = sum(scores) / len(scores) if scores else None
        last = max((a.submitted_at for a, _ in attempts), default=None)
        student_out.append({
            "id": str(s.id), "name": s.full_name, "email": s.email,
            "attempts": len(scores), "quizzesTaken": len({q.id for _, q in attempts}), "totalQuizzes": total_quizzes,
            "avgScore": _r(avg), "bestScore": _r(max(scores)) if scores else None,
            "lastActive": last.isoformat() if last else None,
            "status": "not_started" if avg is None else ("at_risk" if avg < threshold else "on_track"),
        })
    student_out.sort(key=lambda x: (x["avgScore"] is None, x["avgScore"] if x["avgScore"] is not None else 0))

    avgs = [s["avgScore"] for s in student_out if s["avgScore"] is not None]
    histogram = [{"range": f"{lo}-{lo + 10 if lo < 90 else 100}", "students": 0} for lo in range(0, 100, 10)]
    for v in avgs:
        histogram[min(int(v // 10), 9)]["students"] += 1

    most_missed = sorted(
        (
            {"question": questions[qid].question_text, "topic": questions[qid].topic, "missed": m, "answered": n,
             "missRate": _r(m * 100 / n)}
            for qid, (m, n) in q_stats.items() if n and m
        ),
        key=lambda x: (-x["missRate"], -x["answered"]),
    )[:5]

    return {
        "course": {"id": str(course.id), "title": course.title, "code": course.code},
        "threshold": threshold,
        "summary": {
            "students": len(students),
            "active": len(avgs),
            "atRisk": sum(1 for s in student_out if s["status"] == "at_risk"),
            "notStarted": sum(1 for s in student_out if s["status"] == "not_started"),
            "mean": _r(sum(avgs) / len(avgs)) if avgs else None,
            "median": _r(median(avgs)) if avgs else None,
            "attempts": len(rows),
        },
        "histogram": histogram,
        "students": student_out,
        "topics": sorted(
            ({"topic": t, "correct": c, "total": n, "accuracy": _r(c * 100 / n)} for t, (c, n) in topic_stats.items() if n),
            key=lambda x: x["accuracy"],
        ),
        "mostMissed": most_missed,
    }


def class_csv(perf: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Name", "Email", "Quizzes taken", "Total quizzes", "Attempts", "Average %", "Best %", "Last active", "Status"])
    for s in perf["students"]:
        w.writerow([s["name"], s["email"], s["quizzesTaken"], s["totalQuizzes"], s["attempts"],
                    "" if s["avgScore"] is None else s["avgScore"], "" if s["bestScore"] is None else s["bestScore"],
                    s["lastActive"] or "", s["status"].replace("_", " ")])
    return buf.getvalue()


# ── At-risk alert after a quiz submit ───────────────────────────────────────

async def alert_if_at_risk(db: AsyncSession, student: User, quiz: Quiz) -> bool:
    """Notify the course teacher when this submit drops the student's course average below the threshold.

    Only the crossing is notified (the average before this attempt was at or above the
    threshold, or this was the first attempt), so a struggling student does not cause
    a notification on every attempt.
    """
    if quiz.course_id is None or student.role != "student":
        return False
    course = (await db.execute(select(Course).where(Course.id == quiz.course_id))).scalar_one_or_none()
    if course is None or course.owner_id is None:
        return False
    scores = [a.score for a, _ in await _attempts_with_quizzes(db, [course.id], student.id)]
    if not scores:
        return False
    threshold = at_risk_threshold()
    now_avg = sum(scores) / len(scores)
    before = scores[:-1]
    was_ok = not before or sum(before) / len(before) >= threshold
    if now_avg >= threshold or not was_ok:
        return False
    await NotificationDAO.create(
        db, user_id=course.owner_id, type="at_risk",
        title=f"{student.full_name} may need help in {course.title}",
        body=f"Quiz average dropped to {round(now_avg)}% (below {round(threshold)}%) after '{quiz.title}'.",
        link="/progress",
    )
    return True

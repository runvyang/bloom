"""Badges + Points system for gamification."""
from storage import get_conn, get_streak_info, get_recent_records
import os

# ─── Badge Definitions ───────────────────────────────────

BADGES = [
    # Time-based
    {"id": "learner_1h",   "name": "初学者",    "icon": "🌟",  "desc": "累计学习满 1 小时",           "check": "total_hours", "threshold": 1},
    {"id": "learner_10h",  "name": "探索者",    "icon": "🔭",  "desc": "累计学习满 10 小时",          "check": "total_hours", "threshold": 10},
    {"id": "learner_50h",  "name": "学霸",      "icon": "🎓",  "desc": "累计学习满 50 小时",          "check": "total_hours", "threshold": 50},
    {"id": "learner_100h", "name": "大师",      "icon": "👑",  "desc": "累计学习满 100 小时",         "check": "total_hours", "threshold": 100},

    # Streak-based
    {"id": "streak_7d",    "name": "自律达人",  "icon": "🔥",  "desc": "连续打卡 7 天",               "check": "streak",      "threshold": 7},
    {"id": "streak_30d",   "name": "毅力之星",  "icon": "💎",  "desc": "连续打卡 30 天",              "check": "streak",      "threshold": 30},

    # Mastery-based (per course)
    {"id": "math_10",     "name": "数学之星",   "icon": "📐",  "desc": "数学精通 10 个知识点",       "check": "course_mastered", "course": "math", "threshold": 10},
    {"id": "chinese_10",  "name": "语文之星",   "icon": "📖",  "desc": "语文精通 10 个知识点",       "check": "course_mastered", "course": "chinese", "threshold": 10},
    {"id": "english_10",  "name": "英语之星",   "icon": "🇬🇧",  "desc": "英语精通 10 个知识点",       "check": "course_mastered", "course": "english", "threshold": 10},
    {"id": "coding_10",   "name": "编程之星",   "icon": "💻",  "desc": "编程精通 5 个知识点",        "check": "course_mastered", "course": "coding", "threshold": 5},

    # Achievement-based
    {"id": "all_courses", "name": "全能选手",   "icon": "🏆",  "desc": "所有科目都有学习记录",        "check": "all_courses_active"},
    {"id": "first_100",   "name": "勤学苦练",   "icon": "📚",  "desc": "累计完成 100 节课",           "check": "total_sessions", "threshold": 100},
]


def init_badges():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS points_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            points INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_points_user ON points_log(user_id);

        CREATE TABLE IF NOT EXISTS earned_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            badge_id TEXT NOT NULL,
            earned_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, badge_id)
        );
        CREATE INDEX IF NOT EXISTS idx_badges_user ON earned_badges(user_id);
    """)
    conn.commit()
    conn.close()


def add_points(user_id: str, points: int, reason: str):
    conn = get_conn()
    conn.execute("INSERT INTO points_log (user_id, points, reason) VALUES (?,?,?)",
                 (user_id, points, reason))
    conn.commit()
    conn.close()


def get_total_points(user_id: str) -> int:
    conn = get_conn()
    row = conn.execute("SELECT SUM(points) as t FROM points_log WHERE user_id=?",
                       (user_id,)).fetchone()
    conn.close()
    return int(row["t"]) if row and row["t"] else 0


def get_earned_badges(user_id: str) -> list:
    conn = get_conn()
    rows = conn.execute("SELECT badge_id, earned_at FROM earned_badges WHERE user_id=? ORDER BY earned_at DESC",
                        (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def award_badge(user_id: str, badge_id: str) -> bool:
    conn = get_conn()
    try:
        conn.execute("INSERT INTO earned_badges (user_id, badge_id) VALUES (?,?)",
                     (user_id, badge_id))
        conn.commit()
        ok = True
    except Exception:
        ok = False  # already earned
    conn.close()
    return ok


def count_mastered_in_course(user_id: str, course: str) -> int:
    """Count mastered knowledge points in a course state file."""
    state_path = f"data/student/{user_id}/{course}_map.md"
    if not os.path.exists(state_path):
        return 0
    mastered = 0
    with open(state_path, "r", encoding="utf-8") as f:
        for line in f:
            if "| 精通" in line or "| 优秀" in line or "Level 4" in line or "Level 5" in line:
                mastered += 1
    return mastered


def check_and_award(user_id: str) -> dict:
    """Check all badge conditions and award newly earned ones. Returns new badges + total points."""
    earned = [b["badge_id"] for b in get_earned_badges(user_id)]
    new_badges = []
    total_hours = 0

    # Get total learning hours
    try:
        conn = get_conn()
        row = conn.execute("SELECT SUM(total_minutes) as t FROM learning_streaks WHERE user_id=?",
                           (user_id,)).fetchone()
        if row and row["t"]:
            total_hours = int(row["t"]) / 60
        conn.close()
    except Exception:
        pass

    streak = get_streak_info(user_id).get("streak", 0)

    # Count total sessions
    total_sessions = 0
    try:
        conn = get_conn()
        row = conn.execute("SELECT COUNT(*) as c FROM daily_tasks WHERE user_id=? AND status='completed'",
                           (user_id,)).fetchone()
        if row: total_sessions = row["c"]
        conn.close()
    except Exception:
        pass

    # Which courses have been used
    courses_active = set()
    for c in ["math","chinese","english","coding"]:
        if os.path.exists(f"data/student/{user_id}/{c}_state.md"):
            courses_active.add(c)

    for badge in BADGES:
        if badge["id"] in earned:
            continue
        earned_it = False
        check = badge["check"]

        if check == "total_hours" and total_hours >= badge["threshold"]:
            earned_it = True
        elif check == "streak" and streak >= badge["threshold"]:
            earned_it = True
        elif check == "course_mastered":
            m = count_mastered_in_course(user_id, badge["course"])
            if m >= badge["threshold"]:
                earned_it = True
        elif check == "all_courses_active" and len(courses_active) >= 4:
            earned_it = True
        elif check == "total_sessions" and total_sessions >= badge["threshold"]:
            earned_it = True

        if earned_it:
            award_badge(user_id, badge["id"])
            add_points(user_id, 50, f"获得徽章: {badge['name']}")
            new_badges.append(badge)

    total_points = get_total_points(user_id)
    all_earned = get_earned_badges(user_id)

    return {
        "points": total_points,
        "badges": [b for b in BADGES if b["id"] in [e["badge_id"] for e in all_earned]],
        "new_badges": new_badges,
        "all_badge_ids": [e["badge_id"] for e in all_earned]
    }

# Initialize on import
init_badges()


import json
import os
import uuid
from datetime import date, datetime, timedelta
from html import escape

import streamlit as st
from streamlit_dnd import dnd

DATA_FILE = "task.json"

st.set_page_config(
    page_title="Taskboard",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# DATA
# ============================================================

STATUSES = {
    "todo": {"label": "To Do", "icon": "○"},
    "in_progress": {"label": "In Progress", "icon": "◐"},
    "blocked": {"label": "Blocked", "icon": "⊘"},
    "done": {"label": "Done", "icon": "✓"},
}

PRIORITIES = ("high", "medium", "low")


def generate_id(prefix="id"):
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def save_data(data):
    temp_file = DATA_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(temp_file, DATA_FILE)


def load_data():
    if not os.path.exists(DATA_FILE):
        data = {"people": [], "tasks": [], "notifications": []}
        save_data(data)
        return data

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {"people": [], "tasks": [], "notifications": []}

    data.setdefault("people", [])
    data.setdefault("tasks", [])
    data.setdefault("notifications", [])

    # Migration from the previous version.
    for task in data["tasks"]:
        task.setdefault("id", generate_id("task"))
        task.setdefault("person_id", "")
        task.setdefault("title", "Untitled task")
        task.setdefault("description", "")
        task.setdefault("priority", "medium")
        task.setdefault("planned_date", None)
        task.setdefault("created_at", now_iso())
        task.setdefault("completed_at", None)

        old_status = task.get("status", "pending")
        if old_status == "completed":
            task["status"] = "done"
        elif old_status not in STATUSES:
            task["status"] = "todo"

        task.setdefault("position", 0)

    # Give stable positions to old tasks.
    for status in STATUSES:
        status_tasks = sorted(
            [t for t in data["tasks"] if t.get("status") == status],
            key=lambda t: (t.get("position", 0), t.get("created_at", "")),
        )
        for index, task in enumerate(status_tasks):
            task["position"] = index

    return data


data = load_data()

# ============================================================
# DATE / TASK HELPERS
# ============================================================


def get_monday(d):
    return d - timedelta(days=d.weekday())


def get_sunday(d):
    return get_monday(d) + timedelta(days=6)


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def format_date(value):
    d = parse_date(value)
    return d.strftime("%d %b %Y") if d else "-"


def is_this_week(value, reference_date=None):
    d = parse_date(value)
    if not d:
        return False
    reference_date = reference_date or date.today()
    return get_monday(reference_date) <= d <= get_sunday(reference_date)


def is_this_month(value, reference_date=None):
    d = parse_date(value)
    if not d:
        return False
    reference_date = reference_date or date.today()
    return d.year == reference_date.year and d.month == reference_date.month


def is_overdue(task):
    if task.get("status") == "done":
        return False
    d = parse_date(task.get("planned_date"))
    return bool(d and d < date.today())


def is_due_today(task):
    return task.get("status") != "done" and task.get("planned_date") == date.today().isoformat()


def get_person_name(person_id):
    for person in data["people"]:
        if person["id"] == person_id:
            return person["name"]
    return "Unassigned"


def get_person(person_id):
    for person in data["people"]:
        if person["id"] == person_id:
            return person
    return None


def task_by_id(task_id):
    for task in data["tasks"]:
        if task["id"] == task_id:
            return task
    return None


def task_matches_profile(task):
    selected = st.session_state.active_profile
    return selected == "all" or task.get("person_id") == selected


def visible_tasks():
    return [t for t in data["tasks"] if task_matches_profile(t)]


def ordered_tasks(status=None, visible_only=True):
    tasks = visible_tasks() if visible_only else list(data["tasks"])
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    return sorted(
        tasks,
        key=lambda t: (t.get("position", 0), t.get("planned_date") or "9999-12-31", t.get("created_at", "")),
    )


def reindex_positions():
    for status in STATUSES:
        tasks = sorted(
            [t for t in data["tasks"] if t.get("status") == status],
            key=lambda t: (t.get("position", 0), t.get("created_at", "")),
        )
        for index, task in enumerate(tasks):
            task["position"] = index


def set_task_status(task, new_status):
    old_status = task.get("status", "todo")
    if old_status == new_status:
        return

    max_position = max(
        [t.get("position", 0) for t in data["tasks"] if t.get("status") == new_status] or [-1]
    )
    task["status"] = new_status
    task["position"] = max_position + 1

    if new_status == "done":
        task["completed_at"] = date.today().isoformat()
    elif old_status == "done":
        task["completed_at"] = None


# ============================================================
# NOTIFICATIONS
# ============================================================


def notification_exists(notification_id):
    return any(n.get("id") == notification_id for n in data["notifications"])


def ensure_notifications():
    changed = False
    existing = {n.get("id") for n in data["notifications"]}

    for task in data["tasks"]:
        if is_overdue(task):
            nid = f"overdue:{task['id']}:{task.get('planned_date')}"
            if nid not in existing:
                data["notifications"].insert(
                    0,
                    {
                        "id": nid,
                        "message": f"{get_person_name(task.get('person_id'))}: {task.get('title')} is overdue.",
                        "task_id": task["id"],
                        "type": "overdue",
                        "created_at": now_iso(),
                        "read": False,
                    },
                )
                existing.add(nid)
                changed = True

        if is_due_today(task):
            nid = f"today:{task['id']}:{date.today().isoformat()}"
            if nid not in existing:
                data["notifications"].insert(
                    0,
                    {
                        "id": nid,
                        "message": f"{get_person_name(task.get('person_id'))}: {task.get('title')} is due today.",
                        "task_id": task["id"],
                        "type": "due",
                        "created_at": now_iso(),
                        "read": False,
                    },
                )
                existing.add(nid)
                changed = True

    if len(data["notifications"]) > 200:
        data["notifications"] = data["notifications"][:200]
        changed = True

    if changed:
        save_data(data)


ensure_notifications()


# ============================================================
# SESSION STATE / PROFILE
# ============================================================

if "page" not in st.session_state:
    st.session_state.page = "Board"

if "active_profile" not in st.session_state:
    st.session_state.active_profile = "all"

if "selected_week" not in st.session_state:
    st.session_state.selected_week = get_monday(date.today())

# Keep a deleted profile from breaking the app.
valid_profile_ids = {"all"} | {p["id"] for p in data["people"]}
if st.session_state.active_profile not in valid_profile_ids:
    st.session_state.active_profile = "all"


def switch_page(page):
    st.session_state.page = page


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
<style>
:root {
    --navy: #102a43;
    --muted: #66788a;
    --border: #dfe5eb;
    --surface: #ffffff;
    --surface-soft: #f6f8fb;
    --danger: #c62828;
    --warning: #c77700;
    --success: #2e7d32;
}

.block-container {
    padding-top: 1.3rem;
    padding-bottom: 3rem;
    max-width: 1500px;
}

.app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    margin-bottom: 18px;
}

.brand {
    color: var(--navy);
    font-size: 30px;
    font-weight: 750;
    letter-spacing: -0.4px;
}

.subtitle {
    color: var(--muted);
    margin-top: -8px;
    margin-bottom: 18px;
}

.profile-pill {
    border: 1px solid var(--border);
    border-radius: 999px;
    background: var(--surface);
    padding: 8px 13px;
    color: var(--navy);
    font-weight: 650;
    text-align: center;
}

.stat-card {
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 17px;
    background: var(--surface);
    min-height: 105px;
}

.stat-number {
    font-size: 29px;
    font-weight: 750;
    color: var(--navy);
}

.stat-label {
    color: var(--muted);
    font-size: 13px;
    margin-top: 3px;
}

.kanban-column {
    border: 1px solid var(--border);
    border-radius: 14px;
    background: #f8fafc;
    padding: 10px;
    min-height: 420px;
}

.kanban-title {
    font-size: 15px;
    font-weight: 750;
    color: var(--navy);
    padding: 5px 4px 10px;
}

.task-card-inner {
    border: 1px solid var(--border);
    border-radius: 11px;
    padding: 11px;
    background: var(--surface);
    margin-bottom: 7px;
}

.task-title {
    font-size: 14px;
    font-weight: 700;
    color: #183b56;
    line-height: 1.35;
}

.task-meta {
    color: var(--muted);
    font-size: 12px;
    margin-top: 7px;
}

.badge {
    display: inline-block;
    border-radius: 999px;
    padding: 2px 7px;
    font-size: 10px;
    font-weight: 750;
    text-transform: uppercase;
    margin-right: 4px;
}

.badge-high { background: #fde8e8; color: #b42318; }
.badge-medium { background: #fff4d6; color: #9a6700; }
.badge-low { background: #e8f5e9; color: #2e7d32; }

.overdue-text { color: var(--danger); font-weight: 700; }
.today-text { color: var(--warning); font-weight: 700; }

.notification-panel {
    border: 1px solid var(--border);
    border-radius: 13px;
    padding: 12px;
    background: var(--surface);
}

.notification-item {
    padding: 10px 0;
    border-bottom: 1px solid #edf0f3;
}

.notification-item:last-child {
    border-bottom: 0;
}

.small-muted {
    color: var(--muted);
    font-size: 12px;
}

.empty-state {
    color: var(--muted);
    text-align: center;
    padding: 38px 12px;
}

div[data-testid="stSidebar"] {
    background: #f4f6f9;
}

div[data-testid="stSidebar"] button {
    border-radius: 9px;
}

button[kind="primary"] {
    border-radius: 9px;
}

@media (max-width: 900px) {
    .brand { font-size: 25px; }
}
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# HEADER
# ============================================================

with st.sidebar:
    st.markdown("## 📋 Taskboard")
    st.caption("Simple planning. Visible ownership. No authentication circus.")
    st.divider()

    pages = ["Board", "Dashboard", "Weekly Planner", "People", "All Tasks"]
    for page in pages:
        if st.button(
            page,
            key=f"nav_{page}",
            use_container_width=True,
            type="primary" if st.session_state.page == page else "secondary",
        ):
            st.session_state.page = page
            st.rerun()

    st.divider()
    st.markdown("### Active profile")

    profile_options = {"All People": "all"}
    profile_options.update({p["name"]: p["id"] for p in data["people"]})
    names = list(profile_options.keys())
    current_name = next(
        (name for name, pid in profile_options.items() if pid == st.session_state.active_profile),
        "All People",
    )
    selected_name = st.selectbox(
        "Profile",
        names,
        index=names.index(current_name),
        label_visibility="collapsed",
        key="profile_selector",
    )
    selected_id = profile_options[selected_name]
    if selected_id != st.session_state.active_profile:
        st.session_state.active_profile = selected_id
        st.rerun()

    st.divider()
    active_label = "All People" if st.session_state.active_profile == "all" else get_person_name(st.session_state.active_profile)
    st.caption(f"Showing work for **{active_label}**")

unread_count = sum(1 for n in data["notifications"] if not n.get("read"))

header_left, header_profile, header_notifications = st.columns([6, 2, 1])

with header_left:
    st.markdown('<div class="brand">📋 Taskboard</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Plan the work. Track progress. Keep ownership obvious.</div>',
        unsafe_allow_html=True,
    )

with header_profile:
    st.markdown(
        f'<div class="profile-pill">👤 {escape(active_label)}</div>',
        unsafe_allow_html=True,
    )

with header_notifications:
    notification_label = f"🔔 {unread_count}" if unread_count else "🔔"
    if st.button(notification_label, key="open_notifications", use_container_width=True):
        st.session_state.show_notifications = not st.session_state.get("show_notifications", False)
        st.rerun()

if st.session_state.get("show_notifications", False):
    with st.container(border=True):
        n1, n2 = st.columns([5, 1])
        with n1:
            st.markdown("### Notifications")
        with n2:
            if unread_count and st.button("Mark all as read", key="mark_all_read"):
                for n in data["notifications"]:
                    n["read"] = True
                save_data(data)
                st.rerun()

        visible_notifications = [
            n for n in data["notifications"]
            if n.get("task_id") is None or task_by_id(n.get("task_id"))
        ][:30]

        if not visible_notifications:
            st.caption("No notifications.")
        else:
            for n in visible_notifications:
                icon = {"overdue": "🔴", "due": "🟠"}.get(n.get("type"), "🔵")
                read_style = "" if not n.get("read") else "opacity:0.65;"
                st.markdown(
                    f'<div class="notification-item" style="{read_style}">'
                    f'{icon} {escape(n.get("message", ""))}'
                    f'<div class="small-muted">{escape(n.get("created_at", "")[:16].replace("T", " "))}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if not n.get("read") and st.button("Mark read", key=f"read_{n['id']}"):
                    n["read"] = True
                    save_data(data)
                    st.rerun()

# ============================================================
# CRUD
# ============================================================


def add_task(title, description, person_id, planned_date, priority, status="todo"):
    existing_positions = [
        t.get("position", 0) for t in data["tasks"] if t.get("status") == status
    ]
    task = {
        "id": generate_id("task"),
        "person_id": person_id,
        "title": title.strip(),
        "description": description.strip(),
        "status": status,
        "priority": priority,
        "planned_date": planned_date.isoformat() if planned_date else None,
        "completed_at": date.today().isoformat() if status == "done" else None,
        "created_at": now_iso(),
        "position": max(existing_positions or [-1]) + 1,
    }
    data["tasks"].append(task)
    save_data(data)
    return task


def delete_task(task_id):
    data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
    data["notifications"] = [n for n in data["notifications"] if n.get("task_id") != task_id]
    reindex_positions()
    save_data(data)


def edit_task_form(task):
    with st.form(f"edit_{task['id']}"):
        title = st.text_input("Title", value=task.get("title", ""))
        description = st.text_area("Description", value=task.get("description", ""))
        c1, c2, c3 = st.columns(3)
        with c1:
            person_id = st.selectbox(
                "Owner",
                [p["id"] for p in data["people"]],
                index=max(
                    0,
                    [p["id"] for p in data["people"]].index(task["person_id"])
                    if task.get("person_id") in [p["id"] for p in data["people"]]
                    else 0,
                ),
                format_func=get_person_name,
            )
        with c2:
            planned_date = st.date_input(
                "Due date",
                value=parse_date(task.get("planned_date")) or date.today(),
            )
        with c3:
            priority = st.selectbox(
                "Priority",
                PRIORITIES,
                index=PRIORITIES.index(task.get("priority", "medium"))
                if task.get("priority", "medium") in PRIORITIES else 1,
            )

        c1, c2 = st.columns(2)
        with c1:
            if st.form_submit_button("Save changes", type="primary", use_container_width=True):
                task["title"] = title.strip() or task["title"]
                task["description"] = description.strip()
                task["person_id"] = person_id
                task["planned_date"] = planned_date.isoformat()
                task["priority"] = priority
                save_data(data)
                ensure_notifications()
                st.session_state.editing_task = None
                st.rerun()
        with c2:
            if st.form_submit_button("Cancel", use_container_width=True):
                st.session_state.editing_task = None
                st.rerun()


# ============================================================
# KANBAN BOARD
# ============================================================


def render_task_card(task):
    due = parse_date(task.get("planned_date"))
    due_html = format_date(task.get("planned_date"))
    due_class = "overdue-text" if is_overdue(task) else "today-text" if is_due_today(task) else ""

    priority = task.get("priority", "medium")
    owner = get_person_name(task.get("person_id"))
    description = task.get("description", "")

    with st.container(key=f"task_card_{task['id']}", border=True):
        st.markdown(
            f'<div class="task-card-inner">'
            f'<div class="task-title">{escape(task.get("title", "Untitled task"))}</div>'
            f'<div class="task-meta">'
            f'<span class="badge badge-{escape(priority)}">{escape(priority)}</span>'
            f'{"👤 " + escape(owner) + " · " if st.session_state.active_profile == "all" else ""}'
            f'<span class="{due_class}">📅 {escape(due_html)}</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if description:
            st.caption(description[:160] + ("…" if len(description) > 160 else ""))

        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("Edit", key=f"edit_btn_{task['id']}", use_container_width=True):
                st.session_state.editing_task = task["id"]
                st.rerun()
        with b2:
            if task.get("status") == "done":
                if st.button("Undo", key=f"undo_{task['id']}", use_container_width=True):
                    set_task_status(task, "todo")
                    save_data(data)
                    st.rerun()
            else:
                if st.button("Done", key=f"done_{task['id']}", use_container_width=True):
                    set_task_status(task, "done")
                    save_data(data)
                    st.rerun()
        with b3:
            if st.button("Delete", key=f"del_{task['id']}", use_container_width=True):
                st.session_state.delete_task_id = task["id"]
                st.rerun()

        if st.session_state.get("delete_task_id") == task["id"]:
            st.warning("Delete this task permanently?")
            d1, d2 = st.columns(2)
            with d1:
                if st.button("Yes, delete", key=f"confirm_del_{task['id']}", type="primary", use_container_width=True):
                    delete_task(task["id"])
                    st.session_state.delete_task_id = None
                    st.rerun()
            with d2:
                if st.button("Cancel", key=f"cancel_del_{task['id']}", use_container_width=True):
                    st.session_state.delete_task_id = None
                    st.rerun()


def kanban_board():
    active_label = "All People" if st.session_state.active_profile == "all" else get_person_name(st.session_state.active_profile)
    st.subheader(f"Kanban Board · {active_label}")

    board_tasks = visible_tasks()

    if not data["people"]:
        st.warning("Add at least one person before creating tasks.")
    else:
        with st.expander("➕ Add task", expanded=False):
            with st.form("add_task_board"):
                c1, c2 = st.columns([2, 1])
                with c1:
                    title = st.text_input("Task title")
                    description = st.text_area("Description")
                with c2:
                    default_owner = (
                        st.session_state.active_profile
                        if st.session_state.active_profile != "all"
                        else data["people"][0]["id"]
                    )
                    owner_options = [p["id"] for p in data["people"]]
                    owner = st.selectbox(
                        "Owner",
                        owner_options,
                        index=owner_options.index(default_owner),
                        format_func=get_person_name,
                    )
                    planned_date = st.date_input("Due date", value=date.today())
                    priority = st.selectbox("Priority", PRIORITIES, index=1)

                if st.form_submit_button("Add task", type="primary", use_container_width=True):
                    if not title.strip():
                        st.error("Task title is required.")
                    else:
                        add_task(title, description, owner, planned_date, priority)
                        st.success("Task added.")
                        st.rerun()

    if not board_tasks:
        st.markdown('<div class="empty-state">No tasks for this profile yet.</div>', unsafe_allow_html=True)
        return

    columns = st.columns(4)

    for col, (status, meta) in zip(columns, STATUSES.items()):
        with col:
            st.markdown(
                f'<div class="kanban-title">{meta["icon"]} {meta["label"]} '
                f'<span class="small-muted">({len(ordered_tasks(status))})</span></div>',
                unsafe_allow_html=True,
            )
            with st.container(key=f"kanban_{status}", border=True):
                for task in ordered_tasks(status):
                    render_task_card(task)

    event = dnd(
        *[f"kanban_{status}" for status in STATUSES],
        handle="border",
        indicator="ghost",
        key="taskboard_dnd",
        placeholder={f"kanban_{status}": "Drop task here" for status in STATUSES},
    )

    if event:
        # event.item_key is the Streamlit key of the task card container.
        task_id = event.get("item_key", "").replace("task_card_", "")
        task = task_by_id(task_id)
        source_status = event.get("from_container", "").replace("kanban_", "")
        destination_status = event.get("to_container", "").replace("kanban_", "")

        if task and source_status in STATUSES and destination_status in STATUSES:
            task["status"] = destination_status
            task["completed_at"] = (
                date.today().isoformat() if destination_status == "done" else None
            )

            # Rebuild the visible order in the destination/source columns.
            # The DnD event indices refer to the currently visible profile list.
            for status in STATUSES:
                visible = ordered_tasks(status)
                if status == destination_status:
                    visible_ids = [t["id"] for t in visible if t["id"] != task_id]
                    target_index = max(0, min(int(event.get("to_index", len(visible_ids))), len(visible_ids)))
                    visible_ids.insert(target_index, task_id)
                    for idx, tid in enumerate(visible_ids):
                        t = task_by_id(tid)
                        if t:
                            t["position"] = idx
                elif status == source_status and source_status != destination_status:
                    for idx, t in enumerate(visible):
                        if t["id"] != task_id:
                            t["position"] = idx

            reindex_positions()
            save_data(data)
            ensure_notifications()
            st.rerun()

    if st.session_state.get("editing_task"):
        task = task_by_id(st.session_state.editing_task)
        if task and task_matches_profile(task):
            st.divider()
            st.markdown("### Edit task")
            edit_task_form(task)


# ============================================================
# DASHBOARD
# ============================================================


def dashboard():
    tasks = visible_tasks()
    pending = [t for t in tasks if t.get("status") != "done"]
    completed = [t for t in tasks if t.get("status") == "done"]
    overdue = [t for t in pending if is_overdue(t)]
    week_tasks = [t for t in tasks if is_this_week(t.get("planned_date"))]
    completed_month = [t for t in completed if is_this_month(t.get("completed_at"))]

    stats = [
        ("Total Tasks", len(tasks)),
        ("Pending", len(pending)),
        ("Completed", len(completed)),
        ("This Week", len(week_tasks)),
        ("Overdue", len(overdue)),
    ]

    cols = st.columns(5)
    for col, (label, value) in zip(cols, stats):
        with col:
            st.markdown(
                f'<div class="stat-card"><div class="stat-number">{value}</div>'
                f'<div class="stat-label">{label}</div></div>',
                unsafe_allow_html=True,
            )

    st.write("")
    monday = get_monday(date.today())
    sunday = get_sunday(date.today())
    st.subheader(f"This Week · {monday.strftime('%d %b')} - {sunday.strftime('%d %b %Y')}")

    if not week_tasks:
        st.info("No tasks planned for this week.")
    else:
        for task in sorted(week_tasks, key=lambda x: (x.get("planned_date") or "", x.get("position", 0))):
            owner = get_person_name(task.get("person_id"))
            icon = "✓" if task.get("status") == "done" else "○"
            status_text = STATUSES.get(task.get("status"), STATUSES["todo"])["label"]
            due = "OVERDUE" if is_overdue(task) else format_date(task.get("planned_date"))
            st.markdown(
                f"**{icon} {escape(task.get('title', 'Untitled task'))}**  \n"
                f"<span class='small-muted'>{escape(owner)} · {escape(status_text)} · {escape(due)}</span>",
                unsafe_allow_html=True,
            )

    st.subheader("Completion")
    if tasks:
        completion = len(completed) / len(tasks)
        st.progress(completion, text=f"{len(completed)} of {len(tasks)} tasks completed")
    else:
        st.progress(0, text="No tasks yet")

    st.subheader("People")
    if not data["people"]:
        st.info("No people added.")
        return

    cols = st.columns(min(4, len(data["people"])))
    for index, person in enumerate(data["people"]):
        person_tasks = [t for t in data["tasks"] if t.get("person_id") == person["id"]]
        with cols[index % len(cols)]:
            st.markdown(f"### {person['name']}")
            st.metric("Pending", sum(t.get("status") != "done" for t in person_tasks))
            st.metric("Completed this week", sum(
                t.get("status") == "done" and is_this_week(t.get("completed_at"))
                for t in person_tasks
            ))
            st.metric("Completed this month", sum(
                t.get("status") == "done" and is_this_month(t.get("completed_at"))
                for t in person_tasks
            ))


# ============================================================
# WEEKLY PLANNER
# ============================================================


def weekly_planner():
    monday = st.session_state.selected_week
    sunday = monday + timedelta(days=6)

    c1, c2, c3 = st.columns([1, 3, 1])
    with c1:
        if st.button("← Previous Week", use_container_width=True):
            st.session_state.selected_week = monday - timedelta(days=7)
            st.rerun()
    with c2:
        st.markdown(
            f"<h3 style='text-align:center'>{monday.strftime('%d %b')} - {sunday.strftime('%d %b %Y')}</h3>",
            unsafe_allow_html=True,
        )
    with c3:
        if st.button("Next Week →", use_container_width=True):
            st.session_state.selected_week = monday + timedelta(days=7)
            st.rerun()

    if st.button("Today"):
        st.session_state.selected_week = get_monday(date.today())
        st.rerun()

    st.divider()

    tasks = [
        t for t in visible_tasks()
        if monday.isoformat() <= (t.get("planned_date") or "9999-12-31") <= sunday.isoformat()
    ]

    cols = st.columns(7)
    for col, current_day in zip(cols, [monday + timedelta(days=i) for i in range(7)]):
        with col:
            is_today = current_day == date.today()
            st.markdown(f"### {current_day.strftime('%a')}" + (" · TODAY" if is_today else ""))
            st.caption(current_day.strftime("%d %b"))

            day_tasks = [
                t for t in tasks if t.get("planned_date") == current_day.isoformat()
            ]
            if not day_tasks:
                st.caption("No tasks")
            else:
                for task in day_tasks:
                    owner = get_person_name(task.get("person_id"))
                    status = STATUSES.get(task.get("status"), STATUSES["todo"])
                    st.markdown(
                        f"**{status['icon']} {escape(task['title'])}**  \n"
                        f"<span class='small-muted'>{escape(owner)} · {escape(status['label'])}</span>",
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "Done" if task.get("status") != "done" else "Undo",
                        key=f"planner_done_{task['id']}",
                        use_container_width=True,
                    ):
                        set_task_status(task, "done" if task.get("status") != "done" else "todo")
                        save_data(data)
                        st.rerun()

    st.divider()
    st.markdown("### Add task")
    if not data["people"]:
        st.info("Add a person first.")
        return

    with st.form("add_task_week"):
        c1, c2 = st.columns(2)
        with c1:
            title = st.text_input("Task title")
            description = st.text_area("Description")
            owner_options = [p["id"] for p in data["people"]]
            default_owner = (
                st.session_state.active_profile
                if st.session_state.active_profile != "all"
                else owner_options[0]
            )
            owner = st.selectbox(
                "Owner",
                owner_options,
                index=owner_options.index(default_owner),
                format_func=get_person_name,
            )
        with c2:
            planned_date = st.date_input("Planned date", value=max(monday, date.today()) if monday <= date.today() <= sunday else monday)
            priority = st.selectbox("Priority", PRIORITIES, index=1)
            status = st.selectbox(
                "Status",
                list(STATUSES),
                format_func=lambda x: STATUSES[x]["label"],
            )

        if st.form_submit_button("Add task", type="primary", use_container_width=True):
            if not title.strip():
                st.error("Task title is required.")
            else:
                add_task(title, description, owner, planned_date, priority, status)
                st.rerun()


# ============================================================
# PEOPLE
# ============================================================


def people_page():
    st.subheader("People")

    with st.form("add_person"):
        c1, c2 = st.columns([3, 1])
        with c1:
            name = st.text_input("Person name")
        with c2:
            submitted = st.form_submit_button("Add Person", use_container_width=True)

        if submitted:
            name = name.strip()
            if not name:
                st.error("Person name is required.")
            elif any(p["name"].lower() == name.lower() for p in data["people"]):
                st.error("That person already exists.")
            else:
                data["people"].append({"id": generate_id("person"), "name": name})
                save_data(data)
                st.rerun()

    st.divider()

    if not data["people"]:
        st.info("No people have been added.")
        return

    for person in data["people"]:
        person_tasks = [t for t in data["tasks"] if t.get("person_id") == person["id"]]
        pending = [t for t in person_tasks if t.get("status") != "done"]
        completed_week = [t for t in person_tasks if t.get("status") == "done" and is_this_week(t.get("completed_at"))]
        completed_month = [t for t in person_tasks if t.get("status") == "done" and is_this_month(t.get("completed_at"))]

        with st.expander(f"👤 {person['name']}", expanded=False):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Pending", len(pending))
            c2.metric("Completed this week", len(completed_week))
            c3.metric("Completed this month", len(completed_month))
            c4.metric("Total", len(person_tasks))

            if st.button("Use as active profile", key=f"profile_{person['id']}"):
                st.session_state.active_profile = person["id"]
                st.session_state.page = "Board"
                st.rerun()

            st.markdown("#### Current work")
            if pending:
                for task in pending:
                    st.markdown(
                        f"○ **{escape(task['title'])}** · {format_date(task.get('planned_date'))}",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("Nothing pending.")

            st.markdown("#### Completed this week")
            if completed_week:
                for task in completed_week:
                    st.markdown(f"✓ ~~{escape(task['title'])}~~", unsafe_allow_html=True)
            else:
                st.caption("No completed tasks this week.")

            if st.button("Delete person", key=f"delete_person_{person['id']}"):
                if person_tasks:
                    st.error("Cannot delete a person who still owns tasks. Reassign or delete those tasks first.")
                else:
                    data["people"] = [p for p in data["people"] if p["id"] != person["id"]]
                    if st.session_state.active_profile == person["id"]:
                        st.session_state.active_profile = "all"
                    save_data(data)
                    st.rerun()


# ============================================================
# ALL TASKS
# ============================================================


def all_tasks_page():
    st.subheader("All Tasks")

    tasks = visible_tasks()
    if not tasks:
        st.info("No tasks for the active profile.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        status_filter = st.selectbox(
            "Status",
            ["All"] + [meta["label"] for meta in STATUSES.values()],
        )
    with c2:
        priority_filter = st.selectbox("Priority", ["All", *PRIORITIES])
    with c3:
        search = st.text_input("Search", placeholder="Task title or description")

    status_lookup = {meta["label"]: status for status, meta in STATUSES.items()}
    filtered = tasks

    if status_filter != "All":
        filtered = [t for t in filtered if t.get("status") == status_lookup[status_filter]]
    if priority_filter != "All":
        filtered = [t for t in filtered if t.get("priority") == priority_filter]
    if search.strip():
        q = search.lower().strip()
        filtered = [
            t for t in filtered
            if q in t.get("title", "").lower() or q in t.get("description", "").lower()
        ]

    st.caption(f"{len(filtered)} task(s) shown for {('all people' if st.session_state.active_profile == 'all' else get_person_name(st.session_state.active_profile))}")

    for task in sorted(filtered, key=lambda x: (x.get("planned_date") or "9999-12-31", x.get("position", 0))):
        status = STATUSES.get(task.get("status"), STATUSES["todo"])
        with st.container(border=True):
            c1, c2, c3 = st.columns([5, 2, 1])
            with c1:
                st.markdown(f"### {status['icon']} {escape(task['title'])}", unsafe_allow_html=True)
                st.caption(
                    f"{get_person_name(task.get('person_id'))} · "
                    f"{format_date(task.get('planned_date'))} · "
                    f"{task.get('priority', 'medium').upper()}"
                )
                if task.get("description"):
                    st.write(task["description"])
            with c2:
                st.write(f"**Status:** {status['label']}")
                st.write(f"**Completed:** {format_date(task.get('completed_at'))}")
            with c3:
                if task.get("status") == "done":
                    if st.button("Undo", key=f"all_undo_{task['id']}", use_container_width=True):
                        set_task_status(task, "todo")
                        save_data(data)
                        st.rerun()
                else:
                    if st.button("Done", key=f"all_done_{task['id']}", use_container_width=True):
                        set_task_status(task, "done")
                        save_data(data)
                        st.rerun()

                if st.button("Edit", key=f"all_edit_{task['id']}", use_container_width=True):
                    st.session_state.editing_task = task["id"]
                    st.session_state.page = "Board"
                    st.rerun()

                if st.button("Delete", key=f"all_delete_{task['id']}", use_container_width=True):
                    st.session_state.delete_task_id = task["id"]
                    st.rerun()


# ============================================================
# ROUTER
# ============================================================

if st.session_state.page == "Board":
    kanban_board()
elif st.session_state.page == "Dashboard":
    dashboard()
elif st.session_state.page == "Weekly Planner":
    weekly_planner()
elif st.session_state.page == "People":
    people_page()
elif st.session_state.page == "All Tasks":
    all_tasks_page()

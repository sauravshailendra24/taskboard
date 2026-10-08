import streamlit as st
import json
import os
import uuid
from datetime import date, datetime, timedelta

DATA_FILE = "task.json"
st.set_page_config(page_title="Taskboard",page_icon="📋",layout="wide")

def load_data():
    if not os.path.exists(DATA_FILE):
        data = {
            "people": [],
            "tasks": []
        }
        save_data(data)
        return data
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "people" not in data:
            data["people"] = []
        if "tasks" not in data:
            data["tasks"] = []
        return data
    except Exception:
        return {
            "people": [],
            "tasks": []
        }

def save_data(data):
    """Save data to JSON."""

    temp_file = DATA_FILE + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )

    os.replace(temp_file, DATA_FILE)


def generate_id(prefix="id"):
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


# ============================================================
# DATE FUNCTIONS
# ============================================================

def get_monday(d):
    """Return Monday for a given date."""

    return d - timedelta(days=d.weekday())


def get_sunday(d):
    """Return Sunday for a given date."""

    return get_monday(d) + timedelta(days=6)


def is_this_week(date_string, reference_date=None):
    if not date_string:
        return False

    reference_date = reference_date or date.today()

    try:
        d = datetime.strptime(date_string, "%Y-%m-%d").date()
    except ValueError:
        return False

    monday = get_monday(reference_date)
    sunday = get_sunday(reference_date)

    return monday <= d <= sunday


def is_this_month(date_string, reference_date=None):
    if not date_string:
        return False

    reference_date = reference_date or date.today()

    try:
        d = datetime.strptime(date_string, "%Y-%m-%d").date()
    except ValueError:
        return False

    return (
        d.year == reference_date.year
        and d.month == reference_date.month
    )


def format_date(date_string):
    if not date_string:
        return "-"

    try:
        d = datetime.strptime(
            date_string,
            "%Y-%m-%d"
        ).date()

        return d.strftime("%d %b %Y")

    except ValueError:
        return date_string


def is_overdue(task):
    if task.get("status") == "completed":
        return False

    planned_date = task.get("planned_date")

    if not planned_date:
        return False

    try:
        d = datetime.strptime(
            planned_date,
            "%Y-%m-%d"
        ).date()

        return d < date.today()

    except ValueError:
        return False


# ============================================================
# TASK HELPERS
# ============================================================

def get_person_name(data, person_id):

    for person in data["people"]:
        if person["id"] == person_id:
            return person["name"]

    return "Unknown"


def get_person_tasks(data, person_id):

    return [
        task
        for task in data["tasks"]
        if task.get("person_id") == person_id
    ]


def pending_tasks(data):

    return [
        task
        for task in data["tasks"]
        if task.get("status") != "completed"
    ]


def completed_tasks(data):

    return [
        task
        for task in data["tasks"]
        if task.get("status") == "completed"
    ]


# ============================================================
# SESSION STATE
# ============================================================

if "selected_week" not in st.session_state:
    st.session_state.selected_week = get_monday(date.today())

if "selected_person" not in st.session_state:
    st.session_state.selected_person = "all"

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"


# ============================================================
# LOAD DATA
# ============================================================

data = load_data()


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 32px;
        font-weight: 700;
        margin-bottom: 4px;
    }

    .subtitle {
        color: #777;
        margin-bottom: 25px;
    }

    .stat-card {
        padding: 18px;
        border: 1px solid #e5e5e5;
        border-radius: 12px;
        background: white;
        min-height: 110px;
    }

    .stat-number {
        font-size: 30px;
        font-weight: 700;
    }

    .stat-label {
        color: #777;
        font-size: 14px;
    }

    .task-card {
        border: 1px solid #e5e5e5;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 8px;
        background: white;
    }

    .task-title {
        font-weight: 600;
        font-size: 15px;
    }

    .task-meta {
        font-size: 12px;
        color: #777;
    }

    .priority-high {
        color: #d32f2f;
        font-weight: 600;
    }

    .priority-medium {
        color: #f57c00;
        font-weight: 600;
    }

    .priority-low {
        color: #388e3c;
        font-weight: 600;
    }

    .overdue {
        color: #d32f2f;
        font-weight: 600;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("## 📋 Taskboard")

    st.divider()

    pages = [
        "Dashboard",
        "Weekly Planner",
        "People",
        "All Tasks"
    ]

    for page in pages:

        if st.button(
            page,
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.page == page
                else "secondary"
            )
        ):
            st.session_state.page = page
            st.rerun()

    st.divider()

    st.markdown("### Team")

    if data["people"]:

        person_options = {
            "All People": "all"
        }

        for person in data["people"]:
            person_options[
                person["name"]
            ] = person["id"]

        selected_name = st.selectbox(
            "View person",
            list(person_options.keys())
        )

        st.session_state.selected_person = (
            person_options[selected_name]
        )

    else:

        st.info("Add your first person from People.")


# ============================================================
# COMMON HEADER
# ============================================================

st.markdown(
    '<div class="main-title">📋 Taskboard</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">Plan the work. Track what is left. '
    'See what actually got done.</div>',
    unsafe_allow_html=True
)


# ============================================================
# DASHBOARD
# ============================================================

def dashboard():

    today = date.today()

    all_tasks = data["tasks"]

    pending = [
        t for t in all_tasks
        if t.get("status") != "completed"
    ]

    completed = [
        t for t in all_tasks
        if t.get("status") == "completed"
    ]

    overdue = [
        t for t in pending
        if is_overdue(t)
    ]

    week_tasks = [
        t for t in all_tasks
        if is_this_week(t.get("planned_date"))
    ]

    month_tasks = [
        t for t in completed
        if is_this_month(t.get("completed_at"))
    ]

    # --------------------------------------------------------
    # STATS
    # --------------------------------------------------------

    cols = st.columns(5)

    stats = [
        ("Total Tasks", len(all_tasks)),
        ("Pending", len(pending)),
        ("Completed", len(completed)),
        ("This Week", len(week_tasks)),
        ("Overdue", len(overdue))
    ]

    for col, (label, value) in zip(cols, stats):

        with col:

            st.markdown(
                f"""
                <div class="stat-card">
                    <div class="stat-number">{value}</div>
                    <div class="stat-label">{label}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.write("")

    # --------------------------------------------------------
    # WEEK
    # --------------------------------------------------------

    monday = get_monday(today)
    sunday = get_sunday(today)

    st.subheader(
        f"This Week · {monday.strftime('%d %b')} - "
        f"{sunday.strftime('%d %b %Y')}"
    )

    if not week_tasks:

        st.info("No tasks planned for this week.")

    else:

        for task in sorted(
            week_tasks,
            key=lambda x: x.get("planned_date", "")
        ):

            person_name = get_person_name(
                data,
                task["person_id"]
            )

            status = task.get("status")

            if status == "completed":
                icon = "✅"
            else:
                icon = "⬜"

            priority = task.get(
                "priority",
                "medium"
            )

            st.markdown(
                f"""
                <div class="task-card">

                    <div class="task-title">
                        {icon} {task["title"]}
                    </div>

                    <div class="task-meta">
                        {person_name}
                        · {format_date(task.get("planned_date"))}
                        · <span class="priority-{priority}">
                          {priority.upper()}
                          </span>
                    </div>

                </div>
                """,
                unsafe_allow_html=True
            )

    # --------------------------------------------------------
    # PEOPLE SUMMARY
    # --------------------------------------------------------

    st.subheader("Team Overview")

    if not data["people"]:

        st.info("No people added yet.")

    else:

        cols = st.columns(
            min(len(data["people"]), 3)
        )

        for index, person in enumerate(data["people"]):

            person_tasks = get_person_tasks(
                data,
                person["id"]
            )

            person_pending = [
                t for t in person_tasks
                if t.get("status") != "completed"
            ]

            person_completed_week = [
                t for t in person_tasks
                if (
                    t.get("status") == "completed"
                    and is_this_week(
                        t.get("completed_at")
                    )
                )
            ]

            person_completed_month = [
                t for t in person_tasks
                if (
                    t.get("status") == "completed"
                    and is_this_month(
                        t.get("completed_at")
                    )
                )
            ]

            with cols[index % len(cols)]:

                st.markdown(
                    f"### {person['name']}"
                )

                st.metric(
                    "Pending",
                    len(person_pending)
                )

                c1, c2 = st.columns(2)

                with c1:
                    st.metric(
                        "This Week",
                        len(person_completed_week)
                    )

                with c2:
                    st.metric(
                        "This Month",
                        len(person_completed_month)
                    )


# ============================================================
# WEEKLY PLANNER
# ============================================================

def weekly_planner():

    st.subheader("Weekly Planner")

    # --------------------------------------------------------
    # WEEK NAVIGATION
    # --------------------------------------------------------

    monday = st.session_state.selected_week
    sunday = monday + timedelta(days=6)

    c1, c2, c3 = st.columns([1, 3, 1])

    with c1:

        if st.button("← Previous Week"):

            st.session_state.selected_week = (
                monday - timedelta(days=7)
            )

            st.rerun()

    with c2:

        st.markdown(
            f"<h3 style='text-align:center'>"
            f"{monday.strftime('%d %b')} - "
            f"{sunday.strftime('%d %b %Y')}"
            f"</h3>",
            unsafe_allow_html=True
        )

    with c3:

        if st.button("Next Week →"):

            st.session_state.selected_week = (
                monday + timedelta(days=7)
            )

            st.rerun()

    if st.button("Today"):

        st.session_state.selected_week = (
            get_monday(date.today())
        )

        st.rerun()

    st.divider()

    # --------------------------------------------------------
    # ADD TASK
    # --------------------------------------------------------

    if not data["people"]:

        st.warning(
            "Add people first from the People section."
        )

    else:

        with st.expander(
            "➕ Add Task to This Week",
            expanded=True
        ):

            with st.form("add_week_task"):

                c1, c2 = st.columns(2)

                with c1:

                    person_id = st.selectbox(
                        "Person",
                        options=[
                            p["id"]
                            for p in data["people"]
                        ],
                        format_func=lambda x:
                            get_person_name(data, x)
                    )

                    title = st.text_input(
                        "Task"
                    )

                    description = st.text_area(
                        "Description"
                    )

                with c2:

                    planned_date = st.date_input(
                        "Planned Date",
                        value=monday
                    )

                    priority = st.selectbox(
                        "Priority",
                        [
                            "high",
                            "medium",
                            "low"
                        ],
                        index=1
                    )

                submitted = st.form_submit_button(
                    "Add Task",
                    use_container_width=True
                )

                if submitted:

                    if not title.strip():

                        st.error(
                            "Task title is required."
                        )

                    else:

                        new_task = {
                            "id": generate_id("task"),
                            "person_id": person_id,
                            "title": title.strip(),
                            "description": description.strip(),
                            "status": "pending",
                            "priority": priority,
                            "planned_date": planned_date.isoformat(),
                            "completed_at": None,
                            "created_at": date.today().isoformat()
                        }

                        data["tasks"].append(
                            new_task
                        )

                        save_data(data)

                        st.success(
                            "Task added."
                        )

                        st.rerun()

    st.divider()

    # --------------------------------------------------------
    # WEEK COLUMNS
    # --------------------------------------------------------

    days = [
        monday + timedelta(days=i)
        for i in range(7)
    ]

    columns = st.columns(7)

    for col, current_day in zip(columns, days):

        with col:

            is_today = (
                current_day == date.today()
            )

            label = current_day.strftime("%a")

            if is_today:
                label += " · TODAY"

            st.markdown(
                f"### {label}"
            )

            st.caption(
                current_day.strftime("%d %b")
            )

            day_tasks = [
                task
                for task in data["tasks"]
                if task.get("planned_date")
                == current_day.isoformat()
            ]

            if not day_tasks:

                st.caption("No tasks")

            for task in day_tasks:

                person_name = get_person_name(
                    data,
                    task["person_id"]
                )

                completed = (
                    task.get("status")
                    == "completed"
                )

                if completed:
                    icon = "✅"
                else:
                    icon = "⬜"

                st.markdown(
                    f"""
                    <div class="task-card">
                        <div>
                            {icon} <b>{task["title"]}</b>
                        </div>
                        <div class="task-meta">
                            {person_name}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                button_label = (
                    "↩ Undo"
                    if completed
                    else "✓ Done"
                )

                if st.button(
                    button_label,
                    key=f"done_{task['id']}",
                    use_container_width=True
                ):

                    if completed:

                        task["status"] = "pending"
                        task["completed_at"] = None

                    else:

                        task["status"] = "completed"
                        task["completed_at"] = (
                            date.today().isoformat()
                        )

                    save_data(data)

                    st.rerun()


# ============================================================
# PEOPLE
# ============================================================

def people_page():

    st.subheader("People")

    # --------------------------------------------------------
    # ADD PERSON
    # --------------------------------------------------------

    with st.form("add_person"):

        c1, c2 = st.columns([3, 1])

        with c1:

            name = st.text_input(
                "Person name"
            )

        with c2:

            submitted = st.form_submit_button(
                "Add Person",
                use_container_width=True
            )

        if submitted:

            name = name.strip()

            if not name:

                st.error(
                    "Person name is required."
                )

            elif any(
                p["name"].lower() == name.lower()
                for p in data["people"]
            ):

                st.error(
                    "That person already exists."
                )

            else:

                data["people"].append(
                    {
                        "id": generate_id("person"),
                        "name": name
                    }
                )

                save_data(data)

                st.success(
                    f"{name} added."
                )

                st.rerun()

    st.divider()

    # --------------------------------------------------------
    # PEOPLE LIST
    # --------------------------------------------------------

    if not data["people"]:

        st.info(
            "No people have been added."
        )

        return

    for person in data["people"]:

        person_tasks = get_person_tasks(
            data,
            person["id"]
        )

        pending = [
            t for t in person_tasks
            if t.get("status") != "completed"
        ]

        completed_week = [
            t for t in person_tasks
            if (
                t.get("status") == "completed"
                and is_this_week(
                    t.get("completed_at")
                )
            )
        ]

        completed_month = [
            t for t in person_tasks
            if (
                t.get("status") == "completed"
                and is_this_month(
                    t.get("completed_at")
                )
            )
        ]

        with st.expander(
            f"👤 {person['name']}",
            expanded=True
        ):

            c1, c2, c3, c4 = st.columns(4)

            with c1:
                st.metric(
                    "Pending",
                    len(pending)
                )

            with c2:
                st.metric(
                    "This Week",
                    len(completed_week)
                )

            with c3:
                st.metric(
                    "This Month",
                    len(completed_month)
                )

            with c4:
                st.metric(
                    "Total",
                    len(person_tasks)
                )

            st.write("")

            # ------------------------------------------------
            # PENDING
            # ------------------------------------------------

            st.markdown("#### Left")

            if not pending:

                st.caption(
                    "Nothing pending."
                )

            else:

                for task in pending:

                    overdue = is_overdue(task)

                    col1, col2 = st.columns(
                        [6, 1]
                    )

                    with col1:

                        st.markdown(
                            f"⬜ **{task['title']}**"
                        )

                        meta = (
                            f"{format_date(task.get('planned_date'))}"
                            f" · {task.get('priority', 'medium')}"
                        )

                        if overdue:

                            meta += " · OVERDUE"

                        st.caption(meta)

                    with col2:

                        if st.button(
                            "Done",
                            key=f"person_done_{task['id']}"
                        ):

                            task["status"] = "completed"
                            task["completed_at"] = (
                                date.today().isoformat()
                            )

                            save_data(data)

                            st.rerun()

            # ------------------------------------------------
            # THIS WEEK
            # ------------------------------------------------

            st.markdown("#### Completed This Week")

            if not completed_week:

                st.caption(
                    "No completed tasks this week."
                )

            else:

                for task in completed_week:

                    st.markdown(
                        f"✅ ~~{task['title']}~~"
                    )

            # ------------------------------------------------
            # THIS MONTH
            # ------------------------------------------------

            st.markdown("#### Completed This Month")

            if not completed_month:

                st.caption(
                    "No completed tasks this month."
                )

            else:

                for task in completed_month:

                    st.markdown(
                        f"✓ {task['title']} "
                        f"({format_date(task.get('completed_at'))})"
                    )


# ============================================================
# ALL TASKS
# ============================================================

def all_tasks_page():

    st.subheader("All Tasks")

    if not data["tasks"]:

        st.info(
            "No tasks yet."
        )

        return

    # --------------------------------------------------------
    # FILTERS
    # --------------------------------------------------------

    c1, c2, c3 = st.columns(3)

    with c1:

        person_filter = st.selectbox(
            "Person",
            ["All"] + [
                p["name"]
                for p in data["people"]
            ]
        )

    with c2:

        status_filter = st.selectbox(
            "Status",
            [
                "All",
                "Pending",
                "Completed",
                "Overdue"
            ]
        )

    with c3:

        priority_filter = st.selectbox(
            "Priority",
            [
                "All",
                "high",
                "medium",
                "low"
            ]
        )

    # --------------------------------------------------------
    # FILTER TASKS
    # --------------------------------------------------------

    filtered = data["tasks"]

    if person_filter != "All":

        person_id = next(
            (
                p["id"]
                for p in data["people"]
                if p["name"] == person_filter
            ),
            None
        )

        filtered = [
            t for t in filtered
            if t.get("person_id") == person_id
        ]

    if status_filter == "Pending":

        filtered = [
            t for t in filtered
            if t.get("status") != "completed"
        ]

    elif status_filter == "Completed":

        filtered = [
            t for t in filtered
            if t.get("status") == "completed"
        ]

    elif status_filter == "Overdue":

        filtered = [
            t for t in filtered
            if is_overdue(t)
        ]

    if priority_filter != "All":

        filtered = [
            t for t in filtered
            if t.get("priority") == priority_filter
        ]

    st.divider()

    # --------------------------------------------------------
    # TASK LIST
    # --------------------------------------------------------

    for task in sorted(
        filtered,
        key=lambda x: (
            x.get("planned_date") or "",
            x.get("status") or ""
        )
    ):

        person_name = get_person_name(
            data,
            task["person_id"]
        )

        completed = (
            task.get("status") == "completed"
        )

        icon = "✅" if completed else "⬜"

        with st.expander(
            f"{icon} {task['title']}"
        ):

            c1, c2 = st.columns(2)

            with c1:

                st.write(
                    f"**Person:** {person_name}"
                )

                st.write(
                    f"**Status:** "
                    f"{task.get('status', 'pending')}"
                )

                st.write(
                    f"**Priority:** "
                    f"{task.get('priority', 'medium')}"
                )

            with c2:

                st.write(
                    f"**Planned:** "
                    f"{format_date(task.get('planned_date'))}"
                )

                st.write(
                    f"**Completed:** "
                    f"{format_date(task.get('completed_at'))}"
                )

            if task.get("description"):

                st.write(
                    "**Description**"
                )

                st.write(
                    task["description"]
                )

            st.divider()

            c1, c2, c3 = st.columns(3)

            # ------------------------------------------------
            # COMPLETE / UNCOMPLETE
            # ------------------------------------------------

            with c1:

                if completed:

                    if st.button(
                        "↩ Mark Pending",
                        key=f"pending_{task['id']}"
                    ):

                        task["status"] = "pending"
                        task["completed_at"] = None

                        save_data(data)

                        st.rerun()

                else:

                    if st.button(
                        "✓ Mark Complete",
                        key=f"complete_{task['id']}"
                    ):

                        task["status"] = "completed"
                        task["completed_at"] = (
                            date.today().isoformat()
                        )

                        save_data(data)

                        st.rerun()

            # ------------------------------------------------
            # DELETE
            # ------------------------------------------------

            with c3:

                if st.button(
                    "🗑 Delete",
                    key=f"delete_{task['id']}"
                ):

                    data["tasks"] = [
                        t for t in data["tasks"]
                        if t["id"] != task["id"]
                    ]

                    save_data(data)

                    st.rerun()


# ============================================================
# ROUTER
# ============================================================

if st.session_state.page == "Dashboard":

    dashboard()

elif st.session_state.page == "Weekly Planner":

    weekly_planner()

elif st.session_state.page == "People":

    people_page()

elif st.session_state.page == "All Tasks":

    all_tasks_page()
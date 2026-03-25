"""
DPMS — Streamlit UI
====================
Login → role-based chat assistant.

Pages:
  • Not logged in  → Login form
  • Logged in      → Chat interface (role derived from JWT, not user input)

Run:
    streamlit run app/ui/streamlit_app.py
"""

from pathlib import Path
import sys

import requests
import streamlit as st

# ── Path setup ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.conversations.service import fetch_conversation

# ── Config ────────────────────────────────────────────────────────────────────
BACKEND   = "http://127.0.0.1:8000"
LOGIN_URL = f"{BACKEND}/auth/login"
CHAT_URL  = f"{BACKEND}/agents/chat"

# Role colours & icons
ROLE_META = {
    "ADMIN":        {"icon": "🛡️",  "color": "#c0392b", "label": "Admin"},
    "RECEPTIONIST": {"icon": "🗂️",  "color": "#2980b9", "label": "Receptionist"},
    "DOCTOR":       {"icon": "👨‍⚕️", "color": "#27ae60", "label": "Doctor"},
    "PATIENT":      {"icon": "🧑",  "color": "#8e44ad", "label": "Patient"},
}

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DPMS Assistant",
    page_icon="🏥",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Hide the default Streamlit header */
#MainMenu {visibility: hidden;}
header      {visibility: hidden;}
footer      {visibility: hidden;}

/* Login card */
.login-card {
    background: #ffffff;
    border-radius: 12px;
    padding: 2.5rem 2rem;
    box-shadow: 0 4px 24px rgba(0,0,0,0.10);
    max-width: 420px;
    margin: 4rem auto 0;
}
.login-title {
    font-size: 1.7rem;
    font-weight: 700;
    color: #1a1a2e;
    text-align: center;
    margin-bottom: 0.2rem;
}
.login-sub {
    font-size: 0.9rem;
    color: #888;
    text-align: center;
    margin-bottom: 1.5rem;
}
/* Role badge in sidebar */
.role-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    color: white;
    font-size: 0.78rem;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)


# ── Session-state defaults ────────────────────────────────────────────────────
def _init():
    defaults = {
        "token":              None,
        "role":               None,
        "username":           None,
        "display_name":       None,
        "user_id":            None,
        "messages":           [],
        "session_id":         "session-1",
        "loaded_session_id":  None,
        "login_error":        "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN PAGE
# ─────────────────────────────────────────────────────────────────────────────

def show_login():
    st.markdown("""
    <div class="login-card">
        <div class="login-title">🏥 DPMS Assistant</div>
        <div class="login-sub">Doctor-Patient Management System</div>
    </div>
    """, unsafe_allow_html=True)

    # Centre the form
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("#### Sign In")

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="e.g. admin")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Login", use_container_width=True, type="primary")

        if submitted:
            if not username or not password:
                st.error("Please enter both username and password.")
            else:
                _do_login(username, password)

        if st.session_state.login_error:
            st.error(st.session_state.login_error)

        st.markdown("---")
        st.markdown(
            "<small>Demo credentials — Admin: `admin / Admin@123` &nbsp;|&nbsp; "
            "Patient: `patient_amit / Patient@123`</small>",
            unsafe_allow_html=True,
        )


def _do_login(username: str, password: str):
    try:
        resp = requests.post(LOGIN_URL, json={"username": username, "password": password}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            st.session_state.token        = data["access_token"]
            st.session_state.role         = data["role"]
            st.session_state.username     = data["username"]
            st.session_state.display_name = data["display_name"]
            st.session_state.user_id      = data["user_id"]
            st.session_state.session_id   = f"session-{data['user_id'][:8]}"
            st.session_state.messages     = []
            st.session_state.login_error  = ""
            st.rerun()
        elif resp.status_code == 401:
            st.session_state.login_error = "Invalid username or password. Please try again."
            st.rerun()
        else:
            st.session_state.login_error = f"Login failed (HTTP {resp.status_code}). Is the backend running?"
            st.rerun()
    except requests.exceptions.ConnectionError:
        st.session_state.login_error = "⚠️ Cannot connect to backend at http://127.0.0.1:8000. Please start the server first."
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR (when logged in)
# ─────────────────────────────────────────────────────────────────────────────

def show_sidebar():
    role = st.session_state.role
    meta = ROLE_META.get(role, {"icon": "👤", "color": "#555", "label": role})

    with st.sidebar:
        st.markdown(f"## {meta['icon']} {st.session_state.display_name}")
        st.markdown(
            f"<span class='role-badge' style='background:{meta['color']}'>"
            f"{meta['label']}</span>",
            unsafe_allow_html=True,
        )
        st.markdown(f"<small>@{st.session_state.username}</small>", unsafe_allow_html=True)
        st.divider()

        # Session management
        st.markdown("**Chat Session**")
        new_session = st.text_input(
            "Session ID",
            value=st.session_state.session_id,
            help="Change to start a fresh conversation or resume a previous one.",
        )
        if new_session != st.session_state.session_id:
            st.session_state.session_id      = new_session
            st.session_state.loaded_session_id = None
            st.session_state.messages        = []
            st.rerun()

        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages        = []
            st.session_state.loaded_session_id = None
            st.rerun()

        st.divider()

        # Role-specific quick hints
        st.markdown("**Quick actions you can ask:**")
        hints = _role_hints(role)
        for hint in hints:
            st.markdown(f"- _{hint}_")

        st.divider()

        if st.button("🚪 Logout", use_container_width=True):
            for k in ["token","role","username","display_name","user_id",
                      "messages","session_id","loaded_session_id","login_error"]:
                st.session_state[k] = None if k != "messages" else []
            st.session_state.login_error = ""
            st.rerun()


def _role_hints(role: str) -> list:
    return {
        "ADMIN": [
            "List all doctors",
            "Show today's appointments",
            "Who has the most bookings this week?",
            "Add a new doctor",
            "Show all patients with high risk score",
        ],
        "RECEPTIONIST": [
            "Book an appointment for Amit with Dr. Arun tomorrow morning",
            "Cancel appointment <ID>",
            "What slots does Dr. Priya have on Friday?",
            "Add Rahul to the waitlist for Dr. Ravi's morning session",
            "Show today's schedule",
        ],
        "DOCTOR": [
            "Show my appointments today",
            "Who are my upcoming patients this week?",
            "Show all confirmed appointments",
        ],
        "PATIENT": [
            "Book me an appointment with Dr. Arun tomorrow",
            "Show my upcoming appointments",
            "Cancel my appointment",
            "What slots are available for Dr. Priya on Monday?",
            "Add me to the waitlist",
        ],
    }.get(role, ["Ask me anything about the clinic."])


# ─────────────────────────────────────────────────────────────────────────────
# CHAT PAGE
# ─────────────────────────────────────────────────────────────────────────────

def show_chat():
    show_sidebar()

    role = st.session_state.role
    meta = ROLE_META.get(role, {"icon": "💬", "color": "#555", "label": role})

    st.markdown(f"### {meta['icon']} DPMS Chat Assistant")
    st.caption(f"Logged in as **{st.session_state.display_name}** · Role: **{meta['label']}**")
    st.divider()

    # Load conversation history from MongoDB when session_id changes
    session_id = st.session_state.session_id
    if st.session_state.loaded_session_id != session_id:
        try:
            conversation = fetch_conversation(session_id)
            if conversation:
                st.session_state.messages = [
                    {
                        "role":    "user" if m.get("sender") == "user" else "assistant",
                        "content": m.get("content", ""),
                    }
                    for m in conversation.get("messages", [])
                ]
            else:
                st.session_state.messages = []
        except Exception:
            st.session_state.messages = []
        st.session_state.loaded_session_id = session_id

    # Render existing messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Welcome message for fresh sessions
    if not st.session_state.messages:
        with st.chat_message("assistant"):
            st.markdown(
                f"Hello **{st.session_state.display_name}**! 👋 I'm your DPMS assistant. "
                f"How can I help you today?"
            )

    # Chat input
    user_message = st.chat_input("Type your message…")
    if user_message:
        # Show user bubble immediately
        st.session_state.messages.append({"role": "user", "content": user_message})
        with st.chat_message("user"):
            st.markdown(user_message)

        # Call backend
        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                reply = _call_agent(user_message)
            st.markdown(reply)

        st.session_state.messages.append({"role": "assistant", "content": reply})


def _call_agent(message: str) -> str:
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    payload = {
        "role":       st.session_state.role,
        "user_id":    st.session_state.user_id or "unknown",
        "message":    message,
        "session_id": st.session_state.session_id,
    }
    try:
        resp = requests.post(CHAT_URL, json=payload, headers=headers, timeout=90)
        resp.raise_for_status()
        return resp.json().get("message", "No response from agent.")
    except requests.exceptions.ConnectionError:
        return "⚠️ Backend is not reachable. Please make sure the FastAPI server is running."
    except requests.exceptions.Timeout:
        return "⏱️ Request timed out. The agent is taking too long — please try again."
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            st.session_state.token = None   # force re-login
            st.rerun()
        return f"Error from server: {e}"
    except Exception as e:
        return f"Unexpected error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY
# ─────────────────────────────────────────────────────────────────────────────

if st.session_state.token:
    show_chat()
else:
    show_login()

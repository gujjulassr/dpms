"""
DPMS — Streamlit UI
====================
Two login paths:
  • Staff / Doctors  → Username + Password
  • Patients         → Sign in with Google (OAuth)

Run:
    streamlit run app/ui/streamlit_app.py
"""
from __future__ import annotations

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
BACKEND          = "http://127.0.0.1:8000"
LOGIN_URL        = f"{BACKEND}/auth/login"
CHAT_URL         = f"{BACKEND}/agents/chat"
GOOGLE_LOGIN_URL = f"{BACKEND}/auth/google/login"

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

st.markdown("""
<style>
#MainMenu {visibility: hidden;}
header      {visibility: hidden;}
footer      {visibility: hidden;}

.login-title {
    font-size: 1.8rem;
    font-weight: 700;
    color: #1a1a2e;
    text-align: center;
    margin-bottom: 0.25rem;
}
.login-sub {
    font-size: 0.9rem;
    color: #888;
    text-align: center;
    margin-bottom: 1.5rem;
}
.divider-text {
    text-align: center;
    color: #aaa;
    font-size: 0.8rem;
    margin: 0.6rem 0;
}
.google-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    background: #ffffff;
    border: 1.5px solid #dadce0;
    border-radius: 6px;
    padding: 10px 16px;
    font-size: 0.95rem;
    font-weight: 500;
    color: #3c4043;
    text-decoration: none;
    transition: background 0.15s;
    width: 100%;
    box-sizing: border-box;
}
.google-btn:hover { background: #f8f9fa; }
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
        "token":             None,
        "role":              None,
        "username":          None,
        "display_name":      None,
        "user_id":           None,
        "patient_id":        None,
        "messages":          [],
        "session_id":        "session-1",
        "loaded_session_id": None,
        "login_error":       "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()

REGISTER_URL = f"{BACKEND}/auth/google/register"


# ── Pick up params from Google OAuth redirect ─────────────────────────────────
def _consume_google_redirect():
    """
    Google OAuth callback redirects back to Streamlit with one of:
      A) ?token=JWT                          → returning patient, log straight in
      B) ?needs_registration=true&reg_token=…&name=…&email=…
                                             → new patient, show registration form
    """
    params = st.query_params
    if not params or st.session_state.token:
        return

    # ── Case A: returning patient ─────────────────────────────────────────────
    token = params.get("token")
    if token:
        try:
            from app.modules.auth.service import decode_token
            payload = decode_token(token)
            if not payload:
                st.session_state.login_error = "Google login failed — invalid token."
                st.query_params.clear()
                st.rerun()
                return
            _set_logged_in(token, payload)
        except Exception as e:
            st.session_state.login_error = f"Google login error: {e}"
        st.query_params.clear()
        st.rerun()
        return

    # ── Case B: new patient needs to register ────────────────────────────────
    if params.get("needs_registration") == "true":
        st.session_state["reg_token"] = params.get("reg_token", "")
        st.session_state["reg_name"]  = params.get("name", "")
        st.session_state["reg_email"] = params.get("email", "")
        st.query_params.clear()
        st.rerun()


def _set_logged_in(token: str, payload: dict):
    st.session_state.token        = token
    st.session_state.role         = payload.get("role", "PATIENT")
    st.session_state.username     = payload.get("username", "")
    st.session_state.display_name = payload.get("display_name", "")
    st.session_state.user_id      = payload.get("user_id", "")
    st.session_state.patient_id   = payload.get("patient_id")
    st.session_state.session_id   = f"session-{str(payload.get('user_id','g'))[:8]}"
    st.session_state.messages     = []
    st.session_state.login_error  = ""


_consume_google_redirect()


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRATION FORM  (new patients only — shown after first Google login)
# ─────────────────────────────────────────────────────────────────────────────

def show_registration_form():
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("### 🏥 Complete Your Registration")
        st.markdown(
            f"Welcome! You signed in as **{st.session_state.get('reg_name', '')}** "
            f"(`{st.session_state.get('reg_email', '')}`). "
            "Please fill in the details below to finish creating your patient account."
        )
        st.divider()

        with st.form("registration_form"):
            # Name pre-filled from Google but editable
            full_name = st.text_input(
                "Full Name *",
                value=st.session_state.get("reg_name", ""),
            )
            phone = st.text_input(
                "Phone Number *",
                placeholder="e.g. 9876543210",
                help="Up to 15 digits. This will be used to contact you about appointments.",
            )
            dob = st.date_input(
                "Date of Birth (optional)",
                value=None,
                min_value=None,
                format="YYYY-MM-DD",
            )
            submitted = st.form_submit_button(
                "Create My Account", use_container_width=True, type="primary"
            )

        if submitted:
            if not phone.strip():
                st.error("Phone number is required.")
            elif len(phone.strip()) > 15:
                st.error("Phone number must be 15 characters or fewer.")
            else:
                _do_google_register(phone.strip(), str(dob) if dob else None)

        if st.session_state.login_error:
            st.error(st.session_state.login_error)

        st.markdown("---")
        if st.button("← Back to Login", use_container_width=False):
            for k in ["reg_token", "reg_name", "reg_email"]:
                st.session_state.pop(k, None)
            st.session_state.login_error = ""
            st.rerun()


def _do_google_register(phone: str, dob: str | None):
    try:
        resp = requests.post(
            REGISTER_URL,
            json={
                "reg_token":     st.session_state.get("reg_token", ""),
                "phone":         phone,
                "date_of_birth": dob,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            from app.modules.auth.service import decode_token
            token_payload = decode_token(data["access_token"])
            _set_logged_in(data["access_token"], token_payload or {
                "role": data["role"],
                "username": data["username"],
                "user_id": data["user_id"],
                "display_name": data["display_name"],
            })
            # Clear reg state
            for k in ["reg_token", "reg_name", "reg_email"]:
                st.session_state.pop(k, None)
            st.session_state.login_error = ""
            st.rerun()
        else:
            detail = resp.json().get("detail", "Registration failed.")
            st.session_state.login_error = detail
            st.rerun()
    except requests.exceptions.ConnectionError:
        st.session_state.login_error = "⚠️ Cannot reach backend. Is the server running?"
        st.rerun()
    except Exception as e:
        st.session_state.login_error = f"Unexpected error: {e}"
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN PAGE
# ─────────────────────────────────────────────────────────────────────────────

def show_login():
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("<div class='login-title'>🏥 DPMS Assistant</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='login-sub'>Doctor-Patient Management System</div>",
            unsafe_allow_html=True,
        )
        st.divider()

        # ── Tab 1: Patient (Google) | Tab 2: Staff / Doctor ──────────────
        tab_patient, tab_staff = st.tabs(["🧑 Patient — Sign in with Google", "🔑 Staff / Doctor Login"])

        # ── Patient tab ───────────────────────────────────────────────────
        with tab_patient:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                "Patients sign in securely using their **Google account**. "
                "No separate registration needed.",
                unsafe_allow_html=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)

            # Google Sign-In button (opens backend redirect in same tab)
            st.markdown(
                f"""
                <a href="{GOOGLE_LOGIN_URL}" target="_self" class="google-btn">
                    <svg width="20" height="20" viewBox="0 0 48 48">
                        <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
                        <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
                        <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
                        <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
                    </svg>
                    Sign in with Google
                </a>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            st.caption(
                "After clicking, you'll be taken to Google's sign-in page. "
                "You'll be redirected back automatically once signed in."
            )

        # ── Staff / Doctor tab ────────────────────────────────────────────
        with tab_staff:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.form("login_form", clear_on_submit=False):
                username  = st.text_input("Username", placeholder="e.g. admin")
                password  = st.text_input("Password", type="password", placeholder="••••••••")
                submitted = st.form_submit_button(
                    "Login", use_container_width=True, type="primary"
                )

            if submitted:
                if not username or not password:
                    st.error("Please enter both username and password.")
                else:
                    _do_login(username, password)

            st.divider()
            st.markdown(
                "<small>Demo accounts:<br>"
                "`admin / Admin@123` &nbsp;·&nbsp; "
                "`receptionist / Recep@123` &nbsp;·&nbsp; "
                "`doctor_arun / Doctor@123`</small>",
                unsafe_allow_html=True,
            )

        if st.session_state.login_error:
            st.error(st.session_state.login_error)


def _do_login(username: str, password: str):
    try:
        resp = requests.post(
            LOGIN_URL,
            json={"username": username, "password": password},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            st.session_state.token        = data["access_token"]
            st.session_state.role         = data["role"]
            st.session_state.username     = data["username"]
            st.session_state.display_name = data["display_name"]
            st.session_state.user_id      = data["user_id"]
            st.session_state.session_id   = f"session-{str(data['user_id'])[:8]}"
            st.session_state.messages     = []
            st.session_state.login_error  = ""
            st.rerun()
        elif resp.status_code == 401:
            st.session_state.login_error = "Invalid username or password."
            st.rerun()
        else:
            st.session_state.login_error = (
                f"Login failed (HTTP {resp.status_code}). Is the backend running?"
            )
            st.rerun()
    except requests.exceptions.ConnectionError:
        st.session_state.login_error = (
            "⚠️ Cannot reach backend at http://127.0.0.1:8000. "
            "Please start the FastAPI server first."
        )
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
            f"{meta['label']}</span> "
            f"<small>@{st.session_state.username}</small>",
            unsafe_allow_html=True,
        )
        st.divider()

        st.markdown("**Chat Session**")
        new_sid = st.text_input(
            "Session ID",
            value=st.session_state.session_id,
            help="Change to start fresh or resume a previous conversation.",
        )
        if new_sid != st.session_state.session_id:
            st.session_state.session_id        = new_sid
            st.session_state.loaded_session_id = None
            st.session_state.messages          = []
            st.rerun()

        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages          = []
            st.session_state.loaded_session_id = None
            st.rerun()

        st.divider()
        st.markdown("**Quick actions:**")
        for hint in _role_hints(role):
            st.markdown(f"- _{hint}_")

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()


def _role_hints(role: str) -> list:
    return {
        "ADMIN": [
            "List all doctors",
            "Show today's appointments",
            "Who has the most bookings this week?",
            "Show patients with high risk score",
        ],
        "RECEPTIONIST": [
            "Book an appointment for Amit with Dr. Arun tomorrow morning",
            "Cancel appointment <ID>",
            "What times does Dr. Priya have on Friday?",
            "Show today's schedule",
        ],
        "DOCTOR": [
            "Show my appointments today",
            "Who are my upcoming patients this week?",
        ],
        "PATIENT": [
            "Book me an appointment with a cardiologist",
            "Show my upcoming appointments",
            "Cancel my appointment",
            "What times are available with Dr. Arun tomorrow?",
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
    st.caption(
        f"Logged in as **{st.session_state.display_name}** · "
        f"Role: **{meta['label']}**"
    )
    st.divider()

    # Load history from MongoDB when session changes
    sid = st.session_state.session_id
    if st.session_state.loaded_session_id != sid:
        try:
            conv = fetch_conversation(sid)
            if conv:
                st.session_state.messages = [
                    {
                        "role":    "user" if m.get("sender") == "user" else "assistant",
                        "content": m.get("content", ""),
                    }
                    for m in conv.get("messages", [])
                ]
            else:
                st.session_state.messages = []
        except Exception:
            st.session_state.messages = []
        st.session_state.loaded_session_id = sid

    # Render history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Welcome on fresh session
    if not st.session_state.messages:
        with st.chat_message("assistant"):
            st.markdown(
                f"Hello **{st.session_state.display_name}**! 👋 "
                "I'm your DPMS assistant. How can I help you today?"
            )

    user_msg = st.chat_input("Type your message…")
    if user_msg:
        st.session_state.messages.append({"role": "user", "content": user_msg})
        with st.chat_message("user"):
            st.markdown(user_msg)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                reply = _call_agent(user_msg)
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
        return "⚠️ Backend is not reachable. Make sure the FastAPI server is running."
    except requests.exceptions.Timeout:
        return "⏱️ Request timed out. Please try again."
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            st.session_state.token = None
            st.rerun()
        return f"Server error: {e}"
    except Exception as e:
        return f"Unexpected error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if st.session_state.token:
    show_chat()
elif st.session_state.get("reg_token"):
    show_registration_form()
else:
    show_login()

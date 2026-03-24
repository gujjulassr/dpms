"""
DPMS Chatbot UI — keep it simple, just the chat.
"""

from pathlib import Path
import sys

import requests
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.conversations.service import fetch_conversation

st.set_page_config(page_title="DPMS Chat", page_icon="🏥", layout="centered")
st.title("🏥 DPMS Assistant")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "loaded_session_id" not in st.session_state:
    st.session_state.loaded_session_id = None

with st.sidebar:
    role       = st.selectbox("Role", ["ADMIN", "STAFF", "PATIENT"])
    user_id    = st.text_input("User ID", value="admin-1")
    session_id = st.text_input("Session ID", value="session-1")
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

BACKEND_URL = "http://127.0.0.1:8000/agents/chat"

# Load history from MongoDB when session changes
if st.session_state.loaded_session_id != session_id:
    conversation = fetch_conversation(session_id)
    if conversation:
        st.session_state.messages = [
            {"role": "user" if m.get("sender") == "user" else "assistant",
             "content": m.get("content", "")}
            for m in conversation.get("messages", [])
        ]
    else:
        st.session_state.messages = []
    st.session_state.loaded_session_id = session_id

# Render chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Chat input
user_message = st.chat_input("Type your message…")

if user_message:
    st.session_state.messages.append({"role": "user", "content": user_message})
    with st.chat_message("user"):
        st.write(user_message)

    with st.spinner("…"):
        try:
            res = requests.post(BACKEND_URL, json={
                "role": role,
                "user_id": user_id,
                "message": user_message,
                "session_id": session_id,
            }, timeout=60)
            res.raise_for_status()
            reply = res.json().get("message", "No response.")
        except requests.RequestException as e:
            reply = f"Request failed: {e}"

    st.session_state.messages.append({"role": "assistant", "content": reply})
    with st.chat_message("assistant"):
        st.write(reply)

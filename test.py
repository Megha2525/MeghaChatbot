import streamlit as st
import google.generativeai as genai
import pyttsx3
import speech_recognition as sr
from deep_translator import GoogleTranslator

"""
Megha's Chatbot w/ Gemini API Key Gate
--------------------------------------
This version shows an onboarding screen *before* the chatbot loads.
The user must paste a valid Gemini API key (from Google AI Studio) or follow a link
to create one. Once validated, the key is stored in `st.session_state` for the
current browser session only (NOT persisted to disk). The chatbot then runs using
that key.

Security notes:
- Do NOT hard‑code keys in source when sharing publicly.
- For multi‑user/public deployments, prefer Streamlit secrets manager or a server‑side
  credential store; the gated UI is best for personal/demo use.
"""

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------
API_KEY_PORTAL_URL = "https://aistudio.google.com/app/apikey"
GEMINI_MODEL_NAME = "gemini-1.5-flash"

# ------------------------------------------------------------------
# Page Config (do this early)
# ------------------------------------------------------------------
st.set_page_config(page_title="Megha's Chatbot", page_icon="**", layout="wide")

# ------------------------------------------------------------------
# Session State Bootstrapping
# ------------------------------------------------------------------
# API key management flags
if "gemini_api_key" not in st.session_state:
    st.session_state.gemini_api_key = None  # will hold the user‑supplied key
if "api_valid" not in st.session_state:
    st.session_state.api_valid = False
if "api_error" not in st.session_state:
    st.session_state.api_error = ""

# Chat data
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []  # list of (role, msg)
if "latest_question" not in st.session_state:
    st.session_state.latest_question = ""
if "latest_answer" not in st.session_state:
    st.session_state.latest_answer = ""

# ------------------------------------------------------------------
# Helper: validate key with a low‑cost call
# ------------------------------------------------------------------
def validate_gemini_key(candidate_key: str):
    """Try a tiny request against Gemini to confirm the key works.

    Returns (ok: bool, err_msg: str).
    """
    try:
        genai.configure(api_key=candidate_key)
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        # minimal content to trigger auth; keep tokens tiny
        _ = model.generate_content("ping")
        return True, ""
    except Exception as e:  # broad catch; show msg to user
        return False, str(e)


# ------------------------------------------------------------------
# API Key Gate UI
# ------------------------------------------------------------------
def api_key_gate():
    st.title("🔐 Enter Gemini API Key")
    st.markdown(
        "Paste your Gemini API key below. You can create/manage keys in Google AI Studio."
    )
    st.markdown(f"[Create / manage your API key]({API_KEY_PORTAL_URL})")

    with st.form("api_key_form", clear_on_submit=False):
        key_input = st.text_input(
            "Gemini API Key",
            type="password",
            placeholder="Paste your key here...",
            help="Your key stays only in this session state (not saved to disk).",
        )
        submitted = st.form_submit_button("Save & Continue")

    if submitted:
        key_input = key_input.strip()
        if not key_input:
            st.error("Please paste a key.")
            return
        ok, err = validate_gemini_key(key_input)
        if ok:
            st.session_state.gemini_api_key = key_input
            st.session_state.api_valid = True
            st.session_state.api_error = ""
            st.success("API key accepted! Loading chatbot...")
            st.rerun()  # reload w/ valid key
        else:
            st.session_state.api_valid = False
            st.session_state.api_error = err
            st.error(f"API key validation failed: {err}")

    # show last error if present and not re‑submitted
    if st.session_state.api_error and not submitted:
        st.error(f"Previous error: {st.session_state.api_error}")


# ------------------------------------------------------------------
# Gemini model accessor (safe after key valid)
# ------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_gemini_model(api_key: str):
    # Because cache_resource memoizes per key, changing key invalidates cache.
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(GEMINI_MODEL_NAME)


# ------------------------------------------------------------------
# AI Response Generation (uses current model)
# ------------------------------------------------------------------
def generate_response(prompt: str, model):
    try:
        # Gemini expects chronological history oldest->newest; we stored newest first.
        # Reconstruct in correct order.
        formatted_history = [
            {"role": role, "parts": [msg]} for role, msg in reversed(st.session_state.chat_history)
        ]
        chat = model.start_chat(history=formatted_history)
        response = chat.send_message(prompt)
        return response.text
    except Exception as e:
        return f"❌ Error: {e}"


# ------------------------------------------------------------------
# Text‑to‑Speech
# ------------------------------------------------------------------
def text_to_speech(text, lang="en"):
    try:
        translated_text = GoogleTranslator(source="auto", target=lang).translate(text)
        engine = pyttsx3.init()
        engine.say(translated_text)
        engine.runAndWait()
        return translated_text
    except Exception as e:
        return f"TTS error: {e}"


# ------------------------------------------------------------------
# Speech‑to‑Text
# ------------------------------------------------------------------
def speech_to_text():
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            st.info("🎤 Listening... Speak now!")
            recognizer.adjust_for_ambient_noise(source)
            audio = recognizer.listen(source)
            text = recognizer.recognize_google(audio, language="en-US")
            return text
    except sr.UnknownValueError:
        return "Sorry, couldn't understand you."
    except sr.RequestError:
        return "Network error with speech recognition service."
    except OSError:
        return "Microphone not found. Please check your device."


# ------------------------------------------------------------------
# Sidebar: API Key Management
# ------------------------------------------------------------------
with st.sidebar:
    st.header("Settings")
    if st.session_state.api_valid:
        st.success("Gemini key loaded.")
        if st.button("Change / Remove API Key"):
            # clear key + cached model
            st.session_state.gemini_api_key = None
            st.session_state.api_valid = False
            st.session_state.api_error = ""
            get_gemini_model.clear()  # clear cache_resource
            st.rerun()
    else:
        st.warning("No valid API key yet.")
        st.markdown(f"[Get a key]({API_KEY_PORTAL_URL})")


# ------------------------------------------------------------------
# MAIN APP ROUTER
# ------------------------------------------------------------------
if not st.session_state.api_valid:
    # Show gate screen & stop the script early
    api_key_gate()
    st.stop()

# If we reach here, API key is valid ---------------------------------
model = get_gemini_model(st.session_state.gemini_api_key)

st.title("Megha's Chatbot")
st.caption("Ask me anything — from science to stories, AI to astrology — I'm here for you!")

# --- Input Area ---
st.markdown("### 💬 Ask something")
col1, col2 = st.columns([4, 1])

with col1:
    user_input = st.text_input("Type your message...", key="text_input")

with col2:
    if st.button("🎙️"):
        st.session_state["speech_input"] = speech_to_text()
        st.rerun()

# Use speech input if available
if "speech_input" in st.session_state:
    user_input = st.session_state.speech_input
    del st.session_state.speech_input

# --- Generate Response ---
if user_input:
    # Save previous Q&A to history
    if st.session_state.latest_question and st.session_state.latest_answer:
        st.session_state.chat_history.insert(0, ("user", st.session_state.latest_question))
        st.session_state.chat_history.insert(0, ("model", st.session_state.latest_answer))

    with st.spinner("🤖 Thinking..."):
        ai_response = generate_response(user_input, model)

    st.session_state.latest_question = user_input
    st.session_state.latest_answer = ai_response

# --- Display Latest Conversation ---
if st.session_state.latest_question and st.session_state.latest_answer:
    st.markdown("### 🔹 Latest Conversation")
    st.markdown(f"**👤 You:** {st.session_state.latest_question}")
    st.markdown(f"**🤖 Megha's Chatbot:** {st.session_state.latest_answer}")

# --- Text-to-Speech Option ---
lang = st.selectbox(
    "🌍 Read aloud in language",
    ["en", "te", "hi", "es", "fr", "de", "zh", "ar", "ru", "ja"],
)
if st.button("▶ Read Last AI Response"):
    if st.session_state.latest_answer:
        spoken_text = text_to_speech(st.session_state.latest_answer, lang)
        st.success(f"🔊 Speaking in {lang}: {spoken_text}")
    else:
        st.warning("No AI response yet to read.")

# --- Show Previous Chat History ---
with st.expander("📜 Show Previous Chat History"):
    for role, msg in st.session_state.chat_history:
        if role == "user":
            st.markdown(f"**👤 You (old):** {msg}")
        else:
            st.markdown(f"**🤖 Megha (old):** {msg}")

# --- Footer ---
st.markdown("---")
st.markdown("<center>© All rights reserved. Made with Dedication by Megha Sharma</center>", unsafe_allow_html=True)

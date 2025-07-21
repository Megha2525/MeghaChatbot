import streamlit as st
import google.generativeai as genai
import speech_recognition as sr
from deep_translator import GoogleTranslator
from gtts import gTTS
import tempfile
import os

"""
Megha's Chatbot w/ Gemini API Key Gate
--------------------------------------
This version shows an onboarding screen *before* the chatbot loads.
The user must paste a valid Gemini API key (from Google AI Studio).
"""

API_KEY_PORTAL_URL = "https://aistudio.google.com/app/apikey"
GEMINI_MODEL_NAME = "gemini-1.5-flash"

# Streamlit Page Config
st.set_page_config(page_title="Megha's Chatbot", page_icon="🤖", layout="wide")

# Session State
if "gemini_api_key" not in st.session_state:
    st.session_state.gemini_api_key = None
if "api_valid" not in st.session_state:
    st.session_state.api_valid = False
if "api_error" not in st.session_state:
    st.session_state.api_error = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "latest_question" not in st.session_state:
    st.session_state.latest_question = ""
if "latest_answer" not in st.session_state:
    st.session_state.latest_answer = ""

# Validate Gemini Key
def validate_gemini_key(candidate_key: str):
    try:
        genai.configure(api_key=candidate_key)
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        _ = model.generate_content("ping")
        return True, ""
    except Exception as e:
        return False, str(e)

def api_key_gate():
    st.title("🔐 Enter Gemini API Key")
    st.markdown("Paste your Gemini API key below. You can create/manage keys in Google AI Studio.")
    st.markdown(f"[Create / manage your API key]({API_KEY_PORTAL_URL})")
    with st.form("api_key_form", clear_on_submit=False):
        key_input = st.text_input("Gemini API Key", type="password", placeholder="Paste your key here...")
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
            st.rerun()
        else:
            st.session_state.api_valid = False
            st.session_state.api_error = err
            st.error(f"API key validation failed: {err}")

    if st.session_state.api_error and not submitted:
        st.error(f"Previous error: {st.session_state.api_error}")

@st.cache_resource(show_spinner=False)
def get_gemini_model(api_key: str):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(GEMINI_MODEL_NAME)

def generate_response(prompt: str, model):
    try:
        formatted_history = [
            {"role": role, "parts": [msg]} for role, msg in reversed(st.session_state.chat_history)
        ]
        chat = model.start_chat(history=formatted_history)
        response = chat.send_message(prompt)
        return response.text
    except Exception as e:
        return f"❌ Error: {e}"

# New TTS with gTTS
def text_to_speech(text, lang="en"):
    try:
        translated_text = GoogleTranslator(source="auto", target=lang).translate(text)
        tts = gTTS(translated_text, lang=lang)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            tts.save(fp.name)
            st.audio(fp.name, format="audio/mp3")
        return translated_text
    except Exception as e:
        return f"TTS error: {e}"

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

# Sidebar
with st.sidebar:
    st.header("Settings")
    if st.session_state.api_valid:
        st.success("Gemini key loaded.")
        if st.button("Change / Remove API Key"):
            st.session_state.gemini_api_key = None
            st.session_state.api_valid = False
            st.session_state.api_error = ""
            get_gemini_model.clear()
            st.rerun()
    else:
        st.warning("No valid API key yet.")
        st.markdown(f"[Get a key]({API_KEY_PORTAL_URL})")

# Main
if not st.session_state.api_valid:
    api_key_gate()
    st.stop()

model = get_gemini_model(st.session_state.gemini_api_key)
st.title("Megha's Chatbot")
st.caption("Ask me anything — from science to stories, AI to astrology — I'm here for you!")

# Input
st.markdown("### 💬 Ask something")
col1, col2 = st.columns([4, 1])
with col1:
    user_input = st.text_input("Type your message...", key="text_input")
with col2:
    if st.button("🎙️"):
        st.session_state["speech_input"] = speech_to_text()
        st.rerun()

if "speech_input" in st.session_state:
    user_input = st.session_state.speech_input
    del st.session_state.speech_input

# Response
if user_input:
    if st.session_state.latest_question and st.session_state.latest_answer:
        st.session_state.chat_history.insert(0, ("user", st.session_state.latest_question))
        st.session_state.chat_history.insert(0, ("model", st.session_state.latest_answer))

    with st.spinner("🤖 Thinking..."):
        ai_response = generate_response(user_input, model)

    st.session_state.latest_question = user_input
    st.session_state.latest_answer = ai_response

# Show Conversation
if st.session_state.latest_question and st.session_state.latest_answer:
    st.markdown("### 🔹 Latest Conversation")
    st.markdown(f"**👤 You:** {st.session_state.latest_question}")
    st.markdown(f"**🤖 Megha's Chatbot:** {st.session_state.latest_answer}")

# TTS Option
lang = st.selectbox("🌍 Read aloud in language", ["en", "te", "hi", "es", "fr", "de", "zh", "ar", "ru", "ja"])
if st.button("▶ Read Last AI Response"):
    if st.session_state.latest_answer:
        spoken_text = text_to_speech(st.session_state.latest_answer, lang)
        st.success(f"🔊 Speaking in {lang}: {spoken_text}")
    else:
        st.warning("No AI response yet to read.")

# Chat History
with st.expander("📜 Show Previous Chat History"):
    for role, msg in st.session_state.chat_history:
        if role == "user":
            st.markdown(f"**👤 You (old):** {msg}")
        else:
            st.markdown(f"**🤖 Megha (old):** {msg}")

# Footer
st.markdown("---")
st.markdown("<center>© All rights reserved. Made with Dedication by Megha Sharma</center>", unsafe_allow_html=True)

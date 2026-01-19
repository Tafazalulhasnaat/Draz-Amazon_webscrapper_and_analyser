import streamlit as st
import time

st.set_page_config(
    page_title="AI Chatbot",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Max width control
st.markdown("""
<style>
.main .block-container {
    max-width: 720px;
    padding: 1rem;
}
</style>
""", unsafe_allow_html=True)

st.title("🤖 AI Chatbot")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

def ai_reply(prompt):
    time.sleep(1)
    return f"Echo: {prompt}"

prompt = st.chat_input("Type your message...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply = ai_reply(prompt)
            st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})

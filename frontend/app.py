import streamlit as st


st.set_page_config(page_title="Streamlit Input Form", layout="centered")

st.title("Input Form")
st.write("Enter your details below and click submit.")

with st.form("input_form"):
    name = st.text_input("Name", placeholder="Enter your name")
    message = st.text_area("Message", placeholder="Type your message here")
    submitted = st.form_submit_button("Submit")

if submitted:
    if not name.strip() or not message.strip():
        st.warning("Please fill in both fields before submitting.")
    else:
        st.success("Form submitted successfully.")
        st.write(f"Name: {name}")
        st.write(f"Message: {message}")
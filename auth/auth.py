import bcrypt
import streamlit as st

from db import database as db

MIN_PASSWORD_LENGTH = 6


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def register(username: str, password: str) -> tuple[bool, str]:
    username = username.strip()
    if not username:
        return False, "Username is required."
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."

    user_id = db.create_user(username, hash_password(password))
    if user_id is None:
        return False, "Username already taken."

    st.session_state["user_id"] = user_id
    st.session_state["username"] = username
    return True, "Account created."


def login(username: str, password: str) -> tuple[bool, str]:
    user = db.get_user_by_username(username.strip())
    if not user or not verify_password(password, user["password_hash"]):
        return False, "Invalid username or password."

    st.session_state["user_id"] = user["id"]
    st.session_state["username"] = user["username"]
    return True, "Logged in."


def logout() -> None:
    for key in ("user_id", "username"):
        st.session_state.pop(key, None)


def render_auth_forms() -> None:
    st.title("Fitness App")
    st.caption("Log in or create an account to continue.")

    tab_login, tab_register = st.tabs(["Log in", "Register"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            if st.form_submit_button("Log in", type="primary"):
                ok, msg = login(username, password)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    with tab_register:
        with st.form("register_form"):
            username = st.text_input("Username", key="reg_username")
            password = st.text_input("Password", type="password", key="reg_password")
            password2 = st.text_input("Confirm password", type="password", key="reg_password2")
            if st.form_submit_button("Create account", type="primary"):
                if password != password2:
                    st.error("Passwords do not match.")
                else:
                    ok, msg = register(username, password)
                    if ok:
                        st.switch_page("pages/1_Profile.py")
                    else:
                        st.error(msg)


def is_logged_in() -> bool:
    return "user_id" in st.session_state and st.session_state["user_id"] is not None


def current_user_id() -> int | None:
    return st.session_state.get("user_id")


def current_username() -> str | None:
    return st.session_state.get("username")


def require_login() -> int:
    if not is_logged_in():
        render_auth_forms()
        st.stop()
    return st.session_state["user_id"]


def render_logout_button() -> None:
    if is_logged_in():
        st.sidebar.markdown(f"**Logged in as:** {current_username()}")
        if st.sidebar.button("Log out"):
            logout()
            st.rerun()

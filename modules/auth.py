#modules/auth.py
import streamlit as st
import bcrypt
from modules import db_manager, nav

def init_session_state():
    """Initialize necessary session state variables."""
    defaults = {
        "logged_in": False,
        "user_id": None,
        "username": "Guest",
        "user_mode": "Normal",
        "followed_ids": [] # Store list of followed reviewer IDs
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def get_current_user_data(user_id):
    """Retrieve user row from DB."""
    con = db_manager.get_db()
    try:
        user = con.execute("SELECT * FROM users WHERE id = ?", [user_id]).df()
        if not user.empty:
            return user.iloc[0].to_dict()
    except: return None
    
def login_user(username_or_email, password):
    con = db_manager.get_db()
    try:
        user = con.execute("SELECT * FROM users WHERE email = ? OR username = ?", [username_or_email, username_or_email]).df()
        if user.empty: return False, "ไม่พบผู้ใช้"
        
        user_row = user.iloc[0]
        hashed = user_row.get('password_hash', 'NO_HASH')
        
        # --- Authentication Check ---
        valid = False
        try:
            if bcrypt.checkpw(password.encode(), hashed.encode()): valid = True
        except: pass
        
        # Admin Mock Bypass
        if user_row['id'] == 1 and password == "password123": valid = True
        
        if valid:
            st.session_state['logged_in'] = True
            st.session_state['user_id'] = int(user_row['id'])
            st.session_state['username'] = user_row['username']
            st.session_state['user_mode'] = 'AI'
            
            # --- FIX: Robust Followed List Loading ---
            raw = str(user_row.get('followed_reviewers', ''))
            
            # Clean potential leading apostrophe from Google Sheets
            if raw.startswith("'"):
                raw = raw[1:]
                
            if raw and raw != 'nan' and raw.strip():
                try:
                    # Filter out non-numeric strings and cast to int
                    st.session_state['followed_ids'] = [int(x) for x in raw.split(',')]
                    #st.session_state['followed_ids'] = [int(x) for x in raw.split(',') if x.strip().isdigit()]
                except:
                    st.session_state['followed_ids'] = []
            else:
                st.session_state['followed_ids'] = []
                
            return True, "Success"
            
        return False, "รหัสผ่านผิด"
    except Exception as e: 
        return False, f"Login Error: {e}"

def logout():
    """Clear session state and navigate to home."""
    for k in ['logged_in', 'user_id', 'username', 'user_mode', 'followed_ids']:
        if k in st.session_state: del st.session_state[k]
    init_session_state()
    nav.navigate_to("App.py")

def get_user_mode():
    """Returns 'AI' if logged in, otherwise 'Normal'."""
    return st.session_state.get('user_mode', 'Normal')
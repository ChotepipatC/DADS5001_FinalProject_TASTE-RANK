#pages/4_Profile.py

import streamlit as st
from modules import auth, db_manager, nav

st.set_page_config(page_title="My Profile", layout="wide")
nav.inject_custom_css()
auth.init_session_state()

# --- Authentication Check ---
if not st.session_state['logged_in']:
    st.warning("🔒 กรุณาเข้าสู่ระบบ AI Mode ก่อน")
    if st.button("⬅️ กลับหน้าหลัก"): nav.navigate_to("App.py")
    st.stop()

# --- Data Retrieval ---
user_id = st.session_state['user_id']
user_data = auth.get_current_user_data(user_id) # Fetch fresh user data if needed

if not user_data:
    st.error("เกิดข้อผิดพลาดในการโหลดข้อมูลผู้ใช้")
    if st.button("🚪 ออกจากระบบ"): auth.logout()
    st.stop()

st.title(f"👤 My Profile: {st.session_state['username']} 👋")
st.caption(f"User ID: {user_id} | Mode: **{auth.get_user_mode()}**")

st.divider()

# --- Followed Reviewers ---
st.subheader("👥 นักชิมที่คุณติดตาม")
f_ids = st.session_state['followed_ids']
if f_ids:
    cols = st.columns(3)
    for i, fid in enumerate(f_ids):
        with cols[i % 3]:
            rev = db_manager.get_reviewer_detail(fid)
            if rev:
                with st.container(border=True):
                    st.write(f"**{rev['name']}**")
                    st.caption(f"🫂 {rev['followers']} ผู้ติดตาม")
                    if st.button("ดูโปรไฟล์", key=f"my_f_{fid}", use_container_width=True):
                        nav.navigate_to("pages/3_Reviewer.py", {"id": fid})
            else:
                st.warning(f"ID {fid} ไม่พบในระบบ")
else:
    st.info("คุณยังไม่ได้ติดตาม Reviewer คนใด")

st.divider()

c1, c2 = st.columns(2)
with c1:
    if st.button("⬅️ กลับหน้าหลัก", type="secondary", use_container_width=True):
        nav.navigate_to("App.py")

with c2:
    if st.button("🚪 ออกจากระบบ", type="primary", use_container_width=True):
        auth.logout()
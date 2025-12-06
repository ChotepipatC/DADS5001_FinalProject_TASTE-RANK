#pages/3_Reviewer.py
import streamlit as st
import pandas as pd
from modules import db_manager, auth, nav

st.set_page_config(page_title="Reviewer Profile", layout="wide")
nav.inject_custom_css()
auth.init_session_state()

rev_id = nav.get_param("id", type_cast=int)
if not rev_id:
    st.error("ไม่พบรหัส Reviewer")
    if st.button("⬅️ กลับหน้าหลัก"): nav.navigate_to("App.py")
    st.stop()

reviewer = db_manager.get_reviewer_detail(rev_id)
if not reviewer:
    st.error("ไม่พบ Reviewer")
    if st.button("⬅️ กลับหน้าหลัก"): nav.navigate_to("App.py")
    st.stop()
    
reviews = db_manager.get_reviews_by_reviewer_name(reviewer['name'])
avg_given = db_manager.get_average_rating_given(reviewer['name'])

# --- LOGIC ---
def handle_follow_click(target_id):
    if auth.get_user_mode() != 'AI':
        st.error("กรุณาเข้าสู่ระบบ AI Mode")
        return False
    user_id = st.session_state['user_id']
    current_follows = st.session_state.get('followed_ids', [])
    if target_id in current_follows:
        current_follows.remove(target_id)
        db_manager.update_reviewer_follower_count(target_id, increment=False)
    else:
        current_follows.append(target_id)
        db_manager.update_reviewer_follower_count(target_id, increment=True)
    db_manager.update_user_followed_list(user_id, current_follows)
    st.session_state['followed_ids'] = current_follows
    return True

# --- HEADER ---
if st.button("⬅️ กลับ"): nav.navigate_to("App.py")

c1, c2 = st.columns([3, 1])
c1.title(f"🧑‍🍳 {reviewer['name']}")
c1.write(f"**สถิติ:** 📝 {reviewer['total_reviews']} รีวิว | 🫂 {reviewer['followers']} ผู้ติดตาม | ⭐ ให้คะแนนเฉลี่ย: {avg_given:.2f}")

with c2:
    if auth.get_user_mode() == 'AI':
        is_following = rev_id in st.session_state.get('followed_ids', [])
        label = "✅ เลิกติดตาม" if is_following else "➕ ติดตาม"
        type_ = "secondary" if is_following else "primary"
        if st.button(label, type=type_, use_container_width=True):
            if handle_follow_click(rev_id): st.rerun()
    else:
        st.info("Login เพื่อติดตาม")

st.divider()

# --- AI SUMMARY ---
with st.container(border=True):
    if auth.get_user_mode() == 'AI':
            st.subheader("🤖 AI Analysis: สไตล์นักชิม")
            
            # 1. Extract content (Not Rating!)
            if not reviews.empty and 'content' in reviews.columns:
                # Filter out empty or too short reviews
                valid_reviews = reviews[reviews['content'].astype(str).str.len() > 5]
                
                # 2. Limit Data Size: Take top 15 recent reviews to keep input tokens low (~300-500 tokens)
                # This ensures processing time < 15s on CPU
                text_data = " ".join(valid_reviews['content'].astype(str).tolist())
                rating_data = valid_reviews['rating'].astype(int).tolist()
                
                # 3. Hard Limit Characters: Just in case reviews are very long paragraphs
                if len(text_data) > 10000: 
                    text_data = text_data[:10000] + "..."
                    
                if len(text_data) < 10:
                    st.info("ข้อมูลรีวิวน้อยเกินไปสำหรับการวิเคราะห์")
                else:
                    # --- OPTIMIZED PROMPT FOR SMALL MODEL (1B/2B) ---
                    # Strategy: Direct instruction + Data + Output Template
                    user_prompt = f"""
                    Analyze the following restaurant reviews of reviewer: {reviewer['name']} 
                    and summarize about the reviewer in Thai language only.
                    Keep it concise. Use the exact format below.
                    Do it without intro and footnote.
                    Question back is not allow.

                    Reviews:
                    "{text_data}"

                    Rating:
                    "{rating_data=}"

                    Format:
                    จากการวิเคราะห์ประวัติการรีวิวของ **{reviewer['name']}**:
                    - **🍛 แนวอาหารที่ชอบ:** [A kind of food reviewer interest, if the pattern don't clear, show as N/A.
                    Don't show that information unless they're >= 85% confident about it. 
                    Don't conclude the reviewer like Thai food unless they're at least 1 word of "Thai" appear in Reviews.
                    ]
                    - **⭐ สไตล์การให้คะแนน:** [Reviewer rating bahavior in Thai language]
                    - **📍 [Other interesting fact(s)]              

                    """
                    
                    # Call AI
                    with st.spinner("🤖 AI กำลังอ่านรีวิว..."):
                        ai_response = db_manager.get_ollama_text_response(user_prompt)
                    
                    st.markdown(ai_response)
            else:
                st.info("ยังไม่มีข้อมูลรีวิวให้วิเคราะห์")
    else:
        st.subheader("🔒 เข้าสู่ระบบ AI Mode เพื่อดูบทวิเคราะห์สไตล์นักชิม")

st.divider()

# --- REVISITED ---
st.subheader("🔁 ร้านที่ไปรีวิวซ้ำ")
if auth.get_user_mode() == 'AI':
    revisited = db_manager.get_revisited_restaurants(reviewer['name'])
    if not revisited.empty:
        for _, r in revisited.iterrows():
            st.write(f"📍 **{r['name']}** - {r['visit_count']} ครั้ง (ล่าสุด: {r['last_visit'].strftime('%Y-%m-%d')})")
    else:
        st.write("ยังไม่มีร้านที่รีวิวซ้ำ")
else:
    st.warning("🔒 เฉพาะ AI Mode")

st.divider()

# --- REVIEWS HISTORY (FIX 2.1) ---
st.subheader("📝 ประวัติการรีวิว")

is_ai_mode = auth.get_user_mode() == 'AI'
if 'show_all_reviews_rev' not in st.session_state:
    st.session_state['show_all_reviews_rev'] = False

# Ensure sorting
reviews = reviews.sort_values('timestamp', ascending=False)

if not reviews.empty:
    if not is_ai_mode:
        # Normal Mode: Show max 2
        display_reviews = reviews.head(2)
        has_more = len(reviews) > 2
    else:
        # AI Mode: Show max 3 or All
        if not st.session_state['show_all_reviews_rev']:
            display_reviews = reviews.head(3)
            has_more = len(reviews) > 3
        else:
            display_reviews = reviews
            has_more = False

    # Render Reviews
    for _, r in display_reviews.iterrows():
        with st.container(border=True):
            rc1, rc2 = st.columns([4, 1])
            rc1.markdown(f"**{r['restaurant_name']}**")
            rc1.caption(f"{r['timestamp']}")
            rc1.write(r['content'])
            rc2.write("⭐" * int(r['rating']))
            if rc2.button("ดูร้าน", key=f"go_rest_{r['id']}"):
                nav.navigate_to("pages/2_Restaurant.py", {"id": r['restaurant_id']})

    # Render Buttons/Banners based on state
    if not is_ai_mode and has_more:
        st.warning("🔒 กรุณาเข้าสู่ระบบ AI Mode เพื่อดูรีวิวทั้งหมดของนักชิม")
    elif is_ai_mode:
        if not st.session_state['show_all_reviews_rev'] and has_more:
             if st.button(f"⬇️ ดูรีวิวทั้งหมด ({len(reviews)} รายการ)", use_container_width=True):
                 st.session_state['show_all_reviews_rev'] = True
                 st.rerun()
        elif st.session_state['show_all_reviews_rev']:
             if st.button("⬆️ ย่อกลับ (แสดงล่าสุด)", use_container_width=True):
                 st.session_state['show_all_reviews_rev'] = False
                 st.rerun()

st.divider()

# --- SIMILAR REVIEWERS ---
st.subheader("🧑‍🍳 นักชิมที่คล้ายกัน")
sim_revs = db_manager.get_similar_reviewers_content_based(rev_id, top_n=2)
col_sim, col_search = st.columns([2, 1])

with col_sim:
    st.write("🔥 **Top 2 ใกล้เคียงที่สุด**")
    if not sim_revs.empty:
        s_cols = st.columns(2)
        for i, (_, sr) in enumerate(sim_revs.iterrows()):
            if sr['reviewer_id'] == rev_id: continue
            with s_cols[i % 2]:
                with st.container(border=True):
                    st.write(f"**{sr['name']}**")
                    st.caption(f"ตรงกัน {sr['common_restaurants']} ร้าน")
                    if st.button("ดูโปรไฟล์", key=f"sim_{sr['reviewer_id']}", use_container_width=True):
                        nav.navigate_to("pages/3_Reviewer.py", {"id": sr['reviewer_id']})
    else:
        st.write("ไม่พบข้อมูลที่เพียงพอ")

with col_search:
    with st.container(border=True):
        st.markdown("### 🔍")
        st.markdown("**ค้นหานักชิมอื่นๆ เพิ่มเติม**")
        if st.button("ไปหน้าค้นหา", key="search_all", type="primary", use_container_width=True):
            nav.navigate_to("App.py")
#App.py
import streamlit as st
import pandas as pd
import math
from modules import db_manager, auth, nav

st.set_page_config(page_title="🍜 🥇 TASTE RANK", layout="wide")
nav.inject_custom_css()
auth.init_session_state()

# --- HEADER & AUTH ---
c1, c2 = st.columns([3, 1])
c1.title("🍜 🥇 TASTE RANK")
with c2:
    if st.session_state['logged_in']:
        cols = st.columns(2)
        # FIX 1: Removed on_click
        if cols[0].button("👤 โปรไฟล์"):
            nav.navigate_to("pages/4_Profile.py")
        if cols[1].button("🚪 ออกจากระบบ"):
            auth.logout()
            # Logout usually clears state, manual rerun ensures UI updates if not handled by nav
            st.rerun() 
    else:
        with st.expander("🔑 เข้าสู่ระบบ (AI Mode)"):
            with st.form("login"):
                u = st.text_input("User")
                p = st.text_input("Pass", type="password")
                if st.form_submit_button("Login"):
                    ok, msg = auth.login_user(u, p)
                    if ok: st.rerun()
                    else: st.error(msg)

st.divider()

# --- FILTER SECTION ---
st.subheader("🔍 ค้นหาร้านอาหาร")

# Row 1: Search & Actions
c_search, c_sort = st.columns([3, 1])
query = c_search.text_input("คำค้นหา", value=nav.get_param('search_query', ''), placeholder="ชื่อร้าน, เมนู, ย่าน...")
sort_option = c_sort.selectbox("เรียงตาม", ['รีวิวมาก -> น้อย', 'รีวิวน้อย -> มาก', 'Rating สูง -> ต่ำ', 'Rating ต่ำ -> สูง'])

# Row 2: Advanced Filters
with st.expander("ตัวกรองเพิ่มเติม", expanded=bool(query)):
    cf1, cf2, cf3 = st.columns(3)
    min_rate = cf1.slider("Rating ขั้นต่ำ", 0.0, 5.0, 3.0)
    min_rev = cf2.number_input("จำนวนรีวิวขั้นต่ำ", 0, 1000, 0)
    
    cf3.write("") # Spacer
    cf3.write("") 
    
    b1, b2 = cf3.columns(2)
    # FIX 1: Removed on_click
    if b1.button("🧹 ล้างตัวกรอง", use_container_width=True):
        st.query_params.clear()
        nav.navigate_to("App.py") # Reload page clean
    
    if b2.button("📋 ดูร้านทั้งหมด", use_container_width=True):
        nav.navigate_to("App.py", {"search_query": ""})

# --- RESTAURANT RESULTS ---
results = db_manager.search_restaurants_advanced(query, min_rate, min_rev, sort_option)

if not results.empty:
    st.write(f"พบ {len(results)} ร้าน")
    
    # FIX 2.1: Slicer (Pagination)
    ITEMS_PER_PAGE = 5
    total_items = len(results)
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
    
    # Only show slicer if we have more than 1 page
    if total_pages > 1:
        page = st.select_slider(
            "เลือกหน้าแสดงผล", 
            options=range(1, total_pages + 1),
            value=1,
            format_func=lambda x: f"หน้า {x}/{total_pages}"
        )
    else:
        page = 1
        
    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    
    # Slice the dataframe
    display_results = results.iloc[start_idx:end_idx]
    
    # Display Grid
    cols = st.columns(3)
    for idx, row in display_results.iterrows():
        # idx needs to be reset relative to loop for column placement
        col_idx = (idx - start_idx) % 3 
        with cols[col_idx]:
            with st.container(border=True):
                st.subheader(row['name'])
                st.caption(f"⭐ {row['average_rating']} | 📝 {row['review_count']} รีวิว")
                st.write(f"🏷️ {row['keywords']}")
                # FIX 1: Removed on_click, using key for uniqueness
                if st.button("ดูร้าน", key=f"btn_{row['id']}", use_container_width=True):
                    nav.navigate_to("pages/2_Restaurant.py", {"id": row['id']})
else:
    st.info("ไม่พบร้านที่ค้นหา")

st.divider()

# --- REVIEWER SEARCH (BOTTOM) ---
# FIX 2.2: Advanced Filters for Reviewers
st.subheader("🏆 ค้นหานักชิม")

with st.container(border=True):
    rc1, rc2, rc3 = st.columns(3)
    r_query = rc1.text_input("ชื่อนักชิม", placeholder="ค้นหาชื่อ...")
    r_sort = rc2.selectbox("เรียงนักชิมตาม", ['จำนวนผู้ติดตาม', 'จำนวนรีวิว', 'จำนวนร้านที่รีวิว'])
    r_revisit = rc3.checkbox("เฉพาะคนที่เคยรีวิวร้านเดิมซ้ำ (Fanatic)")
    
    rc4, rc5, rc6 = st.columns(3)
    r_min_reviews = rc4.number_input("รีวิวขั้นต่ำ", 0, 100, 0)
    r_min_follows = rc5.number_input("ผู้ติดตามขั้นต่ำ", 0, 1000, 0)
    
    rc6.write("")
    if rc6.button("ล้างตัวกรองนักชิม", use_container_width=True):
        st.rerun() # Simple rerun to reset inputs if not bound to session state heavily

reviewers = db_manager.search_reviewers_advanced(r_query, r_min_reviews, r_min_follows, r_revisit, r_sort)

if not reviewers.empty:
    st.write(f"พบ {len(reviewers)} นักชิม")
    
    # FIX 2.2: Slicer for Reviewers
    REV_PER_PAGE = 4
    total_revs = len(reviewers)
    total_rev_pages = math.ceil(total_revs / REV_PER_PAGE)
    
    if total_rev_pages > 1:
        rev_page = st.select_slider(
            "เลือกหน้าแสดงผลนักชิม", 
            options=range(1, total_rev_pages + 1),
            format_func=lambda x: f"หน้า {x}/{total_rev_pages}"
        )
    else:
        rev_page = 1
        
    r_start = (rev_page - 1) * REV_PER_PAGE
    r_end = r_start + REV_PER_PAGE
    disp_reviewers = reviewers.iloc[r_start:r_end]

    r_cols = st.columns(4)
    # Iterate with index reset logic
    for i, (_, r) in enumerate(disp_reviewers.iterrows()):
        with r_cols[i]: # Simple 0-3 filling
            with st.container(border=True):
                st.write(f"**{r['name']}**")
                st.caption(f"📝 {r['total_reviews']} รีวิว")
                st.caption(f"🫂 {r['followers']} ผู้ติดตาม")
                # FIX 1: Removed on_click
                if st.button("ดูโปรไฟล์", key=f"rev_{r['reviewer_id']}", use_container_width=True):
                    nav.navigate_to("pages/3_Reviewer.py", {"id": r['reviewer_id']})
else:
    st.write("ไม่พบนักชิม")
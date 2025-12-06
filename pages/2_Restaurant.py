#pages/2_Restaurant.py
import streamlit as st
import pandas as pd
import plotly.express as px
from modules import db_manager, auth, nav

# --- CONFIG & INIT ---
st.set_page_config(page_title="Restaurant Detail", layout="wide")
nav.inject_custom_css()
auth.init_session_state()

# --- PARAMETERS ---
res_id = nav.get_param("id", type_cast=int)
if not res_id:
    st.error("ไม่พบรหัสร้านอาหาร")
    if st.button("⬅️ กลับหน้าหลัก"): nav.navigate_to("App.py")
    st.stop()

# --- LOAD DATA ---
restaurant = db_manager.get_restaurant_detail(res_id)
reviews = db_manager.get_reviews_for_restaurant(res_id)
dist_df, ts_df = db_manager.get_restaurant_reviews_stats(res_id)

if not restaurant:
    st.error("ไม่พบร้านอาหารที่ระบุ")
    if st.button("⬅️ กลับหน้าหลัก"): nav.navigate_to("App.py")
    st.stop()

# --- HEADER ---
if st.button("⬅️ กลับหน้าหลัก"): nav.navigate_to("App.py")

st.title(f"🍽️ {restaurant['name']}")
m1, m2, m3 = st.columns(3)
m1.metric("Rating เฉลี่ย", f"{restaurant['average_rating']:.2f} ⭐")
m2.metric("จำนวนรีวิว", f"{restaurant['review_count']} 📝")
m3.info(f"Metadata: Not Available")
#m3.info(f"Metadata: {restaurant.get('metadata', '-')}")

# --- AI SUMMARY ---
if auth.get_user_mode() == 'AI':
    with st.container(border=True):
        st.subheader("🤖 AI Summary (สำหรับสมาชิก)")
        
        # --- DATA PREPARATION FOR AI ---
        ai_summary_text = "กำลังวิเคราะห์ข้อมูล..."
        
        if not reviews.empty and 'content' in reviews.columns:
            valid_reviews = reviews[reviews['content'].astype(str).str.len() > 5]
            text_data = " ".join(valid_reviews['content'].astype(str).tolist()) # Use all/more content logic if needed
            
            # Use same limit as Compare Page for cache hit
            if len(text_data) > 10000: 
                text_data = text_data[:10000] + "..."
                
            if len(text_data) < 10:
                st.info("ข้อมูลรีวิวน้อยเกินไปสำหรับการวิเคราะห์")
            else:
                # --- STANDARD PROMPT (Shared with Compare Page) ---
                user_prompt = f"""
                Analyze the following restaurant reviews and summarize in Thai language only.
                Keep it concise. Use the exact format below.
                Do it without intro and footnote.
                Question back is not allow either.

                Reviews:
                "{text_data}"

                Format:
                **ภาพรวม:** [Summary in 1 sentence, Thai language]
                - **🍛 เมนูแนะนำ:** [List specific food names found in text in Thai language]
                - **⏰ ช่วงเวลาที่ควรไป:** [Time/Meal in Thai language]
                - **🌅 บรรยากาศ:** [Atmosphere in Thai language]
                - **👨‍👩‍👧‍👦 เหมาะสำหรับ:** [Customer type in Thai language]
                """
                
                with st.spinner("🤖 AI กำลังอ่านรีวิว..."):
                    ai_response = db_manager.get_ollama_text_response(user_prompt)
                
                st.markdown(ai_response)
        else:
            st.info("ยังไม่มีข้อมูลรีวิวให้วิเคราะห์")

else:
    st.subheader("🔒 เข้าสู่ระบบ AI Mode เพื่อดูบทวิเคราะห์ร้านอาหารโดยละเอียด")

st.divider()

# --- KEYWORDS ---
st.markdown("##### Keywords: กดคำเพื่อใช้เป็นตัวกรอง")
kw_cols = st.columns(8) 
keywords = [kw.strip() for kw in str(restaurant.get('keywords', '')).split(',') if kw.strip()]

for i, kw in enumerate(keywords):
    if i < 8:
        if kw_cols[i].button(kw, key=f"kw_{i}", use_container_width=True):
            nav.navigate_to("App.py", {"search_query": kw})

st.divider()

# --- GRAPH & INTERACTIVE FILTERS ---
st.subheader("📊 สถิติร้านอาหาร")

c_chart_dist, c_chart_ts = st.columns([1, 2])

if 'chart_filter_rating' not in st.session_state: st.session_state['chart_filter_rating'] = None
if 'chart_filter_month' not in st.session_state: st.session_state['chart_filter_month'] = None

with c_chart_dist:
    st.markdown("##### คะแนนรีวิว (1-5)")
    if not dist_df.empty:
        dist_df = dist_df.sort_values('rating', ascending=False)
        fig = px.bar(dist_df, x='cnt', y='rating', orientation='h', text='cnt')
        fig.update_layout(yaxis=dict(type='category'), xaxis_title=None, clickmode='event+select')
        
        event_dist = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="chart_dist_v4")
        
        if event_dist:
            if len(event_dist.selection['points']) > 0:
                new_rating = event_dist.selection['points'][0]['y']
                if st.session_state['chart_filter_rating'] != new_rating:
                    st.session_state['chart_filter_rating'] = new_rating
                    st.rerun()
            elif st.session_state['chart_filter_rating'] is not None:
                st.session_state['chart_filter_rating'] = None
                st.rerun()
        
        if st.session_state['chart_filter_rating']:
            st.success(f"กำลังกรอง: {st.session_state['chart_filter_rating']} ดาว")
    else:
        st.write("ไม่มีข้อมูล")

with c_chart_ts:
    st.markdown("##### 📈 แนวโน้ม (เลือกจุดเพื่อกรองเดือน)")
    if not ts_df.empty:
        # FIX: Force x-axis to be Category string
        ts_df['month_year_str'] = ts_df['month_year'].astype(str)
        fig2 = px.line(ts_df, x='month_year_str', y='avg_rating', markers=True)
        fig2.update_yaxes(range=[0, 5.5])
        # IMPORTANT: Fix for Line Chart filtering
        fig2.update_xaxes(type='category') 
        fig2.update_layout(clickmode='event+select')
        
        event_ts = st.plotly_chart(fig2, use_container_width=True, on_select="rerun", key="chart_ts_v4")
        
        if event_ts:
            if len(event_ts.selection['points']) > 0:
                new_month = event_ts.selection['points'][0]['x']
                new_month_str = str(new_month)
                if st.session_state['chart_filter_month'] != new_month_str:
                    st.session_state['chart_filter_month'] = new_month_str
                    st.rerun()
            elif st.session_state['chart_filter_month'] is not None:
                st.session_state['chart_filter_month'] = None
                st.rerun()
            
        if st.session_state['chart_filter_month']:
             st.success(f"กำลังกรองเดือน: {st.session_state['chart_filter_month']}")
    else:
        st.write("ไม่มีข้อมูล")

if st.session_state['chart_filter_rating'] or st.session_state['chart_filter_month']:
    if st.button("🔄 ล้างตัวกรองกราฟ"):
        st.session_state['chart_filter_rating'] = None
        st.session_state['chart_filter_month'] = None
        st.rerun()

st.divider()

# --- REVIEWS LIST ---
st.subheader("📝 รีวิวที่ร้านได้รับ")

# 1. Apply Filters
filtered_reviews = reviews.copy()
if st.session_state['chart_filter_rating']:
    filtered_reviews = filtered_reviews[filtered_reviews['rating'] == int(st.session_state['chart_filter_rating'])]
if st.session_state['chart_filter_month']:
    filtered_reviews['ym'] = filtered_reviews['timestamp'].dt.strftime('%Y-%m')
    filtered_reviews = filtered_reviews[filtered_reviews['ym'] == str(st.session_state['chart_filter_month'])]

# 2. Sort
filter_mode = st.radio(
    "เรียงตาม:",
    ["ล่าสุด", "คะแนนมากสุด", "คะแนนน้อยสุด", "คะแนนสวนทาง (Deviation)"],
    horizontal=True,
    key="res_review_sort"
)

if 'prev_filter_mode' not in st.session_state: st.session_state['prev_filter_mode'] = filter_mode
if st.session_state['prev_filter_mode'] != filter_mode:
    st.session_state['show_all_reviews_rest'] = False
    st.session_state['prev_filter_mode'] = filter_mode

avg_rating = restaurant['average_rating']
if filter_mode == "ล่าสุด":
    filtered_reviews = filtered_reviews.sort_values('timestamp', ascending=False)
elif filter_mode == "คะแนนมากสุด":
    filtered_reviews = filtered_reviews.sort_values('rating', ascending=False)
elif filter_mode == "คะแนนน้อยสุด":
    filtered_reviews = filtered_reviews.sort_values('rating', ascending=True)
elif filter_mode == "คะแนนสวนทาง (Deviation)":
    if not filtered_reviews.empty:
        filtered_reviews['dev'] = abs(filtered_reviews['rating'] - avg_rating)
        filtered_reviews = filtered_reviews.sort_values('dev', ascending=False)

# 3. Limit Logic
TOP_N = 4
if 'show_all_reviews_rest' not in st.session_state: st.session_state['show_all_reviews_rest'] = False

total_reviews_count = len(filtered_reviews)
display_reviews = filtered_reviews if st.session_state['show_all_reviews_rest'] else filtered_reviews.head(TOP_N)

# 4. Display
if display_reviews.empty:
    st.info("ไม่พบรีวิวตามเงื่อนไข")
else:
    for _, r in display_reviews.iterrows():
        with st.container(border=True):
            rc1, rc2 = st.columns([4, 1])
            rc1.markdown(f"**🧑‍🍳 {r['reviewer_name']}**")
            rc1.caption(f"{r['timestamp']}")
            rc1.write(r['content'])
            rc2.write("⭐" * int(r['rating']))
            
            # Button Logic
            rev_id_val = r.get('reviewer_id', 0)
            try: rev_id_int = int(rev_id_val)
            except: rev_id_int = 0
                
            if rev_id_int > 0:
                if rc2.button("โปรไฟล์", key=f"go_rev_{r['id']}_{filter_mode}_{rev_id_int}"):
                    nav.navigate_to("pages/3_Reviewer.py", {"id": rev_id_int})

    # Show All / Collapse
    if not st.session_state['show_all_reviews_rest'] and total_reviews_count > TOP_N:
        if st.button(f"⬇️ แสดงทั้งหมด ({total_reviews_count} รีวิว)", use_container_width=True):
            st.session_state['show_all_reviews_rest'] = True
            st.rerun()
    elif st.session_state['show_all_reviews_rest']:
        if st.button("⬆️ ย่อกลับ (แสดง 4 รายการ)", use_container_width=True):
            st.session_state['show_all_reviews_rest'] = False
            st.rerun()

st.divider()

# --- SIMILAR RESTAURANTS ---
st.subheader("🔗 ร้านแนะนำอื่นๆ")
similar_res = db_manager.calculate_similarity_restaurants(res_id, top_n=5) 
cols_row1 = st.columns(3)
cols_row2 = st.columns(3)
all_slots = cols_row1 + cols_row2
count = 0

if not similar_res.empty:
    for _, sim_row in similar_res.head(5).iterrows():
        with all_slots[count]:
            with st.container(border=True):
                st.write(f"**{sim_row['name']}**")
                st.caption(f"Rating: {sim_row['average_rating']:.2f} ⭐")
                if st.button("ดูร้าน", key=f"sim_res_{sim_row['restaurant_id']}", use_container_width=True):
                    nav.navigate_to("pages/2_Restaurant.py", {"id": sim_row['restaurant_id']})
        count += 1

with all_slots[5]:
    with st.container(border=True):
        st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
        st.markdown("### 🔍")
        st.markdown("**ค้นหาร้านโดนใจอื่นๆ**")
        if st.button("ไปหน้าค้นหา", key="search_more", type="primary", use_container_width=True):
            nav.navigate_to("App.py")
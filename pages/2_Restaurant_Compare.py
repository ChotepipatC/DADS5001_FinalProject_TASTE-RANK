#pages/2_Restaurant_Compare.py
import streamlit as st
import pandas as pd
from modules import db_manager, auth, nav

st.set_page_config(page_title="Compare Restaurants", layout="wide")
nav.inject_custom_css()
auth.init_session_state()

# --- HEADER ---
c1, c2 = st.columns([3, 1])
c1.title("⚖️ Restaurant Compare")

# --- AUTH CHECK ---
if not st.session_state['logged_in'] or auth.get_user_mode() != 'AI':
    st.warning("🔒 ฟีเจอร์เปรียบเทียบร้านอาหารสงวนสิทธิ์สำหรับ **AI Mode User** เท่านั้น")
    st.info("กรุณาเข้าสู่ระบบที่หน้าหลัก")
    if st.button("⬅️ กลับหน้าหลัก"):
        nav.navigate_to("App.py")
    st.stop()

with c2:
    if st.button("⬅️ กลับหน้าหลัก"): nav.navigate_to("App.py")

st.markdown("เลือก 2 ร้านอาหารที่คุณสนใจ เพื่อให้ AI ช่วยเปรียบเทียบจุดเด่น-จุดด้อย")

# --- SELECTORS ---
# Fetch all restaurants for dropdown
all_restaurants = db_manager.get_all_restaurants_light()
if all_restaurants.empty:
    st.error("ไม่พบข้อมูลร้านอาหารในระบบ")
    st.stop()

res_options = dict(zip(all_restaurants['id'], all_restaurants['name']))

col_sel1, col_sel2 = st.columns(2)

with col_sel1:
    res_id_1 = st.selectbox("เลือกร้านที่ 1", options=res_options.keys(), format_func=lambda x: res_options[x], index=0)

with col_sel2:
    # Filter options to exclude first selection
    res_2_keys = [k for k in res_options.keys() if k != res_id_1]
    res_id_2 = st.selectbox("เลือกร้านที่ 2", options=res_2_keys, format_func=lambda x: res_options[x], index=0 if res_2_keys else None)

if not res_id_1 or not res_id_2:
    st.info("กรุณาเลือกร้านให้ครบทั้งสองร้าน")
    st.stop()

# --- DATA FETCHING & AI PROCESSING ---
def get_ai_analysis_for_restaurant(rid, rname):
    """
    Reuse the exact logic/prompt from Page 2 to hit the cache.
    """
    reviews = db_manager.get_reviews_for_restaurant(rid)
    if not reviews.empty and 'content' in reviews.columns:
        valid_reviews = reviews[reviews['content'].astype(str).str.len() > 5]
        text_data = " ".join(valid_reviews['content'].astype(str).tolist())
        
        # Use exact logic as page 2 to ensure cache hit
        if len(text_data) > 10000: text_data = text_data[:10000] + "..."
        if len(text_data) < 10: return None
        
        # SAME PROMPT AS PAGE 2
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
        return db_manager.get_ollama_text_response(user_prompt)
    return None

def parse_ai_response(text):
    """Parse the specific AI format into a dictionary."""
    data = {
        "Overview": "-", "Menu": "-", "Time": "-", "Ambient": "-", "Group": "-"
    }
    if not text: return data
    
    try:
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if "**ภาพรวม:**" in line:
                data['Overview'] = line.split(":", 1)[1].strip()
            elif "เมนูแนะนำ:" in line:
                data['Menu'] = line.split(":", 1)[1].strip()
            elif "ช่วงเวลาที่ควรไป:" in line:
                data['Time'] = line.split(":", 1)[1].strip()
            elif "บรรยากาศ:" in line:
                data['Ambient'] = line.split(":", 1)[1].strip()
            elif "เหมาะสำหรับ:" in line:
                data['Group'] = line.split(":", 1)[1].strip()
    except:
        pass # Fallback to default
    return data

# Action
if st.button("🚀 เริ่มเปรียบเทียบ", type="primary", use_container_width=True):
    
    # 1. Basic Stats
    r1 = db_manager.get_restaurant_detail(res_id_1)
    r2 = db_manager.get_restaurant_detail(res_id_2)
    
    # 2. AI Analysis (Hit Cache if visited page 2 before, or Gen new)
    with st.spinner("🤖 AI กำลังรวบรวมข้อมูล..."):
        raw_ai_1 = get_ai_analysis_for_restaurant(res_id_1, r1['name'])
        raw_ai_2 = get_ai_analysis_for_restaurant(res_id_2, r2['name'])
        
    ai_data_1 = parse_ai_response(raw_ai_1)
    ai_data_2 = parse_ai_response(raw_ai_2)

    # 3. Construct Table Data
    table_data = [
        {"หัวข้อ": "จำนวนรีวิว", r1['name']: f"{r1['review_count']} 📝", r2['name']: f"{r2['review_count']} 📝"},
        {"หัวข้อ": "คะแนนเฉลี่ย", r1['name']: f"{r1['average_rating']:.2f} ⭐", r2['name']: f"{r2['average_rating']:.2f} ⭐"},
        {"หัวข้อ": "ภาพรวม", r1['name']: ai_data_1['Overview'], r2['name']: ai_data_2['Overview']},
        {"หัวข้อ": "🍛 เมนูแนะนำ", r1['name']: ai_data_1['Menu'], r2['name']: ai_data_2['Menu']},
        {"หัวข้อ": "⏰ ช่วงเวลาที่ควรไป", r1['name']: ai_data_1['Time'], r2['name']: ai_data_2['Time']},
        {"หัวข้อ": "🌅 บรรยากาศ", r1['name']: ai_data_1['Ambient'], r2['name']: ai_data_2['Ambient']},
        {"หัวข้อ": "👨‍👩‍👧‍👦 เหมาะสำหรับ", r1['name']: ai_data_1['Group'], r2['name']: ai_data_2['Group']},
    ]
    
    df_compare = pd.DataFrame(table_data)
    
    st.subheader("📊 ตารางเปรียบเทียบ")
    st.table(df_compare)
    
    # 4. Final Comparison Summary
    st.subheader("💡 บทสรุปการเปรียบเทียบ")
    
    summary_prompt = f"""
    Compare these two restaurants based on the data below and give a recommendation in Thai.
    
    Restaurant A ({r1['name']}): {r1['average_rating']} Stars. {ai_data_1}
    Restaurant B ({r2['name']}): {r2['average_rating']} Stars. {ai_data_2}
    
    Output Format:
    **ความเหมือน:** ...
    **ความต่าง:** ...
    **คำแนะนำ:** เลือกร้าน A ถ้า... / เลือกร้าน B ถ้า...
    """
    
    with st.spinner("⚖️ AI กำลังสรุปผลการตัดสิน..."):
        final_verdict = db_manager.get_ollama_text_response(summary_prompt)
        st.info(final_verdict)
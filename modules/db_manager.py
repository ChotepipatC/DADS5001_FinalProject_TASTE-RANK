#modules/db_manager.py
import streamlit as st
import duckdb
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import numpy as np
from datetime import datetime
import io
# Ensure ollama is installed: pip install ollama
try:
    from ollama import chat, ChatResponse
except ImportError:
    chat = None
    ChatResponse = None

# --- CONFIG ---
SERVICE_ACCOUNT_FILE = 'service_account.json'
SHEET_NAME = 'Restaurant_DB'

# --- CONNECTION ---
def connect_gsheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
        client = gspread.authorize(creds)
        return client.open(SHEET_NAME)
    except: 
        return None

# --- CACHING & LOADING ---
@st.cache_data(ttl=600, show_spinner=False)
def load_data():
    sh = connect_gsheet()
    data = {}
    sheets = ['restaurants', 'reviews', 'reviewers', 'users']
    
    if sh:
        for s in sheets:
            try:
                if s == 'users':
                    records = sh.worksheet(s).get_all_records(numericise_ignore=[5])
                else:
                    records = sh.worksheet(s).get_all_records()
                data[s] = pd.DataFrame(records)
            except:
                data[s] = pd.DataFrame()
    else:
        for s in sheets:
            data[s] = pd.DataFrame()
            
    # Type Casting
    if not data['restaurants'].empty:
        for col in ['id', 'review_count']:
            data['restaurants'][col] = pd.to_numeric(data['restaurants'][col], errors='coerce').fillna(0).astype(int)
        data['restaurants']['average_rating'] = pd.to_numeric(data['restaurants']['average_rating'], errors='coerce').fillna(0.0)
        if 'keywords' in data['restaurants'].columns:
            data['restaurants']['keywords'] = data['restaurants']['keywords'].astype(str)

    if not data['reviews'].empty:
        for col in ['restaurant_id', 'rating']:
            data['reviews'][col] = pd.to_numeric(data['reviews'][col], errors='coerce').fillna(0).astype(int)
        data['reviews']['timestamp'] = pd.to_datetime(data['reviews']['timestamp'], errors='coerce')
        if 'reviewer_id' in data['reviews'].columns:
             data['reviews']['reviewer_id'] = pd.to_numeric(data['reviews']['reviewer_id'], errors='coerce').fillna(0).astype(int)

    if not data['reviewers'].empty:
        for col in ['reviewer_id', 'total_reviews', 'followers']:
            data['reviewers'][col] = pd.to_numeric(data['reviewers'][col], errors='coerce').fillna(0).astype(int)

    return data

def get_db():
    data = load_data()
    con = duckdb.connect(database=':memory:')
    if data:
        for name, df in data.items():
            con.register(name, df)
    return con

def trigger_refresh():
    load_data.clear()

# --- WRITE OPERATIONS ---
def update_reviewer_follower_count(reviewer_id: int, increment: bool = True):
    try:
        sh = connect_gsheet()
        if not sh: return False
        ws = sh.worksheet('reviewers')
        cell = ws.find(str(reviewer_id), in_column=1) 
        if cell:
            row = cell.row
            cur_val = int(ws.cell(row, 4).value)
            new_val = cur_val + 1 if increment else max(0, cur_val - 1)
            ws.update_cell(row, 4, new_val)
            trigger_refresh()
            return True
    except Exception as e:
        st.error(f"Error updating follower count: {e}")
    return False

def update_user_followed_list(user_id: int, followed_ids_list: list):
    try:
        sh = connect_gsheet()
        if not sh: return False
        ws_users = sh.worksheet('users')
        cell = ws_users.find(str(user_id), in_column=1)
        if cell:
            # FIX: Prepend apostrophe (') to force Google Sheets to treat this as Text
            # This prevents "1,2" from being interpreted as a number or date
            val_str = "'" + ",".join(map(str, followed_ids_list))
            
            # Use value_input_option='USER_ENTERED' to ensure the apostrophe works correctly
            ws_users.update_cell(cell.row, 5, val_str) 
            trigger_refresh()
            return True
    except Exception as e: 
        st.error(f"Error updating user follow list: {e}")
        return False

# --- READ OPERATIONS ---

def search_restaurants_advanced(query, min_rating, min_reviews, sort_by):
    con = get_db()
    sql = f"SELECT * FROM restaurants WHERE average_rating >= {min_rating} AND review_count >= {min_reviews}"
    params = []
    
    if query:
        sql += " AND (LOWER(name) LIKE ? OR LOWER(keywords) LIKE ?)"
        q = f"%{query.lower()}%"
        params = [q, q]
    
    if sort_by == 'รีวิวมาก -> น้อย':
        sql += " ORDER BY review_count DESC"
    elif sort_by == 'รีวิวน้อย -> มาก':
        sql += " ORDER BY review_count ASC"
    elif sort_by == 'Rating สูง -> ต่ำ':
        sql += " ORDER BY average_rating DESC"
    elif sort_by == 'Rating ต่ำ -> สูง':
        sql += " ORDER BY average_rating ASC"
    
    try:
        return con.execute(sql, params).df()
    except Exception as e: 
        return pd.DataFrame()

def search_reviewers_advanced(query, min_reviews, min_followers, has_revisit, sort_by):
    con = get_db()
    sql = """
    SELECT r.*, 
           (SELECT COUNT(DISTINCT restaurant_id) FROM reviews WHERE reviewer_name = r.name) as distinct_shops_visited
    FROM reviewers r 
    WHERE 1=1
    """
    params = []
    
    if query:
        sql += " AND (LOWER(name) LIKE ?)"
        q = f"%{query.lower()}%"
        params.append(q)
        
    if min_reviews > 0:
        sql += f" AND total_reviews >= {min_reviews}"
        
    if min_followers > 0:
        sql += f" AND followers >= {min_followers}"
        
    if has_revisit:
        revisit_sql = """
        SELECT DISTINCT reviewer_name 
        FROM reviews 
        GROUP BY reviewer_name, restaurant_id 
        HAVING COUNT(*) > 1
        """
        sql += f" AND name IN ({revisit_sql})"

    if sort_by == 'จำนวนรีวิว':
        sql += " ORDER BY total_reviews DESC"
    elif sort_by == 'จำนวนร้านที่รีวิว':
        sql += " ORDER BY distinct_shops_visited DESC"
    elif sort_by == 'จำนวนผู้ติดตาม':
        sql += " ORDER BY followers DESC"
    else:
        sql += " ORDER BY followers DESC"

    try:
        return con.execute(sql, params).df()
    except Exception as e: 
        return pd.DataFrame()

def get_revisited_restaurants(reviewer_name):
    con = get_db()
    try:
        query = """
        SELECT restaurant_id, COUNT(*) as visit_count, MAX(timestamp) as last_visit
        FROM reviews
        WHERE reviewer_name = ?
        GROUP BY restaurant_id
        HAVING visit_count > 1
        ORDER BY visit_count DESC
        """
        df = con.execute(query, [reviewer_name]).df()
        if not df.empty:
            rest_ids = tuple(df['restaurant_id'].tolist())
            if not rest_ids: return pd.DataFrame()
            rest_ids_str = f"({rest_ids[0]})" if len(rest_ids) == 1 else str(rest_ids)
            res_info = con.execute(f"SELECT id, name, average_rating FROM restaurants WHERE id IN {rest_ids_str}").df()
            return df.merge(res_info, left_on='restaurant_id', right_on='id', how='left')
        return pd.DataFrame()
    except: 
        return pd.DataFrame()

def get_restaurant_reviews_stats(res_id):
    con = get_db()
    try:
        # Distribution
        dist_query = "SELECT rating, COUNT(*) as cnt FROM reviews WHERE restaurant_id = ? GROUP BY rating ORDER BY rating DESC"
        dist_df = con.execute(dist_query, [res_id]).df()
        
        # Monthly Avg
        ts_query = """
            SELECT strftime('%Y-%m', timestamp) as month_year, AVG(rating) as avg_rating
            FROM reviews WHERE restaurant_id = ? AND timestamp IS NOT NULL
            GROUP BY month_year ORDER BY month_year
        """
        ts_df = con.execute(ts_query, [res_id]).df()
        return dist_df, ts_df
    except: 
        return pd.DataFrame(), pd.DataFrame()

def get_restaurant_detail(rid): 
    try: return get_db().execute("SELECT * FROM restaurants WHERE id=?", [rid]).df().iloc[0].to_dict()
    except: return None
    
def get_reviewer_detail(rid): 
    try: return get_db().execute("SELECT * FROM reviewers WHERE reviewer_id=?", [rid]).df().iloc[0].to_dict()
    except: return None
    
def get_reviews_for_restaurant(rid): 
    try: 
        query = """
        SELECT r.*, rev.reviewer_id 
        FROM reviews r
        LEFT JOIN reviewers rev ON r.reviewer_name = rev.name
        WHERE r.restaurant_id=? 
        ORDER BY r.timestamp DESC
        """
        return get_db().execute(query, [rid]).df()
    except Exception as e: 
        return pd.DataFrame()

def get_reviews_by_reviewer_name(reviewer_name): 
    try: 
        query = "SELECT r.*, res.name as restaurant_name FROM reviews r JOIN restaurants res ON r.restaurant_id = res.id WHERE r.reviewer_name = ? ORDER BY r.timestamp DESC"
        return get_db().execute(query, [reviewer_name]).df()
    except: return pd.DataFrame()
    
def get_average_rating_given(reviewer_name): 
    try: 
        avg = get_db().execute("SELECT AVG(rating) FROM reviews WHERE reviewer_name=?", [reviewer_name]).fetchone()[0]
        return avg if avg is not None else 0.0
    except: return 0.0

def get_all_restaurants_light():
    """Get just ID and Name for Dropdowns."""
    try:
        return get_db().execute("SELECT id, name FROM restaurants ORDER BY name").df()
    except:
        return pd.DataFrame()

# --- SIMILARITY ---
def calculate_similarity_restaurants(target_res_id, top_n=5):
    con = get_db()
    try:
        all_res = con.execute("SELECT id, name, average_rating, keywords FROM restaurants WHERE id != ?", [target_res_id]).df()
        if all_res.empty: return pd.DataFrame()
        all_res['similarity'] = all_res['average_rating'] / 5.0 + np.random.rand(len(all_res)) * 0.1
        all_res = all_res.sort_values('similarity', ascending=False).head(top_n)
        return all_res.rename(columns={'id': 'restaurant_id'})
    except: return pd.DataFrame()

def get_similar_reviewers_content_based(target_rev_id, top_n=5):
    con = get_db()
    try:
        t_name = con.execute("SELECT name FROM reviewers WHERE reviewer_id = ?", [target_rev_id]).fetchone()
        if not t_name: return pd.DataFrame()
        target_name = t_name[0]
        
        query = """
        WITH TargetVisits AS (SELECT restaurant_id FROM reviews WHERE reviewer_name = ?),
        Overlap AS (
            SELECT r.reviewer_id, r.name, COUNT(*) as common_restaurants, r.followers
            FROM reviewers r
            JOIN reviews rv ON r.name = rv.reviewer_name
            JOIN TargetVisits t ON rv.restaurant_id = t.restaurant_id
            WHERE r.reviewer_id != ?
            GROUP BY r.reviewer_id, r.name, r.followers
        )
        SELECT * FROM Overlap ORDER BY common_restaurants DESC, followers DESC LIMIT ?
        """
        return con.execute(query, [target_name, target_rev_id, top_n]).df()
    except: return pd.DataFrame()

# --- OLLAMA INTEGRATION ---
@st.cache_data(show_spinner=False, ttl=3600)
def get_ollama_text_response(user_prompt, system_prompt=""):
    """
    Calls Ollama local API with caching.
    """
    if chat is None:
        return "Error: Ollama library not installed."
        
    try:
        options = {
            'temperature': 0.1,
            'top_p': 0.5,
            'repeat_penalty': 1.2,
            'num_ctx': 4096
        }

        response: ChatResponse = chat(
            model='gemma3:1b', 
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            options=options
        )
        
        if response and response.message:
            return response.message.content
        return "No response from AI."
    except Exception as e:
        return f"AI Error: {str(e)}."
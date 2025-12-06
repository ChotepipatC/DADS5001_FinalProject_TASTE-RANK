import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import numpy as np
import re
from collections import Counter
import string
import nltk
from nltk.corpus import stopwords

# --- 1. SETUP & CONFIG ---
SERVICE_ACCOUNT_FILE = 'service_account.json'
SHEET_NAME = 'Restaurant_DB' # ชื่อ Google Sheet ปลายทาง
CSV_FILE = 'data/source_reviews.csv'

# Download NLTK data for keyword extraction (run once)
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

def connect_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME)

def clean_keywords(text_series):
    """
    Smarter Keyword Extraction:
    Extracts top 10 most frequent meaningful words (nouns/adjectives) 
    from all reviews of a single restaurant.
    """
    # Combine all reviews
    full_text = " ".join(text_series.astype(str).tolist()).lower()
    
    # Remove punctuation
    full_text = full_text.translate(str.maketrans('', '', string.punctuation))
    
    # Tokenize and remove stopwords
    tokens = full_text.split()
    stop_words = set(stopwords.words('english'))
    # Add custom stopwords common in reviews but not descriptive
    custom_stops = {'good', 'great', 'place', 'food', 'service', 'restaurant', 'visit', 'really', 'also', 'nice', 'one', 'get', 'ordered', 'went'}
    stop_words.update(custom_stops)
    
    filtered_tokens = [w for w in tokens if w not in stop_words and len(w) > 3]
    
    # Count frequency
    counter = Counter(filtered_tokens)
    
    # Get top 10 most common words (representing Menu, Ambience, etc.)
    most_common = [word.capitalize() for word, count in counter.most_common(10)]
    
    return ", ".join(most_common)

def main():
    print("📂 Reading CSV...")
    df = pd.read_csv(CSV_FILE)
    
    # --- 2. PREPARE REVIEWS DATA (Base) ---
    print("🧹 Processing Reviews & Timestamp...")
    # 2.1 Fix Timestamp Format (YYYY-MM-DD HH:MM:SS)
    df['Time'] = pd.to_datetime(df['Time'], errors='coerce')
    # Convert to string format compatible with Google Sheets
    df['Time'] = df['Time'].dt.strftime('%Y-%m-%d %H:%M:%S')

    # --- 3. PREPARE RESTAURANTS DATA ---
    print("🏢 Processing Restaurants & Keywords...")
    # Group by restaurant name
    restaurant_groups = df.groupby('Restaurant')
    
    restaurants_data = []
    
    # Create a mapping for Restaurant ID
    res_id_map = {name: i+1 for i, name in enumerate(restaurant_groups.groups.keys())}
    
    for i, (name, group) in enumerate(restaurant_groups):
        res_id = i + 1
        
        # 1.1 Extract Keywords from actual reviews
        keywords = clean_keywords(group['Review'])
        
        # Metadata (Take the first one found, usually generic)
        metadata = group['Metadata'].iloc[0] if 'Metadata' in group.columns else ""
        
        # 1.2 Inject Formulas for Dynamic Updates
        # Assuming in 'reviews' sheet: Col B = restaurant_id, Col D = rating
        # Row index in sheet starts at 2 (Header is 1). So ID 1 is at Row 2.
        # Formula: =AVERAGEIF(reviews!B:B, res_id, reviews!D:D)
        
        # We store the FORMULA string. gspread 'USER_ENTERED' mode will evaluate it.
        # Note: We use INDIRECT or just the ID value. Since ID matches Row-1 roughly, 
        # but to be safe, we hardcode the ID in the formula condition.
        avg_rating_formula = f'=IFERROR(AVERAGEIF(reviews!B:B, {res_id}, reviews!D:D), 0)'
        review_count_formula = f'=COUNTIF(reviews!B:B, {res_id})'
        
        restaurants_data.append([
            res_id,                 # id
            name,                   # name
            avg_rating_formula,     # average_rating (Formula)
            review_count_formula,   # review_count (Formula)
            keywords,               # keywords (Extracted)
            metadata                # metadata
        ])
        
    df_restaurants = pd.DataFrame(restaurants_data, columns=['id', 'name', 'average_rating', 'review_count', 'keywords', 'metadata'])

    # --- 4. PREPARE REVIEWERS DATA ---
    print("🧑‍🍳 Processing Reviewers & Formulas...")
    # Extract Reviewer Info
    # Check if 'Reviewer' column exists
    if 'Reviewer' in df.columns:
        # Group by Reviewer Name to handle duplicates
        reviewer_groups = df.groupby('Reviewer')
        
        reviewers_data = []
        reviewer_id_map = {} # Map Name -> ID
        
        for i, (name, group) in enumerate(reviewer_groups):
            rev_id = i + 1
            reviewer_id_map[name] = rev_id
            
            # Extract followers from Metadata string (e.g., "1 Review , 5 Followers")
            meta = str(group['Metadata'].iloc[0])
            followers = 0
            if 'Followers' in meta:
                try:
                    parts = meta.split(',')
                    for p in parts:
                        if 'Follower' in p:
                            followers = int(re.search(r'\d+', p).group())
                except:
                    followers = 0
            
            # 3.1 Formula for Total Reviews
            # Assuming in 'reviews' sheet: Col H = reviewer_id (We will add this column)
            total_reviews_formula = f'=COUNTIF(reviews!H:H, {rev_id})'
            
            reviewers_data.append([
                rev_id,                 # reviewer_id
                name,                   # name
                total_reviews_formula,  # total_reviews (Formula)
                followers               # followers
            ])
            
        df_reviewers = pd.DataFrame(reviewers_data, columns=['reviewer_id', 'name', 'total_reviews', 'followers'])
    else:
        print("Warning: No 'Reviewer' column found.")
        df_reviewers = pd.DataFrame(columns=['reviewer_id', 'name', 'total_reviews', 'followers'])

    # --- 5. FINALIZE REVIEWS TABLE ---
    print("📝 Finalizing Reviews Table...")
    # Map IDs back to main DF
    df['restaurant_id'] = df['Restaurant'].map(res_id_map)
    df['reviewer_id'] = df['Reviewer'].map(reviewer_id_map)
    
    # Rename and Select Columns for 'reviews' sheet
    # Structure: id, restaurant_id, reviewer_name, rating, content, timestamp, pictures, reviewer_id
    df_reviews_upload = pd.DataFrame()
    df_reviews_upload['id'] = range(1, len(df) + 1)
    df_reviews_upload['restaurant_id'] = df['restaurant_id']
    df_reviews_upload['reviewer_name'] = df['Reviewer']
    df_reviews_upload['rating'] = df['Rating']
    df_reviews_upload['content'] = df['Review']
    df_reviews_upload['timestamp'] = df['Time']
    df_reviews_upload['pictures'] = df['Pictures'].fillna(0)
    df_reviews_upload['reviewer_id'] = df['reviewer_id'] # Col H

    # --- 6. UPLOAD TO GOOGLE SHEETS ---
    print("☁️ Uploading to Google Sheets...")
    sh = connect_gsheet()

    # Function to clear and update sheet with USER_ENTERED option (for formulas)
    def upload_df(worksheet_name, dataframe):
        ws = sh.worksheet(worksheet_name)
        ws.clear()
        # Upload Header
        ws.update([dataframe.columns.values.tolist()], 'A1')
        # Upload Values (using value_input_option='USER_ENTERED' to parse formulas)
        if not dataframe.empty:
            data = dataframe.values.tolist()
            # gspread update using range
            ws.update('A2', data, value_input_option='USER_ENTERED')
        print(f"   ✅ Uploaded {len(dataframe)} rows to '{worksheet_name}'")

    upload_df('restaurants', df_restaurants)
    upload_df('reviewers', df_reviewers)
    upload_df('reviews', df_reviews_upload)
    
    # --- 7. USERS SHEET (FIX 4.1) ---
    print("👤 Creating Default Users...")
    ws_users = sh.worksheet('users')
    ws_users.clear()
    ws_users.append_row(['id', 'username', 'email', 'password_hash', 'followed_reviewers'])
    
    # 4.1 Fix: Ensure followed_reviewers is treated as string even with multiple IDs
    # We prepend a ' (apostrophe) is one way, but just passing a string "1,2" usually works in gspread
    # if it doesn't get auto-formatted to date/number.
    # Safe bet: Use string "1,2" (comma separated).
    
    # Mock Admin User
    ws_users.append_row([1, 'admin', 'admin@example.com', '$2b$12$EXAMPLEHASH...', '']) 
    
    # Mock User with multiple follows (Test Case)
    # Using '1, 2' as a string explicitly
    ws_users.append_row([2, 'demo_user', 'demo@test.com', 'pass123', '1,3,5']) 

    print("🎉 Data Seeding Completed!")

if __name__ == "__main__":
    main()
    
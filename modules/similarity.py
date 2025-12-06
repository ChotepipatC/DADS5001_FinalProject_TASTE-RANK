# modules/similarity.py
import streamlit as st
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import Tuple, List
from modules import db_manager

@st.cache_data
def _load_reviews_table() -> pd.DataFrame:
    con = db_manager.get_db()
    df = con.execute("SELECT * FROM reviews").df()
    # normalize rating to numeric
    if 'rating' in df.columns:
        df['rating'] = pd.to_numeric(df['rating'], errors='coerce').astype('Int64')
    return df

@st.cache_data
def _load_restaurants_table() -> pd.DataFrame:
    con = db_manager.get_db()
    df = con.execute("SELECT * FROM restaurants").df()
    return df

@st.cache_data
def _load_reviewers_table() -> pd.DataFrame:
    con = db_manager.get_db()
    df = con.execute("SELECT * FROM reviewers").df()
    return df

@st.cache_data
def build_restaurant_vectors() -> Tuple[pd.DataFrame, np.ndarray, List[str]]:
    """
    Build vectors for restaurants: concat [rating_counts_5..1] + tfidf(reviewer_ids)
    Returns: restaurants_df (index by restaurant_id), vectors (n x d), restaurant_ids list
    """
    reviews = _load_reviews_table()
    restaurants = _load_restaurants_table()

    # ensure id column names match: try 'id' or 'restaurant_id'
    rest_id_col = 'id' if 'id' in restaurants.columns else 'restaurant_id'
    restaurants = restaurants.copy()
    restaurants['__rid'] = restaurants[rest_id_col].astype(str)

    # Rating counts per restaurant (5->1)
    rating_counts = reviews.groupby(['restaurant_id', 'rating']).size().unstack(fill_value=0)
    # ensure columns 1..5 exist
    for r in [1,2,3,4,5]:
        if r not in rating_counts.columns:
            rating_counts[r] = 0
    # order as [5,4,3,2,1]
    rating_vec = rating_counts[[5,4,3,2,1]].reindex(restaurants[rest_id_col].values, fill_value=0).fillna(0).astype(int).to_numpy()

    # Build reviewer-list-as-string per restaurant for TF-IDF tokenization
    # convert reviewer_id to string tokens
    rev_tokens = reviews.groupby('restaurant_id')['reviewer_name'].apply(lambda s: " ".join([str(x).replace(" ", "_") for x in s.tolist()]))
    # align to restaurant order
    docs = []
    for rid in restaurants[rest_id_col].values:
        docs.append(rev_tokens.get(rid, ""))

    # TF-IDF on reviewer tokens
    vect = TfidfVectorizer(token_pattern=r"(?u)\S+")
    if len(docs) == 0 or all([d == "" for d in docs]):
        tfidf_mat = np.zeros((len(docs),1))
    else:
        tfidf_mat = vect.fit_transform(docs).toarray()

    # Concatenate rating_vec and tfidf_mat
    vectors = np.hstack([rating_vec, tfidf_mat]) if tfidf_mat.size else rating_vec

    # return restaurants df keyed and ids list
    return restaurants.set_index(rest_id_col), vectors, restaurants[rest_id_col].astype(int).tolist()

@st.cache_data
def build_reviewer_vectors() -> Tuple[pd.DataFrame, np.ndarray, List[str]]:
    """
    Build reviewer vectors: rating distribution (5..1) + TF-IDF of restaurants they reviewed
    Returns: reviewers_df (index by reviewer_id), vectors, reviewer_ids
    """
    reviews = _load_reviews_table()
    reviewers = _load_reviewers_table()

    rev_id_col = 'reviewer_id' if 'reviewer_id' in reviewers.columns else 'id'
    reviewers = reviewers.copy()
    reviewers['__rid'] = reviewers[rev_id_col].astype(str)

    # rating counts per reviewer
    rating_counts = reviews.groupby(['reviewer_name','rating']).size().unstack(fill_value=0)
    # find mapping from reviewer_name to id
    # We'll use reviewer_name from reviewers table (assume name column exists)
    # Build docs: for each reviewer, list restaurant ids or names as tokens
    # Build list of unique reviewer names in same order as reviewers table
    reviewer_names = reviewers['name'].astype(str).tolist()
    docs = []
    rating_vecs = []
    for name in reviewer_names:
        sub = reviews[reviews['reviewer_name'] == name]
        # rating counts 5..1
        counts = []
        for r in [5,4,3,2,1]:
            counts.append(int(sub[sub['rating'] == r].shape[0]))
        rating_vecs.append(counts)
        docs.append(" ".join([str(x).replace(" ", "_") for x in sub['restaurant_id'].astype(str).tolist()]))

    rating_vec_array = np.array(rating_vecs)

    vect = TfidfVectorizer(token_pattern=r"(?u)\S+")
    if len(docs) == 0 or all([d == "" for d in docs]):
        tfidf_mat = np.zeros((len(docs),1))
    else:
        tfidf_mat = vect.fit_transform(docs).toarray()

    vectors = np.hstack([rating_vec_array, tfidf_mat]) if tfidf_mat.size else rating_vec_array

    return reviewers.set_index(rev_id_col), vectors, reviewers[rev_id_col].astype(int).tolist()

def get_similar_restaurants(restaurant_id: int, top_n: int = 5) -> pd.DataFrame:
    restaurants_df, vectors, ids = build_restaurant_vectors()
    if restaurant_id not in ids:
        return pd.DataFrame()

    idx = ids.index(restaurant_id)
    sims = cosine_similarity(vectors[idx:idx+1], vectors)[0]
    # build result excluding itself
    df = pd.DataFrame({'restaurant_id': ids, 'similarity': sims})
    df = df[df['restaurant_id'] != restaurant_id].sort_values('similarity', ascending=False).head(top_n)
    # join with restaurants_df metadata
    res = df.merge(restaurants_df.reset_index(), on='restaurant_id', how='left')
    return res

def get_similar_reviewers(reviewer_id: int, top_n: int = 5) -> pd.DataFrame:
    reviewers_df, vectors, ids = build_reviewer_vectors()
    if reviewer_id not in ids:
        return pd.DataFrame()

    idx = ids.index(reviewer_id)
    sims = cosine_similarity(vectors[idx:idx+1], vectors)[0]
    df = pd.DataFrame({'reviewer_id': ids, 'similarity': sims})
    df = df[df['reviewer_id'] != reviewer_id].sort_values('similarity', ascending=False).head(top_n)
    res = df.merge(reviewers_df.reset_index(), on='reviewer_id', how='left')
    return res

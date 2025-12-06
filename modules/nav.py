#modules/nav.py
import streamlit as st
import time

def inject_custom_css():
    """Inject CSS and Aggressive Scroll Script"""
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;500;700&display=swap');
        html, body, [class*="css"]  { font-family: 'Kanit', sans-serif !important; }
        div[data-testid="stContainer"] { border-radius: 12px; padding: 1rem; }
        div[data-testid="stMetricValue"] { font-weight: 700; color: #FF5A5F; }
        .stButton button { border-radius: 8px; transition: all 0.2s; }
        div[data-testid="stSlider"] label { font-size: 14px; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)
    
    # FIX 1.4: Aggressive Scroll To Top
    # Injects JavaScript that runs on every render to force scroll to top
    js = """
    <script>
        function scrollToTop() {
            var main = window.parent.document.querySelector(".main");
            if (main) { main.scrollTop = 0; }
            window.scrollTo(0, 0);
        }
        // Run immediately
        scrollToTop();
        // Run after a slight delay to handle dynamic content loading
        setTimeout(scrollToTop, 100);
    </script>
    """
    st.components.v1.html(js, height=0, width=0)

def navigate_to(page: str, params: dict = None):
    """
    Standard procedural navigation. 
    """
    if params:
        for k, v in params.items():
            st.session_state[k] = v
            st.query_params[k] = str(v)
            
    # Reset display states
    if 'show_all_reviews_rest' in st.session_state:
        st.session_state['show_all_reviews_rest'] = False
    if 'show_all_reviews_rev' in st.session_state:
        st.session_state['show_all_reviews_rev'] = False
            
    time.sleep(0.01)
    st.switch_page(page)

def get_param(key, default=None, type_cast=None):
    val = st.query_params.get(key)
    if val is None:
        val = st.session_state.get(key)
    if val is None:
        return default
    if type_cast:
        try: return type_cast(val)
        except: return default
    return val
import sys
import asyncio
import pandas as pd
import streamlit as st
import os
import time
import altair as alt
from database import Database  

st.set_page_config(page_title="Scrap & Analytics", layout="wide", page_icon="📊")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CRED_PATH = os.path.join(BASE_DIR, "serviceAccountKey.json")

# Initialize Database Class
try:
    if not os.path.exists(CRED_PATH):
        st.error(f"❌ Missing File: {CRED_PATH}")
        st.stop()
    db_helper = Database(CRED_PATH)
except Exception as e:
    st.error(f"❌ Database Connection Error: {e}")
    st.stop()

try:
    from daraz_playwright import scrape_daraz
    from amazon_playwright import scrape_amazon
except ImportError as e:
    st.error(f"❌ Import Error: {e}")
    st.info("Ensure 'daraz_playwright.py' and 'amazon_playwright.py' are in the same folder and have no syntax errors.")
    st.stop()

# Import analytics (Optional - we can keep this soft)
try:
    from price_analytics import show_price_trend
except ImportError:
    st.warning("⚠️ 'price_analytics.py' not found. Trend charts will be disabled.")
    # Create a dummy function so code below doesn't crash
    def show_price_trend(df, db): st.write("Analytics module missing.")

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# CSS STYLING ---
st.markdown("""
    <style>
        div[data-testid="stStatusWidget"] { visibility: hidden; }
        .block-container { max-width: 1200px; padding-top: 2rem; }
        .kpi-card {
            background-color: white; padding: 15px; border-radius: 10px;
            border-left: 5px solid #4B4B4B; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            text-align: center; margin-bottom: 10px;
        }
        .kpi-title { font-size: 12px; color: #888; text-transform: uppercase; font-weight: 600; }
        .kpi-value { font-size: 24px; font-weight: 700; color: #333; margin-top: 5px; }
        .kpi-green { border-left-color: #28a745; }
        .kpi-blue { border-left-color: #17a2b8; }
        .kpi-purple { border-left-color: #6f42c1; }
        .kpi-orange { border-left-color: #fd7e14; }
        .kpi-red { border-left-color: #dc3545; }
        .scatter-insight {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
            border-left: 4px solid #4B4B4B;
        }
    </style>
""", unsafe_allow_html=True)

# HELPER FUNCTIONS ---

import pandas as pd
import re

def normalize_words(text):
    """
    Normalize text into comparable keywords:
    - lowercase
    - remove special characters
    - handle singular/plural forms
    """
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    words = text.split()

    normalized = set()
    for word in words:
        normalized.add(word)

        # simple plural handling
        if word.endswith("s") and len(word) > 3:
            normalized.add(word[:-1])      # chairs -> chair
        else:
            normalized.add(word + "s")     # chair -> chairs

    return normalized


def search_db_smart(query):
    """
    Smart Firestore search with singular/plural handling.
    Returns results as a Pandas DataFrame.
    """
    try:
        if not query or not query.strip():
            return pd.DataFrame()

        query_words = normalize_words(query)

        docs = db_helper.collection.stream()
        results = []

        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id  # preserve Firestore ID

            title = data.get("title", "")
            if not title:
                continue

            title_words = normalize_words(title)

            # ALL query keywords must exist in title (singular/plural safe)
            if query_words.issubset(title_words):
                results.append(data)

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)

        # Sort by latest timestamp
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.sort_values("timestamp", ascending=False)

        return df.reset_index(drop=True)

    except Exception as e:
        print("Search Error:", e)
        return pd.DataFrame()


def clean_price(price_input):
    """Converts price to float."""
    if isinstance(price_input, (int, float)): return float(price_input)
    if not isinstance(price_input, str): return 0.0
    
    clean_str = price_input.replace(",", "").replace("Rs.", "").replace("PKR", "").replace("$", "").strip()
    import re
    match = re.search(r"(\d+(\.\d+)?)", clean_str)
    return float(match.group(1)) if match else 0.0

def clean_rating(rating_input):
    """Converts rating to float 0-5."""
    try:
        if pd.isna(rating_input) or str(rating_input) == "None": return 0.0
        import re
        match = re.search(r"(\d+(\.\d+)?)", str(rating_input))
        if match:
            val = float(match.group(1))
            return val if 0 <= val <= 5 else 0.0
    except: pass
    return 0.0

def calculate_value_score(rating, price):
    """Calculate value score (rating per price unit)."""
    if price > 0:
        return (rating * 10) / price  # Scale rating by 10 for better visibility
    return 0

# SESSION STATE INIT ---
if 'data' not in st.session_state: st.session_state.data = pd.DataFrame()
if 'search_term' not in st.session_state: st.session_state.search_term = ""
if 'show_scrape_button' not in st.session_state: st.session_state.show_scrape_button = False

#  UI LAYOUT
st.markdown("<h1 style='text-align: center;'>📊 Scrap and Analyse</h1>", unsafe_allow_html=True)
st.markdown("<div style='text-align: center; color: #666; margin-bottom: 25px;'>scrap prizes of products from different websites</div>", unsafe_allow_html=True)

col_spacer_l, col_search, col_spacer_r = st.columns([1, 6, 1])
with col_search:
    with st.form(key='search_form'):
        c_input, c_btn = st.columns([5, 1])
        with c_input:
            new_query = st.text_input("Search", placeholder="e.g. iPhone 15...", label_visibility="collapsed")
        with c_btn:
            submit_button = st.form_submit_button("🔍 Search", type="primary", use_container_width=True)

# Search Logic
if submit_button and new_query:
    st.session_state.search_term = new_query

    with st.spinner("🔎 Searching products"):
        df_results = search_db_smart(new_query)

    if not df_results.empty:
        st.session_state.data = df_results
        st.session_state.show_scrape_button = False
    else:
        st.session_state.data = pd.DataFrame()
        st.session_state.show_scrape_button = True


# Scrape Logic
if st.session_state.show_scrape_button:
    col_msg_l, col_msg_main, col_msg_r = st.columns([1, 4, 1])
    with col_msg_main:
        st.info(f"No exact matches found for '{st.session_state.search_term}'.")
        
        if st.button("🕷️ Scrape Live Data", use_container_width=True):
            with st.status(f"🚀 Scraping '{st.session_state.search_term}'...", expanded=True):
                
                st.write("🔄 Scanning Amazon...")
                try: 
                    scrape_amazon(st.session_state.search_term)
                    st.write("✅ Amazon Done.")
                except Exception as e: 
                    st.error(f"Amazon Error: {e}")
                
                st.write("🔄 Scanning Daraz...")
                try: 
                    scrape_daraz(st.session_state.search_term)
                    st.write("✅ Daraz Done.")
                except Exception as e: 
                    st.error(f"Daraz Error: {e}")
            
            # Refresh Data
            df_new = search_db_smart(st.session_state.search_term)
            st.session_state.data = df_new
            st.session_state.show_scrape_button = False
            st.rerun()

# --- 6. DATA PROCESSING & VISUALIZATION ---
df = st.session_state.data

if not df.empty:
    # Clean Data
    if "url" in df.columns:
        df["url"] = df["url"].astype(str).apply(lambda x: x if x.lower().startswith("http") else None)

    df["price_numeric"] = df["price"].apply(clean_price) if "price" in df.columns else 0.0
    df["rating_numeric"] = df["rating"].apply(clean_rating) if "rating" in df.columns else 0.0
    
    clean_df = df[df["price_numeric"] > 1].copy()

    # Sidebar Filters
    with st.sidebar:
        st.header("⚙️ Filter Controls")
        
        all_retailers = clean_df["retailer"].unique().tolist() if "retailer" in clean_df.columns else []
        selected_retailers = st.multiselect("Select Stores", all_retailers, default=all_retailers)
        
        if not clean_df.empty:
            min_p, max_p = int(clean_df["price_numeric"].min()), int(clean_df["price_numeric"].max())
            if min_p == max_p: max_p += 100
            price_range = st.slider("Price Range (Rs.)", min_p, max_p, (min_p, max_p))
        else:
            price_range = (0, 0)
            
        min_rating = st.slider("Min Rating", 0.0, 5.0, 0.0, step=0.5)
        
        st.markdown("---")
        if st.button("🔄 Update Prices", use_container_width=True):
            if st.session_state.search_term:
                with st.status(f"🚀 Updating...", expanded=True):
                    try:
                        scrape_amazon(st.session_state.search_term)
                        scrape_daraz(st.session_state.search_term)
                    except Exception as e:
                        st.error(f"Update Failed: {e}")
                st.session_state.data = search_db_smart(st.session_state.search_term)
                st.rerun()

    # Apply Filters
    if "retailer" in clean_df.columns:
        filtered_df = clean_df[
            (clean_df["retailer"].isin(selected_retailers)) &
            (clean_df["price_numeric"] >= price_range[0]) &
            (clean_df["price_numeric"] <= price_range[1]) &
            (clean_df["rating_numeric"] >= min_rating)
        ]
    else:
        filtered_df = clean_df

    # KPI Cards
    k1, k2, k3, k4, k5 = st.columns(5)
    def kpi(col, title, value, color_class):
        col.markdown(f'<div class="kpi-card {color_class}"><div class="kpi-title">{title}</div><div class="kpi-value">{value}</div></div>', unsafe_allow_html=True)

    if not filtered_df.empty:
        kpi(k1, "Found", f"{len(filtered_df)}", "kpi-blue")
        kpi(k2, "Avg Price", f"{filtered_df['price_numeric'].mean():,.0f}", "kpi-purple")
        kpi(k3, "Lowest", f"{filtered_df['price_numeric'].min():,.0f}", "kpi-green")
        kpi(k4, "Avg Rating", f"{filtered_df['rating_numeric'].mean():.1f} ⭐", "kpi-orange")
        kpi(k5, "Top Store", f"{filtered_df['retailer'].mode()[0]}", "kpi-red")

    st.write("") 

    # Charts
    col_chart1, col_chart2 = st.columns([2, 1])

    with col_chart1:
        st.subheader("💰 Best Prices")
        if not filtered_df.empty:
            top_15 = filtered_df.nsmallest(15, "price_numeric")
            bar_chart = alt.Chart(top_15).mark_bar().encode(
                x=alt.X('title:N', axis=None, sort='y'), 
                y=alt.Y('price_numeric:Q', title='Price'),
                color='retailer:N',
                tooltip=['title', 'price', 'retailer']
            ).properties(height=300)
            st.altair_chart(bar_chart, use_container_width=True)

    with col_chart2:
        st.subheader("📊 Retailer Split")
        if not filtered_df.empty:
            pie_chart = alt.Chart(filtered_df).mark_arc(innerRadius=60).encode(
                theta=alt.Theta("count()", stack=True),
                color=alt.Color("retailer:N"),
                tooltip=["retailer", "count()"]
            ).properties(height=300)
            st.altair_chart(pie_chart, use_container_width=True)
    
    # SCATTER PLOT SECTION (Key Insights removed)
    st.markdown("### 📈 Rating vs Price Analysis")
    if not filtered_df.empty:
        # Calculate value score for insights
        filtered_df['value_score'] = filtered_df.apply(
            lambda row: calculate_value_score(row['rating_numeric'], row['price_numeric']), 
            axis=1
        )
        
        # Create scatter plot
        scatter_chart = alt.Chart(filtered_df).mark_circle(size=100).encode(
            x=alt.X('price_numeric:Q', 
                   title='Price (PKR)',
                   scale=alt.Scale(zero=False)),
            y=alt.Y('rating_numeric:Q', 
                   title='Rating',
                   scale=alt.Scale(domain=[0, 5])),
            color=alt.Color('retailer:N', 
                          legend=alt.Legend(title="Retailer")),
            size=alt.Size('rating_numeric:Q',
                         legend=None,
                         scale=alt.Scale(range=[50, 300])),
            tooltip=['title:N', 'price:N', 'rating:N', 'retailer:N', 'value_score:Q']
        ).properties(
            height=400,
            title='Product Rating vs Price Relationship'
        ).configure_axis(
            grid=True
        ).configure_view(
            strokeWidth=0
        )
        
        st.altair_chart(scatter_chart, use_container_width=True)

    # Detailed Table
    st.markdown("### 📄 Product Details")
    # Prepare dataframe for display
    display_df = filtered_df.copy()
    if 'value_score' in display_df.columns:
        display_df = display_df[["title", "price", "rating_numeric", "value_score", "retailer", "url"]]
        column_config = {
            "url": st.column_config.LinkColumn("Link"),
            "rating_numeric": st.column_config.ProgressColumn("Rating", min_value=0, max_value=5, format="%.1f"),
            "value_score": st.column_config.NumberColumn("Value Score", format="%.3f")
        }
    else:
        display_df = display_df[["title", "price", "rating_numeric", "retailer", "url"]]
        column_config = {
            "url": st.column_config.LinkColumn("Link"),
            "rating_numeric": st.column_config.ProgressColumn("Rating", min_value=0, max_value=5, format="%.1f"),
        }
    
    st.dataframe(
        display_df,
        column_config=column_config,
        use_container_width=True,
        hide_index=True
    )

    # --- 7. PRICE ANALYTICS IMPORT ---
    if not filtered_df.empty:
        show_price_trend(filtered_df, db_helper)

# EMPTY STATE HANDLING 
else:
    if st.session_state.search_term:
        st.info(f"No products found for '{st.session_state.search_term}'. Try a different search term or scrape new data.")
    else:
        st.info("🔍 Enter a product name in the search box above to get started.")
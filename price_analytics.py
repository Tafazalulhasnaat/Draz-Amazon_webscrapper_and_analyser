import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime

def show_price_trend(df, db_helper):
    """
    Displays a mobile-friendly price history chart for a selected product.
    Fetches data from the 'history' subcollection in Firestore.

    Optimized for:
    - Mobile scrolling stability
    - No layout fluctuation
    - Smooth UX
    """

    st.markdown("---")
    st.subheader("📈 Price History Analytics")

    if df.empty or 'id' not in df.columns:
        st.warning("No product data available for analytics.")
        return

    # 🔹 Create display label
    df = df.copy()
    df['display_label'] = (
        df['title'] + " (" + df['retailer'] + " - " + df['price'].astype(str) + ")"
    )

    # 🔹 Default to cheapest product
    cheapest_idx = df['price_numeric'].idxmin()
    selected_label = st.selectbox(
        "Select a product to see price history:",
        df['display_label'].tolist(),
        index=df.index.get_loc(cheapest_idx)
    )

    selected_row = df[df['display_label'] == selected_label].iloc[0]
    doc_id = selected_row['id']
    product_title = selected_row['title']

    # 🔹 Fetch history subcollection
    history_ref = db_helper.collection.document(doc_id).collection("history")
    history_docs = history_ref.stream()

    history_data = []
    for doc in history_docs:
        h = doc.to_dict()
        if 'timestamp' in h and 'price' in h:
            history_data.append(h)

    if not history_data:
        st.info("Not enough historical data collected yet. Try scraping again later.")
        return

    # 🔹 Prepare dataframe
    hist_df = pd.DataFrame(history_data)
    hist_df['timestamp'] = pd.to_datetime(hist_df['timestamp'])

    def clean_price(p):
        if isinstance(p, (int, float)):
            return float(p)
        import re
        clean = str(p).replace(",", "").replace("Rs.", "").replace("PKR", "").strip()
        match = re.search(r"(\d+(\.\d+)?)", clean)
        return float(match.group(1)) if match else 0.0

    hist_df['price_val'] = hist_df['price'].apply(clean_price)
    hist_df = hist_df.sort_values('timestamp')

    # 🔹 Mobile-friendly chart (NO interaction)
    chart = alt.Chart(hist_df).mark_line(point=True).encode(
        x=alt.X(
            'timestamp:T',
            title='Date',
            axis=alt.Axis(format='%d %b')
        ),
        y=alt.Y('price_val:Q', title='Price (Rs.)'),
        tooltip=['price_val']
    ).properties(
        title=f"Price Trend: {product_title[:40]}",
        height=250
    )

    # 🔹 Wrap chart to prevent auto-scroll jump
    with st.expander("📊 View Price History Chart", expanded=False):
        st.altair_chart(chart, use_container_width=True)

    # 🔹 Stacked metrics (mobile-safe)
    st.metric("📉 Lowest Recorded Price", f"{hist_df['price_val'].min():,.0f} Rs.")
    st.metric("📈 Highest Recorded Price", f"{hist_df['price_val'].max():,.0f} Rs.")
    st.metric("🧾 Data Points Collected", f"{len(hist_df)}")

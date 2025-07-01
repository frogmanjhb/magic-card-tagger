import streamlit as st
import pandas as pd
import requests
import io

SCRYFALL_API = "https://api.scryfall.com/cards/named?exact="

def fetch_card_tags(card_name):
    try:
        response = requests.get(SCRYFALL_API + requests.utils.quote(card_name))
        if response.status_code != 200:
            return None
        data = response.json()
        # Rarity
        rarity = data.get('rarity', '').capitalize()
        # Colors
        colors = data.get('colors', [])
        color_map = {'W': 'White', 'U': 'Blue', 'B': 'Black', 'R': 'Red', 'G': 'Green'}
        if not colors:
            color_tag = 'Colour: Colorless'
        else:
            color_names = [color_map.get(c, c) for c in colors]
            color_tag = f"Colour: {', '.join(color_names)}"
        # Card types
        type_line = data.get('type_line', '')
        card_types = [t.strip() for t in type_line.split('—')[0].split() if t[0].isupper()]
        type_tag = f"Type: {' '.join(card_types)}" if card_types else ''
        rarity_tag = f"Rarity: {rarity}" if rarity else ''
        tags = ', '.join([color_tag, rarity_tag, type_tag])
        return tags
    except Exception:
        return None

def main():
    st.title("Magic Card Tagger")
    st.write("Upload a CSV with a 'name' column. The app will fill in the 'tag' column with rarity, color, and card types from Scryfall.")

    uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        # Accept 'name', 'Name', 'title', or 'Title' as the card name column
        name_col = None
        for col in ['name', 'Name', 'title', 'Title']:
            if col in df.columns:
                name_col = col
                break
        if not name_col:
            st.error("CSV must contain a 'name', 'Name', 'title', or 'Title' column.")
            return
        # Use 'Tags' column if it exists, otherwise create it
        tag_col = 'Tags'
        if tag_col not in df.columns:
            df[tag_col] = ''
        progress = st.progress(0)
        for idx, row in df.iterrows():
            tags = fetch_card_tags(row[name_col])
            if tags:
                df.at[idx, tag_col] = tags
            progress.progress((idx + 1) / len(df))
        st.success("Tags populated!")
        output = io.StringIO()
        df.to_csv(output, index=False)
        st.download_button("Download tagged CSV", data=output.getvalue(), file_name="tagged_cards.csv", mime="text/csv")

if __name__ == "__main__":
    main()

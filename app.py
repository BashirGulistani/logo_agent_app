import os
import uuid
import requests
from io import BytesIO
from PIL import Image
from rembg import remove
from bs4 import BeautifulSoup
import streamlit as st

# Output folder
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

st.title("Company Logo Scraper + Background Remover")

query = st.text_input("Enter Company Name or URL")
submit = st.button("Get Transparent Logo")

def scrape_logo_url(query: str) -> str:
    search_url = f"https://www.google.com/search?q={query}+logo&tbm=isch"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(search_url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    img_tags = soup.find_all("img")
    for img in img_tags:
        src = img.get("src")
        if src and "http" in src:
            return src
    return None

def download_image(url: str) -> Image.Image:
    response = requests.get(url)
    return Image.open(BytesIO(response.content)).convert("RGBA")

def remove_background(image: Image.Image) -> str:
    result = remove(image)
    filename = f"{uuid.uuid4()}.png"
    output_path = os.path.join(OUTPUT_DIR, filename)
    with open(output_path, "wb") as f:
        f.write(result)
    return output_path

if submit and query:
    with st.spinner("Processing..."):
        try:
            logo_url = scrape_logo_url(query)
            if not logo_url:
                st.error("No logo found. Try a different company name.")
            else:
                image = download_image(logo_url)
                st.image(image, caption="Original Logo")

                output_path = remove_background(image)
                st.success("Background removed!")

                st.image(output_path, caption="Transparent Logo")
                with open(output_path, "rb") as file:
                    btn = st.download_button(
                        label="Download Transparent Logo",
                        data=file,
                        file_name=os.path.basename(output_path),
                        mime="image/png"
                    )
        except Exception as e:
            st.error(f"Error: {e}")

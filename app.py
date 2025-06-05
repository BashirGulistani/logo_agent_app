import os
import uuid
import requests
import openai
import streamlit as st
from io import BytesIO
from PIL import Image, ImageEnhance
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader

# ---- CONFIG ----
os.makedirs("output", exist_ok=True)

# ---- FUNCTIONS ----

def get_logo_from_brandfetch(domain, brandfetch_api_key):
    headers = {"Authorization": f"Bearer {brandfetch_api_key}"}
    res = requests.get(f"https://api.brandfetch.io/v2/brands/{domain}", headers=headers)
    if res.status_code != 200:
        st.error("Brand not found on Brandfetch.")
        return []
    data = res.json()
    return [fmt["src"] for logo in data["logos"] for fmt in logo["formats"] if fmt["format"] == "png"]

def download_image(url):
    response = requests.get(url)
    return Image.open(BytesIO(response.content)).convert("RGBA")

def is_logo_bright(image):
    grayscale = image.convert("L")
    brightness = sum(grayscale.getdata()) / (grayscale.width * grayscale.height)
    return brightness > 180  # brightness threshold

def generate_product_image(product_type, background_color, openai_api_key):
    openai.api_key = openai_api_key
    prompt = f"{product_type} mockup, {background_color} background, minimal, flat view"
    response = openai.images.generate(
        model="dall-e-3",
        prompt=prompt,
        n=1,
        size="1024x1024"
    )
    img_url = response.data[0].url
    return download_image(img_url)

def overlay_logo(base_image, logo_image):
    logo_size = int(min(base_image.width, base_image.height) * 0.2)
    logo_resized = logo_image.resize((logo_size, logo_size))
    position = (base_image.width - logo_size - 20, base_image.height - logo_size - 20)
    base_image.paste(logo_resized, position, logo_resized)
    return base_image

def create_pdf(images, pdf_path="output/product_mockups.pdf"):
    c = canvas.Canvas(pdf_path, pagesize=A4)
    for img in images:
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        c.drawImage(ImageReader(buffer), 100, 300, width=300, height=300)
        c.showPage()
    c.save()
    return pdf_path

# ---- STREAMLIT APP ----

st.title("🔧 Auto Product Mockup Generator")

brand = st.text_input("Enter company domain (e.g., nike.com)")
brandfetch_key = st.text_input("Brandfetch API Key", type="password")
openai_key = st.text_input("OpenAI API Key", type="password")
run = st.button("Generate Mockups")

if run and brand and brandfetch_key and openai_key:
    with st.spinner("Fetching logo..."):
        logos = get_logo_from_brandfetch(brand, brandfetch_key)
        if not logos:
            st.stop()
        logos_images = [download_image(url) for url in logos]

    main_logo = logos_images[0]
    logo_brightness = is_logo_bright(main_logo)
    bg_color = "black" if logo_brightness else "white"

    products = ["t-shirt", "steel water bottle", "hat", "tote bag", "pen"]
    final_images = []

    st.header("🧢 Final Mockups")

    for product, logo in zip(products, logos_images[:5]):
        with st.spinner(f"Generating {product}..."):
            base = generate_product_image(product, bg_color, openai_key)
            result = overlay_logo(base, logo)
            final_images.append(result)
            st.image(result, caption=product)

    with st.spinner("Creating downloadable PDF..."):
        pdf_path = create_pdf(final_images)
        with open(pdf_path, "rb") as f:
            st.download_button("📄 Download Product Mockups PDF", f, file_name="mockups.pdf")

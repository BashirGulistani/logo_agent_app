import os
import uuid
import random
import requests
import openai
import streamlit as st
from io import BytesIO
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader

# Create output dir
os.makedirs("output", exist_ok=True)

# ---- UTIL FUNCTIONS ----

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
    return brightness > 180

def generate_product_image(product_type, background_color, openai_api_key):
    openai.api_key = openai_api_key
    prompt = f"{product_type} mockup, {background_color} background, minimal, flat view, make sure the images are realistic"
    response = openai.images.generate(
        model="dall-e-3",
        prompt=prompt,
        n=1,
        size="1024x1024"
    )
    img_url = response.data[0].url
    return download_image(img_url)

def generate_print_mockup(product_img: Image.Image, logo_img: Image.Image, product_type: str, openai_api_key: str):
    openai.api_key = openai_api_key

    prompt = f"I want to print this {product_type} with print-on-demand. Place this logo naturally on the front of the {product_type} so it looks like a real product mockup. Make sure the logo is visible but not too big."

    def img_to_bytes(img):
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    product_bytes = img_to_bytes(product_img)
    logo_bytes = img_to_bytes(logo_img)

    # ✳️ Requires OpenAI's image editing capabilities with image+prompt input.
    response = openai.images.edit(
        prompt=prompt,
        image=product_bytes,
        mask=None,  # No mask, let it place freely
        n=1,
        size="1024x1024"
    )
    result_url = response['data'][0]['url']
    return download_image(result_url)

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

st.title("🛍️ Product Mockup Generator with Print-Ready Logos")

brand = st.text_input("Enter company domain (e.g., nike.com)")
brandfetch_key = st.text_input("Brandfetch API Key", type="password")
openai_key = st.text_input("OpenAI API Key", type="password")
run = st.button("Generate Mockups")

if run and brand and brandfetch_key and openai_key:
    with st.spinner("Fetching logos..."):
        logos = get_logo_from_brandfetch(brand, brandfetch_key)
        if not logos:
            st.stop()
        logos_images = [download_image(url) for url in logos]

    main_logo = logos_images[0]
    bg_color = "black" if is_logo_bright(main_logo) else "white"

    # Adjust logos for 5 products
    if len(logos_images) < 5:
        logos_to_use = random.choices(logos_images, k=5)
    else:
        logos_to_use = random.sample(logos_images, 5)

    products = ["t-shirt", "steel water bottle", "hat", "tote bag", "pen"]
    final_images = []

    st.header("🧢 Final Print-On-Demand Mockups")

    for product, logo in zip(products, logos_to_use):
        with st.spinner(f"Creating {product}..."):
            base_product = generate_product_image(product, bg_color, openai_key)
            final = generate_print_mockup(base_product, logo, product, openai_key)
            final_images.append(final)
            st.image(final, caption=product)

    with st.spinner("Creating downloadable PDF..."):
        pdf_path = create_pdf(final_images)
        with open(pdf_path, "rb") as f:
            st.download_button("📄 Download Product Mockups PDF", f, file_name="mockups.pdf")

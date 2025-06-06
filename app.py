import streamlit as st
import requests
import random
from PIL import Image
from io import BytesIO
from fpdf import FPDF
import os
from google import genai
from google.genai import types

# ------------------- Configuration -------------------
st.set_page_config(page_title="Brand Logo Mockups", layout="centered")
st.title("🧢 Brand Product Mockup Generator")

# ------------------- Templates -------------------
templates = [
    {
        "light_tshirt": {"template_id": "bad-doves-scare-yearly-1794", "placeholder_id": "logoLayer", "size": (295, 286)},
        "dark_tshirt": {"template_id": "rebel-hedgehogs-walk-ably-1675", "placeholder_id": "image_blackshirt", "size": (299, 296)}
    },
    {
        "light_totebag": {"template_id": "bad-dogs-behave-cruelly-1636", "placeholder_id": "image_whitebag", "size": (298, 291)},
        "dark_totebag": {"template_id": "greedy-orcs-pray-tightly-1486", "placeholder_id": "image_blackbag", "size": (287, 288)}
    },
    {
        "light_pen": {"template_id": "bright-clams-cheer-promptly-1824", "placeholder_id": "image_whitepen", "size": (81, 80)},
        "dark_pen": {"template_id": "icky-bookworms-hunt-often-1163", "placeholder_id": "image_pen", "size": (88, 87)}
    },
    {
        "light_hat": {"template_id": "tall-fauns-shiver-soon-1646", "placeholder_id": "image_whitehat", "size": (217, 223)},
        "dark_hat": {"template_id": "dashing-hares-flap-loosely-1743", "placeholder_id": "image_blackhat", "size": (191, 190)}
    },
    {
        "light_bottle": {"template_id": "filthy-oxen-hang-loudly-1802", "placeholder_id": "image_whitebottle", "size": (156, 156)},
        "dark_bottle": {"template_id": "zany-monkeys-slap-bravely-1525", "placeholder_id": "image_blackbottle", "size": (191, 192)}
    }
]

# ------------------- Helpers -------------------
def is_logo_light(url):
    img = Image.open(BytesIO(requests.get(url).content)).convert("RGB")
    pixels = list(img.getdata())
    avg = tuple(sum(x) / len(x) for x in zip(*pixels))
    brightness = sum(avg) / 3
    return brightness > 30

def resize_logo(url, size):
    response = requests.get(url)
    img = Image.open(BytesIO(response.content)).convert("RGBA")
    img = img.resize(size, Image.Resampling.LANCZOS)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

def download_and_convert_to_png(image_url, save_path_png):
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content)).convert("RGB")
        img.save(save_path_png, "PNG")
        return True
    except Exception as e:
        print(f"❌ Failed to download or convert image: {e}")
        return False

def enhance_image_with_gemini(product_type, image_path):
    image = Image.open(image_path).convert("RGB")
    client = genai.Client(api_key=st.secrets["gemini_api_key"])
    prompt = (
        "Enhance this image, add fabric texture and realistic lighting. It should look natural, and ready for print on direct-to-garment (DTG) printer. Also, Enhance the appearance of the logo on the product in the image so that it looks naturally integrated and realistic. The logo should appear as if it was originally part of the product design and not added later. Consider the product's surface texture, how light interacts with both the product and the logo, and the perspective to ensure a seamless and believable integration."
    )
    response = client.models.generate_content(
        model="gemini-2.0-flash-preview-image-generation",
        contents=[prompt, image],
        config=types.GenerateContentConfig(response_modalities=['TEXT', 'IMAGE'])
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data:
            enhanced_img = Image.open(BytesIO(part.inline_data.data))
            enhanced_img.save(image_path)

# ------------------- PDF -------------------
def create_pdf(images_with_labels, output_path="mockups.pdf"):
    pdf = FPDF()
    for path, label in images_with_labels:
        if not os.path.exists(path):
            continue
        pdf.add_page()
        pdf.set_font("Arial", size=14)
        pdf.set_xy(20, 15)
        pdf.cell(0, 10, txt=label, ln=1)
        pdf.image(path, x=20, y=30, w=170)
    pdf.output(output_path)
    return output_path

# ------------------- Main App -------------------
brand = st.text_input("Enter Brand Name or Domain (e.g., airbnb.com)")
ai_toggle = st.toggle("✨ AI Enhance Logo Placement")

if st.button("Generate Mockups") and brand:
    with st.spinner("Fetching logos and rendering mockups..."):
        # Get logos
        headers = {"Authorization": f"Bearer {st.secrets['brandfetch_api_key']}"}
        r = requests.get(f"https://api.brandfetch.io/v2/brands/{brand}", headers=headers)
        data = r.json()

        logo_urls = []
        for logo in data.get("logos", []):
            formats = logo.get("formats", [])
            png_url = next((f["src"] for f in formats if f.get("format") == "png"), None)
            jpg_url = next((f["src"] for f in formats if f.get("format") == "jpg"), None)
            if png_url:
                logo_urls.append(png_url)
            elif jpg_url:
                logo_urls.append(jpg_url)
            if len(logo_urls) >= 5:
                break

        images_with_labels = []

        # Generate mockups
        for template in templates:
            product_key = list(template.keys())[0].split("_")[-1]
            logo_url = random.choice(logo_urls)
            logo_is_light = is_logo_light(logo_url)
            key_prefix = "dark" if logo_is_light else "light"
            selected_key = f"{key_prefix}_{product_key}"
            product_template = template[selected_key]
            resized_logo = resize_logo(logo_url, product_template["size"])

            render_payload = {
                "template": product_template["template_id"],
                "data": {
                    f"{product_template['placeholder_id']}.src": logo_url
                }
            }

            res = requests.post(
                "https://get.renderform.io/api/v2/render",
                headers={
                    "X-API-KEY": st.secrets["renderform_api_key"],
                    "Content-Type": "application/json"
                },
                json=render_payload
            )

            if res.status_code == 200:
                image_url = res.json().get("href")
                path = f"{product_key}_mockup_converted.png"
                if download_and_convert_to_png(image_url, path):
                    if ai_toggle:
                        enhance_image_with_gemini(product_key, path)
                    images_with_labels.append((path, f"{product_key.title()} Mockup"))

        # Generate PDF
        pdf_path = create_pdf(images_with_labels)
        with open(pdf_path, "rb") as f:
            st.download_button("📄 Download PDF", f, file_name="mockups.pdf")

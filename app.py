import streamlit as st
import requests
import random
from PIL import Image
from io import BytesIO
from fpdf import FPDF
from google import genai
from google.genai import types

# Define your templates
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
        "light_pen": {"template_id": "bright-clams-cheer-promptly-1824", "placeholder_id": "image_whitepen", "size": (69, 67)},
        "dark_pen": {"template_id": "icky-bookworms-hunt-often-1163", "placeholder_id": "image_pen", "size": (63, 62)}
    },
    {
        "light_hat": {"template_id": "tall-fauns-shiver-soon-1646", "placeholder_id": "image_whitehat", "size": (207, 206)},
        "dark_hat": {"template_id": "dashing-hares-flap-loosely-1743", "placeholder_id": "image_blackhat", "size": (191, 190)}
    },
    {
        "light_bottle": {"template_id": "filthy-oxen-hang-loudly-1802", "placeholder_id": "image_whitebottle", "size": (156, 156)},
        "dark_bottle": {"template_id": "zany-monkeys-slap-bravely-1525", "placeholder_id": "image_blackbottle", "size": (191, 192)}
    }
]

# Helper functions
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

def enhance_image_with_gemini(product_type, image_path):
    image = Image.open(image_path).convert("RGB")
    client = genai.Client(api_key=st.secrets["gemini_api_key"])
    prompt = (
        f"Enhance this image and make the logo look naturally printed on the {product_type}, "
        f"blending it into the surface with realistic lighting, accurate fabric texture, and natural appearance. "
        f"Do not zoom, crop, reposition, rotate, or modify the image composition. Keep everything as it is."
    )
    response = client.models.generate_content(
        model="gemini-2.0-flash-preview-image-generation",
        contents=[prompt, image],
        config=types.GenerateContentConfig(response_modalities=['TEXT', 'IMAGE'])
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data:
            enhanced_img = Image.open(BytesIO(part.inline_data.data))
            save_path = f"enhanced_{product_type}.png"
            enhanced_img.save(save_path)
            return save_path
    return image_path

def render_and_enhance(templates, logo_urls, renderform_key, ai_toggle):
    image_paths = []

    for template in templates:
        product_key = list(template.keys())[0].split("_")[-1]
        logo_url = random.choice(logo_urls)
        logo_is_light = is_logo_light(logo_url)

        key_prefix = "dark" if logo_is_light else "light"
        selected_key = f"{key_prefix}_{product_key}"
        product_template = template[selected_key]

        render_payload = {
            "template": product_template["template_id"],
            "data": {
                f"{product_template['placeholder_id']}.src": logo_url
            }
        }

        res = requests.post(
            "https://get.renderform.io/api/v2/render",
            headers={
                "X-API-KEY": renderform_key,
                "Content-Type": "application/json"
            },
            json=render_payload
        )

        if res.status_code == 200:
            image_url = res.json().get("href")
            path = f"{product_key}_mockup.png"
            img_data = requests.get(image_url).content
            with open(path, "wb") as f:
                f.write(img_data)

            if ai_toggle:
                final_path = enhance_image_with_gemini(product_key, path)
            else:
                final_path = path

            image_paths.append((product_key.capitalize(), final_path))

    return image_paths

def create_pdf(images_with_labels):
    pdf = FPDF()
    for label, path in images_with_labels:
        pdf.add_page()
        pdf.set_font("Arial", size=16)
        pdf.cell(200, 10, txt=label, ln=True, align='C')
        pdf.image(path, x=20, y=30, w=170)
    output_path = "mockups.pdf"
    pdf.output(output_path)
    return output_path

# Streamlit app
st.title("🧢 AI Product Mockup Generator")

brand_input = st.text_input("Enter brand name or domain (e.g. airbnb.com):")
ai_toggle = st.toggle("✨ Enhance Logo Realism with Gemini", value=True)

if st.button("Generate Mockups") and brand_input:
    brandfetch_api_key = st.secrets["brandfetch_api_key"]
    renderform_api_key = st.secrets["renderform_api_key"]

    headers = {"Authorization": f"Bearer {brandfetch_api_key}"}
    r = requests.get(f"https://api.brandfetch.io/v2/brands/{brand_input}", headers=headers)
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

    st.success("✅ Logos fetched successfully!")

    images_with_labels = render_and_enhance(templates, logo_urls, renderform_api_key, ai_toggle)

    for label, img_path in images_with_labels:
        st.image(img_path, caption=label)

    pdf_path = create_pdf(images_with_labels)
    with open(pdf_path, "rb") as file:
        st.download_button("📥 Download PDF", file, file_name="Product_Mockups.pdf")

import streamlit as st
import requests
import random
import os
from PIL import Image, UnidentifiedImageError
from io import BytesIO
from google import genai
from google.genai import types
from fpdf import FPDF
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse

# templates
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
        "light_mug": {"template_id": "jazzy-guinea pigs-travel-gently-1653", "placeholder_id": "image_whitemug", "size": (353, 358)},
        "dark_mug": {"template_id": "red-unicorns-hunt-rudely-1857", "placeholder_id": "image_blackmug", "size": (512, 512)}
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

def is_logo_light(url):
    if url.lower().endswith(".svg"):
        print(f"[i] Skipping brightness check for SVG: {url}")
        return False  

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        img = Image.open(BytesIO(response.content)).convert("RGB")
        pixels = list(img.getdata())
        avg = tuple(sum(x) / len(x) for x in zip(*pixels))
        brightness = sum(avg) / 3
        return brightness > 30

    except Exception as e:
        print(f"[⚠] Failed to analyze image brightness for {url}: {e}")
        return False


def resize_logo(url, size):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        content = response.content

        if url.lower().endswith(".svg"):
            print(f"[i] Skipping resize for SVG: {url}")
            return None  

        img = Image.open(BytesIO(content)).convert("RGBA")
        img = img.resize(size, Image.Resampling.LANCZOS)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    except Exception as e:
        print(f"[⚠] Failed to resize logo from {url}: {e}")
        return None

def enhance_image_with_gemini(product_type, image_path, use_ai=True):
    if not use_ai:
        return image_path

    image = Image.open(image_path).convert("RGB")
    client = genai.Client(api_key=st.secrets["gemini_api_key"])
    prompt = (
        "Enhance this image, add fabric texture and realistic lighting. Also, make the logo blend into the product texture and lighting for a more natural look. Do not zoom in or out, the whole product should be visible."
    )

    response = client.models.generate_content(
        model="gemini-2.0-flash-preview-image-generation",
        contents=[prompt, image],
        config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data:
            enhanced_img = Image.open(BytesIO(part.inline_data.data))
            enhanced_path = f"enhanced_{product_type}.png"
            enhanced_img.save(enhanced_path)
            return enhanced_path
    return image_path

def get_logo_from_brandfetch(domain, api_key):
    headers = {"Authorization": f"Bearer {api_key}"}
    r = requests.get(f"https://api.brandfetch.io/v2/brands/{domain}", headers=headers)
    if r.status_code != 200:
        st.warning(f"Brandfetch error {r.status_code}: {r.text}")

        return []
    data = r.json()
    urls = []
    for logo in data.get("logos", []):
        formats = logo.get("formats", [])
        png_url = next((f["src"] for f in formats if f.get("format") == "png"), None)
        jpg_url = next((f["src"] for f in formats if f.get("format") == "jpg"), None)
        if png_url:
            urls.append(png_url)
        elif jpg_url:
            urls.append(jpg_url)
        if len(urls) >= 5:
            break
    return urls

def is_valid_image_url(url):
    try:
        response = requests.head(url, allow_redirects=True, timeout=5)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '').lower()
            return content_type.startswith('image/')
    except requests.exceptions.RequestException:
        return False
    return False

def fallback_scrape_logo(domain):
    base_url = f"https://{domain}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    print(f"Scraping {base_url}...")
    try:
        response = requests.get(base_url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"-> Failed to fetch website: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    candidate_urls = []

    
    for img_tag in soup.find_all("img"):
        src = img_tag.get("src")
        if not src:
            continue
        alt = img_tag.get("alt", "").lower()
        class_name = " ".join(img_tag.get("class", [])).lower()
        if "logo" in alt or "logo" in class_name or "logo" in src.lower():
            candidate_urls.append(urljoin(base_url, src))

    
    for link_tag in soup.find_all("link", rel=re.compile("icon", re.I)):
        href = link_tag.get("href")
        if href and "logo" in href.lower():
            candidate_urls.append(urljoin(base_url, href))

    print(f"-> Found {len(set(candidate_urls))} potential candidates. Validating...")
    valid_logo_urls = []

    for url in dict.fromkeys(candidate_urls):
        if is_valid_image_url(url):
            print(f"  [✓] Valid logo found: {url}")
            valid_logo_urls.append(url)

    
    allowed_exts = (".svg", ".png", ".jpg", ".jpeg")
    filtered = []
    for url in valid_logo_urls:
        filename = urlparse(url).path.split("/")[-1].split("?")[0].lower()
        if filename.endswith(allowed_exts) and "logo" in filename:
            filtered.append(url)

    
    if not filtered:
        print("No 'logo' found, trying generic image fallback...")
        fallback_candidates = []

        
        for tag in soup.find_all(["img", "link"]):
            src = tag.get("src") or tag.get("href")
            if src:
                full_url = urljoin(base_url, src)
                filename = urlparse(full_url).path.split("/")[-1].split("?")[0].lower()
                if filename.endswith(allowed_exts):
                    fallback_candidates.append(full_url)

        
        for url in dict.fromkeys(fallback_candidates):
            if is_valid_image_url(url):
                print(f"  [✓] Fallback valid image found: {url}")
                filtered.append(url)
                break  

    print(f"\nSUCCESS! Returning {len(filtered)} logo(s) for {domain}:")
    for url in filtered:
        print(f"  -> {url}")

    return filtered




def render_and_enhance(templates, logo_urls, renderform_key, use_ai):
    images_with_labels = []

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
            "data": {f"{product_template['placeholder_id']}.src": logo_url}
        }

        res = requests.post(
            "https://get.renderform.io/api/v2/render",
            headers={"X-API-KEY": renderform_key, "Content-Type": "application/json"},
            json=render_payload
        )

        if res.status_code == 200:
            image_url = res.json().get("href")
            
            img_data = requests.get(image_url).content
            img = Image.open(BytesIO(img_data)).convert("RGB")
            mockup_path = f"{product_key}_mockup.png"
            img.save(mockup_path, format="PNG")



            final_path = enhance_image_with_gemini(product_key, mockup_path, use_ai)
            images_with_labels.append((final_path, product_key.capitalize()))
        else:
            st.error(f"Failed to render {product_key}")
    return images_with_labels


def create_pdf(images_with_labels, output_path="client_ready_mockups.pdf"):
    pdf = FPDF()
    product_colors = [
        ("Black", "#000000"), ("White", "#FFFFFF"), ("Coral", "#FF5733"),
        ("Sky Blue", "#33C1FF"), ("Green", "#28A745"), ("Gold", "#FFC107"),
        ("Purple", "#8E44AD"), ("Pink", "#E91E63"), ("Slate", "#607D8B"), ("Brown", "#795548")
    ]

    for idx, (path, caption) in enumerate(images_with_labels):
        pdf.add_page()

        # Product Title
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 15, txt=f"{caption} Edition", ln=True, align='C')

        # Subtitle
        pdf.set_font("Helvetica", "", 12)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(0, 10, txt="Perfect for events, teams, or brand giveaways", ln=True, align='C')

        # Product Image
        pdf.image(path, x=30, y=35, w=150)

        # Color Label
        pdf.set_xy(30, 200)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 10, txt="Available Colors:", ln=True)

        # Color Swatches + Labels
        x_start = 30
        y_start = 215
        swatch_size = 8
        spacing = 14

        for i, (name, hex_color) in enumerate(product_colors):
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            x = x_start + i * spacing

            # Swatch with black border
            pdf.set_draw_color(0, 0, 0)
            pdf.set_fill_color(r, g, b)
            pdf.rect(x, y_start, swatch_size, swatch_size, style='FD')

            # Color Name
            pdf.set_xy(x - 2, y_start + swatch_size + 2)
            pdf.set_font("Helvetica", size=6)
            pdf.set_text_color(50, 50, 50)
            pdf.cell(swatch_size + 6, 4, name, align='C')

        # Divider
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, 240, 200, 240)

        # Contact Info / CTA
        pdf.set_xy(10, 250)
        pdf.set_font("Helvetica", size=10)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 6, "To place an order, contact: behappy@inkdstores.com or visit inkdstores.com", align='C')

    pdf.output(output_path)
    return output_path



def is_valid_domain_format(domain):
    """
    Ensures domain is of the form name.com or sub-name.org, without protocol, path, or port.
    """
    # Strip whitespace and lowercase
    domain = domain.strip().lower()

    # Disallow protocols, ports, slashes
    if domain.startswith("http://") or domain.startswith("https://") or "/" in domain or ":" in domain:
        return False

    # Check for something like name.com, name.co.uk, etc.
    return bool(re.fullmatch(r"[\w\-]+\.[\w\.\-]+", domain))


def resolve_company_name_to_domain(name):
    query = f"{name} official site"
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://duckduckgo.com/html/?q={query}"

    res = requests.get(url, headers=headers)
    matches = re.findall(r'https?://(www\.)?([\w\-]+\.\w+)', res.text)
    if matches:
        domain = matches[0][1]
        return domain
    else:
        return None


# Streamlit UI
st.set_page_config(page_title="Brand Logo Product Mockups")
BRAND_LOGO_URL = "https://cdn.brandfetch.io/idoN--mZ12/w/200/h/77/theme/light/logo.png?c=1dxbfHSJFAPEGdCLU4o5B"

st.markdown("""
    <style>
    /* App background and font */
    html, body, [class*="css"] {
        font-family: 'Segoe UI', sans-serif;
        background-color: #f8f9fa;
    }

    /* Title header */
    .stApp > header {
        background-color: #2c3e50;
        color: white;
        padding: 1rem;
        border-radius: 0 0 10px 10px;
    }

    /* Input fields */
    .stTextInput > div > div > input {
        border: 2px solid #ccc;
        border-radius: 6px;
        padding: 0.4rem;
    }

    /* Buttons */
    .stButton>button {
        border-radius: 8px;
        background-color: #1abc9c;
        color: white;
        font-weight: bold;
        padding: 0.5rem 1.2rem;
    }

    .stButton>button:hover {
        background-color: #16a085;
    }

    /* Toggle */
    .stToggle {
        background-color: #e3f6f5;
        padding: 0.4rem 0.7rem;
        border-radius: 8px;
    }

    /* Section titles */
    .stMarkdown h1 {
        font-size: 2rem;
        color: #2c3e50;
    }

    /* Warnings/info blocks */
    .stAlert {
        border-left: 5px solid #f3f6f4 !important;
        background-color: #1abc9c !important;
    }

    footer {
        visibility: hidden;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown(f"""
    <div style='display: flex; align-items: center; justify-content: center; margin-bottom: 20px;'>
        <img src="{BRAND_LOGO_URL}" alt="Brand Logo" style="height: 80px; border-radius: 10px;" />
    </div>
""", unsafe_allow_html=True)



st.title("Product Mockup Generator")

brand_input = st.text_input("Enter a brand name or domain (e.g., Airbnb or airbnb.com)")
use_ai = st.toggle("Enhance with AI", value=True)
run = st.button("Generate Mockups")

if run and brand_input:
    if not is_valid_domain_format(brand_input):
        resolved_domain = resolve_company_name_to_domain(brand_input)
        if resolved_domain and is_valid_domain_format(resolved_domain):
            brand_input = resolved_domain
        else:
            st.error("Please enter a valid domain like airbnb.com.")
            st.stop()


    logo_urls = get_logo_from_brandfetch(brand_input, st.secrets["brandfetch_api_key"])
    if not logo_urls:
        st.warning("Brandfetch failed, trying to scrape logo from website...")
        logo_urls = fallback_scrape_logo(brand_input)

    if not logo_urls:
        st.error("No logo found.")
    else:
        st.info("Generating mockups...")
        images_with_labels = render_and_enhance(templates, logo_urls, st.secrets["renderform_api_key"], use_ai)
        pdf_path = create_pdf(images_with_labels)
        st.success("PDF created successfully!")
        with open(pdf_path, "rb") as f:
            st.download_button("Download PDF", f, file_name="mockups.pdf")





import os
import requests
from openai import OpenAI
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.media import UploadFile
from wordpress_xmlrpc.methods.posts import NewPost
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import warnings
import re
from requests.packages.urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

# Configuration
WORDPRESS_URL = "https://your-wordpress-site.com/xmlrpc.php"
WORDPRESS_USER = ""
WORDPRESS_PASSWORD = ""
OPENAI_API_KEY = ""

client = OpenAI(api_key=OPENAI_API_KEY)
wp_client = Client(WORDPRESS_URL, WORDPRESS_USER, WORDPRESS_PASSWORD)

def debug_log(*args):
    """Helper function for debug logging"""
    print("[DEBUG]", *args)

def generate_new_title(original_title):
    """Generate a new title using OpenAI while preserving the original meaning and style"""
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Rewrite the following title while maintaining its original meaning and style. Make it more engaging and SEO-friendly."},
                {"role": "user", "content": original_title}
            ],
            temperature=0.5,
            max_tokens=50
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        debug_log(f"Title Generation Error: {str(e)}")
        return original_title

def process_content_sections(content):
    """Split content into sections and process each with GPT-3.5"""
    try:
        sections = re.split(r'\n\s*\n', content)
        processed = []

        for section in sections:
            if len(section.strip()) == 0:
                continue

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Rewrite this text while maintaining the original style, tone, and meaning. Make it more engaging and professional."},
                    {"role": "user", "content": section}
                ],
                temperature=0.5,
                max_tokens=len(section.split()) * 2
            )
            processed_section = response.choices[0].message.content.strip()
            processed.append(processed_section)

        return '\n\n'.join(processed)
    except Exception as e:
        debug_log(f"Content Processing Error: {str(e)}")
        return content

def upload_image_to_wordpress(image_url, session):
    """Upload image to WordPress media library with simplified messages"""
    try:
        debug_log(f"Attempting to upload: {image_url}")

        # Skip Gravatar and data URIs
        if "gravatar.com" in image_url or image_url.startswith("data:image/"):
            debug_log(f"Skipping Gravatar or data URI: {image_url}")
            return None, None

        # Skip non-image files
        if not any(image_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
            debug_log(f"Skipping non-image file: {image_url}")
            return None, None

        # Use the existing session for consistent connection settings
        response = session.get(image_url, stream=True, timeout=20)
        response.raise_for_status()

        # Validate content type
        content_type = response.headers.get('Content-Type', '')
        if not content_type.startswith('image/'):
            debug_log(f"Invalid content type {content_type} for {image_url}")
            return None, None

        # Generate filename
        parsed_url = urlparse(image_url)
        file_name = os.path.basename(parsed_url.path)
        if not file_name or '.' not in file_name:
            file_name = f"image_{abs(hash(image_url))}.{content_type.split('/')[-1]}"

        data = {
            'name': file_name,
            'type': content_type,
            'bits': response.content,
            'overwrite': False
        }

        # Upload to WordPress
        media = wp_client.call(UploadFile(data))

        # Handle response format
        if isinstance(media, dict):
            media_id = media.get('id')
            media_url = media.get('url')
        else:
            media_id = media.id
            media_url = media.url

        if not media_url:
            raise ValueError("Image upload failed")

        # Simplified success message
        print(f"✅ Image uploaded successfully")
        return media_id, media_url

    except Exception as e:
        debug_log(f"⛔️Image Upload Failed ({image_url}): {str(e)}")
        return None, None

def process_and_replace_images(content, session, base_url):
    """Process images while maintaining their positions"""
    soup = BeautifulSoup(content, 'html.parser')
    image_map = {}

    for img in soup.find_all('img'):
        img_url = img.get('src') or img.get('data-src') or ''

        # Skip SVG and data URI images completely
        if any([
            img_url.startswith('data:image/svg'),
            'svg' in img_url.lower(),
            img_url.startswith('data:image/') and 'xml' in img_url.lower()
        ]):
            img.decompose()  # Remove the <img> tag completely
            continue

        # Handle relative URLs
        full_url = urljoin(base_url, img_url)

        # Upload image and get WordPress URL
        media_id, media_url = upload_image_to_wordpress(full_url, session)

        if media_url:
            # Replace image source and add WordPress classes
            img['src'] = media_url
            img['class'] = 'wp-image-' + str(media_id)
            img['srcset'] = ''
            image_map[full_url] = media_url
        else:
            img.decompose()

    return str(soup), image_map

def extract_main_content(soup):
    """Extract the main content from the webpage."""
    # Try to find the main content container with the class 'wysiwyg__content'
    main_content = soup.find(class_='wysiwyg__content')

    # If 'wysiwyg__content' is not found, try to find the main content using other common selectors
    if not main_content:
        debug_log("'wysiwyg__content' class not found. Falling back to alternative selectors.")
        main_content = soup.find('article') or soup.find('main') or soup.find('body')

    if not main_content:
        return "Untitled Post", "No content found."

    # Extract the title (if available within the main content)
    title_element = main_content.find('h1') or soup.title
    title = title_element.get_text(strip=True) if title_element else "Untitled Post"

    # Remove any unwanted elements within the main content
    for element in main_content.find_all(['header', 'footer', 'nav', 'aside', 'script', 'style', 'form', 'iframe']):
        element.decompose()

    # Extract the cleaned content
    content = str(main_content)

    return title, content

def process_blog_post(url):
    """Main processing function with enhanced logging"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    }

    with requests.Session() as session:
        session.verify = False
        session.headers.update(headers)

        try:
            debug_log(f"Starting processing for: {url}")
            response = session.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            debug_log("HTML parsed successfully")

            # Extract only the main content (title and body)
            title, raw_content = extract_main_content(soup)
            debug_log(f"Extracted title: {title}")
            debug_log(f"Extracted content length: {len(raw_content)}")

            # Generate a new title using OpenAI
            new_title = generate_new_title(title)
            debug_log(f"New title: {new_title}")

            # Process images in the content
            processed_content, image_map = process_and_replace_images(raw_content, session, url)
            debug_log(f"Processed {len(image_map)} images")

            # Process text content
            text_content = BeautifulSoup(processed_content, 'html.parser').get_text('\n', strip=True)
            processed_text = process_content_sections(text_content)
            debug_log("Content processed with OpenAI")

            # Merge processed text
            final_content = BeautifulSoup(processed_content, 'html.parser')
            paragraphs = final_content.find_all(['p', 'div'], string=True)
            text_sections = re.split(r'\n\s*\n', processed_text)

            for p, new_text in zip(paragraphs, text_sections):
                if p.name == 'img' or not p.get_text(strip=True):
                    continue
                p.clear()
                p.append(new_text)

            # Upload final post
            final_html = str(final_content)
            debug_log(f"Final HTML length: {len(final_html)} characters")
            post = WordPressPost()
            post.title = new_title
            post.content = final_html
            post.post_status = 'publish'
            post_id = wp_client.call(NewPost(post))

            if post_id:
                print(f"✅ Success! Post ID: {post_id}")
                print(f"📝 Content length: {len(final_html)}")
                print(f"🖼️ Images uploaded: {len(image_map)}")
                return True

        except Exception as e:
            debug_log(f"🔥 Critical error: {str(e)}")

        return False

if __name__ == '__main__':
    blog_url = input("Enter blog post URL: ").strip()
    if process_blog_post(blog_url):
        print("🎉 Process completed successfully!")
    else:
        print("⛔️ Process failed. Check debug logs.")
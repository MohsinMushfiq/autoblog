# Blog Post Processor and Uploader

This script processes blog posts, enhances content using OpenAI, and publishes them to WordPress.

---

## Requirements

1. **Python 3.12 or higher** (get it from [Python](https://www.python.org/downloads/)).
2. **WordPress XML-RPC** enabled on your site.
3. **OpenAI API Key** (get it from [OpenAI](https://openai.com/api/)).

---

## Steps to Run

### 1. Download the Script
Download the script file (e.g., `blog_processor.py`) to your computer.

### 2. Install Required Libraries
Run the following command to install dependencies:
```bash
pip install requests openai python-wordpress-xmlrpc beautifulsoup4 lxml
````

### 3. Set Up Credentials
```bash
WORDPRESS_URL=https://your-wordpress-site.com/xmlrpc.php
WORDPRESS_USER=""
WORDPRESS_PASSWORD=""
OPENAI_API_KEY=""
````

### 4. Run the Script
Run the following command to Execute the script:
```bash
python blog_processor.py
````

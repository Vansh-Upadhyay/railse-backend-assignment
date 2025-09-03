import os
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
import google.auth
import google.auth.transport.requests
import re
import csv
import asyncio
import json
import time
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from typing import Dict, List, Tuple
import concurrent.futures
from pathlib import Path
import re as _re


# Disable OAuthlib's HTTPS verification when running locally.
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Import configuration
try:
    from config import *
except ImportError:
    # Fallback configuration if config.py is not found
    CLIENT_SECRETS_FILE = "client_secret.json"
    TOKEN_FILE = "token.json"
    SCOPES = ['https://www.googleapis.com/auth/youtube']
    GEMINI_CHAT_URL = "https://gemini.google.com/app/d7ad065476069e3d"
    VIDEOS_CSV_FILE = "videos.csv"
    LOG_FILE = "youtube_automation_log.txt"
    PROGRESS_FILE = "progress.json"
    VIDEO_LIMIT = 10
    PARALLEL_LIMIT = 2
    BATCH_DELAY = 5
    GEMINI_RESPONSE_WAIT = 30
    BROWSER_PROFILE_DIR = "./gemini_profile"
    BROWSER_PROFILE_DIR_EVEN = "C:/AnnotationBot/ProfileEven"
    BROWSER_PROFILE_DIR_ODD = "C:/AnnotationBot/ChromeProfile"
    BROWSER_CHANNEL = "chrome"
    BROWSER_HEADLESS = False
    BROWSER_TIMEOUT = 15000
    MAX_RETRIES = 3
    RETRY_DELAY = 5
    
    # Field mapping for Gemini response parsing
    FIELD_MAP = {
        "1": "title",
        "2": "description", 
        "3": "tags"
    }

def sanitize_tags(tags_text: str) -> List[str]:
    if not tags_text:
        return []
    # Split by comma
    tags = [t.strip() for t in tags_text.split(",")]
    # Remove empty or invalid tags
    tags = [t for t in tags if t]
    # Enforce YouTube limits (≤30 chars each, ≤500 total)
    tags = [t[:30] for t in tags]
    total_len = 0
    valid_tags = []
    for t in tags:
        if total_len + len(t) <= 500:
            valid_tags.append(t)
            total_len += len(t)
        else:
            break
    return valid_tags

def log_message(msg: str):
    """Log message to console and file"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_msg + '\n')

def get_authenticated_service():
    """Authenticate with YouTube API"""
    credentials = None
    
    if os.path.exists(TOKEN_FILE):
        credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(google.auth.transport.requests.Request())
        else:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, SCOPES)
            credentials = flow.run_local_server(port=0)
        
        with open(TOKEN_FILE, 'w') as token:
            token.write(credentials.to_json())
    
    return build('youtube', 'v3', credentials=credentials)

def get_channel_id(youtube_service):
    """Get the authenticated user's channel ID"""
    try:
        request = youtube_service.channels().list(part="id", mine=True)
        response = request.execute()
        
        if response['items']:
            return response['items'][0]['id']
        else:
            log_message("❌ No channel found for authenticated user")
            return None
    except Exception as e:
        log_message(f"❌ Error getting channel ID: {e}")
        return None

def fetch_all_channel_videos(youtube_service, max_results=50):
    """Fetch all videos from the authenticated user's channel"""
    try:
        channel_id = get_channel_id(youtube_service)
        if not channel_id:
            return []
        
        log_message(f"📺 Fetching videos from channel ID: {channel_id}")
        
        videos = []
        next_page_token = None
        
        while True:
            # Get videos from channel
            request = youtube_service.search().list(
                part="id,snippet",
                channelId=channel_id,
                type="video",
                maxResults=min(50, max_results - len(videos)),
                pageToken=next_page_token,
                order="date"
            )
            
            response = request.execute()
            
            for item in response['items']:
                video_id = item['id']['videoId']
                video_title = item['snippet']['title']
                
                # Get video details to determine if it's a short
                video_details = youtube_service.videos().list(
                    part="contentDetails",
                    id=video_id
                ).execute()
                
                if video_details['items']:
                    duration = video_details['items'][0]['contentDetails']['duration']
                    # YouTube Shorts are typically 60 seconds or less
                    # Parse ISO 8601 duration (PT1M30S = 1 minute 30 seconds)
                    duration_seconds = parse_duration_to_seconds(duration)
                    
                    if duration_seconds <= 60:
                        # It's a short
                        video_url = f"https://www.youtube.com/shorts/{video_id}"
                    else:
                        # It's a regular video
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                    
                    videos.append((str(len(videos) + 1), video_url))
                    log_message(f"📹 Found video: {video_title} ({'Short' if duration_seconds <= 60 else 'Regular'})")
            
            # Check if there are more pages
            next_page_token = response.get('nextPageToken')
            if not next_page_token or len(videos) >= max_results:
                break
        
        log_message(f"✅ Found {len(videos)} videos from your channel")
        return videos
        
    except Exception as e:
        log_message(f"❌ Error fetching channel videos: {e}")
        return []

def parse_duration_to_seconds(duration):
    """Parse YouTube duration format (PT1M30S) to seconds"""
    import re
    
    # Remove PT prefix
    duration = duration[2:]
    total_seconds = 0
    
    # Extract hours
    hours_match = re.search(r'(\d+)H', duration)
    if hours_match:
        total_seconds += int(hours_match.group(1)) * 3600
    
    # Extract minutes
    minutes_match = re.search(r'(\d+)M', duration)
    if minutes_match:
        total_seconds += int(minutes_match.group(1)) * 60
    
    # Extract seconds
    seconds_match = re.search(r'(\d+)S', duration)
    if seconds_match:
        total_seconds += int(seconds_match.group(1))
    
    return total_seconds

def get_video_id_from_url(url: str) -> str:
    """Extract video ID from YouTube URL"""
    # Handle YouTube Shorts URLs
    shorts_match = re.search(r"youtube\.com\/shorts\/([A-Za-z0-9_-]{11})", url)
    if shorts_match:
        return shorts_match.group(1)
    # General patterns (watch?v=, youtu.be, embed, etc.)
    regex = r"(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e|embed)\/|.*[?&]v=)|youtu\.be\/)([^\"&?\/\s]{11})"
    match = re.search(regex, url)
    return match.group(1) if match else None

def update_video_metadata(youtube_service, video_id: str, new_title: str = None, 
                         new_description: str = None, new_tags: List[str] = None):
    """Update video metadata using YouTube API"""
    try:
        # Get current video metadata
        videos_list_response = youtube_service.videos().list(
            id=video_id,
            part='snippet'
        ).execute()

        if not videos_list_response['items']:
            log_message(f"Error: Video with ID '{video_id}' not found.")
            return False

        existing_snippet = videos_list_response['items'][0]['snippet']

        # Prepare update body
        update_body = {
            'id': video_id,
            'snippet': {
                'categoryId': existing_snippet['categoryId']
            }
        }

        # Only update fields that are provided
        if new_title:
            update_body['snippet']['title'] = new_title
        if new_description:
            update_body['snippet']['description'] = new_description
        if new_tags:
            update_body['snippet']['tags'] = new_tags

        # Execute update
        request = youtube_service.videos().update(
            part='snippet',
            body=update_body
        )
        response = request.execute()

        log_message(f"✅ Video '{response['snippet']['title']}' updated successfully!")
        return True

    except HttpError as e:
        log_message(f"❌ HTTP error occurred: {e}")
        return False
    except Exception as e:
        log_message(f"❌ Unexpected error occurred: {e}")
        return False

def parse_gemini_response(html_content: str) -> Dict[str, str]:
    """Parse Gemini response HTML to extract Optimized Title, Description, and Tags.

    Robust to headings like <h3><b>Optimized Title:</b></h3> and content in following <p>.
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # Find model responses and prefer the last one that contains optimized sections
    response_blocks = soup.find_all("message-content", class_="model-response-text")
    if not response_blocks:
        return {}

    def block_has_sections(block) -> bool:
        for h3 in block.find_all("h3"):
            b = h3.find("b")
            text = (b.get_text(strip=True) if b else h3.get_text(strip=True)).lower()
            if any(x in text for x in ["optimized title", "optimized description", "optimized tags"]):
                return True
        return False

    latest_block = None
    for block in reversed(response_blocks):
        if block_has_sections(block):
            latest_block = block
            break
    if latest_block is None:
        latest_block = response_blocks[-1]

    def find_section_p_text(block, label: str) -> str:
        for h3 in block.find_all("h3"):
            b = h3.find("b")
            heading = (b.get_text(strip=True) if b else h3.get_text(strip=True))
            if label.lower() in heading.lower():
                # Iterate over following siblings until we find a non-empty <p>
                node = h3.find_next_sibling()
                while node is not None and node.name != "h3":
                    if node.name == "p":
                        # Prefer bold text inside <p> if present
                        pb = node.find("b")
                        text = (pb.get_text(strip=True) if pb else node.get_text(strip=True))
                        if text:
                            return text
                    node = node.find_next_sibling()
                return ""
        return ""

    # Title
    title = find_section_p_text(latest_block, "Optimized Title")

    # Description: collect all sibling nodes until next h3
    description = ""
    desc_anchor = None
    for h3 in latest_block.find_all("h3"):
        b = h3.find("b")
        heading = (b.get_text(strip=True) if b else h3.get_text(strip=True))
        if "optimized description" in heading.lower():
            desc_anchor = h3
            break

    if desc_anchor is not None:
        parts: List[str] = []
        node = desc_anchor.find_next_sibling()
        while node and node.name != "h3":
            if node.name in ["p", "li"]:
                parts.append(node.get_text(" ", strip=True))

            elif node.name == "ul":
                # Check if this UL follows a "You should also checkout this" anchor
                prev = node.find_previous_sibling()
                if prev and "checkout this" in prev.get_text(strip=True).lower():
                    items = []
                    for idx, li in enumerate(node.find_all("li"), start=1):
                        text = li.get_text(" ", strip=True)
                        # Extract the first link inside li
                        link = li.find("a")
                        url = link["href"] if link else ""
                        # Clean up text: remove duplicate url if present
                        if url and url in text:
                            text = text.replace(url, "").strip()
                        items.append(f"{idx}️⃣ {text}\n🔗 {url}" if url else f"{idx}️⃣ {text}")
                    parts.append("👉 You should also checkout this:\n\n" + "\n\n".join(items))
                else:
                    # Normal UL parsing
                    for li in node.find_all("li"):
                        parts.append(li.get_text(" ", strip=True))

            elif isinstance(node, str):  # bare text (like "Related Search Terms:")
                text = node.strip()
                if text:
                    if text.lower().startswith("related search terms:"):
                        parts.append(text.replace("Related Search Terms:", "Related Search Terms:\n"))
                    else:
                        parts.append(text)

            node = node.find_next_sibling()

        description = "\n\n".join(parts)

    # Tags
    tags_text = find_section_p_text(latest_block, "Optimized Tags")

    return {
        "title": title.strip(),
        "description": description.strip(),
        "tags": tags_text.strip()
    }

async def get_gemini_optimization(page, video_url: str) -> Dict[str, str]:
    """Get SEO optimization from Gemini by sending only the video URL.

    Assumes the Gemini chat is pre-configured. Polls until response appears.
    """
    try:
        await page.goto(GEMINI_CHAT_URL)
        await page.wait_for_load_state("domcontentloaded")
        
        # Attempt to send URL up to 2 times if page navigates unexpectedly
        for attempt in range(2):
            # Ensure we're on the chat URL
            if page.url.startswith("about:blank"):
                await page.goto(GEMINI_CHAT_URL)
                await page.wait_for_load_state("domcontentloaded")

            # Count existing responses to detect a new one
            initial_html = await page.content()
            initial_data = parse_gemini_response(initial_html)
            
            # Focus chat input and send only the URL
            await page.wait_for_selector('div.ql-editor', timeout=BROWSER_TIMEOUT)
            await page.fill('div.ql-editor', video_url)
            await page.click('button.send-button')

            # Give Gemini time to generate before polling
            await asyncio.sleep(35)

            # Poll up to ~5 minutes for an answer containing optimized sections
            deadline = time.time() + 300
            while time.time() < deadline:
                await asyncio.sleep(3)
                # If the page navigated to about:blank, break and retry once
                if page.url.startswith("about:blank"):
                    break
                html = await page.content()
                optimization_data = parse_gemini_response(html)
                # Return when any field is present
                if optimization_data.get("title") or optimization_data.get("description") or optimization_data.get("tags"):
                    return optimization_data

        # Final attempt on current page
        html = await page.content()
        return parse_gemini_response(html)
        
    except Exception as e:
        log_message(f"❌ Error getting Gemini optimization: {e}")
        return {}

def load_videos_from_csv() -> List[Tuple[str, str]]:
    """Load videos from CSV file"""
    videos = []
    try:
        with open(VIDEOS_CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    # Skip header row if present
                    if row[0].strip().lower().startswith('video'):
                        continue
                    video_number = row[0].strip()
                    video_url = row[1].strip()
                    videos.append((video_number, video_url))
    except FileNotFoundError:
        log_message(f"⚠️ CSV file '{VIDEOS_CSV_FILE}' not found. Creating sample file...")
        create_sample_csv()
        return []
    
    return videos

def create_sample_csv():
    """Create a sample CSV file"""
    sample_data = [
        ["1", "https://www.youtube.com/watch?v=EXAMPLE1"],
        ["2", "https://www.youtube.com/watch?v=EXAMPLE2"],
        ["3", "https://www.youtube.com/watch?v=EXAMPLE3"]
    ]
    
    with open(VIDEOS_CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Video Number", "YouTube URL"])
        writer.writerows(sample_data)
    
    log_message(f"📝 Created sample CSV file: {VIDEOS_CSV_FILE}")

def get_user_choice() -> Tuple[int, List[int]]:
    """Get user choice for update type and fields"""
    print("\n" + "="*60)
    print("🎬 YOUTUBE STUDIO AUTOMATION SOFTWARE")
    print("="*60)
    
    # Get update type
    print("\n1. Update specific video")
    print("2. Update all videos from your channel")
    
    while True:
        try:
            choice = int(input("\nEnter your choice (1 or 2): "))
            if choice in [1, 2]:
                break
            else:
                print("❌ Please enter 1 or 2")
        except ValueError:
            print("❌ Please enter a valid number")
    
    # Get fields to update
    print("\nWhich fields do you want to update?")
    print("1. Title")
    print("2. Description") 
    print("3. Tags")
    print("\nEnter multiple choices separated by commas (e.g., '1,2' or '1,2,3'): ")
    
    while True:
        try:
            field_input = input("Enter field numbers: ").strip()
            field_numbers = [int(x.strip()) for x in field_input.split(',')]
            
            if all(f in [1, 2, 3] for f in field_numbers):
                break
            else:
                print("❌ Please enter valid field numbers (1, 2, or 3)")
        except ValueError:
            print("❌ Please enter valid numbers separated by commas")
    
    return choice, field_numbers

def get_specific_video_choice(videos: List[Tuple[str, str]]) -> int:
    """Get user choice for specific video"""
    print(f"\n📋 Available videos ({len(videos)} total):")
    for i, (video_num, url) in enumerate(videos, 1):
        print(f"{i}. Video {video_num}: {url}")
    
    while True:
        try:
            choice = int(input(f"\nEnter video number (1-{len(videos)}): "))
            if 1 <= choice <= len(videos):
                return choice - 1
            else:
                print(f"❌ Please enter a number between 1 and {len(videos)}")
        except ValueError:
            print("❌ Please enter a valid number")

def format_description_for_youtube(raw_description: str) -> str:
    """Normalize spacing and newlines in description to improve readability.

    - Ensure a space before URLs after colons (":https://" -> ": https://")
    - Put common bullet markers on their own lines (✅, 📸, 📢, 📧)
    - Ensure a newline after headings like "Join our Family:" and "About Me:"
    """
    if not raw_description:
        return raw_description

    desc = raw_description
    # Space before URLs following a colon
    desc = _re.sub(r":(https?://)", r": \1", desc)
    # Ensure bullets/emojis start on new line
    desc = _re.sub(r"(?<!\n)(✅|📸|📢|📧)", r"\n\1", desc)
    # Ensure heading newlines
    desc = desc.replace("Join our Family:", "Join our Family:\n")
    desc = desc.replace("About Me:", "About Me: ")
    # Collapse excessive spaces
    desc = _re.sub(r"[ \t]+\n", "\n", desc)
    return desc.strip()

async def process_single_video(video_number: str, video_url: str, fields_to_update: List[int], 
                             youtube_service, browser_context) -> bool:
    """Process a single video with Gemini optimization"""
    try:
        log_message(f"🎬 Processing Video {video_number}: {video_url}")
        
        # Create new page for Gemini
        page = await browser_context.new_page()
        
        # Get optimization from Gemini
        log_message(f"🤖 Getting Gemini optimization for Video {video_number}...")
        optimization = await get_gemini_optimization(page, video_url)
        
        if not optimization:
            log_message(f"❌ Failed to get Gemini optimization for Video {video_number}")
            await page.close()
            return False
        
        # Extract video ID
        video_id = get_video_id_from_url(video_url)
        if not video_id:
            log_message(f"❌ Could not extract video ID from URL: {video_url}")
            await page.close()
            return False
        
        # Prepare update data
        update_title = optimization.get("title") if "1" in [str(f) for f in fields_to_update] else None
        update_description = optimization.get("description") if "2" in [str(f) for f in fields_to_update] else None
        update_tags = None
        if "3" in [str(f) for f in fields_to_update]:
            raw_tags = optimization.get("tags")
            update_tags = sanitize_tags(raw_tags)

        # Basic validation to avoid invalid/empty title/description
        if update_title is not None:
            update_title = update_title.strip()
            if not update_title:
                log_message(f"❌ Empty title generated for Video {video_number}. Skipping update.")
                await page.close()
                return False
            if len(update_title) > 100:
                update_title = update_title[:100]
        if update_description is not None:
            update_description = format_description_for_youtube(update_description.strip())
            if len(update_description) > 4900:
                update_description = update_description[:4900]
        
        # Update video metadata
        log_message(f"📝 Updating Video {video_number} metadata...")
        success = update_video_metadata(
            youtube_service, video_id, update_title, update_description, update_tags
        )
        
        await page.close()
        return success
        
    except Exception as e:
        log_message(f"❌ Error processing Video {video_number}: {e}")
        return False

async def process_all_videos(videos: List[Tuple[str, str]], fields_to_update: List[int], 
                           youtube_service, browser_context_even, browser_context_odd) -> None:
    """Process all videos in parallel (2 at a time)"""
    log_message(f"🚀 Starting parallel processing of {len(videos)} videos...")
    
    # Process videos in pairs for parallel execution
    for i in range(0, len(videos), 2):
        batch = videos[i:i+2]
        tasks = []
        
        for idx, (video_num, video_url) in enumerate(batch):
            # Alternate between even/odd contexts to use your logged-in profiles
            ctx = browser_context_even if (i + idx) % 2 == 0 else browser_context_odd
            task = process_single_video(video_num, video_url, fields_to_update, youtube_service, ctx)
            tasks.append(task)
        
        # Execute batch in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log results
        for j, (video_num, video_url) in enumerate(batch):
            if isinstance(results[j], Exception):
                log_message(f"❌ Video {video_num} failed with error: {results[j]}")
            elif results[j]:
                log_message(f"✅ Video {video_num} processed successfully")
            else:
                log_message(f"❌ Video {video_num} failed to process")
        
        # Small delay between batches
        if i + 2 < len(videos):
            await asyncio.sleep(BATCH_DELAY)

async def process_videos_staggered(videos: List[Tuple[str, str]], fields_to_update: List[int], 
                                 youtube_service, browser_context_even, browser_context_odd, 
                                 stagger_seconds: int = 35) -> None:
    """Start two videos in parallel but stagger the second by N seconds, then proceed in pairs."""
    log_message(f"🚀 Starting staggered parallel processing of {len(videos)} videos (stagger={stagger_seconds}s)...")
    for i in range(0, len(videos), 2):
        batch = videos[i:i+2]
        tasks: List[asyncio.Task] = []

        # First starts immediately
        if len(batch) >= 1:
            video_num_1, url_1 = batch[0]
            ctx1 = browser_context_even if (i % 2 == 0) else browser_context_odd
            tasks.append(asyncio.create_task(process_single_video(video_num_1, url_1, fields_to_update, youtube_service, ctx1)))

        # Second starts after delay
        if len(batch) == 2:
            video_num_2, url_2 = batch[1]
            ctx2 = browser_context_odd if (i % 2 == 0) else browser_context_even

            async def delayed_start():
                await asyncio.sleep(stagger_seconds)
                return await process_single_video(video_num_2, url_2, fields_to_update, youtube_service, ctx2)

            tasks.append(asyncio.create_task(delayed_start()))

        # Await both for this pair
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for j, (video_num, _) in enumerate(batch):
            if isinstance(results[j], Exception):
                log_message(f"❌ Video {video_num} failed with error: {results[j]}")
            elif results[j]:
                log_message(f"✅ Video {video_num} processed successfully")
            else:
                log_message(f"❌ Video {video_num} failed to process")

async def main():
    """Main function"""
    try:
        # Initialize logging
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)
        
        log_message("🚀 Starting YouTube Studio Automation Software")
        
        # Get user choices
        update_type, fields_to_update = get_user_choice()
        
        # Initialize YouTube service
        log_message("🔐 Authenticating with YouTube API...")
        youtube_service = get_authenticated_service()
        log_message("✅ YouTube API authentication successful")
        
        # Get videos based on user choice
        if update_type == 1:
            # Load videos from CSV for specific video selection
            videos = load_videos_from_csv()
            if not videos:
                log_message("❌ No videos found. Please check your CSV file.")
                return
            
            # Get specific video choice
            video_index = get_specific_video_choice(videos)
            selected_video = videos[video_index]
            videos = [selected_video]
            
        else:  # update_type == 2
            # Fetch all videos from channel
            log_message("📺 Fetching all videos from your YouTube channel...")
            videos = fetch_all_channel_videos(youtube_service, max_results=50)
            if not videos:
                log_message("❌ No videos found on your channel.")
                return
        
        # Initialize browser for Gemini with your logged-in Chrome profiles
        log_message("🌐 Initializing browsers (even/odd profiles) for Gemini...")
        async with async_playwright() as playwright:
            browser_even = await playwright.chromium.launch_persistent_context(
                user_data_dir=BROWSER_PROFILE_DIR_EVEN,
                channel=BROWSER_CHANNEL,
                headless=BROWSER_HEADLESS
            )
            browser_odd = await playwright.chromium.launch_persistent_context(
                user_data_dir=BROWSER_PROFILE_DIR_ODD,
                channel=BROWSER_CHANNEL,
                headless=BROWSER_HEADLESS
            )
            
            try:
                if update_type == 1:  # Specific video → start first two automatically with stagger
                    log_message("🎯 Specific mode selected → starting 2 videos automatically with 35s stagger...")
                    first_two = videos[:2]
                    await process_videos_staggered(first_two, fields_to_update, youtube_service, browser_even, browser_odd, stagger_seconds=35)
                else:  # All videos
                    log_message("🔄 Processing all videos in staggered parallel mode (2 at a time)...")
                    await process_videos_staggered(videos, fields_to_update, youtube_service, browser_even, browser_odd, stagger_seconds=35)
                    log_message("✅ All videos processed!")
            
            finally:
                await browser_even.close()
                await browser_odd.close()
        
        log_message("🎉 YouTube Studio Automation completed!")
        
    except KeyboardInterrupt:
        log_message("⚠️ Process interrupted by user")
    except Exception as e:
        log_message(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
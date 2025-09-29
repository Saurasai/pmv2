import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import logging
import re
import asyncio
import streamlit.components.v1 as components
from api import generate_platform_drafts
from config import PROMPT_TEMPLATES
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
API_BASE_URL = os.getenv("API_BASE_URL", "https://pmv2-production.up.railway.app/api")
logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Config
PLATFORMS = ["bluesky", "facebook", "gmb", "instagram", "linkedin", "pinterest", "reddit", "snapchat", "telegram", "tiktok", "threads", "twitter", "youtube"]
TONE_OPTIONS = ["Professional", "Casual", "Excited"]
st.set_page_config(page_title="🌟 Post Muse", layout="wide", initial_sidebar_state="expanded")

# Social media platform URLs
PLATFORM_URLS = {
    "twitter": "https://twitter.com",
    "linkedin": "https://www.linkedin.com",
    "instagram": "https://www.instagram.com"
}

def clean_draft_content(draft: str) -> str:
    return re.sub(r'^\d+\.\s*', '', draft.strip(), count=1)

def get_user_info(api_key: str) -> dict:
    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        with st.spinner("🔄 Loading user profile..."):
            response = requests.get(f"{API_BASE_URL}/user", headers=headers, timeout=5)
            response.raise_for_status()
            user_info = response.json()
            logger.info(f"User info fetched for api_key: {api_key[:4]}... - {user_info}")
            return user_info
    except requests.HTTPError as e:
        logger.error(f"Failed to fetch user info: {str(e)}, response: {e.response.text if e.response else 'No response'}")
        st.warning("⚠️ Could not load user profile. Defaulting to non-admin.")
        return {"is_admin": False}
    except Exception as e:
        logger.error(f"Error fetching user info: {str(e)}")
        st.warning(f"⚠️ Error loading profile: {str(e)}")
        return {"is_admin": False}

async def simulate_progress(progress_bar):
    for i in range(100):
        progress_bar.progress(i + 1)
        await asyncio.sleep(0.02)

def login():
    with st.container(border=True):
        st.markdown("## 🔐 Welcome to Post Muse")
        st.markdown("Create and share vibrant social media posts! 🚀")
        auth_option = st.selectbox("Action", ["Login", "Register"], key="auth_option", help="Choose to log in or register")
        
        with st.form(key="auth_form"):
            if auth_option == "Login":
                email = st.text_input("📧 Email", placeholder="your@email.com", key="login_email")
                password = st.text_input("🔒 Password", type="password", placeholder="Enter password", key="login_pass")
                submit_button = st.form_submit_button("🚀 Log In", type="primary")
                if submit_button:
                    with st.spinner("🔄 Logging in..."):
                        try:
                            response = requests.post(
                                f"{API_BASE_URL}/login",
                                json={"email": email.lower(), "password": password},
                                headers={"Content-Type": "application/json"},
                                timeout=5
                            )
                            response.raise_for_status()
                            response_json = response.json()
                            st.session_state.user = {"email": email.lower(), "api_key": response_json["api_key"]}
                            st.success("🎉 Logged in successfully!")
                            st.balloons()
                            logger.info(f"Login successful for {email}")
                            st.rerun()
                        except requests.HTTPError as e:
                            error_msg = e.response.json().get('detail', 'Unknown error') if e.response else str(e)
                            st.error(f"❌ Login failed: {error_msg}")
                            logger.warning(f"Login failed for {email}: {e.response.text if e.response else str(e)}")
                        except requests.ConnectionError:
                            st.error(f"❌ Cannot connect to server at {API_BASE_URL}.")
                            logger.error(f"Connection error for {email}: Server not reachable")
                        except requests.Timeout:
                            st.error("❌ Request timed out. Check network or server status.")
                            logger.error(f"Timeout error for {email}")
                        except Exception as e:
                            st.error(f"❌ Login error: {str(e)}")
                            logger.error(f"Login error for {email}: {str(e)}")
            else:
                email = st.text_input("📧 Email", placeholder="your@email.com", key="reg_email")
                password = st.text_input("🔒 Password", type="password", placeholder="Enter password", key="reg_pass")
                confirm_password = st.text_input("🔒 Confirm Password", type="password", placeholder="Confirm password", key="reg_pass2")
                is_admin = st.checkbox("🛡️ Register as Admin", key="reg_is_admin", help="Requires admin secret")
                admin_secret = st.text_input("🔑 Admin Secret", type="password", placeholder="Enter admin secret", key="reg_admin_secret") if is_admin else None
                submit_button = st.form_submit_button("🌟 Register", type="primary")
                if submit_button:
                    if password != confirm_password:
                        st.error("❌ Passwords do not match")
                        logger.warning("Password mismatch during registration")
                        return
                    with st.spinner("🔄 Registering..."):
                        try:
                            payload = {
                                "email": email.lower(),
                                "password": password,
                                "confirm_password": confirm_password,
                                "tier": "free",
                                "is_admin": is_admin,
                                "admin_secret": admin_secret if is_admin else None
                            }
                            logger.info(f"Sending registration request for {email}: {payload}")
                            response = requests.post(f"{API_BASE_URL}/user", json=payload, headers={"Content-Type": "application/json"}, timeout=5)
                            response.raise_for_status()
                            response_json = response.json()
                            st.session_state.user = {"email": email.lower(), "api_key": response_json["api_key"]}
                            st.success(f"🎉 Registered successfully! API Key: {response_json['api_key']}")
                            st.balloons()
                            logger.info(f"Registered user: {email}, is_admin: {is_admin}, api_key: {response_json['api_key']}")
                            st.rerun()
                        except requests.HTTPError as e:
                            error_msg = e.response.json().get('detail', 'Unknown error') if e.response else str(e)
                            st.error(f"❌ Registration failed: {error_msg}")
                            logger.warning(f"Registration failed for {email}: {e.response.text if e.response else str(e)}")
                        except requests.ConnectionError:
                            st.error(f"❌ Cannot connect to server at {API_BASE_URL}.")
                            logger.error(f"Connection error for {email}: Server not reachable")
                        except requests.Timeout:
                            st.error("❌ Request timed out. Check network or server status.")
                            logger.error(f"Timeout error for {email}")
                        except Exception as e:
                            st.error(f"❌ Registration error: {str(e)}")
                            logger.error(f"Registration error for {email}: {str(e)}")

if "user" not in st.session_state:
    login()
    st.stop()

# Sidebar: User Info and Logout
with st.sidebar:
    with st.container(border=True):
        st.markdown("## 👤 Profile")
        user_email = st.session_state.user.get('email', 'Unknown')
        user_info = get_user_info(st.session_state.user.get('api_key', ''))
        st.markdown(f"**Email**: {user_email}")
        st.markdown(f"**Tier**: {user_info.get('tier', 'Free')}")
        st.markdown(f"**Status**: {'🛡️ Admin' if user_info.get('is_admin', False) else '🌟 User'}")
        if st.button("🚪 Log Out", type="primary", key="logout"):
            st.session_state.clear()
            st.success("🎉 Logged out successfully!")
            st.snow()
            logger.info(f"User {user_email} logged out")
            st.rerun()

# Main Title
st.markdown("# 🌟 Post Muse")
st.markdown("Craft vibrant, platform-ready social media posts! 🚀")

# Determine if user is admin
api_key = st.session_state.user.get("api_key", "")
if not api_key:
    st.error("❌ No API key found. Please log in again.")
    logger.error("No API key in session state")
    st.stop()
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
user_info = get_user_info(api_key)
is_admin = user_info.get("is_admin", False)

# Tabs
tab1, tab2, tab3 = st.tabs(["📝 Create", "💾 Drafts", "⚙️ Settings"])

with tab1:
    with st.container(border=True):
        st.markdown("## 📝 Create Post")
        st.markdown("Unleash your ideas and generate posts! 🌈")
        col1, col2 = st.columns([1, 1], gap="medium")
        with col1:
            topic = st.text_input("🧠 Topic", placeholder="e.g., Smart AI Writing Tool", key="topic")
            hashtags = st.text_input("🐦 Hashtags", placeholder="e.g., #AI #Productivity", key="hashtags")
        with col2:
            insight = st.text_area("💼 Story", placeholder="Share your insight...", height=100, key="insight")
            tone = st.selectbox("🎨 Tone", TONE_OPTIONS, index=1, key="tone", help="Set the post vibe")
        
        if st.button("🚀 Generate Posts", key="generate_drafts", type="primary"):
            if not topic.strip():
                st.error("❌ Please enter a topic to generate posts.")
            else:
                with st.spinner("🌟 Creating your posts..."):
                    progress_bar = st.progress(0)
                    try:
                        asyncio.run(simulate_progress(progress_bar))
                        draft_platforms = ["twitter", "linkedin", "instagram"]
                        tasks = [generate_platform_drafts(p, {
                            "topic": topic,
                            "hashtags": hashtags,
                            "insight": insight,
                            "tone": tone
                        }, PROMPT_TEMPLATES) for p in draft_platforms]
                        results = asyncio.run(asyncio.gather(*tasks))
                        st.session_state.drafts = {p: [clean_draft_content(d) for d in d] for p, d in zip(draft_platforms, results)}
                        st.success("🎉 Posts generated! Check them below.")
                        st.balloons()
                        logger.info("Drafts generated successfully")
                    except Exception as e:
                        st.error(f"❌ Generation failed: {str(e)}")
                        logger.error(f"Draft generation failed: {str(e)}")
                    progress_bar.empty()

    with st.container(border=True):
        st.markdown("## 📬 Your Posts")
        draft_platforms = ["twitter", "linkedin", "instagram"]
        tabs = st.tabs([f"🐦 Twitter" if p == "twitter" else f"💼 LinkedIn" if p == "linkedin" else f"📸 Instagram" for p in draft_platforms])
        for tab, platform in zip(tabs, draft_platforms):
            with tab:
                drafts = st.session_state.get("drafts", {}).get(platform, [])
                if not drafts:
                    st.info(f"ℹ️ No posts for {platform.capitalize()}. Generate some above! 😊")
                else:
                    st.markdown(f"[Visit {platform.capitalize()}]({PLATFORM_URLS.get(platform, '#')}) 🌐")
                    for i, draft in enumerate(drafts, 1):
                        with st.expander(f"Post {i} for {platform.capitalize()}", expanded=True):
                            draft_key = f"{platform}_{i}_edit"
                            edited_draft = st.text_area(f"✍️ Edit Post", value=draft, key=draft_key, height=100)
                            if edited_draft != draft:
                                st.session_state.drafts[platform][i-1] = edited_draft
                                st.info(f"✨ Post {i} updated for {platform.capitalize()}!")
                                logger.debug(f"Draft {i} edited for {platform}")
                            col1, col2, col3 = st.columns([0.6, 0.2, 0.2])
                            with col1:
                                st.markdown(f"**Content**: {edited_draft}")
                            with col2:
                                copy_key = f"{platform}_{i}_copy"
                                if copy_key not in st.session_state:
                                    st.session_state[copy_key] = False
                                copy_script = f"""
                                <button onclick="copyToClipboard()">📋 Copy</button>
                                <script>
                                function copyToClipboard() {{
                                    navigator.clipboard.writeText(`{edited_draft.replace("`", "\\`").replace("\n", "\\n").replace('"', '\\"').replace("'", "\\'")}`)
                                        .then(() => {{
                                            const input = document.createElement('input');
                                            input.id = '{copy_key}';
                                            input.value = 'copied';
                                            document.body.appendChild(input);
                                            input.dispatchEvent(new Event('change'));
                                            input.remove();
                                        }})
                                        .catch(err => alert("Failed to copy: " + err));
                                }}
                                </script>
                                """
                                components.html(copy_script, height=50)
                                copy_trigger = st.text_input("", key=copy_key, label_visibility="hidden")
                                if copy_trigger == "copied":
                                    st.success(f"🎉 Copied post {i} to clipboard!")
                                    st.balloons()
                                    logger.debug(f"Draft {i} copied for {platform}")
                                    st.session_state[copy_key] = False
                            with col3:
                                if st.button("💾 Save", key=f"{platform}_{i}_save"):
                                    payload = {"content": clean_draft_content(edited_draft), "platform": platform}
                                    with st.spinner(f"🔄 Saving to {platform.capitalize()}..."):
                                        try:
                                            response = requests.post(f"{API_BASE_URL}/draft", json=payload, headers=headers, timeout=5)
                                            response.raise_for_status()
                                            st.success(f"🎉 Post saved for {platform.capitalize()}!")
                                            st.snow()
                                            logger.info(f"Draft saved for {platform} by {st.session_state.user['email']}")
                                        except requests.HTTPError as e:
                                            error_msg = e.response.json().get('detail', 'Unknown error') if e.response else str(e)
                                            st.error(f"❌ Failed to save: {error_msg}")
                                            logger.warning(f"Draft save failed for {platform}: {e.response.text if e.response else str(e)}")
                                        except requests.ConnectionError:
                                            st.error(f"❌ Cannot connect to server at {API_BASE_URL}.")
                                            logger.error(f"Connection error for {platform} draft save")
                                        except requests.Timeout:
                                            st.error("❌ Request timed out. Check network or server status.")
                                            logger.error(f"Timeout error for {platform} draft save")
                                        except Exception as e:
                                            st.error(f"❌ Failed to save: {str(e)}")
                                            logger.error(f"Draft save failed for {platform}: {str(e)}")
                            if platform != "twitter" or is_admin:
                                if st.button(f"📤 Post", key=f"{platform}_{i}_post", type="primary"):
                                    cleaned_draft = clean_draft_content(edited_draft)
                                    payload = {"post": cleaned_draft, "platforms": [platform]}
                                    with st.spinner(f"📬 Posting to {platform.capitalize()}..."):
                                        try:
                                            response = requests.post(f"{API_BASE_URL}/post", json=payload, headers=headers, timeout=5)
                                            response.raise_for_status()
                                            response_json = response.json()
                                            post_ids = response_json["postIds"]
                                            for p in post_ids:
                                                if p["platform"] == platform and p["status"] == "success":
                                                    st.success(f"🎉 Posted to {platform.capitalize()}! [View]({p['postUrl']})")
                                                    st.balloons()
                                                    logger.info(f"Posted to {platform} for {st.session_state.user['email']}, ID: {p['id']}")
                                                else:
                                                    st.error(f"❌ Failed to post to {platform.capitalize()}: {p.get('error', 'Unknown error')}")
                                                    logger.warning(f"Post failed to {platform}: {p.get('error', 'Unknown error')}")
                                        except requests.HTTPError as e:
                                            error_msg = e.response.json().get('detail', 'Unknown error') if e.response else str(e)
                                            st.error(f"❌ Failed to post: {error_msg}")
                                            logger.warning(f"Post failed for {platform}: {e.response.text if e.response else str(e)}")
                                        except requests.ConnectionError:
                                            st.error(f"❌ Cannot connect to server at {API_BASE_URL}.")
                                            logger.error(f"Connection error for {platform} post")
                                        except requests.Timeout:
                                            st.error("❌ Request timed out. Check network or server status.")
                                            logger.error(f"Timeout error for {platform} post")
                                        except Exception as e:
                                            st.error(f"❌ Failed to post: {str(e)}")
                                            logger.error(f"Post failed for {platform}: {str(e)}")
                            else:
                                st.info("ℹ️ Twitter posting is admin-only. Save or copy instead! 😊")

with tab2:
    with st.container(border=True):
        st.markdown("## 💾 Saved Posts")
        st.markdown("View your saved drafts across platforms. 📚")
        if st.button("🔄 Load Saved Posts", key="load_drafts", type="primary"):
            with st.spinner("🔄 Loading saved posts..."):
                progress_bar = st.progress(0)
                try:
                    asyncio.run(simulate_progress(progress_bar))
                    response = requests.get(f"{API_BASE_URL}/drafts", headers=headers, timeout=5)
                    response.raise_for_status()
                    drafts = response.json()
                    df = pd.DataFrame(drafts)
                    if df.empty:
                        st.info("ℹ️ No saved posts found. Create some in the Create tab! 😊")
                    else:
                        st.dataframe(df[["platform", "content", "created_at"]], use_container_width=True, hide_index=True)
                        st.success("🎉 Saved posts loaded!")
                        st.balloons()
                    logger.info(f"Drafts loaded successfully, count: {len(drafts)}")
                except requests.HTTPError as e:
                    error_msg = e.response.json().get('detail', 'Unknown error') if e.response else str(e)
                    st.error(f"❌ Error loading posts: {error_msg}")
                    logger.warning(f"Draft fetch failed: {e.response.text if e.response else str(e)}")
                except requests.ConnectionError:
                    st.error(f"❌ Cannot connect to server at {API_BASE_URL}.")
                    logger.error("Connection error for drafts")
                except requests.Timeout:
                    st.error("❌ Request timed out. Check network or server status.")
                    logger.error("Timeout error for drafts")
                except Exception as e:
                    st.error(f"❌ Error loading posts: {str(e)}")
                    logger.error(f"Draft fetch failed: {str(e)}")
                progress_bar.empty()

with tab3:
    with st.container(border=True):
        st.markdown("## ⚙️ Settings")
        st.markdown("Manage your account and preferences. 🛠️")
        tier = st.selectbox("🌟 Plan", ["Free", "Premium", "Business"], key="tier_select", help="Choose your subscription plan")
        if st.button("🚀 Update Plan", key="update_tier", type="primary"):
            st.success(f"🎉 Upgraded to {tier}!")
            st.balloons()
            logger.info(f"User {st.session_state.user['email']} requested tier upgrade to {tier}")

# Post Muse Application Documentation

This document provides comprehensive documentation for the Post Muse application, a social media content creation and management tool. It consists of a frontend dashboard (`dashboard.py`) built with Streamlit, a backend API (`main.py`) built with FastAPI, and supporting modules (`api.py` for AI draft generation and `config.py` for prompt templates). The application uses SQLite for data persistence and integrates with Google's Generative AI (Gemini) for content generation. It supports user authentication, AI-powered draft generation, editing, saving, and posting to social media platforms, with admin-only restrictions for features like Twitter posting.

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Installation and Setup](#installation-and-setup)
4. [File Documentation](#file-documentation)
   - [dashboard.py (Frontend)](#dashboardpy-frontend)
   - [main.py (Backend)](#mainpy-backend)
   - [api.py (AI Draft Generation)](#apipy-ai-draft-generation)
   - [config.py (Configuration and Templates)](#configpy-configuration-and-templates)
5. [Security Considerations](#security-considerations)
6. [Potential Improvements](#potential-improvements)

## Overview
Post Muse streamlines social media content workflows by allowing users to:
- Register or log in with email and password, including admin privileges.
- Generate AI-assisted drafts for platforms like Twitter, LinkedIn, and Instagram using inputs such as topic, hashtags, insight, and tone.
- Edit, copy to clipboard, save, or post drafts.
- View and manage saved drafts.
- Update account settings (e.g., tier, though partially mocked).
- Integrate with social platforms: Real posting to Twitter (admin-only via Tweepy) and Instagram (text-only via Graph API), with mocks for others.

The AI component leverages Google's Gemini model to generate platform-specific content based on predefined prompt templates. The application emphasizes usability with Streamlit's interactive UI and security through API keys, hashing, and encryption.

## Architecture
- **Frontend (`dashboard.py`)**: Streamlit-based UI for user interactions, form inputs, and API calls to the backend. It handles session state for user data and drafts.
- **Backend (`main.py`)**: FastAPI RESTful API for endpoints handling authentication, user management, drafts, and posts. Integrates with SQLite for storage and external APIs (Twitter, Instagram).
- **AI Module (`api.py`)**: Asynchronous functions to generate drafts using Google's Generative AI (Gemini). Parses and cleans AI responses.
- **Configuration (`config.py`)**: Defines prompt templates for AI generation and tone options.
- **Database**: SQLite for users, posts, drafts, and platform tokens.
- **Communication**: Frontend uses `requests` to call backend endpoints with API key authentication.
- **Dependencies**:
  - **Frontend/Core**: Streamlit, Requests, Pandas, Asyncio, Pyperclip, python-dotenv, Re, Logging.
  - **Backend**: FastAPI, Pydantic, SQLite3, Tweepy, Cryptography, Passlib, Requests.
  - **AI**: google-generativeai (Gemini SDK), nest_asyncio.
- **Deployment**: Backend on a hosting platform (e.g., Railway.app); frontend on Streamlit Cloud. CORS configured for secure cross-origin access.

## Installation and Setup
### Prerequisites
- Python 3.10+ (compatible with Python 3.12 for some libraries like Gemini).
- pip for installing packages.

### Environment Variables
Create a `.env` file with:
- `API_BASE_URL`: Backend URL (e.g., `https://pmv2-production.up.railway.app/api`).
- `DB_PATH`: SQLite path (e.g., `data/post_muse.db`).
- `ENCRYPTION_KEY`: Fernet encryption key (generate via `Fernet.generate_key()`).
- `ADMIN_SECRET`: For admin registration.
- `GEMINI_API_KEY`: Google Generative AI API key (required for `api.py`).
- Twitter credentials: `TWITTER_CONSUMER_KEY`, `TWITTER_CONSUMER_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_TOKEN_SECRET`.
- Instagram tokens: Stored per-user in DB (not in `.env`).

### Installation
1. Install dependencies:
   ```
   pip install streamlit requests pandas python-dotenv pyperclip fastapi uvicorn sqlite3 tweepy cryptography passlib pydantic google-generativeai nest_asyncio
   ```
2. Run backend: `uvicorn main:app --reload`.
3. Run frontend: `streamlit run dashboard.py`.

### Directory Structure
- `dashboard.py`: Main frontend.
- `main.py`: Main backend.
- `api.py`: AI generation logic.
- `config.py`: Prompts and tones.
- `data/post_muse.db`: SQLite DB (auto-created).
- `.env`: Secrets.
- `tweepy_patch.py`: (Assumed) Compatibility patch for Tweepy in Python 3.13.

## File Documentation

### dashboard.py (Frontend)
This file implements the Streamlit dashboard for user interaction, authentication, draft generation, and management.

#### Imports and Configuration
- **Imports**: Streamlit (UI), Requests (HTTP), Pandas (data display), Datetime/Logging/Re/Asyncio (utilities), Pyperclip (clipboard), api/config (custom), python-dotenv (env loading).
- **Configuration**:
  - Loads `.env` via `load_dotenv()`.
  - `API_BASE_URL` from env (backend endpoint).
  - Logger at INFO level.
  - `PLATFORMS`: Supported platforms list.
  - `TONE_OPTIONS`: Tone choices (Professional, Casual, Excited).
  - Page config: Title, wide layout, expanded sidebar.
  - `PLATFORM_URLS`: Platform links.

#### Functions
- `clean_draft_content(draft: str) -> str`: Strips leading numbers via regex.
- `get_user_info(api_key: str) -> dict`: GET `/user` from backend; handles errors, defaults to non-admin.
- `async simulate_progress(progress_bar)`: Fills progress bar asynchronously.
- `login()`: Form for login/register. POSTs to `/login` or `/user`; stores in session state; error handling for HTTP/connection/timeout.

#### Main Logic
- Session check: Login if no user.
- Sidebar: Profile display, logout.
- Tabs:
  - **Create Post**: Inputs (topic, hashtags, insight, tone). Generate button: Async draft generation via `generate_platform_drafts`; display/edit/copy/save/post drafts.
  - **Saved Drafts**: Load from `/drafts`, show dataframe.
  - **Settings**: Tier selector, mock update.
- Error Handling: Spinners, errors, logging.

### main.py (Backend)
This file sets up the FastAPI API for core operations.

#### Imports and Setup
- **Imports**: FastAPI/HTTPException/Depends (API), Pydantic (models), SQLite3 (DB), python-dotenv (env), Requests/Tweepy (integrations), Logging/UUID/Passlib/Cryptography (utils), CORS.
- **Setup**:
  - FastAPI app with title/version.
  - CORS for Streamlit/localhost.
  - HTTPBearer security, bcrypt hashing, Fernet encryption.
  - `DB_PATH`, `ENCRYPTION_KEY` from env.
  - `PLATFORMS` list.
  - `MockClient`: Simulates non-Twitter posts.
  - `get_twitter_client(user_id)`: Admin-only Tweepy client.
  - `init_db()`: Creates DB tables (users, posts, platform_tokens, drafts).

#### Models
- `UserCreateRequest`: Validates email, passwords, admin secret.
- `PostRequest`: Post content, platforms, options.
- `PostResponse`: Status, ID, post IDs.
- `DraftRequest`: Content, platform.
- `LoginRequest`: Email, password.

#### Utilities
- `encrypt_token/decrypt_token`: Fernet for tokens.
- `get_current_user(authorization)`: Validates API key, checks limits.
- `get_platform_token(user_id, platform)`: Decrypts DB tokens.
- `post_to_instagram(user_id, content)`: Graph API post.

#### Endpoints
- POST `/api/login`: Verify credentials, return API key.
- POST `/api/post`: Validate, post to platforms (Twitter/Tweepy admin-only, Instagram/Graph, mocks); store in DB.
- POST `/api/draft`: Save draft.
- GET `/api/drafts`: Retrieve user's drafts.
- DELETE `/api/post/{post_id}`: Delete owned post.
- POST `/api/user`: Create user, hash password, generate API key.
- GET `/api/user`: Get user info.
- Error Handling: HTTPExceptions, logging.

### api.py (AI Draft Generation)
This module handles AI content generation using Google's Gemini model for platform-specific drafts.

#### Imports and Configuration
- **Imports**: Asyncio/Re/Streamlit (async/regex/UI), google-generativeai (Gemini), python-dotenv (env), Logging, nest_asyncio (Streamlit async fix).
- **Configuration**:
  - Logger at module level.
  - Applies `nest_asyncio` for Streamlit compatibility.
  - Loads `GEMINI_API_KEY` from env; configures `genai`.
  - Initializes `model = genai.GenerativeModel("gemini-2.5-flash-lite")`.
  - Error handling: Logs and shows Streamlit errors if setup fails.

#### Functions
- `async generate_single_prompt(prompt: str) -> str`:
  - Generates content via Gemini using executor for async compatibility.
  - Returns response text; handles errors with empty string.
- `split_numbered_drafts(text: str) -> list[str]`:
  - Parses numbered drafts via regex (e.g., matches "1. Content").
  - Fallback split if <3 matches.
  - Returns up to 3 cleaned drafts; handles errors.
- `async generate_platform_drafts(platform: str, vars: dict, prompt_templates: dict) -> list[str]`:
  - Formats template with vars (topic, hashtags, etc.).
  - Calls `generate_single_prompt`, splits, returns first 3 drafts.
  - Logs process; handles errors with empty list.

This module integrates AI seamlessly into the frontend for dynamic content creation.

### config.py (Configuration and Templates)
This file defines constants for AI prompts and tones.

#### Contents
- `PROMPT_TEMPLATES`: Dict of platform-specific strings.
  - **twitter**: 3 posts <280 chars, tone/emojis/hashtags; numbered output.
  - **linkedin**: 3 professional posts with insight; numbered.
  - **instagram**: 3 captions with tone/emojis/CTA; numbered.
  - Uses string formatting (e.g., `{topic}`, `{tone}`).
- `TONE_OPTIONS`: List of tones (casual, professional, etc.).

This centralizes configurable elements for easy maintenance.

## Security Considerations
- API keys for auth; tier limits (e.g., 20 posts/month free).
- Bcrypt password hashing; Fernet token encryption.
- Admin secret for registration; Twitter posting restricted.
- Parametrized SQL queries prevent injection.
- CORS limited to trusted origins.
- Gemini API key in env only.
- Vulnerabilities: Secure `.env`; validate all inputs.

## Potential Improvements
- Expand AI tones/platforms.
- Real integrations for more platforms.
- OAuth for tokens.
- Scheduling for posts.
- ORM (SQLAlchemy) for DB.
- Unit/integration tests.
- Rate limiting on AI calls.

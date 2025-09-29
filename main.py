import os
from datetime import datetime
from typing import List, Optional, Dict
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr, field_validator
import sqlite3
from dotenv import load_dotenv
import requests
import tweepy
import logging
import uuid
from passlib.context import CryptContext
from cryptography.fernet import Fernet
from fastapi.middleware.cors import CORSMiddleware
import tweepy_patch  # Import patch to mock imghdr for Python 3.13

# Load environment variables once
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Post Muse", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://postmusev3.streamlit.app/",
        "http://localhost:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security and database setup
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"])
DB_PATH = os.getenv("DB_PATH", "data/post_muse.db")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
cipher = Fernet(ENCRYPTION_KEY)

# Supported platforms
PLATFORMS = ["bluesky", "facebook", "gmb", "instagram", "linkedin", "pinterest", "reddit", "snapchat", "telegram", "tiktok", "threads", "twitter", "youtube"]

# Mock client for non-Twitter platforms
class MockClient:
    def post(self, content: str, platform: str) -> Dict:
        return {"status": "success", "id": str(uuid.uuid4()), "postUrl": f"https://{platform}.com/post/{uuid.uuid4()}"}

mock_client = MockClient()

# Twitter client for admin users
def get_twitter_client(user_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        if not row or not row[0]:
            logger.error(f"Non-admin user {user_id} attempted to access Twitter client")
            raise HTTPException(status_code=403, detail="Twitter posting restricted to admin users")
        return tweepy.Client(
            consumer_key=os.getenv("TWITTER_CONSUMER_KEY"),
            consumer_secret=os.getenv("TWITTER_CONSUMER_SECRET"),
            access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
            access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
        )

# Initialize database
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE,
                password TEXT,
                api_key TEXT UNIQUE,
                tier TEXT DEFAULT 'free',
                api_calls INTEGER DEFAULT 0,
                monthly_posts INTEGER DEFAULT 0,
                is_admin BOOLEAN DEFAULT FALSE
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                content TEXT,
                platforms TEXT,
                status TEXT DEFAULT 'pending',
                post_ids TEXT,
                created_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS platform_tokens (
                user_id TEXT,
                platform TEXT,
                access_token TEXT,
                refresh_token TEXT,
                expiry INTEGER,
                PRIMARY KEY (user_id, platform)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS drafts (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                content TEXT,
                platform TEXT,
                created_at TEXT
            )
        """)
        conn.commit()

init_db()

# Pydantic models
class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str
    confirm_password: str
    admin_secret: Optional[str] = None
    is_admin: bool = False
    tier: str = "free"

    @field_validator("confirm_password")
    def passwords_match(cls, v, info):
        if info.data.get("password") and v != info.data.get("password"):
            raise ValueError("Passwords do not match")
        return v

    @field_validator("is_admin")
    def restrict_admin(cls, v, info):
        if v and info.data.get("admin_secret") != os.getenv("ADMIN_SECRET"):
            raise ValueError("Invalid admin secret")
        return v

class PostRequest(BaseModel):
    post: str
    platforms: List[str]
    shortUrl: Optional[bool] = False
    autoHashtag: Optional[bool] = False
    autoSchedule: Optional[bool] = False
    mentions: Optional[List[str]] = None
    notes: Optional[str] = None
    requiresApproval: Optional[bool] = False
    evergreen: Optional[Dict[str, int]] = None

class PostResponse(BaseModel):
    status: str
    id: str
    postIds: List[Dict[str, str]]

class DraftRequest(BaseModel):
    content: str
    platform: str

class LoginRequest(BaseModel):
    email: str
    password: str

# Token encryption
def encrypt_token(token: str) -> str:
    return cipher.encrypt(token.encode()).decode()

def decrypt_token(encrypted: str) -> str:
    return cipher.decrypt(encrypted.encode()).decode()

# Authentication dependency
def get_current_user(authorization: str = Depends(security)) -> str:
    try:
        token = authorization.credentials
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT id, tier, monthly_posts, is_admin FROM users WHERE api_key = ?", (token,))
            row = c.fetchone()
            if not row:
                logger.error(f"Invalid API key: {token[:4]}... (truncated)")
                raise HTTPException(status_code=401, detail="Invalid API key")
            user_id, tier, monthly_posts, is_admin = row
            if tier == "free" and monthly_posts >= 20:
                logger.warning(f"Free tier limit reached for user_id: {user_id}")
                raise HTTPException(status_code=429, detail="Free tier limit reached")
            logger.debug(f"Authenticated user_id: {user_id}, tier: {tier}, is_admin: {is_admin}")
            return user_id
    except Exception as e:
        logger.error(f"Auth error: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid API key: {str(e)}")

# Login endpoint
@app.post("/api/login")
async def login_user(request: LoginRequest):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT password, api_key FROM users WHERE email = ?", (request.email.lower(),))
            row = c.fetchone()
            if row and pwd_context.verify(request.password, row[0]):
                logger.debug(f"Login successful for {request.email}")
                return {"api_key": row[1], "message": "Login successful"}
            logger.warning(f"Invalid credentials for {request.email}")
            raise HTTPException(status_code=401, detail="Invalid email or password")
    except Exception as e:
        logger.error(f"Login error for {request.email}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Login error: {str(e)}")

# Get platform token
def get_platform_token(user_id: str, platform: str) -> Optional[Dict]:
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT access_token, refresh_token, expiry FROM platform_tokens WHERE user_id = ? AND platform = ?", (user_id, platform))
        row = c.fetchone()
        if row:
            return {"access_token": decrypt_token(row[0]), "refresh_token": row[1] and decrypt_token(row[1]), "expiry": row[2]}
        return None

# Instagram posting (text-only)
def post_to_instagram(user_id: str, content: str) -> Dict:
    token = get_platform_token(user_id, "instagram")
    if not token:
        logger.error(f"No Instagram token for user_id: {user_id}")
        return {"status": "error", "id": None, "error": "No Instagram token"}
    try:
        response = requests.post(
            f"https://graph.instagram.com/me/media",
            params={"access_token": token["access_token"], "caption": content}
        )
        response.raise_for_status()
        logger.info(f"Instagram post successful for user_id: {user_id}")
        return {"status": "success", "id": response.json().get("id", str(uuid.uuid4())), "postUrl": f"https://instagram.com/p/{uuid.uuid4()}"}
    except Exception as e:
        logger.error(f"Instagram post failed for user_id: {user_id}: {str(e)}")
        return {"status": "error", "id": None, "error": str(e)}

# Post endpoint
@app.post("/api/post", response_model=PostResponse)
async def create_post(request: PostRequest, user_id: str = Depends(get_current_user)):
    if not all(p in PLATFORMS for p in request.platforms):
        logger.error(f"Invalid platforms: {request.platforms}")
        raise HTTPException(status_code=400, detail="Invalid platforms")
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        is_admin = row[0] if row else False
    
    if "twitter" in request.platforms and not is_admin:
        logger.error(f"Non-admin user {user_id} attempted to post to Twitter")
        raise HTTPException(status_code=403, detail="Twitter posting restricted to admin users")
    
    post_id = str(uuid.uuid4())
    status = "awaiting_approval" if request.requiresApproval else "success"
    
    post_ids = []
    for platform in request.platforms:
        if platform == "twitter":
            try:
                client = get_twitter_client(user_id)
                response = client.create_tweet(text=request.post)
                post_ids.append({"platform": platform, "status": "success", "id": str(response.data['id']), "postUrl": f"https://twitter.com/user/status/{response.data['id']}"})
                logger.info(f"Twitter post successful for user_id: {user_id}, post_id: {response.data['id']}")
            except Exception as e:
                logger.error(f"Twitter post failed for user_id: {user_id}: {str(e)}")
                post_ids.append({"platform": platform, "status": "error", "id": None, "error": str(e)})
        elif platform == "instagram":
            result = post_to_instagram(user_id, request.post)
            post_ids.append({"platform": platform, **result})
        else:
            mock_id = mock_client.post(request.post, platform)
            post_ids.append({"platform": platform, **mock_id})
            logger.info(f"Mock post to {platform} successful for user_id: {user_id}")
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO posts (id, user_id, content, platforms, status, post_ids, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (post_id, user_id, request.post, str(request.platforms), status, str(post_ids), datetime.utcnow().isoformat()))
        c.execute("UPDATE users SET monthly_posts = monthly_posts + 1 WHERE id = ?", (user_id,))
        conn.commit()
    
    logger.info(f"Post created: post_id={post_id}, user_id={user_id}, platforms={request.platforms}")
    return PostResponse(status=status, id=post_id, postIds=post_ids)

# Draft endpoint
@app.post("/api/draft")
async def save_draft(request: DraftRequest, user_id: str = Depends(get_current_user)):
    draft_id = str(uuid.uuid4())
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO drafts (id, user_id, content, platform, created_at) VALUES (?, ?, ?, ?, ?)",
                  (draft_id, user_id, request.content, request.platform, datetime.utcnow().isoformat()))
        conn.commit()
    logger.info(f"Draft saved for user {user_id} on platform {request.platform}, draft_id={draft_id}")
    return {"status": "success", "id": draft_id}

# Get drafts endpoint
@app.get("/api/drafts")
async def get_drafts(user_id: str = Depends(get_current_user)):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id, content, platform, created_at FROM drafts WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        drafts = c.fetchall()
    logger.info(f"Drafts retrieved for user_id: {user_id}, count: {len(drafts)}")
    return [{"id": d[0], "content": d[1], "platform": d[2], "created_at": d[3]} for d in drafts]

# Delete post endpoint
@app.delete("/api/post/{post_id}")
async def delete_post(post_id: str, user_id: str = Depends(get_current_user)):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT post_ids FROM posts WHERE id = ? AND user_id = ?", (post_id, user_id))
        row = c.fetchone()
        if row:
            c.execute("DELETE FROM posts WHERE id = ?", (post_id,))
            conn.commit()
            logger.info(f"Post deleted: post_id={post_id}, user_id={user_id}")
            return {"status": "deleted"}
        logger.warning(f"Post not found: post_id={post_id}, user_id={user_id}")
        raise HTTPException(status_code=404, detail="Post not found")

# User creation endpoint
@app.post("/api/user")
async def create_user(request: UserCreateRequest):
    logger.info(f"Received registration request for email: {request.email}, is_admin: {request.is_admin}")
    hashed = pwd_context.hash(request.password)
    api_key = str(uuid.uuid4())
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (id, email, password, api_key, tier, is_admin) VALUES (?, ?, ?, ?, ?, ?)", 
                      (str(uuid.uuid4()), request.email.lower(), hashed, api_key, request.tier, request.is_admin))
            conn.commit()
            logger.info(f"User created successfully: email={request.email}, is_admin={request.is_admin}, api_key={api_key}")
            return {"api_key": api_key}
        except sqlite3.IntegrityError as e:
            logger.warning(f"User creation failed: email={request.email} already exists - {str(e)}")
            raise HTTPException(status_code=400, detail="User already exists")
        except Exception as e:
            logger.error(f"Unexpected error creating user {request.email}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

# Get user info endpoint
@app.get("/api/user")
async def get_user(user_id: str = Depends(get_current_user)):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT email, tier, is_admin FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        if row:
            logger.info(f"User info retrieved for user_id: {user_id}")
            return {"email": row[0], "tier": row[1], "is_admin": bool(row[2])}
        logger.warning(f"User not found: user_id={user_id}")

        raise HTTPException(status_code=404, detail="User not found")



from fastapi import FastAPI, Request, HTTPException, Depends, Cookie, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import uvicorn
import hashlib
import hmac
from datetime import datetime, timedelta


import json
import logging

import config
import config
from database import Database, User, Match, Discipline, StreamChannel, ChatMessage
from fastapi import Form, WebSocket, WebSocketDisconnect
from typing import List

# LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from pathlib import Path

# --- UTILS ---

def get_db():
    session = db.get_session()
    try:
        yield session
    finally:
        session.close()

def verify_telegram_auth(data: dict, bot_token: str) -> bool:
    """Verifies the hash from Telegram Login Widget"""
    if not data.get('hash'): return False
    
    check_hash = data['hash']
    data_check_arr = []
    for key, value in data.items():
        if key != 'hash':
            data_check_arr.append(f"{key}={value}")
    
    data_check_string = "\n".join(sorted(data_check_arr))
    
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    hash_calc = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    return hash_calc == check_hash

# APP INIT
app = FastAPI(title="Stataggg Web")

@app.post("/api/admin/gift_all")
async def admin_gift_all(
    days: int = Form(...),
    message: str = Form(...),
    user_id: str = Cookie(None),
    db_sess: Session = Depends(get_db)
):
    if not user_id: raise HTTPException(status_code=403)
    admin = db_sess.query(User).filter_by(telegram_id=int(user_id)).first()
    if not admin or not admin.is_admin: raise HTTPException(status_code=403)

    all_users = db_sess.query(User).all()
    now = datetime.now()
    
    for u in all_users:
        # Add premium days
        if u.is_premium and u.premium_until and u.premium_until > now:
            u.premium_until += timedelta(days=days)
        else:
            u.is_premium = True
            u.premium_since = now
            u.premium_until = now + timedelta(days=days)
        
        # Set notification
        u.gift_notification = message
    
    db_sess.commit()
    return {"status": "success", "count": len(all_users)}

@app.post("/api/user/clear_notification")
async def clear_notification(
    user_id: str = Cookie(None),
    db_sess: Session = Depends(get_db)
):
    if not user_id: return {"status": "error"}
    user = db_sess.query(User).filter_by(telegram_id=int(user_id)).first()
    if user:
        user.gift_notification = None
        db_sess.commit()
    return {"status": "success"}

@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"DEBUG REQUEST: {request.method} {request.url.path}")
    response = await call_next(request)
    return response

# --- WEBSOCKET MANAGER ---

class ConnectionManager:
    def __init__(self):
        # Map websocket to user data: {websocket: {"id": 1, "username": "Admin", "photo": "..."}}
        self.active_connections: dict = {}

    async def connect(self, websocket: WebSocket, user_data: dict = None):
        await websocket.accept()
        self.active_connections[websocket] = user_data
        if user_data:
            await self.broadcast_online_list()

    async def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]
            await self.broadcast_online_list()

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections.keys()):
            try:
                await connection.send_json(message)
            except:
                if connection in self.active_connections:
                    del self.active_connections[connection]

    async def broadcast_online_list(self):
        # Get unique users
        unique_users = {}
        for data in self.active_connections.values():
            if data and data.get("id"):
                unique_users[data["id"]] = data
        
        online_list = list(unique_users.values())
        await self.broadcast({
            "type": "online_list",
            "users": online_list
        })

manager = ConnectionManager()

# --- CHAT ROUTES ---

@app.get("/api/chat/history")
async def get_chat_history(db_sess: Session = Depends(get_db)):
    """Fetch last 100 messages"""
    messages = db_sess.query(ChatMessage).order_by(ChatMessage.created_at.desc()).limit(100).all()
    # Return reversed (oldest first) for UI
    return [{
        "id": m.id,
        "content": m.content,
        "username": m.user.username or m.user.first_name,
        "is_admin": m.user.is_admin,
        "is_premium": m.user.is_premium,
        "photo_url": m.user.photo_url,
        "created_at": m.created_at.strftime("%H:%M"),
        "timestamp": m.created_at.timestamp(),
        "reply_to": m.reply_to_id,
        "is_edited": m.is_edited
    } for m in reversed(messages)]

@app.websocket("/ws/chat")
async def websocket_chat_endpoint(websocket: WebSocket, db_sess: Session = Depends(get_db)):
    # Parse User from Cookie at the start
    cookie_header = websocket.headers.get('cookie')
    user_data = None
    user_id = None
    if cookie_header:
        from http.cookies import SimpleCookie
        cookie = SimpleCookie()
        cookie.load(cookie_header)
        if 'user_id' in cookie:
            user_id = cookie['user_id'].value
    
    if user_id:
        user = db_sess.query(User).filter_by(telegram_id=int(user_id)).first()
        if user and not user.is_banned:
            user_data = {
                "id": user.telegram_id,
                "username": user.username or user.first_name,
                "photo_url": user.photo_url,
                "is_admin": user.is_admin,
                "is_premium": user.is_premium
            }

    await manager.connect(websocket, user_data)
    
    try:
        while True:
            data = await websocket.receive_json()
            if not user_id or not user_data: continue
            
            # Re-fetch user in loop only if needed (e.g. for ban check)
            # but for performance let's use cached user_data for now
            # unless we want to be super strict about mid-session bans
            
            if data['type'] == 'send':
                content = data.get('content', '').strip()[:1000]
                if not content: continue
                
                reply_to_id = data.get('reply_to_id')
                
                # Save to DB
                new_msg = ChatMessage(
                    user_id=user.id,
                    content=content,
                    reply_to_id=reply_to_id
                )
                db_sess.add(new_msg)
                db_sess.commit()
                
                # Cleanup Old Messages (>100)
                count = db_sess.query(ChatMessage).count()
                if count > 100:
                    limit_count = count - 100
                    subq = db_sess.query(ChatMessage.id).order_by(ChatMessage.created_at.asc()).limit(limit_count)
                    db_sess.query(ChatMessage).filter(ChatMessage.id.in_(subq)).delete(synchronize_session=False)
                    db_sess.commit()

                # Broadcast
                await manager.broadcast({
                    "type": "new_message",
                    "id": new_msg.id,
                    "content": new_msg.content,
                    "username": user_data["username"],
                    "is_admin": user_data["is_admin"],
                    "is_premium": user_data["is_premium"],
                    "photo_url": user_data["photo_url"],
                    "created_at": new_msg.created_at.strftime("%H:%M"),
                    "reply_to": reply_to_id
                })
                
            elif data['type'] == 'delete' and user_data["is_admin"]:
                msg_id = data.get('msg_id')
                msg = db_sess.query(ChatMessage).filter_by(id=msg_id).first()
                if msg:
                     db_sess.delete(msg)
                     db_sess.commit()
                     await manager.broadcast({"type": "delete", "id": msg_id})

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WS Error: {e}")
        try:
            await manager.disconnect(websocket)
        except: pass

db = Database()
print(f"Database Connected: {db.url}")
print("DEBUG: Routes /disciplines/add registered.")

BASE_DIR = Path(__file__).resolve().parent

# TEMPLATES & STATIC
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# --- UTILS ---

def get_db():
    session = db.get_session()
    try:
        yield session
    finally:
        session.close()

def verify_telegram_auth(data: dict, bot_token: str) -> bool:
    """Verifies the hash from Telegram Login Widget"""
    if not data.get('hash'): return False
    
    check_hash = data['hash']
    data_check_arr = []
    for key, value in data.items():
        if key != 'hash':
            data_check_arr.append(f'{key}={value}')
    
    data_check_string = '\n'.join(sorted(data_check_arr))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    hash_calc = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    return hash_calc == check_hash

def get_current_user(request: Request, user_id: str = Cookie(None), db_sess: Session = Depends(get_db)):
    if not user_id:
        return None
    try:
        user = db_sess.query(User).filter_by(telegram_id=int(user_id)).first()
        if user and user.is_banned:
            if user.ban_until and user.ban_until < datetime.now():
                user.is_banned = False
                user.ban_until = None
                db_sess.commit()
            else:
                # User is still banned
                return user
        return user
    except:
        return None

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user: User = Depends(get_current_user)):
    if user and user.is_banned:
        return templates.TemplateResponse("banned.html", {"request": request, "user_obj": user, "user": user}, status_code=403)
    
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/auth/telegram")
async def auth_telegram(
    id: str, 
    first_name: str, 
    username: str = None, 
    photo_url: str = None, 
    auth_date: str = None, 
    hash: str = None,
    db_sess: Session = Depends(get_db)
):
    # Verify Hash
    data = {
        "id": id, "first_name": first_name, "username": username, 
        "photo_url": photo_url, "auth_date": auth_date, "hash": hash
    }
    # Clean None values for verification
    data = {k: v for k, v in data.items() if v is not None}
    
    if not verify_telegram_auth(data, config.BOT_TOKEN):
        raise HTTPException(status_code=400, detail="Invalid Telegram Hash")
    
    # Check if user exists, else create
    tg_id = int(id)
    user = db_sess.query(User).filter_by(telegram_id=tg_id).first()
    
    if not user:
        user = User(
            telegram_id=tg_id,
            first_name=first_name,
            username=username,
            photo_url=photo_url,
            is_admin=(tg_id in config.ADMIN_IDS)
        )
        db_sess.add(user)
        db_sess.commit()
        logger.info(f"New User Registered: {username} ({tg_id})")
    else:
        # Update info
        user.first_name = first_name
        user.username = username
        user.username = username
        user.photo_url = photo_url
        if tg_id in config.ADMIN_IDS:
            user.is_admin = True
        db_sess.commit()

    # Login (Set Cookie)
    response = RedirectResponse(url="/dashboard")
    response.set_cookie(key="user_id", value=str(tg_id)) # Simple cookie for now
    return response

@app.get("/auth/dev")
async def auth_dev(db_sess: Session = Depends(get_db)):
    """Bypasses Telegram Auth for Local Development"""
    dev_id = 777
    user = db_sess.query(User).filter_by(telegram_id=dev_id).first()
    if not user:
        user = User(
            telegram_id=dev_id,
            first_name="Developer",
            username="dev_admin",
            photo_url="https://via.placeholder.com/150",
            is_admin=True
        )
        db_sess.add(user)
        db_sess.commit()
    else:
        # Ensure dev is always admin
        if not user.is_admin:
            user.is_admin = True
            db_sess.commit()
    
    response = RedirectResponse(url="/dashboard")
    response.set_cookie(key="user_id", value=str(dev_id))
    return response



@app.get("/reset_premium")
async def reset_premium_dev(request: Request, user_id: str = Cookie(None), db_sess: Session = Depends(get_db)):
    """Temporary Dev Route to Reset to Basic"""
    if not user_id: return RedirectResponse(url="/")
    user = db_sess.query(User).filter_by(telegram_id=int(user_id)).first()
    if not user: return RedirectResponse(url="/")
    
    # Reset to Basic
    user.is_premium = False
    user.premium_since = None
    user.premium_until = None
    db_sess.commit()
    
    return RedirectResponse(url="/dashboard", status_code=302)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: User = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/")
    if user and user.is_banned:
        return templates.TemplateResponse("banned.html", {"request": request, "user_obj": user, "user": user}, status_code=403)
        
    # Fetch Matches (Aggregated from CS2 & Dota)
    finished_matches = db.get_finished_matches_paginated(limit=10)

    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "user": user,
        "live_matches": [],
        "upcoming_matches": [],
        "finished_matches": finished_matches
    })

@app.get("/api/matches")
async def get_matches_api(
    skip: int = 0,
    limit: int = 10
):
    """
    Pagination endpoint for matches history. Uses aggregate logic from Database class.
    """
    matches = db.get_finished_matches_paginated(skip=skip, limit=limit)
        
    result = []
    for m in matches:
        # Determine scores for coloring (frontend expect integers)
        s1, s2 = 0, 0
        if m.score and ':' in str(m.score):
            try:
                parts = str(m.score).split(':')
                s1 = int(parts[0])
                s2 = int(parts[1])
            except: pass
            
        # Use the branded league name if available, fallback to game_type
        league_name = getattr(m, 'league_name', m.game_type)
            
        result.append({
            "id": m.id,
            "match_time": m.match_time,
            "league": league_name,
            "team1": m.team1,
            "team2": m.team2,
            "score": m.score,
            "s1": s1, 
            "s2": s2,
            "odds_p1": m.odds_p1,
            "odds_p2": m.odds_p2,
            "map_scores": m.map_scores,
            "history": m.history 
        })
        
    return result

@app.get("/streams", response_class=HTMLResponse)
async def streams_page(request: Request, user: User = Depends(get_current_user), db_sess: Session = Depends(get_db)):
    if not user: return RedirectResponse(url="/")
    if user and user.is_banned:
        return templates.TemplateResponse("banned.html", {"request": request, "user_obj": user, "user": user}, status_code=403)

    disciplines = db_sess.query(Discipline).filter_by(is_active=True).all()
    return templates.TemplateResponse("streams.html", {
        "request": request, 
        "user": user, 
        "disciplines": disciplines
    })

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    """Profile is now part of the global modal. Redirect to dashboard."""
    return RedirectResponse(url="/dashboard")

@app.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard_page(request: Request, user: User = Depends(get_current_user), db_sess: Session = Depends(get_db)):
    if not user: return RedirectResponse(url="/")
    if user and user.is_banned:
        return templates.TemplateResponse("banned.html", {"request": request, "user_obj": user, "user": user}, status_code=403)

    # Top 50 users by registration date
    top_users = db_sess.query(User).order_by(User.created_at.desc()).limit(50).all()

    return templates.TemplateResponse("leaderboard.html", {
        "request": request, 
        "user": user, 
        "users": top_users
    })

@app.on_event("startup")
async def startup_event():
    logger.info("Listing all registered routes:")
    for route in app.routes:
        methods = getattr(route, "methods", "N/A")
        logger.info(f"Route: {route.path} [{methods}]")

@app.get("/disciplines/add")
async def add_discipline_get():
    return {"message": "GET request received. POST to this URL to add a discipline."}

import shutil
import uuid
from fastapi import File, UploadFile

# ... (Previous code)

@app.post("/streams/add") # Legacy support for cached pages
@app.post("/disciplines/add")
async def add_discipline(
    name: str = Form(...),
    image: UploadFile = File(...),
    user_id: str = Cookie(None),
    db_sess: Session = Depends(get_db)
):
    if not user_id: raise HTTPException(status_code=403)
    user = db_sess.query(User).filter_by(telegram_id=int(user_id)).first()
    if not user or not user.is_admin: raise HTTPException(status_code=403)

    # Validate file type
    if not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Generate unique filename
    file_ext = image.filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{file_ext}"
    file_path = BASE_DIR / "static" / "uploads" / unique_filename
    
    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
    
    image_url = f"/static/uploads/{unique_filename}"

    new_disc = Discipline(name=name, image_url=image_url)
    db_sess.add(new_disc)
    db_sess.commit()
    
    return RedirectResponse(url="/streams", status_code=303)

@app.get("/streams/{discipline_id}", response_class=HTMLResponse)
async def discipline_page(discipline_id: int, request: Request, user: User = Depends(get_current_user), db_sess: Session = Depends(get_db)):
    if not user: return RedirectResponse(url="/")
    if user and user.is_banned:
        return templates.TemplateResponse("banned.html", {"request": request, "user_obj": user, "user": user}, status_code=403)

    discipline = db_sess.query(Discipline).filter_by(id=discipline_id).first()
    if not discipline:
        raise HTTPException(status_code=404, detail="Discipline not found")

    channels = db_sess.query(StreamChannel).filter_by(discipline_id=discipline_id, is_active=True).all()

    return templates.TemplateResponse("discipline.html", {
        "request": request, 
        "user": user, 
        "discipline": discipline,
        "channels": channels
    })

@app.post("/streams/{discipline_id}/add_channel")
async def add_channel(
    discipline_id: int,
    name: str = Form(...),
    stream_url: str = Form(...),
    user_id: str = Cookie(None),
    db_sess: Session = Depends(get_db)
):
    if not user_id: raise HTTPException(status_code=403)
    user = db_sess.query(User).filter_by(telegram_id=int(user_id)).first()
    if not user or not user.is_admin: raise HTTPException(status_code=403)

    new_channel = StreamChannel(
        discipline_id=discipline_id,
        name=name,
        stream_url=stream_url
    )
    db_sess.add(new_channel)
    db_sess.commit()
    
    return RedirectResponse(url=f"/streams/{discipline_id}", status_code=303)

@app.post("/streams/{discipline_id}/channels/{channel_id}/delete")
async def delete_channel(
    discipline_id: int, 
    channel_id: int, 
    user_id: str = Cookie(None), 
    db_sess: Session = Depends(get_db)
):
    if not user_id: raise HTTPException(status_code=403)
    user = db_sess.query(User).filter_by(telegram_id=int(user_id)).first()
    if not user or not user.is_admin: raise HTTPException(status_code=403)

    channel = db_sess.query(StreamChannel).filter_by(id=channel_id, discipline_id=discipline_id).first()
    if channel:
        db_sess.delete(channel)
        db_sess.commit()
    
    return RedirectResponse(url=f"/streams/{discipline_id}", status_code=303)

@app.post("/disciplines/{discipline_id}/delete")
async def delete_discipline(
    discipline_id: int, 
    user_id: str = Cookie(None), 
    db_sess: Session = Depends(get_db)
):
    if not user_id: raise HTTPException(status_code=403)
    user = db_sess.query(User).filter_by(telegram_id=int(user_id)).first()
    if not user or not user.is_admin: raise HTTPException(status_code=403)

    disc = db_sess.query(Discipline).filter_by(id=discipline_id).first()
    if disc:
        # Optional: Delete associated image file if needed
        # Optional: Delete associated channels? SQLAlchemy cascade might handle it or we leave orphans.
        # For now, just delete the record.
        db_sess.delete(disc)
        db_sess.commit()
    
    return RedirectResponse(url="/streams", status_code=303)

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("user_id")
    return response

# --- ADMIN PANEL ---

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, user: User = Depends(get_current_user), db_sess: Session = Depends(get_db)):
    if not user: return RedirectResponse(url="/")
    if user and user.is_banned:
        return templates.TemplateResponse("banned.html", {"request": request, "user_obj": user, "user": user}, status_code=403)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    all_users = db_sess.query(User).order_by(User.created_at.desc()).all()
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "user": user,
        "users": all_users
    })

@app.post("/api/admin/update_subscription")
async def admin_update_subscription(
    telegram_id: int = Form(...),
    action: str = Form(...),
    days: int = Form(30),
    user_id: str = Cookie(None),
    db_sess: Session = Depends(get_db)
):
    if not user_id: raise HTTPException(status_code=403)
    admin = db_sess.query(User).filter_by(telegram_id=int(user_id)).first()
    if not admin or not admin.is_admin: raise HTTPException(status_code=403)

    target_user = db_sess.query(User).filter_by(telegram_id=telegram_id).first()
    if not target_user: raise HTTPException(status_code=404, detail="Пользователь не найден")

    if action == "add":
        if target_user.is_premium and target_user.premium_until and target_user.premium_until > datetime.now():
            target_user.premium_until += timedelta(days=days)
        else:
            target_user.is_premium = True
            target_user.premium_since = datetime.now()
            target_user.premium_until = datetime.now() + timedelta(days=days)
    elif action == "remove":
        target_user.is_premium = False
        target_user.premium_since = None
        target_user.premium_until = None
    
    db_sess.commit()
    return {"status": "success"}

@app.post("/api/admin/toggle_ban")
async def admin_toggle_ban(
    telegram_id: int = Form(...),
    is_banned: bool = Form(...),
    duration_days: int = Form(0),
    user_id: str = Cookie(None),
    db_sess: Session = Depends(get_db)
):
    if not user_id: raise HTTPException(status_code=403)
    admin = db_sess.query(User).filter_by(telegram_id=int(user_id)).first()
    if not admin or not admin.is_admin: raise HTTPException(status_code=403)

    target_user = db_sess.query(User).filter_by(telegram_id=telegram_id).first()
    if not target_user: raise HTTPException(status_code=404, detail="Пользователь не найден")
    if target_user.telegram_id == admin.telegram_id:
        raise HTTPException(status_code=400, detail="Вы не можете забанить самого себя")

    target_user.is_banned = is_banned
    if is_banned:
        if duration_days > 0:
            target_user.ban_until = datetime.now() + timedelta(days=duration_days)
        else:
            target_user.ban_until = None # Permanent
    else:
        target_user.ban_until = None

    db_sess.commit()
    return {"status": "success"}

@app.post("/api/admin/delete_user")
async def admin_delete_user(
    telegram_id: int = Form(...),
    user_id: str = Cookie(None),
    db_sess: Session = Depends(get_db)
):
    if not user_id: raise HTTPException(status_code=403)
    admin = db_sess.query(User).filter_by(telegram_id=int(user_id)).first()
    if not admin or not admin.is_admin: raise HTTPException(status_code=403)

    target_user = db_sess.query(User).filter_by(telegram_id=telegram_id).first()
    if not target_user: raise HTTPException(status_code=404, detail="Пользователь не найден")
    if target_user.telegram_id == admin.telegram_id:
        raise HTTPException(status_code=400, detail="Вы не можете удалить самого себя")

    db_sess.commit() # Ensure previous changes are saved
    db_sess.delete(target_user)
    db_sess.commit()
    return {"status": "success"}

# --- ANALYTICS ROUTES ---

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user: return RedirectResponse("/")
    if user and user.is_banned:
        return templates.TemplateResponse("banned.html", {"request": request, "user_obj": user, "user": user}, status_code=403)
    
    if not user.is_premium:
        # Simply redirect back to dashboard if not premium
        return RedirectResponse("/dashboard")
        
    # Get all teams for the dropdown
    teams_q = db.query(Match.team1).union(db.query(Match.team2)).distinct().all()
    teams = sorted([t[0] for t in teams_q if t[0]])
    
    return templates.TemplateResponse("analytics.html", {"request": request, "user": user, "teams": teams})

@app.post("/api/predict")
async def predict_match(
    team1: str = Form(...),
    team2: str = Form(...)
    # Using global 'db' for aggregation
):
    # --- HELPER: STATS CALC ---
    def calculate_stats(team_name, all_matches, lookback=20):
        # Filter for this team
        relevant = []
        for m in all_matches:
            if m.team1 == team_name or m.team2 == team_name:
                relevant.append(m)
        
        # Sort by latest
        # Note: We rely on list already being somewhat sorted or sort here
        # Assuming matches returned by DB need sorting? get_team_matches does NOT sort by default potentially
        # Let's sort manually to be safe
        def sort_key(m):
            try: return datetime.strptime(str(m.match_time), '%Y-%m-%d %H:%M')
            except: return datetime.min
            
        relevant.sort(key=sort_key, reverse=True)
        recent = relevant[:lookback]
        
        total = len(recent)
        if total == 0:
            return 0.5, 0.5, 0.5 # Default
            
        wins = 0
        fb_count = 0
        map1_wins = 0
        
        for m in recent:
            # Winrate
            s1, s2 = 0, 0
            if m.score and ':' in m.score:
                try: s1, s2 = map(int, m.score.split(':'))
                except: pass
                
            winner = None
            if s1 > s2: winner = m.team1
            elif s2 > s1: winner = m.team2
            
            if winner == team_name: wins += 1
            
            # FB (First Blood)
            # Check 'first_blood' field
            if hasattr(m, 'first_blood') and m.first_blood == team_name:
                fb_count += 1
                
            # Map 1 Win
            # Need to parse history or map_scores? 
            # If map_scores is "16:5", that's Map 1.
            # If history has "map_1": "16:5"
            map1_winner = None
            
            # Try History first
            h = m.history if isinstance(m.history, dict) else {}
            m1_score = h.get('map_1')
            if not m1_score:
                # Fallback to map_scores if single map match
                if m.map_scores and isinstance(m.map_scores, str) and ':' in m.map_scores:
                    m1_score = m.map_scores
            
            if m1_score and ':' in m1_score:
                try: 
                    mk1, mk2 = map(int, m1_score.split(':'))
                    if mk1 > mk2: map1_winner = m.team1
                    elif mk2 > mk1: map1_winner = m.team2
                except: pass
            
            if map1_winner == team_name:
                map1_wins += 1
        
        return (wins/total), (fb_count/total), (map1_wins/total)

    # --- 1. FETCH AGGREGATED DATA ---
    matches_t1 = db.get_team_matches(team1)
    matches_t2 = db.get_team_matches(team2)
    
    # --- 2. CALCULATE METRICS ---
    wr_t1, fb_t1, m1_t1 = calculate_stats(team1, matches_t1)
    wr_t2, fb_t2, m1_t2 = calculate_stats(team2, matches_t2)
    
    # --- 3. H2H ---
    # Intersect matches
    h2h_wins_t1 = 0
    h2h_total = 0
    
    # We can iterate one list and check if opponent is team2
    for m in matches_t1:
        if m.team1 == team2 or m.team2 == team2:
            h2h_total += 1
            # Determine winner
            s1, s2 = 0, 0
            if m.score and ':' in m.score:
                try: s1, s2 = map(int, m.score.split(':'))
                except: pass
            if s1 > s2: 
                if m.team1 == team1: h2h_wins_t1 += 1
            elif s2 > s1:
                if m.team2 == team1: h2h_wins_t1 += 1
                
    h2h_rate_t1 = h2h_wins_t1 / h2h_total if h2h_total > 0 else 0.5
    
    # --- 4. WEIGHTED FORMULA ---
    # Formula: 
    # Global Confidence for T1 = 
    #   30% H2H 
    # + 30% Recent Winrate Diff (normalized)
    # + 20% FB Rate Diff
    # + 20% Map 1 Rate Diff
    
    # Normalize Comparison: P(T1) = T1 / (T1 + T2)
    
    def normalize(v1, v2):
        s = v1 + v2
        return v1 / s if s > 0 else 0.5
        
    p_h2h = h2h_rate_t1 # Already T1 vs Total
    p_wr  = normalize(wr_t1, wr_t2)
    p_fb  = normalize(fb_t1, fb_t2)
    p_m1  = normalize(m1_t1, m1_t2)
    
    # Adjust weights if no H2H
    if h2h_total == 0:
        # 40% WR, 30% FB, 30% M1
        final_score = (p_wr * 0.4) + (p_fb * 0.3) + (p_m1 * 0.3)
    else:
        # 30% H2H, 30% WR, 20% FB, 20% M1
        final_score = (p_h2h * 0.3) + (p_wr * 0.3) + (p_fb * 0.2) + (p_m1 * 0.2)
        
    # --- 5. RESULT ---
    winner = team1 if final_score >= 0.5 else team2
    confidence = int(final_score * 100) if winner == team1 else int((1 - final_score) * 100)
    
    # Cap
    confidence = max(51, min(confidence, 92))
    
    # Display Stats
    disp_fb = int(fb_t1 * 100) if winner == team1 else int(fb_t2 * 100)
    
    return {
        "winner": winner,
        "confidence": confidence,
        "team1": team1,
        "team2": team2,
        "stats": {
            "avg_duration": "~35-45m",
            "first_blood_rate": disp_fb, 
            "win_probability": confidence
        }
    }

@app.get("/api/matches")
async def get_matches_paginated(
    skip: int = 0,
    limit: int = 10
    # No Depends(get_db) needed for aggregation since we use global 'db' which manages its own sessions
):
    # Only FINISHED matches (Aggregated)
    matches = db.get_finished_matches_paginated(skip=skip, limit=limit)
    
    result = []
    for m in matches:
        scores = m.score.split(':') if m.score and ':' in m.score else ["0", "0"]
        try:
            s1 = int(scores[0])
            s2 = int(scores[1])
        except:
            s1, s2 = 0, 0
            
        result.append({
            "id": m.id,
            "match_time": m.match_time,
            "league": m.game_type, # Using game_type based on user feedback
            "team1": m.team1,
            "team2": m.team2,
            "score": m.score,
            "s1": s1,
            "s2": s2,
            "odds_p1": m.odds_p1,
            "odds_p2": m.odds_p2,
            "map_scores": m.map_scores # Will be parsed by JS if possible, but usually string now
        })
        
    return result

@app.post("/api/team_stats")
async def get_team_stats(
    team: str = Form(...)
):
    from sqlalchemy import or_
    import random

    # Query all finished matches for the team using aggregation
    matches = db.get_team_matches(team)

    total_games = len(matches)
    wins = 0
    losses = 0
    ranking_score = 1000 # Base ELO-like score (Mock start)

    # Calculate real Winrate
    for m in matches:
        # Determine winner from score "S1:S2"
        if not m.score or ':' not in m.score: continue
        try:
            s1, s2 = map(int, m.score.split(':'))
            winner_name = None
            if s1 > s2: winner_name = m.team1
            if s2 > s1: winner_name = m.team2
            
            if winner_name == team:
                wins += 1
            else:
                losses += 1
        except:
            continue
            
    winrate = (wins / total_games * 100) if total_games > 0 else 0
    
    # Mock/derived stats since we don't have granular event data yet
    fb_rate = int(winrate * 0.9) + random.randint(-5, 5) # Correlation with winrate
    fb_rate = max(10, min(fb_rate, 90))
    
    map1_wr = int(winrate) + random.randint(-10, 10)
    map1_wr = max(10, min(map1_wr, 90))

    return {
        "team": team,
        "total_games": total_games,
        "wins": wins,
        "losses": losses,
        "winrate": int(winrate),
        "fb_rate": fb_rate,
        "map1_winrate": map1_wr,
        "last_5": [
            1 if (m.team1 == team and int(m.score.split(':')[0]) > int(m.score.split(':')[1])) or 
                 (m.team2 == team and int(m.score.split(':')[1]) > int(m.score.split(':')[0])) else 0 
            for m in matches[-5:]
        ] if total_games > 0 else []
    }

@app.get("/api/leagues")
async def get_leagues(db: Session = Depends(get_db)):
    # Get distinct leagues (game_type) from matches or stream channels? 
    # User wants match analysis, so matches table.
    # We should exclude 'Unknown' leagues if possible.
    results = db.query(Match.game_type).distinct().all()
    # Filter out empty or None
    leagues = [r[0] for r in results if r[0]]
    return {"leagues": sorted(leagues)}

@app.get("/api/teams")
async def get_teams(
    league: str = Query(None),
    db: Session = Depends(get_db)
):
    from sqlalchemy import or_
    
    query = db.query(Match.team1).union(db.query(Match.team2))
    
    if league:
        # Filter matches by game_type before union?
        # Union is tricky with filters.
        # Better:
        # distinct team1 from matches where game_type=league
        # UNION
        # distinct team2 from matches where game_type=league
        
        q1 = db.query(Match.team1).filter(Match.game_type == league)
        q2 = db.query(Match.team2).filter(Match.game_type == league)
        query = q1.union(q2)
        
    results = query.distinct().all()
    teams = sorted([r[0] for r in results if r[0]])
    return {"teams": teams}

if __name__ == "__main__":
    print("\n" + "="*50)
    print(" >>> ATTENTION! SERVER IS STARTING <<< ")
    print(" >>> USE THIS URL: http://localhost:8090/streams <<<")
    print("="*50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8090)

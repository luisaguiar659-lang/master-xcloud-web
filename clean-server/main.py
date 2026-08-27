import asyncio
import os
import secrets
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from playwright.async_api import async_playwright

from xcloud import XCloudError, add_device, add_playlist, delete_device, login, reset_device

load_dotenv()

app = FastAPI(title="Master XCloud API", version="1.0-clean")
origins = [x.strip() for x in os.getenv("FRONTEND_ORIGINS", "*").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

TTL = int(os.getenv("SESSION_TTL_MINUTES", "120")) * 60
HEADLESS = os.getenv("HEADLESS", "true").lower() != "false"
pw = None
browser = None
sessions = {}


@dataclass
class Session:
    context: object
    page: object
    expires: float
    lock: asyncio.Lock


class LoginIn(BaseModel):
    email: str
    password: str


class ActivateIn(BaseModel):
    device: str
    playlist: str


class DeviceIn(BaseModel):
    device: str


@app.on_event("startup")
async def startup():
    global pw, browser
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        executable_path="/usr/bin/chromium",
        headless=HEADLESS,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )


@app.on_event("shutdown")
async def shutdown():
    for s in list(sessions.values()):
        try:
            await s.context.close()
        except Exception:
            pass
    if browser:
        await browser.close()
    if pw:
        await pw.stop()


async def session_from(auth):
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(401, "Sessão ausente.")
    token = auth.split(" ", 1)[1]
    s = sessions.get(token)
    if not s or s.expires < time.time():
        if s:
            try:
                await s.context.close()
            except Exception:
                pass
            sessions.pop(token, None)
        raise HTTPException(401, "Sessão expirada.")
    s.expires = time.time() + TTL
    return token, s


async def run_op(auth, fn):
    _, s = await session_from(auth)
    async with s.lock:
        if s.page is None or s.page.is_closed():
            s.page = await s.context.new_page()
            s.page.set_default_timeout(15000)
        try:
            return await fn(s.page)
        except XCloudError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            raise HTTPException(500, f"Falha na automação: {e}")


@app.get("/health")
async def health():
    return {"ok": True, "service": "master-xcloud-api", "mode": "clean-v1"}


@app.post("/auth/login")
async def auth_login(data: LoginIn):
    ctx = await browser.new_context(service_workers="block")
    page = await ctx.new_page()
    page.set_default_timeout(15000)
    try:
        await login(page, data.email.strip(), data.password)
    except Exception as e:
        try:
            await ctx.close()
        except Exception:
            pass
        raise HTTPException(401, str(e))
    token = secrets.token_urlsafe(32)
    sessions[token] = Session(ctx, page, time.time() + TTL, asyncio.Lock())
    return {"ok": True, "token": token}


@app.get("/auth/session")
async def auth_session(authorization: str | None = Header(default=None)):
    _, s = await session_from(authorization)
    return {"ok": True, "expires_in": max(0, int(s.expires - time.time()))}


@app.post("/auth/logout")
async def auth_logout(authorization: str | None = Header(default=None)):
    token, s = await session_from(authorization)
    sessions.pop(token, None)
    try:
        await s.context.close()
    except Exception:
        pass
    return {"ok": True}


@app.post("/operations/activate")
async def activate(data: ActivateIn, authorization: str | None = Header(default=None)):
    async def op(page):
        dev = data.device.strip().upper()
        await add_device(page, dev)
        await add_playlist(page, dev, data.playlist.strip())
        return {"ok": True, "message": "Ativar MAC + DNS concluído."}
    return await run_op(authorization, op)


@app.post("/operations/delete")
async def delete(data: DeviceIn, authorization: str | None = Header(default=None)):
    async def op(page):
        await delete_device(page, data.device.strip().upper())
        return {"ok": True, "message": "Dispositivo removido."}
    return await run_op(authorization, op)


@app.post("/operations/reset")
async def reset(data: ActivateIn, authorization: str | None = Header(default=None)):
    async def op(page):
        dev = data.device.strip().upper()
        await reset_device(page, dev, data.playlist.strip())
        return {"ok": True, "message": "Editar (Reset) + DNS concluído."}
    return await run_op(authorization, op)

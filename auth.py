from fastapi import APIRouter, HTTPException
import logging
import secrets
import time
from jose import jwt
from datetime import datetime, timedelta
from config import config
from email_service import email_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = config.STRIPE_SECRET_KEY or "change-me-in-production"
ALGORITHM = "HS256"

magic_link_attempts = {}

@router.post("/magic-link")
async def request_magic_link(email: str):
    current_time = time.time()
    attempts_key = f"{email}:{int(current_time / 60)}"

    if attempts_key in magic_link_attempts and magic_link_attempts[attempts_key] >= 3:
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")

    magic_link_attempts[attempts_key] = magic_link_attempts.get(attempts_key, 0) + 1

    token = jwt.encode({
        'email': email,
        'exp': datetime.utcnow() + timedelta(days=7),
        'iat': datetime.utcnow(),
        'type': 'magic_link'
    }, SECRET_KEY, algorithm=ALGORITHM)

    magic_link = f"https://yourdomain.com/auth/verify?token={token}"

    subject = "Your Magic Link"
    body = f"""Click the link below to sign in to your account:

{magic_link}

This link will expire in 7 days.

If you didn't request this link, please ignore this email."""

    success = email_service.send_email(email, subject, body)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to send magic link")

    logger.info(f"Magic link sent to {email}")

    return {
        "status": "sent",
        "email": email,
        "message": "Check your email for the magic link"
    }

@router.get("/verify")
async def verify_magic_link(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        if payload.get('type') != 'magic_link':
            raise HTTPException(status_code=400, detail="Invalid token type")

        email = payload.get('email')

        logger.info(f"Magic link verified for {email}")

        return {
            "status": "verified",
            "email": email,
            "token": token
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

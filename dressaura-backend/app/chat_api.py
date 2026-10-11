
import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from . import auth
from .auth import get_current_user
from .chat_models import Conversation, Message, Offer
from .chat_ws import manager
from .database import SessionLocal, get_db
from .models import Dress, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

MAX_MESSAGE_LENGTH = 5000


def _utc_iso(value: datetime | None) -> str | None:
    """Serialize DB datetimes as explicit UTC so browsers don't treat them as local time."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _conversation_for_user(
    conversation_id: int,
    user_id: int,
    db: Session,
) -> Conversation:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if user_id not in (conversation.user1_id, conversation.user2_id):
        raise HTTPException(
            status_code=403,
            detail="Not a participant in this conversation",
        )

    return conversation


@router.post("/conversation")
def create_or_get_conversation(
    user1_id: int,
    user2_id: int,
    product_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id not in (user1_id, user2_id) or user1_id == user2_id:
        raise HTTPException(status_code=403, detail="Invalid conversation participants")

    other_user_id = user2_id if current_user.id == user1_id else user1_id

    if not db.query(User.id).filter(User.id == other_user_id).first():
        raise HTTPException(status_code=404, detail="User not found")

    if product_id is not None:
        dress = db.query(Dress).filter(Dress.id == product_id).first()

        if not dress or dress.user_id != other_user_id:
            raise HTTPException(
                status_code=400,
                detail="Dress does not belong to the other participant",
            )

    conversation = (
        db.query(Conversation)
        .filter(
            or_(
                (Conversation.user1_id == user1_id)
                & (Conversation.user2_id == user2_id),
                (Conversation.user1_id == user2_id)
                & (Conversation.user2_id == user1_id),
            ),
            Conversation.product_id == product_id,
        )
        .first()
    )

    if conversation:
        return conversation

    conversation = Conversation(
        user1_id=user1_id,
        user2_id=user2_id,
        product_id=product_id,
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation


@router.get("/user-conversations/{user_id}")
def get_user_conversations(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot view another user's conversations",
        )

    conversations = (
        db.query(Conversation)
        .filter(
            or_(
                Conversation.user1_id == user_id,
                Conversation.user2_id == user_id,
            )
        )
        .all()
    )

    result = []

    for conversation in conversations:
        last_message = (
            db.query(Message)
            .filter(Message.conversation_id == conversation.id)
            .order_by(desc(Message.created_at), desc(Message.id))
            .first()
        )

        last_offer = (
            db.query(Offer)
            .filter(Offer.conversation_id == conversation.id)
            .order_by(desc(Offer.created_at), desc(Offer.id))
            .first()
        )

        other_user_id = (
            conversation.user2_id
            if conversation.user1_id == user_id
            else conversation.user1_id
        )

        other_user = db.query(User).filter(User.id == other_user_id).first()
        dress = (
            db.query(Dress)
            .filter(Dress.id == conversation.product_id)
            .first()
        )

        last_text = None
        last_time = None

        if last_message and last_offer:
            if last_offer.created_at > last_message.created_at:
                last_text = f"Offer made: €{float(last_offer.amount)}"
                last_time = last_offer.created_at
            else:
                last_text = last_message.message_text
                last_time = last_message.created_at
        elif last_offer:
            last_text = f"Offer made: €{float(last_offer.amount)}"
            last_time = last_offer.created_at
        elif last_message:
            last_text = last_message.message_text
            last_time = last_message.created_at

        result.append(
            {
                "conversation_id": conversation.id,
                "other_user_id": other_user_id,
                "other_user_name": (
                    other_user.name if other_user else f"User {other_user_id}"
                ),
                "last_message": last_text,
                "last_message_time": _utc_iso(last_time),
                "product": (
                    {
                        "id": dress.id,
                        "user_id": dress.user_id,
                        "brand": dress.brand,
                        "price": float(dress.price),
                        "size": dress.size,
                        "image_url": dress.image_url,
                        "is_sold": dress.is_sold,
                    }
                    if dress
                    else None
                ),
            }
        )

    result.sort(
        key=lambda item: item["last_message_time"] or "",
        reverse=True,
    )

    return result


@router.get("/conversation/{conversation_id}/messages")
def get_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _conversation_for_user(conversation_id, current_user.id, db)

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .all()
    )

    return [
        {
            "id": message.id,
            "sender_id": message.sender_id,
            "message": message.message_text,
            "created_at": _utc_iso(message.created_at),
        }
        for message in messages
    ]


def _authenticate_token(token: str) -> int | None:
    """Blocking helper: return the user id for a valid token (own short-lived session)."""
    with SessionLocal() as db:
        user = auth.get_user_from_token(token, db)
        return user.id if user else None


def _save_message(
    sender_id: int,
    conversation_id: int,
    receiver_id: int,
    text: str,
) -> tuple[dict | None, str | None]:
    """Blocking helper: validate + persist one message. Returns (event, error)."""
    with SessionLocal() as db:
        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )

        if not conversation or sender_id not in (
            conversation.user1_id,
            conversation.user2_id,
        ):
            return None, "Invalid conversation"

        expected_receiver_id = (
            conversation.user2_id
            if conversation.user1_id == sender_id
            else conversation.user1_id
        )

        if receiver_id != expected_receiver_id:
            return None, "Invalid recipient"

        message = Message(
            conversation_id=conversation.id,
            sender_id=sender_id,
            message_text=text,
        )

        try:
            db.add(message)
            db.commit()
            db.refresh(message)
        except Exception:
            db.rollback()
            logger.exception("Could not save chat message")
            return None, "Message could not be saved. Please try again."

        return (
            {
                "type": "message",
                "conversation_id": conversation.id,
                "sender_id": sender_id,
                "receiver_id": receiver_id,
                "message": message.message_text,
                "message_id": message.id,
                "created_at": _utc_iso(message.created_at),
            },
            None,
        )


async def _receive_json(websocket: WebSocket):
    """Receive a text frame and parse it; return None for malformed JSON instead of raising."""
    raw = await websocket.receive_text()
    try:
        return json.loads(raw)
    except ValueError:
        return None


@router.websocket("/ws/{user_id}")
async def websocket_chat(websocket: WebSocket, user_id: int):
    # NOTE: no Depends(get_db) here. A dependency session would be held open for the
    # whole connection (exhausting the pool and dying on idle timeouts) and its blocking
    # queries would stall the event loop. Each operation opens its own short session
    # in a worker thread instead.
    logger.info("Chat WebSocket connection requested for user_id=%s", user_id)

    await websocket.accept()
    registered = False

    try:
        try:
            authentication = await asyncio.wait_for(_receive_json(websocket), timeout=10)
        except asyncio.TimeoutError:
            logger.warning("Chat WebSocket auth timed out for user_id=%s", user_id)
            await websocket.close(code=1008)
            return

        token = authentication.get("token") if isinstance(authentication, dict) else None
        authenticated_id = (
            await run_in_threadpool(_authenticate_token, token)
            if isinstance(token, str)
            else None
        )

        if authenticated_id is None or authenticated_id != user_id:
            logger.warning(
                "Chat WebSocket auth rejected: requested_user_id=%s authenticated=%s",
                user_id,
                authenticated_id is not None,
            )
            await websocket.close(code=1008)
            return

        await manager.connect(user_id, websocket, accept=False)
        registered = True
        await websocket.send_json({"type": "ready"})

        while True:
            data = await _receive_json(websocket)

            if not isinstance(data, dict):
                await websocket.send_json({"type": "error", "detail": "Invalid message"})
                continue

            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            try:
                conversation_id = int(data.get("conversation_id", 0))
                receiver_id = int(data.get("receiver_id", 0))
            except (TypeError, ValueError):
                await websocket.send_json({"type": "error", "detail": "Invalid conversation"})
                continue

            message_text = data.get("message")

            if not isinstance(message_text, str) or not message_text.strip():
                await websocket.send_json({"type": "error", "detail": "Message cannot be empty"})
                continue

            if len(message_text) > MAX_MESSAGE_LENGTH:
                await websocket.send_json({"type": "error", "detail": "Message is too long"})
                continue

            event, error = await run_in_threadpool(
                _save_message,
                user_id,
                conversation_id,
                receiver_id,
                message_text.strip(),
            )

            if error or event is None:
                await websocket.send_json({"type": "error", "detail": error or "Invalid message"})
                continue

            await manager.send_message(user_id, event)
            if receiver_id != user_id:
                await manager.send_message(receiver_id, event)

    except WebSocketDisconnect:
        logger.info("Chat WebSocket disconnected for user_id=%s", user_id)

    except Exception:
        logger.exception("Unexpected chat WebSocket failure for user_id=%s", user_id)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass

    finally:
        if registered:
            manager.disconnect(user_id, websocket)


@router.get("/users/{current_user_id}")
def get_all_users(
    current_user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != current_user_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot view users as another account",
        )

    users = db.query(User).filter(User.id != current_user_id).all()

    return [{"id": user.id, "name": user.name} for user in users]


@router.post("/offers")
def create_offer(
    conversation_id: int,
    dress_id: int,
    buyer_id: int,
    seller_id: int,
    amount: float,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = _conversation_for_user(conversation_id, current_user.id, db)
    dress = db.query(Dress).filter(Dress.id == dress_id).first()

    if (
        not dress
        or conversation.product_id != dress_id
        or current_user.id != buyer_id
        or dress.user_id != seller_id
        or seller_id not in (conversation.user1_id, conversation.user2_id)
        or amount <= 0
    ):
        raise HTTPException(status_code=400, detail="Invalid offer")

    offer = Offer(
        conversation_id=conversation_id,
        dress_id=dress_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
        amount=amount,
        status="pending",
    )

    db.add(offer)
    db.commit()
    db.refresh(offer)

    return {
        "id": offer.id,
        "conversation_id": offer.conversation_id,
        "dress_id": offer.dress_id,
        "buyer_id": offer.buyer_id,
        "seller_id": offer.seller_id,
        "amount": float(offer.amount),
        "status": offer.status,
        "created_at": _utc_iso(offer.created_at),
    }


@router.get("/conversation/{conversation_id}/offers")
def get_conversation_offers(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _conversation_for_user(conversation_id, current_user.id, db)

    offers = (
        db.query(Offer)
        .filter(Offer.conversation_id == conversation_id)
        .order_by(Offer.created_at.asc(), Offer.id.asc())
        .all()
    )

    return [
        {
            "id": offer.id,
            "conversation_id": offer.conversation_id,
            "dress_id": offer.dress_id,
            "buyer_id": offer.buyer_id,
            "seller_id": offer.seller_id,
            "amount": float(offer.amount),
            "status": offer.status,
            "created_at": _utc_iso(offer.created_at),
        }
        for offer in offers
    ]


def _update_offer(
    offer_id: int,
    status: str,
    db: Session,
    current_user: User,
):
    offer = db.query(Offer).filter(Offer.id == offer_id).first()

    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    _conversation_for_user(offer.conversation_id, current_user.id, db)

    if current_user.id != offer.seller_id:
        raise HTTPException(
            status_code=403,
            detail="Only the seller can respond to this offer",
        )

    if offer.status != "pending":
        raise HTTPException(status_code=409, detail="Offer is no longer pending")

    offer.status = status
    db.commit()
    db.refresh(offer)

    return {
        "message": f"Offer {status}",
        "offer_id": offer.id,
        "status": offer.status,
    }


@router.put("/offers/{offer_id}/accept")
def accept_offer(
    offer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _update_offer(offer_id, "accepted", db, current_user)


@router.put("/offers/{offer_id}/decline")
def decline_offer(
    offer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _update_offer(offer_id, "declined", db, current_user)

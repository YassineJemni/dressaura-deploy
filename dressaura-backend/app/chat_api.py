from datetime import datetime
import asyncio

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from . import auth
from .auth import get_current_user
from .chat_models import Conversation, Message, Offer
from .chat_ws import manager
from .database import get_db
from .models import Dress, User

router = APIRouter(prefix="/chat", tags=["chat"])


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
        raise HTTPException(status_code=403, detail="Not a participant in this conversation")
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
            raise HTTPException(status_code=400, detail="Dress does not belong to the other participant")

    conversation = (
        db.query(Conversation)
        .filter(
            or_(
                (Conversation.user1_id == user1_id) & (Conversation.user2_id == user2_id),
                (Conversation.user1_id == user2_id) & (Conversation.user2_id == user1_id),
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
        raise HTTPException(status_code=403, detail="Cannot view another user's conversations")

    conversations = (
        db.query(Conversation)
        .filter(or_(Conversation.user1_id == user_id, Conversation.user2_id == user_id))
        .all()
    )
    result = []

    for conversation in conversations:
        last_message = (
            db.query(Message)
            .filter(Message.conversation_id == conversation.id)
            .order_by(desc(Message.created_at))
            .first()
        )
        last_offer = (
            db.query(Offer)
            .filter(Offer.conversation_id == conversation.id)
            .order_by(desc(Offer.created_at))
            .first()
        )
        other_user_id = (
            conversation.user2_id
            if conversation.user1_id == user_id
            else conversation.user1_id
        )
        other_user = db.query(User).filter(User.id == other_user_id).first()
        dress = db.query(Dress).filter(Dress.id == conversation.product_id).first()

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
                "other_user_name": other_user.name if other_user else f"User {other_user_id}",
                "last_message": last_text,
                "last_message_time": last_time,
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
        key=lambda item: item["last_message_time"] or datetime.min,
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
        .order_by(Message.created_at.asc())
        .all()
    )
    return [
        {
            "id": message.id,
            "sender_id": message.sender_id,
            "message": message.message_text,
            "created_at": message.created_at,
        }
        for message in messages
    ]


@router.websocket("/ws/{user_id}")
async def websocket_chat(
    websocket: WebSocket,
    user_id: int,
    db: Session = Depends(get_db),
):
    await websocket.accept()
    try:
        try:
            authentication = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        except TimeoutError:
            await websocket.close(code=1008)
            return

        token = authentication.get("token") if isinstance(authentication, dict) else None
        current_user = auth.get_user_from_token(token, db) if isinstance(token, str) else None
        if not current_user or current_user.id != user_id:
            await websocket.close(code=1008)
            return

        await manager.connect(user_id, websocket, accept=False)
        await websocket.send_json({"type": "ready"})

        while True:
            data = await websocket.receive_json()
            if not isinstance(data, dict):
                await websocket.send_json({"type": "error", "detail": "Invalid message"})
                continue

            try:
                conversation_id = int(data.get("conversation_id", 0))
                receiver_id = int(data.get("receiver_id", 0))
            except (TypeError, ValueError):
                await websocket.send_json({"type": "error", "detail": "Invalid conversation"})
                continue

            conversation = (
                db.query(Conversation)
                .filter(Conversation.id == conversation_id)
                .first()
            )
            if not conversation or user_id not in (conversation.user1_id, conversation.user2_id):
                await websocket.send_json({"type": "error", "detail": "Invalid conversation"})
                continue

            expected_receiver_id = (
                conversation.user2_id
                if conversation.user1_id == user_id
                else conversation.user1_id
            )
            if receiver_id != expected_receiver_id:
                await websocket.send_json({"type": "error", "detail": "Invalid recipient"})
                continue

            message_text = data.get("message")
            if not isinstance(message_text, str) or not message_text.strip():
                await websocket.send_json({"type": "error", "detail": "Message cannot be empty"})
                continue
            if len(message_text) > 5000:
                await websocket.send_json({"type": "error", "detail": "Message is too long"})
                continue

            message = Message(
                conversation_id=conversation.id,
                sender_id=user_id,
                message_text=message_text.strip(),
            )
            db.add(message)
            db.commit()
            db.refresh(message)

            event = {
                "type": "message",
                "conversation_id": conversation.id,
                "sender_id": user_id,
                "receiver_id": receiver_id,
                "message": message.message_text,
                "message_id": message.id,
                "created_at": message.created_at.isoformat() if message.created_at else None,
            }
            await manager.send_message(user_id, event)
            await manager.send_message(receiver_id, event)
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(user_id, websocket)


@router.get("/users/{current_user_id}")
def get_all_users(
    current_user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != current_user_id:
        raise HTTPException(status_code=403, detail="Cannot view users as another account")
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
        "created_at": offer.created_at,
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
        .order_by(Offer.created_at.asc())
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
            "created_at": offer.created_at,
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
        raise HTTPException(status_code=403, detail="Only the seller can respond to this offer")
    if offer.status != "pending":
        raise HTTPException(status_code=409, detail="Offer is no longer pending")

    offer.status = status
    db.commit()
    db.refresh(offer)
    return {"message": f"Offer {status}", "offer_id": offer.id, "status": offer.status}


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

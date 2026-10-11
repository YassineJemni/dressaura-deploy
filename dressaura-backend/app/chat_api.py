from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from .database import get_db, SessionLocal
from .chat_models import Conversation, Message, Offer
from .chat_ws import manager
from .models import User
from datetime import datetime

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/conversation")
def create_or_get_conversation(
    user1_id: int,
    user2_id: int,
    product_id: int | None = None,
    db: Session = Depends(get_db)
):
    conversation = db.query(Conversation).filter(
        (
            ((Conversation.user1_id == user1_id) & (Conversation.user2_id == user2_id)) |
            ((Conversation.user1_id == user2_id) & (Conversation.user2_id == user1_id))
        ),
        Conversation.product_id == product_id
    ).first()

    if conversation:
        return conversation

    new_convo = Conversation(
        user1_id=user1_id,
        user2_id=user2_id,
        product_id=product_id
    )

    db.add(new_convo)
    db.commit()
    db.refresh(new_convo)
    return new_convo

@router.get("/user-conversations/{user_id}")
def get_user_conversations(user_id: int, db: Session = Depends(get_db)):
    from .models import User, Dress

    conversations = db.query(Conversation).filter(
        or_(Conversation.user1_id == user_id, Conversation.user2_id == user_id)
    ).all()

    result = []

    for conv in conversations:
        last_msg = db.query(Message).filter(
            Message.conversation_id == conv.id
        ).order_by(desc(Message.created_at)).first()

        last_offer = db.query(Offer).filter(
            Offer.conversation_id == conv.id
        ).order_by(desc(Offer.created_at)).first()

        other_user_id = conv.user2_id if conv.user1_id == user_id else conv.user1_id
        other_user = db.query(User).filter(User.id == other_user_id).first()
        dress = db.query(Dress).filter(Dress.id == conv.product_id).first()

        last_message = None
        last_message_time = None

        if last_msg and last_offer:
            if last_offer.created_at > last_msg.created_at:
                last_message = f"Offer made: €{float(last_offer.amount)}"
                last_message_time = last_offer.created_at
            else:
                last_message = last_msg.message_text
                last_message_time = last_msg.created_at
        elif last_offer:
            last_message = f"Offer made: €{float(last_offer.amount)}"
            last_message_time = last_offer.created_at
        elif last_msg:
            last_message = last_msg.message_text
            last_message_time = last_msg.created_at

        result.append({
            "conversation_id": conv.id,
            "other_user_id": other_user_id,
            "other_user_name": other_user.name if other_user else f"User {other_user_id}",
            "last_message": last_message,
            "last_message_time": last_message_time,
            "product": {
                "id": dress.id,
                "user_id": dress.user_id,
                "brand": dress.brand,
                "price": float(dress.price),
                "size": dress.size,
                "image_url": dress.image_url,
                "is_sold": dress.is_sold,
            } if dress else None,
        })

    result.sort(
        key=lambda x: x["last_message_time"] or datetime.min,
        reverse=True
    )

    return result



@router.get("/conversation/{conversation_id}/messages")
def get_messages(conversation_id: int, db: Session = Depends(get_db)):
    messages = db.query(Message)\
                 .filter(Message.conversation_id == conversation_id)\
                 .order_by(Message.created_at.asc())\
                 .all()
    return [
        {
            "id": msg.id,
            "sender_id": msg.sender_id,
            "message": msg.message_text,
            "created_at": msg.created_at,
        } for msg in messages
    ]


@router.websocket("/ws/{user_id}")
async def websocket_chat(websocket: WebSocket, user_id: int):
    await manager.connect(user_id, websocket)
    db: Session = SessionLocal()

    try:
        while True:
            data = await websocket.receive_json()
            receiver_id = data["receiver_id"]
            message_text = data["message"]

            conversation_id = data.get("conversation_id")

            conversation = None

            if conversation_id:
                conversation = db.query(Conversation).filter(
                    Conversation.id == conversation_id
                ).first()

            if not conversation:
                conversation = db.query(Conversation).filter(
                    ((Conversation.user1_id == user_id) & (Conversation.user2_id == receiver_id)) |
                    ((Conversation.user1_id == receiver_id) & (Conversation.user2_id == user_id))
                ).first()

            if not conversation:
                conversation = Conversation(user1_id=user_id, user2_id=receiver_id)
                db.add(conversation)
                db.commit()
                db.refresh(conversation)

            new_message = Message(
                conversation_id=conversation.id,
                sender_id=user_id,
                message_text=message_text
            )
            db.add(new_message)
            db.commit()
            db.refresh(new_message)

            await manager.send_message(receiver_id, {
                "conversation_id": conversation.id,
                "sender_id": user_id,
                "message": message_text,
                "message_id": new_message.id,
            })

    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
    finally:
        db.close()

@router.get("/users/{current_user_id}")
def get_all_users(current_user_id: int, db: Session = Depends(get_db)):
    users = db.query(User).filter(User.id != current_user_id).all()
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "created_at": u.created_at,
        } for u in users
    ]


@router.post("/offers")
def create_offer(
    conversation_id: int,
    dress_id: int,
    buyer_id: int,
    seller_id: int,
    amount: float,
    db: Session = Depends(get_db)
):
    offer = Offer(
        conversation_id=conversation_id,
        dress_id=dress_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
        amount=amount,
        status="pending"
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
def get_conversation_offers(conversation_id: int, db: Session = Depends(get_db)):
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


@router.put("/offers/{offer_id}/accept")
def accept_offer(offer_id: int, db: Session = Depends(get_db)):
    offer = db.query(Offer).filter(Offer.id == offer_id).first()

    if not offer:
        return {"error": "Offer not found"}

    offer.status = "accepted"
    db.commit()
    db.refresh(offer)

    return {"message": "Offer accepted", "offer_id": offer.id, "status": offer.status}


@router.put("/offers/{offer_id}/decline")
def decline_offer(offer_id: int, db: Session = Depends(get_db)):
    offer = db.query(Offer).filter(Offer.id == offer_id).first()

    if not offer:
        return {"error": "Offer not found"}

    offer.status = "declined"
    db.commit()
    db.refresh(offer)

    return {"message": "Offer declined", "offer_id": offer.id, "status": offer.status}
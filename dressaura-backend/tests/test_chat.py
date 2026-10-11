import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "test-secret-key-only")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "3306")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth
from app import deps
from app.auth import create_access_token
from app.chat_api import router
from app.database import Base, get_db
from app.models import Dress, User
from app.routers import auth as auth_routes
from app.routers import dresses, orders


class ChatWebSocketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.session_factory = sessionmaker(bind=cls.engine, autoflush=False)
        Base.metadata.create_all(bind=cls.engine)

        cls.app = FastAPI()
        cls.app.include_router(router)
        cls.app.include_router(auth_routes.router)
        cls.app.include_router(dresses.router)
        cls.app.include_router(orders.router)

        def test_db():
            db = cls.session_factory()
            try:
                yield db
            finally:
                db.close()

        cls.app.dependency_overrides[get_db] = test_db
        cls.app.dependency_overrides[deps.get_db] = test_db
        cls.app.dependency_overrides[auth.get_db] = test_db
        cls.app.dependency_overrides[auth_routes.get_db] = test_db

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=cls.engine)
        cls.engine.dispose()

    def setUp(self):
        self.upload_directory = tempfile.TemporaryDirectory()
        self.upload_path_patch = patch.object(
            dresses,
            "UPLOAD_DIR",
            Path(self.upload_directory.name),
        )
        self.upload_path_patch.start()
        self.addCleanup(self.upload_path_patch.stop)
        self.addCleanup(self.upload_directory.cleanup)

        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        with self.session_factory() as db:
            self.buyer = User(name="Buyer", email="buyer@example.com", password="hash")
            self.seller = User(name="Seller", email="seller@example.com", password="hash")
            self.other = User(name="Other", email="other@example.com", password="hash")
            db.add_all([self.buyer, self.seller, self.other])
            db.commit()
            db.refresh(self.buyer)
            db.refresh(self.seller)
            db.refresh(self.other)
            self.dress = Dress(
                user_id=self.seller.id,
                brand="Test Dress",
                size="M",
                condition_status="Good",
                price=30,
            )
            db.add(self.dress)
            db.commit()
            db.refresh(self.dress)
            self.buyer_id = self.buyer.id
            self.seller_id = self.seller.id
            self.other_id = self.other.id
            self.dress_id = self.dress.id

        self.buyer_token = create_access_token({"sub": "buyer@example.com"})
        self.seller_token = create_access_token({"sub": "seller@example.com"})
        self.other_token = create_access_token({"sub": "other@example.com"})
        self.client = TestClient(self.app)

    def test_two_users_exchange_persisted_messages(self):
        response = self.client.post(
            "/chat/conversation",
            params={
                "user1_id": self.buyer_id,
                "user2_id": self.seller_id,
                "product_id": self.dress_id,
            },
            headers={"Authorization": f"Bearer {self.buyer_token}"},
        )
        self.assertEqual(response.status_code, 200)
        conversation_id = response.json()["id"]

        with self.client.websocket_connect(
            f"/chat/ws/{self.buyer_id}"
        ) as buyer_socket:
            with self.client.websocket_connect(
                f"/chat/ws/{self.seller_id}"
            ) as seller_socket:
                buyer_socket.send_json({"type": "auth", "token": self.buyer_token})
                seller_socket.send_json({"type": "auth", "token": self.seller_token})
                self.assertEqual(buyer_socket.receive_json()["type"], "ready")
                self.assertEqual(seller_socket.receive_json()["type"], "ready")
                buyer_socket.send_json(
                    {
                        "conversation_id": conversation_id,
                        "receiver_id": self.seller_id,
                        "message": "Hello from the buyer",
                    }
                )
                buyer_event = buyer_socket.receive_json()
                seller_event = seller_socket.receive_json()
                seller_socket.send_json(
                    {
                        "conversation_id": conversation_id,
                        "receiver_id": self.buyer_id,
                        "message": "Hello from the seller",
                    }
                )
                seller_reply = seller_socket.receive_json()
                buyer_reply = buyer_socket.receive_json()

        self.assertEqual(buyer_event, seller_event)
        self.assertEqual(buyer_event["type"], "message")
        self.assertEqual(buyer_event["sender_id"], self.buyer_id)
        self.assertEqual(buyer_event["message"], "Hello from the buyer")
        self.assertGreater(buyer_event["message_id"], 0)
        self.assertEqual(seller_reply, buyer_reply)
        self.assertEqual(seller_reply["sender_id"], self.seller_id)

        response = self.client.get(
            f"/chat/conversation/{conversation_id}/messages",
            headers={"Authorization": f"Bearer {self.seller_token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
        self.assertEqual(response.json()[0]["message"], "Hello from the buyer")
        self.assertEqual(response.json()[1]["message"], "Hello from the seller")

    def test_nonparticipant_cannot_read_messages_or_connect_as_another_user(self):
        response = self.client.post(
            "/chat/conversation",
            params={
                "user1_id": self.buyer_id,
                "user2_id": self.seller_id,
                "product_id": self.dress_id,
            },
            headers={"Authorization": f"Bearer {self.buyer_token}"},
        )
        conversation_id = response.json()["id"]

        response = self.client.get(
            f"/chat/conversation/{conversation_id}/messages",
            headers={"Authorization": f"Bearer {self.other_token}"},
        )
        self.assertEqual(response.status_code, 403)

        from starlette.websockets import WebSocketDisconnect

        with self.client.websocket_connect(f"/chat/ws/{self.buyer_id}") as socket:
            socket.send_json({"type": "auth", "token": self.other_token})
            with self.assertRaises(WebSocketDisconnect):
                socket.receive_json()

    def test_listing_upload_and_mutations_enforce_owner(self):
        response = self.client.post(
            "/dresses/",
            data={
                "brand": "Uploaded Dress",
                "size": "M",
                "condition_status": "Good",
                "price": "42",
                "description": "Two image test",
            },
            files=[
                ("images", ("front.png", b"front image bytes", "image/png")),
                ("images", ("back.png", b"back image bytes", "image/png")),
            ],
            headers={"Authorization": f"Bearer {self.buyer_token}"},
        )
        self.assertEqual(response.status_code, 200)
        created = response.json()
        self.assertEqual(created["user_id"], self.buyer_id)
        self.assertEqual(len(created["images"]), 2)
        self.assertEqual(created["image_url"], created["images"][0]["image_url"])
        self.assertTrue((Path(self.upload_directory.name) / Path(created["image_url"]).name).exists())
        self.app.mount(
            "/uploads/dresses",
            StaticFiles(directory=self.upload_directory.name),
            name="test-dress-uploads",
        )
        image_response = self.client.get(created["image_url"])
        self.assertEqual(image_response.status_code, 200)
        self.assertEqual(image_response.content, b"front image bytes")

        response = self.client.put(
            f"/dresses/{created['id']}",
            json={
                "brand": "Changed",
                "size": "M",
                "condition_status": "Good",
                "price": 45,
                "description": "Updated",
            },
            headers={"Authorization": f"Bearer {self.seller_token}"},
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.put(
            f"/dresses/{created['id']}",
            json={
                "brand": "Updated Dress",
                "size": "M",
                "condition_status": "Good",
                "price": 45,
                "description": "Updated",
            },
            headers={"Authorization": f"Bearer {self.buyer_token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["brand"], "Updated Dress")

        response = self.client.delete(
            f"/dresses/{created['id']}",
            headers={"Authorization": f"Bearer {self.seller_token}"},
        )
        self.assertEqual(response.status_code, 403)

        image_id = created["images"][0]["id"]
        response = self.client.delete(
            f"/dresses/images/{image_id}",
            headers={"Authorization": f"Bearer {self.seller_token}"},
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.delete(
            f"/dresses/images/{image_id}",
            headers={"Authorization": f"Bearer {self.buyer_token}"},
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.delete(
            f"/dresses/{created['id']}",
            headers={"Authorization": f"Bearer {self.buyer_token}"},
        )
        self.assertEqual(response.status_code, 200)

    def test_order_uses_listing_price_and_marks_item_sold(self):
        response = self.client.post(
            "/orders/",
            params={
                "user_id": self.buyer_id,
                "dress_id": self.dress_id,
                "payment_method": "cash",
                "delivery_company": "DPD",
                "order_price": 0.01,
            },
            headers={"Authorization": f"Bearer {self.buyer_token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["order_price"], 30)

        with self.session_factory() as db:
            order = db.query(orders.Order).filter_by(id=response.json()["order_id"]).one()
            dress = db.query(Dress).filter_by(id=self.dress_id).one()
            self.assertEqual(float(order.order_price), 30)
            self.assertTrue(dress.is_sold)

    def test_existing_user_login_and_token_validation(self):
        existing_user = User(
            name="Existing Account",
            email="existing-account@example.com",
            password="$2b$12$ToFfXSnxJklNf/uuEkhCY.OjS2pVViW6gVFY2O2tzAv3V2O2vLQNa",
        )
        with self.session_factory() as db:
            db.add(existing_user)
            db.commit()
            db.refresh(existing_user)
            existing_user_id = existing_user.id

        response = self.client.post(
            "/auth/login",
            json={
                "email": "existing-account@example.com",
                "password": "existing-user-password-for-regression",
            },
        )
        self.assertEqual(response.status_code, 200)
        access_token = response.json()["access_token"]
        self.assertEqual(
            auth.jwt.decode(access_token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])["sub"],
            str(existing_user_id),
        )

        response = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], existing_user_id)
        self.assertEqual(response.json()["email"], "existing-account@example.com")

        legacy_token = create_access_token({"sub": "existing-account@example.com"})
        response = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {legacy_token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], existing_user_id)

    def test_registration_login_and_profile_update_require_valid_session(self):
        response = self.client.post(
            "/auth/register",
            json={
                "name": "New Account",
                "email": "new-account@example.com",
                "password": "a test password",
            },
        )
        self.assertEqual(response.status_code, 200)
        registered = response.json()
        self.assertNotIn("password", registered["user"])

        response = self.client.post(
            "/auth/login",
            json={
                "email": "new-account@example.com",
                "password": "a test password",
            },
        )
        self.assertEqual(response.status_code, 200)
        token = response.json()["access_token"]

        response = self.client.put(
            f"/auth/users/{self.buyer_id}",
            json={"name": "Changed Name", "email": "changed@example.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 403)

        registered_user_id = registered["user"]["id"]
        response = self.client.put(
            f"/auth/users/{registered_user_id}",
            json={"name": "Changed Name", "email": "changed@example.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "changed@example.com")

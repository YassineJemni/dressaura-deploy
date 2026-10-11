import logging

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self.logger = logging.getLogger(__name__)

    async def connect(
        self,
        user_id: int,
        websocket: WebSocket,
        accept: bool = True,
    ):
        if accept:
            await websocket.accept()

        if user_id not in self.active_connections:
            self.active_connections[user_id] = []

        self.active_connections[user_id].append(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket):
        connections = self.active_connections.get(user_id)
        if not connections:
            return

        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            self.active_connections.pop(user_id, None)

    async def send_message(self, user_id: int, message: dict):
        for connection in tuple(self.active_connections.get(user_id, [])):
            try:
                await connection.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                self.logger.debug("Removing a closed chat connection")
                self.disconnect(user_id, connection)


manager = ConnectionManager()
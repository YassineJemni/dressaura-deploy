import "./Chats.css";

export default function Chats() {
  return (
    <div className="chats-page">
      <h1>Chats</h1>
      <p className="subtitle">Your conversations</p>

      <div className="chats-card">
        <div className="chat-item">
          <div className="chat-avatar">S</div>
          <div className="chat-info">
            <h4>Sara</h4>
            <p>Is the dress still available?</p>
          </div>
          <span className="time">2m</span>
        </div>

        <div className="chat-item unread">
          <div className="chat-avatar">L</div>
          <div className="chat-info">
            <h4>Lina</h4>
            <p>Can you lower the price?</p>
          </div>
          <span className="time">1h</span>
        </div>
      </div>
    </div>
  );
}

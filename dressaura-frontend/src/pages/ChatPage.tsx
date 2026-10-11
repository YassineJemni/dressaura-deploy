
import React, { useEffect, useState, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import "./ChatPage.css";

const API_URL = "https://dressaura-backend.vercel.app";
const WS_URL = "wss://dressaura-backend.vercel.app";

export default function ChatPage() {
  const [conversations, setConversations] = useState([]);
  const [activeConversation, setActiveConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState("");
  const [chatProduct, setChatProduct] = useState(null);
  const [notice, setNotice] = useState("");

  const showNotice = (message: string) => {
    setNotice(message);

    setTimeout(() => {
      setNotice("");
    }, 3000);
  };

  const [offers, setOffers] = useState([]);
  const [offerAmount, setOfferAmount] = useState("");

  const socketRef = useRef(null);
  const messagesEndRef = useRef(null);
  const messagesAreaRef = useRef(null);

  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const CURRENT_USER_ID = user?.id;

  const sortConversations = (items) => {
    return [...items]
      .filter((c) => c.last_message)
      .sort((a, b) => {
        const timeA = a.last_message_time
          ? new Date(a.last_message_time).getTime()
          : 0;
        const timeB = b.last_message_time
          ? new Date(b.last_message_time).getTime()
          : 0;
        return timeB - timeA;
      });
  };

  useEffect(() => {
    if (!CURRENT_USER_ID) return;

    fetch(`${API_URL}/chat/user-conversations/${CURRENT_USER_ID}`)
      .then((r) => r.json())
      .then((data) => setConversations(sortConversations(data)))
      .catch(console.error);
  }, [CURRENT_USER_ID]);

  useEffect(() => {
    const conversationId = location.state?.conversationId;

    if (!conversationId) return;

    if (
      activeConversation &&
      Number(activeConversation.conversation_id) === Number(conversationId)
    ) {
      if (location.state?.product) {
        setChatProduct(location.state.product);
      }
      return;
    }

    const foundConversation = conversations.find(
      (conv) => Number(conv.conversation_id) === Number(conversationId)
    );

    if (foundConversation) {
      setActiveConversation(foundConversation);
      setChatProduct(foundConversation.product || null);
    } else if (location.state?.sellerId) {
      setActiveConversation({
        conversation_id: Number(conversationId),
        other_user_id: Number(location.state.sellerId),
        other_user_name: location.state?.sellerName || "Seller",
        last_message: null,
      });
    }

    if (location.state?.product) {
      setChatProduct(location.state.product);
    }
  }, [location.state, conversations]);

  useEffect(() => {
    if (!CURRENT_USER_ID) return;

    const timeout = setTimeout(() => {
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }

      const ws = new WebSocket(`${WS_URL}/chat/ws/${CURRENT_USER_ID}`);
      socketRef.current = ws;

      ws.onopen = () => console.log("WS connected");

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const now = new Date().toISOString();

          setConversations((prev) => {
            const existing = prev.find(
              (c) => Number(c.conversation_id) === Number(data.conversation_id)
            );

            const updatedConversation = {
              ...(existing || data),
              conversation_id: data.conversation_id,
              other_user_id: data.sender_id,
              other_user_name:
                existing?.other_user_name || data.other_user_name || "Seller",
              last_message: data.message,
              last_message_time: now,
            };

            return sortConversations([
              updatedConversation,
              ...prev.filter(
                (c) =>
                  Number(c.conversation_id) !== Number(data.conversation_id)
              ),
            ]);
          });

          setMessages((prev) => {
            if (
              Number(activeConversation?.conversation_id) ===
              Number(data.conversation_id)
            ) {
              return [
                ...prev,
                {
                  id: data.message_id,
                  sender_id: data.sender_id,
                  message: data.message,
                  created_at: now,
                },
              ];
            }

            return prev;
          });
        } catch (e) {
          console.error(e);
        }
      };

      ws.onerror = console.error;
      ws.onclose = () => console.log("WS closed");
    }, 50);

    return () => {
      clearTimeout(timeout);
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [CURRENT_USER_ID, activeConversation]);

  useEffect(() => {
    if (!CURRENT_USER_ID || !activeConversation?.other_user_id) return;

    const nameIsMissing =
      !activeConversation.other_user_name ||
      activeConversation.other_user_name === "Seller" ||
      activeConversation.other_user_name.startsWith("User ");

    if (!nameIsMissing) return;

    fetch(`${API_URL}/chat/users/${CURRENT_USER_ID}`)
      .then((res) => res.json())
      .then((users) => {
        const otherUser = users.find(
          (u) => Number(u.id) === Number(activeConversation.other_user_id)
        );

        if (otherUser) {
          setActiveConversation((prev) => ({
            ...prev,
            other_user_name: otherUser.name,
          }));

          setConversations((prev) =>
            prev.map((conv) =>
              Number(conv.conversation_id) ===
              Number(activeConversation.conversation_id)
                ? { ...conv, other_user_name: otherUser.name }
                : conv
            )
          );
        }
      })
      .catch(console.error);
  }, [
    CURRENT_USER_ID,
    activeConversation?.conversation_id,
    activeConversation?.other_user_id,
    activeConversation?.other_user_name,
  ]);

  useEffect(() => {
    if (!activeConversation) return;

    fetch(
      `${API_URL}/chat/conversation/${activeConversation.conversation_id}/messages`
    )
      .then((r) => r.json())
      .then(setMessages)
      .catch(console.error);

    fetch(
      `${API_URL}/chat/conversation/${activeConversation.conversation_id}/offers`
    )
      .then((r) => r.json())
      .then(setOffers)
      .catch(console.error);
  }, [activeConversation?.conversation_id]);

  useEffect(() => {
    if (!activeConversation?.conversation_id) return;

    const interval = setInterval(() => {
      fetch(
        `${API_URL}/chat/conversation/${activeConversation.conversation_id}/offers`
      )
        .then((r) => r.json())
        .then(setOffers)
        .catch(console.error);
    }, 3000);

    return () => clearInterval(interval);
  }, [activeConversation?.conversation_id]);

  useEffect(() => {
    const box = messagesAreaRef.current;
    if (!box) return;

    setTimeout(() => {
      box.scrollTop = box.scrollHeight;
    }, 50);
  }, [activeConversation?.conversation_id, messages.length, offers.length]);

  const sendMessage = () => {
    const socket = socketRef.current;

    if (!newMessage.trim() || !socket || !activeConversation) return;
    if (socket.readyState !== WebSocket.OPEN) return;

    const now = new Date().toISOString();

    socket.send(
      JSON.stringify({
        conversation_id: activeConversation.conversation_id,
        receiver_id: activeConversation.other_user_id,
        message: newMessage,
      })
    );

    setMessages((prev) => [
      ...prev,
      {
        id: Date.now(),
        sender_id: CURRENT_USER_ID,
        message: newMessage,
        created_at: now,
      },
    ]);

    setConversations((prev) => {
      const updatedConversation = {
        ...activeConversation,
        last_message: newMessage,
        last_message_time: now,
      };

      return sortConversations([
        updatedConversation,
        ...prev.filter(
          (c) =>
            Number(c.conversation_id) !==
            Number(activeConversation.conversation_id)
        ),
      ]);
    });

    setActiveConversation((prev) => ({
      ...prev,
      last_message: newMessage,
      last_message_time: now,
    }));

    setNewMessage("");
  };

  const makeOffer = async () => {
    if (!offerAmount || !chatProduct || !activeConversation || !CURRENT_USER_ID) {
      showNotice("Enter an offer amount first.");
      return;
    }

    const sellerId = chatProduct.user_id || activeConversation.other_user_id;

    try {
      const params = new URLSearchParams({
        conversation_id: String(activeConversation.conversation_id),
        dress_id: String(chatProduct.id),
        buyer_id: String(CURRENT_USER_ID),
        seller_id: String(sellerId),
        amount: offerAmount,
      });

      const res = await fetch(`${API_URL}/chat/offers?${params.toString()}`, {
        method: "POST",
      });

      const data = await res.json();

      if (data.error) {
        showNotice(data.error);
        return;
      }

      setOffers((prev) => [...prev, data]);
      setOfferAmount("");
    } catch (error) {
      console.error(error);
      showNotice("Could not send offer.");
    }
  };

  const updateOfferStatus = async (offerId, action) => {
    try {
      const res = await fetch(
        `${API_URL}/chat/offers/${offerId}/${action}`,
        {
          method: "PUT",
        }
      );

      const data = await res.json();

      if (data.error) {
        showNotice(data.error);
        return;
      }

      setOffers((prev) =>
        prev.map((offer) =>
          offer.id === offerId ? { ...offer, status: data.status } : offer
        )
      );
    } catch (error) {
      console.error(error);
      showNotice("Could not update offer.");
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") sendMessage();
  };

  const getInitial = (name) => (name || "?").charAt(0).toUpperCase();

  const formatTime = (ts) => {
    if (!ts) return "";
    return new Date(ts).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const isBuyer =
    chatProduct &&
    Number(chatProduct.user_id) !== Number(CURRENT_USER_ID);

  const isUnavailable = chatProduct?.is_sold === true;

  return (
    <div className="chat-page">
      {notice && <div className="product-notice">{notice}</div>}

      <div className="panel convos-panel">
        <div className="panel-header">
          <div className="panel-title">Messages</div>
          <div className="panel-subtitle">{conversations.length} chats</div>
        </div>

        <div className="panel-body">
          {conversations.length === 0 && (
            <div className="empty-state">
              No conversations yet.
              <br />
              Message a seller to start.
            </div>
          )}

          {conversations.map((conv) => (
            <div
              key={conv.conversation_id}
              className={`chat-item${
                Number(activeConversation?.conversation_id) ===
                Number(conv.conversation_id)
                  ? " active"
                  : ""
              }`}
              onClick={() => {
                setActiveConversation(conv);
                setChatProduct(conv.product || null);
              }}
            >
              <div className="avatar sm">
                {getInitial(conv.other_user_name || `U${conv.other_user_id}`)}
              </div>

              <div className="chat-item-info">
                <div className="chat-item-name">
                  {conv.other_user_name || `User ${conv.other_user_id}`}
                </div>

                <div className="chat-item-preview">{conv.last_message}</div>
              </div>

              {conv.last_message_time && (
                <div className="chat-item-time">
                  {formatTime(conv.last_message_time)}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {activeConversation ? (
        <div className="chat-window">
          <div className="chat-window-header">
            <div className="avatar">
              {getInitial(
                activeConversation.other_user_name ||
                  `U${activeConversation.other_user_id}`
              )}
            </div>

            <div>
              <div className="chat-window-name">
                {activeConversation.other_user_name ||
                  `User ${activeConversation.other_user_id}`}
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: "#4caf7d",
                  marginTop: 1,
                }}
              >
                ● Online
              </div>
            </div>

            <div className="online-dot" style={{ marginLeft: "auto" }} />
          </div>

          {chatProduct && (
            <div className="product-context">
              {chatProduct.image_url && (
                <img
                  src={`${API_URL}${chatProduct.image_url}`}
                  alt={chatProduct.brand}
                />
              )}

              <div className="product-context-info">
                <div className="product-context-label">Regarding this dress</div>
                <div className="product-context-title">
                  {chatProduct.brand} Dress
                </div>
                <div className="product-context-meta">
                  Size {chatProduct.size} · €{chatProduct.price}
                </div>

                {isUnavailable && (
                  <div
                    style={{
                      color: "#b00020",
                      fontSize: 12,
                      marginTop: 4,
                    }}
                  >
                    This listing is no longer available
                  </div>
                )}
              </div>

              {isBuyer && !isUnavailable && (
                <>
                  <input
                    className="chat-input"
                    style={{ maxWidth: "110px" }}
                    type="number"
                    placeholder="€ offer"
                    value={offerAmount}
                    onChange={(e) => setOfferAmount(e.target.value)}
                  />

                  <button className="make-offer-btn" onClick={makeOffer}>
                    Make Offer
                  </button>
                </>
              )}
            </div>
          )}

          <div className="messages-area" ref={messagesAreaRef}>
            {messages.length === 0 && offers.length === 0 && (
              <div
                style={{
                  textAlign: "center",
                  color: "#ccc",
                  fontSize: 13,
                  marginTop: 40,
                }}
              >
                No messages yet — say hello!
              </div>
            )}

            {offers.map((offer) => {
              const mine = Number(offer.buyer_id) === Number(CURRENT_USER_ID);
              const seller =
                Number(offer.seller_id) === Number(CURRENT_USER_ID);

              return (
                <div
                  key={`offer-${offer.id}`}
                  className={`offer-box${mine ? " mine" : ""}`}
                >
                  <div className="offer-title">
                    {mine ? "Your offer" : "Offer received"}
                  </div>

                  <div className="offer-amount">€{offer.amount}</div>

                  <div className="offer-status">Status: {offer.status}</div>

                  {mine && offer.status === "accepted" && !isUnavailable && (
                    <button
                      className="offer-buy-btn"
                      style={{ marginTop: "10px" }}
                      onClick={() =>
                        navigate("/checkout", {
                          state: {
                            ...chatProduct,
                            price: offer.amount,
                            accepted_offer_id: offer.id,
                          },
                        })
                      }
                    >
                      Buy for €{offer.amount}
                    </button>
                  )}

                  {seller && offer.status === "pending" && !isUnavailable && (
                    <div className="offer-actions">
                      <button
                        className="accept-btn"
                        onClick={() => updateOfferStatus(offer.id, "accept")}
                      >
                        Accept
                      </button>

                      <button
                        className="decline-btn"
                        onClick={() => updateOfferStatus(offer.id, "decline")}
                      >
                        Decline
                      </button>
                    </div>
                  )}
                </div>
              );
            })}

            {messages.map((msg) => {
              const isMine =
                Number(msg.sender_id) === Number(CURRENT_USER_ID);

              return (
                <div
                  key={msg.id}
                  className={`message-row${isMine ? " mine" : ""}`}
                >
                  {!isMine && (
                    <div
                      className="avatar"
                      style={{
                        width: 28,
                        height: 28,
                        fontSize: 11,
                        marginBottom: 18,
                      }}
                    >
                      {getInitial(activeConversation.other_user_name)}
                    </div>
                  )}

                  <div>
                    <div className={`bubble${isMine ? " mine" : " theirs"}`}>
                      {msg.message}
                    </div>

                    <div
                      className="bubble-time"
                      style={{ textAlign: isMine ? "right" : "left" }}
                    >
                      {formatTime(msg.created_at)}
                    </div>
                  </div>
                </div>
              );
            })}

            <div ref={messagesEndRef} />
          </div>

          <div className="chat-input-area">
            <input
              className="chat-input"
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                isUnavailable
                  ? "This listing is no longer available"
                  : "Write a message..."
              }
              disabled={isUnavailable}
            />

            <button
              className="send-btn"
              onClick={sendMessage}
              disabled={!newMessage.trim() || isUnavailable}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#fff"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
        </div>
      ) : (
        <div className="no-chat">
          <div className="no-chat-icon">💬</div>
          <div className="no-chat-text">Select a conversation</div>
        </div>
      )}
    </div>
  );
}

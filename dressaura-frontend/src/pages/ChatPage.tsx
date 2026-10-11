
import { useEffect, useState, useRef } from "react";
import type { KeyboardEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import "./ChatPage.css";
import { API_URL, WS_URL, apiFetch } from "../api/client";

type ChatProduct = {
  id: number;
  user_id?: number;
  brand: string;
  price: number;
  size: string;
  image_url?: string;
  is_sold?: boolean;
};

type ChatConversation = {
  conversation_id: number;
  other_user_id: number;
  other_user_name: string;
  last_message: string | null;
  last_message_time?: string | null;
  product?: ChatProduct | null;
};

type ChatMessage = {
  id: number;
  sender_id: number;
  message: string;
  created_at: string | null;
};

type ChatOffer = {
  id: number;
  buyer_id: number;
  seller_id: number;
  amount: number;
  status: string;
};

type ChatUser = { id: number; name: string };

export default function ChatPage() {
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeConversation, setActiveConversation] =
    useState<ChatConversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [newMessage, setNewMessage] = useState("");
  const [chatProduct, setChatProduct] = useState<ChatProduct | null>(null);
  const [notice, setNotice] = useState("");
  const [socketConnected, setSocketConnected] = useState(false);

  const showNotice = (message: string) => {
    setNotice(message);

    setTimeout(() => {
      setNotice("");
    }, 3000);
  };

  const [offers, setOffers] = useState<ChatOffer[]>([]);
  const [offerAmount, setOfferAmount] = useState("");

  const socketRef = useRef<WebSocket | null>(null);
  const activeConversationRef = useRef<ChatConversation | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const messagesAreaRef = useRef<HTMLDivElement | null>(null);

  const { user, token } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const CURRENT_USER_ID = user?.id;

  useEffect(() => {
    activeConversationRef.current = activeConversation;
  }, [activeConversation]);

  const sortConversations = (items: ChatConversation[]) => {
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

    apiFetch(`${API_URL}/chat/user-conversations/${CURRENT_USER_ID}`)
      .then(async (response) => {
        if (!response.ok) throw new Error(`Could not load conversations (HTTP ${response.status})`);
        const data = await response.json();
        if (!Array.isArray(data)) throw new Error("Invalid conversations response");
        setConversations(sortConversations(data));
      })
      .catch((error) => {
        console.error("Could not load conversations:", error);
        showNotice("Could not load your conversations.");
      });
  }, [CURRENT_USER_ID]);

  useEffect(() => {
    const conversationId = location.state?.conversationId;

    if (!conversationId) return;

    const currentConversation = activeConversationRef.current;
    if (
      currentConversation &&
      Number(currentConversation.conversation_id) === Number(conversationId)
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
    if (!CURRENT_USER_ID || !token) return;

    let shouldReconnect = true;
    let retryCount = 0;
    let currentSocket: WebSocket | null = null;

    const connect = () => {
      if (!shouldReconnect) return;

      const ws = new WebSocket(`${WS_URL}/chat/ws/${CURRENT_USER_ID}`);
      currentSocket = ws;
      socketRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: "auth", token }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "ready") {
            retryCount = 0;
            setSocketConnected(true);
            const activeConversationId =
              activeConversationRef.current?.conversation_id;
            if (activeConversationId) {
              apiFetch(
                `${API_URL}/chat/conversation/${activeConversationId}/messages`
              )
                .then(async (response) => {
                  if (!response.ok) throw new Error(`HTTP ${response.status}`);
                  const missedMessages: ChatMessage[] = await response.json();
                  setMessages((previous) => {
                    const messagesById = new Map(
                      [...previous, ...missedMessages].map((message) => [
                        message.id,
                        message,
                      ])
                    );
                    return [...messagesById.values()].sort(
                      (left, right) =>
                        new Date(left.created_at || 0).getTime() -
                        new Date(right.created_at || 0).getTime()
                    );
                  });
                })
                .catch((error) => {
                  console.error("Unable to sync messages after reconnect:", error);
                  showNotice("Could not sync missed messages.");
                });
            }
            return;
          }
          if (data.type === "error") {
            showNotice(data.detail || "Message could not be sent.");
            return;
          }
          if (data.type !== "message") return;

          const receivedAt = data.created_at || new Date().toISOString();
          const otherUserId =
            Number(data.sender_id) === Number(CURRENT_USER_ID)
              ? Number(data.receiver_id)
              : Number(data.sender_id);

          setConversations((previous) => {
            const existing = previous.find(
              (conversation) =>
                Number(conversation.conversation_id) === Number(data.conversation_id)
            );
            const updatedConversation = {
              ...(existing || {}),
              conversation_id: data.conversation_id,
              other_user_id: otherUserId,
              other_user_name: existing?.other_user_name || "Seller",
              last_message: data.message,
              last_message_time: receivedAt,
            };
            return sortConversations([
              updatedConversation,
              ...previous.filter(
                (conversation) =>
                  Number(conversation.conversation_id) !== Number(data.conversation_id)
              ),
            ]);
          });

          if (
            Number(activeConversationRef.current?.conversation_id) ===
            Number(data.conversation_id)
          ) {
            setMessages((previous) =>
              previous.some((message) => Number(message.id) === Number(data.message_id))
                ? previous
                : [
                    ...previous,
                    {
                      id: data.message_id,
                      sender_id: data.sender_id,
                      message: data.message,
                      created_at: receivedAt,
                    },
                  ]
            );
            setActiveConversation((previous) =>
              previous &&
              Number(previous.conversation_id) === Number(data.conversation_id)
                ? { ...previous, last_message: data.message, last_message_time: receivedAt }
                : previous
            );
          }
        } catch (error) {
          console.error("Invalid chat message received:", error);
          showNotice("A chat message could not be read.");
        }
      };

      ws.onerror = () => {
        showNotice("Chat connection error. Reconnecting…");
      };

      ws.onclose = (event) => {
        setSocketConnected(false);
        if (socketRef.current === ws) socketRef.current = null;
        if (!shouldReconnect || event.code === 1008 || event.code === 1002) {
          if (event.code === 1008) showNotice("Your chat session expired. Please log in again.");
          return;
        }
        const delay = Math.min(1000 * 2 ** retryCount, 30000);
        retryCount += 1;
        reconnectTimerRef.current = setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      shouldReconnect = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (currentSocket && currentSocket.readyState < WebSocket.CLOSING) currentSocket.close();
      socketRef.current = null;
      setSocketConnected(false);
    };
  }, [CURRENT_USER_ID, token]);

  useEffect(() => {
    if (!CURRENT_USER_ID || !activeConversation?.other_user_id) return;

    const nameIsMissing =
      !activeConversation.other_user_name ||
      activeConversation.other_user_name === "Seller" ||
      activeConversation.other_user_name.startsWith("User ");

    if (!nameIsMissing) return;

    apiFetch(`${API_URL}/chat/users/${CURRENT_USER_ID}`)
      .then((res) => res.json())
      .then((users) => {
        const otherUser = (users as ChatUser[]).find(
          (u) => Number(u.id) === Number(activeConversation.other_user_id)
        );

        if (otherUser) {
          setActiveConversation((prev) =>
            prev &&
            Number(prev.conversation_id) ===
              Number(activeConversation.conversation_id)
              ? { ...prev, other_user_name: otherUser.name }
              : prev
          );

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
    const conversationId = activeConversation?.conversation_id;
    if (!conversationId) return;

    apiFetch(
      `${API_URL}/chat/conversation/${conversationId}/messages`
    )
      .then(async (response) => {
        if (!response.ok) throw new Error(`Could not load messages (HTTP ${response.status})`);
        const data = await response.json();
        if (!Array.isArray(data)) throw new Error("Invalid messages response");
        setMessages(data);
      })
      .catch((error) => {
        console.error("Could not load messages:", error);
        showNotice("Could not load messages for this conversation.");
      });

    apiFetch(
      `${API_URL}/chat/conversation/${conversationId}/offers`
    )
      .then(async (response) => {
        if (!response.ok) throw new Error(`Could not load offers (HTTP ${response.status})`);
        setOffers(await response.json());
      })
      .catch((error) => {
        console.error("Could not load offers:", error);
        showNotice("Could not load offers for this conversation.");
      });
  }, [activeConversation?.conversation_id]);

  useEffect(() => {
    const conversationId = activeConversation?.conversation_id;
    if (!conversationId) return;

    const interval = setInterval(() => {
      apiFetch(
        `${API_URL}/chat/conversation/${conversationId}/offers`
      )
        .then(async (response) => {
          if (!response.ok) throw new Error(`Could not refresh offers (HTTP ${response.status})`);
          const data: unknown = await response.json();
          if (!Array.isArray(data)) throw new Error("Invalid offers response");
          setOffers(data);
        })
        .catch((error) => console.error("Could not refresh offers:", error));
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

    if (!newMessage.trim() || !activeConversation) return;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      showNotice("Chat is reconnecting. Please try again in a moment.");
      return;
    }

    try {
      socket.send(
        JSON.stringify({
          conversation_id: activeConversation.conversation_id,
          receiver_id: activeConversation.other_user_id,
          message: newMessage,
        })
      );
      setNewMessage("");
    } catch (error) {
      console.error("Unable to send chat message:", error);
      showNotice("Message was not sent. Please try again.");
    }
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

      const res = await apiFetch(`${API_URL}/chat/offers?${params.toString()}`, {
        method: "POST",
      });

      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || "Could not send offer.");

      setOffers((prev) => [...prev, data]);
      setOfferAmount("");
    } catch (error) {
      console.error(error);
      showNotice("Could not send offer.");
    }
  };

  const updateOfferStatus = async (
    offerId: number,
    action: "accept" | "decline"
  ) => {
    try {
      const res = await apiFetch(
        `${API_URL}/chat/offers/${offerId}/${action}`,
        {
          method: "PUT",
        }
      );

      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || "Could not update offer.");

      setOffers((prev) =>
        prev.map((offer) =>
          offer.id === offerId ? { ...offer, status: data.status } : offer
        )
      );
    } catch (error) {
      console.error(error);
      showNotice(error instanceof Error ? error.message : "Could not update offer.");
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") sendMessage();
  };

  const getInitial = (name?: string) => (name || "?").charAt(0).toUpperCase();

  const formatTime = (ts?: string | null) => {
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
              <div style={{ fontSize: 11, color: socketConnected ? "#4caf7d" : "#b0783c", marginTop: 1 }}>
                {socketConnected ? "Connected" : "Reconnecting…"}
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

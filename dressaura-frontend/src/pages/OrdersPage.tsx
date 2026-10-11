
import "./OrdersPage.css";
import { Link, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";

const API_URL = "https://dressaura-backend.vercel.app";

function OrdersPage() {
  const { type, status } = useParams();
  const { user } = useAuth();

  const [orders, setOrders] = useState<any[]>([]);
  const [notice, setNotice] = useState("");
  const [updatingDelivery, setUpdatingDelivery] = useState<number | null>(null);

  const deliveryStatuses = [
    "Awaiting Drop-off",
    "Dropped Off",
    "In Transit",
    "Out for Delivery",
    "Delivered",
  ];

  const showNotice = (message: string) => {
    setNotice(message);

    setTimeout(() => {
      setNotice("");
    }, 3000);
  };

  const titleType = type === "sold" ? "Sold" : "Ordered";
  const titleStatus = status === "completed" ? "Completed" : "In Progress";

  useEffect(() => {
    if (!user?.id || !type || !status) return;

    fetch(`${API_URL}/orders/${user.id}/${type}/${status}`)
      .then((res) => res.json())
      .then((data) => setOrders(data))
      .catch(console.error);
  }, [user, type, status]);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [type, status]);

  const markAsCompleted = async (orderId: number) => {
    try {
      const res = await fetch(
        `${API_URL}/orders/${orderId}/complete`,
        {
          method: "PUT",
        }
      );

      const data = await res.json();

      if (data.error) {
        showNotice(data.error);
        return;
      }

      setOrders((prev) =>
        prev.filter((order) => order.id !== orderId)
      );

      showNotice("Order marked as completed.");
    } catch (error) {
      console.error(error);
      showNotice("Failed to update order.");
    }
  };

  const updateDeliveryStatus = async (
    orderId: number,
    newStatus: string
  ) => {
    if (!user?.id) return;

    try {
      setUpdatingDelivery(orderId);

      const params = new URLSearchParams({
        status: newStatus,
        user_id: String(user.id),
      });

      const res = await fetch(
        `${API_URL}/orders/${orderId}/delivery-status?${params.toString()}`,
        {
          method: "PUT",
        }
      );

      const data = await res.json();

      if (data.error) {
        showNotice(data.error);
        return;
      }

      setOrders((prev) =>
        prev.map((order) =>
          order.id === orderId
            ? {
                ...order,
                delivery_status: newStatus,
              }
            : order
        )
      );

      showNotice(`Delivery updated to "${newStatus}".`);
    } catch (error) {
      console.error(error);
      showNotice("Failed to update delivery status.");
    } finally {
      setUpdatingDelivery(null);
    }
  };

  const getDeliveryProgress = (deliveryStatus: string) => {
    const index = deliveryStatuses.indexOf(deliveryStatus);

    if (index === -1) return 0;

    return index;
  };

  return (
    <div className="orders-page">
      {notice && <div className="product-notice">{notice}</div>}

      <div className="orders-wrapper">
        <div className="orders-card">
          <Link to="/profile" className="back-link">
            ← Back to Profile
          </Link>

          <h1 className="orders-title">{titleType}</h1>

          <p className="orders-subtitle">
            {titleStatus} orders
          </p>

          {orders.length === 0 ? (
            <div className="empty-orders">
              No {titleStatus.toLowerCase()}{" "}
              {titleType.toLowerCase()} orders yet.
            </div>
          ) : (
            <div className="orders-list">
              {orders.map((order) => {
                const deliveryStatus =
                  order.delivery_status || "Awaiting Drop-off";

                const progress = getDeliveryProgress(deliveryStatus);

                const displayedPrice =
                  order.order_price !== null &&
                  order.order_price !== undefined
                    ? order.order_price
                    : order.dress?.price;

                return (
                  <div className="order-item" key={order.id}>
                    {order.dress?.image_url && (
                      <img
                        src={`${API_URL}${order.dress.image_url}`}
                        alt={order.dress.brand}
                      />
                    )}

                    <div className="order-information">
                      <h3>{order.dress?.brand} Dress</h3>

                      <p>Size: {order.dress?.size}</p>

                      <p>€{displayedPrice}</p>

                      <span className="order-status">
                        {order.status}
                      </span>

                      {/* DELIVERY INFORMATION */}
                      <div
                        style={{
                          marginTop: "18px",
                          paddingTop: "15px",
                          borderTop: "1px solid #e5e5e5",
                        }}
                      >
                        <h4
                          style={{
                            marginBottom: "10px",
                            fontSize: "15px",
                          }}
                        >
                          Delivery Information
                        </h4>

                        <p>
                          <strong>Company:</strong>{" "}
                          {order.delivery_company
                            ? order.delivery_company.toUpperCase()
                            : "Not selected"}
                        </p>

                        <p>
                          <strong>Tracking Number:</strong>{" "}
                          {order.tracking_number || "Not available"}
                        </p>

                        <p>
                          <strong>Drop-off Location:</strong>{" "}
                          {order.dropoff_location || "Not available"}
                        </p>

                        <p>
                          <strong>Status:</strong> {deliveryStatus}
                        </p>
                      </div>

                      {/* DELIVERY PROGRESS */}
                      <div
                        style={{
                          marginTop: "18px",
                        }}
                      >
                        <h4
                          style={{
                            marginBottom: "12px",
                            fontSize: "15px",
                          }}
                        >
                          Delivery Progress
                        </h4>

                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: "8px",
                          }}
                        >
                          {deliveryStatuses.map((deliveryStep, index) => {
                            const completed = index <= progress;

                            return (
                              <div
                                key={deliveryStep}
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "10px",
                                  fontSize: "13px",
                                  fontWeight:
                                    deliveryStep === deliveryStatus
                                      ? 600
                                      : 400,
                                }}
                              >
                                <span
                                  style={{
                                    width: "10px",
                                    height: "10px",
                                    borderRadius: "50%",
                                    background: completed ? "#111" : "#ddd",
                                    display: "inline-block",
                                    flexShrink: 0,
                                  }}
                                />

                                <span>{deliveryStep}</span>
                              </div>
                            );
                          })}
                        </div>
                      </div>

                      {/* SELLER DELIVERY CONTROLS */}
                      {type === "sold" &&
                        status === "in-progress" &&
                        deliveryStatus !== "Delivered" && (
                          <div
                            style={{
                              marginTop: "18px",
                              paddingTop: "15px",
                              borderTop: "1px solid #e5e5e5",
                            }}
                          >
                            <h4
                              style={{
                                marginBottom: "10px",
                                fontSize: "15px",
                              }}
                            >
                              Update Delivery
                            </h4>

                            {progress < deliveryStatuses.length - 1 && (
                              <button
                                onClick={() =>
                                  updateDeliveryStatus(
                                    order.id,
                                    deliveryStatuses[progress + 1]
                                  )
                                }
                                disabled={updatingDelivery === order.id}
                                style={{
                                  display: "block",
                                  marginTop: "10px",
                                  padding: "8px 14px",
                                  borderRadius: "8px",
                                  border: "none",
                                  background: "#111",
                                  color: "#fff",
                                  cursor: "pointer",
                                  fontSize: "13px",
                                }}
                              >
                                {updatingDelivery === order.id
                                  ? "Updating..."
                                  : `Mark as ${deliveryStatuses[progress + 1]}`}
                              </button>
                            )}
                          </div>
                        )}

                      {/* COMPLETE ORDER */}
                      {type === "sold" && status === "in-progress" && (
                        <button
                          onClick={() => markAsCompleted(order.id)}
                          style={{
                            display: "block",
                            marginTop: "10px",
                            padding: "8px 14px",
                            borderRadius: "8px",
                            border: "none",
                            background: "#111",
                            color: "#fff",
                            cursor: "pointer",
                            fontSize: "13px",
                          }}
                        >
                          Mark as Completed
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default OrdersPage;

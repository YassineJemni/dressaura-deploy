import "./Checkout.css";
import { useLocation, Link, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";

function Checkout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();
  const product = location.state as any;

  const [paymentMethod, setPaymentMethod] = useState<
    "card" | "apple" | "paypal" | "cash"
  >("card");

  const [deliveryCompany, setDeliveryCompany] = useState<
    "DPD" | "GLS" | "Packeta"
  >("DPD");

  const [cardNumber, setCardNumber] = useState("");
  const [expiry, setExpiry] = useState("");
  const [cvc, setCvc] = useState("");

  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");

  const showNotice = (message: string) => {
    setNotice(message);

    setTimeout(() => {
      setNotice("");
    }, 3000);
  };

  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/login");
    }
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  const handleConfirmPurchase = async () => {
    if (!user?.id || !product?.id) {
      showNotice("Missing user or product information");
      return;
    }

    if (paymentMethod === "card" && (!cardNumber || !expiry || !cvc)) {
      showNotice("Please enter full card details");
      return;
    }

    try {
      setLoading(true);

      const params = new URLSearchParams({
        user_id: String(user.id),
        dress_id: String(product.id),
        payment_method: paymentMethod,
        delivery_company: deliveryCompany,
        order_price: String(product.price),
      });

      const res = await fetch(
        `http://localhost:8000/orders/?${params.toString()}`,
        {
          method: "POST",
        }
      );

      if (!res.ok) {
        throw new Error("Failed to place order");
      }

      const data = await res.json();

      if (data.error) {
        showNotice(data.error);
        return;
      }

      if (paymentMethod === "card") {
        showNotice("Card payment processed successfully");
      } else if (paymentMethod === "apple") {
        showNotice("Apple Pay processed successfully");
      } else if (paymentMethod === "paypal") {
        showNotice("PayPal payment processed successfully");
      } else {
        showNotice("Cash order placed successfully");
      }

      navigate("/orders/ordered/in-progress");
    } catch (err) {
      console.error("❌ Order failed:", err);
      showNotice("Could not place order");
    } finally {
      setLoading(false);
    }
  };

  if (!isAuthenticated) {
    return null;
  }

  if (!product) {
    return (
      <div className="checkout-page">
        <div className="checkout-empty">
          <h1>Checkout</h1>
          <p>You must select a dress before checkout.</p>

          <Link to="/browse" className="checkout-back-btn">
            Go to Browse
          </Link>
        </div>
      </div>
    );
  }

  const productImage =
    product.image_url || product.image || product.images?.[0]?.image_url;

  const formattedPrice = Number(product.price || 0).toFixed(2);

  return (
    <div className="checkout-page">
      {notice && <div className="product-notice">{notice}</div>}

      <div className="checkout-container">
        {/* HEADER */}
        <div className="checkout-header">
          <Link to="/browse" className="checkout-back">
            ← Back to Browse
          </Link>

          <h1>Checkout</h1>

          <p>Complete your purchase securely.</p>
        </div>

        <div className="checkout-layout">
          {/* LEFT SIDE */}
          <main className="checkout-main">
            {/* DELIVERY */}
            <section className="checkout-section">
              <div className="section-heading">
                <div className="section-number">1</div>

                <div>
                  <h2>Delivery</h2>
                  <p>Choose your preferred delivery company.</p>
                </div>
              </div>

              <div className="option-grid delivery-grid">
                <button
                  type="button"
                  className={`option-card ${
                    deliveryCompany === "DPD" ? "selected" : ""
                  }`}
                  onClick={() => setDeliveryCompany("DPD")}
                >
                  <div className="option-radio">
                    <span />
                  </div>

                  <div className="option-content">
                    <strong>DPD</strong>
                    <span>Parcel delivery</span>
                  </div>

                  {deliveryCompany === "DPD" && (
                    <div className="selected-check">✓</div>
                  )}
                </button>

                <button
                  type="button"
                  className={`option-card ${
                    deliveryCompany === "GLS" ? "selected" : ""
                  }`}
                  onClick={() => setDeliveryCompany("GLS")}
                >
                  <div className="option-radio">
                    <span />
                  </div>

                  <div className="option-content">
                    <strong>GLS</strong>
                    <span>Parcel delivery</span>
                  </div>

                  {deliveryCompany === "GLS" && (
                    <div className="selected-check">✓</div>
                  )}
                </button>

                <button
                  type="button"
                  className={`option-card ${
                    deliveryCompany === "Packeta" ? "selected" : ""
                  }`}
                  onClick={() => setDeliveryCompany("Packeta")}
                >
                  <div className="option-radio">
                    <span />
                  </div>

                  <div className="option-content">
                    <strong>Packeta</strong>
                    <span>Pick-up point delivery</span>
                  </div>

                  {deliveryCompany === "Packeta" && (
                    <div className="selected-check">✓</div>
                  )}
                </button>
              </div>

              <div className="delivery-note">
                <span className="note-icon">i</span>

                <p>
                  After the order is
                  created, a tracking number and seller drop-off location will
                  be generated.
                </p>
              </div>
            </section>

            {/* PAYMENT */}
            <section className="checkout-section">
              <div className="section-heading">
                <div className="section-number">2</div>

                <div>
                  <h2>Payment</h2>
                  <p>Select your preferred payment method.</p>
                </div>
              </div>

              <div className="payment-options">
                <button
                  type="button"
                  className={`payment-option ${
                    paymentMethod === "card" ? "selected" : ""
                  }`}
                  onClick={() => setPaymentMethod("card")}
                >
                  <div className="payment-icon card-icon">▣</div>

                  <div className="payment-option-content">
                    <strong>Credit / Debit Card</strong>
                    <span>Pay securely with your card</span>
                  </div>

                  <div className="option-radio">
                    <span />
                  </div>
                </button>

                <button
                  type="button"
                  className={`payment-option ${
                    paymentMethod === "apple" ? "selected" : ""
                  }`}
                  onClick={() => setPaymentMethod("apple")}
                >
                  <div className="payment-icon apple-icon">●</div>

                  <div className="payment-option-content">
                    <strong>Apple Pay</strong>
                    <span>Fast and convenient payment</span>
                  </div>

                  <div className="option-radio">
                    <span />
                  </div>
                </button>

                <button
                  type="button"
                  className={`payment-option ${
                    paymentMethod === "paypal" ? "selected" : ""
                  }`}
                  onClick={() => setPaymentMethod("paypal")}
                >
                  <div className="payment-icon paypal-icon">P</div>

                  <div className="payment-option-content">
                    <strong>PayPal</strong>
                    <span>Pay using your PayPal account</span>
                  </div>

                  <div className="option-radio">
                    <span />
                  </div>
                </button>

                <button
                  type="button"
                  className={`payment-option ${
                    paymentMethod === "cash" ? "selected" : ""
                  }`}
                  onClick={() => setPaymentMethod("cash")}
                >
                  <div className="payment-icon cash-icon">€</div>

                  <div className="payment-option-content">
                    <strong>Cash on Delivery</strong>
                    <span>Pay when your order arrives</span>
                  </div>

                  <div className="option-radio">
                    <span />
                  </div>
                </button>
              </div>

              {/* CARD */}
              {paymentMethod === "card" && (
                <div className="payment-details-box">
                  <div className="payment-details-header">
                    <div>
                      <h3>Card details</h3>

                    </div>

                    <span className="secure-badge">Secure</span>
                  </div>

                  <div className="form-field full-width">
                    <label>Card number</label>

                    <input
                      type="text"
                      placeholder="1234 5678 9012 3456"
                      value={cardNumber}
                      onChange={(e) => setCardNumber(e.target.value)}
                      maxLength={19}
                    />
                  </div>

                  <div className="form-row">
                    <div className="form-field">
                      <label>Expiry date</label>

                      <input
                        type="text"
                        placeholder="MM / YY"
                        value={expiry}
                        onChange={(e) => setExpiry(e.target.value)}
                        maxLength={7}
                      />
                    </div>

                    <div className="form-field">
                      <label>CVC</label>

                      <input
                        type="password"
                        placeholder="123"
                        value={cvc}
                        onChange={(e) => setCvc(e.target.value)}
                        maxLength={4}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* APPLE PAY */}
              {paymentMethod === "apple" && (
                <div className="payment-details-box simple-payment-box">
                  <div className="simple-payment-icon">●</div>

                  <div>
                    <h3>Apple Pay</h3>
                    <p>
                      Your order will be created after confirmation.
                    </p>
                  </div>
                </div>
              )}

              {/* PAYPAL */}
              {paymentMethod === "paypal" && (
                <div className="payment-details-box simple-payment-box">
                  <div className="simple-payment-icon paypal-large">P</div>

                  <div>
                    <h3>PayPal</h3>
                    <p>
                       Your order will be created after confirmation.
                    </p>
                  </div>
                </div>
              )}

              {/* CASH */}
              {paymentMethod === "cash" && (
                <div className="payment-details-box simple-payment-box">
                  <div className="simple-payment-icon cash-large">€</div>

                  <div>
                    <h3>Cash on Delivery</h3>
                    <p>
                      You will pay when the dress is delivered to you.
                    </p>
                  </div>
                </div>
              )}
            </section>
          </main>

          {/* RIGHT SIDE - ORDER SUMMARY */}
          <aside className="checkout-sidebar">
            <div className="summary-card">
              <h2>Order summary</h2>

              <div className="summary-product">
                <div className="summary-image">
                  {productImage ? (
                    <img
                      src={
                        productImage.startsWith("http")
                          ? productImage
                          : `http://127.0.0.1:8000${productImage}`
                      }
                      alt={product.brand || "Dress"}
                    />
                  ) : (
                    <div className="summary-image-placeholder">
                      No image
                    </div>
                  )}
                </div>

                <div className="summary-product-info">
                  <h3>{product.brand || "Dress"} Dress</h3>

                  <p>Size: {product.size || "—"}</p>


                </div>
              </div>

              <div className="summary-divider" />

              <div className="summary-row">
                <span>Item</span>
                <strong>€{formattedPrice}</strong>
              </div>

              <div className="summary-row">
                <span>Delivery</span>
                <span className="free-label">Included</span>
              </div>

              <div className="summary-divider" />

              <div className="summary-total">
                <span>Total</span>
                <strong>€{formattedPrice}</strong>
              </div>

              <button
                className="confirm-btn"
                onClick={handleConfirmPurchase}
                disabled={loading}
              >
                {loading
                  ? "Placing Order..."
                  : paymentMethod === "paypal"
                  ? "Continue to PayPal"
                  : paymentMethod === "apple"
                  ? "Pay with Apple Pay"
                  : paymentMethod === "cash"
                  ? "Place Order"
                  : "Confirm Purchase"}
              </button>

              <p className="checkout-disclaimer">
                By confirming your purchase, you agree to complete the order
                through Dressaura.
              </p>
            </div>

            <Link to="/browse" className="cancel-link">
              Cancel and return to browse
            </Link>
          </aside>
        </div>
      </div>
    </div>
  );
}

export default Checkout;
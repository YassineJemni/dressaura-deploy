
import { useParams, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import "./ProductDetails.css";

const API_URL = "https://dressaura-backend.vercel.app";

function ProductDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();

  const [product, setProduct] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState("");

  const [currentImageIndex, setCurrentImageIndex] = useState(0);
  const [touchStartX, setTouchStartX] = useState<number | null>(null);
  const [touchEndX, setTouchEndX] = useState<number | null>(null);

  const showNotice = (message: string) => {
    setNotice(message);

    setTimeout(() => {
      setNotice("");
    }, 3000);
  };

  useEffect(() => {
    fetch(`${API_URL}/dresses/${id}`)
      .then((res) => {
        if (!res.ok) {
          throw new Error("Dress not found");
        }

        return res.json();
      })
      .then((data) => {
        console.log("PRODUCT DATA:", data);

        setProduct({
          ...data,
          condition: data.condition_status,
          price: Number(data.price),
        });

        setCurrentImageIndex(0);
        setLoading(false);
      })
      .catch((err) => {
        console.error("❌ Failed to load product:", err);
        setLoading(false);
      });
  }, [id]);

  const productImages =
    product?.images && product.images.length > 0
      ? product.images
      : product?.image_url
      ? [
          {
            id: "legacy-image",
            image_url: product.image_url,
            display_order: 0,
          },
        ]
      : [];

  const currentImage =
    productImages[currentImageIndex]?.image_url || null;

  const getImageUrl = (imageUrl: string) => {
    if (!imageUrl) return "";
    if (imageUrl.startsWith("http")) return imageUrl;
    return `${API_URL}${imageUrl.startsWith("/") ? "" : "/"}${imageUrl}`;
  };

  const nextImage = () => {
    if (productImages.length <= 1) return;

    setCurrentImageIndex((prev) =>
      prev === productImages.length - 1 ? 0 : prev + 1
    );
  };

  const previousImage = () => {
    if (productImages.length <= 1) return;

    setCurrentImageIndex((prev) =>
      prev === 0 ? productImages.length - 1 : prev - 1
    );
  };

  const handleTouchStart = (
    e: React.TouchEvent<HTMLDivElement>
  ) => {
    setTouchStartX(e.targetTouches[0].clientX);
    setTouchEndX(null);
  };

  const handleTouchMove = (
    e: React.TouchEvent<HTMLDivElement>
  ) => {
    setTouchEndX(e.targetTouches[0].clientX);
  };

  const handleTouchEnd = () => {
    if (touchStartX === null || touchEndX === null) {
      return;
    }

    const distance = touchStartX - touchEndX;
    const minimumSwipeDistance = 50;

    if (Math.abs(distance) < minimumSwipeDistance) {
      return;
    }

    if (distance > 0) {
      // Swipe left → next photo
      nextImage();
    } else {
      // Swipe right → previous photo
      previousImage();
    }

    setTouchStartX(null);
    setTouchEndX(null);
  };

  const handleBuyNow = () => {
    if (!isAuthenticated) {
      showNotice("Please log in or register to buy a dress.");
      navigate("/login");
      return;
    }

    const sellerId =
      product.user_id ||
      product.seller_id ||
      product.owner_id ||
      product.created_by;

    if (Number(sellerId) === Number(user?.id)) {
      showNotice("You can’t buy your own listing.");
      return;
    }

    navigate("/checkout", {
      state: product,
    });
  };

  const handleMessageSeller = async () => {
    if (!isAuthenticated) {
      showNotice(
        "Please log in or register to message the seller."
      );

      navigate("/login");
      return;
    }

    const sellerId =
      product.user_id ||
      product.seller_id ||
      product.owner_id ||
      product.created_by;

    console.log("CURRENT USER:", user?.id);
    console.log("SELLER ID:", sellerId);
    console.log("PRODUCT:", product);

    if (!sellerId) {
      showNotice(
        "Seller information is missing for this dress."
      );
      return;
    }

    if (Number(sellerId) === Number(user?.id)) {
      showNotice(
        "You can’t message yourself about your own listing."
      );
      return;
    }

    try {
      const params = new URLSearchParams({
        user1_id: String(user?.id),
        user2_id: String(sellerId),
        product_id: String(product.id),
      });

      const res = await fetch(
        `${API_URL}/chat/conversation?${params.toString()}`,
        {
          method: "POST",
        }
      );

      if (!res.ok) {
        throw new Error("Failed to start chat");
      }

      const convo = await res.json();

      console.log("CHAT RESPONSE:", convo);

      const conversationId =
        convo.id || convo.conversation_id;

      navigate("/chat", {
        state: {
          conversationId: Number(conversationId),
          sellerId: sellerId,

          sellerName:
            product.user_name ||
            product.seller_name ||
            product.owner_name ||
            product.username ||
            "Seller",

          prefillMessage: `Hi, I'm interested in your ${product.brand} dress for €${product.price}.`,

          product: {
            id: product.id,

            user_id:
              product.user_id ||
              product.seller_id ||
              product.owner_id ||
              product.created_by,

            brand: product.brand,
            price: product.price,
            size: product.size,

            image_url:
              product.image_url ||
              productImages[0]?.image_url,
          },
        },
      });
    } catch (err) {
      console.error(
        "❌ Failed to message seller:",
        err
      );

      showNotice(
        "Could not open chat with seller."
      );
    }
  };

  if (loading) {
    return (
      <p style={{ padding: "40px" }}>
        Loading...
      </p>
    );
  }

  if (!product) {
    return (
      <p style={{ padding: "40px" }}>
        Product not found.
      </p>
    );
  }

  return (
    <div className="product-details">
      {notice && (
        <div className="product-notice">
          {notice}
        </div>
      )}

      <div className="details-container">
        <div className="images">
          <div
            className="main-image-wrapper"
            onTouchStart={handleTouchStart}
            onTouchMove={handleTouchMove}
            onTouchEnd={handleTouchEnd}
          >
            {currentImage ? (
              <>
                <img
                  src={getImageUrl(currentImage)}
                  alt={`${product.brand} dress ${
                    currentImageIndex + 1
                  }`}
                  className="main-product-image"
                />

                {productImages.length > 1 && (
                  <>
                    {/* PREVIOUS */}
                    <button
                      type="button"
                      className="gallery-arrow gallery-arrow-left"
                      onClick={previousImage}
                      aria-label="Previous photo"
                    >
                      ‹
                    </button>

                    {/* NEXT */}
                    <button
                      type="button"
                      className="gallery-arrow gallery-arrow-right"
                      onClick={nextImage}
                      aria-label="Next photo"
                    >
                      ›
                    </button>
                  </>
                )}
              </>
            ) : (
              <div className="main-image">
                No Image
              </div>
            )}
          </div>

          {/* PHOTO COUNTER */}
          {productImages.length > 1 && (
            <div className="image-counter">
              {currentImageIndex + 1} / {productImages.length}
            </div>
          )}

          {/* DOTS */}
          {productImages.length > 1 && (
            <div className="image-dots">
              {productImages.map(
                (image: any, index: number) => (
                  <button
                    key={image.id ?? index}
                    type="button"
                    className={`image-dot ${
                      index === currentImageIndex
                        ? "active"
                        : ""
                    }`}
                    onClick={() =>
                      setCurrentImageIndex(index)
                    }
                    aria-label={`View photo ${index + 1}`}
                  />
                )
              )}
            </div>
          )}
        </div>

        <div className="info">
          <h1>
            {product.brand} Dress
          </h1>

          <p className="price">
            €{product.price}
          </p>

          <div className="meta">
            <p>
              <strong>Size:</strong> {product.size}
            </p>

            <p>
              <strong>Condition:</strong> {product.condition}
            </p>

            <p>
              <strong>Brand:</strong> {product.brand}
            </p>
          </div>

          <p className="description">
            {product.description}
          </p>

          {/* ACTIONS */}
          <div className="actions">
            <button
              className="btn secondary"
              onClick={() => navigate("/browse")}
            >
              ← Back to Browse
            </button>

            <button
              className="btn secondary"
              onClick={handleMessageSeller}
            >
              Message Seller
            </button>

            <button
              className="btn primary"
              onClick={handleBuyNow}
            >
              Buy Now
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ProductDetails;

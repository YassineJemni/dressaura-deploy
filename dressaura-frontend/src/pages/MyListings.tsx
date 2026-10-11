
import "./MyListings.css";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useEffect, useState } from "react";

const API_URL = "https://dressaura-backend.vercel.app";

export default function MyListings() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [listings, setListings] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedListingId, setSelectedListingId] = useState<number | null>(null);
  const [showSuccessModal, setShowSuccessModal] = useState(false);

  const getImageUrl = (imageUrl: any) => {
    if (!imageUrl) return "https://via.placeholder.com/120x140";
    if (imageUrl.startsWith("http")) return imageUrl;
    return `${API_URL}${imageUrl}`;
  };

  const handleDelete = async (listingId: any) => {
    try {
      const res = await fetch(`${API_URL}/dresses/${listingId}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        let message = "Failed to delete listing.";

        try {
          const error = await res.json();
          message = error.detail || message;
        } catch {
          message = await res.text();
        }

        throw new Error(message);
      }

      setListings((prev) =>
        prev.filter((item) => Number(item.id) !== Number(listingId))
      );

      setSelectedListingId(null);
      setShowSuccessModal(true);
    } catch (error: any) {
      console.error("Delete failed:", error);
      alert(error.message || "Failed to delete listing");
    }
  };

  useEffect(() => {
    const fetchListings = async () => {
      try {
        const res = await fetch(`${API_URL}/dresses`);

        if (!res.ok) {
          throw new Error("Failed to fetch listings");
        }

        const data = await res.json();

        const userListings = data.filter(
          (item: any) => Number(item.user_id) === Number(user?.id)
        );

        setListings(userListings);
      } catch (error) {
        console.error("Failed to fetch listings:", error);
      } finally {
        setLoading(false);
      }
    };

    if (user?.id) {
      fetchListings();
    } else {
      setLoading(false);
    }
  }, [user]);

  if (loading) {
    return (
      <div className="my-listings-page">
        <div className="my-listings-wrapper">
          <div className="my-listings-top">
            <h1>My Listings</h1>
            <p>Loading your listings...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="my-listings-page">
      <div className="my-listings-wrapper">
        <div className="my-listings-top">
          <h1>My Listings</h1>
          <p>Manage the items you are selling</p>
        </div>

        <button className="add-listing-btn" onClick={() => navigate("/sell")}>
          + Add New Listing
        </button>

        {listings.length === 0 ? (
          <div className="empty-state">
            <p>You have not listed anything yet.</p>
          </div>
        ) : (
          <div className="listings-grid">
            {listings.map((item: any) => (
              <div className="listing-card" key={item.id}>
                <img
                  src={getImageUrl(item.image_url)}
                  alt={item.brand}
                  className="listing-image"
                />

                <div className="listing-info">
                  <div className="listing-top-row">
                    <h3>{item.brand}</h3>
                    <span className="status-badge available">Available</span>
                  </div>

                  <p className="price">€{item.price}</p>
                  <p className="details">Size: {item.size}</p>
                  <p className="details">
                    Condition: {item.condition_status}
                  </p>

                  {item.description && (
                    <p className="details">{item.description}</p>
                  )}

                  <div className="listing-actions">
                    <button onClick={() => navigate(`/edit-listing/${item.id}`)}>
                      Edit
                    </button>

                    <button
                      className="delete-btn"
                      onClick={() => setSelectedListingId(Number(item.id))}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {selectedListingId !== null && (
          <div className="modal-overlay">
            <div className="listing-modal">
              <div className="modal-icon delete-icon">!</div>
              <h2>Delete listing?</h2>
              <p>
                Are you sure you want to delete this listing? It will be
                removed from your active listings.
              </p>

              <div className="modal-actions">
                <button
                  className="modal-cancel"
                  onClick={() => setSelectedListingId(null)}
                >
                  Cancel
                </button>

                <button
                  className="modal-delete"
                  onClick={() => handleDelete(selectedListingId)}
                >
                  Delete listing
                </button>
              </div>
            </div>
          </div>
        )}

        {showSuccessModal && (
          <div className="modal-overlay">
            <div className="listing-modal">
              <div className="modal-icon success-icon">✓</div>
              <h2>Listing deleted</h2>
              <p>
                Your listing has been successfully removed from your active
                listings.
              </p>

              <div className="modal-actions">
                <button
                  className="modal-done"
                  onClick={() => setShowSuccessModal(false)}
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

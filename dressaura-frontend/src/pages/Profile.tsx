import "./Profile.css";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { Link } from "react-router-dom";

interface Dress {
  id: number;
  user_id: number;
  brand: string;
  size: string;
  condition_status: string;
  price: number;
  description?: string;
  image_url?: string;
}

export default function Profile() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [showOrders, setShowOrders] = useState(false);

  const [stats, setStats] = useState({
    listings: 0,
    sold: 0,
    ordered: 0,
  });

  useEffect(() => {
    const fetchStats = async () => {
      if (!user) return;

      try {
        // Fetch listings
        const dressesRes = await fetch("https://dressaura-backend.vercel.app/dresses/");
        const dressesData: Dress[] = await dressesRes.json();

        const userListings = dressesData.filter(
          (item) => Number(item.user_id) === Number(user.id)
        );

        // Fetch sold + ordered stats
        const ordersRes = await fetch(`https://dressaura-backend.vercel.app/orders/stats/${user.id}`);
        const ordersData = await ordersRes.json();

        setStats({
          listings: userListings.length,
          sold: ordersData.sold || 0,
          ordered: ordersData.ordered || 0,
        });
      } catch (error) {
        console.error("Failed to fetch profile stats:", error);
      }
    };

    fetchStats();
  }, [user]);

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  const firstLetter = user?.name ? user.name.charAt(0).toUpperCase() : "U";

  return (
    <div className="profile-page">
      <div className="profile-wrapper">
        <div className="profile-top">
          <h1>My Profile</h1>
          <p className="subtitle">Manage your account, listings, and orders</p>
        </div>

        <div className="profile-card">
          <div className="profile-header">
            <div className="avatar">{firstLetter}</div>

            <div className="profile-info">
              <h2>{user?.name || "User Name"}</h2>
              <p>{user?.email || "user@email.com"}</p>
            </div>
          </div>

          <div className="profile-stats">
            <div className="stat-box">
              <h3>{stats.listings}</h3>
              <p>Listings</p>
            </div>
            <div className="stat-box">
              <h3>{stats.sold}</h3>
              <p>Sold</p>
            </div>
            <div className="stat-box">
              <h3>{stats.ordered}</h3>
              <p>Ordered</p>
            </div>
          </div>

          <div className="profile-actions">
            <button
              className="primary-btn"
              onClick={() => navigate("/edit-profile")}
            >
              Edit Info
            </button>

            <button
              className="secondary-btn"
              onClick={() => navigate("/my-listings")}
            >
              My Listings
            </button>

            <button
              className="secondary-btn"
              onClick={() => setShowOrders(!showOrders)}
            >
              My Orders <span>{showOrders ? "−" : "+"}</span>
            </button>

            {showOrders && (
              <div className="orders-box">
                <div className="order-group">
                  <h4>Ordered</h4>

                  <Link to="/orders/ordered/in-progress" className="order-link">
                    In Progress
                  </Link>

                  <Link to="/orders/ordered/completed" className="order-link">
                    Completed
                  </Link>
                </div>

                <div className="order-group">
                  <h4>Sold</h4>

                  <Link to="/orders/sold/in-progress" className="order-link">
                    In Progress
                  </Link>

                  <Link to="/orders/sold/completed" className="order-link">
                    Completed
                  </Link>
                </div>
              </div>
            )}

            <button className="logout-btn" onClick={handleLogout}>
              Logout
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

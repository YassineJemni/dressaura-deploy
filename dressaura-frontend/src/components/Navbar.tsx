import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import "./Navbar.css";

function Navbar() {
  const { isAuthenticated, user, logout } = useAuth();

  return (
    <header className="navbar">
      <div className="navbar-container">
        <div className="logo">
          <Link to="/">DRESSAURA</Link>
        </div>

        <nav className="nav-links">
          <Link to="/">Home</Link>
          <Link to="/browse">Browse</Link>
          <Link to="/#how-it-works">How it works</Link>
          <Link to="/sell">Sell</Link>
          {isAuthenticated && <Link to="/chat">Chats</Link>}
        </nav>

        <div className="auth-links">
          {isAuthenticated ? (
            <>
              <Link to="/profile">{user?.name}</Link>
              <button onClick={logout} className="register">
                Logout
              </button>
            </>
          ) : (
            <>
              <Link to="/login">Login</Link>
              <Link to="/register" className="register">
                Register
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

export default Navbar;
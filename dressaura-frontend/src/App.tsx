import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import ChatPage from "./pages/ChatPage";
import Home from "./pages/Home";
import Browse from "./pages/Browse";
import ProductDetails from "./pages/ProductDetails";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Sell from "./pages/Sell";
import Checkout from "./pages/Checkout";
import Profile from "./pages/Profile";
import OrdersPage from "./pages/OrdersPage";
/* Footer Pages */
import Help from "./pages/Help";
import About from "./pages/About";
import Terms from "./pages/Terms";
import Privacy from "./pages/Privacy";
import MyListings from "./pages/MyListings";
import EditProfile from "./pages/EditProfile";
import EditListing from "./pages/EditListing";

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Navbar />

        <Routes>
          {/* Main pages */}
          <Route path="/" element={<Home />} />
          <Route path="/browse" element={<Browse />} />
          <Route path="/product/:id" element={<ProductDetails />} />
          <Route path="/checkout" element={<Checkout />} />
          <Route path="/sell" element={<Sell />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/my-listings" element={<MyListings />} />
          <Route path="/edit-profile" element={<EditProfile />} />
          <Route path="/edit-listing/:id" element={<EditListing />} />
          <Route path="/orders/:type/:status" element={<OrdersPage />} />

          {/* Footer pages */}
          <Route path="/help" element={<Help />} />
          <Route path="/about" element={<About />} />
          <Route path="/terms" element={<Terms />} />
          <Route path="/privacy" element={<Privacy />} />

        </Routes>

        <Footer />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
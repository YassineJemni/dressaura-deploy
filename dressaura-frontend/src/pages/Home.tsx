import "./Home.css";
import DressCard from "../components/DressCard";
import { useEffect, useState } from "react";
import { useLocation, Link } from "react-router-dom";

function Home() {
  const [dresses, setDresses] = useState<any[]>([]);
  const location = useLocation();

  useEffect(() => {
    fetch("https://dressaura-backend.vercel.app/dresses/")
      .then((res) => res.json())
      .then((data) => setDresses(data))
      .catch((err) => console.error("Failed to load dresses:", err));
  }, []);


  useEffect(() => {
    if (location.hash === "#how-it-works") {
      const section = document.getElementById("how-it-works");
      if (section) {
        section.scrollIntoView({ behavior: "smooth" });
      }
    }
  }, [location]);

  return (
    <div className="home">
      {/* HERO */}
      <section className="hero">
        <div className="hero-container">
          <h1 className="brand-title">DRESSAURA</h1>
          <p className="brand-tagline">
            old soul · new aura
          </p>

          <div className="hero-buttons">
            <Link to="/browse" className="btn primary">
              Browse Dresses
            </Link>

            <Link to="/sell" className="btn secondary">
              Sell a Dress
            </Link>
          </div>
        </div>
      </section>

      {/* FEATURED */}
      <section className="featured">
        <div className="featured-header">
          <p className="featured-label">Freshly picked for you</p>
          <h2 className="section-title">Featured Dresses</h2>
        </div>

        <div className="featured-marquee">
          <div className="featured-track">
            {dresses.length > 0 &&
              [...dresses, ...dresses, ...dresses].map((dress, index) => (
                <div
                  className="featured-card-wrap"
                  key={`${dress.id}-${index}`}
                >
                  <DressCard dress={dress} />
                </div>
              ))}
          </div>
        </div>
      </section>

      <section id="how-it-works" className="how-it-works">
        <div className="how-container">
          <h2 className="section-title light">How It Works</h2>

          <div className="flows">
            {/* BUYERS */}
            <div className="flow-card">
              <h3>For Buyers</h3>

              <div className="flow-step">
                <span>01</span>
                <div>
                  <h4>Explore</h4>
                  <p>Find unique dresses for every occasion</p>
                </div>
              </div>

              <div className="flow-step">
                <span>02</span>
                <div>
                  <h4>Connect</h4>
                  <p>Message sellers and ask questions safely</p>
                </div>
              </div>

              <div className="flow-step">
                <span>03</span>
                <div>
                  <h4>Order</h4>
                  <p>Buy securely and receive your dress</p>
                </div>
              </div>
            </div>

            {/* SELLERS */}
            <div className="flow-card">
              <h3>For Sellers</h3>

              <div className="flow-step">
                <span>01</span>
                <div>
                  <h4>Upload</h4>
                  <p>List dresses you no longer wear</p>
                </div>
              </div>

              <div className="flow-step">
                <span>02</span>
                <div>
                  <h4>Chat</h4>
                  <p>Answer questions and confirm details</p>
                </div>
              </div>

              <div className="flow-step">
                <span>03</span>
                <div>
                  <h4>Sell</h4>
                  <p>Complete the order and get paid</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

export default Home;

import "./Browse.css";
import DressCard from "../components/DressCard";
import { useEffect, useState } from "react";

function Browse() {
  const [dresses, setDresses] = useState<any[]>([]);
  const [filteredDresses, setFilteredDresses] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // FILTER STATES
  const [size, setSize] = useState("");
  const [condition, setCondition] = useState("");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");

  useEffect(() => {
    fetch("https://dressaura-backend.vercel.app/dresses/")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        console.log("✅ dresses from backend:", data);

        const normalized = data.map((dress: any) => ({
          ...dress,
          condition: dress.condition_status,
          price: Number(dress.price),
        }));

        setDresses(normalized);
        setFilteredDresses(normalized);
        setLoading(false);
      })
      .catch((err) => {
        console.error("❌ Failed to fetch dresses:", err);
        setLoading(false);
      });
  }, []);


  const applyFilters = () => {
    let result = [...dresses];

    if (size) {
      result = result.filter((d) => d.size === size);
    }

    if (condition) {
      result = result.filter((d) => d.condition === condition);
    }

    if (minPrice) {
      result = result.filter((d) => d.price >= Number(minPrice));
    }

    if (maxPrice) {
      result = result.filter((d) => d.price <= Number(maxPrice));
    }

    setFilteredDresses(result);
  };

  return (
    <div className="browse">
      <div className="browse-container">
        <aside className="filters">
          <h3>Filter</h3>

          <div className="filter-group">
            <label>Size</label>
            <select value={size} onChange={(e) => setSize(e.target.value)}>
              <option value="">All sizes</option>
              <option>XXS</option>
              <option>XS</option>
              <option>S</option>
              <option>M</option>
              <option>L</option>
              <option>XL</option>
              <option>XXL</option>
              <option>XXXL</option>
              <option>One Size</option>
            </select>
          </div>

          <div className="filter-group">
            <label>Price range</label>
            <div className="price-range">
              <input
                type="number"
                min="0"
                placeholder="Min €"
                value={minPrice}
                onChange={(e) => setMinPrice(e.target.value)}
              />
              <input
                type="number"
                min="0"
                placeholder="Max €"
                value={maxPrice}
                onChange={(e) => setMaxPrice(e.target.value)}
              />
            </div>
          </div>

          <div className="filter-group">
            <label>Condition</label>
            <select
              value={condition}
              onChange={(e) => setCondition(e.target.value)}
            >
              <option value="">All conditions</option>
              <option>New with tags</option>
              <option>New without tags</option>
              <option>Very good</option>
              <option>Good</option>
              <option>Satisfactory</option>
            </select>
          </div>

          {/* SEARCH BUTTON */}
          <button className="filter-btn" onClick={applyFilters}>
            Search
          </button>
        </aside>

        <section className="results">
          <h2>Browse Dresses</h2>

          {loading && <p>Loading dresses...</p>}

          {!loading && filteredDresses.length === 0 && (
            <p>No dresses match your filters.</p>
          )}

          {!loading && filteredDresses.length > 0 && (
            <div className="dress-grid">
              {filteredDresses.map((dress) => (
                <DressCard key={dress.id} dress={dress} />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default Browse;

import { Link } from "react-router-dom";
import "./DressCard.css";

type Dress = {
  id: number;
  brand: string;
  size: string;
  price: number;
  image_url?: string;
};

function DressCard({ dress }: { dress: Dress }) {
  return (
    <div className="dress-card">
      {/* IMAGE */}
      {dress.image_url ? (
        <img
          src={`https://dressaura-backend.vercel.app${dress.image_url}`}
          alt={dress.brand}
          style={{
            width: "100%",
            height: "220px",
            objectFit: "cover",
            borderRadius: "14px",
            marginBottom: "18px"
          }}
        />
      ) : (
        <div className="image-placeholder">No Image</div>
      )}

      <div className="card-content">
        <h3>{dress.brand}</h3>
        <p className="size">Size {dress.size}</p>

        <div className="card-footer">
          <span className="price">€{dress.price}</span>

          <Link to={`/product/${dress.id}`} className="view-btn">
            View details
          </Link>
        </div>
      </div>
    </div>
  );
}

export default DressCard;


import "./EditListing.css";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

const API_URL = "https://dressaura-backend.vercel.app";

type PhotoItem =
  | {
      type: "existing";
      id: number | string;
      image_url: string;
      preview: string;
    }
  | {
      type: "new";
      file: File;
      preview: string;
      tempId: string;
    };

export default function EditListing() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    brand: "",
    size: "",
    condition_status: "",
    description: "",
    price: "",
  });

  const [photos, setPhotos] = useState<PhotoItem[]>([]);
  const [initialPhotos, setInitialPhotos] = useState<PhotoItem[]>([]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const getImageUrl = (url: string) => {
    if (!url) return "";

    if (url.startsWith("http")) {
      return url;
    }

    return `${API_URL}${url}`;
  };

  useEffect(() => {
    const fetchListing = async () => {
      try {
        const res = await fetch(`${API_URL}/dresses/${id}`);

        const data = await res.json();

        if (!res.ok) {
          throw new Error(
            data.detail || "Failed to load listing."
          );
        }

        setFormData({
          brand: data.brand || "",
          size: data.size || "",
          condition_status: data.condition_status || "",
          description: data.description || "",
          price:
            data.price !== undefined && data.price !== null
              ? String(data.price)
              : "",
        });

        let loadedPhotos: PhotoItem[] = [];

        if (Array.isArray(data.images) && data.images.length > 0) {
          const sortedImages = [...data.images].sort(
            (a, b) =>
              Number(a.display_order) - Number(b.display_order)
          );

          loadedPhotos = sortedImages.map((image) => ({
            type: "existing" as const,
            id: image.id,
            image_url: image.image_url,
            preview: getImageUrl(image.image_url),
          }));
        } else if (data.image_url) {
          // Backwards compatibility with old listings
          loadedPhotos = [
            {
              type: "existing",
              id: "legacy-image",
              image_url: data.image_url,
              preview: getImageUrl(data.image_url),
            },
          ];
        }

        setPhotos(loadedPhotos);
        setInitialPhotos(loadedPhotos);
      } catch (err: any) {
        console.error("❌ Failed to load listing:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchListing();
  }, [id]);

  const handleChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >
  ) => {
    setFormData((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  const handleImageChange = (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    const selectedFiles = Array.from(e.target.files || []);

    if (selectedFiles.length === 0) return;

    const remainingSlots = 10 - photos.length;

    if (remainingSlots <= 0) {
      setError("You can upload a maximum of 10 photos.");
      e.target.value = "";
      return;
    }

    const filesToAdd = selectedFiles.slice(0, remainingSlots);

    const preparedPhotos: PhotoItem[] = filesToAdd.map(
      (file, index) => ({
        type: "new" as const,
        file,
        preview: URL.createObjectURL(file),
        tempId: `${Date.now()}-${index}-${Math.random()}`,
      })
    );

    setPhotos((prev) => [...prev, ...preparedPhotos]);

    if (selectedFiles.length > remainingSlots) {
      setError(
        `Only ${remainingSlots} more photo(s) can be added. Maximum is 10.`
      );
    } else {
      setError("");
    }

    e.target.value = "";
  };

  const removePhoto = (photoToRemove: PhotoItem) => {
    if (photoToRemove.type === "new") {
      URL.revokeObjectURL(photoToRemove.preview);
    }

    setPhotos((prev) =>
      prev.filter((photo) => {
        if (
          photo.type === "existing" &&
          photoToRemove.type === "existing"
        ) {
          return photo.id !== photoToRemove.id;
        }

        if (
          photo.type === "new" &&
          photoToRemove.type === "new"
        ) {
          return photo.tempId !== photoToRemove.tempId;
        }

        return true;
      })
    );

    setError("");
  };

  const handleDragStart = (
    e: React.DragEvent<HTMLDivElement>,
    index: number
  ) => {
    e.dataTransfer.setData("photoIndex", String(index));
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDrop = (
    e: React.DragEvent<HTMLDivElement>,
    dropIndex: number
  ) => {
    e.preventDefault();

    const draggedIndex = Number(
      e.dataTransfer.getData("photoIndex")
    );

    if (
      Number.isNaN(draggedIndex) ||
      draggedIndex < 0 ||
      draggedIndex >= photos.length ||
      draggedIndex === dropIndex
    ) {
      return;
    }

    setPhotos((prev) => {
      const updated = [...prev];
      const [movedPhoto] = updated.splice(draggedIndex, 1);

      if (!movedPhoto) return prev;

      updated.splice(dropIndex, 0, movedPhoto);
      return updated;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!id) {
      setError("Listing ID is missing.");
      return;
    }

    if (photos.length > 10) {
      setError("You can upload a maximum of 10 photos.");
      return;
    }

    if (photos.length === 0) {
      setError("Please keep at least one photo.");
      return;
    }

    // Older listings may have only a legacy cover image instead of image records.
    // The current image endpoints cannot safely reorder or delete that legacy image.
    const hasLegacyImage = initialPhotos.some(
      (photo) => photo.type === "existing" && photo.id === "legacy-image"
    );

    const legacyPhotoStillPresent = photos.some(
      (photo) => photo.type === "existing" && photo.id === "legacy-image"
    );

    const hasNewPhotos = photos.some((photo) => photo.type === "new");

    if (hasLegacyImage && (hasNewPhotos || !legacyPhotoStillPresent)) {
      setError(
        "This older listing needs backend support for editing its legacy cover photo. No changes were saved."
      );
      return;
    }

    setSaving(true);

    const readResponse = async (response: Response) => {
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || data.message || "Failed to save changes."
        );
      }

      return data;
    };

    try {
      // 1. Save listing details.
      const detailsResponse = await fetch(
        `${API_URL}/dresses/${id}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            brand: formData.brand,
            size: formData.size,
            condition_status: formData.condition_status,
            description: formData.description,
            price: Number(formData.price),
          }),
        }
      );

      await readResponse(detailsResponse);

      // A legacy cover-only listing has no image records to reorder.
      // Its details can still be saved without touching the cover image.
      if (hasLegacyImage) {
        navigate("/my-listings");
        return;
      }

      // 2. Delete existing photos removed from the editor.
      const initialExistingPhotos = initialPhotos.filter(
        (photo): photo is Extract<PhotoItem, { type: "existing" }> =>
          photo.type === "existing" && photo.id !== "legacy-image"
      );

      const remainingExistingIds = new Set(
        photos
          .filter(
            (photo): photo is Extract<PhotoItem, { type: "existing" }> =>
              photo.type === "existing" && photo.id !== "legacy-image"
          )
          .map((photo) => String(photo.id))
      );

      const removedPhotos = initialExistingPhotos.filter(
        (photo) => !remainingExistingIds.has(String(photo.id))
      );

      for (const photo of removedPhotos) {
        const deleteResponse = await fetch(
          `${API_URL}/dresses/images/${photo.id}`,
          { method: "DELETE" }
        );

        await readResponse(deleteResponse);
      }

      // 3. Upload newly added photos.
      const newPhotos = photos.filter(
        (photo): photo is Extract<PhotoItem, { type: "new" }> =>
          photo.type === "new"
      );

      if (newPhotos.length > 0) {
        const imageFormData = new FormData();

        newPhotos.forEach((photo) => {
          imageFormData.append("images", photo.file);
        });

        const uploadResponse = await fetch(
          `${API_URL}/dresses/${id}/images`,
          {
            method: "POST",
            body: imageFormData,
          }
        );

        await readResponse(uploadResponse);
      }

      // 4. Reload saved images to obtain IDs assigned to uploaded files.
      const listingResponse = await fetch(
        `${API_URL}/dresses/${id}`
      );

      const listingData = await readResponse(listingResponse);

      const persistedImages = Array.isArray(listingData.images)
        ? [...listingData.images].sort(
            (a, b) => Number(a.display_order) - Number(b.display_order)
          )
        : [];

      const originalIds = new Set(
        initialExistingPhotos.map((photo) => String(photo.id))
      );

      const uploadedImages = persistedImages.filter(
        (image) => !originalIds.has(String(image.id))
      );

      if (uploadedImages.length !== newPhotos.length) {
        throw new Error(
          "The photos were uploaded, but their saved order could not be confirmed. Please reload the listing and check it."
        );
      }

      let newPhotoIndex = 0;

      const orderedImageIds = photos.map((photo) => {
        if (photo.type === "existing") return Number(photo.id);

        const uploadedImage = uploadedImages[newPhotoIndex];
        newPhotoIndex += 1;
        return uploadedImage.id;
      });

      // 5. Save final order; the first photo becomes the cover.
      const reorderResponse = await fetch(
        `${API_URL}/dresses/${id}/images/reorder`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image_ids: orderedImageIds }),
        }
      );

      await readResponse(reorderResponse);

      newPhotos.forEach((photo) => URL.revokeObjectURL(photo.preview));
      navigate("/my-listings");
    } catch (err: any) {
      console.error("Failed to save listing:", err);
      setError(err.message || "Failed to save changes. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="edit-listing-page">
        <h1 className="edit-title">Edit Listing</h1>
        <p className="edit-subtitle">Loading listing...</p>
      </div>
    );
  }

  const totalImages = photos.length;
  const remainingSlots = 10 - photos.length;

  return (
    <div className="edit-listing-page">
      <h1 className="edit-title">Edit Listing</h1>

      <p className="edit-subtitle">
        Update your item details and photos
      </p>

      <form onSubmit={handleSubmit} className="edit-form">
        <div className="form-group">
          <div className="photo-header">
            <label>Dress Photos</label>

            <span className="photo-count">
              {totalImages}/10 photos
            </span>
          </div>

          <p className="photo-help">
            Drag photos to change their order. The first photo will be shown
            as the main listing photo.
          </p>

          <div className="photo-grid">
            {photos.map((photo, index) => (
              <div
                key={
                  photo.type === "existing"
                    ? `existing-${photo.id}`
                    : `new-${photo.tempId}`
                }
                className={`photo-item ${
                  index === 0 ? "cover-photo" : ""
                }`}
                draggable
                onDragStart={(e) => handleDragStart(e, index)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => handleDrop(e, index)}
              >
                <img
                  src={photo.preview}
                  alt={`Dress ${index + 1}`}
                />

                {index === 0 && (
                  <span className="cover-badge">
                    Cover Photo
                  </span>
                )}

                <span className="photo-number">
                  {index + 1}
                </span>

                <button
                  type="button"
                  className="remove-photo"
                  onClick={() => removePhoto(photo)}
                  aria-label="Remove photo"
                >
                  ×
                </button>

                <span className="drag-hint">↕</span>
              </div>
            ))}

            {remainingSlots > 0 && (
              <label
                htmlFor="edit-image-upload"
                className="add-photo"
              >
                <span className="add-photo-icon">+</span>

                <span>Add Photos</span>

                <small>
                  {remainingSlots}{" "}
                  {remainingSlots === 1 ? "slot" : "slots"} remaining
                </small>
              </label>
            )}
          </div>

          <input
            id="edit-image-upload"
            type="file"
            accept="image/*"
            multiple
            onChange={handleImageChange}
            style={{
              display: "none",
            }}
          />
        </div>

        <div className="form-group">
          <label>Brand</label>

          <input
            type="text"
            name="brand"
            value={formData.brand}
            onChange={handleChange}
            required
          />
        </div>

        <div className="form-group">
          <label>Size</label>

          <select
            name="size"
            value={formData.size}
            onChange={handleChange}
            required
          >
            <option value="">Select size</option>
            <option value="XXS">XXS</option>
            <option value="XS">XS</option>
            <option value="S">S</option>
            <option value="M">M</option>
            <option value="L">L</option>
            <option value="XL">XL</option>
            <option value="XXL">XXL</option>
            <option value="XXXL">XXXL</option>
            <option value="One Size">One Size</option>
          </select>
        </div>

        <div className="form-group">
          <label>Condition</label>

          <select
            name="condition_status"
            value={formData.condition_status}
            onChange={handleChange}
            required
          >
            <option value="">Select condition</option>
            <option value="New with tags">New with tags</option>
            <option value="New without tags">New without tags</option>
            <option value="Very good">Very good</option>
            <option value="Good">Good</option>
            <option value="Satisfactory">Satisfactory</option>
          </select>
        </div>

        <div className="form-group">
          <label>Describe your item</label>

          <textarea
            name="description"
            value={formData.description}
            onChange={handleChange}
            rows={5}
          />
        </div>

        <div className="form-group">
          <label>Price (€)</label>

          <input
            type="number"
            name="price"
            value={formData.price}
            onChange={handleChange}
            min="0"
            step="0.01"
            required
          />
        </div>

        {/* ERROR */}
        {error && (
          <p className="edit-error">
            {error}
          </p>
        )}

        {/* ACTIONS */}
        <div className="edit-actions">
          <button
            type="button"
            className="cancel-btn"
            onClick={() => navigate("/my-listings")}
          >
            Cancel
          </button>

          <button
            type="submit"
            className="save-btn"
            disabled={saving}
          >
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </form>
    </div>
  );
}

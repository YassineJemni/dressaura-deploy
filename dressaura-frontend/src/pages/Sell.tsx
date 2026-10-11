import "./Sell.css";
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

function Sell() {
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();

  const [brand, setBrand] = useState("");
  const [size, setSize] = useState("");
  const [conditionStatus, setConditionStatus] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");

  const [imageFiles, setImageFiles] = useState<File[]>([]);
  const [imagePreviews, setImagePreviews] = useState<string[]>([]);

  const [draggedIndex, setDraggedIndex] = useState<number | null>(
    null
  );

  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/login");
    }
  }, [isAuthenticated, navigate]);




  const handleImageChange = (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    const selectedFiles = Array.from(
      e.target.files || []
    );

    if (selectedFiles.length === 0) {
      return;
    }

    const remainingSlots = 10 - imageFiles.length;

    if (remainingSlots <= 0) {
      alert("You can upload a maximum of 10 photos.");
      return;
    }

    const filesToAdd = selectedFiles.slice(
      0,
      remainingSlots
    );

    if (selectedFiles.length > remainingSlots) {
      alert(
        `You can only add ${remainingSlots} more photo${
          remainingSlots === 1 ? "" : "s"
        }.`
      );
    }

    const newFiles = [
      ...imageFiles,
      ...filesToAdd
    ];

    setImageFiles(newFiles);

    const newPreviews = filesToAdd.map((file) =>
      URL.createObjectURL(file)
    );

    setImagePreviews([
      ...imagePreviews,
      ...newPreviews
    ]);


    e.target.value = "";
  };




  const removeImage = (index: number) => {
    URL.revokeObjectURL(
      imagePreviews[index]
    );

    setImageFiles(
      imageFiles.filter(
        (_, i) => i !== index
      )
    );

    setImagePreviews(
      imagePreviews.filter(
        (_, i) => i !== index
      )
    );
  };



  const handleDragStart = (
    index: number
  ) => {
    setDraggedIndex(index);
  };




  const handleDragOver = (
    e: React.DragEvent<HTMLDivElement>
  ) => {
    e.preventDefault();
  };



  const handleDrop = (
    targetIndex: number
  ) => {
    if (
      draggedIndex === null ||
      draggedIndex === targetIndex
    ) {
      setDraggedIndex(null);
      return;
    }

    const reorderedFiles = [...imageFiles];
    const reorderedPreviews = [...imagePreviews];

    const [movedFile] =
      reorderedFiles.splice(
        draggedIndex,
        1
      );

    const [movedPreview] =
      reorderedPreviews.splice(
        draggedIndex,
        1
      );

    reorderedFiles.splice(
      targetIndex,
      0,
      movedFile
    );

    reorderedPreviews.splice(
      targetIndex,
      0,
      movedPreview
    );

    setImageFiles(reorderedFiles);
    setImagePreviews(reorderedPreviews);
    setDraggedIndex(null);
  };




  const handleSubmit = async (
    e: React.FormEvent
  ) => {
    e.preventDefault();

    if (!user?.id) {
      alert(
        "User information missing. Please login again."
      );
      return;
    }

    if (imageFiles.length === 0) {
      alert(
        "Please upload at least one photo."
      );
      return;
    }

    const formData = new FormData();

    formData.append(
      "user_id",
      String(user.id)
    );

    formData.append(
      "brand",
      brand
    );

    formData.append(
      "size",
      size
    );

    formData.append(
      "condition_status",
      conditionStatus
    );

    formData.append(
      "price",
      price
    );

    formData.append(
      "description",
      description
    );



    imageFiles.forEach((file) => {
      formData.append(
        "images",
        file
      );
    });

    console.log(
      "📦 Sending dress with",
      imageFiles.length,
      "images..."
    );

    try {
      const res = await fetch(
        "/api/dresses/",
        {
          method: "POST",
          body: formData,
        }
      );

      if (!res.ok) {
        const errorData =
          await res.json().catch(
            () => null
          );

        throw new Error(
          errorData?.detail ||
            `HTTP ${res.status}`
        );
      }

      const data = await res.json();

      console.log(
        "✅ Created dress:",
        data
      );

      // Clean preview URLs
      imagePreviews.forEach((preview) => {
        URL.revokeObjectURL(preview);
      });

      // Reset form
      setBrand("");
      setSize("");
      setConditionStatus("");
      setDescription("");
      setPrice("");
      setImageFiles([]);
      setImagePreviews([]);

      navigate("/my-listings");

    } catch (err) {
      console.error(
        "❌ Failed to publish listing:",
        err
      );

      alert(
        err instanceof Error
          ? err.message
          : "Failed to publish listing"
      );
    }
  };


  if (!isAuthenticated) {
    return null;
  }


  return (
    <div className="sell-page">

      <h1 className="sell-title">
        Sell a Dress
      </h1>

      <p className="sell-subtitle">
        List your pre-owned dress and give it a
        second life.
      </p>


      <form
        className="sell-form"
        onSubmit={handleSubmit}
      >

        {/* IMAGE UPLOAD */}

        <div className="form-group">

          <label>
            Dress Photos
          </label>

          <p
            style={{
              fontSize: "13px",
              color: "#777",
              marginBottom: "10px",
            }}
          >
            Add up to 10 photos. Drag and drop
            them to change their order. The first
            photo will be your main listing photo.
          </p>


          <input
            type="file"
            accept="image/*"
            multiple
            onChange={handleImageChange}
            style={{
              display: "none",
            }}
            id="image-upload"
          />


          <div
            style={{
              display: "grid",
              gridTemplateColumns:
                "repeat(auto-fill, minmax(110px, 1fr))",
              gap: "12px",
              marginBottom: "12px",
            }}
          >

            {imagePreviews.map(
              (preview, index) => (

                <div
                  key={preview}
                  draggable
                  onDragStart={() =>
                    handleDragStart(index)
                  }
                  onDragOver={handleDragOver}
                  onDrop={() =>
                    handleDrop(index)
                  }
                  style={{
                    position: "relative",
                    height: "130px",
                    borderRadius: "10px",
                    overflow: "hidden",
                    border:
                      index === 0
                        ? "2px solid #111"
                        : "1px solid #ddd",
                    cursor: "grab",
                    background: "#f5f5f5",
                  }}
                >

                  <img
                    src={preview}
                    alt={`Preview ${index + 1}`}
                    style={{
                      width: "100%",
                      height: "100%",
                      objectFit: "cover",
                    }}
                  />


                  {/* MAIN PHOTO LABEL */}

                  {index === 0 && (
                    <span
                      style={{
                        position: "absolute",
                        top: "6px",
                        left: "6px",
                        background: "#111",
                        color: "#fff",
                        padding:
                          "4px 7px",
                        borderRadius: "5px",
                        fontSize: "10px",
                      }}
                    >
                      Main photo
                    </span>
                  )}


                  {/* PHOTO NUMBER */}

                  <span
                    style={{
                      position: "absolute",
                      bottom: "6px",
                      left: "6px",
                      background:
                        "rgba(0,0,0,0.65)",
                      color: "#fff",
                      padding:
                        "3px 6px",
                      borderRadius: "5px",
                      fontSize: "11px",
                    }}
                  >
                    {index + 1}
                  </span>


                  {/* REMOVE BUTTON */}

                  <button
                    type="button"
                    onClick={() =>
                      removeImage(index)
                    }
                    style={{
                      position: "absolute",
                      top: "5px",
                      right: "5px",
                      width: "25px",
                      height: "25px",
                      borderRadius: "50%",
                      border: "none",
                      background:
                        "rgba(0,0,0,0.7)",
                      color: "#fff",
                      cursor: "pointer",
                    }}
                  >
                    ×
                  </button>

                </div>
              )
            )}


            {/* ADD PHOTO BUTTON */}

            {imageFiles.length < 10 && (
              <label
                htmlFor="image-upload"
                style={{
                  height: "130px",
                  border:
                    "2px dashed #ccc",
                  borderRadius: "10px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent:
                    "center",
                  textAlign: "center",
                  cursor: "pointer",
                  color: "#777",
                  fontSize: "13px",
                  padding: "10px",
                }}
              >
                + Add photo
              </label>
            )}

          </div>


          <p
            style={{
              fontSize: "12px",
              color: "#888",
            }}
          >
            {imageFiles.length}/10 photos
          </p>

        </div>


        {/* BRAND */}

        <div className="form-group">

          <label>
            Brand
          </label>

          <input
            type="text"
            required
            value={brand}
            onChange={(e) =>
              setBrand(e.target.value)
            }
          />

        </div>


        {/* SIZE */}

        <div className="form-group">

          <label>
            Size
          </label>

          <select
            required
            value={size}
            onChange={(e) =>
              setSize(e.target.value)
            }
          >
            <option value="">
              Select size
            </option>

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


        {/* CONDITION */}

        <div className="form-group">

          <label>
            Condition
          </label>

          <select
            required
            value={conditionStatus}
            onChange={(e) =>
              setConditionStatus(
                e.target.value
              )
            }
          >
            <option value="">
              Select condition
            </option>

            <option>
              New with tags
            </option>

            <option>
              New without tags
            </option>

            <option>
              Very good
            </option>

            <option>
              Good
            </option>

            <option>
              Satisfactory
            </option>
          </select>

        </div>


        {/* DESCRIPTION */}

        <div className="form-group">

          <label>
            Describe your item
          </label>

          <textarea
            rows={4}
            required
            value={description}
            onChange={(e) =>
              setDescription(
                e.target.value
              )
            }
          />

        </div>


        {/* PRICE */}

        <div className="form-group">

          <label>
            Price (€)
          </label>

          <input
            type="number"
            min="0"
            required
            value={price}
            onChange={(e) =>
              setPrice(e.target.value)
            }
          />

        </div>


        {/* SUBMIT */}

        <button
          type="submit"
          className="sell-btn"
        >
          Publish Listing
        </button>

      </form>

    </div>
  );
}

export default Sell;
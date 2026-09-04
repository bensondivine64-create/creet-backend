import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name="lcjgnp0q",
    api_key="557198235456264",
    api_secret="_HloHiWWn4hbgJNPVEyrJk4f43o",
    secure=True,
)


def upload_image(file_storage, folder):
    result = cloudinary.uploader.upload(file_storage, folder=folder)
    return result["secure_url"]

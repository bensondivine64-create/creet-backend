import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name="lcjgnp0q",
    api_key="251968674712245",
    api_secret="9Uv55pY06Bouh1wA2Yd3Zvnb1Qs",
    secure=True,
)


def upload_image(file_storage, folder):
    result = cloudinary.uploader.upload(file_storage, folder=folder)
    return result["secure_url"]

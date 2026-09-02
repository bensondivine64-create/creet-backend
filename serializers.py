def user_to_dict(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_verified": bool(user.is_verified),
        "is_premium": bool(user.is_premium),
        "avatar": user.avatar,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }

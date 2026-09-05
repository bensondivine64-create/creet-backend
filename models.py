from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON, Numeric
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # buyer | freelancer | vendor
    is_admin = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    is_premium = Column(Boolean, default=False)
    premium_expires = Column(DateTime, nullable=True)
    avatar = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    categories = Column(JSON, default=list)
    profile_completed = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class OtpCode(Base):
    __tablename__ = "otp_codes"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    purpose = Column(String(10), nullable=False)  # verify | reset
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    kind = Column(String(10), nullable=False)  # gig | product | request
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=False)
    price = Column(Numeric(12, 2), nullable=False, default=0)
    currency = Column(String(10), default="NGN")
    images = Column(JSON, default=list)
    delivery_days = Column(Integer, nullable=True)
    condition_status = Column(String(10), nullable=True)  # new | used
    stock = Column(Integer, nullable=True)
    deadline = Column(DateTime, nullable=True)
    rating_avg = Column(Numeric(3, 2), default=0)
    rating_count = Column(Integer, default=0)
    status = Column(String(10), default="active")
    sold_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String(20), nullable=False)  # reply | announcement | system
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    link = Column(String(500), nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_a_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_b_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

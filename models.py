from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Text, ForeignKey, JSON, Numeric
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
    email_confirmed = Column(Boolean, default=False)
    is_premium = Column(Boolean, default=False)
    premium_expires = Column(DateTime, nullable=True)
    avatar = Column(String(500), nullable=True)
    cover_photo = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    short_bio = Column(String(150), nullable=True)
    location = Column(String(255), nullable=True)
    phone_number = Column(String(30), nullable=True)
    referral_source = Column(String(100), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    country = Column(String(100), nullable=True)
    categories = Column(JSON, default=list)
    profile_completed = Column(Boolean, default=False)
    account_status = Column(String(20), default="active")  # active | suspended
    last_active = Column(DateTime, nullable=True)
    hide_online_status = Column(Boolean, default=False)
    notify_messages = Column(Boolean, default=True)
    notify_announcements = Column(Boolean, default=True)
    notify_listing_activity = Column(Boolean, default=True)
    onboarding_extra = Column(JSON, default=dict)
    suspension_type = Column(String(10), nullable=True)  # temporary | serious
    suspension_until = Column(DateTime, nullable=True)
    suspension_reason = Column(Text, nullable=True)
    suspension_count = Column(Integer, default=0)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class AdminAiLog(Base):
    __tablename__ = "admin_ai_logs"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    command = Column(Text, nullable=False)
    ai_raw_response = Column(Text, nullable=True)
    action_taken = Column(String(50), nullable=True)
    target_id = Column(Integer, nullable=True)
    success = Column(Boolean, default=False)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class SiteSettings(Base):
    __tablename__ = "site_settings"

    id = Column(Integer, primary_key=True)
    maintenance_mode = Column(Boolean, default=False)
    banner_active = Column(Boolean, default=False)
    banner_text = Column(Text, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Connection(Base):
    __tablename__ = "connections"

    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(10), default="pending")  # pending | accepted | declined
    created_at = Column(DateTime, server_default=func.now())
    responded_at = Column(DateTime, nullable=True)


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
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_a_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_b_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=True)
    user_a_last_read = Column(DateTime, nullable=True)
    user_b_last_read = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    target_type = Column(String(10), nullable=False)  # listing | user
    target_id = Column(Integer, nullable=False)
    reason = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(10), default="pending")  # pending | resolved
    created_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime, nullable=True)


class PremiumPayment(Base):
    __tablename__ = "premium_payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan = Column(String(20), nullable=False)  # monthly | three_months | yearly
    tx_ref = Column(String(100), unique=True, nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="NGN")
    status = Column(String(20), default="pending")  # pending | successful | failed
    flutterwave_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    verified_at = Column(DateTime, nullable=True)


class Ad(Base):
    __tablename__ = "ads"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    image_url = Column(String(500), nullable=False)
    link_url = Column(String(500), nullable=True)
    position = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Block(Base):
    __tablename__ = "blocks"

    id = Column(Integer, primary_key=True, index=True)
    blocker_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    blocked_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

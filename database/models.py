from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, 
    ForeignKey, JSON, Enum as SQLEnum, BigInteger, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

Base = declarative_base()


class SubscriptionStatus(str, enum.Enum):
    FREE = "free"
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VOICE = "voice"
    VIDEO = "video"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True, index=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    
    # Subscription
    subscription_status = Column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.FREE, index=True)
    subscription_expires_at = Column(DateTime, nullable=True, index=True)
    trial_started_at = Column(DateTime, nullable=True)
    trial_ended = Column(Boolean, default=False)
    
    # Free tier limits
    free_messages_used = Column(Integer, default=0)
    free_messages_limit = Column(Integer, default=10)
    trial_messages_used = Column(Integer, default=0)
    trial_messages_limit = Column(Integer, default=50)
    
    # Channel subscription
    channel_subscribed = Column(Boolean, default=False, index=True)
    channel_check_required = Column(Boolean, default=True)
    channel_checked_at = Column(DateTime, nullable=True)
    
    # Language
    language = Column(String(10), default="ru", index=True)
    
    # Analytics
    total_messages_sent = Column(Integer, default=0)
    total_images_sent = Column(Integer, default=0)
    total_audio_sent = Column(Integer, default=0)
    total_tokens_used = Column(Integer, default=0)  # Общее количество токенов
    total_cost_estimated = Column(Integer, default=0)  # Примерная стоимость в центах
    last_activity_at = Column(DateTime, nullable=True, index=True)
    
    # Performance
    is_active = Column(Boolean, default=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user")
    analytics = relationship("Analytics", back_populates="user")
    
    # Composite indexes для оптимизации запросов
    __table_args__ = (
        Index('idx_user_status_expires', 'subscription_status', 'subscription_expires_at'),
        Index('idx_user_active_activity', 'is_active', 'last_activity_at'),
    )


class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    message_count = Column(Integer, default=0)  # Кэшированное количество сообщений
    is_archived = Column(Boolean, default=False, index=True)  # Архивация для оптимизации
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_message_at = Column(DateTime, nullable=True, index=True)
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship(
        "Message", 
        back_populates="conversation", 
        cascade="all, delete-orphan", 
        order_by="Message.created_at",
        lazy="dynamic"  # Lazy loading для оптимизации
    )


class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message_type = Column(SQLEnum(MessageType), nullable=False)
    content = Column(Text, nullable=True)
    file_id = Column(String(255), nullable=True, index=True)
    file_path = Column(String(500), nullable=True)
    is_from_user = Column(Boolean, default=True, index=True)
    ai_response = Column(Text, nullable=True)
    tokens_used = Column(Integer, default=0)
    cost_estimated = Column(Integer, default=0)  # Стоимость в центах
    processing_time = Column(Integer, default=0)  # В миллисекундах
    created_at = Column(DateTime, default=func.now(), index=True)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    
    # Indexes для оптимизации
    __table_args__ = (
        Index('idx_msg_conv_created', 'conversation_id', 'created_at'),
        Index('idx_msg_user_type', 'user_id', 'message_type'),
    )


class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    currency = Column(String(10), default="USD")
    telegram_payment_charge_id = Column(String(255), nullable=True, unique=True, index=True)
    provider_payment_charge_id = Column(String(255), nullable=True, index=True)
    status = Column(String(50), default="pending", index=True)
    subscription_duration_days = Column(Integer, default=30)
    created_at = Column(DateTime, default=func.now(), index=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="payments")


class Analytics(Base):
    __tablename__ = "analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    event_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now(), index=True)
    
    # Relationships
    user = relationship("User", back_populates="analytics")
    
    # Partitioning index для быстрой очистки старых данных
    __table_args__ = (
        Index('idx_analytics_type_date', 'event_type', 'created_at'),
    )


class BroadcastMessage(Base):
    __tablename__ = "broadcast_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, nullable=False)
    message_text = Column(Text, nullable=True)
    photo = Column(String(255), nullable=True)
    video = Column(String(255), nullable=True)
    buttons = Column(JSON, nullable=True)
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    total_users = Column(Integer, default=0)
    status = Column(String(50), default="pending", index=True)
    created_at = Column(DateTime, default=func.now(), index=True)
    sent_at = Column(DateTime, nullable=True)


class AICache(Base):
    """Кэш для AI запросов"""
    __tablename__ = "ai_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String(255), unique=True, nullable=False, index=True)
    prompt_hash = Column(String(64), nullable=False, index=True)  # SHA256 хэш промпта
    response = Column(Text, nullable=False)
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now(), index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    hit_count = Column(Integer, default=0)  # Количество использований
    
    __table_args__ = (
        Index('idx_cache_expires', 'expires_at'),
    )


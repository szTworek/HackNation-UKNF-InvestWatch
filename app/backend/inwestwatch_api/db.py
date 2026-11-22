from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# Timestamps are ISO-8601 UTC strings ("2026-11-21T22:31:14Z"): sortable, identical on SQLite and Postgres.

class Entity(Base):
    __tablename__ = "entities"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    registry_entries: Mapped[list] = mapped_column(JSON, default=list)
    domains: Mapped[list] = mapped_column(JSON, default=list)
    social_handles: Mapped[dict] = mapped_column(JSON, default=dict)


class Item(Base):
    __tablename__ = "items"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    entity_ids: Mapped[list] = mapped_column(JSON, default=list)
    channel: Mapped[str] = mapped_column(String(16), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    source_url: Mapped[str] = mapped_column(String(1024), unique=True)
    author: Mapped[str | None] = mapped_column(String(256), nullable=True)
    author_is_entity: Mapped[bool] = mapped_column(Boolean, default=False)
    author_entity_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    published_at: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    fetched_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    query_keywords: Mapped[list] = mapped_column(JSON, default=list)
    text: Mapped[dict] = mapped_column(JSON, default=dict)
    source_meta: Mapped[dict] = mapped_column(JSON, default=dict)
    mock: Mapped[bool] = mapped_column(Boolean, default=False)


class ItemEntity(Base):
    __tablename__ = "item_entities"
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"), primary_key=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), primary_key=True, index=True)


class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"), index=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    module: Mapped[str] = mapped_column(String(4), index=True)
    score: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(8))
    rule_hits: Mapped[list] = mapped_column(JSON, default=list)
    model: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[str] = mapped_column(String(32), index=True)
    mock: Mapped[bool] = mapped_column(Boolean, default=False)


class Page(Base):
    __tablename__ = "pages"
    page_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    url: Mapped[str] = mapped_column(String(1024))
    label: Mapped[str | None] = mapped_column(String(256), nullable=True)
    mock: Mapped[bool] = mapped_column(Boolean, default=False)


class Snapshot(Base):
    __tablename__ = "snapshots"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    page_id: Mapped[str] = mapped_column(String(128), index=True)
    entity_id: Mapped[str] = mapped_column(String(32), index=True)
    url: Mapped[str] = mapped_column(String(1024))
    fetched_at: Mapped[str] = mapped_column(String(32))
    text_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    text: Mapped[str | None] = mapped_column(String, nullable=True)
    risk_warning: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    mock: Mapped[bool] = mapped_column(Boolean, default=False)


class Change(Base):
    __tablename__ = "changes"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    page_id: Mapped[str] = mapped_column(String(128), index=True)
    entity_id: Mapped[str] = mapped_column(String(32), index=True)
    from_snapshot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_snapshot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detected_at: Mapped[str] = mapped_column(String(32), index=True)
    kinds: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str | None] = mapped_column(String, nullable=True)
    added_lines: Mapped[list] = mapped_column(JSON, default=list)
    removed_lines: Mapped[list] = mapped_column(JSON, default=list)
    mock: Mapped[bool] = mapped_column(Boolean, default=False)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    severity: Mapped[str] = mapped_column(String(8))
    title: Mapped[str] = mapped_column(String(512))
    ref: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(8), default="new", index=True)
    mock: Mapped[bool] = mapped_column(Boolean, default=False)


def init_db():
    Base.metadata.create_all(engine)

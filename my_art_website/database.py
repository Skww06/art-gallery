from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./gallery.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Painting(Base):
    __tablename__ = "paintings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    medium = Column(String, nullable=False)
    dimensions = Column(String, nullable=False)
    price_cents = Column(Integer, nullable=False)
    image_filename = Column(String, nullable=False)
    extra_images = Column(Text, nullable=True)
    description = Column(Text, nullable=True)  # <-- Added description field
    is_available = Column(Boolean, default=True)

Base.metadata.create_all(bind=engine)
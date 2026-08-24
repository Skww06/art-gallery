from database import SessionLocal, engine, Base, Painting

# Ensure tables are created
Base.metadata.create_all(bind=engine)

def seed_database():
    db = SessionLocal()
    
    # Optional: Clear existing data so you don't get duplicates if you run this twice
    db.query(Painting).delete()
    
    sample_paintings = [
        Painting(
            title="Midnight Resonance",
            medium="Oil on Canvas",
            dimensions="24 x 36 inches",
            price_cents=120000,
            image_filename="sample1.JPG",  # <-- Updated to .JPG
            description="A striking exploration of shadow and light, inspired by the quiet isolation of the city at midnight. Heavy impasto techniques give the canvas a deep, tactile texture.",
            is_available=True
        ),
        Painting(
            title="Ethereal Bloom",
            medium="Acrylic and Gold Leaf",
            dimensions="18 x 24 inches",
            price_cents=85000,
            image_filename="sample2.JPG",  # <-- Updated to .JPG
            description="Delicate floral forms emerge through layers of translucent acrylic washes. The subtle gold leaf accents catch the light, changing the mood of the piece depending on the viewing angle.",
            is_available=True
        ),
        Painting(
            title="Coastal Convergence",
            medium="Watercolor on Cold Press",
            dimensions="11 x 14 inches",
            price_cents=45000,
            image_filename="sample3.JPG",  # <-- Updated to .JPG
            description="Painted en plein air on the rugged coast. This work captures the volatile energy where the ocean meets the rocky shoreline using rapid, expressive brushstrokes.",
            is_available=False
        )
    ]

    # Add all sample paintings to the database
    db.add_all(sample_paintings)
    db.commit()
    db.close()
    
    print("✅ Database successfully seeded with artworks and descriptions!")

if __name__ == "__main__":
    seed_database()
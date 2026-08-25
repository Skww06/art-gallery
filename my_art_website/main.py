import os
import secrets
import shutil
import stripe
from fastapi import FastAPI, Depends, Request, Form, File, UploadFile, status, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from database import SessionLocal, Painting

app = FastAPI(title="Original Art Gallery")

# Mount static folder & setup Jinja2 templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

IMAGE_DIR = "static/images"
os.makedirs(IMAGE_DIR, exist_ok=True)

# Basic Auth Setup
security = HTTPBasic()
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "supersecretpassword"

# Stripe API Setup
# Replace with your actual secret key from dashboard.stripe.com when ready for live payments
stripe.api_key = "sk_test_51U5co2KPLf2b02uzXrHyd4zN8EED2SHTuhqWPIPxighnj64T2gR3Pn0wehNlxgWUEL9TmzPs9bCJvKDuZQYwZWT100lBlff3jI" 

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    is_user_correct = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    is_pass_correct = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (is_user_correct and is_pass_correct):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------
# PUBLIC CUSTOMER ROUTES
# ----------------

@app.get("/")
async def home(request: Request, db: Session = Depends(get_db)):
    # Grab ALL paintings, including sold ones
    paintings = db.query(Painting).all()
    
    return templates.TemplateResponse(
        request=request,
        name="index.html", 
        context={"request": request, "paintings": paintings}
    )

@app.post("/create-checkout-session/{painting_id}")
def create_checkout_session(painting_id: int, request: Request, db: Session = Depends(get_db)):
    painting = db.query(Painting).filter(Painting.id == painting_id, Painting.is_available == True).first()
    
    if not painting:
        raise HTTPException(status_code=404, detail="Painting not found or sold")
        
    base_url = str(request.base_url).rstrip("/")
    
    checkout_session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd", 
                "product_data": {"name": painting.title}, 
                "unit_amount": painting.price_cents
            }, 
            "quantity": 1
        }],
        mode="payment",
        success_url=f"{base_url}/success?painting_id={painting.id}",
        cancel_url=f"{base_url}/",
    )
    
    return RedirectResponse(url=checkout_session.url, status_code=303)

@app.post("/add")
async def create_painting(
    title: str = Form(...),
    medium: str = Form(...),
    dimensions: str = Form(...),
    price_dollars: float = Form(...),
    description: str = Form(""),
    image_file: UploadFile = File(...),
    extra_images: list[UploadFile] = File(None),  # <-- Accept multiple optional files
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin)
):
    """Protected upload handler for main image and optional extra gallery shots."""
    # Save main thumbnail image
    main_filename = image_file.filename
    main_path = os.path.join(IMAGE_DIR, main_filename)
    with open(main_path, "wb") as buffer:
        shutil.copyfileobj(image_file.file, buffer)

    # Save extra detailed images
    saved_extra_filenames = []
    if extra_images:
        for img in extra_images:
            if img.filename:
                extra_path = os.path.join(IMAGE_DIR, img.filename)
                with open(extra_path, "wb") as buffer:
                    shutil.copyfileobj(img.file, buffer)
                saved_extra_filenames.append(img.filename)

    price_cents = int(price_dollars * 100)
    extra_images_str = ",".join(saved_extra_filenames) if saved_extra_filenames else ""

    new_painting = Painting(
        title=title,
        medium=medium,
        dimensions=dimensions,
        price_cents=price_cents,
        image_filename=main_filename,
        extra_images=extra_images_str,  # <-- Save comma-separated list
        description=description,
        is_available=True
    )

    db.add(new_painting)
    db.commit()

    return RedirectResponse(url="/admin", status_code=303)

@app.get("/success")
def payment_success(request: Request, painting_id: int, db: Session = Depends(get_db)):
    """Page displayed after successful Stripe payment."""
    painting = db.query(Painting).filter(Painting.id == painting_id).first()
    if painting:
        # Mark painting as sold upon successful checkout
        painting.is_available = False
        db.commit()
    return templates.TemplateResponse(
        request=request,
        name="success.html",
        context={"painting": painting}
    )

# ----------------
# PROTECTED ADMIN ROUTES
# ----------------

@app.get("/admin")
def admin_dashboard(
    request: Request, 
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin)
):
    paintings = db.query(Painting).all()
    return templates.TemplateResponse(
        request=request, 
        name="admin.html", 
        context={"paintings": paintings}
    )

@app.get("/add")
def add_painting_form(
    request: Request,
    admin: str = Depends(verify_admin)
):
    return templates.TemplateResponse(
        request=request,
        name="add_painting.html",
        context={}
    )

@app.post("/add")
async def create_painting(
    title: str = Form(...),
    medium: str = Form(...),
    dimensions: str = Form(...),
    price_dollars: float = Form(...),
    description: str = Form(""),
    photos: list[UploadFile] = File(...),  # <-- Receives all selected photos at once
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin)
):
    """Protected upload handler that automatically assigns the first photo as thumbnail and the rest as extras."""
    if not photos or not photos[0].filename:
        return RedirectResponse(url="/admin", status_code=303)

    saved_filenames = []
    
    # Save all uploaded photos to static/images/
    for img in photos:
        if img.filename:
            file_path = os.path.join(IMAGE_DIR, img.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(img.file, buffer)
            saved_filenames.append(img.filename)

    # First image is the main thumbnail
    main_filename = saved_filenames[0]
    
    # Any remaining images become extra gallery slider shots
    extra_filenames = saved_filenames[1:]
    extra_images_str = ",".join(extra_filenames) if extra_filenames else ""

    price_cents = int(price_dollars * 100)

    new_painting = Painting(
        title=title,
        medium=medium,
        dimensions=dimensions,
        price_cents=price_cents,
        image_filename=main_filename,
        extra_images=extra_images_str,
        description=description,
        is_available=True
    )

    db.add(new_painting)
    db.commit()

    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/toggle/{painting_id}")
def toggle_painting_status(
    painting_id: int, 
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin)
):
    painting = db.query(Painting).filter(Painting.id == painting_id).first()
    if painting:
        painting.is_available = not painting.is_available
        db.commit()
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/delete/{painting_id}")
def delete_painting(
    painting_id: int, 
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin)
):
    painting = db.query(Painting).filter(Painting.id == painting_id).first()
    if painting:
        db.delete(painting)
        db.commit()
    return RedirectResponse(url="/admin", status_code=303)
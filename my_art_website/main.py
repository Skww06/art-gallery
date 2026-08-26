import cloudinary
import cloudinary.uploader

# Configure Cloudinary with your credentials from Step 1
cloudinary.config(
    cloud_name="your_cloud_name_here",
    api_key="your_api_key_here",
    api_secret="your_api_secret_here"
)
import os
import secrets
import shutil
import stripe
import uuid
from fastapi import FastAPI, Depends, Request, Form, File, UploadFile, status, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database import SessionLocal, Painting

app = FastAPI(title="Original Art Gallery")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

IMAGE_DIR = "static/images"
os.makedirs(IMAGE_DIR, exist_ok=True)

# Admin Credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Sr19960412!"

# Stripe API Setup
stripe.api_key = "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" 

def verify_admin(request: Request):
    """Checks if the user has a valid admin session cookie."""
    session_token = request.cookies.get("admin_session")
    if session_token != "authenticated_active":
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"}
        )
    return ADMIN_USERNAME

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------
# AUTHENTICATION ROUTES
# ----------------

@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})

@app.post("/login")
def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    is_user_correct = secrets.compare_digest(username, ADMIN_USERNAME)
    is_pass_correct = secrets.compare_digest(password, ADMIN_PASSWORD)
    
    if not (is_user_correct and is_pass_correct):
        return templates.TemplateResponse(
            request=request, 
            name="login.html", 
            context={"error": "Invalid username or password."},
            status_code=401
        )
    
    # Set a secure session cookie upon successful login
    response = RedirectResponse(url="/admin", status_code=303)
    response.set_cookie(key="admin_session", value="authenticated_active", httponly=True)
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="admin_session")
    return response

# ----------------
# PUBLIC CUSTOMER ROUTES
# ----------------

@app.get("/")
async def home(request: Request, db: Session = Depends(get_db)):
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
        shipping_address_collection={
            "allowed_countries": ["US", "CA", "GB", "AU", "FR", "DE"],
        },
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

@app.get("/success")
def payment_success(request: Request, painting_id: int, db: Session = Depends(get_db)):
    painting = db.query(Painting).filter(Painting.id == painting_id).first()
    if painting:
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
    photos: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin)
):
    if not photos or not photos[0].filename:
        return RedirectResponse(url="/admin", status_code=303)

    saved_image_urls = []
    
    for img in photos:
        if img.filename:
            # Upload directly to Cloudinary cloud storage
            upload_result = cloudinary.uploader.upload(img.file)
            secure_url = upload_result.get("secure_url")
            saved_image_urls.append(secure_url)

    main_url = saved_image_urls[0]
    extra_urls = saved_image_urls[1:]
    extra_images_str = ",".join(extra_urls) if extra_urls else ""
    price_cents = int(price_dollars * 100)

    new_painting = Painting(
        title=title,
        medium=medium,
        dimensions=dimensions,
        price_cents=price_cents,
        image_filename=main_url,         # Stores the full Cloudinary URL
        extra_images=extra_images_str,   # Stores comma-separated Cloudinary URLs
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
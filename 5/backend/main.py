from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Form, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, Boolean, Text, DateTime, func, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pydantic import BaseModel, ConfigDict
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uuid
import os
import shutil
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "finance_world")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
    
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

print(f"DATABASE_URL настроен")

UPLOAD_FOLDER = "/tmp/uploads/product_images"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    icon = Column(String, nullable=False)
    active = Column(Boolean, default=True)

class Product(Base):
    __tablename__ = "products"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    bank = Column(String, nullable=False)
    category = Column(String, nullable=False)
    image_url = Column(String, nullable=True)
    description = Column(Text, nullable=False)
    conditions = Column(Text, nullable=False)
    url = Column(String, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        with engine.begin() as conn:
            try:
                conn.execute(text("ALTER TABLE categories ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE;"))
            except Exception:
                pass

        Base.metadata.create_all(bind=engine)
        
        db = SessionLocal()
        try:
            if db.query(Category).count() == 0:
                default_categories = [
                    Category(id="debit", name="Дебетовые карты", icon="💳", active=True),
                    Category(id="credit", name="Кредитные карты", icon="💰", active=True),
                    Category(id="sim", name="SIM карты", icon="📱", active=True),
                    Category(id="ip", name="ИП", icon="👨‍💼", active=True),
                    Category(id="rko", name="РКО", icon="🏦", active=True),
                ]
                db.add_all(default_categories)
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
    except Exception:
        pass
        
    yield

app = FastAPI(title="Finance World API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",
        "http://localhost:3000",
        "http://localhost:5500",
        "http://localhost:8080",
        "https://*.pages.dev",
        "https://*.finance-world.online",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Expose-Headers"] = "*"
    return response

class CategoryCreate(BaseModel):
    id: str
    name: str
    icon: str
    active: bool = True

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    active: Optional[bool] = None

class CategoryResponse(BaseModel):
    id: str
    name: str
    icon: str
    active: bool
    
    model_config = ConfigDict(from_attributes=True)

class ProductCreate(BaseModel):
    name: str
    bank: str
    category: str
    description: str
    conditions: str
    url: str
    active: bool = True

class ProductResponse(BaseModel):
    id: str
    name: str
    bank: str
    category: str
    image_url: Optional[str] = None
    description: str
    conditions: str
    url: str
    active: bool
    created_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@finance.ru")
ADMIN_PASSWORD_HASH = pwd_context.hash(os.getenv("ADMIN_PASSWORD", "admin123"))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str = Depends(oauth2_scheme)):
    if not token:
        raise HTTPException(status_code=403, detail="Для выполнения данного действия авторизуйтесь")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Токен не может быть прочитан")

def verify_token_optional(token: Optional[str] = Depends(oauth2_scheme_optional)):
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None

@app.get("/")
async def root():
    return {
        "message": "Finance World API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": db_status,
        "total_categories": db.query(Category).count(),
        "total_products": db.query(Product).count()
    }

@app.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username != ADMIN_EMAIL or not pwd_context.verify(form_data.password, ADMIN_PASSWORD_HASH):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неправильный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_values = {"sub": form_data.username}
    return {
        "access_token": create_access_token(token_values),
        "token_type": "bearer",
    }

@app.get("/categories", response_model=List[CategoryResponse])
def get_categories(
    db: Session = Depends(get_db),
    current_user: Optional[str] = Depends(verify_token_optional)
):
    query = db.query(Category)
    
    # Если НЕ админ, показываем только активные
    if not current_user:
        query = query.filter(Category.active == True)
    
    # Сортируем для удобства админа (например, по ID или имени)
    return query.order_by(Category.name).all()

@app.get("/categories/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: str, 
    db: Session = Depends(get_db),
    current_user: Optional[str] = Depends(verify_token_optional)
):
    query = db.query(Category).filter(Category.id == category_id)
    
    if not current_user:
        query = query.filter(Category.active == True)
        
    category = query.first()
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена или скрыта")
    return category

@app.post("/categories", response_model=CategoryResponse)
def create_category(
    category: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: str = Depends(verify_token)
):
    existing_category = db.query(Category).filter(Category.id == category.id).first()
    if existing_category:
        raise HTTPException(status_code=400, detail="Category with this ID already exists")
    
    db_category = Category(**category.model_dump())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    
    return db_category

@app.put("/categories/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: str,
    category_update: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: str = Depends(verify_token)
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    update_data = category_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)
    
    db.commit()
    db.refresh(category)
    
    return category

@app.delete("/categories/{category_id}")
def delete_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: str = Depends(verify_token)
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    products_count = db.query(Product).filter(Product.category == category_id).count()
    if products_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete category. There are {products_count} products in this category."
        )
    
    db.delete(category)
    db.commit()
    
    return {"message": "Category deleted successfully"}

@app.get("/products", response_model=List[ProductResponse])
def get_products(
    db: Session = Depends(get_db),
    current_user: Optional[str] = Depends(verify_token_optional)
):
    query = db.query(Product)
    
    if not current_user:
        query = query.join(Category, Product.category == Category.id).filter(
            Product.active == True,
            Category.active == True
        )
    
    return query.order_by(Product.created_at.desc()).all()

@app.get("/products/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: str, 
    db: Session = Depends(get_db),
    current_user: Optional[str] = Depends(verify_token_optional)
):
    query = db.query(Product).filter(Product.id == product_id)
    
    if not current_user:
        query = query.join(Category, Product.category == Category.id).filter(
            Product.active == True,
            Category.active == True
        )
        
    product = query.first()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден или скрыт")
    return product

@app.post("/products", response_model=ProductResponse)
async def create_product(
    name: str = Form(...),
    bank: str = Form(...),
    category: str = Form(...),
    description: str = Form(...),
    conditions: str = Form(...),
    url: str = Form(...),
    active: bool = Form(True),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: str = Depends(verify_token)
):
    category_exists = db.query(Category).filter(Category.id == category).first()
    if not category_exists:
        raise HTTPException(status_code=400, detail=f"Category '{category}' does not exist")
    
    product_id = str(uuid.uuid4())
    product = Product(
        id=product_id,
        name=name,
        bank=bank,
        category=category,
        description=description,
        conditions=conditions,
        url=url,
        active=active
    )
    
    if file and file.filename:
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        filename = f"{product_id}.{file_extension}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        product.image_url = f"/uploads/product_images/{filename}"
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    return product

@app.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    name: str = Form(...),
    bank: str = Form(...),
    category: str = Form(...),
    description: str = Form(...),
    conditions: str = Form(...),
    url: str = Form(...),
    active: bool = Form(...),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: str = Depends(verify_token)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    category_exists = db.query(Category).filter(Category.id == category).first()
    if not category_exists:
        raise HTTPException(status_code=400, detail=f"Category '{category}' does not exist")
    
    product.name = name
    product.bank = bank
    product.category = category
    product.description = description
    product.conditions = conditions
    product.url = url
    product.active = active
    
    if file and file.filename:
        if product.image_url:
            old_file_path = product.image_url.lstrip("/")
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
        
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        filename = f"{product_id}.{file_extension}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        product.image_url = f"/uploads/product_images/{filename}"
    
    db.commit()
    db.refresh(product)
    
    return product

@app.delete("/products/{product_id}")
async def delete_product(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: str = Depends(verify_token)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if product.image_url:
        file_path = product.image_url.lstrip("/")
        if os.path.exists(file_path):
            os.remove(file_path)
    
    db.delete(product)
    db.commit()
    
    return {"message": "Product deleted successfully"}

@app.get("/stats")
async def get_stats(
    db: Session = Depends(get_db),
    current_user: str = Depends(verify_token)
):
    total_products = db.query(func.count(Product.id)).scalar()
    active_products = db.query(func.count(Product.id)).filter(Product.active == True).scalar()
    total_categories = db.query(func.count(Category.id)).scalar()
    
    categories_stats = db.query(
        Category.id, 
        Category.name, 
        func.count(Product.id).label("product_count")
    ).join(Product, Category.id == Product.category, isouter=True)\
     .group_by(Category.id, Category.name).all()
    
    return {
        "total_products": total_products,
        "active_products": active_products,
        "inactive_products": total_products - active_products,
        "total_categories": total_categories,
        "categories": [
            {"id": cat.id, "name": cat.name, "product_count": cat.product_count} 
            for cat in categories_stats
        ]
    }

app.mount("/uploads/product_images", StaticFiles(directory=UPLOAD_FOLDER), name="uploads")

if __name__ == "__main__":
    import uvicorn
    
    port_str = os.getenv("PORT")
    if port_str is None:
        port = 8000
    else:
        try:
            port = int(port_str)
        except ValueError:
            port = 8000
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )
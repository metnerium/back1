from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import jwt
import random
import os
from datetime import datetime, timedelta
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

# Настройка CORS
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение к базе данных PostgreSQL
SQLALCHEMY_DATABASE_URL = "postgresql://app:qwerty00@localhost/myapp"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Модели данных
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True)
    username = Column(String)
    jwt = Column(String)

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    lessons = Column(String)
    video_links = Column(String)

class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))

    user = relationship("User", backref="enrollments")
    course = relationship("Course", backref="enrollments")

# Схемы Pydantic
class UserCreate(BaseModel):
    phone_number: str

class UserInfo(BaseModel):
    username: str

class CourseInfo(BaseModel):
    id: int
    name: str
    lessons: str
    video_links: str

# Утилиты
SECRET_KEY = "my_secret_key"
ALGORITHM = "HS256"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def generate_jwt(user_id):
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=30)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_jwt(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        return user_id
    except jwt.exceptions.DecodeError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Роуты
@app.post("/auth")
def auth(user_create: UserCreate, db=Depends(get_db)):
    phone_number = user_create.phone_number
    user = db.query(User).filter(User.phone_number == phone_number).first()

    if not user:
        # Создать нового пользователя
        code = str(random.randint(10000, 99999))
        # Отправить код на номер телефона через SMS API
        new_user = User(phone_number=phone_number, username=f"Ученик {code}")
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return {"message": f"Код отправлен на номер {phone_number}"}

    # Генерировать новый код и отправить на номер телефона
    code = str(random.randint(10000, 99999))
    # Отправить код на номер телефона через SMS API
    return {"message": f"Код отправлен на номер {phone_number}"}

@app.post("/verify")
def verify(code: str, db=Depends(get_db)):
    # Проверить код и выдать JWT токен
    user = db.query(User).filter(User.username == f"Ученик {code}").first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid code")

    jwt_token = generate_jwt(user.id)
    user.jwt = jwt_token
    db.commit()

    return {"jwt": jwt_token}

@app.post("/setname")
def set_name(user_info: UserInfo, token: str = Depends(decode_jwt), db=Depends(get_db)):
    user_id = decode_jwt(token)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.username = user_info.username
    db.commit()

    return {"message": "Username updated successfully"}

@app.get("/profile")
def get_profile(token: str = Depends(decode_jwt), db=Depends(get_db)):
    user_id = decode_jwt(token)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"username": user.username, "phone_number": user.phone_number}

@app.get("/courses", response_model=List[str])
def get_courses(db=Depends(get_db)):
    courses = db.query(Course).all()
    course_names = [course.name for course in courses]
    return course_names

@app.get("/enrolled_courses")
def get_enrolled_courses(token: str = Depends(decode_jwt), db=Depends(get_db)):
    user_id = decode_jwt(token)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    enrollments = user.enrollments
    course_names = [enrollment.course.name for enrollment in enrollments]
    return course_names

@app.get("/course_details/{course_id}")
def get_course_details(course_id: int, token: str = Depends(decode_jwt), db=Depends(get_db)):
    decode_jwt(token)  # Проверка JWT токена
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    return {
        "id": course.id,
        "name": course.name,
        "lessons": course.lessons,
        "video_links": course.video_links
    }

# Создание таблиц в базе данных
Base.metadata.create_all(bind=engine)

# Настройка Swagger UI
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="EGE Preparation Online School API",
        version="1.0.0",
        description="API for the EGE Preparation Online School",
        routes=app.routes,
    )

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
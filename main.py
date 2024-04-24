from fastapi.middleware.cors import CORSMiddleware
import secrets
import string
import requests
import jwt
from datetime import datetime, timedelta
from typing import List
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.openapi.utils import get_openapi

# Настройка базы данных
engine = create_engine('postgresql://user:Fogot173546@localhost/online_school')
Session = sessionmaker(bind=engine)
Base = declarative_base()

# Модели для таблиц
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    phone_number = Column(String, unique=True)
    username = Column(String)
    jwt_token = Column(String)

    enrollments = relationship('Enrollment', back_populates='user')

class Course(Base):
    __tablename__ = 'courses'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    lessons = Column(String)
    video_links = Column(String)

class Enrollment(Base):
    __tablename__ = 'enrollments'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    course_id = Column(Integer, ForeignKey('courses.id'))

    user = relationship('User', back_populates='enrollments')
    course = relationship('Course')

Base.metadata.create_all(engine)

# Модели для запросов
class AuthRequest(BaseModel):
    phone_number: str

class NameRequest(BaseModel):
    name: str
    jwt_token: str

# Настройка FastAPI
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Секретный ключ для JWT
SECRET_KEY = 'your_secret_key'

# Функция для генерации JWT токена
def generate_token(phone_number):
    payload = {
        'phone_number': phone_number,
        'exp': datetime.utcnow() + timedelta(days=1)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

# Функция для проверки JWT токена
def verify_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        phone_number = payload['phone_number']
        return phone_number
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        raise HTTPException(status_code=401, detail='Invalid token')

# Функция для получения кода авторизации
def get_auth_code():
    return ''.join(secrets.choice(string.digits) for _ in range(5))

# Функция для отправки SMS
def send_sms(phone_number, code):
    url = f'http://api.smsfeedback.ru/messages/v2/send?login=metnerium&password=Fogot173546&phone={phone_number}&text=Код авторизации в Дитнастии - {code}'
    requests.get(url)

# Роут для авторизации
@app.post('/auth')
def auth(auth_request: AuthRequest, session: Session = Depends(Session)):
    phone_number = auth_request.phone_number
    user = session.query(User).filter_by(phone_number=phone_number).first()

    if not user:
        code = get_auth_code()
        send_sms(phone_number, code)
        # Здесь нужно получить код от пользователя и сравнить с отправленным кодом
        # ...
        new_user = User(phone_number=phone_number, username=f'Ученик {len(session.query(User).all()) + 1}')
        session.add(new_user)
        session.commit()
        token = generate_token(phone_number)
        new_user.jwt_token = token
        session.commit()
        return {'jwt_token': token}
    else:
        code = get_auth_code()
        send_sms(phone_number, code)
        # Здесь нужно получить код от пользователя и сравнить с отправленным кодом
        # ...
        token = generate_token(phone_number)
        user.jwt_token = token
        session.commit()
        return {'jwt_token': token}

# Роут для установки имени пользователя
@app.post('/set_name')
def set_name(name_request: NameRequest, session: Session = Depends(Session)):
    jwt_token = name_request.jwt_token
    phone_number = verify_token(jwt_token)
    user = session.query(User).filter_by(phone_number=phone_number).first()
    if user:
        user.username = name_request.name
        session.commit()
        return {'message': 'Username set successfully'}
    else:
        raise HTTPException(status_code=401, detail='Invalid token')

# Роут для получения информации о профиле
@app.get('/profile')
def get_profile(jwt_token: str = Depends(verify_token), session: Session = Depends(Session)):
    phone_number = verify_token(jwt_token)
    user = session.query(User).filter_by(phone_number=phone_number).first()
    if user:
        return {'username': user.username, 'phone_number': user.phone_number}
    else:
        raise HTTPException(status_code=401, detail='Invalid token')

# Роут для получения списка курсов
@app.get('/courses')
def get_courses(session: Session = Depends(Session)):
    courses = session.query(Course).all()
    return [{'id': course.id, 'name': course.name} for course in courses]

# Роут для получения списка курсов, на которые зачислен пользователь
@app.get('/enrolled_courses')
def get_enrolled_courses(jwt_token: str = Depends(verify_token), session: Session = Depends(Session)):
    phone_number = verify_token(jwt_token)
    user = session.query(User).filter_by(phone_number=phone_number).first()
    if user:
        enrollments = user.enrollments
        courses = [enrollment.course for enrollment in enrollments]
        return [{'id': course.id, 'name': course.name} for course in courses]
    else:
        raise HTTPException(status_code=401, detail='Invalid token')

# Роут для получения детальной информации о курсе
@app.get('/course_details/{course_id}')
def get_course_details(course_id: int, jwt_token: str = Depends(verify_token), session: Session = Depends(Session)):
    phone_number = verify_token(jwt_token)
    user = session.query(User).filter_by(phone_number=phone_number).first()
    if user:
        course = session.query(Course).filter_by(id=course_id).first()
        if course:
            return {
                'id': course.id,
                'name': course.name,
                'lessons': course.lessons.split(','),
                'video_links': course.video_links.split(',')
            }
        else:
            raise HTTPException(status_code=404, detail='Course not found')
    else:
        raise HTTPException(status_code=401, detail='Invalid token')

# Роут для Swagger UI
@app.get('/docs', include_in_schema=False)
async def get_documentation(request: Request):
    return RedirectResponse(url='/docs')

@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint():
    return JSONResponse(get_openapi(title="Online School API", version="1.0.0", routes=app.routes))
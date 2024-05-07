from fastapi.middleware.cors import CORSMiddleware
import secrets
import string
import requests
import jwt
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.openapi.utils import get_openapi
from fastapi import Header

# Настройка базы данных
engine = create_engine('postgresql://user:pass@localhost/db')
Session = sessionmaker(bind=engine)
Base = declarative_base()
auth_scheme = HTTPBearer()
# Модели для таблиц
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    phone_number = Column(String, unique=True)
    username = Column(String)
    jwt_token = Column(String)
    auth_code = Column(String)  # Новое поле для кода авторизации
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
class CourseCreationRequest(BaseModel):
    name: str
    lessons: List[str]
    video_links: List[str]

class CourseUpdateRequest(BaseModel):
    name: Optional[str] = None
    lessons: Optional[List[str]] = None
    video_links: Optional[List[str]] = None
class EnrollmentRequest(BaseModel):
    jwt_token: str
    course_id: int
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
SECRET_KEY = 'qwerty00'

# Функция для генерации JWT токена
def generate_token(phone_number):
    payload = {
        'phone_number': phone_number,
        'exp': datetime.utcnow() + timedelta(days=30)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

# Функция для проверки JWT токена
def verify_token(token: str = Depends(auth_scheme)):
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
    url = f'http://api.smsfeedback.ru/messages/v2/send?login=metnerium&password=pass&phone={phone_number}&text=Код авторизации в Династии - {code}'
    requests.get(url)

# Роут для авторизации
@app.post('/send_auth_code')
def send_auth_code(auth_request: AuthRequest):
    session = Session()
    phone_number = auth_request.phone_number
    user = session.query(User).filter_by(phone_number=phone_number).first()

    if not user:
        code = get_auth_code()
        send_sms(phone_number, code)
        new_user = User(phone_number=phone_number, username=f'Ученик {len(session.query(User).all()) + 1}', auth_code=code)
        session.add(new_user)
        session.commit()
        return {'message': 'Code sent to your phone number'}
    else:
        code = get_auth_code()
        user.auth_code = code
        session.commit()
        send_sms(phone_number, code)
        return {'message': 'Code sent to your phone number'}
    session.close()
# Роут для проверки кода авторизации
@app.post('/verify_code')
def verify_code(code: str, auth_request: AuthRequest):
    session = Session()
    phone_number = auth_request.phone_number
    user = session.query(User).filter_by(phone_number=phone_number).first()

    if user:
        if code == user.auth_code:
            token = generate_token(phone_number)
            user.jwt_token = token
            session.commit()
            return {'jwt_token': token}
        else:
            raise HTTPException(status_code=401, detail='Invalid code')
    else:
        raise HTTPException(status_code=404, detail='User not found')
    session.close()
# Роут для установки имени пользователя
@app.post('/set_name')
def set_name(name_request: NameRequest):
    session = Session()
    jwt_token = name_request.jwt_token
    phone_number = verify_token(jwt_token)
    user = session.query(User).filter_by(phone_number=phone_number).first()
    if user:
        user.username = name_request.name
        session.commit()
        return {'message': 'Username set successfully'}
    else:
        raise HTTPException(status_code=401, detail='Invalid token')
    session.close()
# Роут для получения информации о профиле
@app.get('/profile')
def get_profile(jwt_token: str):
    session = Session()
    phone_number = verify_token(jwt_token)  # This call retrieves phone number
    user = session.query(User).filter_by(phone_number=phone_number).first()
    if user:
        return {'username': user.username, 'phone_number': user.phone_number}
    else:
        raise HTTPException(status_code=401, detail='Invalid token')
    session.close()
# Роут для получения списка курсов
@app.get('/courses')
def get_courses():
    session = Session()
    courses = session.query(Course).all()
    return [{'id': course.id, 'name': course.name} for course in courses]
    session.close()
# Роут для получения списка курсов, на которые зачислен пользователь
@app.get('/enrolled_courses')
def get_enrolled_courses(jwt_token: str):
    session = Session()
    phone_number = verify_token(jwt_token)
    user = session.query(User).filter_by(phone_number=phone_number).first()
    if user:
        enrollments = user.enrollments
        courses = [enrollment.course for enrollment in enrollments]
        return [{'id': course.id, 'name': course.name} for course in courses]
    else:
        raise HTTPException(status_code=401, detail='Invalid token')
    session.close()

# Роут для получения детальной информации о курсе
@app.get('/course_details/{course_id}')
def get_course_details(course_id: int, jwt_token: str):
    session = Session()
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
    session.close()
# Роут для создания курса
@app.post('/create_courses')
def create_course(course_request: CourseCreationRequest):
    session = Session()
    course = Course(
        name=course_request.name,
        lessons=','.join(course_request.lessons),
        video_links=','.join(course_request.video_links)
    )
    session.add(course)
    session.commit()
    session.refresh(course)
    session.close()
    return {'id': course.id}

# Роут для редактирования курса
@app.put('/edit_courses/{course_id}')
def update_course(course_id: int, course_request: CourseUpdateRequest):
    session = Session()
    course = session.query(Course).filter_by(id=course_id).first()
    if course:
        if course_request.name:
            course.name = course_request.name
        if course_request.lessons:
            course.lessons = ','.join(course_request.lessons)
        if course_request.video_links:
            course.video_links = ','.join(course_request.video_links)
        session.commit()
        session.close()
        return {'message': 'Course updated successfully'}
    else:
        session.close()
        raise HTTPException(status_code=404, detail='Course not found')
# Роут для записи на курс
@app.post('/enroll')
def enroll_course(enrollment_request: EnrollmentRequest, jwt_token: str = Depends(auth_scheme)):
    session = Session()
    jwt_token = enrollment_request.jwt_token
    phone_number = verify_token(jwt_token)
    user = session.query(User).filter_by(phone_number=phone_number).first()
    course = session.query(Course).filter_by(id=enrollment_request.course_id).first()

    if user and course:
        # Проверяем, не записан ли пользователь уже на этот курс
        existing_enrollment = session.query(Enrollment).filter_by(user_id=user.id, course_id=course.id).first()
        if existing_enrollment:
            session.close()
            raise HTTPException(status_code=400, detail='User already enrolled in this course')

        enrollment = Enrollment(user_id=user.id, course_id=course.id)
        session.add(enrollment)
        session.commit()
        session.close()
        return {'message': 'User enrolled in course successfully'}
    else:
        session.close()
        raise HTTPException(status_code=404, detail='User or course not found')
# Роут для Swagger UI
@app.get('/docs', include_in_schema=False)
async def get_documentation(request: Request):
    return RedirectResponse(url='/docs')

@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint():
    return JSONResponse(get_openapi(title="Online School API", version="1.0.0", routes=app.routes))

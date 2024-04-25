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

# Роут для отправки кода авторизации
def get_auth_code():
    return ''.join(secrets.choice(string.digits) for _ in range(5))

# Функция для отправки SMS
def send_sms(phone_number, code):
    url = f'http://api.smsfeedback.ru/messages/v2/send?login=metnerium&password=Fogot173546&phone={phone_number}&text=Код авторизации в Династии - {code}'
    requests.get(url)
code = get_auth_code()
send_sms("79280108240", code)
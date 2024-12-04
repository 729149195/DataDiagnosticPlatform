@echo off
start powershell -NoExit -Command "cd frontend;  npm run dev"
start powershell -NoExit -Command "cd backend; python manage.py runserver 0.0.0.0:5000"

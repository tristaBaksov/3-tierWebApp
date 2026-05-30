import os
import time
from typing import List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI()

# Читаем настройки подключения из переменных окружения (которые мы прописали в docker-compose)
DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("DB_NAME", "todo_db")
DB_USER = os.getenv("DB_USER", "devops_user")
DB_PASS = os.getenv("DB_PASS", "super_password")

def get_db_connection():
    # Ждем запуска базы данных (до 10 попыток с паузой)
    for i in range(10):
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASS
            )
            return conn
        except psycopg2.OperationalError:
            print("База данных еще не готова, ждем 2 секунды...")
            time.sleep(2)
    raise Exception("Не удалось подключиться к PostgreSQL!")

# При старте приложения создаем таблицу, если её нет
@app.on_event("startup")
def startup_event():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            completed BOOLEAN DEFAULT FALSE
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

# Модели Pydantic для валидации данных
class TaskCreate(BaseModel):
    title: str

class Task(BaseModel):
    id: int
    title: str
    completed: bool = False

@app.get("/api/tasks", response_model=List[Task])
def get_tasks():
    conn = get_db_connection()
    # RealDictCursor нужен, чтобы получать данные из базы в виде словарей (JSON)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, title, completed FROM tasks ORDER BY id ASC;")
    tasks = cur.fetchall()
    cur.close()
    conn.close()
    return tasks

@app.post("/api/tasks", response_model=Task)
def create_task(task: TaskCreate):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "INSERT INTO tasks (title) VALUES (%s) RETURNING id, title, completed;",
        (task.title,)
    )
    new_task = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return new_task

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE id = %s RETURNING id;", (task_id,))
    deleted = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True}
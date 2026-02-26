"""
run.py  –  Launch desde la RAÍZ del proyecto
─────────────────────────────────────────────
Uso:
    python run.py

Equivalente a:
    uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

Por qué este archivo existe:
    En Windows es fácil abrir terminal dentro de la carpeta 'app/' por error.
    Este script siempre agrega la raíz del proyecto al sys.path correctamente.
"""

import sys
import os

# Garantiza que la raíz del proyecto esté en el path
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[ROOT],
    )

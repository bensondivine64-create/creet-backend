from flask import Flask
from flask_cors import CORS

from database import Base, engine
import models
from routers_auth import auth_bp

Base.metadata.create_all(bind=engine)

app = Flask(__name__)
CORS(app, origins=["http://localhost:3000", "http://localhost:3001", "https://creet.name.ng"])

app.register_blueprint(auth_bp)


@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

from flask import Flask
from flask_cors import CORS

from database import Base, engine
import models
from routers_auth import auth_bp
from routers_listings import listings_bp
from routers_profile import profile_bp
from routers_comments import comments_bp
from routers_notifications import notifications_bp
from routers_messages import messages_bp
from routers_admin import admin_bp
from routers_reports import reports_bp
from routers_settings import settings_bp
from routers_connections import connections_bp
from routers_payments import payments_bp
from routers_ads import ads_bp
from routers_blocks import blocks_bp
from routers_network import network_bp
from welcome_email import start_welcome_email_scheduler

Base.metadata.create_all(bind=engine)

app = Flask(__name__)
CORS(app, origins=["http://localhost:3000", "http://localhost:3001", "https://creet.name.ng"], supports_credentials=True)

app.register_blueprint(auth_bp)
app.register_blueprint(listings_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(comments_bp)
app.register_blueprint(notifications_bp)
app.register_blueprint(messages_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(connections_bp)
app.register_blueprint(payments_bp)
app.register_blueprint(ads_bp)
app.register_blueprint(blocks_bp)
app.register_blueprint(network_bp)


@app.get("/api/health")
def health():
    return {"status": "ok"}


import os
if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
    start_welcome_email_scheduler()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

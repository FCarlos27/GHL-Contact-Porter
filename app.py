import os
from dotenv import load_dotenv
from flask import Flask

load_dotenv()

from routes.auth import auth_bp
from routes.main import main_bp
from routes.oauth import oauth_bp
from routes.contacts import contacts_bp

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-fallback-only-use-locally")

app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(oauth_bp)
app.register_blueprint(contacts_bp)

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=5000)

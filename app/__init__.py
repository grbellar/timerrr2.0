from flask import Flask
from flask_cors import CORS

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # Configuration
    app.config['SECRET_KEY'] = 'dev-secret-key'
    
    # Register blueprints
    from app.routes import main
    app.register_blueprint(main)
    
    return app

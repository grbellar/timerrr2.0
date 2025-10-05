from app import create_app
import os
from dotenv import load_dotenv

# Load environment variables in development
load_dotenv()

app, socketio = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    # Run without async_mode specified - Flask-SocketIO will auto-select threading mode
    socketio.run(app, debug=True, host='0.0.0.0', port=port, use_reloader=True)

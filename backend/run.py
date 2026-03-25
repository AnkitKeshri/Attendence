from backend.app import app, configure_logging
from backend.database import initialize_database


if __name__ == "__main__":
    initialize_database()
    configure_logging()
    app.run(host="0.0.0.0", port=5000, debug=False)

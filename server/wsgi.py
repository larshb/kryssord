from app import app

if __name__ == "__main__":
    # Use Render default configuration for production
    app.run(host="0.0.0.0", port=10000)

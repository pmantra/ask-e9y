import os
import uvicorn

if __name__ == "__main__":
    # Get the port from environment variables or default to 8000
    port = int(os.environ.get("PORT", 8000))

    # Run the application with the correct port
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
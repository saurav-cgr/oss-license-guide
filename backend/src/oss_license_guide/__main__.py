"""Entry point for running the backend with uvicorn."""

import uvicorn


def main() -> None:
    """Run the uvicorn development server."""
    uvicorn.run(
        "oss_license_guide.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        app_dir="src",
    )


if __name__ == "__main__":
    main()

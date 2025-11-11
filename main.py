from app import create_app


def main():
    app = create_app()
    # For local development; production should use a WSGI server
    app.run(debug=True)


if __name__ == "__main__":
    main()

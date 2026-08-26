from app import create_app

app = create_app()

if __name__ == "__main__":
    # Listen on the phone's LAN interface so trusted devices on the same
    # Wi-Fi network can reach the app. Keep this LAN-only and do not expose
    # port 5000 directly to the public internet.
    app.run(host="0.0.0.0", port=5000)

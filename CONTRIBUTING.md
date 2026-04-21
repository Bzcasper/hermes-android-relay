# Contributing to Hermes Android Relay

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Testing

```bash
pytest tests/
```

## Building APK locally

Requires Android Studio or gradle.

```bash
git clone --depth 1 https://github.com/raulvidis/hermes-android.git
cd hermes-android/hermes-android-bridge
./gradlew assembleDebug
```

## Deploy to Render

Push to `main` branch triggers automatic deployment via GitHub Actions.

Manual deploy:
```bash
git push origin main
```

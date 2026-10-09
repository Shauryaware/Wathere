# Wathere — Python Prototype

Wathere is a Flask + SQLite prototype for discovering public drinking-water points and public toilets, viewing reported cleanliness and operational status, and submitting community reports.

## Features included
- Search and filter facilities by type or name/address
- Facility detail pages
- Community issue reports with optional image upload
- Add-facility form
- Basic confidence/freshness heuristic
- Nearby facilities JSON endpoint (`/api/nearby?lat=29.58&lon=80.22&radius=5`)
- Responsive, black-and-white interface

## Important limitations
- The included facilities are fictional sample records. Replace them with verified data before any real use.
- The confidence score is a transparent demo heuristic, not a validated AI model.
- Image upload is included, but image analysis is **not yet implemented**. A computer-vision model can be integrated later.
- The app does not determine whether drinking water is safe. Water safety requires appropriate tests or trusted test records.
- The add-facility route has no authentication and is for local demonstration only. Add login/authorization before deployment.
- This is a prototype, not a production-ready public service.

## Run on Windows

1. Install Python 3.10 or newer.
2. Extract the ZIP and open the `Wathere_Python_Project` folder in VS Code.
3. Open a terminal in that folder.
4. Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\\Scripts\\activate
```

5. Install dependencies:

```powershell
pip install -r requirements.txt
```

6. Run the app:

```powershell
python app.py
```

7. Open `http://127.0.0.1:5000` in your browser.

The SQLite database is created automatically on first run. To reset the demo data, stop the app and delete `wathere.db`; it will be recreated at the next launch.

## Suggested next steps
1. Add admin authentication and moderation of user reports.
2. Integrate a real map and browser geolocation.
3. Add an image-classification model trained/evaluated on appropriate sanitation images.
4. Import verified facility locations and current inspection data.
5. Test the cleanliness and status scoring against human inspections.

# timerrr-w-flask

A Flask application created with my Flask boilerplate generator.

## Getting Started

### Activate virtual environment
```bash
source .venv/bin/activate
```

### Install dependencies
```bash
pip install -r requirements.txt
```

### app the application
```bash
python app.py
```

Visit http://localhost:5000 to see your app!

## Project Structure

```
timerrr-w-flask/
├── app/
│   ├── __init__.py       # App factory
│   ├── routes.py         # Route definitions
│   ├── templates/        # HTML templates
│   │   ├── base.html
│   │   └── index.html
│   ├── static/           # Static files
│   │   └── css/
│   │       └── style.css
│   └── models/           # Database models (if needed)
├── .venv/                 # Virtual environment
├── .env                  # Environment variables
├── .gitignore
├── requirements.txt
├── app.py               # Application entry point
└── README.md
```

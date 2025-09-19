# run.py
from app import create_app

app = create_app()
from dotenv import load_dotenv
load_dotenv()
if __name__ == "__main__":
    app.run(debug=True)
#source venv/bin/activate
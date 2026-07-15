import tempfile

from app import create_app
from models import db


def test_home_redirects_to_login():
    with tempfile.NamedTemporaryFile(suffix=".db") as database:
        app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database.name}",
        })
        
        with app.app_context():
            db.create_all()
        client = app.test_client()
        response = client.get("/")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

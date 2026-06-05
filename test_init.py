import os

db_path = os.path.join(os.path.dirname(__file__), "gfsmis.db")
if os.path.exists(db_path):
    os.remove(db_path)

from app import app, seed_database
from models import db, User

with app.app_context():
    db.create_all()
    seed_database()
    print(f"Database created and seeded successfully")
    print(f"Users: {User.query.count()}")
    print(f"Stations: {__import__('models', fromlist=['Station']).Station.query.count()}")
    print(f"Certificates: {__import__('models', fromlist=['FireCertificate']).FireCertificate.query.count()}")
    print(f"Incidents: {__import__('models', fromlist=['Incident']).Incident.query.count()}")
    print(f"Budgets: {__import__('models', fromlist=['Budget']).Budget.query.count()}")
    print(f"Hydrants: {__import__('models', fromlist=['Hydrant']).Hydrant.query.count()}")
    print("All good!")

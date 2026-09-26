from app.db import init_db
from app.monitor import monitor_all

if __name__ == "__main__":
    init_db()
    print(monitor_all())

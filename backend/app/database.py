from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base , sessionmaker
from app.config import settings
from urllib.parse import quote_plus


engine = create_engine(
    settings.database_url,
    pool_pre_ping = True,
    pool_size = 5,
    max_overflow = 10
    )

SessionLocal = sessionmaker(autocommit = False, autoflush = False , bind = engine)
Base = declarative_base() #Every model in this project inherits from this base class

def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit() #commit only when the route completes without raising any error
    except Exception:
        db.rollback()  #undo any partial writes or error
        raise
    finally:
        db.close()
        
        
           #Dependancy that gives one database session per request and ensures the db is closed 
           #Either the request was successful or failure
    
       


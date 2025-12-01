import os
import logging
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, BigInteger, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, scoped_session
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///socios_bot.db') 

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Base = declarative_base()
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

def get_session():
    """Retorna una nueva sesión de SQLAlchemy."""
    return SessionLocal()

# --- Modelos de Datos ---

class Usuario(Base):
    __tablename__ = 'usuarios'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=True) 
    username = Column(String(50), unique=True, nullable=False)
    login_key = Column(String(100), nullable=False) 
    saldo = Column(Float, default=0.00)
    es_admin = Column(Boolean, default=False)
    fecha_registro = Column(DateTime, default=datetime.now)
    keys_usadas = relationship("Key", back_populates="usuario")

class Producto(Base):
    __tablename__ = 'productos'
    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False)
    categoria = Column(String(50), nullable=False)
    precio = Column(Float, nullable=False)
    descripcion = Column(String(255)) 
    fecha_creacion = Column(DateTime, default=datetime.now)
    keys = relationship("Key", back_populates="producto")

class Key(Base):
    __tablename__ = 'keys'
    id = Column(Integer, primary_key=True)
    licencia = Column(String(255), unique=True, nullable=False)
    estado = Column(String(20), default='available')
    producto_id = Column(Integer, ForeignKey('productos.id'))
    usuario_id = Column(Integer, ForeignKey('usuarios.id'), nullable=True)
    producto = relationship("Producto", back_populates="keys")
    usuario = relationship("Usuario", back_populates="keys_usadas")


def inicializar_db(target_engine=None):
    """Crea las tablas y el usuario administrador si no existen."""
    current_engine = target_engine if target_engine is not None else engine
    Base.metadata.create_all(current_engine)
    
    Session = sessionmaker(bind=current_engine)
    with Session() as session:
        if session.query(Usuario).count() == 0:
            logging.info("Insertando SOLAMENTE el usuario administrador: admin/adminpass")
            admin_user = Usuario(username='admin', login_key='adminpass', saldo=1000.00, es_admin=True)
            session.add(admin_user)
            session.commit()
            print("Base de datos inicializada con usuario administrador: admin/adminpass.")
        else:
             print("Base de datos verificada. Usuario administrador existente.")


if __name__ == '__main__':
    DATABASE_URL_LOCAL = 'sqlite:///socios_bot.db'
    print(f"Inicializando DB: {DATABASE_URL_LOCAL}")

    try:
        engine_temp = create_engine(DATABASE_URL_LOCAL)
        inicializar_db(engine_temp) 
        print("¡Proceso de creación de tablas finalizado con éxito!")
    
    except Exception as e:
        print(f"*** ERROR CRÍTICO DE CONEXIÓN ***")
        print(f"Error detallado: {e}")
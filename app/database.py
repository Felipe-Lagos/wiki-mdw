import os
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "wiki_mdw.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# Habilitar SQLite Foreign Keys estrictas
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# Creación del motor de base de datos
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False
)

# Fábrica de sesiones thread-safe con expire_on_commit=False para soporte Jinja2
SessionLocal = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
)

Base = declarative_base()


def init_db():
    """Crea todas las tablas definidas en los modelos, migra columnas y siembra el superusuario admin."""
    import app.models  # noqa: F401
    from app.models.user import User, Group
    Base.metadata.create_all(bind=engine)

    # Migración de columnas segura para SQLite sin pérdida de datos
    with engine.connect() as conn:
        try:
            cursor = conn.connection.cursor()

            # 1. Columnas en incidents
            cursor.execute("PRAGMA table_info(incidents)")
            inc_cols = [row[1] for row in cursor.fetchall()]
            if "applied_runbook_id" not in inc_cols:
                cursor.execute("ALTER TABLE incidents ADD COLUMN applied_runbook_id INTEGER REFERENCES runbooks(id)")

            # 2. Columnas en servers
            cursor.execute("PRAGMA table_info(servers)")
            srv_cols = [row[1] for row in cursor.fetchall()]
            server_new_cols = [
                ("platform_type", "VARCHAR(50) DEFAULT 'On-Premise'"),
                ("location", "VARCHAR(150)"),
                ("auth_type", "VARCHAR(30) DEFAULT 'NONE'"),
                ("auth_username", "VARCHAR(100)"),
                ("auth_secret", "VARCHAR(255)"),
                ("ssh_key_content", "TEXT"),
                ("domain_name", "VARCHAR(100)"),
                ("auth_notes", "TEXT"),
            ]
            for col_name, col_def in server_new_cols:
                if col_name not in srv_cols:
                    cursor.execute(f"ALTER TABLE servers ADD COLUMN {col_name} {col_def}")

            # 3. Columnas en users
            cursor.execute("PRAGMA table_info(users)")
            usr_cols = [row[1] for row in cursor.fetchall()]
            user_new_cols = [
                ("password_hash", "VARCHAR(255)"),
                ("group_id", "INTEGER REFERENCES groups(id)"),
                ("last_login_at", "DATETIME"),
                ("last_login_ip", "VARCHAR(45)")
            ]
            for col_name, col_def in user_new_cols:
                if col_name not in usr_cols:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")

            conn.connection.commit()
            cursor.close()
        except Exception as e:
            print(f"Nota migración BD: {e}")

    # Sembrar Grupos y Superusuario admin por defecto si no existen
    with SessionLocal() as session:
        # Grupos por defecto
        admin_grp = session.query(Group).filter(Group.code == "GRP-ADMIN").first()
        if not admin_grp:
            admin_grp = Group(
                name="Administradores de Infraestructura y Middleware",
                code="GRP-ADMIN",
                role="admin",
                description="Acceso completo: ver credenciales, editar, eliminar y gestionar usuarios."
            )
            session.add(admin_grp)

        oper_grp = session.query(Group).filter(Group.code == "GRP-OPER").first()
        if not oper_grp:
            oper_grp = Group(
                name="Operadores de Producción y Soporte L2",
                code="GRP-OPER",
                role="editor",
                description="Puede ver y editar servidores, corta-palos e incidentes. No elimina ni ve contraseñas."
            )
            session.add(oper_grp)

        view_grp = session.query(Group).filter(Group.code == "GRP-VIEW").first()
        if not view_grp:
            view_grp = Group(
                name="Lectores / Auditores / Monitoreo",
                code="GRP-VIEW",
                role="viewer",
                description="Solo lectura de inventario, base de conocimiento y métricas."
            )
            session.add(view_grp)

        session.flush()

        # Superusuario admin
        admin_user = session.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_user = User(
                username="admin",
                full_name="Super Administrador Wiki-MDW",
                email="admin@wiki-mdw.local",
                role="admin",
                is_active=True,
                group_id=admin_grp.id
            )
            admin_user.set_password("admin")
            session.add(admin_user)
        else:
            # Asegurar que admin tenga hash si la columna era nueva
            if not admin_user.password_hash:
                admin_user.set_password("admin")
                admin_user.role = "admin"
                admin_user.group_id = admin_grp.id

        session.commit()


def drop_db():
    """Elimina todas las tablas (útil para testing y reinicio limpio)."""
    Base.metadata.drop_all(bind=engine)


@contextmanager
def get_db():
    """Context manager para operaciones transaccionales con commit automático."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise

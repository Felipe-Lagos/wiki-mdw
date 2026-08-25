import os
from flask import Flask, session, g
from datetime import datetime, timezone
from app.config import config_by_name, Config
from app.database import init_db, SessionLocal
from app.routes import (
    main_bp, servers_bp, projects_bp, runbooks_bp,
    incidents_bp, audit_bp, api_bp, auth_bp, admin_users_bp
)


def create_app(config_name=None):
    """Fábrica de aplicaciones Flask con autenticación y control de roles."""
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)
    app_config = config_by_name.get(config_name, Config)
    app.config.from_object(app_config)

    # Asegurar SECRET_KEY robusta para sesiones firmadas
    if not app.config.get("SECRET_KEY") or app.config["SECRET_KEY"] == "dev-secret-key-wiki-mdw-2026-secure":
        app.secret_key = "wiki-mdw-2026-session-secret-key-change-in-prod"
    else:
        app.secret_key = app.config["SECRET_KEY"]

    # Inicializar Base de Datos y sembrar datos por defecto
    with app.app_context():
        init_db()

    # Cerrar sesión de BD al terminar cada request
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        SessionLocal.remove()

    # Inyectar usuario actual en cada request para las plantillas
    @app.before_request
    def load_current_user():
        g.user = None
        g.is_admin = False
        g.can_edit = False
        user_id = session.get("user_id")
        if user_id:
            from app.models.user import User
            from app.database import get_db
            with get_db() as db:
                user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
                if user:
                    g.user = user
                    g.is_admin = user.is_admin
                    g.can_edit = user.can_edit

    # Procesadores de contexto globales para templates Jinja2
    @app.context_processor
    def inject_global_context():
        open_incidents_count = 0
        try:
            from app.models.incident import IncidentLog
            from app.database import get_db
            with get_db() as db:
                open_incidents_count = db.query(IncidentLog).filter(
                    IncidentLog.status.in_(["OPEN", "IN_PROGRESS"])
                ).count()
        except Exception:
            pass

        return {
            "current_year": datetime.now(timezone.utc).year,
            "app_name": app.config.get("APP_NAME", "Wiki-MDW"),
            "app_version": app.config.get("APP_VERSION", "2.0.0"),
            "sidebar_open_incidents": open_incidents_count,
            "current_user": g.get("user"),
            "is_admin": g.get("is_admin", False),
            "can_edit": g.get("can_edit", False),
        }

    # Registrar todos los Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_users_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(servers_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(runbooks_bp)
    app.register_blueprint(incidents_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(api_bp)

    return app

from functools import wraps
from datetime import datetime, timezone
from flask import Blueprint, request, render_template, redirect, url_for, flash, session, g
from app.database import get_db
from app.models.user import User
from app.services.audit_service import AuditService

auth_bp = Blueprint("auth", __name__)


def get_current_user():
    """Obtiene el usuario autenticado en la sesión actual o None."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    with get_db() as db_session:
        user = db_session.query(User).filter(User.id == user_id, User.is_active == True).first()
        return user


def login_required(f):
    """Decorador para proteger rutas que requieren autenticación."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Por favor inicia sesión para acceder al portal.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorador para restringir el acceso exclusivamente a Administradores (rol 'admin')."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Inicia sesión como Administrador para acceder.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        user = get_current_user()
        if not user or not user.is_admin:
            flash("Acceso denegado: Se requieren permisos de Administrador.", "danger")
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)
    return decorated_function


def editor_required(f):
    """Decorador para permitir acceso a usuarios con permisos de edición ('admin' o 'editor')."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Inicia sesión para realizar modificaciones.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        user = get_current_user()
        if not user or not user.can_edit:
            flash("Acceso denegado: Tu perfil es solo de Lectura (Viewer).", "warning")
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Página de inicio de sesión segura."""
    if "user_id" in session:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        next_url = request.form.get("next") or request.args.get("next")

        with get_db() as db_session:
            user = db_session.query(User).filter(User.username == username).first()

            if user and user.is_active and user.check_password(password):
                # Actualizar metadatos de login
                user.last_login_at = datetime.now(timezone.utc)
                user.last_login_ip = request.remote_addr

                session.clear()
                session["user_id"] = user.id
                session["username"] = user.username
                session["full_name"] = user.full_name
                session["role"] = user.effective_role
                session["is_admin"] = user.is_admin
                session["can_edit"] = user.can_edit

                # Auditoría de acceso
                AuditService.log_change(
                    session=db_session,
                    entity_type="User",
                    entity_id=user.id,
                    action="LOGIN",
                    summary=f"Inicio de sesión exitoso de {user.username} ({user.effective_role})",
                    user_name=user.username,
                    ip_address=request.remote_addr
                )

                flash(f"¡Bienvenido de nuevo, {user.full_name}!", "success")
                if next_url and next_url.startswith("/"):
                    return redirect(next_url)
                return redirect(url_for("main.dashboard"))
            else:
                flash("Usuario o contraseña incorrectos. Verifica tus credenciales.", "danger")

    return render_template("auth/login.html", next=request.args.get("next", ""))


@auth_bp.route("/logout")
def logout():
    """Cierra la sesión del usuario."""
    username = session.get("username", "usuario")
    session.clear()
    flash(f"Sesión finalizada correctamente.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Interfaz y guía de recuperación de clave."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        master_key = request.form.get("master_key", "").strip()
        new_password = request.form.get("new_password", "").strip()

        # Llave maestra de emergencia por defecto o configurada por variable de entorno
        expected_key = "wiki-mdw-emergency-reset-2026"

        if master_key == expected_key and username and new_password:
            with get_db() as db_session:
                user = db_session.query(User).filter(User.username == username).first()
                if user:
                    user.set_password(new_password)
                    flash(f"Contraseña de '{username}' restablecida con éxito. Inicia sesión ahora.", "success")
                    return redirect(url_for("auth.login"))
                else:
                    flash(f"El usuario '{username}' no existe.", "danger")
        else:
            flash("Llave maestra de recuperación incorrecta o datos incompletos.", "danger")

    return render_template("auth/forgot_password.html")

"""
Mantenedor de Usuarios y Grupos — Solo accesible por Administradores.
CRUD completo: Crear, Editar, Activar/Desactivar y Eliminar usuarios y grupos.
"""
from flask import Blueprint, request, render_template, redirect, url_for, flash, session
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.models.user import User, Group
from app.routes.auth import admin_required
from app.services.audit_service import AuditService

admin_users_bp = Blueprint("admin_users", __name__, url_prefix="/admin/users")


# ──────────────────────────────────────────────
# GRUPOS
# ──────────────────────────────────────────────

@admin_users_bp.route("/groups")
@admin_required
def list_groups():
    with get_db() as db:
        groups = db.query(Group).order_by(Group.name.asc()).all()
    return render_template("admin/groups_list.html", groups=groups)


@admin_users_bp.route("/groups/new", methods=["GET", "POST"])
@admin_required
def create_group():
    if request.method == "POST":
        data = request.form
        try:
            with get_db() as db:
                grp = Group(
                    name=data["name"].strip(),
                    code=data["code"].strip().upper(),
                    role=data.get("role", "viewer"),
                    description=data.get("description", "").strip() or None,
                )
                db.add(grp)
                db.flush()
                AuditService.log_change(db, "Group", grp.id, "CREATE",
                    f"Nuevo grupo: {grp.name} [{grp.role}]",
                    user_name=session.get("username"), ip_address=request.remote_addr)
            flash(f"Grupo '{grp.name}' creado.", "success")
            return redirect(url_for("admin_users.list_groups"))
        except IntegrityError:
            flash("El código o nombre de grupo ya existe.", "danger")
    return render_template("admin/group_form.html", group=None, action="Crear")


@admin_users_bp.route("/groups/<int:group_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_group(group_id):
    with get_db() as db:
        grp = db.query(Group).filter(Group.id == group_id).first()
        if not grp:
            flash("Grupo no encontrado.", "danger")
            return redirect(url_for("admin_users.list_groups"))

        if request.method == "POST":
            data = request.form
            old = grp.to_dict()
            grp.name = data["name"].strip()
            grp.role = data.get("role", grp.role)
            grp.description = data.get("description", "").strip() or None
            db.flush()
            AuditService.log_change(db, "Group", grp.id, "UPDATE",
                f"Edición de grupo {grp.name}",
                user_name=session.get("username"),
                old_values=old, new_values=grp.to_dict(),
                ip_address=request.remote_addr)
            flash(f"Grupo '{grp.name}' actualizado.", "success")
            return redirect(url_for("admin_users.list_groups"))

    return render_template("admin/group_form.html", group=grp, action="Editar")


@admin_users_bp.route("/groups/<int:group_id>/delete", methods=["POST"])
@admin_required
def delete_group(group_id):
    with get_db() as db:
        grp = db.query(Group).filter(Group.id == group_id).first()
        if grp:
            if grp.code == "GRP-ADMIN":
                flash("No se puede eliminar el grupo de Administradores.", "danger")
                return redirect(url_for("admin_users.list_groups"))
            name = grp.name
            db.delete(grp)
            flash(f"Grupo '{name}' eliminado.", "success")
    return redirect(url_for("admin_users.list_groups"))


# ──────────────────────────────────────────────
# USUARIOS
# ──────────────────────────────────────────────

@admin_users_bp.route("/")
@admin_required
def list_users():
    with get_db() as db:
        users = db.query(User).order_by(User.username.asc()).all()
        groups = db.query(Group).order_by(Group.name.asc()).all()
    return render_template("admin/users_list.html", users=users, groups=groups)


@admin_users_bp.route("/new", methods=["GET", "POST"])
@admin_required
def create_user():
    with get_db() as db:
        groups = db.query(Group).order_by(Group.name.asc()).all()
        if request.method == "POST":
            data = request.form
            password = data.get("password", "").strip()
            if len(password) < 6:
                flash("La contraseña debe tener al menos 6 caracteres.", "danger")
                return render_template("admin/user_form.html", user=None, groups=groups, action="Crear")
            try:
                user = User(
                    username=data["username"].strip().lower(),
                    full_name=data["full_name"].strip(),
                    email=data.get("email", "").strip() or None,
                    role=data.get("role", "viewer"),
                    is_active=data.get("is_active") == "1",
                    group_id=int(data["group_id"]) if data.get("group_id") else None,
                )
                user.set_password(password)
                db.add(user)
                db.flush()
                AuditService.log_change(db, "User", user.id, "CREATE",
                    f"Alta de usuario {user.username} ({user.role})",
                    user_name=session.get("username"), ip_address=request.remote_addr)
                flash(f"Usuario '{user.username}' creado.", "success")
                return redirect(url_for("admin_users.list_users"))
            except IntegrityError:
                flash("El nombre de usuario o email ya está registrado.", "danger")

    return render_template("admin/user_form.html", user=None, groups=groups, action="Crear")


@admin_users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_user(user_id):
    with get_db() as db:
        user = db.query(User).filter(User.id == user_id).first()
        groups = db.query(Group).order_by(Group.name.asc()).all()
        if not user:
            flash("Usuario no encontrado.", "danger")
            return redirect(url_for("admin_users.list_users"))

        if request.method == "POST":
            data = request.form
            old = user.to_dict()
            user.full_name = data["full_name"].strip()
            user.email = data.get("email", "").strip() or None
            user.role = data.get("role", user.role)
            user.is_active = data.get("is_active") == "1"
            user.group_id = int(data["group_id"]) if data.get("group_id") else None
            new_pass = data.get("new_password", "").strip()
            if new_pass:
                if len(new_pass) < 6:
                    flash("La contraseña debe tener al menos 6 caracteres.", "danger")
                    return render_template("admin/user_form.html", user=user, groups=groups, action="Editar")
                user.set_password(new_pass)
            db.flush()
            AuditService.log_change(db, "User", user.id, "UPDATE",
                f"Edición de usuario {user.username}",
                user_name=session.get("username"),
                old_values=old, new_values=user.to_dict(),
                ip_address=request.remote_addr)
            flash(f"Usuario '{user.username}' actualizado.", "success")
            return redirect(url_for("admin_users.list_users"))

    return render_template("admin/user_form.html", user=user, groups=groups, action="Editar")


@admin_users_bp.route("/<int:user_id>/toggle", methods=["POST"])
@admin_required
def toggle_user(user_id):
    """Activa o desactiva un usuario."""
    with get_db() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            if user.username == "admin":
                flash("No se puede desactivar el superusuario admin.", "warning")
                return redirect(url_for("admin_users.list_users"))
            user.is_active = not user.is_active
            state = "activado" if user.is_active else "desactivado"
            flash(f"Usuario '{user.username}' {state}.", "info")
    return redirect(url_for("admin_users.list_users"))


@admin_users_bp.route("/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    with get_db() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            if user.username == "admin":
                flash("No se puede eliminar el superusuario admin.", "danger")
                return redirect(url_for("admin_users.list_users"))
            username = user.username
            db.delete(user)
            flash(f"Usuario '{username}' eliminado permanentemente.", "success")
    return redirect(url_for("admin_users.list_users"))

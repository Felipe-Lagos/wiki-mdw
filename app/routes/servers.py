from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from sqlalchemy import or_
from app.database import get_db
from app.models import Server, MiddlewareInstance, Project, RunbookCommand, IncidentLog, AuditLog
from app.services.audit_service import AuditService

servers_bp = Blueprint("servers", __name__, url_prefix="/servers")


@servers_bp.route("")
def list_servers():
    """Listado y filtrado de servidores de inventario."""
    q = request.args.get("q", "").strip()
    project_id = request.args.get("project_id", type=int)
    environment = request.args.get("environment", "").strip()
    status = request.args.get("status", "").strip()
    
    with get_db() as session:
        query = session.query(Server)
        
        if q:
            query = query.filter(
                or_(
                    Server.hostname.ilike(f"%{q}%"),
                    Server.ip_address.ilike(f"%{q}%"),
                    Server.os_name.ilike(f"%{q}%"),
                    Server.notes.ilike(f"%{q}%")
                )
            )
        if project_id:
            query = query.filter(Server.project_id == project_id)
        if environment:
            query = query.filter(Server.environment == environment)
        if status:
            query = query.filter(Server.status == status)

        servers = query.order_by(Server.hostname.asc()).all()
        projects = session.query(Project).order_by(Project.name.asc()).all()

        return render_template(
            "servers/list.html",
            servers=servers,
            projects=projects,
            filters={"q": q, "project_id": project_id, "environment": environment, "status": status}
        )


from sqlalchemy.exc import IntegrityError

@servers_bp.route("/new", methods=["GET", "POST"])
def create_server():
    """Creación de un nuevo servidor en el inventario."""
    with get_db() as session:
        if request.method == "POST":
            data = request.form
            server = Server(
                hostname=data.get("hostname", "").strip(),
                ip_address=data.get("ip_address", "").strip(),
                secondary_ips=data.get("secondary_ips", "").strip() or None,
                os_name=data.get("os_name", "Linux").strip(),
                os_version=data.get("os_version", "").strip() or None,
                environment=data.get("environment", "PROD").strip(),
                status=data.get("status", "ACTIVE").strip(),
                cpu_cores=int(data["cpu_cores"]) if data.get("cpu_cores") else None,
                ram_gb=int(data["ram_gb"]) if data.get("ram_gb") else None,
                ssh_port=int(data.get("ssh_port", 22)),
                project_id=int(data["project_id"]) if data.get("project_id") else None,
                notes=data.get("notes", "").strip() or None
            )
            session.add(server)
            try:
                session.flush()
            except IntegrityError:
                session.rollback()
                flash(f"Error: Ya existe un servidor registrado con el hostname '{server.hostname}' o la IP '{server.ip_address}'.", "danger")
                projects = session.query(Project).order_by(Project.name.asc()).all()
                return render_template("servers/create.html", projects=projects), 400

            # Auditoría
            AuditService.log_change(
                session=session,
                entity_type="Server",
                entity_id=server.id,
                action="CREATE",
                summary=f"Alta de nuevo servidor {server.hostname} ({server.ip_address})",
                user_name=request.headers.get("X-User", "sysadmin"),
                new_values=server.to_dict(),
                ip_address=request.remote_addr
            )
            flash(f"Servidor '{server.hostname}' registrado exitosamente.", "success")
            return redirect(url_for("servers.view_server", server_id=server.id))

        projects = session.query(Project).order_by(Project.name.asc()).all()
        return render_template("servers/create.html", projects=projects)


@servers_bp.route("/<int:server_id>")
def view_server(server_id: int):
    """Detalle completo del servidor con sus middlewares, runbooks, bitácora e historial."""
    with get_db() as session:
        server = session.query(Server).filter(Server.id == server_id).first()
        if not server:
            flash("Servidor no encontrado.", "danger")
            return redirect(url_for("servers.list_servers"))

        middlewares = session.query(MiddlewareInstance).filter(
            MiddlewareInstance.server_id == server_id
        ).all()
        
        runbooks = session.query(RunbookCommand).filter(
            RunbookCommand.server_id == server_id
        ).all()

        incidents = session.query(IncidentLog).filter(
            IncidentLog.server_id == server_id
        ).order_by(IncidentLog.occurred_at.desc()).all()

        audit_history = session.query(AuditLog).filter(
            AuditLog.entity_type == "Server",
            AuditLog.entity_id == server_id
        ).order_by(AuditLog.created_at.desc()).all()

        return render_template(
            "servers/view.html",
            server=server,
            middlewares=middlewares,
            runbooks=runbooks,
            incidents=incidents,
            audit_history=audit_history
        )


@servers_bp.route("/<int:server_id>/edit", methods=["GET", "POST"])
def edit_server(server_id: int):
    """Edición de propiedades del servidor con registro de diff en auditoría."""
    with get_db() as session:
        server = session.query(Server).filter(Server.id == server_id).first()
        if not server:
            flash("Servidor no encontrado.", "danger")
            return redirect(url_for("servers.list_servers"))

        if request.method == "POST":
            old_data = server.to_dict()
            data = request.form

            server.hostname = data.get("hostname", server.hostname).strip()
            server.ip_address = data.get("ip_address", server.ip_address).strip()
            server.secondary_ips = data.get("secondary_ips", "").strip() or None
            server.os_name = data.get("os_name", server.os_name).strip()
            server.os_version = data.get("os_version", "").strip() or None
            server.environment = data.get("environment", server.environment).strip()
            server.status = data.get("status", server.status).strip()
            server.cpu_cores = int(data["cpu_cores"]) if data.get("cpu_cores") else None
            server.ram_gb = int(data["ram_gb"]) if data.get("ram_gb") else None
            server.ssh_port = int(data.get("ssh_port", 22))
            server.project_id = int(data["project_id"]) if data.get("project_id") else None
            server.notes = data.get("notes", "").strip() or None

            session.flush()
            new_data = server.to_dict()

            # Calcular diff y auditar
            diff = AuditService.calculate_diff(old_data, new_data)
            if diff:
                AuditService.log_change(
                    session=session,
                    entity_type="Server",
                    entity_id=server.id,
                    action="UPDATE",
                    summary=f"Modificación en servidor {server.hostname} ({', '.join(diff.keys())})",
                    user_name=request.headers.get("X-User", "sysadmin"),
                    old_values=old_data,
                    new_values=new_data,
                    ip_address=request.remote_addr
                )

            flash(f"Servidor '{server.hostname}' actualizado correctamente.", "success")
            return redirect(url_for("servers.view_server", server_id=server.id))

        projects = session.query(Project).order_by(Project.name.asc()).all()
        return render_template("servers/edit.html", server=server, projects=projects)


@servers_bp.route("/<int:server_id>/delete", methods=["POST"])
def delete_server(server_id: int):
    """Eliminación de servidor y auditoría correspondiente."""
    with get_db() as session:
        server = session.query(Server).filter(Server.id == server_id).first()
        if not server:
            flash("Servidor no encontrado.", "danger")
            return redirect(url_for("servers.list_servers"))

        hostname = server.hostname
        old_data = server.to_dict()
        session.delete(server)
        session.flush()

        AuditService.log_change(
            session=session,
            entity_type="Server",
            entity_id=server_id,
            action="DELETE",
            summary=f"Baja de servidor {hostname}",
            user_name=request.headers.get("X-User", "sysadmin"),
            old_values=old_data,
            ip_address=request.remote_addr
        )

        flash(f"Servidor '{hostname}' eliminado del inventario.", "warning")
        return redirect(url_for("servers.list_servers"))


# ==========================================
# RUTAS PARA MIDDLEWARE INSTANCES EN SERVIDOR
# ==========================================

@servers_bp.route("/<int:server_id>/middlewares/new", methods=["POST"])
def add_middleware(server_id: int):
    """Agrega una instancia de middleware a un servidor."""
    with get_db() as session:
        server = session.query(Server).filter(Server.id == server_id).first()
        if not server:
            flash("Servidor no encontrado.", "danger")
            return redirect(url_for("servers.list_servers"))

        data = request.form
        middleware = MiddlewareInstance(
            server_id=server_id,
            name=data.get("name", "").strip(),
            version=data.get("version", "").strip() or None,
            install_path=data.get("install_path", "").strip(),
            domain_or_instance=data.get("domain_or_instance", "").strip() or None,
            binary_path=data.get("binary_path", "").strip() or None,
            config_path=data.get("config_path", "").strip() or None,
            service_name=data.get("service_name", "").strip() or None,
            ports=data.get("ports", "").strip() or None,
            run_user=data.get("run_user", "").strip() or None,
            status=data.get("status", "RUNNING").strip(),
            notes=data.get("notes", "").strip() or None
        )
        session.add(middleware)
        session.flush()

        AuditService.log_change(
            session=session,
            entity_type="MiddlewareInstance",
            entity_id=middleware.id,
            action="CREATE",
            summary=f"Instalación de {middleware.name} en servidor {server.hostname}",
            user_name=request.headers.get("X-User", "sysadmin"),
            new_values=middleware.to_dict(),
            ip_address=request.remote_addr
        )

        flash(f"Middleware '{middleware.name}' agregado a {server.hostname}.", "success")
        return redirect(url_for("servers.view_server", server_id=server_id))

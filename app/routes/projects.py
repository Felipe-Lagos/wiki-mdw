from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from sqlalchemy import func
from app.database import get_db
from app.models import Project, Server, IncidentLog
from app.services.audit_service import AuditService

projects_bp = Blueprint("projects", __name__, url_prefix="/projects")


@projects_bp.route("")
def list_projects():
    """Listado de proyectos y áreas con resumen de servidores asociados."""
    with get_db() as session:
        projects = session.query(Project).order_by(Project.name.asc()).all()
        
        # Conteo de servidores por proyecto
        stats = []
        for p in projects:
            server_count = session.query(Server).filter(Server.project_id == p.id).count()
            incident_count = session.query(IncidentLog).filter(IncidentLog.project_id == p.id).count()
            stats.append({
                "project": p,
                "server_count": server_count,
                "incident_count": incident_count
            })

        return render_template("projects/list.html", project_stats=stats)


@projects_bp.route("/new", methods=["GET", "POST"])
def create_project():
    """Alta de nuevo proyecto."""
    with get_db() as session:
        if request.method == "POST":
            data = request.form
            project = Project(
                name=data.get("name", "").strip(),
                code=data.get("code", "").strip().upper(),
                description=data.get("description", "").strip() or None,
                lead_name=data.get("lead_name", "").strip() or None,
                environment=data.get("environment", "PROD").strip()
            )
            session.add(project)
            session.flush()

            AuditService.log_change(
                session=session,
                entity_type="Project",
                entity_id=project.id,
                action="CREATE",
                summary=f"Creación del proyecto {project.name} ({project.code})",
                user_name=request.headers.get("X-User", "sysadmin"),
                new_values=project.to_dict(),
                ip_address=request.remote_addr
            )
            flash(f"Proyecto '{project.name}' creado exitosamente.", "success")
            return redirect(url_for("projects.list_projects"))

        return render_template("projects/create.html")


@projects_bp.route("/<int:project_id>")
def view_project(project_id: int):
    """Detalle de proyecto con servidores e incidentes relacionados."""
    with get_db() as session:
        project = session.query(Project).filter(Project.id == project_id).first()
        if not project:
            flash("Proyecto no encontrado.", "danger")
            return redirect(url_for("projects.list_projects"))

        servers = session.query(Server).filter(Server.project_id == project_id).all()
        incidents = session.query(IncidentLog).filter(IncidentLog.project_id == project_id).all()

        return render_template("projects/view.html", project=project, servers=servers, incidents=incidents)

#!/usr/bin/env python3
"""
Script de Recuperación y Reseteo de Contraseña de Administrador para Wiki-MDW.
Uso:
    python reset_admin.py
    python reset_admin.py <nuevo_password>
"""
import sys
from app.database import init_db, get_db
from app.models.user import User, Group


def reset_admin(new_pass="admin"):
    init_db()
    with get_db() as session:
        admin_grp = session.query(Group).filter(Group.code == "GRP-ADMIN").first()
        if not admin_grp:
            admin_grp = Group(
                name="Administradores de Infraestructura y Middleware",
                code="GRP-ADMIN",
                role="admin",
                description="Acceso total a la plataforma."
            )
            session.add(admin_grp)
            session.flush()

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
            session.add(admin_user)
            print("[+] Creando superusuario 'admin'...")
        else:
            admin_user.role = "admin"
            admin_user.is_active = True
            admin_user.group_id = admin_grp.id
            print("[+] Actualizando superusuario 'admin' existente...")

        admin_user.set_password(new_pass)
        session.commit()

        print("=" * 60)
        print("🎉 CONTRASEÑA DE ADMINISTRADOR RESTABLECIDA CON ÉXITO")
        print("=" * 60)
        print(f"Usuario    : admin")
        print(f"Contraseña : {new_pass}")
        print(f"Rol        : admin (Super Administrador)")
        print("=" * 60)


if __name__ == "__main__":
    password = sys.argv[1] if len(sys.argv) > 1 else "admin"
    reset_admin(password)

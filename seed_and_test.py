"""
Script de Verificación y Carga de Datos Semilla para la Fase 1 de Wiki-MDW.
Ejecuta la creación de tablas en SQLite, inserta datos de prueba realistas y valida consultas.
"""
from datetime import datetime, timezone
import json
from app.database import init_db, drop_db, get_db, DEFAULT_DB_PATH
from app.models import (
    User, Project, Server, MiddlewareInstance, 
    RunbookCommand, IncidentLog, AuditLog
)


def run_phase1_verification():
    print("=" * 70)
    print("🚀 INICIANDO VERIFICACIÓN DE FASE 1: MODELO DE DATOS SQLITE (WIKI-MDW)")
    print("=" * 70)

    # 1. Reiniciar e inicializar base de datos
    print(f"[*] Creando esquema en base de datos: {DEFAULT_DB_PATH}")
    drop_db()
    init_db()
    print("✅ Tablas creadas exitosamente en SQLite con Foreign Keys habilitadas.\n")

    # 2. Insertar datos de prueba
    with get_db() as session:
        print("[*] Insertando datos semilla...")

        # Usuarios / Operadores
        admin_user = User(
            username="felipelagos",
            full_name="Felipe Lagos",
            email="felipe.lagos@empresa.com",
            role="admin"
        )
        operator_user = User(
            username="cgonzalez",
            full_name="Carlos Gonzalez",
            email="carlos.gonzalez@empresa.com",
            role="operator"
        )
        session.add_all([admin_user, operator_user])
        session.flush()

        # Proyectos
        prj_core = Project(
            name="Core Bancario y Cuentas",
            code="PRJ-CORE",
            description="Plataforma transaccional principal y backend de cuentas corrientes.",
            lead_name="Felipe Lagos",
            environment="PROD"
        )
        prj_pagos = Project(
            name="Switch de Pagos & Transferencias",
            code="PRJ-PAY",
            description="Microservicios e integraciones de pagos en tiempo real.",
            lead_name="Carlos Gonzalez",
            environment="PROD"
        )
        session.add_all([prj_core, prj_pagos])
        session.flush()

        # Servidores
        srv1 = Server(
            hostname="srv-wls-core-prod01",
            ip_address="10.10.10.11",
            secondary_ips="10.10.10.211 (VIP Cluster)",
            os_name="Red Hat Enterprise Linux",
            os_version="8.8",
            environment="PROD",
            status="ACTIVE",
            cpu_cores=16,
            ram_gb=64,
            ssh_port=22,
            project_id=prj_core.id,
            notes="Cluster WebLogic Nodo 01 - Servidor físico en Datacenter Principal"
        )
        srv2 = Server(
            hostname="srv-mq-core-prod01",
            ip_address="10.10.10.15",
            secondary_ips="10.10.10.215",
            os_name="Red Hat Enterprise Linux",
            os_version="8.8",
            environment="PROD",
            status="ACTIVE",
            cpu_cores=8,
            ram_gb=32,
            ssh_port=22,
            project_id=prj_core.id,
            notes="Hub de Mensajería IBM MQ para integración de canales"
        )
        srv3 = Server(
            hostname="srv-tc-pagos-qa01",
            ip_address="10.20.10.25",
            os_name="Ubuntu Server",
            os_version="22.04 LTS",
            environment="QA",
            status="ACTIVE",
            cpu_cores=4,
            ram_gb=16,
            ssh_port=2222,
            project_id=prj_pagos.id,
            notes="Servidor de pruebas Tomcat para switch transaccional"
        )
        session.add_all([srv1, srv2, srv3])
        session.flush()

        # Middlewares / Aplicaciones
        wls_app = MiddlewareInstance(
            server_id=srv1.id,
            name="Oracle WebLogic Server",
            version="12.2.1.4.0",
            install_path="/u01/app/oracle/middleware/wlserver_12.2",
            domain_or_instance="domain_core_prod",
            binary_path="/u01/app/oracle/domains/domain_core_prod/bin",
            config_path="/u01/app/oracle/domains/domain_core_prod/config/config.xml",
            service_name="nodemanager.service",
            ports="7001 (Admin), 7002 (ManagedServer_01), 5556 (NodeMgr)",
            run_user="oracle",
            status="RUNNING",
            notes="JVM Flags: -Xms16g -Xmx16g -XX:+UseG1GC"
        )
        mq_app = MiddlewareInstance(
            server_id=srv2.id,
            name="IBM MQ",
            version="9.2.0.5",
            install_path="/opt/mqm",
            domain_or_instance="QM_CORE_BKG",
            binary_path="/opt/mqm/bin",
            config_path="/var/mqm/qmgrs/QM_CORE_BKG/qm.ini",
            service_name="ibm-mq.service",
            ports="1414 (Listener QM_CORE)",
            run_user="mqm",
            status="RUNNING",
            notes="Queue Manager principal con persistencia en /var/mqm"
        )
        tomcat_app = MiddlewareInstance(
            server_id=srv3.id,
            name="Apache Tomcat",
            version="9.0.82",
            install_path="/opt/tomcat/apache-tomcat-9.0.82",
            domain_or_instance="instance_switch_pay",
            binary_path="/opt/tomcat/apache-tomcat-9.0.82/bin",
            config_path="/opt/tomcat/apache-tomcat-9.0.82/conf/server.xml",
            service_name="tomcat-switch.service",
            ports="8080 (HTTP), 8443 (HTTPS), 8005 (Shutdown)",
            run_user="tomcat",
            status="RUNNING",
            notes="Despliegue de war: switch-api-v2.war"
        )
        session.add_all([wls_app, mq_app, tomcat_app])
        session.flush()

        # Runbooks / Corta-Palos
        rb1 = RunbookCommand(
            title="Reinicio Seguro de Managed Server WebLogic",
            category="WebLogic",
            description="Procedimiento para detener de forma forzada un Managed Server colgado y volverlo a iniciar vía NodeManager o script.",
            command_text=(
                "# 1. Verificar procesos activos de la JVM\n"
                "ps -ef | grep ManagedServer_01 | grep -v grep\n\n"
                "# 2. Detención graceful\n"
                "cd /u01/app/oracle/domains/domain_core_prod/bin\n"
                "./stopManagedWebLogic.sh ManagedServer_01 t3://10.10.10.11:7001\n\n"
                "# 3. En caso de stuck threads que no responden, terminar proceso\n"
                "kill -9 <PID>\n\n"
                "# 4. Iniciar en segundo plano con nohup\n"
                "nohup ./startManagedWebLogic.sh ManagedServer_01 t3://10.10.10.11:7001 > /u01/logs/ms01_boot.log 2>&1 &"
            ),
            is_dangerous=True,
            requires_sudo=False,
            created_by="felipelagos",
            server_id=srv1.id,
            middleware_id=wls_app.id
        )

        rb2 = RunbookCommand(
            title="Verificar y Reiniciar Listener de IBM MQ",
            category="IBM MQ",
            description="Comandos para verificar canales caídos y reiniciar el listener de colas.",
            command_text=(
                "# 1. Entrar como usuario mqm\n"
                "sudo su - mqm\n\n"
                "# 2. Ver estado de Queue Manager\n"
                "dspmq -m QM_CORE_BKG\n\n"
                "# 3. Ingresar a consola MQSC y chequear Listener\n"
                "runmqsc QM_CORE_BKG <<EOF\n"
                "DISPLAY LSSTATUS(LISTENER.1414)\n"
                "START LISTENER(LISTENER.1414)\n"
                "DISPLAY CHSTATUS(*)\n"
                "END\n"
                "EOF"
            ),
            is_dangerous=False,
            requires_sudo=True,
            created_by="cgonzalez",
            server_id=srv2.id,
            middleware_id=mq_app.id
        )

        rb3 = RunbookCommand(
            title="Rotación de Logs y Limpieza de Catalina.out Tomcat",
            category="Tomcat",
            description="Vaciar catalina.out sin bloquear el descriptor de archivos del proceso Java activo.",
            command_text=(
                "# NO USAR rm catalina.out (provoca retención por descriptor abierto)\n"
                "cd /opt/tomcat/apache-tomcat-9.0.82/logs\n"
                "cp catalina.out catalina.out.$(date +%Y%m%d_%H%M%S).bak\n"
                ": > catalina.out\n"
                "gzip catalina.out.*.bak"
            ),
            is_dangerous=False,
            requires_sudo=False,
            created_by="felipelagos",
            server_id=srv3.id,
            middleware_id=tomcat_app.id
        )
        session.add_all([rb1, rb2, rb3])
        session.flush()

        # Bitácora / Incidentes
        inc1 = IncidentLog(
            ticket_ref="INC-2026-0814",
            title="Saturación de Stuck Threads en ManagedServer_01 WebLogic",
            description="Alerta de APM Dynatrace por más de 80 hilos en estado STUCK en la conexión JDBC al backend de base de datos.",
            severity="HIGH",
            status="RESOLVED",
            actions_taken=(
                "1. Se generó un Thread Dump (kill -3 PID).\n"
                "2. Se detectó contención en el DataSource 'ds_core_accounts' por bloqueo de tabla en Oracle DB.\n"
                "3. El DBA liberó el cerrojo en la BD.\n"
                "4. Se reinició el ManagedServer_01 según corta-palos oficial."
            ),
            root_cause="Bloqueo exclusivo (row lock) generado por un job batch desalineado fuera de ventana.",
            resolution_steps="Ajuste de timeout en el DataSource a 30s y reprogramación del job batch.",
            operator_name="Felipe Lagos",
            server_id=srv1.id,
            middleware_id=wls_app.id,
            project_id=prj_core.id,
            occurred_at=datetime(2026, 8, 14, 15, 30, tzinfo=timezone.utc),
            resolved_at=datetime(2026, 8, 14, 16, 15, tzinfo=timezone.utc)
        )
        session.add(inc1)
        session.flush()

        # Audit Logs
        AuditLog.log(
            session=session,
            entity_type="Server",
            entity_id=srv1.id,
            action="CREATE",
            summary="Alta de servidor srv-wls-core-prod01 en inventario",
            user_name="felipelagos",
            new_values=srv1.to_dict()
        )

        # Simular una modificación y registrar su auditoría (historial de cambios)
        old_data = wls_app.to_dict()
        wls_app.notes = "JVM Flags: -Xms16g -Xmx16g -XX:+UseG1GC -Dweblogic.StdoutDebugEnabled=false"
        session.flush()
        new_data = wls_app.to_dict()

        AuditLog.log(
            session=session,
            entity_type="MiddlewareInstance",
            entity_id=wls_app.id,
            action="UPDATE",
            summary="Actualización de parámetros JVM en WebLogic",
            user_name="felipelagos",
            old_values=old_data,
            new_values=new_data,
            ip_address="192.168.1.50"
        )
        print("✅ Datos semilla insertados correctamente.\n")

    # 3. Validar y ejecutar consultas
    print("=" * 70)
    print("📊 PRUEBAS DE CONSULTA Y RELACIONES (ORM)")
    print("=" * 70)
    with get_db() as session:
        # A) Listar Servidores con su Proyecto y Middlewares asociados
        servers = session.query(Server).all()
        print(f"\n[+] Total de Servidores registrados: {len(servers)}")
        for s in servers:
            prj_name = s.project.name if s.project else "Sin Proyecto"
            print(f"  • Host: {s.hostname} | IP: {s.ip_address} | SO: {s.os_name} {s.os_version or ''} | Proyecto: {prj_name} [{s.environment}]")
            for m in s.middlewares:
                print(f"    └── Middleware: {m.name} v{m.version} | Path: {m.install_path} | User: {m.run_user} | Status: {m.status}")

        # B) Listar Corta-Palos (Runbooks)
        runbooks = session.query(RunbookCommand).all()
        print(f"\n[+] Total de 'Corta-Palos' (Runbooks): {len(runbooks)}")
        for rb in runbooks:
            danger_tag = "⚠️ [PELIGROSO]" if rb.is_dangerous else "ℹ️ [SEGURO]"
            sudo_tag = "🔑 [SUDO]" if rb.requires_sudo else ""
            target = f"Host: {rb.server.hostname}" if rb.server else "Genérico"
            print(f"  • [{rb.category}] {rb.title} {danger_tag} {sudo_tag} ({target})")

        # C) Listar Bitácora de Incidentes
        incidents = session.query(IncidentLog).all()
        print(f"\n[+] Total de Incidentes en Bitácora: {len(incidents)}")
        for inc in incidents:
            print(f"  • Ref: {inc.ticket_ref} | Severidad: {inc.severity} | Estado: {inc.status} | Operador: {inc.operator_name}")
            print(f"    Título: {inc.title}")
            print(f"    Causa Raíz: {inc.root_cause}")

        # D) Listar Auditoría y Control de Versiones
        audit_records = session.query(AuditLog).all()
        print(f"\n[+] Registros de Auditoría y Control de Cambios: {len(audit_records)}")
        for log in audit_records:
            print(f"  • [{log.action}] {log.entity_type} ID #{log.entity_id} por '{log.user_name}' a las {log.created_at}")
            print(f"    Resumen: {log.summary}")
            if log.old_values and log.new_values:
                print("    Diferencias detectadas:")
                for k, v in log.new_values.items():
                    if log.old_values.get(k) != v:
                        print(f"      - {k}: '{log.old_values.get(k)}' ➔ '{v}'")

    print("\n" + "=" * 70)
    print("🎉 FASE 1 COMPLETADA CON ÉXITO: Base de datos SQLite lista para la Fase 2.")
    print("=" * 70)


if __name__ == "__main__":
    run_phase1_verification()

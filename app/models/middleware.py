from sqlalchemy import Column, String, Text, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class MiddlewareInstance(BaseModel):
    """
    Instancias de Middlewares, Servidores de Aplicaciones o Software instalados en un servidor.
    Ej: Oracle WebLogic, Apache Tomcat, IBM MQ, JBoss EAP, Apache HTTP, Nginx, etc.
    """
    __tablename__ = "middlewares"

    server_id = Column(Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(100), nullable=False, index=True)  # Ej: 'Oracle WebLogic', 'IBM MQ', 'Apache Tomcat'
    version = Column(String(50), nullable=True)  # Ej: '12.2.1.4', '9.2.0.5', '9.0.82'
    
    install_path = Column(String(255), nullable=False)  # Ej: '/u01/app/oracle/middleware'
    domain_or_instance = Column(String(100), nullable=True)  # Ej: 'domain_core_prod', 'QM_PAGOS_01'
    binary_path = Column(String(255), nullable=True)  # Ej: '/u01/app/oracle/domains/domain_core/bin'
    config_path = Column(String(255), nullable=True)  # Ej: '/u01/app/oracle/domains/domain_core/config/config.xml'
    
    service_name = Column(String(100), nullable=True)  # Ej: 'weblogic.service', 'ibm-mq'
    ports = Column(String(150), nullable=True)  # Ej: '7001 (Admin), 7002 (Managed1), 5556 (NodeMgr)'
    run_user = Column(String(50), nullable=True)  # Ej: 'oracle', 'mqm', 'tomcat'
    status = Column(String(20), default="RUNNING", nullable=False)  # RUNNING, STOPPED, DEGRADED, UNKNOWN
    notes = Column(Text, nullable=True)

    # Relaciones
    server = relationship("Server", back_populates="middlewares")
    runbooks = relationship("RunbookCommand", back_populates="middleware")
    incidents = relationship("IncidentLog", back_populates="middleware")

    def __repr__(self):
        return f"<Middleware {self.name} v{self.version} @ Server #{self.server_id}>"

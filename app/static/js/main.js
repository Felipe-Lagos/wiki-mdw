// Wiki-MDW Main JavaScript

document.addEventListener("DOMContentLoaded", () => {
    // 1. Botones para copiar comandos al portapapeles
    document.querySelectorAll(".btn-copy").forEach(button => {
        button.addEventListener("click", () => {
            const targetId = button.getAttribute("data-target");
            let textToCopy = "";
            
            if (targetId) {
                const targetElement = document.getElementById(targetId);
                if (targetElement) {
                    textToCopy = targetElement.innerText || targetElement.textContent;
                }
            } else if (button.getAttribute("data-clipboard-text")) {
                textToCopy = button.getAttribute("data-clipboard-text");
            }

            if (textToCopy) {
                navigator.clipboard.writeText(textToCopy.trim()).then(() => {
                    const originalHTML = button.innerHTML;
                    button.innerHTML = '<i class="bi bi-check-lg"></i> ¡Copiado!';
                    button.classList.add("btn-success");
                    setTimeout(() => {
                        button.innerHTML = originalHTML;
                        button.classList.remove("btn-success");
                    }, 2000);
                }).catch(err => {
                    console.error("Error al copiar al portapapeles:", err);
                });
            }
        });
    });

    // 2. Búsqueda Global Instantánea
    const searchInput = document.getElementById("globalSearchInput");
    const searchDropdown = document.getElementById("globalSearchResults");

    if (searchInput && searchDropdown) {
        let debounceTimer;

        searchInput.addEventListener("input", (e) => {
            clearTimeout(debounceTimer);
            const query = e.target.value.trim();

            if (query.length < 2) {
                searchDropdown.style.display = "none";
                searchDropdown.innerHTML = "";
                return;
            }

            debounceTimer = setTimeout(() => {
                fetch(`/api/v1/search?q=${encodeURIComponent(query)}`)
                    .then(res => res.json())
                    .then(data => {
                        if (data.results && data.results.length > 0) {
                            let html = "";
                            data.results.forEach(item => {
                                let badgeColor = "bg-primary";
                                if (item.type === "server") badgeColor = "bg-info text-dark";
                                if (item.type === "middleware") badgeColor = "bg-warning text-dark";
                                if (item.type === "runbook") badgeColor = "bg-success";
                                if (item.type === "incident") badgeColor = "bg-danger";

                                html += `
                                    <a href="${item.url}" class="search-result-item">
                                        <div class="d-flex align-items-center justify-content-between">
                                            <strong class="text-light">${item.title}</strong>
                                            <span class="badge ${badgeColor} text-uppercase" style="font-size: 0.65rem;">${item.type}</span>
                                        </div>
                                        <small class="text-muted">${item.subtitle}</small>
                                    </a>
                                `;
                            });
                            searchDropdown.innerHTML = html;
                            searchDropdown.style.display = "block";
                        } else {
                            searchDropdown.innerHTML = `<div class="p-3 text-center text-muted"><small>No se encontraron resultados para "${query}"</small></div>`;
                            searchDropdown.style.display = "block";
                        }
                    })
                    .catch(err => {
                        console.error("Error en búsqueda global:", err);
                    });
            }, 250);
        });

        // Cerrar dropdown al hacer clic fuera
        document.addEventListener("click", (e) => {
            if (!searchInput.contains(e.target) && !searchDropdown.contains(e.target)) {
                searchDropdown.style.display = "none";
            }
        });
    }

    // 3. Auto-ocultar alertas Flash después de 4 segundos
    document.querySelectorAll(".alert-dismissible").forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 4500);
    });
});

// Función global para mostrar el modal de auditoría
function showAuditDiff(auditId) {
    fetch(`/audit/${auditId}`)
        .then(res => res.json())
        .then(data => {
            document.getElementById("auditModalTitle").innerText = `Auditoría #${data.id} - ${data.action} en ${data.entity_type} (#${data.entity_id})`;
            document.getElementById("auditModalUser").innerText = `${data.user_name} (${data.ip_address || 'IP N/A'}) el ${data.created_at}`;
            document.getElementById("auditModalSummary").innerText = data.summary;

            const oldContainer = document.getElementById("auditModalOldValues");
            const newContainer = document.getElementById("auditModalNewValues");

            oldContainer.textContent = data.old_values ? JSON.stringify(data.old_values, null, 2) : "No disponible (Creación)";
            newContainer.textContent = data.new_values ? JSON.stringify(data.new_values, null, 2) : "No disponible (Eliminación)";

            const modal = new bootstrap.Modal(document.getElementById("auditDiffModal"));
            modal.show();
        })
        .catch(err => alert("Error al cargar detalles de auditoría: " + err));
}

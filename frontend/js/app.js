const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

let clientsCache = [];
let projectsCache = [];
let notificationTimer;

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[char]);
}

function showMessage(message, type = "success") {
    const box = $("#notification");
    box.textContent = message;
    box.className = `notification show ${type}`;
    clearTimeout(notificationTimer);
    notificationTimer = setTimeout(() => {
        box.className = "notification";
    }, 4500);
}

async function api(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            ...(options.body ? { "Content-Type": "application/json" } : {}),
            ...options.headers
        }
    });

    if (!response.ok) {
        let message = `Request failed (${response.status})`;
        try {
            const data = await response.json();
            message = typeof data.detail === "string"
                ? data.detail
                : JSON.stringify(data.detail ?? data);
        } catch {
            // Keep the fallback error message.
        }
        throw new Error(message);
    }

    if (response.status === 204) return null;
    return response.json();
}

function formData(form) {
    const data = Object.fromEntries(new FormData(form).entries());

    for (const key of Object.keys(data)) {
        if (typeof data[key] === "string") data[key] = data[key].trim();
        if (data[key] === "") delete data[key];
    }

    for (const key of ["client_id", "project_id"]) {
        if (data[key] !== undefined) data[key] = Number(data[key]);
    }

    if (data.budget !== undefined) data.budget = Number(data.budget);
    return data;
}

function dateText(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? escapeHTML(value) : date.toLocaleString();
}

function statusLabel(value) {
    return String(value ?? "")
        .replaceAll("_", " ")
        .replace(/\b\w/g, (char) => char.toUpperCase());
}

function emptyRow(message, columns) {
    return `<tr><td colspan="${columns}" class="empty-state">${escapeHTML(message)}</td></tr>`;
}

function goTo(viewName) {
    $$(".view").forEach((view) => {
        view.classList.toggle("active", view.id === `view-${viewName}`);
    });

    $$(".nav-item").forEach((button) => {
        button.classList.toggle("active", button.dataset.view === viewName);
    });

    const labels = {
        dashboard: "Dashboard",
        clients: "Clients",
        projects: "Projects",
        interactions: "Interactions"
    };

    $("#page-breadcrumb").textContent = labels[viewName] || "Dashboard";
    $("#sidebar").classList.remove("open");

    if (viewName === "dashboard") loadDashboard();
    if (viewName === "clients") loadClients();
    if (viewName === "projects") {
        refreshReferenceData().then(loadProjects).catch(handleError);
    }
    if (viewName === "interactions") {
        refreshReferenceData().then(loadInteractions).catch(handleError);
    }
}

function handleError(error) {
    showMessage(error.message || "Something went wrong.", "error");
}

function clientName(id) {
    return clientsCache.find((client) => client.id === Number(id))?.full_name
        || `Client #${id}`;
}

function projectName(id) {
    return projectsCache.find((project) => project.id === Number(id))?.title
        || `Project #${id}`;
}

async function refreshReferenceData() {
    [clientsCache, projectsCache] = await Promise.all([
        api("/api/clients"),
        api("/api/projects")
    ]);

    const clientOptions = clientsCache.map((client) =>
        `<option value="${client.id}">${escapeHTML(client.full_name)}</option>`
    ).join("");

    const projectClient = $("#project-client");
    const interactionClient = $("#interaction-client");
    const interactionProject = $("#interaction-project");

    projectClient.innerHTML =
        `<option value="">Choose a client</option>${clientOptions}`;
    interactionClient.innerHTML =
        `<option value="">Choose a client</option>${clientOptions}`;

    interactionProject.innerHTML =
        `<option value="">No specific project</option>` +
        projectsCache.map((project) =>
            `<option value="${project.id}" data-client="${project.client_id}">${escapeHTML(project.title)}</option>`
        ).join("");

    filterInteractionProjects();
}

function filterInteractionProjects() {
    const clientId = $("#interaction-client").value;
    [...$("#interaction-project").options].forEach((option) => {
        if (!option.value) {
            option.hidden = false;
            return;
        }
        option.hidden = Boolean(clientId) && option.dataset.client !== clientId;
    });

    const selected = $("#interaction-project").selectedOptions[0];
    if (selected?.hidden) $("#interaction-project").value = "";
}

async function loadDashboard() {
    try {
        const data = await api("/api/dashboard");

        $("#stat-clients").textContent = data.clients;
        $("#stat-projects").textContent = data.projects;
        $("#stat-active").textContent = data.active_projects;
        $("#stat-interactions").textContent = data.interactions;

        const rows = await Promise.all(data.recent_interactions.map(async (item) => {
            return `<tr>
                <td><strong>${escapeHTML(item.subject)}</strong>
                    <span class="table-subtext">${escapeHTML(statusLabel(item.interaction_type))}</span></td>
                <td>${escapeHTML(clientName(item.client_id))}</td>
                <td>${escapeHTML(dateText(item.occurred_at))}</td>
            </tr>`;
        }));

        $("#recent-interactions").innerHTML = rows.length
            ? `<table><thead><tr><th>Subject</th><th>Client</th><th>Date</th></tr></thead><tbody>${rows.join("")}</tbody></table>`
            : `<p class="empty-state">No interactions yet. Record your first client communication.</p>`;
    } catch (error) {
        $("#recent-interactions").innerHTML =
            `<p class="empty-state">Could not load dashboard data. Check the API and database.</p>`;
        handleError(error);
    }
}

async function loadClients(search = "") {
    try {
        clientsCache = await api(`/api/clients${search ? `?search=${encodeURIComponent(search)}` : ""}`);

        $("#clients-list").innerHTML = clientsCache.length
            ? `<table><thead><tr><th>Client</th><th>Company</th><th>Contact</th><th>Actions</th></tr></thead><tbody>
                ${clientsCache.map((client) => `<tr>
                    <td><strong>${escapeHTML(client.full_name)}</strong><span class="table-subtext">${escapeHTML(client.notes || "")}</span></td>
                    <td>${escapeHTML(client.company || "—")}</td>
                    <td>${escapeHTML(client.email || "—")}<span class="table-subtext">${escapeHTML(client.phone || "")}</span></td>
                    <td><div class="row-actions">
                        <button class="small-button" data-edit-client="${client.id}">Edit</button>
                        <button class="small-button danger" data-delete-client="${client.id}">Delete</button>
                    </div></td>
                </tr>`).join("")}
            </tbody></table>`
            : `<p class="empty-state">No clients found. Add a client using the form above.</p>`;

        await refreshReferenceData();
    } catch (error) {
        handleError(error);
    }
}

async function loadProjects() {
    try {
        projectsCache = await api("/api/projects");
        $("#projects-list").innerHTML = projectsCache.length
            ? `<table><thead><tr><th>Project</th><th>Client</th><th>Status</th><th>Budget</th><th>Due date</th><th>Actions</th></tr></thead><tbody>
                ${projectsCache.map((project) => `<tr>
                    <td><strong>${escapeHTML(project.title)}</strong><span class="table-subtext">${escapeHTML(project.description || "")}</span></td>
                    <td>${escapeHTML(clientName(project.client_id))}</td>
                    <td><span class="badge ${escapeHTML(project.status)}">${escapeHTML(statusLabel(project.status))}</span></td>
                    <td>${project.budget == null ? "—" : "₦" + Number(project.budget).toLocaleString()}</td>
                    <td>${escapeHTML(project.due_date || "—")}</td>
                    <td><div class="row-actions">
                        <button class="small-button" data-edit-project="${project.id}">Edit</button>
                        <button class="small-button danger" data-delete-project="${project.id}">Delete</button>
                    </div></td>
                </tr>`).join("")}
            </tbody></table>`
            : `<p class="empty-state">No projects yet. Create your first project above.</p>`;
    } catch (error) {
        handleError(error);
    }
}

async function loadInteractions() {
    try {
        const items = await api("/api/interactions");
        $("#interactions-list").innerHTML = items.length
            ? `<table><thead><tr><th>Subject</th><th>Client</th><th>Project</th><th>Type</th><th>Date</th><th>Actions</th></tr></thead><tbody>
                ${items.map((item) => `<tr>
                    <td><strong>${escapeHTML(item.subject)}</strong><span class="table-subtext">${escapeHTML(item.details || "")}</span></td>
                    <td>${escapeHTML(clientName(item.client_id))}</td>
                    <td>${escapeHTML(item.project_id ? projectName(item.project_id) : "—")}</td>
                    <td>${escapeHTML(statusLabel(item.interaction_type))}</td>
                    <td>${escapeHTML(dateText(item.occurred_at))}</td>
                    <td><button class="small-button danger" data-delete-interaction="${item.id}">Delete</button></td>
                </tr>`).join("")}
            </tbody></table>`
            : `<p class="empty-state">No interactions recorded yet.</p>`;
    } catch (error) {
        handleError(error);
    }
}

$("#client-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
        await api("/api/clients", {
            method: "POST",
            body: JSON.stringify(formData(event.currentTarget))
        });
        event.currentTarget.reset();
        showMessage("Client saved successfully.");
        await loadClients($("#client-search").value.trim());
        loadDashboard();
    } catch (error) {
        handleError(error);
    }
});

$("#project-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
        await api("/api/projects", {
            method: "POST",
            body: JSON.stringify(formData(event.currentTarget))
        });
        event.currentTarget.reset();
        showMessage("Project saved successfully.");
        await refreshReferenceData();
        await loadProjects();
        loadDashboard();
    } catch (error) {
        handleError(error);
    }
});

$("#interaction-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
        await api("/api/interactions", {
            method: "POST",
            body: JSON.stringify(formData(event.currentTarget))
        });
        event.currentTarget.reset();
        showMessage("Interaction saved successfully.");
        await refreshReferenceData();
        await loadInteractions();
        loadDashboard();
    } catch (error) {
        handleError(error);
    }
});

$("#interaction-client").addEventListener("change", filterInteractionProjects);

$("#client-search").addEventListener("input", (event) => {
    loadClients(event.currentTarget.value.trim());
});

document.addEventListener("click", async (event) => {
    const navigation = event.target.closest("[data-view]");
    const goButton = event.target.closest("[data-go]");

    if (navigation) goTo(navigation.dataset.view);
    if (goButton) goTo(goButton.dataset.go);

    const editClient = event.target.closest("[data-edit-client]");
    const deleteClient = event.target.closest("[data-delete-client]");
    const editProject = event.target.closest("[data-edit-project]");
    const deleteProject = event.target.closest("[data-delete-project]");
    const deleteInteraction = event.target.closest("[data-delete-interaction]");

    try {
        if (editClient) {
            const id = Number(editClient.dataset.editClient);
            const client = clientsCache.find((item) => item.id === id);
            if (!client) return;
            const full_name = prompt("Client full name:", client.full_name);
            if (full_name === null) return;
            if (!full_name.trim()) return showMessage("Name cannot be empty.", "error");
            const email = prompt("Email (leave blank to clear):", client.email || "");
            if (email === null) return;
            const phone = prompt("Phone:", client.phone || "");
            if (phone === null) return;
            const company = prompt("Company:", client.company || "");
            if (company === null) return;
            const notes = prompt("Notes:", client.notes || "");
            if (notes === null) return;

            await api(`/api/clients/${id}`, {
                method: "PATCH",
                body: JSON.stringify({
                    full_name: full_name.trim(),
                    email: email.trim() || null,
                    phone: phone.trim() || null,
                    company: company.trim() || null,
                    notes: notes.trim() || null
                })
            });
            showMessage("Client updated successfully.");
            await loadClients($("#client-search").value.trim());
            loadDashboard();
        }

        if (deleteClient) {
            const id = Number(deleteClient.dataset.deleteClient);
            if (!confirm("Delete this client and their associated projects and interactions? This cannot be undone.")) return;
            await api(`/api/clients/${id}`, { method: "DELETE" });
            showMessage("Client deleted.");
            await loadClients($("#client-search").value.trim());
            loadDashboard();
        }

        if (editProject) {
            const id = Number(editProject.dataset.editProject);
            const project = projectsCache.find((item) => item.id === id);
            if (!project) return;
            const title = prompt("Project title:", project.title);
            if (title === null) return;
            if (!title.trim()) return showMessage("Title cannot be empty.", "error");
            const statuses = ["planned", "in_progress", "completed", "on_hold"];
            const status = prompt(`Status (${statuses.join(", ")}):`, project.status);
            if (status === null) return;
            if (!statuses.includes(status)) return showMessage("Invalid project status.", "error");
            const budgetText = prompt("Budget (leave blank to clear):", project.budget ?? "");
            if (budgetText === null) return;
            const due_date = prompt("Due date (YYYY-MM-DD, blank to clear):", project.due_date || "");
            if (due_date === null) return;

            await api(`/api/projects/${id}`, {
                method: "PATCH",
                body: JSON.stringify({
                    title: title.trim(),
                    status,
                    budget: budgetText.trim() ? Number(budgetText) : null,
                    due_date: due_date.trim() || null
                })
            });
            showMessage("Project updated successfully.");
            await refreshReferenceData();
            await loadProjects();
            loadDashboard();
        }

        if (deleteProject) {
            const id = Number(deleteProject.dataset.deleteProject);
            if (!confirm("Delete this project? Related interaction records will remain without a project link.")) return;
            await api(`/api/projects/${id}`, { method: "DELETE" });
            showMessage("Project deleted.");
            await refreshReferenceData();
            await loadProjects();
            loadInteractions();
            loadDashboard();
        }

        if (deleteInteraction) {
            const id = Number(deleteInteraction.dataset.deleteInteraction);
            if (!confirm("Delete this interaction record?")) return;
            await api(`/api/interactions/${id}`, { method: "DELETE" });
            showMessage("Interaction deleted.");
            await loadInteractions();
            loadDashboard();
        }
    } catch (error) {
        handleError(error);
    }
});

$("#menu-button").addEventListener("click", () => {
    $("#sidebar").classList.toggle("open");
});

async function startApp() {
    try {
        await refreshReferenceData();
        await Promise.all([loadDashboard(), loadClients(), loadProjects(), loadInteractions()]);
    } catch (error) {
        handleError(error);
    }
}

startApp();

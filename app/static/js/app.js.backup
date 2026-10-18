const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

let clientsCache = [];
let projectsCache = [];
let notificationTimer;
let searchTimer;

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
    if (!box) return;

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

    if (response.status === 201 || response.status === 200) {
        const contentType = response.headers.get("content-type") || "";

        return contentType.includes("application/json")
            ? response.json()
            : null;
    }

    return null;
}

function formData(form) {
    const data = Object.fromEntries(new FormData(form).entries());

    for (const key of Object.keys(data)) {
        if (typeof data[key] === "string") {
            data[key] = data[key].trim();
        }

        if (data[key] === "") {
            delete data[key];
        }
    }

    for (const key of ["client_id", "project_id"]) {
        if (data[key] !== undefined) {
            data[key] = Number(data[key]);
        }
    }

    if (data.budget !== undefined) {
        data.budget = Number(data.budget);
    }

    return data;
}

function dateText(value) {
    if (!value) return "—";

    const date = new Date(value);

    return Number.isNaN(date.getTime())
        ? escapeHTML(value)
        : date.toLocaleString();
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
        const active = button.dataset.view === viewName;

        button.classList.toggle("active", active);

        if (active) {
            button.setAttribute("aria-current", "page");
        } else {
            button.removeAttribute("aria-current");
        }
    });

    const labels = {
        dashboard: "Dashboard",
        clients: "Clients",
        projects: "Projects",
        interactions: "Interactions"
    };

    $("#page-breadcrumb").textContent = labels[viewName] || "Dashboard";

    $("#sidebar").classList.remove("open");
    $("#menu-button").setAttribute("aria-expanded", "false");

    if (viewName === "dashboard") {
        loadDashboard();
    }

    if (viewName === "clients") {
        loadClients($("#client-search").value.trim());
    }

    if (viewName === "projects") {
        refreshReferenceData()
            .then(loadProjects)
            .catch(handleError);
    }

    if (viewName === "interactions") {
        refreshReferenceData()
            .then(loadInteractions)
            .catch(handleError);
    }
}

function handleError(error) {
    showMessage(
        error.message || "Something went wrong. Please try again.",
        "error"
    );
}

function clientName(id) {
    return clientsCache.find(
        (client) => client.id === Number(id)
    )?.full_name || `Client #${id}`;
}

function projectName(id) {
    return projectsCache.find(
        (project) => project.id === Number(id)
    )?.title || `Project #${id}`;
}

async function refreshReferenceData() {
    const [clients, projects] = await Promise.all([
        api("/api/clients"),
        api("/api/projects")
    ]);

    clientsCache = Array.isArray(clients) ? clients : [];
    projectsCache = Array.isArray(projects) ? projects : [];

    const clientOptions = clientsCache.map((client) =>
        `<option value="${client.id}">${escapeHTML(client.full_name)}</option>`
    ).join("");

    const projectClient = $("#project-client");
    const interactionClient = $("#interaction-client");
    const interactionProject = $("#interaction-project");

    if (projectClient) {
        const previousValue = projectClient.value;

        projectClient.innerHTML =
            `<option value="">Choose a client</option>${clientOptions}`;

        if ([...projectClient.options].some(
            (option) => option.value === previousValue
        )) {
            projectClient.value = previousValue;
        }
    }

    if (interactionClient) {
        const previousValue = interactionClient.value;

        interactionClient.innerHTML =
            `<option value="">Choose a client</option>${clientOptions}`;

        if ([...interactionClient.options].some(
            (option) => option.value === previousValue
        )) {
            interactionClient.value = previousValue;
        }
    }

    if (interactionProject) {
        const previousValue = interactionProject.value;

        interactionProject.innerHTML =
            `<option value="">No specific project</option>` +
            projectsCache.map((project) =>
                `<option value="${project.id}" data-client="${project.client_id}">${escapeHTML(project.title)}</option>`
            ).join("");

        if ([...interactionProject.options].some(
            (option) => option.value === previousValue
        )) {
            interactionProject.value = previousValue;
        }
    }

    filterInteractionProjects();
}

function filterInteractionProjects() {
    const clientSelect = $("#interaction-client");
    const projectSelect = $("#interaction-project");

    if (!clientSelect || !projectSelect) return;

    const clientId = clientSelect.value;

    [...projectSelect.options].forEach((option) => {
        if (!option.value) {
            option.hidden = false;
            return;
        }

        option.hidden = Boolean(clientId) &&
            option.dataset.client !== clientId;
    });

    const selected = projectSelect.selectedOptions[0];

    if (selected?.hidden) {
        projectSelect.value = "";
    }
}

async function loadDashboard() {
    try {
        const data = await api("/api/dashboard");

        $("#stat-clients").textContent = data.clients ?? 0;
        $("#stat-projects").textContent = data.projects ?? 0;
        $("#stat-active").textContent = data.active_projects ?? 0;
        $("#stat-interactions").textContent = data.interactions ?? 0;

        const recent = Array.isArray(data.recent_interactions)
            ? data.recent_interactions
            : [];

        const rows = recent.map((item) => `<tr>
            <td>
                <strong>${escapeHTML(item.subject)}</strong>
                <span class="table-subtext">${escapeHTML(statusLabel(item.interaction_type))}</span>
            </td>
            <td>${escapeHTML(clientName(item.client_id))}</td>
            <td>${escapeHTML(dateText(item.occurred_at))}</td>
        </tr>`);

        $("#recent-interactions").innerHTML = rows.length
            ? `<table>
                <thead>
                    <tr>
                        <th>Subject</th>
                        <th>Client</th>
                        <th>Date</th>
                    </tr>
                </thead>
                <tbody>${rows.join("")}</tbody>
            </table>`
            : `<p class="empty-state">No interactions yet. Record your first client communication.</p>`;

    } catch (error) {
        $("#recent-interactions").innerHTML =
            `<p class="empty-state">Could not load dashboard data. Check that the API and database are running.</p>`;

        handleError(error);
    }
}

async function loadClients(search = "") {
    try {
        const result = await api(
            `/api/clients${search ? `?search=${encodeURIComponent(search)}` : ""}`
        );

        clientsCache = Array.isArray(result) ? result : [];

        $("#clients-list").innerHTML = clientsCache.length
            ? `<table>
                <thead>
                    <tr>
                        <th>Client</th>
                        <th>Company</th>
                        <th>Contact</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${clientsCache.map((client) => `<tr>
                        <td>
                            <strong>${escapeHTML(client.full_name)}</strong>
                            <span class="table-subtext">${escapeHTML(client.notes || "")}</span>
                        </td>
                        <td>${escapeHTML(client.company || "—")}</td>
                        <td>
                            ${escapeHTML(client.email || "—")}
                            <span class="table-subtext">${escapeHTML(client.phone || "")}</span>
                        </td>
                        <td>
                            <div class="row-actions">
                                <button class="small-button" data-edit-client="${client.id}">Edit</button>
                                <button class="small-button danger" data-delete-client="${client.id}">Delete</button>
                            </div>
                        </td>
                    </tr>`).join("")}
                </tbody>
            </table>`
            : `<p class="empty-state">No clients found. Add a client using the form above.</p>`;

        await refreshReferenceData();

    } catch (error) {
        handleError(error);
    }
}

async function loadProjects() {
    try {
        const result = await api("/api/projects");

        projectsCache = Array.isArray(result) ? result : [];

        $("#projects-list").innerHTML = projectsCache.length
            ? `<table>
                <thead>
                    <tr>
                        <th>Project</th>
                        <th>Client</th>
                        <th>Status</th>
                        <th>Budget</th>
                        <th>Due date</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${projectsCache.map((project) => `<tr>
                        <td>
                            <strong>${escapeHTML(project.title)}</strong>
                            <span class="table-subtext">${escapeHTML(project.description || "")}</span>
                        </td>
                        <td>${escapeHTML(clientName(project.client_id))}</td>
                        <td>
                            <span class="badge ${escapeHTML(project.status)}">${escapeHTML(statusLabel(project.status))}</span>
                        </td>
                        <td>${project.budget == null
                            ? "—"
                            : "₦" + Number(project.budget).toLocaleString("en-NG")}
                        </td>
                        <td>${escapeHTML(project.due_date || "—")}</td>
                        <td>
                            <div class="row-actions">
                                <button class="small-button" data-edit-project="${project.id}">Edit</button>
                                <button class="small-button danger" data-delete-project="${project.id}">Delete</button>
                            </div>
                        </td>
                    </tr>`).join("")}
                </tbody>
            </table>`
            : `<p class="empty-state">No projects yet. Create your first project above.</p>`;

    } catch (error) {
        handleError(error);
    }
}

async function loadInteractions() {
    try {
        const result = await api("/api/interactions");
        const items = Array.isArray(result) ? result : [];

        $("#interactions-list").innerHTML = items.length
            ? `<table>
                <thead>
                    <tr>
                        <th>Subject</th>
                        <th>Client</th>
                        <th>Project</th>
                        <th>Type</th>
                        <th>Date</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${items.map((item) => `<tr>
                        <td>
                            <strong>${escapeHTML(item.subject)}</strong>
                            <span class="table-subtext">${escapeHTML(item.details || "")}</span>
                        </td>
                        <td>${escapeHTML(clientName(item.client_id))}</td>
                        <td>${escapeHTML(item.project_id ? projectName(item.project_id) : "—")}</td>
                        <td>${escapeHTML(statusLabel(item.interaction_type))}</td>
                        <td>${escapeHTML(dateText(item.occurred_at))}</td>
                        <td>
                            <button class="small-button danger" data-delete-interaction="${item.id}">Delete</button>
                        </td>
                    </tr>`).join("")}
                </tbody>
            </table>`
            : `<p class="empty-state">No interactions recorded yet.</p>`;

    } catch (error) {
        handleError(error);
    }
}

/* Create a client */
$("#client-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    const form = event.currentTarget;

    try {
        await api("/api/clients", {
            method: "POST",
            body: JSON.stringify(formData(form))
        });

        form.reset();

        showMessage("Client saved successfully.");

        await loadClients($("#client-search").value.trim());
        await loadDashboard();

    } catch (error) {
        handleError(error);
    }
});

/* Create a project */
$("#project-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    const form = event.currentTarget;

    try {
        await api("/api/projects", {
            method: "POST",
            body: JSON.stringify(formData(form))
        });

        form.reset();

        showMessage("Project saved successfully.");

        await refreshReferenceData();
        await loadProjects();
        await loadDashboard();

    } catch (error) {
        handleError(error);
    }
});

/* Record an interaction */
$("#interaction-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    const form = event.currentTarget;

    try {
        await api("/api/interactions", {
            method: "POST",
            body: JSON.stringify(formData(form))
        });

        form.reset();

        showMessage("Interaction saved successfully.");

        await refreshReferenceData();
        await loadInteractions();
        await loadDashboard();

    } catch (error) {
        handleError(error);
    }
});

/* Update available projects when the selected client changes */
$("#interaction-client").addEventListener(
    "change",
    filterInteractionProjects
);

/* Search clients without sending a request on every keystroke */
$("#client-search").addEventListener("input", (event) => {
    clearTimeout(searchTimer);

    const value = event.currentTarget.value.trim();

    searchTimer = setTimeout(() => {
        loadClients(value);
    }, 250);
});

/* Handle navigation, edits and deletions */
document.addEventListener("click", async (event) => {
    const navigation = event.target.closest("[data-view]");
    const goButton = event.target.closest("[data-go]");

    if (navigation) {
        goTo(navigation.dataset.view);
    }

    if (goButton) {
        goTo(goButton.dataset.go);
    }

    const editClient = event.target.closest("[data-edit-client]");
    const deleteClient = event.target.closest("[data-delete-client]");
    const editProject = event.target.closest("[data-edit-project]");
    const deleteProject = event.target.closest("[data-delete-project]");
    const deleteInteraction = event.target.closest("[data-delete-interaction]");

    try {
        /* Edit client */
        if (editClient) {
            const id = Number(editClient.dataset.editClient);

            const client = clientsCache.find(
                (item) => item.id === id
            );

            if (!client) return;

            const full_name = prompt(
                "Client full name:",
                client.full_name
            );

            if (full_name === null) return;

            if (!full_name.trim()) {
                return showMessage("Name cannot be empty.", "error");
            }

            const email = prompt(
                "Email (leave blank to clear):",
                client.email || ""
            );

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
            await loadDashboard();
        }

        /* Delete client */
        if (deleteClient) {
            const id = Number(deleteClient.dataset.deleteClient);

            if (!confirm(
                "Delete this client and their associated projects and interactions? This cannot be undone."
            )) {
                return;
            }

            await api(`/api/clients/${id}`, {
                method: "DELETE"
            });

            showMessage("Client deleted.");

            await loadClients($("#client-search").value.trim());
            await loadDashboard();
        }

        /* Edit project */
        if (editProject) {
            const id = Number(editProject.dataset.editProject);

            const project = projectsCache.find(
                (item) => item.id === id
            );

            if (!project) return;

            const title = prompt(
                "Project title:",
                project.title
            );

            if (title === null) return;

            if (!title.trim()) {
                return showMessage("Title cannot be empty.", "error");
            }

            const statuses = [
                "planned",
                "in_progress",
                "completed",
                "on_hold"
            ];

            const status = prompt(
                `Status (${statuses.join(", ")}):`,
                project.status
            );

            if (status === null) return;

            if (!statuses.includes(status)) {
                return showMessage("Invalid project status.", "error");
            }

            const budgetText = prompt(
                "Budget (leave blank to clear):",
                project.budget ?? ""
            );

            if (budgetText === null) return;

            const due_date = prompt(
                "Due date (YYYY-MM-DD, blank to clear):",
                project.due_date || ""
            );

            if (due_date === null) return;

            const budget = budgetText.trim()
                ? Number(budgetText)
                : null;

            if (
                budget !== null &&
                (!Number.isFinite(budget) || budget < 0)
            ) {
                return showMessage(
                    "Enter a valid non-negative budget.",
                    "error"
                );
            }

            await api(`/api/projects/${id}`, {
                method: "PATCH",
                body: JSON.stringify({
                    title: title.trim(),
                    status,
                    budget,
                    due_date: due_date.trim() || null
                })
            });

            showMessage("Project updated successfully.");

            await refreshReferenceData();
            await loadProjects();
            await loadDashboard();
        }

        /* Delete project */
        if (deleteProject) {
            const id = Number(deleteProject.dataset.deleteProject);

            if (!confirm(
                "Delete this project? Related interaction records will remain without a project link."
            )) {
                return;
            }

            await api(`/api/projects/${id}`, {
                method: "DELETE"
            });

            showMessage("Project deleted.");

            await refreshReferenceData();
            await loadProjects();
            await loadInteractions();
            await loadDashboard();
        }

        /* Delete interaction */
        if (deleteInteraction) {
            const id = Number(
                deleteInteraction.dataset.deleteInteraction
            );

            if (!confirm("Delete this interaction record?")) {
                return;
            }

            await api(`/api/interactions/${id}`, {
                method: "DELETE"
            });

            showMessage("Interaction deleted.");

            await loadInteractions();
            await loadDashboard();
        }

    } catch (error) {
        handleError(error);
    }
});

/* Mobile navigation */
$("#menu-button").addEventListener("click", () => {
    const sidebar = $("#sidebar");
    const isOpen = sidebar.classList.toggle("open");

    $("#menu-button").setAttribute(
        "aria-expanded",
        String(isOpen)
    );
});

/* Close the mobile navigation with Escape */
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
        $("#sidebar").classList.remove("open");

        $("#menu-button").setAttribute(
            "aria-expanded",
            "false"
        );
    }
});

/* Start the application */
async function startApp() {
    try {
        await refreshReferenceData();

        await Promise.all([
            loadDashboard(),
            loadClients(),
            loadProjects(),
            loadInteractions()
        ]);

    } catch (error) {
        handleError(error);
    }
}

startApp();
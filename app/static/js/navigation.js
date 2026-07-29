const activeNavigationKey = "smartStoreActiveNavigation";
const activeSidebarKey = "smartStoreActiveSidebarItem";
const sidebarCollapsedKey = "smartStoreSidebarCollapsed";
const themeStorageKey = "smartStoreTheme";
const headerNavItems = document.querySelectorAll("[data-header-nav-item]");
const topNavItems = document.querySelectorAll("[data-top-nav-item]");
const sidebarItems = document.querySelectorAll("[data-sidebar-item]");
const appNavbar = document.querySelector(".app-navbar");
const sidebarToggle = document.querySelector("[data-sidebar-toggle]");
const darkModeToggle = document.getElementById("darkModeToggle");
const sidebarTooltips = [];

function showPageLoader() {
    document.body.classList.add("is-page-loading");
}

function hidePageLoader() {
    document.body.classList.remove("is-page-loading");
}

function shouldShowPageLoader(event, link) {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
        return false;
    }

    if (!link || (link.target && link.target !== "_self") || link.hasAttribute("download")) {
        return false;
    }

    const href = link.getAttribute("href");
    if (!href || href.startsWith("#")) {
        return false;
    }

    const destination = new URL(link.href, window.location.href);
    return destination.origin === window.location.origin;
}

function attachPageLoader(link) {
    link.addEventListener("click", (event) => {
        if (shouldShowPageLoader(event, link)) {
            showPageLoader();
        }
    });
}

function updateAppNavbarHeight() {
    if (!appNavbar) {
        return;
    }

    document.documentElement.style.setProperty("--app-navbar-height", `${appNavbar.offsetHeight}px`);
}

function applyTheme(theme) {
    const normalizedTheme = theme === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", normalizedTheme);
    localStorage.setItem(themeStorageKey, normalizedTheme);

    if (darkModeToggle) {
        darkModeToggle.checked = normalizedTheme === "dark";
    }
}

function setSidebarCollapsed(isCollapsed) {
    document.body.classList.toggle("is-sidebar-collapsed", isCollapsed);
    localStorage.setItem(sidebarCollapsedKey, isCollapsed ? "true" : "false");

    if (sidebarToggle) {
        sidebarToggle.setAttribute("aria-expanded", String(!isCollapsed));
        sidebarToggle.setAttribute("aria-label", isCollapsed ? "Expand sidebar" : "Collapse sidebar");
    }

    sidebarTooltips.forEach((tooltip) => {
        if (isCollapsed) {
            tooltip.enable();
        } else {
            tooltip.hide();
            tooltip.disable();
        }
    });
}

function initializeSidebarTooltips() {
    if (!window.bootstrap || !window.bootstrap.Tooltip) {
        return;
    }

    sidebarItems.forEach((item) => {
        sidebarTooltips.push(new window.bootstrap.Tooltip(item, {
            container: "body",
            trigger: "hover focus"
        }));
    });
}

function clearHeaderNavItems() {
    headerNavItems.forEach((item) => {
        item.classList.remove("active");
        item.removeAttribute("aria-current");
    });
}

function clearTopNavItems() {
    topNavItems.forEach((item) => {
        item.classList.remove("active");
        item.removeAttribute("aria-current");
    });
}

function clearSidebarItems() {
    sidebarItems.forEach((item) => {
        item.classList.remove("active");
        item.setAttribute("aria-pressed", "false");
    });
}

function setActiveHeaderNavItem(activeItem) {
    headerNavItems.forEach((item) => {
        const isActive = item === activeItem;
        item.classList.toggle("active", isActive);
        if (isActive) {
            item.setAttribute("aria-current", "page");
        } else {
            item.removeAttribute("aria-current");
        }
    });
}

function setActiveTopNavItem(activeItem) {
    topNavItems.forEach((item) => {
        const isActive = item === activeItem;
        item.classList.toggle("active", isActive);
        if (isActive) {
            item.setAttribute("aria-current", "page");
        } else {
            item.removeAttribute("aria-current");
        }
    });
}

function setActiveSidebarItem(activeItem) {
    sidebarItems.forEach((item) => {
        const isActive = item === activeItem;
        item.classList.toggle("active", isActive);
        item.setAttribute("aria-pressed", String(isActive));
    });
}

function activateHeaderNavItem(item) {
    setActiveHeaderNavItem(item);
    clearTopNavItems();
    clearSidebarItems();
    localStorage.setItem(activeNavigationKey, "header");
    localStorage.removeItem(activeSidebarKey);
}

function activateSidebarItem(item) {
    clearHeaderNavItems();
    clearTopNavItems();
    setActiveSidebarItem(item);
    localStorage.setItem(activeNavigationKey, "sidebar");
    localStorage.setItem(activeSidebarKey, item.dataset.sidebarItem);
}

function activateTopNavItem(item) {
    clearHeaderNavItems();
    setActiveTopNavItem(item);
    clearSidebarItems();
    localStorage.setItem(activeNavigationKey, "top");
    localStorage.removeItem(activeSidebarKey);
}

if (localStorage.getItem(activeNavigationKey) === "header") {
    const activeHeaderItem = document.querySelector("[data-header-nav-item].active") || headerNavItems[0];
    clearTopNavItems();
    clearSidebarItems();
    if (activeHeaderItem) {
        setActiveHeaderNavItem(activeHeaderItem);
    }
} else if (localStorage.getItem(activeNavigationKey) === "sidebar") {
    const storedSidebarItem = localStorage.getItem(activeSidebarKey);
    const initialSidebarItem = storedSidebarItem
        ? document.querySelector(`[data-sidebar-item="${storedSidebarItem}"]`)
        : null;

    clearHeaderNavItems();
    clearTopNavItems();
    if (initialSidebarItem) {
        setActiveSidebarItem(initialSidebarItem);
    }
} else {
    clearHeaderNavItems();
    clearSidebarItems();
}

headerNavItems.forEach((item) => {
    item.addEventListener("click", () => activateHeaderNavItem(item));
    attachPageLoader(item);
});

topNavItems.forEach((item) => {
    item.addEventListener("click", () => activateTopNavItem(item));
    attachPageLoader(item);
});

sidebarItems.forEach((item) => {
    item.setAttribute("aria-pressed", String(item.classList.contains("active")));
    item.addEventListener("click", () => activateSidebarItem(item));
    item.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            activateSidebarItem(item);
        }
    });
});

initializeSidebarTooltips();
setSidebarCollapsed(localStorage.getItem(sidebarCollapsedKey) === "true");
applyTheme(localStorage.getItem(themeStorageKey) || document.documentElement.getAttribute("data-theme"));

if (sidebarToggle) {
    sidebarToggle.addEventListener("click", () => {
        setSidebarCollapsed(!document.body.classList.contains("is-sidebar-collapsed"));
    });
}

if (darkModeToggle) {
    darkModeToggle.addEventListener("change", () => {
        applyTheme(darkModeToggle.checked ? "dark" : "light");
    });
}

updateAppNavbarHeight();
window.addEventListener("load", updateAppNavbarHeight);
window.addEventListener("pageshow", hidePageLoader);
window.addEventListener("resize", updateAppNavbarHeight);

if (appNavbar) {
    appNavbar.addEventListener("shown.bs.collapse", updateAppNavbarHeight);
    appNavbar.addEventListener("hidden.bs.collapse", updateAppNavbarHeight);
}
